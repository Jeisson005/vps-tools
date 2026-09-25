from typing import Dict, Any, List, Optional
from ..base import BaseMcpService
from .client import TrelloClient
from .tools import TRELLO_TOOLS


class TrelloService(BaseMcpService):
    """Trello project management connector supporting multiple accounts.

    Each account stores an API key + user token pair as secrets
    (key from a Power-Up at trello.com/power-ups/admin, token via
    ``/1/authorize?expiration=never&scope=read,write``). The ``account`` tool
    argument selects which account is used; when omitted (or when only one
    account exists) the default account is used.
    """

    service_id: str = "trello"
    name: str = "Trello"
    description: str = "Project management: boards, lists, cards, comments and search via API key + token, with multiple accounts."
    supports_instances: bool = True

    def __init__(self, config, secrets, enabled=True, instances=None):
        super().__init__(config, secrets, enabled)
        self.accounts: Dict[str, TrelloClient] = {}
        self.default_account_id = ""
        self.reload_accounts(instances or [])

    @staticmethod
    def _build_client(cfg: Dict[str, Any], sec: Dict[str, str]) -> TrelloClient:
        return TrelloClient(
            api_key=sec.get("api_key", "") or cfg.get("api_key", ""),
            api_token=sec.get("api_token", "") or sec.get("token", "") or cfg.get("api_token", ""),
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
                "base_url": "https://api.trello.com",
                "user_email": "",
                "fingerprint": "",
                "has_private_key": False,
                "has_passphrase": False,
                "has_secrets": cli.is_configured(),
            })
        return out

    def get_account_schema(self) -> Dict[str, Any]:
        return {
            "service_id": "trello",
            "label": "Trello",
            "config": [],
            "secrets": [
                {"key": "api_key", "label": "API Key (Power-Up → trello.com/power-ups/admin → API Key)",
                 "type": "password", "required": True, "placeholder": "tu api key"},
                {"key": "api_token", "label": "Token (…/1/authorize?expiration=never&scope=read,write&key=TU_KEY)",
                 "type": "password", "required": True, "placeholder": "tu token"},
            ],
        }

    def _resolve_client(self, account: Optional[str]) -> TrelloClient:
        if not account:
            account = self.default_account_id
        client = self.accounts.get(account or "")
        if not client:
            raise RuntimeError(
                f"Cuenta Trello '{account}' no existe. Cuentas disponibles: {list(self.accounts.keys()) or '(ninguna)'}"
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
        for tool in copy.deepcopy(TRELLO_TOOLS):
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
            raise RuntimeError("Trello service is not enabled or not fully configured.")

        args = dict(arguments or {})
        account = args.pop("account", None)

        if tool_name == "trello_list_accounts":
            return self.get_account_summary()

        client = self._resolve_client(account)

        if tool_name == "trello_get_user":
            return await client.get_user()
        if tool_name == "trello_list_boards":
            return await client.list_boards(filter=args.get("filter", "open"))
        if tool_name == "trello_get_board":
            return await client.get_board(board_id=args.get("board_id", ""))
        if tool_name == "trello_create_board":
            return await client.create_board(name=args.get("name", ""), desc=args.get("desc", ""))
        if tool_name == "trello_list_lists":
            return await client.list_lists(
                board_id=args.get("board_id", ""), filter=args.get("filter", "open"))
        if tool_name == "trello_create_list":
            return await client.create_list(
                board_id=args.get("board_id", ""), name=args.get("name", ""),
                pos=args.get("pos", "bottom"))
        if tool_name == "trello_update_list":
            return await client.update_list(
                list_id=args.get("list_id", ""), name=args.get("name"),
                closed=args.get("closed"))
        if tool_name == "trello_list_cards":
            return await client.list_cards(
                board_id=args.get("board_id", ""), list_id=args.get("list_id", ""),
                filter=args.get("filter", "open"))
        if tool_name == "trello_get_card":
            return await client.get_card(card_id=args.get("card_id", ""))
        if tool_name == "trello_create_card":
            return await client.create_card(
                list_id=args.get("list_id", ""), name=args.get("name", ""),
                desc=args.get("desc", ""), due=args.get("due", ""),
                pos=args.get("pos", "bottom"), member_ids=args.get("member_ids"))
        if tool_name == "trello_update_card":
            passthrough = {k: args[k] for k in (
                "name", "desc", "due", "dueComplete", "closed",
                "idList", "pos", "member_ids", "idMembers") if args.get(k) is not None}
            return await client.update_card(card_id=args.get("card_id", ""), **passthrough)
        if tool_name == "trello_archive_card":
            return await client.archive_card(card_id=args.get("card_id", ""))
        if tool_name == "trello_list_card_comments":
            return await client.list_card_comments(
                card_id=args.get("card_id", ""),
                limit=int(args.get("limit") or 50))
        if tool_name == "trello_create_card_comment":
            return await client.create_card_comment(
                card_id=args.get("card_id", ""), text=args.get("text", ""))
        if tool_name == "trello_list_board_members":
            return await client.list_board_members(board_id=args.get("board_id", ""))
        if tool_name == "trello_search":
            return await client.search(
                query=args.get("query", ""), model_types=args.get("model_types", "cards,boards"),
                cards_limit=int(args.get("cards_limit") or 20),
                boards_limit=int(args.get("boards_limit") or 10))
        raise ValueError(f"Unknown Trello tool: '{tool_name}'")

    async def test_connection(self) -> Dict[str, Any]:
        if self.default_account_id and self.default_account_id in self.accounts:
            return await self.accounts[self.default_account_id].test_connection()
        if self.accounts:
            return await next(iter(self.accounts.values())).test_connection()
        return {"ok": False, "message": "No hay cuentas Trello configuradas.", "details": {}}

    async def test_account(self, account: str) -> Dict[str, Any]:
        return await self._resolve_client(account).test_connection()
