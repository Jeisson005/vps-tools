import time
import logging
from typing import Dict, Any, List, Optional
import httpx

logger = logging.getLogger("mcp.microsoft")

GRAPH = "https://graph.microsoft.com/v1.0"
AUTH = "https://login.microsoftonline.com"


class MSGraphClient:
    """Microsoft 365 client (Outlook mail + Calendar) via Graph API + OAuth2 refresh token."""

    DEFAULT_SCOPE = "https://graph.microsoft.com/.default"

    def __init__(self, tenant_id: str, client_id: str, client_secret: str, refresh_token: str = "", scope: str = ""):
        self.tenant_id = tenant_id or ""
        self.client_id = client_id or ""
        self.client_secret = client_secret or ""
        self.refresh_token = refresh_token or ""
        self.scope = scope or self.DEFAULT_SCOPE
        self._access_token = ""
        self._token_expires = 0.0

    def is_configured(self) -> bool:
        return bool(self.tenant_id and self.client_id and self.client_secret and self.refresh_token)

    async def _get_access_token(self) -> str:
        if self._access_token and time.time() < self._token_expires - 60:
            return self._access_token
        url = f"{AUTH}/{self.tenant_id}/oauth2/v2.0/token"
        async with httpx.AsyncClient(timeout=20.0) as client:
            res = await client.post(url, data={
                "client_id": self.client_id,
                "client_secret": self.client_secret,
                "scope": self.scope,
                "grant_type": "refresh_token",
                "refresh_token": self.refresh_token,
            })
            if res.status_code != 200:
                raise RuntimeError(f"Microsoft token refresh failed ({res.status_code}): {res.text[:300]}")
            data = res.json()
            self._access_token = data.get("access_token", "")
            self._token_expires = time.time() + int(data.get("expires_in", 3600))
            return self._access_token

    async def _request(self, method: str, path: str, *, params: Optional[dict] = None, json_body: Optional[dict] = None):
        token = await self._get_access_token()
        headers = {"Authorization": f"Bearer {token}", "Accept": "application/json"}
        async with httpx.AsyncClient(timeout=30.0) as client:
            res = await client.request(method, f"{GRAPH}{path}", params=params, json=json_body, headers=headers)
            if res.status_code >= 400:
                raise RuntimeError(f"Graph API error ({res.status_code}): {res.text[:300]}")
            return res.json() if res.content else {}

    async def mail_list(self, filter: str = "", search: str = "", top: int = 10) -> list:
        params = {"$top": top, "$orderby": "receivedDateTime desc", "$select": "id,subject,from,receivedDateTime,isRead"}
        if filter:
            params["$filter"] = filter
        if search:
            params["$search"] = f'"{search}"'
        data = await self._request("GET", "/me/messages", params=params)
        return [{
            "id": m.get("id"),
            "subject": m.get("subject", ""),
            "from": (m.get("from", {}) or {}).get("emailAddress", {}).get("address", ""),
            "receivedDateTime": m.get("receivedDateTime", ""),
            "isRead": m.get("isRead"),
        } for m in data.get("value", [])]

    async def mail_get(self, message_id: str, include_attachments: bool = False) -> dict:
        path = f"/me/messages/{message_id}"
        params = {"$expand": "attachments"} if include_attachments else None
        data = await self._request("GET", path, params=params)
        attachments = []
        if include_attachments:
            for a in data.get("attachments", []) or []:
                attachments.append({
                    "filename": a.get("name", ""),
                    "contentType": a.get("contentType", ""),
                    "data": a.get("contentBytes", ""),
                    "size": a.get("size"),
                })
        return {
            "id": data.get("id"),
            "subject": data.get("subject", ""),
            "from": (data.get("from", {}) or {}).get("emailAddress", {}).get("address", ""),
            "to": ", ".join((r.get("emailAddress", {}) or {}).get("address", "") for r in data.get("toRecipients", []) or []),
            "body": (data.get("body", {}) or {}).get("content", "")[:5000],
            "receivedDateTime": data.get("receivedDateTime", ""),
            "isRead": data.get("isRead"),
            "attachments": attachments,
        }

    async def mail_send(self, to: str, subject: str, body: str, cc: str = "", attachments: Optional[list] = None) -> dict:
        recipients = [{"emailAddress": {"address": x.strip()}} for x in to.split(",") if x.strip()]
        cc_list = [{"emailAddress": {"address": x.strip()}} for x in cc.split(",") if x.strip()] if cc else []
        message = {
            "subject": subject,
            "body": {"contentType": "Text", "content": body},
            "toRecipients": recipients,
            **({"ccRecipients": cc_list} if cc_list else {}),
        }
        if attachments:
            message["attachments"] = [
                {"@odata.type": "#microsoft.graph.fileAttachment", "name": a.get("filename", "archivo"),
                 "contentType": a.get("mimeType", "application/octet-stream"), "contentBytes": a.get("data", "")}
                for a in attachments
            ]
        payload = {"message": message, "saveToSentItems": True}
        await self._request("POST", "/me/sendMail", json_body=payload)
        return {"status": "sent", "to": to, "subject": subject}

    async def mail_set_read(self, message_id: str, read: bool = True) -> dict:
        await self._request("PATCH", f"/me/messages/{message_id}", json_body={"isRead": read})
        return {"id": message_id, "read": read}

    async def drafts(self) -> list:
        data = await self._request("GET", "/me/mailFolders/drafts/messages", params={"$top": 20})
        return [{
            "id": m.get("id"),
            "subject": m.get("subject", ""),
            "to": ", ".join((r.get("emailAddress", {}) or {}).get("address", "") for r in (m.get("toRecipients") or [])),
        } for m in data.get("value", [])]

    async def draft_send(self, message_id: str) -> dict:
        await self._request("POST", f"/me/messages/{message_id}/send")
        return {"id": message_id, "status": "sent"}

    async def folders(self) -> list:
        data = await self._request("GET", "/me/mailFolders")
        return [{"id": f.get("id"), "name": f.get("displayName", ""), "unread": f.get("unreadItemCount"), "total": f.get("totalItemCount")} for f in data.get("value", [])]

    async def mail_transcribe_attachment(self, message_id: str, attachment_index: int = 0, language: str = "") -> dict:
        import base64
        data = await self.mail_get(message_id, include_attachments=True)
        atts = data.get("attachments", []) or []
        if not atts or attachment_index >= len(atts):
            return {"ok": False, "message": "Adjunto no encontrado."}
        att = atts[attachment_index]
        from ...core.asr import transcribe
        try:
            text = transcribe(base64.b64decode(att["data"]), filename=att.get("filename") or "audio.m4a", language=language)
        except Exception as e:
            return {"ok": False, "message": f"Error transcribiendo: {e}"}
        return {"ok": True, "text": text, "filename": att.get("filename"), "contentType": att.get("contentType")}

    async def calendar_events(self, top: int = 20, calendar_id: str = "calendars/me") -> list:
        params = {"$top": top, "$orderby": "start/dateTime asc", "$select": "id,subject,start,end,organizer"}
        base = "/me/calendar/events" if calendar_id in ("me", "calendars/me") else f"/me/calendars/{calendar_id}/events"
        data = await self._request("GET", base, params=params)
        return [{
            "id": e.get("id"),
            "subject": e.get("subject", ""),
            "start": (e.get("start", {}) or {}).get("dateTime", ""),
            "end": (e.get("end", {}) or {}).get("dateTime", ""),
            "organizer": (e.get("organizer", {}) or {}).get("emailAddress", {}).get("address", ""),
        } for e in data.get("value", [])]

    async def calendar_create(self, subject: str, start: str, end: str, body: str = "", attendees: Optional[list] = None, calendar_id: str = "me") -> dict:
        payload = {"subject": subject, "start": {"dateTime": start}, "end": {"dateTime": end}}
        if body:
            payload["body"] = {"contentType": "Text", "content": body}
        if attendees:
            payload["attendees"] = [{"emailAddress": {"address": a}} for a in attendees]
        base = "/me/events" if calendar_id in ("me", "calendars/me") else f"/me/calendars/{calendar_id}/events"
        data = await self._request("POST", base, json_body=payload)
        return {"id": data.get("id"), "webLink": data.get("webLink", ""), "status": "created"}

    async def test_connection(self) -> Dict[str, Any]:
        try:
            await self._get_access_token()
            return {"ok": True, "message": "Microsoft 365 token válido.", "details": {}}
        except Exception as e:
            return {"ok": False, "message": f"Error de conexión con Microsoft 365: {e}", "details": {"error": str(e)}}
