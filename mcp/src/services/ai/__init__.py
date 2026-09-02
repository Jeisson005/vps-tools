from typing import Dict, Any, List, Optional
from ..base import BaseMcpService
from ...core.ai import AiClient
from .tools import AI_TOOLS


class AiService(BaseMcpService):
    """Transparent LLM helper supporting multiple provider accounts (panel-managed)."""

    service_id: str = "ai"
    name: str = "AI (LLM helper)"
    description: str = "Run a single LLM completion with configured AI providers, one or several accounts."
    supports_instances: bool = True

    def __init__(self, config, secrets, enabled=True, instances=None):
        super().__init__(config, secrets, enabled)
        self.accounts: Dict[str, AiClient] = {}
        self.default_account_id = ""
        self.reload_accounts(instances or [])

    @staticmethod
    def _build_client(cfg: Dict[str, Any], sec: Dict[str, str]) -> AiClient:
        return AiClient(
            base_url=cfg.get("base_url", ""),
            api_key=sec.get("api_key", ""),
            model=cfg.get("model", ""),
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
                "base_url": cli.base_url,
                "user_email": cli.model,
                "fingerprint": "",
                "has_private_key": False,
                "has_passphrase": bool(cli.api_key),
                "has_secrets": bool(cli.api_key),
            })
        return out

    def get_account_schema(self) -> Dict[str, Any]:
        return {
            "service_id": "ai",
            "label": "AI (LLM provider)",
            "config": [
                {"key": "base_url", "label": "Base URL (OpenAI-compatible)", "type": "url", "required": True,
                 "placeholder": "https://api.openai.com/v1"},
                {"key": "model", "label": "Model", "type": "text", "required": True,
                 "placeholder": "gpt-4o-mini / deepseek-v4-flash"},
            ],
            "secrets": [
                {"key": "api_key", "label": "API Key", "type": "password", "required": True},
            ],
        }

    def _resolve_client(self, account: Optional[str]) -> AiClient:
        if not account:
            account = self.default_account_id
        client = self.accounts.get(account or "")
        if not client:
            raise RuntimeError(f"Cuenta AI '{account}' no existe. Cuentas: {list(self.accounts.keys()) or '(ninguna)'}")
        return client

    def is_configured(self) -> bool:
        return bool(self.accounts) and any(c.is_configured() for c in self.accounts.values())

    def get_tools(self) -> List[Dict[str, Any]]:
        if not self.enabled or not self.is_configured():
            return []
        import copy
        account_ids = list(self.accounts.keys())
        tools = []
        for tool in copy.deepcopy(AI_TOOLS):
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
            raise RuntimeError("AI service no configurado (agrega una cuenta en el panel).")
        args = dict(arguments or {})
        account = args.pop("account", None)
        if tool_name == "ai_list_accounts":
            return self.get_account_summary()
        client = self._resolve_client(account)
        if tool_name == "ai_complete":
            return {"text": client.complete(
                args.get("prompt", ""),
                system=args.get("system"),
                max_tokens=int(args.get("max_tokens") or 1024),
            )}
        raise ValueError(f"Unknown AI tool: '{tool_name}'")

    async def test_connection(self) -> Dict[str, Any]:
        if self.default_account_id and self.default_account_id in self.accounts:
            return await self.accounts[self.default_account_id].test_connection()
        if self.accounts:
            return await next(iter(self.accounts.values())).test_connection()
        return {"ok": False, "message": "No hay cuentas de IA configuradas.", "details": {}}

    async def test_account(self, account: str) -> Dict[str, Any]:
        return await self._resolve_client(account).test_connection()
