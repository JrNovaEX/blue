"""Interactive menu mode -- runs when `exiur` is invoked with no subcommand.

Just a thin numbered-menu wrapper around the same ExiurAPI methods the
click commands use, so behaviour stays identical either way.
"""
from __future__ import annotations

import click
from datetime import datetime, timedelta, timezone

from .api import APIError, ExiurAPI
from .config import clear_session, is_logged_in
from .ui import console, err, ok, table_from_rows


def prompt_choice(title: str, options: list[tuple[str, str]]) -> str:
    """Print a numbered menu and return the chosen key. '0' is always Back/Exit."""
    console.print(f"\n[bold cyan]{title}[/]")
    for key, label in options:
        console.print(f"  [ {key} ] {label}")
    valid = {k for k, _ in options}
    while True:
        choice = click.prompt("select", default="0")
        if choice in valid:
            return choice
        console.print("[yellow]invalid choice, try again[/]")


def show(result) -> None:
    if isinstance(result, list):
        if not result:
            console.print("(empty)")
        else:
            console.print(table_from_rows("Result", result, list(result[0].keys())))
    else:
        console.print(result)


# ---------------------------------------------------------------------------
# admins
# ---------------------------------------------------------------------------

def menu_admins(api: ExiurAPI) -> None:
    while True:
        choice = prompt_choice("Admins", [
            ("1", "list"), ("2", "add"), ("3", "promote"),
            ("4", "demote"), ("5", "remove"), ("0", "back"),
        ])
        try:
            if choice == "1":
                roles = api.list_roles()
                admin_role = next((r for r in roles if r.get("level") == "ADMIN"), None)
                members = api.list_members(limit=100)
                rows = members.get("data", members) if isinstance(members, dict) else members
                if admin_role:
                    rows = [
                        m for m in rows
                        if m.get("roleId") == admin_role.get("id")
                        or m.get("role", {}).get("level") == "ADMIN"
                    ]
                show(rows)
            elif choice == "2":
                username = click.prompt("username")
                email = click.prompt("email")
                password = click.prompt("password", hide_input=True, confirmation_prompt=True)
                display = click.prompt("display name", default="", show_default=False) or None
                admin_role = api.find_role_by_level("ADMIN")
                if not admin_role:
                    err("No ADMIN role found in this panel.")
                    continue
                user = api.create_user(username, email, password, display, role_id=admin_role["id"])
                ok(f"Created admin '{username}' (id={user.get('id')}).")
            elif choice == "3":
                user_id = click.prompt("user id")
                admin_role = api.find_role_by_level("ADMIN")
                if not admin_role:
                    err("No ADMIN role found in this panel.")
                    continue
                api.set_member_role(user_id, admin_role["id"])
                ok(f"User {user_id} promoted to ADMIN.")
            elif choice == "4":
                user_id = click.prompt("user id")
                user_role = api.find_role_by_level("USER")
                if not user_role:
                    err("No USER role found in this panel.")
                    continue
                api.set_member_role(user_id, user_role["id"])
                ok(f"User {user_id} demoted to USER.")
            elif choice == "5":
                user_id = click.prompt("user id")
                if click.confirm("this soft-deletes the user account entirely, continue?"):
                    api.delete_user(user_id)
                    ok(f"Deleted user {user_id}.")
            else:
                return
        except APIError as e:
            err(str(e))


# ---------------------------------------------------------------------------
# users
# ---------------------------------------------------------------------------

def menu_users(api: ExiurAPI) -> None:
    while True:
        choice = prompt_choice("Users", [
            ("1", "list"), ("2", "get"), ("3", "create"), ("4", "update"),
            ("5", "status"), ("6", "delete"), ("7", "ban"), ("8", "unban"),
            ("9", "bans"), ("0", "back"),
        ])
        try:
            if choice == "1":
                page = click.prompt("page", default=1, type=int)
                limit = click.prompt("limit", default=20, type=int)
                result = api.list_users(page, limit)
                rows = result.get("data", []) if isinstance(result, dict) else result
                show(rows)
            elif choice == "2":
                show(api.get_user(click.prompt("user id")))
            elif choice == "3":
                username = click.prompt("username")
                email = click.prompt("email")
                password = click.prompt("password", hide_input=True, confirmation_prompt=True)
                display = click.prompt("display name", default="", show_default=False) or None
                user = api.create_user(username, email, password, display)
                ok(f"Created user '{username}' (id={user.get('id')}).")
            elif choice == "4":
                user_id = click.prompt("user id")
                email = click.prompt("email (blank to skip)", default="", show_default=False) or None
                display = click.prompt("display name (blank to skip)", default="", show_default=False) or None
                avatar = click.prompt("avatar url (blank to skip)", default="", show_default=False) or None
                api.update_user(user_id, email=email, displayName=display, avatarUrl=avatar)
                ok(f"Updated user {user_id}.")
            elif choice == "5":
                user_id = click.prompt("user id")
                status = click.prompt(
                    "status", type=click.Choice(
                        ["ACTIVE", "INACTIVE", "SUSPENDED", "PENDING_VERIFICATION", "DELETED"]
                    ),
                )
                api.set_user_status(user_id, status)
                ok(f"User {user_id} status set to {status}.")
            elif choice == "6":
                user_id = click.prompt("user id")
                if click.confirm("soft-delete this user?"):
                    api.delete_user(user_id)
                    ok(f"Deleted user {user_id}.")
            elif choice == "7":
                user_id = click.prompt("user id")
                reason = click.prompt("reason")
                ban_type = click.prompt("type", type=click.Choice(["TEMPORARY", "PERMANENT"]), default="TEMPORARY")
                expires = None
                if ban_type == "TEMPORARY":
                    expires = click.prompt("expires at (ISO datetime)")
                ban = api.ban_user(user_id, reason, ban_type, expires)
                ok(f"Banned user {user_id} (ban id={ban.get('id')}).")
            elif choice == "8":
                ban_id = click.prompt("ban id")
                reason = click.prompt("reason")
                api.revoke_ban(ban_id, reason)
                ok(f"Ban {ban_id} revoked.")
            elif choice == "9":
                active_only = click.confirm("active only?", default=False)
                show(api.list_bans(active_only))
            else:
                return
        except APIError as e:
            err(str(e))


# ---------------------------------------------------------------------------
# tokens
# ---------------------------------------------------------------------------

def menu_tokens(api: ExiurAPI) -> None:
    while True:
        choice = prompt_choice("Access Tokens", [
            ("1", "list"), ("2", "create"), ("3", "rotate"), ("4", "revoke"), ("0", "back"),
        ])
        try:
            if choice == "1":
                show(api.list_licenses())
            elif choice == "2":
                name = click.prompt("name")
                scopes = click.prompt("scopes, comma-separated (blank to skip)", default="", show_default=False)
                rate_limit = click.prompt("rate limit (blank to skip)", default="", show_default=False)
                expires = click.prompt("expires at, ISO datetime (blank to skip)", default="", show_default=False)
                if expires and expires.strip().isdigit():
                    expires = (datetime.now(timezone.utc) + timedelta(days=int(expires))).isoformat()
                scope_list = [s.strip() for s in scopes.split(",")] if scopes else None
                result = api.create_license(
                    name, scope_list,
                    int(rate_limit) if rate_limit else None,
                    expires or None,
                )
                ok(f"Created token '{name}'.")
                console.print(f"[bold yellow]Save this now, it won't be shown again:[/]\n{result.get('rawToken')}")
            elif choice == "3":
                token_id = click.prompt("token id")
                reason = click.prompt("reason")
                result = api.rotate_license(token_id, reason)
                ok("Token rotated.")
                console.print(f"[bold yellow]New token, save it now:[/]\n{result.get('rawToken')}")
            elif choice == "4":
                token_id = click.prompt("token id")
                reason = click.prompt("reason")
                api.revoke_license(token_id, reason)
                ok(f"Token {token_id} revoked.")
            else:
                return
        except APIError as e:
            err(str(e))


# ---------------------------------------------------------------------------
# top level
# ---------------------------------------------------------------------------

def run_menu(cfg: dict, api: ExiurAPI) -> None:
    while True:
        logged_in = is_logged_in(cfg)
        console.print(
            f"\n[bold]welcome to exiur panel[/]"
            + (f" [dim](logged in as {cfg.get('username')})[/]" if logged_in else " [dim](not logged in)[/]")
        )

        if not logged_in:
            choice = prompt_choice("select pls", [("1", "login"), ("0", "exit")])
            if choice == "0":
                return
            username = click.prompt("username")
            password = click.prompt("password", hide_input=True)
            try:
                api.login(username, password)
                ok(f"logged in as {username}.")
            except APIError as e:
                err(str(e))
            continue

        choice = prompt_choice("select pls", [
            ("1", "admins"), ("2", "users"), ("3", "tokens"),
            ("4", "whoami"), ("5", "health"), ("6", "logout"), ("0", "exit"),
        ])
        try:
            if choice == "1":
                menu_admins(api)
            elif choice == "2":
                menu_users(api)
            elif choice == "3":
                menu_tokens(api)
            elif choice == "4":
                show(api.me())
            elif choice == "5":
                h = api.health()
                ok(f"status={h.get('status')} db={h.get('details', {}).get('database', {})}")
            elif choice == "6":
                try:
                    api.logout()
                except APIError:
                    pass
                clear_session(cfg)
                ok("logged out.")
            else:
                console.print("bye 👋")
                return
        except APIError as e:
            err(str(e))
