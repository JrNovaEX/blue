from __future__ import annotations

import sys

import click

from .api import APIError, ExiurAPI
from .config import (
    clear_session,
    is_initialized,
    is_logged_in,
    load_config,
    save_config,
    update_config,
)
from .menu import run_menu
from .ui import console, die, ok, table_from_rows


# ---------------------------------------------------------------------------
# Root group -- runs a health check before every command except `init`.
# ---------------------------------------------------------------------------

@click.group(invoke_without_command=True)
@click.pass_context
def cli(ctx: click.Context):
    """exiur -- terminal admin tool for the BlueGuard 'exiur' panel.

    Run with no arguments (`exiur`) to get an interactive menu instead of
    typing subcommands by hand.
    """
    ctx.ensure_object(dict)
    cfg = load_config()
    ctx.obj["cfg"] = cfg

    if ctx.invoked_subcommand in ("init",):
        return

    # Don't gate --help behind init/health -- let people read the docs.
    if {"--help", "-h"} & set(sys.argv[1:]):
        return

    if not is_initialized(cfg):
        die("Not initialized yet. Run `exiur init` first.")

    api = ExiurAPI(cfg)
    ctx.obj["api"] = api

    try:
        health = api.health()
    except APIError as e:
        die(f"BlueGuard is unreachable ({e}). Aborting.")
        return

    if health.get("status") != "ok":
        die(f"BlueGuard is up but unhealthy, refusing to run commands. Raw response: {health}")

    # `exiur` with no subcommand at all -> interactive menu.
    if ctx.invoked_subcommand is None:
        run_menu(cfg, api)


# ---------------------------------------------------------------------------
# init / health / whoami
# ---------------------------------------------------------------------------

@cli.command()
def init():
    """Configure the server URL and the exiur panel id (one-time setup)."""
    server = click.prompt("BlueGuard server URL", default="http://localhost:4000/api/v1")
    panel_id = click.prompt("exiur panel ID (UUID)")

    cfg = update_config(server=server.rstrip("/"), panel_id=panel_id)

    console.print("Checking connection...")
    try:
        health = ExiurAPI(cfg).health()
    except APIError as e:
        console.print(f"[yellow]⚠ Saved config, but could not reach the server: {e}[/]")
        return

    if health.get("status") == "ok":
        ok(f"Configured. Connected to {server}, panel {panel_id}.")
    else:
        console.print("[yellow]⚠ Saved config, but server reports it's unhealthy.[/]")


@cli.command()
@click.pass_context
def health(ctx: click.Context):
    """Check BlueGuard health (already checked automatically, this just prints it)."""
    api: ExiurAPI = ctx.obj["api"]
    h = api.health()
    ok(f"status={h.get('status')} db={h.get('details', {}).get('database', {})}")


@cli.command()
@click.pass_context
def whoami(ctx: click.Context):
    """Show the currently logged-in user."""
    cfg = ctx.obj["cfg"]
    if not is_logged_in(cfg):
        die("Not logged in. Run `exiur login`.")
    api: ExiurAPI = ctx.obj["api"]
    try:
        me = api.me()
    except APIError as e:
        die(str(e))
        return
    console.print(me)


# ---------------------------------------------------------------------------
# auth: login / logout
# ---------------------------------------------------------------------------

@cli.command()
@click.option("--username", prompt=True)
@click.option("--password", prompt=True, hide_input=True)
@click.pass_context
def login(ctx: click.Context, username: str, password: str):
    """Log in and persist the session locally (~/.exiur/config.json)."""
    api: ExiurAPI = ctx.obj["api"]
    try:
        api.login(username, password)
    except APIError as e:
        die(f"Login failed: {e}")
        return
    ok(f"Logged in as {username}.")


@cli.command()
@click.pass_context
def logout(ctx: click.Context):
    """Log out and clear the local session."""
    cfg = ctx.obj["cfg"]
    api: ExiurAPI = ctx.obj["api"]
    try:
        api.logout()
    except APIError:
        pass  # still clear local session even if the server call fails
    clear_session(cfg)
    ok("Logged out.")


# ---------------------------------------------------------------------------
# admins: users that hold the ADMIN role in the exiur panel
# ---------------------------------------------------------------------------

@cli.group()
def admins():
    """Manage panel admins (users with the ADMIN role)."""


@admins.command("list")
@click.pass_context
def admins_list(ctx: click.Context):
    """List members of the panel who hold the ADMIN role."""
    api: ExiurAPI = ctx.obj["api"]
    try:
        roles = api.list_roles()
        admin_role = next((r for r in roles if r.get("level") == "ADMIN"), None)
        members = api.list_members(limit=100)
    except APIError as e:
        die(str(e))
        return

    rows = members.get("data", members) if isinstance(members, dict) else members
    if admin_role:
        rows = [
            m for m in rows
            if m.get("roleId") == admin_role.get("id") or m.get("role", {}).get("level") == "ADMIN"
        ]
    if not rows:
        console.print("No admins found.")
        return
    console.print(table_from_rows("Panel Admins", rows, ["userId", "username", "roleId"]))


@admins.command("add")
@click.option("--username", required=True)
@click.option("--email", required=True)
@click.option("--password", required=True, prompt=True, hide_input=True, confirmation_prompt=True)
@click.option("--display", "display_name", default=None)
@click.pass_context
def admins_add(ctx: click.Context, username: str, email: str, password: str, display_name: str | None):
    """Create a brand-new user and add them to the panel as ADMIN."""
    api: ExiurAPI = ctx.obj["api"]
    try:
        admin_role = api.find_role_by_level("ADMIN")
        if not admin_role:
            die("No ADMIN role found in this panel. Create one first with the BlueGuard `bg roles create` tool.")
            return
        user = api.create_user(username, email, password, display_name, role_id=admin_role["id"])
    except APIError as e:
        die(str(e))
        return
    ok(f"Created admin '{username}' (id={user.get('id')}).")


@admins.command("promote")
@click.option("--user-id", required=True)
@click.pass_context
def admins_promote(ctx: click.Context, user_id: str):
    """Give an existing user the ADMIN role in this panel."""
    api: ExiurAPI = ctx.obj["api"]
    try:
        admin_role = api.find_role_by_level("ADMIN")
        if not admin_role:
            die("No ADMIN role found in this panel.")
            return
        api.set_member_role(user_id, admin_role["id"])
    except APIError as e:
        die(str(e))
        return
    ok(f"User {user_id} promoted to ADMIN.")


@admins.command("demote")
@click.option("--user-id", required=True)
@click.pass_context
def admins_demote(ctx: click.Context, user_id: str):
    """Drop a user's role back down to USER in this panel."""
    api: ExiurAPI = ctx.obj["api"]
    try:
        user_role = api.find_role_by_level("USER")
        if not user_role:
            die("No USER role found in this panel.")
            return
        api.set_member_role(user_id, user_role["id"])
    except APIError as e:
        die(str(e))
        return
    ok(f"User {user_id} demoted to USER.")


@admins.command("remove")
@click.option("--user-id", required=True)
@click.confirmation_option(prompt="This soft-deletes the user account entirely. Continue?")
@click.pass_context
def admins_remove(ctx: click.Context, user_id: str):
    """Fully delete an admin's user account (soft delete)."""
    api: ExiurAPI = ctx.obj["api"]
    try:
        api.delete_user(user_id)
    except APIError as e:
        die(str(e))
        return
    ok(f"Deleted user {user_id}.")


# ---------------------------------------------------------------------------
# users: everyday user management
# ---------------------------------------------------------------------------

@cli.group()
def users():
    """Manage regular panel users."""


@users.command("list")
@click.option("--page", default=1)
@click.option("--limit", default=20)
@click.pass_context
def users_list(ctx: click.Context, page: int, limit: int):
    api: ExiurAPI = ctx.obj["api"]
    try:
        result = api.list_users(page, limit)
    except APIError as e:
        die(str(e))
        return
    rows = result.get("data", []) if isinstance(result, dict) else result
    if not rows:
        console.print("No users found.")
        return
    console.print(table_from_rows("Users", rows, ["id", "username", "email", "status"]))


@users.command("get")
@click.argument("user_id")
@click.pass_context
def users_get(ctx: click.Context, user_id: str):
    api: ExiurAPI = ctx.obj["api"]
    try:
        console.print(api.get_user(user_id))
    except APIError as e:
        die(str(e))


@users.command("create")
@click.option("--username", required=True)
@click.option("--email", required=True)
@click.option("--password", required=True, prompt=True, hide_input=True, confirmation_prompt=True)
@click.option("--display", "display_name", default=None)
@click.pass_context
def users_create(ctx: click.Context, username: str, email: str, password: str, display_name: str | None):
    api: ExiurAPI = ctx.obj["api"]
    try:
        user = api.create_user(username, email, password, display_name)
    except APIError as e:
        die(str(e))
        return
    ok(f"Created user '{username}' (id={user.get('id')}).")


@users.command("update")
@click.argument("user_id")
@click.option("--email", default=None)
@click.option("--display", "displayName", default=None)
@click.option("--avatar", "avatarUrl", default=None)
@click.pass_context
def users_update(ctx: click.Context, user_id: str, email: str | None, displayName: str | None, avatarUrl: str | None):
    api: ExiurAPI = ctx.obj["api"]
    try:
        api.update_user(user_id, email=email, displayName=displayName, avatarUrl=avatarUrl)
    except APIError as e:
        die(str(e))
        return
    ok(f"Updated user {user_id}.")


@users.command("status")
@click.argument("user_id")
@click.option("--status", required=True,
              type=click.Choice(["ACTIVE", "INACTIVE", "SUSPENDED", "PENDING_VERIFICATION", "DELETED"]))
@click.pass_context
def users_status(ctx: click.Context, user_id: str, status: str):
    api: ExiurAPI = ctx.obj["api"]
    try:
        api.set_user_status(user_id, status)
    except APIError as e:
        die(str(e))
        return
    ok(f"User {user_id} status set to {status}.")


@users.command("delete")
@click.argument("user_id")
@click.confirmation_option(prompt="Soft-delete this user?")
@click.pass_context
def users_delete(ctx: click.Context, user_id: str):
    api: ExiurAPI = ctx.obj["api"]
    try:
        api.delete_user(user_id)
    except APIError as e:
        die(str(e))
        return
    ok(f"Deleted user {user_id}.")


@users.command("ban")
@click.option("--user-id", required=True)
@click.option("--reason", required=True)
@click.option("--type", "ban_type", default="TEMPORARY", type=click.Choice(["TEMPORARY", "PERMANENT"]))
@click.option("--expires", default=None, help="ISO datetime, required for TEMPORARY bans")
@click.pass_context
def users_ban(ctx: click.Context, user_id: str, reason: str, ban_type: str, expires: str | None):
    api: ExiurAPI = ctx.obj["api"]
    if ban_type == "TEMPORARY" and not expires:
        die("--expires is required for TEMPORARY bans.")
        return
    try:
        ban = api.ban_user(user_id, reason, ban_type, expires)
    except APIError as e:
        die(str(e))
        return
    ok(f"Banned user {user_id} (ban id={ban.get('id')}).")


@users.command("unban")
@click.argument("ban_id")
@click.option("--reason", required=True)
@click.pass_context
def users_unban(ctx: click.Context, ban_id: str, reason: str):
    api: ExiurAPI = ctx.obj["api"]
    try:
        api.revoke_ban(ban_id, reason)
    except APIError as e:
        die(str(e))
        return
    ok(f"Ban {ban_id} revoked.")


@users.command("bans")
@click.option("--active-only", is_flag=True)
@click.pass_context
def users_bans(ctx: click.Context, active_only: bool):
    api: ExiurAPI = ctx.obj["api"]
    try:
        rows = api.list_bans(active_only)
    except APIError as e:
        die(str(e))
        return
    if not rows:
        console.print("No bans found.")
        return
    console.print(table_from_rows("Bans", rows, ["id", "userId", "reason", "type", "expiresAt"]))


# ---------------------------------------------------------------------------
# tokens: license tokens (API keys)
# ---------------------------------------------------------------------------

@cli.group()
def tokens():
    """Manage access tokens (license/API keys) for the panel."""


@tokens.command("list")
@click.pass_context
def tokens_list(ctx: click.Context):
    api: ExiurAPI = ctx.obj["api"]
    try:
        rows = api.list_licenses()
    except APIError as e:
        die(str(e))
        return
    if not rows:
        console.print("No access tokens found.")
        return
    console.print(table_from_rows("Access Tokens", rows, ["id", "name", "prefix", "rateLimit", "expiresAt"]))


@tokens.command("create")
@click.option("--name", required=True)
@click.option("--scopes", default=None, help="comma-separated, e.g. read,write")
@click.option("--rate-limit", default=None, type=int)
@click.option("--expires", default=None, help="ISO datetime")
@click.pass_context
def tokens_create(ctx: click.Context, name: str, scopes: str | None, rate_limit: int | None, expires: str | None):
    api: ExiurAPI = ctx.obj["api"]
    scope_list = [s.strip() for s in scopes.split(",")] if scopes else None
    try:
        result = api.create_license(name, scope_list, rate_limit, expires)
    except APIError as e:
        die(str(e))
        return
    ok(f"Created token '{name}'.")
    console.print(f"[bold yellow]Save this now, it won't be shown again:[/]\n{result.get('rawToken')}")


@tokens.command("rotate")
@click.argument("token_id")
@click.option("--reason", required=True)
@click.pass_context
def tokens_rotate(ctx: click.Context, token_id: str, reason: str):
    api: ExiurAPI = ctx.obj["api"]
    try:
        result = api.rotate_license(token_id, reason)
    except APIError as e:
        die(str(e))
        return
    ok("Token rotated.")
    console.print(f"[bold yellow]New token, save it now:[/]\n{result.get('rawToken')}")


@tokens.command("revoke")
@click.argument("token_id")
@click.option("--reason", required=True)
@click.pass_context
def tokens_revoke(ctx: click.Context, token_id: str, reason: str):
    api: ExiurAPI = ctx.obj["api"]
    try:
        api.revoke_license(token_id, reason)
    except APIError as e:
        die(str(e))
        return
    ok(f"Token {token_id} revoked.")


def main():
    cli(obj={})


if __name__ == "__main__":
    main()
