"""Passbolt logins as a vault backend (``pb:`` handles) — vps-tools addition.

Surfacing the Passbolt vault Hermes already reads (via the local MCP gateway)
as a first-class login source for the password-blind browser tools:

- ``list_items``        metadata only (label, identifier, origin) — never secrets.
- ``resolve_password``  decrypted password, resolved server-side at fill time.
- ``resolve_otp``       live TOTP code minted by the gateway at fill time.

Design notes:

- ``needs_unlock = False``: the gateway process holds the Passbolt session, so
  this backend works in headless sessions (Telegram/API/cron) with no prompt.
- Passbolt URIs often lack a scheme (``live.com``); ``https://`` is assumed.
  Per-resource origin overrides come from ``vault.passbolt.origin_overrides``
  (``{resource_uuid: origin}``) for IdP hosts such as
  ``https://login.microsoftonline.com``.
- A full listing takes ~30 s (per-item GPG decrypt on the gateway), so list
  results are cached in-process for ``vault.passbolt.list_ttl_seconds``
  (default 600). Secrets are ALWAYS resolved fresh — a password changed in
  Passbolt is picked up on the very next fill. Zero migration, zero sync.
- Auth: ``Authorization: Bearer <token>`` where the token is
  ``MCP_GATEWAY_TOKEN`` from the environment (already present — the MCP
  servers in ``~/.hermes/config.yaml`` use it) or
  ``vault.passbolt.gateway_token`` as fallback. The token is never logged.

Installed by ``vps-tools/hermes/scripts/patch-hermes.py``
(``install_passbolt_backend``), which copies this file to
``agent/vault_backends/passbolt.py`` and registers the backend in ``base.py``.
"""

from __future__ import annotations

import json
import logging
import os
import time
import urllib.request
from typing import Dict, List, Optional

from agent.vault_backends.base import LoginBackend
from agent.vault_store import VaultItemMeta, normalize_origin

logger = logging.getLogger(__name__)

_DEFAULT_GATEWAY_URL = "http://127.0.0.1:8005"
_DEFAULT_SCOPE = "unified"
_DEFAULT_LIST_TTL = 600.0
_LIST_TIMEOUT = 120.0
_SECRET_TIMEOUT = 30.0


def _cfg() -> Dict:
    from hermes_cli.config import load_config_readonly
    cfg = load_config_readonly().get("vault") or {}
    section = cfg.get("passbolt") if isinstance(cfg, dict) else None
    return section if isinstance(section, dict) else {}


def _token(cfg: Dict) -> str:
    return str(cfg.get("gateway_token") or os.environ.get("MCP_GATEWAY_TOKEN") or "").strip()


def is_configured() -> bool:
    """Enabled when a gateway token is available (no CLI install needed)."""
    try:
        return bool(_token(_cfg()))
    except Exception:
        return False


def _gateway_call(tool: str, arguments: Dict, timeout: float) -> Dict:
    cfg = _cfg()
    token = _token(cfg)
    if not token:
        raise RuntimeError(
            "Passbolt backend: no gateway token. Set MCP_GATEWAY_TOKEN in the "
            "environment or vault.passbolt.gateway_token in config."
        )
    base = str(cfg.get("gateway_url") or _DEFAULT_GATEWAY_URL).rstrip("/")
    scope = str(cfg.get("scope") or _DEFAULT_SCOPE)
    url = f"{base}/api/admin/tools/execute"
    payload = {"scope": scope, "tool": tool, "arguments": arguments}
    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json", "Authorization": f"Bearer {token}"},
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            body = json.loads(resp.read().decode("utf-8"))
    except Exception as exc:
        raise RuntimeError(f"Passbolt backend: gateway call {tool!r} failed: {exc}") from exc
    if isinstance(body, dict) and body.get("error"):
        raise RuntimeError(f"Passbolt backend: gateway error for {tool!r}: {body['error']}")
    try:
        text = body["result"]["content"][0]["text"]
    except (KeyError, IndexError, TypeError) as exc:
        raise RuntimeError(f"Passbolt backend: unexpected gateway response for {tool!r}") from exc
    try:
        return json.loads(text)
    except Exception:
        # get_secret-style tools already return a dict envelope in some paths
        if isinstance(text, dict):
            return text
        raise RuntimeError(f"Passbolt backend: could not parse {tool!r} response")


def _origin_for(resource_id: str, uri: str, overrides: Dict) -> Optional[str]:
    if resource_id in overrides:
        try:
            return normalize_origin(str(overrides[resource_id]))
        except Exception:
            pass
    raw = (uri or "").strip()
    if not raw:
        return None
    if "://" not in raw:
        raw = "https://" + raw
    try:
        return normalize_origin(raw)
    except Exception:
        return None


def _identifier_type(identifier: str) -> Optional[str]:
    ident = (identifier or "").strip()
    if not ident:
        return None
    if "@" in ident:
        return "email"
    if ident.lstrip("+").isdigit():
        return "phone"
    return "username"


# In-process metadata cache: {expires_at, items, skipped}. Secrets are never cached.
_cache: Dict = {"expires_at": 0.0, "items": [], "skipped": 0}


class PassboltLoginBackend(LoginBackend):
    name = "passbolt"
    display_name = "Passbolt"
    prefix = "pb:"
    needs_unlock = False

    def __init__(self, cfg: Optional[Dict] = None):
        self.cfg = cfg or _cfg()

    def _overrides(self) -> Dict:
        raw = self.cfg.get("origin_overrides") or {}
        return dict(raw) if isinstance(raw, dict) else {}

    def list_items(self) -> List[VaultItemMeta]:
        now = time.monotonic()
        ttl = float(self.cfg.get("list_ttl_seconds") or _DEFAULT_LIST_TTL)
        if now < _cache["expires_at"] and _cache["items"]:
            return list(_cache["items"])
        limit = int(self.cfg.get("list_limit") or 500)
        raw_items = _gateway_call(
            "passbolt_search_resources",
            {"query": "", "limit": limit, **({"account": self.cfg["account"]} if self.cfg.get("account") else {})},
            _LIST_TIMEOUT,
        )
        if not isinstance(raw_items, list):
            raise RuntimeError("Passbolt backend: search did not return a list")
        overrides = self._overrides()
        out: List[VaultItemMeta] = []
        skipped = 0
        for item in raw_items:
            if not isinstance(item, dict):
                continue
            rid = str(item.get("id") or "")
            if not rid:
                continue
            origin = _origin_for(rid, str(item.get("uri") or ""), overrides)
            if not origin:
                skipped += 1
                continue
            username = str(item.get("username") or "").strip() or None
            out.append(VaultItemMeta(
                id=f"{self.prefix}{rid}",
                kind="login",
                label=str(item.get("name") or origin),
                origin=origin,
                created_at=str(item.get("modified") or ""),
                identifier_type=_identifier_type(username or ""),
                identifier=username,
            ))
        _cache.update({"expires_at": now + ttl, "items": out, "skipped": skipped})
        if skipped:
            logger.warning("Passbolt backend: %d item(s) skipped (no usable origin; "
                           "add vault.passbolt.origin_overrides entries)", skipped)
        return list(out)

    def get_meta(self, handle: str) -> Optional[VaultItemMeta]:
        return next((m for m in self.list_items() if m.id == handle), None)

    def _secret(self, handle: str) -> Dict:
        rid = handle[len(self.prefix):]
        if not rid:
            raise RuntimeError("Passbolt backend: empty handle")
        args: Dict = {"resource_id": rid}
        if self.cfg.get("account"):
            args["account"] = self.cfg["account"]
        data = _gateway_call("passbolt_get_secret", args, _SECRET_TIMEOUT)
        if not isinstance(data, dict):
            raise RuntimeError("Passbolt backend: secret response was not an object")
        return data

    def resolve_password(self, handle: str) -> str:
        password = str(self._secret(handle).get("password") or "")
        if not password:
            raise RuntimeError("Passbolt backend: empty password in secret response")
        return password

    def resolve_otp(self, handle: str) -> Optional[str]:
        try:
            totp = self._secret(handle).get("totp") or {}
        except Exception:
            return None
        code = str(totp.get("code") or "").strip() if isinstance(totp, dict) else ""
        return code if code.isdigit() else None
