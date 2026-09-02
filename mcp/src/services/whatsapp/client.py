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

    async def list_chats(self) -> list:
        data = await self._get("/chats")
        return data.get("chats", [])

    async def get_messages(self, chat_id: str, limit: int = 20) -> list:
        data = await self._get(f"/messages?chatId={chat_id}")
        return data.get("messages", [])[:limit]

    async def send_message(self, chat_id: str, text: str) -> dict:
        return await self._post("/send", {"chatId": chat_id, "text": text})

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
