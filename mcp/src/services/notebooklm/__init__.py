from typing import Dict, Any, List, Optional
from ..base import BaseMcpService
from .client import NotebookLMClient, _profile_for
from .tools import NOTEBOOKLM_TOOLS


class NotebookLMService(BaseMcpService):
    """Gemini Notebook (NotebookLM) grounded-QA connector, multi-account.

    Each panel account stores the full ``storage_state.json`` (Google session
    cookies from ``notebooklm-py``) as the ``auth_json`` secret. The service
    shells out to the ``notebooklm`` CLI with an isolated ``NOTEBOOKLM_HOME``
    + ``--profile <account>`` per call, so accounts never share cookies.

    The ``account`` tool argument selects which account is used; when omitted
    (or when only one account exists) the default account is used.
    """

    service_id: str = "notebooklm"
    name: str = "NotebookLM (Gemini Notebook)"
    description: str = "Grounded Q&A over your NotebookLM sources via notebooklm-py (unofficial API): notebooks, sources, cited answers. Multi-account, configured 100% from the panel."
    supports_instances: bool = True

    def __init__(self, config, secrets, enabled=True, instances=None):
        super().__init__(config, secrets, enabled)
        self.accounts: Dict[str, NotebookLMClient] = {}
        self.default_account_id = ""
        self.reload_accounts(instances or [])

    @staticmethod
    def _build_client(cfg: Dict[str, Any], sec: Dict[str, str], instance_id: str = "default") -> NotebookLMClient:
        return NotebookLMClient(
            auth_json=sec.get("auth_json", "") or sec.get("storage_state", ""),
            email=cfg.get("email", "") or cfg.get("user_email", ""),
            language=cfg.get("language", "") or cfg.get("hl", ""),
            profile=_profile_for(instance_id),
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
            self.accounts[iid] = self._build_client(inst.get("config", {}), inst.get("secrets", {}), iid)
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
                "base_url": "https://notebooklm.google.com",
                "user_email": cli.email,
                "fingerprint": "",
                "has_private_key": False,
                "has_passphrase": False,
                "has_secrets": cli.is_configured(),
            })
        return out

    def get_account_schema(self) -> Dict[str, Any]:
        return {
            "service_id": "notebooklm",
            "label": "NotebookLM (Gemini Notebook)",
            "config": [
                {"key": "email", "label": "Cuenta de Google (email, solo etiqueta + routing)", "type": "text", "required": True,
                 "placeholder": "tu@gmail.com"},
                {"key": "language", "label": "Idioma de salida (hl, opcional: en, es, ...)", "type": "text", "required": False,
                 "placeholder": "es"},
            ],
            "secrets": [
                {"key": "auth_json", "label": "Auth JSON (contenido de storage_state.json de notebooklm-py —Cookies de sesión Google)",
                 "type": "textarea", "required": True,
                 "placeholder": '{"cookies": [{"name": "SID", ...}], ...} — En tu PC: notebooklm login y copia ~/.notebooklm/profiles/default/storage_state.json'},
            ],
        }

    def _resolve_client(self, account: Optional[str]) -> NotebookLMClient:
        if not account:
            account = self.default_account_id
        client = self.accounts.get(account or "")
        if not client:
            raise RuntimeError(
                f"Cuenta NotebookLM '{account}' no existe. Cuentas disponibles: {list(self.accounts.keys()) or '(ninguna)'}"
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
        for tool in copy.deepcopy(NOTEBOOKLM_TOOLS):
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
            raise RuntimeError("NotebookLM service is not enabled or not fully configured (add an account in the panel).")

        args = dict(arguments or {})
        account = args.pop("account", None)

        if tool_name == "notebooklm_list_accounts":
            return self.get_account_summary()

        client = self._resolve_client(account)

        if tool_name == "notebooklm_auth_check":
            return await client.test_connection()
        if tool_name == "notebooklm_list_notebooks":
            return await client.list_notebooks(limit=int(args.get("limit") or 50))
        if tool_name == "notebooklm_create_notebook":
            return await client.create_notebook(title=args.get("title", ""))
        if tool_name == "notebooklm_rename_notebook":
            return await client.rename_notebook(
                notebook_id=args.get("notebook_id", ""), new_title=args.get("new_title", ""))
        if tool_name == "notebooklm_delete_notebook":
            return await client.delete_notebook(notebook_id=args.get("notebook_id", ""))
        if tool_name == "notebooklm_describe_notebook":
            return await client.describe_notebook(notebook_id=args.get("notebook_id", ""))
        if tool_name == "notebooklm_list_sources":
            return await client.list_sources(
                notebook_id=args.get("notebook_id", ""),
                limit=int(args.get("limit") or 50),
                status=args.get("status", "") or "")
        if tool_name == "notebooklm_get_source":
            return await client.get_source(
                notebook_id=args.get("notebook_id", ""), source_id=args.get("source_id", ""))
        if tool_name == "notebooklm_fulltext_source":
            return await client.fulltext_source(
                notebook_id=args.get("notebook_id", ""), source_id=args.get("source_id", ""),
                max_chars=int(args.get("max_chars") or 15000))
        if tool_name == "notebooklm_search_sources":
            return await client.search_sources(
                notebook_id=args.get("notebook_id", ""), query=args.get("query", ""),
                limit=int(args.get("limit") or 5))
        if tool_name == "notebooklm_add_source_url":
            return await client.add_source_url(
                notebook_id=args.get("notebook_id", ""), url=args.get("url", ""),
                title=args.get("title", "") or "", wait=bool(args.get("wait", True)))
        if tool_name == "notebooklm_add_source_text":
            return await client.add_source_text(
                notebook_id=args.get("notebook_id", ""), text=args.get("text", ""),
                title=args.get("title", ""))
        if tool_name == "notebooklm_ask":
            return await client.ask(
                notebook_id=args.get("notebook_id", ""), question=args.get("question", ""),
                source_ids=args.get("source_ids"), conversation_id=args.get("conversation_id", "") or "")
        if tool_name == "notebooklm_history":
            return await client.history(
                notebook_id=args.get("notebook_id", ""), limit=int(args.get("limit") or 10))
        if tool_name == "notebooklm_suggest_prompts":
            return await client.suggest_prompts(notebook_id=args.get("notebook_id", ""))
        raise ValueError(f"Unknown NotebookLM tool: '{tool_name}'")

    async def test_connection(self) -> Dict[str, Any]:
        if self.default_account_id and self.default_account_id in self.accounts:
            return await self.accounts[self.default_account_id].test_connection()
        if self.accounts:
            return await next(iter(self.accounts.values())).test_connection()
        return {"ok": False, "message": "No hay cuentas NotebookLM configuradas.", "details": {}}

    async def test_account(self, account: str) -> Dict[str, Any]:
        return await self._resolve_client(account).test_connection()
