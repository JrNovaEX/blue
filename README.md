# exiur — terminal admin tool for the BlueGuard `exiur` panel

A small, panel-locked CLI on top of the BlueGuard API. Built from the
BlueGuard docs, so it's only as accurate as those docs — see
**Assumptions** below for the two spots worth double-checking against the
real server.

## Install

```bash
cd exiur-cli
python3 -m venv venv
source venv/bin/activate
pip install -e .
```

## First run

```bash
exiur init      # asks for server URL + exiur panel ID, saves to ~/.exiur/config.json
exiur login     # asks for username/password, saves the session (token persists)
```

Every command after `init` runs a health check first — if BlueGuard is
down or the DB is unreachable, the CLI refuses to run and tells you why
instead of throwing a confusing error mid-command.

## Commands

### Admins (users with the ADMIN role in this panel)
```bash
exiur admins list
exiur admins add --username X --email X@x.com --display "X Y"      # prompts for password
exiur admins promote --user-id <uuid>     # bump an existing user to ADMIN
exiur admins demote  --user-id <uuid>     # drop back to USER
exiur admins remove  --user-id <uuid>     # soft-delete the account entirely
```

### Users
```bash
exiur users list [--page N] [--limit N]
exiur users get <id>
exiur users create --username X --email X@x.com                    # prompts for password
exiur users update <id> [--email X] [--display X] [--avatar URL]
exiur users status <id> --status SUSPENDED
exiur users delete <id>
exiur users ban --user-id <uuid> --reason "..." --type TEMPORARY --expires 2026-08-01T00:00:00Z
exiur users unban <ban_id> --reason "..."
exiur users bans [--active-only]
```

### Access tokens (license/API keys)
```bash
exiur tokens list
exiur tokens create --name "Prod key" [--scopes read,write] [--rate-limit 1000] [--expires ...]
exiur tokens rotate <id> --reason "..."
exiur tokens revoke <id> --reason "..."
```

Token `create`/`rotate` print the raw token once — copy it immediately,
BlueGuard never shows it again.

### Misc
```bash
exiur health     # manual health check
exiur whoami     # current logged-in user
exiur logout     # clears the local session
```

## Assumptions to verify against the real server

The docs don't fully specify two things, so I made a reasonable call —
flag these for a quick check once you have a live BlueGuard instance:

1. **`GET /panels/:id/members` response shape.** I assumed each member
   object has a `roleId` (and maybe an embedded `role.level`). If the
   real shape differs, fix the filtering logic in
   `exiur/api.py::list_members` and the `admins list` command in
   `exiur/cli.py`.
2. **Changing an existing member's role.** There's no documented `PUT`
   for panel members, so `set_member_role()` (used by `admins promote`
   / `admins demote`) does a `DELETE` + `POST` (remove, then re-add with
   the new role). If BlueGuard has a direct role-update endpoint, swap
   it in — it'll be more atomic than remove+re-add.

## Standalone build (cross-platform)

Build a single `.pyz` file that works on Linux, macOS, Windows, and Android —
anywhere Python 3.10+ is installed:

```bash
python build_zipapp.py
```

Output: `dist/exiur.pyz` (~1.6 MB). Contains all dependencies bundled.

Run it:
```bash
python exiur.pyz
```

No venv, no `pip install`, no compilation needed on the target machine.
Just copy `exiur.pyz` and run with Python.

## Config file

`~/.exiur/config.json` (permissions locked to your user only):
```json
{
  "server": "http://localhost:4000/api/v1",
  "panel_id": "...",
  "access_token": "...",
  "refresh_token": "...",
  "username": "..."
}
```
