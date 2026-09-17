from typing import Dict, Any, List, Optional
from ..base import BaseMcpService
from .client import GoogleClient
from .tools import GOOGLE_TOOLS


class GoogleService(BaseMcpService):
    """Google workspace connector (Gmail + Calendar + Drive + Contacts + Sheets + Docs + Photos) supporting multiple accounts."""

    service_id: str = "google"
    name: str = "Google Workspace (Gmail + Calendar + Drive + Docs + Sheets + Contacts + Photos)"
    description: str = "Gmail, Calendar, Drive, Docs, Sheets, Contacts and Photos via OAuth2, with multiple accounts."
    supports_instances: bool = True

    def __init__(self, config, secrets, enabled=True, instances=None):
        super().__init__(config, secrets, enabled)
        self.accounts: Dict[str, GoogleClient] = {}
        self.default_account_id = ""
        self.reload_accounts(instances or [])

    @staticmethod
    def _build_client(cfg: Dict[str, Any], sec: Dict[str, str]) -> GoogleClient:
        return GoogleClient(
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
            "service_id": "google",
            "label": "Google (Gmail + Calendar + Drive + Docs + Sheets + Contacts + Photos)",
            "config": [
                {"key": "email", "label": "Cuenta de Google (email)", "type": "text", "required": True,
                 "placeholder": "tu@gmail.com"},
            ],
            "secrets": [
                {"key": "client_id", "label": "OAuth 2.0 Client ID", "type": "text", "required": True},
                {"key": "client_secret", "label": "OAuth 2.0 Client Secret", "type": "password", "required": True},
                {"key": "refresh_token", "label": "Refresh Token (OAuth) — o usa «Conectar con Google»", "type": "textarea", "required": False,
                 "placeholder": "1//0xxxx... (se rellena solo al conectar)"},
                {"key": "scope", "label": "Scopes (opcional)", "type": "text", "required": False,
                 "placeholder": "https://www.googleapis.com/auth/gmail.modify https://www.googleapis.com/auth/calendar https://www.googleapis.com/auth/drive ..."},
            ],
        }

    def _resolve_client(self, account: Optional[str]) -> GoogleClient:
        if not account:
            account = self.default_account_id
        client = self.accounts.get(account or "")
        if not client:
            raise RuntimeError(
                f"Cuenta Google '{account}' no existe. Cuentas disponibles: {list(self.accounts.keys()) or '(ninguna)'}"
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
        for tool in copy.deepcopy(GOOGLE_TOOLS):
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
            raise RuntimeError("Google service is not enabled or not fully configured.")

        args = dict(arguments or {})
        account = args.pop("account", None)

        if tool_name == "google_list_accounts":
            return self.get_account_summary()

        client = self._resolve_client(account)

        if tool_name == "google_gmail_list":
            return await client.gmail_list(query=args.get("query", ""), max_results=int(args.get("max_results") or 10))
        if tool_name == "google_gmail_get":
            return await client.gmail_get(args.get("message_id"), format=args.get("format") or "full", include_attachments=bool(args.get("include_attachments")))
        if tool_name == "google_gmail_send":
            return await client.gmail_send(
                to=args.get("to", ""), subject=args.get("subject", ""), body=args.get("body", ""),
                cc=args.get("cc", ""), bcc=args.get("bcc", ""), attachments=args.get("attachments"),
                from_addr=args.get("from", "") or "",
            )
        if tool_name == "google_gmail_drafts":
            return await client.gmail_drafts()
        if tool_name == "google_gmail_draft_create":
            return await client.gmail_draft_create(
                to=args.get("to", ""), subject=args.get("subject", ""), body=args.get("body", ""),
                attachments=args.get("attachments"), from_addr=args.get("from", "") or "",
            )
        if tool_name == "google_gmail_draft_send":
            return await client.gmail_draft_send(args.get("draft_id", ""))
        if tool_name == "google_gmail_draft_delete":
            return await client.gmail_draft_delete(args.get("draft_id", ""))
        if tool_name == "google_gmail_labels":
            return await client.gmail_labels()
        if tool_name == "google_gmail_sendas_list":
            return await client.gmail_sendas_list()
        if tool_name == "google_gmail_set_read":
            return await client.gmail_set_read(args.get("message_id", ""), bool(args.get("read", True)))
        if tool_name == "google_gmail_thread":
            return await client.gmail_thread(args.get("thread_id", ""))
        if tool_name == "google_gmail_transcribe_attachment":
            return await client.gmail_transcribe_attachment(args.get("message_id", ""), int(args.get("attachment_index") or 0), args.get("language", ""))
        if tool_name == "google_calendar_events":
            return await client.calendar_events(
                calendar_id=args.get("calendar_id") or "primary",
                time_min=args.get("time_min", ""), time_max=args.get("time_max", ""),
                max_results=int(args.get("max_results") or 20),
            )
        if tool_name == "google_calendar_create":
            return await client.calendar_create(
                summary=args.get("summary", ""), description=args.get("description", ""),
                start=args.get("start", ""), end=args.get("end", ""),
                attendees=args.get("attendees"), calendar_id=args.get("calendar_id") or "primary",
            )
        if tool_name == "google_calendar_delete":
            return await client.calendar_delete(args.get("event_id", ""), calendar_id=args.get("calendar_id") or "primary")
        if tool_name == "google_drive_list":
            return await client.drive_list(
                query=args.get("query", ""), page_size=int(args.get("page_size") or 20),
                order_by=args.get("order_by") or "modifiedTime desc",
            )
        if tool_name == "google_drive_get":
            return await client.drive_get(args.get("file_id", ""))
        if tool_name == "google_drive_download":
            return await client.drive_download(args.get("file_id", ""))
        if tool_name == "google_drive_create_folder":
            return await client.drive_create_folder(args.get("name", ""), parent_id=args.get("parent_id") or "")
        if tool_name == "google_drive_upload":
            return await client.drive_upload(
                args.get("name", ""), data_b64=args.get("data", "") or "",
                content_text=args.get("content_text", "") or "",
                mime_type=args.get("mime_type", "") or "", parent_id=args.get("parent_id") or "",
            )
        if tool_name == "google_drive_delete":
            return await client.drive_delete(args.get("file_id", ""))
        if tool_name == "google_contacts_search":
            return await client.contacts_search(args.get("query", ""), page_size=int(args.get("page_size") or 10))
        if tool_name == "google_contacts_list":
            return await client.contacts_list(page_size=int(args.get("page_size") or 20))
        if tool_name == "google_sheets_info":
            return await client.sheets_info(args.get("spreadsheet_id", ""))
        if tool_name == "google_sheets_read":
            return await client.sheets_read(args.get("spreadsheet_id", ""), args.get("range", ""))
        if tool_name == "google_sheets_append":
            return await client.sheets_append(args.get("spreadsheet_id", ""), args.get("range", ""), args.get("values") or [])
        if tool_name == "google_sheets_update":
            return await client.sheets_update(args.get("spreadsheet_id", ""), args.get("range", ""), args.get("values") or [])
        if tool_name == "google_docs_get":
            return await client.docs_get(args.get("document_id", ""))
        if tool_name == "google_docs_append":
            return await client.docs_append(args.get("document_id", ""), args.get("text", ""))
        if tool_name == "google_photos_list":
            return await client.photos_list(page_size=int(args.get("page_size") or 20))
        if tool_name == "google_photos_get":
            return await client.photos_get(args.get("media_item_id", ""))
        if tool_name == "google_photos_search":
            return await client.photos_search(
                year=int(args.get("year") or 0), month=int(args.get("month") or 0), day=int(args.get("day") or 0),
                content_category=args.get("content_category") or "", media_type=args.get("media_type") or "ALL_MEDIA",
                page_size=int(args.get("page_size") or 20),
            )
        if tool_name == "google_photos_albums":
            return await client.photos_albums(page_size=int(args.get("page_size") or 20))
        raise ValueError(f"Unknown Google tool: '{tool_name}'")

    async def test_connection(self) -> Dict[str, Any]:
        if self.default_account_id and self.default_account_id in self.accounts:
            return await self.accounts[self.default_account_id].test_connection()
        if self.accounts:
            return await next(iter(self.accounts.values())).test_connection()
        return {"ok": False, "message": "No hay cuentas Google configuradas.", "details": {}}

    async def test_account(self, account: str) -> Dict[str, Any]:
        return await self._resolve_client(account).test_connection()
