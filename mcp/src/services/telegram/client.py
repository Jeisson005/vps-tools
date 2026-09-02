import logging
from typing import Dict, Any, Optional

logger = logging.getLogger("mcp.telegram")

# Telethon is imported lazily so the gateway never crashes at import time when
# the optional dependency is not installed yet.
_telethon = None


def _tg():
    global _telethon
    if _telethon is None:
        try:
            from telethon import TelegramClient  # noqa: F401
            from telethon.sessions import StringSession  # noqa: F401
            _telethon = (TelegramClient, StringSession)
        except Exception as e:
            raise RuntimeError(f"Telethon no está instalado: {e}")
    return _telethon


class TelegramMTClient:
    """Telegram user client built on Telethon (MTProto), with persistent session."""

    def __init__(self, api_id: str, api_hash: str, phone: str, session: str = ""):
        self.api_id = int(api_id) if api_id else 0
        self.api_hash = api_hash or ""
        self.phone = phone or ""
        self.session_string = session or ""
        self._client = None

    def is_configured(self) -> bool:
        return bool(self.api_id and self.api_hash and self.phone)

    def _make_client(self):
        TelegramClient, StringSession = _tg()
        if self._client:
            return self._client
        session = StringSession(self.session_string) if self.session_string else StringSession()
        self._client = TelegramClient(session, self.api_id, self.api_hash)
        return self._client

    async def _ensure(self):
        try:
            client = self._make_client()
            await client.connect()
            return client
        except Exception as e:
            raise RuntimeError(f"No se pudo conectar con Telegram: {e}")

    async def is_authorized(self) -> bool:
        try:
            client = await self._ensure()
            return bool(await client.is_user_authorized())
        except Exception as e:
            logger.debug(f"telegram is_authorized: {e}")
            return False

    async def request_code(self) -> Dict[str, Any]:
        client = await self._ensure()
        if await client.is_user_authorized():
            return {"ok": True, "already_authorized": True, "message": "La cuenta ya está autorizada."}
        sent = await client.send_code_request(self.phone)
        return {
            "ok": True,
            "already_authorized": False,
            "phone_code_hash": getattr(sent, "phone_code_hash", ""),
            "message": "Código enviado a Telegram. Proporciónalo en telegram_sign_in.",
        }

    async def sign_in(self, code: str, phone_code_hash: str = "") -> Dict[str, Any]:
        client = await self._ensure()
        if await client.is_user_authorized():
            return {"ok": True, "message": "Ya autorizado."}
        await client.sign_in(self.phone, code, phone_code_hash=phone_code_hash or None)
        await client.get_me()
        self.session_string = client.session.save()
        return {"ok": True, "session": self.session_string, "message": "Sesión de Telegram guardada."}

    async def logout(self) -> Dict[str, Any]:
        client = await self._ensure()
        try:
            await client.log_out()
        except Exception as e:
            logger.debug(f"telegram logout: {e}")
        self.session_string = ""
        return {"ok": True, "message": "Sesión cerrada."}

    async def list_chats(self, limit: int = 25) -> list:
        client = await self._ensure()
        out = []
        async for d in client.iter_dialogs():
            out.append({"id": d.id, "name": d.name or "", "type": type(d.entity).__name__})
            if len(out) >= limit:
                break
        return out

    async def send_message(self, entity: str, message: str) -> dict:
        client = await self._ensure()
        msg = await client.send_message(entity, message)
        return {"id": msg.id, "status": "sent", "to": entity}

    async def get_messages(self, entity: str, limit: int = 10) -> list:
        client = await self._ensure()
        out = []
        async for m in client.iter_messages(entity, limit=limit):
            out.append({
                "id": m.id,
                "from": getattr(m.sender, "username", "") or getattr(m.sender, "first_name", ""),
                "text": (m.message or "")[:2000],
                "date": str(m.date) if m.date else "",
                "media": self._media_type(m),
            })
        return out

    @staticmethod
    def _media_type(m) -> str:
        if not getattr(m, "media", None):
            return ""
        if getattr(m, "photo", None):
            return "photo"
        if getattr(m, "video", None):
            return "video"
        if getattr(m, "voice", None) or getattr(m, "audio", None):
            return "audio"
        if getattr(m, "document", None):
            return "document"
        return "media"

    async def get_media(self, entity: str, message_id: int) -> dict:
        import base64
        client = await self._ensure()
        msg = await client.get_messages(entity, ids=int(message_id))
        if not msg:
            raise RuntimeError(f"Mensaje {message_id} no encontrado.")
        if not getattr(msg, "media", None):
            return {"ok": False, "message": "El mensaje no tiene media."}
        data = await msg.download_media(file=bytes)
        if not data:
            return {"ok": False, "message": "No se pudo descargar la media."}
        fname = getattr(getattr(msg, "file", None), "name", "") or f"msg-{message_id}"
        return {
            "ok": True,
            "base64": base64.b64encode(data).decode(),
            "type": self._media_type(msg),
            "filename": fname,
        }

    async def send_media(self, entity: str, data: bytes, filename: str = "", caption: str = "", media_type: str = "document") -> dict:
        import base64
        if isinstance(data, str) and data.startswith("data:"):
            data = base64.b64decode(data.split(",", 1)[1])
        elif isinstance(data, str):
            data = base64.b64decode(data)
        client = await self._ensure()
        kwargs = {"caption": caption or None}
        if media_type == "photo":
            kwargs["force_document"] = False
        elif media_type == "voice":
            kwargs["voice_note"] = True
        elif media_type == "video_note":
            kwargs["video_note"] = True
        elif media_type == "audio":
            kwargs["voice_note"] = False
        else:
            kwargs["force_document"] = True
            if filename:
                import telethon
                kwargs["attributes"] = [telethon.types.DocumentAttributeFilename(filename)]
        sent = await client.send_file(entity, data, **kwargs)
        return {"ok": True, "id": sent.id, "status": "sent"}

    async def transcribe_message(self, entity: str, message_id: int, language: str = "") -> dict:
        import base64
        data = await self.get_media(entity, message_id)
        if not data.get("ok") or not data.get("base64"):
            return {"ok": False, "message": "No se pudo obtener la media."}
        if data.get("type") not in ("audio", "voice", "video"):
            return {"ok": False, "message": "El mensaje no es de audio para transcribir.", "type": data.get("type")}
        from ...core.asr import transcribe
        try:
            text = transcribe(base64.b64decode(data["base64"]), filename=data.get("filename") or "audio.oga", language=language)
        except Exception as e:
            return {"ok": False, "message": f"Error transcribiendo: {e}"}
        return {"ok": True, "text": text, "type": data.get("type")}

    async def test_connection(self) -> Dict[str, Any]:
        try:
            authorized = await self.is_authorized()
            return {
                "ok": authorized,
                "message": "Cuenta de Telegram autorizada." if authorized else "Cuenta de Telegram sin autorizar (haz login).",
                "details": {"authorized": authorized, "phone": self.phone},
            }
        except Exception as e:
            return {"ok": False, "message": f"Error de conexión con Telegram: {e}", "details": {"error": str(e)}}
