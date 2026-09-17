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
DRIVE_SCOPE = "https://www.googleapis.com/auth/drive"
CONTACTS_SCOPE = "https://www.googleapis.com/auth/contacts.readonly"
SHEETS_SCOPE = "https://www.googleapis.com/auth/spreadsheets"
DOCS_SCOPE = "https://www.googleapis.com/auth/documents"
PHOTOS_SCOPE = "https://www.googleapis.com/auth/photoslibrary.readonly"

# Scopes solicitados en el flujo OAuth web del panel.
GOOGLE_SCOPES = f"{GMAIL_SCOPE} {CAL_SCOPE} {DRIVE_SCOPE} {CONTACTS_SCOPE} {SHEETS_SCOPE} {DOCS_SCOPE} {PHOTOS_SCOPE}"


class GoogleClient:
    """Minimal Google workspace client (Gmail + Calendar + Drive + Contacts + Sheets + Docs) using OAuth2 refresh tokens."""

    TOKEN_URL = "https://oauth2.googleapis.com/token"
    AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
    GMAIL_API = "https://gmail.googleapis.com/gmail/v1"
    CAL_API = "https://www.googleapis.com/calendar/v3"
    DRIVE_API = "https://www.googleapis.com/drive/v3"
    DRIVE_UPLOAD_API = "https://www.googleapis.com/upload/drive/v3/files"
    PEOPLE_API = "https://people.googleapis.com/v1"
    SHEETS_API = "https://sheets.googleapis.com/v4/spreadsheets"
    DOCS_API = "https://docs.googleapis.com/v1/documents"
    PHOTOS_API = "https://photoslibrary.googleapis.com/v1"

    def __init__(self, client_id: str, client_secret: str, refresh_token: str, scope: str = ""):
        self.client_id = client_id or ""
        self.client_secret = client_secret or ""
        self.refresh_token = refresh_token or ""
        self.scope = scope or GOOGLE_SCOPES
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

    async def gmail_get(self, message_id: str, format: str = "full", include_attachments: bool = False) -> dict:
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
        attachments = []
        if include_attachments:
            attachments = await self.gmail_get_attachments(message_id, data.get("payload", {}))
        return {
            "id": data.get("id"),
            "threadId": data.get("threadId"),
            "from": headers.get("From", ""),
            "to": headers.get("To", ""),
            "subject": headers.get("Subject", ""),
            "date": headers.get("Date", ""),
            "snippet": data.get("snippet", ""),
            "body": body[:5000],
            "attachments": attachments,
        }

    async def gmail_send(self, to: str, subject: str, body: str, cc: str = "", bcc: str = "", attachments: Optional[list] = None, from_addr: str = "") -> dict:
        mime = self._build_mime(to, subject, body, cc, bcc, attachments=attachments or [], from_addr=from_addr)
        raw = base64.urlsafe_b64encode(mime.encode("utf-8")).decode("ascii")
        data = await self._request(
            "POST", f"{self.GMAIL_API}/users/me/messages/send",
            json_body={"raw": raw}, headers={"Content-Type": "application/json"},
        )
        return {"id": data.get("id"), "status": "sent"}

    async def gmail_get_attachments(self, message_id: str, payload: dict) -> list:
        """Collect base64 attachments from a Gmail message payload."""
        out = []
        async def walk(part):
            if part.get("filename") and part.get("body", {}).get("attachmentId"):
                att = await self._request("GET", f"{self.GMAIL_API}/users/me/messages/{message_id}/attachments/{part['body']['attachmentId']}")
                out.append({
                    "filename": part.get("filename"),
                    "mimeType": part.get("mimeType", ""),
                    "size": part.get("body", {}).get("size"),
                    "data": att.get("data", ""),
                })
                return
            for p in part.get("parts", []) or []:
                await walk(p)
        await walk(payload)
        return out

    async def gmail_drafts(self) -> list:
        data = await self._request("GET", f"{self.GMAIL_API}/users/me/drafts", params={"maxResults": 20})
        return [{"id": d.get("id"), "message_id": (d.get("message") or {}).get("id")} for d in data.get("drafts", [])]

    async def gmail_draft_create(self, to: str, subject: str, body: str, attachments: Optional[list] = None, from_addr: str = "") -> dict:
        mime = self._build_mime(to, subject, body, "", "", attachments=attachments or [], from_addr=from_addr)
        raw = base64.urlsafe_b64encode(mime.encode("utf-8")).decode("ascii")
        data = await self._request("POST", f"{self.GMAIL_API}/users/me/drafts", json_body={"message": {"raw": raw}})
        return {"id": data.get("id"), "message_id": (data.get("message") or {}).get("id"), "status": "draft"}

    async def gmail_draft_send(self, draft_id: str) -> dict:
        data = await self._request(
            "POST", f"{self.GMAIL_API}/users/me/drafts/send",
            json_body={"id": draft_id}, headers={"Content-Type": "application/json"},
        )
        return {"id": (data.get("message") or {}).get("id", data.get("id")), "status": "sent"}

    async def gmail_draft_delete(self, draft_id: str) -> dict:
        await self._request("DELETE", f"{self.GMAIL_API}/users/me/drafts/{draft_id}")
        return {"id": draft_id, "status": "deleted"}

    async def gmail_sendas_list(self) -> list:
        """List the account's SendAs identities (extra 'send mail as' addresses)."""
        data = await self._request("GET", f"{self.GMAIL_API}/users/me/settings/sendAs")
        return [
            {
                "email": s.get("sendAsEmail", ""),
                "displayName": s.get("displayName", ""),
                "isDefault": bool(s.get("isDefault")),
                "isPrimary": bool(s.get("isPrimary")),
                "replyTo": s.get("replyToAddress", ""),
            }
            for s in data.get("sendAs", [])
        ]

    async def gmail_labels(self) -> list:
        data = await self._request("GET", f"{self.GMAIL_API}/users/me/labels")
        return [{"id": l.get("id"), "name": l.get("name"), "type": l.get("type")} for l in data.get("labels", [])]

    async def gmail_set_read(self, message_id: str, read: bool = True) -> dict:
        body = {"removeLabelIds": ["UNREAD"]} if read else {"addLabelIds": ["UNREAD"]}
        await self._request("POST", f"{self.GMAIL_API}/users/me/messages/{message_id}/modify", json_body=body)
        return {"id": message_id, "read": read}

    async def gmail_thread(self, thread_id: str) -> dict:
        data = await self._request("GET", f"{self.GMAIL_API}/users/me/threads/{thread_id}", params={"format": "full"})
        msgs = []
        for m in data.get("messages", []):
            headers = {}
            for h in m.get("payload", {}).get("headers", []) or []:
                headers[h.get("name", "")] = h.get("value", "")
            msgs.append({
                "id": m.get("id"),
                "from": headers.get("From", ""),
                "subject": headers.get("Subject", ""),
                "snippet": m.get("snippet", ""),
            })
        return {"id": thread_id, "messages": msgs}

    async def gmail_transcribe_attachment(self, message_id: str, attachment_index: int = 0, language: str = "") -> dict:
        import base64
        info = await self._request("GET", f"{self.GMAIL_API}/users/me/messages/{message_id}", params={"format": "full"})
        atts = await self.gmail_get_attachments(message_id, info.get("payload", {}))
        if not atts or attachment_index >= len(atts):
            return {"ok": False, "message": "Adjunto no encontrado."}
        att = atts[attachment_index]
        from ...core.asr import transcribe
        try:
            text = transcribe(base64.urlsafe_b64decode(att["data"] + "=" * (-len(att["data"]) % 4)), filename=att.get("filename") or "audio.m4a", language=language)
        except Exception as e:
            return {"ok": False, "message": f"Error transcribiendo: {e}"}
        return {"ok": True, "text": text, "filename": att.get("filename"), "mimeType": att.get("mimeType")}

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

    async def calendar_delete(self, event_id: str, calendar_id: str = "primary") -> dict:
        await self._request("DELETE", f"{self.CAL_API}/calendars/{calendar_id}/events/{event_id}")
        return {"id": event_id, "status": "deleted"}

    # ---- Drive ----
    async def _request_bytes(self, method: str, url: str, *, params: Optional[dict] = None) -> bytes:
        token = await self._get_access_token()
        h = {"Authorization": f"Bearer {token}"}
        async with httpx.AsyncClient(timeout=60.0) as client:
            res = await client.request(method, url, params=params, headers=h)
            if res.status_code >= 400:
                raise RuntimeError(f"Google API error ({res.status_code}): {res.text[:300]}")
            return res.content

    async def drive_list(self, query: str = "", page_size: int = 20, order_by: str = "modifiedTime desc") -> list:
        params: Dict[str, Any] = {
            "pageSize": max(1, min(int(page_size or 20), 100)),
            "orderBy": order_by or "modifiedTime desc",
            "fields": "files(id,name,mimeType,size,modifiedTime,parents,webViewLink)",
        }
        if query:
            params["q"] = query
        data = await self._request("GET", f"{self.DRIVE_API}/files", params=params)
        return [
            {
                "id": f.get("id"),
                "name": f.get("name", ""),
                "mimeType": f.get("mimeType", ""),
                "size": f.get("size"),
                "modifiedTime": f.get("modifiedTime", ""),
                "parents": f.get("parents", []),
                "webViewLink": f.get("webViewLink", ""),
            }
            for f in data.get("files", [])
        ]

    async def drive_get(self, file_id: str) -> dict:
        data = await self._request(
            "GET", f"{self.DRIVE_API}/files/{file_id}",
            params={"fields": "id,name,mimeType,size,modifiedTime,createdTime,parents,owners,webViewLink,webContentLink"},
        )
        return {
            "id": data.get("id"),
            "name": data.get("name", ""),
            "mimeType": data.get("mimeType", ""),
            "size": data.get("size"),
            "modifiedTime": data.get("modifiedTime", ""),
            "createdTime": data.get("createdTime", ""),
            "parents": data.get("parents", []),
            "owners": [o.get("emailAddress", "") for o in data.get("owners", []) or []],
            "webViewLink": data.get("webViewLink", ""),
            "webContentLink": data.get("webContentLink", ""),
        }

    async def drive_download(self, file_id: str) -> dict:
        meta = await self.drive_get(file_id)
        mime = meta.get("mimeType", "")
        # Documentos nativos de Google no admiten alt=media: se exportan.
        export_mime = ""
        if mime == "application/vnd.google-apps.document":
            export_mime = "text/plain"
        elif mime == "application/vnd.google-apps.spreadsheet":
            export_mime = "text/csv"
        elif mime == "application/vnd.google-apps.presentation":
            export_mime = "text/plain"
        try:
            if export_mime:
                raw = await self._request_bytes(
                    "GET", f"{self.DRIVE_API}/files/{file_id}/export", params={"mimeType": export_mime}
                )
                filename = (meta.get("name") or "documento") + ("csv" if export_mime == "text/csv" else ".txt")
            else:
                raw = await self._request_bytes("GET", f"{self.DRIVE_API}/files/{file_id}", params={"alt": "media"})
                filename = meta.get("name") or "archivo"
        except Exception as e:
            return {"ok": False, "message": f"No se pudo descargar: {e}", "meta": meta}
        if len(raw) > 4 * 1024 * 1024:
            return {"ok": False, "message": f"Archivo demasiado grande ({len(raw)} bytes > 4 MB).", "meta": meta, "size": len(raw)}
        return {
            "ok": True,
            "filename": filename,
            "mimeType": export_mime or mime,
            "size": len(raw),
            "data": base64.b64encode(raw).decode("ascii"),
            "meta": meta,
        }

    async def drive_create_folder(self, name: str, parent_id: str = "") -> dict:
        body: Dict[str, Any] = {"name": name, "mimeType": "application/vnd.google-apps.folder"}
        if parent_id:
            body["parents"] = [parent_id]
        data = await self._request("POST", f"{self.DRIVE_API}/files", params={"fields": "id,name,mimeType"}, json_body=body)
        return {"id": data.get("id"), "name": data.get("name", name), "mimeType": data.get("mimeType", ""), "status": "created"}

    async def drive_upload(self, name: str, data_b64: str = "", content_text: str = "",
                           mime_type: str = "", parent_id: str = "") -> dict:
        metadata: Dict[str, Any] = {"name": name, "mimeType": mime_type or "application/octet-stream"}
        if parent_id:
            metadata["parents"] = [parent_id]
        if not content_text and not data_b64:
            # Sin contenido: solo crea el archivo por metadatos (sirve para
            # Docs/Sheets/Slides nativos y carpetas lógicas).
            data = await self._request("POST", f"{self.DRIVE_API}/files",
                                       params={"fields": "id,name,mimeType,size"}, json_body=metadata)
            return {"id": data.get("id"), "name": data.get("name", name),
                    "mimeType": data.get("mimeType", ""), "size": data.get("size"), "status": "created"}
        if content_text:
            raw = content_text.encode("utf-8")
            metadata["mimeType"] = mime_type or "text/plain"
        else:
            try:
                raw = base64.b64decode(data_b64 + "=" * (-len(data_b64) % 4))
            except Exception as e:
                raise RuntimeError(f"data base64 inválido: {e}")
        if len(raw) > 10 * 1024 * 1024:
            raise RuntimeError(f"Archivo demasiado grande ({len(raw)} bytes > 10 MB).")
        boundary = "vpsmcp" + uuid.uuid4().hex[:12]
        meta_json = json.dumps(metadata).encode("utf-8")
        body = (
            f"--{boundary}\r\nContent-Type: application/json; charset=UTF-8\r\n\r\n".encode()
            + meta_json + b"\r\n"
            + f"--{boundary}\r\nContent-Type: {metadata['mimeType']}\r\n\r\n".encode()
            + raw + b"\r\n"
            + f"--{boundary}--\r\n".encode()
        )
        token = await self._get_access_token()
        async with httpx.AsyncClient(timeout=60.0) as client:
            res = await client.post(
                self.DRIVE_UPLOAD_API,
                params={"uploadType": "multipart", "fields": "id,name,mimeType,size"},
                content=body,
                headers={"Authorization": f"Bearer {token}", "Content-Type": f'multipart/related; boundary="{boundary}"'},
            )
            if res.status_code >= 400:
                raise RuntimeError(f"Google API error ({res.status_code}): {res.text[:300]}")
            data = res.json() if res.content else {}
        return {"id": data.get("id"), "name": data.get("name", name), "mimeType": data.get("mimeType", ""), "size": data.get("size"), "status": "uploaded"}

    async def drive_delete(self, file_id: str) -> dict:
        await self._request("DELETE", f"{self.DRIVE_API}/files/{file_id}")
        return {"id": file_id, "status": "deleted"}

    # ---- Contacts (People API, solo lectura) ----
    @staticmethod
    def _person_to_dict(p: dict) -> dict:
        names = p.get("names", []) or []
        emails = [e.get("value", "") for e in (p.get("emailAddresses", []) or []) if e.get("value")]
        phones = [t.get("value", "") for t in (p.get("phoneNumbers", []) or []) if t.get("value")]
        orgs = [o.get("name", "") for o in (p.get("organizations", []) or []) if o.get("name")]
        return {
            "resourceName": p.get("resourceName", ""),
            "name": names[0].get("displayName", "") if names else "",
            "emails": emails,
            "phones": phones,
            "organizations": orgs,
        }

    async def contacts_search(self, query: str, page_size: int = 10) -> list:
        data = await self._request(
            "GET", f"{self.PEOPLE_API}/people:searchContacts",
            params={
                "query": query,
                "readMask": "names,emailAddresses,phoneNumbers,organizations",
                "pageSize": max(1, min(int(page_size or 10), 30)),
            },
        )
        return [self._person_to_dict(r.get("person", {})) for r in data.get("results", [])]

    async def contacts_list(self, page_size: int = 20) -> list:
        data = await self._request(
            "GET", f"{self.PEOPLE_API}/people/me/connections",
            params={
                "personFields": "names,emailAddresses,phoneNumbers,organizations",
                "pageSize": max(1, min(int(page_size or 20), 100)),
            },
        )
        return [self._person_to_dict(p) for p in data.get("connections", [])]

    # ---- Sheets ----
    async def sheets_info(self, spreadsheet_id: str) -> dict:
        data = await self._request(
            "GET", f"{self.SHEETS_API}/{spreadsheet_id}",
            params={"fields": "spreadsheetId,properties.title,sheets.properties.title,sheets.properties.gridProperties"},
        )
        return {
            "id": data.get("spreadsheetId"),
            "title": (data.get("properties") or {}).get("title", ""),
            "tabs": [(s.get("properties") or {}).get("title", "") for s in data.get("sheets", [])],
        }

    async def sheets_read(self, spreadsheet_id: str, cell_range: str) -> dict:
        data = await self._request("GET", f"{self.SHEETS_API}/{spreadsheet_id}/values/{cell_range}")
        return {"range": data.get("range", cell_range), "values": data.get("values", [])}

    async def sheets_append(self, spreadsheet_id: str, cell_range: str, values: list) -> dict:
        data = await self._request(
            "POST", f"{self.SHEETS_API}/{spreadsheet_id}/values/{cell_range}:append",
            params={"valueInputOption": "USER_ENTERED"},
            json_body={"majorDimension": "ROWS", "values": values},
        )
        updates = data.get("updates", {}) or {}
        return {"updatedRange": updates.get("updatedRange", ""), "updatedCells": updates.get("updatedCells", 0), "status": "appended"}

    async def sheets_update(self, spreadsheet_id: str, cell_range: str, values: list) -> dict:
        data = await self._request(
            "PUT", f"{self.SHEETS_API}/{spreadsheet_id}/values/{cell_range}",
            params={"valueInputOption": "USER_ENTERED"},
            json_body={"majorDimension": "ROWS", "values": values},
        )
        return {"updatedRange": data.get("updatedRange", ""), "updatedCells": data.get("updatedCells", 0), "status": "updated"}

    # ---- Docs ----
    @staticmethod
    def _doc_to_text(doc: dict) -> str:
        parts = []
        for el in ((doc.get("body") or {}).get("content") or []):
            para = el.get("paragraph") or {}
            for pel in para.get("elements") or []:
                text_run = pel.get("textRun") or {}
                if text_run.get("content"):
                    parts.append(text_run["content"])
        return "".join(parts)

    async def docs_get(self, document_id: str) -> dict:
        data = await self._request("GET", f"{self.DOCS_API}/{document_id}", params={"fields": "documentId,title,body"})
        text = self._doc_to_text(data)
        capped = len(text) > 8000
        return {
            "id": data.get("documentId"),
            "title": data.get("title", ""),
            "chars": len(text),
            "truncated": capped,
            "text": text[:8000] if capped else text,
        }

    async def docs_append(self, document_id: str, text: str) -> dict:
        meta = await self._request("GET", f"{self.DOCS_API}/{document_id}", params={"fields": "body.content.endIndex"})
        content = ((meta.get("body") or {}).get("content") or [])
        end_index = (content[-1].get("endIndex") if content else 2) or 2
        if not text.endswith("\n"):
            text = text + "\n"
        data = await self._request(
            "POST", f"{self.DOCS_API}/{document_id}:batchUpdate",
            json_body={"requests": [{"insertText": {"location": {"index": max(end_index - 1, 1)}, "text": text}}]},
        )
        replies = data.get("replies", []) or []
        return {"id": document_id, "status": "appended", "chars_added": len(text), "replies": len(replies)}

    # ---- Photos (Library API, solo lectura) ----
    @staticmethod
    def _photo_to_dict(m: dict) -> dict:
        meta = m.get("mediaMetadata") or {}
        return {
            "id": m.get("id", ""),
            "description": m.get("description", ""),
            "mimeType": m.get("mimeType", ""),
            "creationTime": meta.get("creationTime", ""),
            "width": meta.get("width", ""),
            "height": meta.get("height", ""),
            "productUrl": m.get("productUrl", ""),
            # baseUrl caduca (~60 min): sirve para ver/descargar la imagen directamente.
            "baseUrl": m.get("baseUrl", ""),
        }

    async def photos_list(self, page_size: int = 20) -> dict:
        data = await self._request(
            "GET", f"{self.PHOTOS_API}/mediaItems",
            params={"pageSize": max(1, min(int(page_size or 20), 100))},
        )
        return {"items": [self._photo_to_dict(m) for m in data.get("mediaItems", [])],
                "nextPageToken": data.get("nextPageToken", "")}

    async def photos_get(self, media_item_id: str) -> dict:
        data = await self._request("GET", f"{self.PHOTOS_API}/mediaItems/{media_item_id}")
        return self._photo_to_dict(data)

    async def photos_search(self, year: int = 0, month: int = 0, day: int = 0,
                            content_category: str = "", media_type: str = "ALL_MEDIA",
                            page_size: int = 20) -> dict:
        body: Dict[str, Any] = {"pageSize": max(1, min(int(page_size or 20), 100))}
        filters: Dict[str, Any] = {}
        if year:
            date: Dict[str, int] = {"year": int(year)}
            if month:
                date["month"] = int(month)
            if day:
                date["day"] = int(day)
            filters["dateFilter"] = {"dates": [date]}
        if content_category:
            filters["contentFilter"] = {"includedContentCategories": [content_category.upper()]}
        if media_type and media_type.upper() != "ALL_MEDIA":
            filters["mediaTypeFilter"] = {"mediaTypes": [media_type.upper()]}
        if filters:
            body["filters"] = filters
        data = await self._request("POST", f"{self.PHOTOS_API}/mediaItems:search", json_body=body)
        return {"items": [self._photo_to_dict(m) for m in data.get("mediaItems", [])],
                "nextPageToken": data.get("nextPageToken", "")}

    async def photos_albums(self, page_size: int = 20) -> dict:
        data = await self._request(
            "GET", f"{self.PHOTOS_API}/albums",
            params={"pageSize": max(1, min(int(page_size or 20), 50))},
        )
        return {"albums": [
            {"id": a.get("id", ""), "title": a.get("title", ""),
             "items": a.get("totalMediaItems", ""), "url": a.get("productUrl", "")}
            for a in data.get("albums", [])
        ]}

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
    def _build_mime(to: str, subject: str, body: str, cc: str = "", bcc: str = "", attachments: Optional[list] = None, from_addr: str = "") -> str:
        import mimetypes
        attachments = attachments or []
        boundary = "vpsmcp" + uuid.uuid4().hex[:12]
        lines = [f"From: {from_addr.strip()}" if from_addr and from_addr.strip() else "From: me", f"To: {to}"]
        if cc:
            lines.append(f"Cc: {cc}")
        if bcc:
            lines.append(f"Bcc: {bcc}")
        lines += [
            "Subject: " + subject[:998],
            "MIME-Version: 1.0",
            f"Content-Type: multipart/mixed; boundary=\"{boundary}\"",
            "",
            f"--{boundary}",
            "Content-Type: text/plain; charset=UTF-8",
            "",
            body,
        ]
        for att in attachments:
            filename = att.get("filename", "archivo")
            mime_type = att.get("mimeType") or mimetypes.guess_type(filename)[0] or "application/octet-stream"
            data = att.get("data", "")
            # Gmail raw expects URL-safe base64.
            try:
                raw_b64 = base64.urlsafe_b64decode(data + "=" * (-len(data) % 4))
            except Exception:
                raw_b64 = data.encode("latin-1", errors="ignore")
            lines += [
                f"--{boundary}",
                f"Content-Type: {mime_type}",
                "Content-Transfer-Encoding: base64",
                f"Content-Disposition: attachment; filename=\"{filename}\"",
                "",
                base64.b64encode(raw_b64).decode(),
            ]
        lines += [f"--{boundary}--", ""]
        return "\r\n".join(lines)
