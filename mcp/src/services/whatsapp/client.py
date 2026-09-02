import logging
from typing import Dict, Any, List, Optional
import httpx

logger = logging.getLogger("mcp.whatsapp")

# Default bridge location used when an account does not specify one. The bridge is
# a host-side process (the MCP container has no Node); override per deployment via
# env if needed.
DEFAULT_BRIDGE_URL = "http://127.0.0.1:3010"


class WhatsAppClient:
    """WhatsApp client that talks to a per-account Baileys bridge over HTTP."""

    def __init__(self, bridge_url: str, phone: str = ""):
        self.bridge_url = (bridge_url or DEFAULT_BRIDGE_URL).rstrip("/")
        self.phone = phone or ""

    def is_configured(self) -> bool:
        return bool(self.bridge_url)

    async def _get(self, path: str):
        async with httpx.AsyncClient(timeout=15.0) as client:
            res = await client.get(f"{self.bridge_url}{path}")
            if res.status_code >= 400:
                raise RuntimeError(f"WhatsApp bridge error ({res.status_code}): {res.text[:200]}")
            return res.json()

    async def _post(self, path: str, payload: dict):
        async with httpx.AsyncClient(timeout=20.0) as client:
            res = await client.post(f"{self.bridge_url}{path}", json=payload)
            if res.status_code >= 400:
                raise RuntimeError(f"WhatsApp bridge error ({res.status_code}): {res.text[:200]}")
            return res.json()

    async def status(self) -> Dict[str, Any]:
        return await self._get("/status")

    async def is_linked(self) -> bool:
        try:
            data = await self.status()
            return bool(data.get("loggedIn") or data.get("connected"))
        except Exception:
            return False

    async def get_qr(self) -> str:
        data = await self._get("/status")
        return data.get("qr", "") or ""

    async def get_qr_data_uri(self):
        """Return (raw_qr, image_data_uri) rendering the bridge QR as a PNG."""
        qr = await self.get_qr()
        if not qr:
            return "", ""
        try:
            import base64
            import io
            import qrcode
            img = qrcode.make(qr)
            buf = io.BytesIO()
            img.save(buf, format="PNG")
            return qr, "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode()
        except Exception as e:
            logger.debug(f"qr render: {e}")
            return qr, ""

    async def list_chats(self) -> list:
        data = await self._get("/chats")
        return data.get("chats", [])

    async def get_messages(self, chat_id: str, limit: int = 20) -> list:
        data = await self._get(f"/messages?chatId={chat_id}")
        return data.get("messages", [])[:limit]

    async def get_history(self, chat_id: str, limit: int = 50) -> list:
        # Real, restart-proof history from disk (up to WHATSAPP_HISTORY_LIMIT).
        data = await self._get(f"/history?chatId={chat_id}&limit={limit}")
        return data.get("messages", [])

    async def send_message(self, chat_id: str, text: str) -> dict:
        return await self._post("/send", {"chatId": chat_id, "text": text})

    async def get_media(self, message_id: str) -> dict:
        return await self._get(f"/media?id={message_id}")

    async def get_media_bytes(self, message_id: str) -> bytes:
        async with httpx.AsyncClient(timeout=60.0) as client:
            r = await client.get(f"{self.bridge_url}/download?id={message_id}")
            if r.status_code != 200:
                raise RuntimeError(f"Descarga de media falló ({r.status_code})")
            return r.content

    async def send_media(self, chat_id: str, media_type: str, base64: str, caption: str = "", filename: str = "") -> dict:
        return await self._post("/send-media", {
            "chatId": chat_id, "mediaType": media_type, "base64": base64,
            "caption": caption, "filename": filename,
        })

    async def transcribe_media(self, message_id: str, language: str = "") -> dict:
        import os
        data = await self.get_media(message_id)
        if not data.get("size", 0) and not data.get("base64"):
            return {"ok": False, "message": "No se encontró la media.", "media": data}
        try:
            raw = await self.get_media_bytes(message_id)
        except Exception as e:
            return {"ok": False, "message": f"Error descargando media: {e}", "media": data}
        from ..core.asr import transcribe
        mimetype = data.get("mimetype", "")
        ext = (mimetype.rsplit("/", 1)[-1] if "/" in mimetype else "oga") or "oga"
        try:
            text = transcribe(raw, filename="msg." + ext, language=language)
        except Exception as e:
            return {"ok": False, "message": f"Error transcribiendo: {e}", "media": data}
        return {"ok": True, "text": text, "type": data.get("type"), "mimetype": mimetype}

    async def test_connection(self) -> Dict[str, Any]:
        try:
            data = await self.status()
            linked = bool(data.get("loggedIn") or data.get("connected"))
            return {
                "ok": linked,
                "message": "WhatsApp vinculado y conectado." if linked else "WhatsApp sin vincular (escanea el QR).",
                "details": {"linked": linked, "has_qr": bool(data.get("qr"))},
            }
        except Exception as e:
            return {"ok": False, "message": f"Error de conexión con el bridge de WhatsApp: {e}", "details": {"error": str(e)}}
