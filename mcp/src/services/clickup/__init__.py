from typing import Dict, Any, List, Optional
from ..base import BaseMcpService
from .client import ClickUpClient
from .tools import CLICKUP_TOOLS


class ClickUpService(BaseMcpService):
    """ClickUp project management connector supporting multiple accounts.

    Each account stores a personal API token (``pk_...``) as secret and an
    optional default Workspace (team) id in config. The ``account`` tool
    argument selects which account is used; when omitted (or when only one
    account exists) the default account is used.
    """

    service_id: str = "clickup"
    name: str = "ClickUp"
    description: str = "Project management: workspaces, spaces, folders, lists and full task CRUD via personal API token, with multiple accounts."
    supports_instances: bool = True

    def __init__(self, config, secrets, enabled=True, instances=None):
        super().__init__(config, secrets, enabled)
        self.accounts: Dict[str, ClickUpClient] = {}
        self.default_account_id = ""
        self.reload_accounts(instances or [])

    @staticmethod
    def _build_client(cfg: Dict[str, Any], sec: Dict[str, str]) -> ClickUpClient:
        return ClickUpClient(
            api_token=sec.get("api_token", "") or sec.get("api_key", ""),
            default_team_id=cfg.get("team_id", "") or cfg.get("default_team_id", ""),
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
                "base_url": "https://api.clickup.com",
                "user_email": "",
                "fingerprint": "",
                "has_private_key": False,
                "has_passphrase": False,
                "has_secrets": cli.is_configured(),
            })
        return out

    def get_account_schema(self) -> Dict[str, Any]:
        return {
            "service_id": "clickup",
            "label": "ClickUp",
            "config": [
                {"key": "team_id", "label": "Workspace ID por defecto (opcional, se descubre con clickup_list_workspaces)",
                 "type": "text", "required": False, "placeholder": "12345678"},
            ],
            "secrets": [
                {"key": "api_token", "label": "Personal API Token (pk_... · Settings → Apps → API Token)",
                 "type": "password", "required": True, "placeholder": "pk_..."},
            ],
        }

    def _resolve_client(self, account: Optional[str]) -> ClickUpClient:
        if not account:
            account = self.default_account_id
        client = self.accounts.get(account or "")
        if not client:
            raise RuntimeError(
                f"Cuenta ClickUp '{account}' no existe. Cuentas disponibles: {list(self.accounts.keys()) or '(ninguna)'}"
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
        for tool in copy.deepcopy(CLICKUP_TOOLS):
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
            raise RuntimeError("ClickUp service is not enabled or not fully configured.")

        args = dict(arguments or {})
        account = args.pop("account", None)

        if tool_name == "clickup_list_accounts":
            return self.get_account_summary()

        client = self._resolve_client(account)

        if tool_name == "clickup_list_workspaces":
            return await client.list_workspaces()
        if tool_name == "clickup_list_spaces":
            return await client.list_spaces(team_id=args.get("team_id", ""), archived=bool(args.get("archived", False)))
        if tool_name == "clickup_get_space":
            return await client.get_space(space_id=args.get("space_id", ""))
        if tool_name == "clickup_create_space":
            return await client.create_space(
                team_id=args.get("team_id", ""), name=args.get("name", ""),
                color=args.get("color"), private=args.get("private"))
        if tool_name == "clickup_update_space":
            return await client.update_space(
                space_id=args.get("space_id", ""), name=args.get("name"), color=args.get("color"),
                private=args.get("private"), archived=args.get("archived"))
        if tool_name == "clickup_delete_space":
            return await client.delete_space(space_id=args.get("space_id", ""))
        if tool_name == "clickup_list_folders":
            return await client.list_folders(space_id=args.get("space_id", ""), archived=bool(args.get("archived", False)))
        if tool_name == "clickup_create_folder":
            return await client.create_folder(space_id=args.get("space_id", ""), name=args.get("name", ""))
        if tool_name == "clickup_list_lists":
            return await client.list_lists(
                folder_id=args.get("folder_id", ""), space_id=args.get("space_id", ""),
                archived=bool(args.get("archived", False)))
        if tool_name == "clickup_get_list":
            return await client.get_list(list_id=args.get("list_id", ""))
        if tool_name == "clickup_create_list":
            return await client.create_list(
                name=args.get("name", ""), folder_id=args.get("folder_id", ""),
                space_id=args.get("space_id", ""), content=args.get("content"))
        if tool_name == "clickup_update_list":
            return await client.update_list(
                list_id=args.get("list_id", ""), name=args.get("name"), content=args.get("content"),
                status=args.get("status"), archived=args.get("archived"))
        if tool_name == "clickup_delete_list":
            return await client.delete_list(list_id=args.get("list_id", ""))
        if tool_name == "clickup_list_tasks":
            return await client.list_tasks(
                list_id=args.get("list_id", ""), archived=bool(args.get("archived", False)),
                page=int(args.get("page") or 0), include_closed=bool(args.get("include_closed", True)),
                subtasks=bool(args.get("subtasks", True)))
        if tool_name == "clickup_get_task":
            return await client.get_task(task_id=args.get("task_id", ""))
        if tool_name == "clickup_create_task":
            passthrough = {k: args[k] for k in (
                "description", "assignees", "tags", "status", "priority", "due_date",
                "due_date_time", "time_estimate", "parent") if args.get(k) is not None}
            return await client.create_task(list_id=args.get("list_id", ""), name=args.get("name", ""), **passthrough)
        if tool_name == "clickup_update_task":
            passthrough = {k: args[k] for k in (
                "name", "description", "status", "priority", "due_date",
                "time_estimate", "parent", "archived", "assignees") if args.get(k) is not None}
            return await client.update_task(task_id=args.get("task_id", ""), **passthrough)
        if tool_name == "clickup_delete_task":
            return await client.delete_task(task_id=args.get("task_id", ""))
        if tool_name == "clickup_list_task_comments":
            return await client.list_task_comments(task_id=args.get("task_id", ""))
        if tool_name == "clickup_create_task_comment":
            return await client.create_task_comment(
                task_id=args.get("task_id", ""), comment_text=args.get("comment_text", ""),
                notify_all=bool(args.get("notify_all", True)))
        raise ValueError(f"Unknown ClickUp tool: '{tool_name}'")

    async def test_connection(self) -> Dict[str, Any]:
        if self.default_account_id and self.default_account_id in self.accounts:
            return await self.accounts[self.default_account_id].test_connection()
        if self.accounts:
            return await next(iter(self.accounts.values())).test_connection()
        return {"ok": False, "message": "No hay cuentas ClickUp configuradas.", "details": {}}

    async def test_account(self, account: str) -> Dict[str, Any]:
        return await self._resolve_client(account).test_connection()
