"""Thin wrapper around the BlueGuard API, scoped to a single panel (exiur).

Endpoints and payload shapes below are taken directly from the BlueGuard
docs (authentication.md, users.md, panels.md, roles.md, bans.md,
licenses.md, health.md). Two spots are NOT fully specified by the docs and
are marked ASSUMPTION below -- check them against the real server once you
have access, they're the most likely thing to need a tweak:

  1. GET /panels/:id/members -- the exact JSON shape of each member
     (whether role info is embedded or just a roleId) isn't documented.
  2. Changing an existing member's role -- there's no PUT for panel
     members, so `set_member_role()` does remove + re-add. If the real
     API supports a direct role update, swap it in there.
"""
from __future__ import annotations

import requests

from .config import save_config


class APIError(Exception):
    def __init__(self, message: str, code: str | None = None, status: int | None = None):
        super().__init__(message)
        self.message = message
        self.code = code
        self.status = status

    def __str__(self) -> str:
        if self.code:
            return f"[{self.code}] {self.message}"
        return self.message


class ExiurAPI:
    def __init__(self, cfg: dict):
        self.cfg = cfg

    # -- low level -----------------------------------------------------

    def _base(self) -> str:
        server = self.cfg.get("server")
        if not server:
            raise APIError("Not initialized. Run `exiur init` first.")
        return server.rstrip("/")

    def _headers(self, auth: bool = True, panel: bool = True) -> dict:
        headers = {"Content-Type": "application/json"}
        if auth and self.cfg.get("access_token"):
            headers["Authorization"] = f"Bearer {self.cfg['access_token']}"
        if panel and self.cfg.get("panel_id"):
            headers["X-Panel-Id"] = self.cfg["panel_id"]
        return headers

    def _request(
        self,
        method: str,
        path: str,
        *,
        json_body: dict | None = None,
        params: dict | None = None,
        auth: bool = True,
        panel: bool = True,
        retry_on_expired: bool = True,
    ):
        url = f"{self._base()}{path}"
        try:
            resp = requests.request(
                method, url, json=json_body, params=params,
                headers=self._headers(auth=auth, panel=panel), timeout=15,
            )
        except requests.RequestException as e:
            raise APIError(f"Could not reach {url}: {e}")

        # Token expired -> try one silent refresh and replay the request.
        if resp.status_code == 401 and retry_on_expired and self.cfg.get("refresh_token"):
            body = self._safe_json(resp)
            code = (body or {}).get("error", {}).get("code")
            if code in ("AUTH_002", "SESSION_002"):
                try:
                    self.refresh()
                except APIError:
                    pass
                else:
                    return self._request(
                        method, path, json_body=json_body, params=params,
                        auth=auth, panel=panel, retry_on_expired=False,
                    )

        body = self._safe_json(resp)
        if not resp.ok or (isinstance(body, dict) and body.get("success") is False):
            err = (body or {}).get("error", {}) if isinstance(body, dict) else {}
            raise APIError(
                err.get("message", f"HTTP {resp.status_code}"),
                code=err.get("code"),
                status=resp.status_code,
            )
        return body

    @staticmethod
    def _safe_json(resp: requests.Response):
        try:
            return resp.json()
        except ValueError:
            return None

    @staticmethod
    def _data(body):
        if isinstance(body, dict) and "data" in body:
            return body["data"]
        return body

    # -- health ----------------------------------------------------------

    def health(self) -> dict:
        # No auth/panel headers -- /health is public.
        # NOTE: health.md docs show a flat response, but the real server
        # wraps it like every other endpoint ({"success":true,"data":{...}}).
        # Unwrap defensively so this keeps working either way.
        return self._data(self._request("GET", "/health", auth=False, panel=False))

    # -- auth --------------------------------------------------------------

    def login(self, username: str, password: str) -> dict:
        body = self._request(
            "POST", "/auth/login",
            json_body={"username": username, "password": password},
            auth=False, panel=False,
        )
        data = self._data(body)
        self.cfg.update({
            "access_token": data["accessToken"],
            "refresh_token": data["refreshToken"],
            "username": username,
        })
        save_config(self.cfg)
        return data

    def refresh(self) -> dict:
        body = self._request(
            "POST", "/auth/refresh",
            json_body={"refreshToken": self.cfg.get("refresh_token")},
            auth=False, panel=False, retry_on_expired=False,
        )
        data = self._data(body)
        self.cfg.update({
            "access_token": data["accessToken"],
            "refresh_token": data["refreshToken"],
        })
        save_config(self.cfg)
        return data

    def logout(self) -> None:
        self._request("POST", "/auth/logout", panel=False, retry_on_expired=False)

    def me(self) -> dict:
        return self._data(self._request("GET", "/users/me"))

    # -- roles ---------------------------------------------------------

    def list_roles(self) -> list:
        return self._data(self._request("GET", "/roles"))

    def find_role_by_level(self, level: str) -> dict | None:
        for role in self.list_roles() or []:
            if role.get("level") == level:
                return role
        return None

    # -- panel members (used for admins) --------------------------------

    def list_members(self, page: int = 1, limit: int = 20) -> dict:
        panel_id = self.cfg["panel_id"]
        return self._data(self._request(
            "GET", f"/panels/{panel_id}/members", params={"page": page, "limit": limit},
        ))

    def add_member(self, user_id: str, role_id: str) -> dict:
        panel_id = self.cfg["panel_id"]
        return self._data(self._request(
            "POST", f"/panels/{panel_id}/members",
            json_body={"userId": user_id, "roleId": role_id},
        ))

    def remove_member(self, user_id: str) -> None:
        panel_id = self.cfg["panel_id"]
        self._request("DELETE", f"/panels/{panel_id}/members/{user_id}")

    def set_member_role(self, user_id: str, role_id: str) -> dict:
        # ASSUMPTION: no documented PUT for a member's role, so we
        # remove + re-add. Swap for a direct PUT if the server has one.
        try:
            self.remove_member(user_id)
        except APIError:
            pass  # user may not have been a member yet
        return self.add_member(user_id, role_id)

    # -- users -----------------------------------------------------------

    def list_users(self, page: int = 1, limit: int = 20) -> dict:
        return self._data(self._request("GET", "/users", params={"page": page, "limit": limit}))

    def get_user(self, user_id: str) -> dict:
        return self._data(self._request("GET", f"/users/{user_id}"))

    def create_user(self, username: str, email: str, password: str,
                     display_name: str | None = None, role_id: str | None = None) -> dict:
        payload = {"username": username, "email": email, "password": password}
        if display_name:
            payload["displayName"] = display_name
        payload["panelId"] = self.cfg["panel_id"]
        if role_id:
            payload["roleId"] = role_id
        return self._data(self._request("POST", "/users", json_body=payload))

    def update_user(self, user_id: str, **fields) -> dict:
        fields = {k: v for k, v in fields.items() if v is not None}
        return self._data(self._request("PUT", f"/users/{user_id}", json_body=fields))

    def delete_user(self, user_id: str) -> None:
        self._request("DELETE", f"/users/{user_id}")

    def set_user_status(self, user_id: str, status: str) -> dict:
        return self._data(self._request(
            "POST", f"/users/{user_id}/status", json_body={"status": status},
        ))

    # -- bans (part of user management) ----------------------------------

    def list_bans(self, active_only: bool = False) -> list:
        path = "/bans/active" if active_only else "/bans"
        return self._data(self._request("GET", path))

    def ban_user(self, user_id: str, reason: str, ban_type: str = "TEMPORARY",
                 expires_at: str | None = None) -> dict:
        payload = {"userId": user_id, "reason": reason, "type": ban_type}
        if expires_at:
            payload["expiresAt"] = expires_at
        return self._data(self._request("POST", "/bans", json_body=payload))

    def revoke_ban(self, ban_id: str, reason: str) -> dict:
        return self._data(self._request(
            "PUT", f"/bans/{ban_id}/revoke", json_body={"reason": reason},
        ))

    # -- licenses / access tokens -----------------------------------------

    def list_licenses(self) -> list:
        return self._data(self._request("GET", "/licenses"))

    def create_license(self, name: str, scopes: list[str] | None = None,
                        rate_limit: int | None = None, expires_at: str | None = None) -> dict:
        payload = {"name": name}
        if scopes:
            payload["scopes"] = scopes
        if rate_limit is not None:
            payload["rateLimit"] = rate_limit
        if expires_at:
            payload["expiresAt"] = expires_at
        return self._data(self._request("POST", "/licenses", json_body=payload))

    def rotate_license(self, license_id: str, reason: str) -> dict:
        return self._data(self._request(
            "POST", f"/licenses/{license_id}/rotate", json_body={"reason": reason},
        ))

    def revoke_license(self, license_id: str, reason: str) -> dict:
        return self._data(self._request(
            "POST", f"/licenses/{license_id}/revoke", json_body={"reason": reason},
        ))
