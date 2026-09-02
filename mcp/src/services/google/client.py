import json
import logging
from typing import Dict, Any, List, Optional
import httpx
import base64
import uuid
import time

logger = logging.getLogger("mcp.google")

GMAIL_SCOPE = "https://www.googleapis.com/auth/gmail.modify"
CAL_SCOPE = "https://www.googleapis.com/auth/calendar"


class GoogleClient:
    """Minimal Google workspace client (Gmail + Calendar) using OAuth2 refresh tokens."""

    TOKEN_URL = "https://oauth2.googleapis.com/token"
    GMAIL_API = "https://gmail.googleapis.com/gmail/v1"
    CAL_API = "https://www.googleapis.com/calendar/v3"

    def __init__(self, client_id: str, client_secret: str, refresh_token: str, scope: str = ""):
        self.client_id = client_id or ""
        self.client_secret = client_secret or ""
        self.refresh_token = refresh_token or ""
        self.scope = scope or f"{GMAIL_SCOPE} {CAL_SCOPE}"
        self._access_token = ""
        self._token_expires = 0.0

    def is_configured(self) -> bool:
        return bool(self.client_id and self.client_secret and self.refresh_token)

    async def _get_access_token(self) -> str:
        if self._access_token and time.time() < self._token_expires - 60:
            return self._access_token
        async with httpx.AsyncClient(timeout=20.0) as client:
            res = await client.post(self.TOKEN_URL, data={
                "client_id": self.client_id,
                "client_secret": self.client_secret,
                "refresh_token": self.refresh_token,
                "grant_type": "refresh_token",
            })
            if res.status_code != 200:
                raise RuntimeError(f"Google token refresh failed ({res.status_code}): {res.text[:300]}")
            data = res.json()
            self._access_token = data.get("access_token", "")
            self._token_expires = time.time() + int(data.get("expires_in", 3600))
            return self._access_token

    async def _request(self, method: str, url: str, *, params: Optional[dict] = None, json_body: Optional[dict] = None, headers: Optional[dict] = None):
        token = await self._get_access_token()
        h = {"Authorization": f"Bearer {token}", "Accept": "application/json"}
        if headers:
            h.update(headers)
        async with httpx.AsyncClient(timeout=30.0) as client:
            res = await client.request(method, url, params=params, json=json_body, headers=h)
            if res.status_code >= 400:
                raise RuntimeError(f"Google API error ({res.status_code}): {res.text[:300]}")
            return res.json() if res.content else {}

    # ---- Gmail ----
    async def gmail_list(self, query: str = "", max_results: int = 10) -> list:
        data = await self._request(
            "GET", f"{self.GMAIL_API}/users/me/messages",
            params={"q": query, "maxResults": max_results},
        )
        out = []
        for m in data.get("messages", []):
            out.append({"id": m.get("id"), "threadId": m.get("threadId")})
        return out

    async def gmail_get(self, message_id: str, format: str = "full") -> dict:
        data = await self._request(
            "GET", f"{self.GMAIL_API}/users/me/messages/{message_id}",
            params={"format": format},
        )
        headers = {}
        for h in data.get("payload", {}).get("headers", []) or []:
            headers[h.get("name", "")] = h.get("value", "")
        body = ""
        if format in ("full", "text"):
            body = self._decode_body(data.get("payload", {}))
        return {
            "id": data.get("id"),
            "threadId": data.get("threadId"),
            "from": headers.get("From", ""),
            "to": headers.get("To", ""),
            "subject": headers.get("Subject", ""),
            "date": headers.get("Date", ""),
            "snippet": data.get("snippet", ""),
            "body": body[:5000],
        }

    async def gmail_send(self, to: str, subject: str, body: str, cc: str = "", bcc: str = "") -> dict:
        mime = self._build_mime(to, subject, body, cc, bcc)
        raw = base64.urlsafe_b64encode(mime.encode("utf-8")).decode("ascii")
        data = await self._request(
            "POST", f"{self.GMAIL_API}/users/me/messages/send",
            json_body={"raw": raw}, headers={"Content-Type": "application/json"},
        )
        return {"id": data.get("id"), "status": "sent"}

    # ---- Calendar ----
    async def calendar_events(self, calendar_id: str = "primary", time_min: str = "", time_max: str = "", max_results: int = 20) -> list:
        params = {"maxResults": max_results, "orderBy": "startTime", "singleEvents": "true"}
        if time_min:
            params["timeMin"] = time_min
        if time_max:
            params["timeMax"] = time_max
        data = await self._request("GET", f"{self.CAL_API}/calendars/{calendar_id}/events", params=params)
        return [
            {
                "id": e.get("id"),
                "summary": e.get("summary", ""),
                "start": e.get("start", {}).get("dateTime") or e.get("start", {}).get("date", ""),
                "end": e.get("end", {}).get("dateTime") or e.get("end", {}).get("date", ""),
                "status": e.get("status", ""),
            }
            for e in data.get("items", [])
        ]

    async def calendar_create(self, summary: str, start: str, end: str, description: str = "", attendees: Optional[list] = None, calendar_id: str = "primary") -> dict:
        payload = {
            "summary": summary,
            "description": description,
            "start": {"dateTime": start},
            "end": {"dateTime": end},
        }
        if attendees:
            payload["attendees"] = [{"email": a} for a in attendees]
        data = await self._request("POST", f"{self.CAL_API}/calendars/{calendar_id}/events", json_body=payload)
        return {"id": data.get("id"), "htmlLink": data.get("htmlLink", ""), "status": "created"}

    async def test_connection(self) -> Dict[str, Any]:
        try:
            await self._get_access_token()
            return {"ok": True, "message": "Google OAuth token válido.", "details": {}}
        except Exception as e:
            return {"ok": False, "message": f"Error de conexión con Google: {e}", "details": {"error": str(e)}}

    # ---- helpers ----
    @staticmethod
    def _decode_body(payload: dict) -> str:
        parts = []
        if payload.get("body", {}).get("data"):
            parts.append(base64.urlsafe_b64decode(payload["body"]["data"]).decode("utf-8", errors="ignore"))
        for p in payload.get("parts", []) or []:
            if p.get("mimeType") in ("text/plain", "text/html") and p.get("body", {}).get("data"):
                parts.append(base64.urlsafe_b64decode(p["body"]["data"]).decode("utf-8", errors="ignore"))
            else:
                parts.append(GoogleClient._decode_body(p))
        return "\n".join(p for p in parts if p)

    @staticmethod
    def _build_mime(to: str, subject: str, body: str, cc: str = "", bcc: str = "") -> str:
        lines = ["From: me", f"To: {to}"]
        if cc:
            lines.append(f"Cc: {cc}")
        if bcc:
            lines.append(f"Bcc: {bcc}")
        lines += ["Subject: " + subject[:998], "MIME-Version: 1.0", "Content-Type: text/plain; charset=UTF-8", "", body]
        return "\r\n".join(lines)
