import hashlib
import os
import re
from typing import Dict, Any, List, Optional
from ..base import BaseMcpService
from .client import WhatsAppClient, DEFAULT_BRIDGE_URL
from .tools import WHATSAPP_TOOLS

# Bridges run as containers on the same Docker network as the MCP gateway, so the
# gateway resolves them by their container name (wa-<slug>) unless WHATSAPP_BRIDGE_HOST
# is set to an explicit host/IP (e.g. if bridges run outside the shared network).
BRIDGE_HOST = (os.environ.get("WHATSAPP_BRIDGE_HOST") or "").strip()


def slug_for(instance_id: str) -> str:
    """Deterministic, DNS-safe slug for a WhatsApp account (container name)."""
    s = re.sub(r"[^a-z0-9]", "", (instance_id or "").lower())
    return s or "account"


def bridge_url_for(instance_id: str) -> str:
    """Deterministic bridge URL for an account (host + port derived from the slug)."""
    slug = slug_for(instance_id)
    try:
        port = 3001 + (int(hashlib.sha1(slug.encode()).hexdigest()[:8], 16) % 200)
    except Exception:
        port = 3010
    host = BRIDGE_HOST or f"wa-{slug}"
    return f"http://{host}:{port}"


class WhatsAppService(BaseMcpService):
    """WhatsApp connector (personal chat) via a per-account Baileys bridge, multiple accounts."""

    service_id: str = "whatsapp"
    name: str = "WhatsApp (chat personal)"
    description: str = "Send/receive WhatsApp messages via a self-hosted Baileys bridge, with multiple accounts (one phone each)."
    supports_instances: bool = True

    def __init__(self, config, secrets, enabled=True, instances=None):
        super().__init__(config, secrets, enabled)
        self.accounts: Dict[str, WhatsAppClient] = {}
        self.default_account_id = ""
        self.reload_accounts(instances or [])

    @staticmethod
    def _build_client(instance_id: str, cfg: Dict[str, Any], sec: Dict[str, str]) -> WhatsAppClient:
        return WhatsAppClient(bridge_url=bridge_url_for(instance_id), phone=cfg.get("phone", ""))

    def reload_accounts(self, instances: List[Dict[str, Any]]):
        self.accounts = {}
        self.default_account_id = ""
        for inst in instances or []:
            if not inst.get("enabled", True):
                continue
            iid = inst.get("instance_id")
            if not iid:
                continue
            self.accounts[iid] = self._build_client(iid, inst.get("config", {}), inst.get("secrets", {}))
            if inst.get("is_default"):
                self.default_account_id = iid
        if not self.default_account_id and self.accounts:
            self.default_account_id = next(iter(self.accounts))

    def get_account_summary(self) -> List[Dict[str, Any]]:
        out = []
        for iid, cli in self.accounts.items():
            out.append({
                "instance_id": iid,
                "name": "",
                "enabled": True,
                "is_default": iid == self.default_account_id,
                "configured": cli.is_configured(),
                "base_url": cli.bridge_url,
                "user_email": cli.phone,
                "fingerprint": "",
                "has_private_key": False,
                "has_passphrase": False,
                "has_secrets": cli.is_configured(),
            })
        return out

    def get_account_schema(self) -> Dict[str, Any]:
        return {
            "service_id": "whatsapp",
            "label": "WhatsApp (chat personal)",
            "config": [
                {"key": "phone", "label": "Número de WhatsApp (código de país + número)", "type": "text",
                 "required": True, "placeholder": "+573001234567"},
            ],
            "secrets": [],
        }

    def _resolve_client(self, account: Optional[str]) -> WhatsAppClient:
        if not account:
            account = self.default_account_id
        client = self.accounts.get(account or "")
        if not client:
            raise RuntimeError(
                f"Cuenta WhatsApp '{account}' no existe. Cuentas disponibles: {list(self.accounts.keys()) or '(ninguna)'}"
            )
        return client

    def is_configured(self) -> bool:
        return bool(self.accounts) and any(c.is_configured() for c in self.accounts.values())

    def get_tools(self) -> List[Dict[str, Any]]:
        if not self.enabled or not self.is_configured():
            return []
        import copy
        account_ids = list(self.accounts.keys())
        tools = []
        for tool in copy.deepcopy(WHATSAPP_TOOLS):
            props = tool.get("inputSchema", {}).get("properties", {})
            acc_prop = props.get("account")
            if acc_prop and account_ids:
                acc_prop["enum"] = account_ids
                if self.default_account_id:
                    acc_prop.setdefault("default", self.default_account_id)
            tools.append(tool)
        return tools

    async def call_tool(self, tool_name: str, arguments: Dict[str, Any]) -> Any:
        if not self.enabled or not self.is_configured():
            raise RuntimeError("WhatsApp service is not enabled or not fully configured.")

        args = dict(arguments or {})
        account = args.pop("account", None)

        if tool_name == "whatsapp_list_accounts":
            return self.get_account_summary()

        client = self._resolve_client(account)

        if tool_name == "whatsapp_status":
            return await client.test_connection()
        if tool_name == "whatsapp_list_chats":
            return await client.list_chats()
        if tool_name == "whatsapp_get_messages":
            return await client.get_messages(args.get("chat_id", ""), limit=int(args.get("limit") or 20))
        if tool_name == "whatsapp_send_message":
            return await client.send_message(args.get("chat_id", ""), args.get("message", ""))
        if tool_name == "whatsapp_send_media":
            return await client.send_media(
                args.get("chat_id", ""), args.get("media_type", ""), args.get("base64", ""),
                args.get("caption", ""), args.get("filename", ""),
            )
        if tool_name == "whatsapp_get_media":
            return await client.get_media(args.get("message_id", ""))
        if tool_name == "whatsapp_transcribe_media":
            return await client.transcribe_media(args.get("message_id", ""), args.get("language", ""))
        raise ValueError(f"Unknown WhatsApp tool: '{tool_name}'")

    async def test_connection(self) -> Dict[str, Any]:
        if self.default_account_id and self.default_account_id in self.accounts:
            return await self.accounts[self.default_account_id].test_connection()
        if self.accounts:
            return await next(iter(self.accounts.values())).test_connection()
        return {"ok": False, "message": "No hay cuentas de WhatsApp configuradas.", "details": {}}

    async def get_account_qr(self, account: str) -> Dict[str, Any]:
        client = self._resolve_client(account)
        qr, image = await client.get_qr_data_uri()
        return {"account": account, "qr": qr, "image": image}

    async def test_account(self, account: str) -> Dict[str, Any]:
        return await self._resolve_client(account).test_connection()
