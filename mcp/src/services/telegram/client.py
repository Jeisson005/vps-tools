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
            })
        return out

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
