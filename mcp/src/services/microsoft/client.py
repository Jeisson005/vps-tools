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

    async def calendar_delete(self, event_id: str, calendar_id: str = "me") -> dict:
        if not event_id:
            raise ValueError("Se requiere 'event_id'.")
        base = f"/me/events/{event_id}" if calendar_id in ("me", "calendars/me", "") else f"/me/calendars/{calendar_id}/events/{event_id}"
        token = await self._get_access_token()
        async with httpx.AsyncClient(timeout=30.0) as client:
            res = await client.delete(f"{GRAPH}{base}", headers={"Authorization": f"Bearer {token}"})
            if res.status_code not in (200, 201, 202, 204):
                raise RuntimeError(f"Graph API error ({res.status_code}): {res.text[:300]}")
        return {"id": event_id, "status": "deleted"}

    # ---- Teams (chats y canales, cuenta personal con permisos delegados) ----
    # Permisos delegados requeridos: Team.ReadBasic.All, Channel.ReadBasic.All,
    # ChannelMessage.Read.All, ChannelMessage.Send, Chat.ReadWrite, ChatMessage.Send.
    @staticmethod
    def _fmt_chat_message(m: dict) -> dict:
        body = (m.get("body") or {})
        content = body.get("content", "") or ""
        sender = ((m.get("from") or {}).get("user") or {}).get("displayName", "")
        return {
            "id": m.get("id"),
            "body": content[:5000],
            "contentType": body.get("contentType", ""),
            "from": sender,
            "createdDateTime": m.get("createdDateTime", ""),
        }

    async def teams_joined(self) -> list:
        data = await self._request("GET", "/me/joinedTeams", params={"$select": "id,displayName,description"})
        return [{
            "id": t.get("id"),
            "displayName": t.get("displayName", ""),
            "description": t.get("description", ""),
        } for t in data.get("value", [])]

    async def teams_channels(self, team_id: str) -> list:
        if not team_id:
            raise ValueError("Se requiere 'team_id'.")
        data = await self._request("GET", f"/teams/{team_id}/channels")
        return [{
            "id": c.get("id"),
            "displayName": c.get("displayName", ""),
            "description": c.get("description", ""),
        } for c in data.get("value", [])]

    async def teams_channel_messages(self, team_id: str, channel_id: str, top: int = 20) -> list:
        if not team_id or not channel_id:
            raise ValueError("Se requieren 'team_id' y 'channel_id'.")
        data = await self._request(
            "GET", f"/teams/{team_id}/channels/{channel_id}/messages",
            params={"$top": top, "$orderby": "createdDateTime desc"},
        )
        return [self._fmt_chat_message(m) for m in data.get("value", [])]

    async def teams_channel_send(self, team_id: str, channel_id: str, message: str) -> dict:
        if not team_id or not channel_id or not message:
            raise ValueError("Se requieren 'team_id', 'channel_id' y 'message'.")
        data = await self._request(
            "POST", f"/teams/{team_id}/channels/{channel_id}/messages",
            json_body={"body": {"contentType": "text", "content": message}},
        )
        return {"id": data.get("id"), "status": "sent"}

    async def teams_chats(self, top: int = 20) -> list:
        data = await self._request("GET", "/me/chats", params={"$top": top, "$expand": "members"})
        out = []
        for c in data.get("value", []):
            members = []
            for m in c.get("members", []) or []:
                members.append((m.get("displayName") or "").strip())
            out.append({
                "id": c.get("id"),
                "topic": c.get("topic", ""),
                "chatType": c.get("chatType", ""),
                "members": [m for m in members if m][:10],
            })
        return out

    async def teams_chat_messages(self, chat_id: str, top: int = 20) -> list:
        if not chat_id:
            raise ValueError("Se requiere 'chat_id'.")
        data = await self._request(
            "GET", f"/me/chats/{chat_id}/messages",
            params={"$top": top, "$orderby": "createdDateTime desc"},
        )
        return [self._fmt_chat_message(m) for m in data.get("value", [])]

    async def teams_chat_send(self, chat_id: str, message: str) -> dict:
        if not chat_id or not message:
            raise ValueError("Se requieren 'chat_id' y 'message'.")
        data = await self._request(
            "POST", f"/me/chats/{chat_id}/messages",
            json_body={"body": {"contentType": "text", "content": message}},
        )
        return {"id": data.get("id"), "status": "sent"}

    # ---- OneDrive (archivos personales) ----
    # Permisos delegados requeridos: Files.ReadWrite.All.
    @staticmethod
    def _fmt_drive_item(it: dict) -> dict:
        return {
            "id": it.get("id"),
            "name": it.get("name", ""),
            "size": it.get("size"),
            "mimeType": ((it.get("file") or {}).get("mimeType")) if it.get("file") else None,
            "isFolder": bool(it.get("folder")),
            "lastModified": ((it.get("lastModifiedDateTime")) or ""),
            "webUrl": it.get("webUrl", ""),
        }

    async def onedrive_list(self, item_id: str = "", top: int = 50) -> list:
        base = "/me/drive/root/children" if not item_id or item_id in ("root", "me") else f"/me/drive/items/{item_id}/children"
        data = await self._request("GET", base, params={"$top": top})
        return [self._fmt_drive_item(it) for it in data.get("value", [])]

    async def onedrive_get(self, item_id: str) -> dict:
        if not item_id:
            raise ValueError("Se requiere 'item_id'.")
        data = await self._request("GET", f"/me/drive/items/{item_id}")
        return self._fmt_drive_item(data)

    async def onedrive_download(self, item_id: str) -> dict:
        import base64
        if not item_id:
            raise ValueError("Se requiere 'item_id'.")
        meta = await self.onedrive_get(item_id)
        if meta.get("isFolder"):
            raise ValueError("El item es una carpeta, no se puede descargar.")
        token = await self._get_access_token()
        async with httpx.AsyncClient(timeout=60.0) as client:
            res = await client.get(
                f"{GRAPH}/me/drive/items/{item_id}/content",
                headers={"Authorization": f"Bearer {token}"},
            )
            if res.status_code >= 400:
                raise RuntimeError(f"Graph API error ({res.status_code}): {res.text[:300]}")
            content = res.content
        if len(content) > 4 * 1024 * 1024:
            raise ValueError(f"Archivo muy grande ({len(content)} bytes, máx 4 MB por el MCP).")
        return {
            "id": item_id,
            "name": meta.get("name", ""),
            "mimeType": meta.get("mimeType", "application/octet-stream"),
            "size": len(content),
            "data": base64.b64encode(content).decode("ascii"),
        }

    async def onedrive_upload(self, name: str, content_text: str = "", data: str = "",
                              folder_id: str = "", mime_type: str = "text/plain") -> dict:
        import base64
        if not name:
            raise ValueError("Se requiere 'name'.")
        if data:
            raw = base64.b64decode(data)
        elif content_text is not None:
            raw = content_text.encode("utf-8")
        else:
            raise ValueError("Provee 'content_text' o 'data' (base64).")
        if len(raw) > 10 * 1024 * 1024:
            raise ValueError(f"Archivo muy grande ({len(raw)} bytes, máx 10 MB).")
        token = await self._get_access_token()
        if folder_id and folder_id not in ("root", "me"):
            url = f"{GRAPH}/me/drive/items/{folder_id}:/{name}:/content"
        else:
            url = f"{GRAPH}/me/drive/root:/{name}:/content"
        async with httpx.AsyncClient(timeout=60.0) as client:
            res = await client.put(
                url, content=raw,
                headers={"Authorization": f"Bearer {token}", "Content-Type": mime_type or "application/octet-stream"},
            )
            if res.status_code not in (200, 201):
                raise RuntimeError(f"Graph API error ({res.status_code}): {res.text[:300]}")
            created = res.json()
        return {"id": created.get("id"), "name": created.get("name", name),
                "size": created.get("size"), "webUrl": created.get("webUrl", ""), "status": "uploaded"}

    async def test_connection(self) -> Dict[str, Any]:
        try:
            await self._get_access_token()
            return {"ok": True, "message": "Microsoft 365 token válido.", "details": {}}
        except Exception as e:
            return {"ok": False, "message": f"Error de conexión con Microsoft 365: {e}", "details": {"error": str(e)}}
