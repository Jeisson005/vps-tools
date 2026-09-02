from typing import Dict, Any, List, Optional
from ..base import BaseMcpService
from .client import TelegramMTClient
from .tools import TELEGRAM_TOOLS


class TelegramService(BaseMcpService):
    """Telegram (MTProto / Telethon) connector for personal chat, multiple accounts."""

    service_id: str = "telegram"
    name: str = "Telegram (chat personal)"
    description: str = "Send/receive Telegram messages and list chats via Telethon (MTProto), with multiple accounts."
    supports_instances: bool = True

    def __init__(self, config, secrets, enabled=True, instances=None):
        super().__init__(config, secrets, enabled)
        self.accounts: Dict[str, TelegramMTClient] = {}
        self.default_account_id = ""
        self.reload_accounts(instances or [])

    @staticmethod
    def _build_client(cfg: Dict[str, Any], sec: Dict[str, str]) -> TelegramMTClient:
        return TelegramMTClient(
            api_id=sec.get("api_id", ""),
            api_hash=sec.get("api_hash", ""),
            phone=cfg.get("phone", "") or sec.get("phone", ""),
            session=sec.get("session", ""),
        )

    def reload_accounts(self, instances: List[Dict[str, Any]]):
        self.accounts = {}
        self.default_account_id = ""
        for inst in instances or []:
            if not inst.get("enabled", True):
                continue
            iid = inst.get("instance_id")
            if not iid:
                continue
            self.accounts[iid] = self._build_client(inst.get("config", {}), inst.get("secrets", {}))
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
                "base_url": "telegram",
                "user_email": cli.phone,
                "fingerprint": "",
                "has_private_key": False,
                "has_passphrase": False,
                "has_secrets": cli.is_configured(),
            })
        return out

    def get_account_schema(self) -> Dict[str, Any]:
        return {
            "service_id": "telegram",
            "label": "Telegram (chat personal)",
            "config": [
                {"key": "phone", "label": "Número de teléfono (código de país + número)", "type": "text",
                 "required": True, "placeholder": "+573001234567"},
            ],
            "secrets": [
                {"key": "api_id", "label": "API ID (my.telegram.org)", "type": "text", "required": True},
                {"key": "api_hash", "label": "API Hash (my.telegram.org)", "type": "password", "required": True},
                {"key": "session", "label": "Sesión (se genera al hacer login; opcional)", "type": "textarea",
                 "required": False, "placeholder": "1BQM... (StringSession)"},
            ],
        }

    def _resolve_client(self, account: Optional[str]) -> TelegramMTClient:
        if not account:
            account = self.default_account_id
        client = self.accounts.get(account or "")
        if not client:
            raise RuntimeError(
                f"Cuenta Telegram '{account}' no existe. Cuentas disponibles: {list(self.accounts.keys()) or '(ninguna)'}"
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
        for tool in copy.deepcopy(TELEGRAM_TOOLS):
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
            raise RuntimeError("Telegram service is not enabled or not fully configured.")

        args = dict(arguments or {})
        account = args.pop("account", None)

        if tool_name == "telegram_list_accounts":
            return self.get_account_summary()

        client = self._resolve_client(account)

        if tool_name == "telegram_status":
            return await client.test_connection()
        if tool_name == "telegram_request_code":
            return await client.request_code()
        if tool_name == "telegram_sign_in":
            result = await client.sign_in(args.get("code", ""), args.get("phone_code_hash", ""))
            if result.get("ok") and result.get("session"):
                await self._persist_session(client)
            return result
        if tool_name == "telegram_logout":
            result = await client.logout()
            await self._persist_session(client)
            return result
        if tool_name == "telegram_list_chats":
            return await client.list_chats(limit=int(args.get("limit") or 25))
        if tool_name == "telegram_send_message":
            return await client.send_message(args.get("entity", ""), args.get("message", ""))
        if tool_name == "telegram_get_messages":
            return await client.get_messages(args.get("entity", ""), limit=int(args.get("limit") or 10))
        raise ValueError(f"Unknown Telegram tool: '{tool_name}'")

    async def _persist_session(self, client: TelegramMTClient):
        """Persist the (possibly updated) session string back to the account."""
        try:
            from ..core.registry import registry
            from ..core.db import get_service_instance
            iid = next((k for k, c in self.accounts.items() if c is client), None)
            if not iid:
                return
            inst = get_service_instance("telegram", iid)
            if not inst:
                return
            secrets = dict(inst["secrets"])
            secrets["session"] = client.session_string
            registry.save_instance("telegram", iid, True, inst["config"], secrets, inst["is_default"], inst.get("name", ""))
        except Exception as e:
            logger = __import__("logging").getLogger("mcp.telegram")
            logger.debug(f"persist session: {e}")

    async def test_connection(self) -> Dict[str, Any]:
        if self.default_account_id and self.default_account_id in self.accounts:
            return await self.accounts[self.default_account_id].test_connection()
        if self.accounts:
            return await next(iter(self.accounts.values())).test_connection()
        return {"ok": False, "message": "No hay cuentas de Telegram configuradas.", "details": {}}

    async def test_account(self, account: str) -> Dict[str, Any]:
        return await self._resolve_client(account).test_connection()
