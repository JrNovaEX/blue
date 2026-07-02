"""Local config & token storage for the exiur CLI.

Everything lives in ~/.exiur/config.json (mode 600). This holds the server
URL, the exiur panel id, and the current login session (access/refresh
tokens) so the user only has to log in once.
"""
from __future__ import annotations

import json
import os
import stat
from pathlib import Path
from typing import Any

CONFIG_DIR = Path.home() / ".exiur"
CONFIG_FILE = CONFIG_DIR / "config.json"

DEFAULTS: dict[str, Any] = {
    "server": None,          # e.g. http://localhost:4000/api/v1
    "panel_id": None,        # exiur panel UUID
    "access_token": None,
    "refresh_token": None,
    "username": None,
}


def load_config() -> dict[str, Any]:
    if not CONFIG_FILE.exists():
        return dict(DEFAULTS)
    try:
        data = json.loads(CONFIG_FILE.read_text())
    except (json.JSONDecodeError, OSError):
        return dict(DEFAULTS)
    merged = dict(DEFAULTS)
    merged.update(data)
    return merged


def save_config(cfg: dict[str, Any]) -> None:
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    CONFIG_FILE.write_text(json.dumps(cfg, indent=2))
    # Tokens live in here -> keep it readable only by the owner.
    try:
        os.chmod(CONFIG_FILE, stat.S_IRUSR | stat.S_IWUSR)
    except OSError:
        pass


def update_config(**fields: Any) -> dict[str, Any]:
    cfg = load_config()
    cfg.update(fields)
    save_config(cfg)
    return cfg


def is_initialized(cfg: dict[str, Any]) -> bool:
    return bool(cfg.get("server") and cfg.get("panel_id"))


def is_logged_in(cfg: dict[str, Any]) -> bool:
    return bool(cfg.get("access_token"))


def clear_session(cfg: dict[str, Any]) -> dict[str, Any]:
    cfg["access_token"] = None
    cfg["refresh_token"] = None
    cfg["username"] = None
    save_config(cfg)
    return cfg
