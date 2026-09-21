from typing import Dict, Any, List, Optional
from ..base import BaseMcpService
from .client import MSGraphClient
from .tools import MICROSOFT_TOOLS


class MicrosoftService(BaseMcpService):
    """Microsoft 365 connector (Outlook mail + Calendar + Teams + OneDrive) supporting multiple accounts."""

    service_id: str = "microsoft"
    name: str = "Microsoft 365 (Outlook + Calendar + Teams + OneDrive)"
    description: str = "Read/send Outlook mail, manage Calendar, read/send Teams chats/channels and manage OneDrive files via Microsoft Graph, with multiple accounts."
    supports_instances: bool = True

    def __init__(self, config, secrets, enabled=True, instances=None):
        super().__init__(config, secrets, enabled)
        self.accounts: Dict[str, MSGraphClient] = {}
        self.default_account_id = ""
        self.reload_accounts(instances or [])

    @staticmethod
    def _build_client(cfg: Dict[str, Any], sec: Dict[str, str]) -> MSGraphClient:
        return MSGraphClient(
            tenant_id=sec.get("tenant_id", ""),
            client_id=sec.get("client_id", ""),
            client_secret=sec.get("client_secret", ""),
            refresh_token=sec.get("refresh_token", ""),
            scope=sec.get("scope", ""),
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
                "base_url": "",
                "user_email": "",
                "fingerprint": "",
                "has_private_key": False,
                "has_passphrase": bool(cli.client_secret),
                "has_secrets": cli.is_configured(),
            })
        return out

    def get_account_schema(self) -> Dict[str, Any]:
        return {
            "service_id": "microsoft",
            "label": "Microsoft 365 (Outlook + Calendar + Teams + OneDrive)",
            "config": [
                {"key": "email", "label": "Correo de la cuenta 365", "type": "text", "required": True,
                 "placeholder": "usuario@dominio.com"},
            ],
            "secrets": [
                {"key": "tenant_id", "label": "Tenant ID (o 'common' / 'consumers' / 'organizations')", "type": "text", "required": True,
                 "placeholder": "common — para cuentas personales usa 'consumers' o deja 'common'"},
                {"key": "client_id", "label": "Application (client) ID", "type": "text", "required": True},
                {"key": "client_secret", "label": "Client Secret", "type": "password", "required": True},
                {"key": "refresh_token", "label": "Refresh Token (OAuth) — o usa «Conectar con Microsoft»", "type": "textarea", "required": False,
                 "placeholder": "(se rellena solo al conectar)"},
                {"key": "scope", "label": "Scope (opcional, se rellena al conectar)", "type": "text", "required": False,
                 "placeholder": "Mail.ReadWrite Mail.Send Calendars.ReadWrite Files.ReadWrite.All User.Read offline_access"},
            ],
        }

    def _resolve_client(self, account: Optional[str]) -> MSGraphClient:
        if not account:
            account = self.default_account_id
        client = self.accounts.get(account or "")
        if not client:
            raise RuntimeError(
                f"Cuenta Microsoft 365 '{account}' no existe. Cuentas disponibles: {list(self.accounts.keys()) or '(ninguna)'}"
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
        for tool in copy.deepcopy(MICROSOFT_TOOLS):
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
            raise RuntimeError("Microsoft 365 service is not enabled or not fully configured.")

        args = dict(arguments or {})
        account = args.pop("account", None)

        if tool_name == "outlook_list_accounts":
            return self.get_account_summary()

        client = self._resolve_client(account)

        if tool_name == "outlook_mail_list":
            return await client.mail_list(filter=args.get("filter", ""), search=args.get("search", ""), top=int(args.get("top") or 10))
        if tool_name == "outlook_mail_get":
            return await client.mail_get(args.get("message_id"), include_attachments=bool(args.get("include_attachments")))
        if tool_name == "outlook_mail_send":
            return await client.mail_send(to=args.get("to", ""), subject=args.get("subject", ""), body=args.get("body", ""), cc=args.get("cc", ""), attachments=args.get("attachments"))
        if tool_name == "outlook_mail_set_read":
            return await client.mail_set_read(args.get("message_id", ""), bool(args.get("read", True)))
        if tool_name == "outlook_drafts":
            return await client.drafts()
        if tool_name == "outlook_draft_send":
            return await client.draft_send(args.get("message_id", ""))
        if tool_name == "outlook_folders":
            return await client.folders()
        if tool_name == "outlook_mail_transcribe_attachment":
            return await client.mail_transcribe_attachment(args.get("message_id", ""), int(args.get("attachment_index") or 0), args.get("language", ""))
        if tool_name == "outlook_calendar_events":
            return await client.calendar_events(top=int(args.get("top") or 20), calendar_id=args.get("calendar_id") or "me")
        if tool_name == "outlook_calendar_create":
            return await client.calendar_create(
                subject=args.get("subject", ""), start=args.get("start", ""), end=args.get("end", ""),
                body=args.get("body", ""), attendees=args.get("attendees"), calendar_id=args.get("calendar_id") or "me",
            )
        if tool_name == "outlook_calendar_delete":
            return await client.calendar_delete(
                event_id=args.get("event_id", ""), calendar_id=args.get("calendar_id") or "me",
            )
        if tool_name == "teams_list_joined":
            return await client.teams_joined()
        if tool_name == "teams_list_channels":
            return await client.teams_channels(team_id=args.get("team_id", ""))
        if tool_name == "teams_channel_messages":
            return await client.teams_channel_messages(
                team_id=args.get("team_id", ""), channel_id=args.get("channel_id", ""),
                top=int(args.get("top") or 20))
        if tool_name == "teams_channel_send":
            return await client.teams_channel_send(
                team_id=args.get("team_id", ""), channel_id=args.get("channel_id", ""),
                message=args.get("message", ""))
        if tool_name == "teams_list_chats":
            return await client.teams_chats(top=int(args.get("top") or 20))
        if tool_name == "teams_chat_messages":
            return await client.teams_chat_messages(
                chat_id=args.get("chat_id", ""), top=int(args.get("top") or 20))
        if tool_name == "teams_chat_send":
            return await client.teams_chat_send(
                chat_id=args.get("chat_id", ""), message=args.get("message", ""))
        if tool_name == "onedrive_list":
            return await client.onedrive_list(
                item_id=args.get("item_id", ""), top=int(args.get("top") or 50))
        if tool_name == "onedrive_get":
            return await client.onedrive_get(item_id=args.get("item_id", ""))
        if tool_name == "onedrive_download":
            return await client.onedrive_download(item_id=args.get("item_id", ""))
        if tool_name == "onedrive_upload":
            return await client.onedrive_upload(
                name=args.get("name", ""), content_text=args.get("content_text", ""),
                data=args.get("data", ""), folder_id=args.get("folder_id", ""),
                mime_type=args.get("mime_type") or "text/plain")
        raise ValueError(f"Unknown Microsoft tool: '{tool_name}'")

    async def test_connection(self) -> Dict[str, Any]:
        if self.default_account_id and self.default_account_id in self.accounts:
            return await self.accounts[self.default_account_id].test_connection()
        if self.accounts:
            return await next(iter(self.accounts.values())).test_connection()
        return {"ok": False, "message": "No hay cuentas de Microsoft 365 configuradas.", "details": {}}

    async def test_account(self, account: str) -> Dict[str, Any]:
        return await self._resolve_client(account).test_connection()
