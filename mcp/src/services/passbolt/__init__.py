from typing import Dict, Any, List, Optional
from ..base import BaseMcpService
from .client import PassboltClient
from .tools import PASSBOLT_TOOLS


class PassboltService(BaseMcpService):
    """Passbolt gateway that can manage one or more vault accounts.

    Each account is a :class:`PassboltClient` with its own Passbolt server,
    GPG key and 2FA. The ``account`` tool argument selects which one is used;
    when omitted (or when only one account exists) the default account is used.
    """

    service_id: str = "passbolt"
    name: str = "Passbolt Password Manager"
    description: str = "Team password manager with OpenPGP client-side encryption, TOTP 2FA, and full CRUD support."
    supports_instances: bool = True

    def __init__(
        self,
        config: Dict[str, Any],
        secrets: Dict[str, str],
        enabled: bool = True,
        instances: Optional[List[Dict[str, Any]]] = None,
    ):
        super().__init__(config, secrets, enabled)
        self.accounts: Dict[str, PassboltClient] = {}
        self.default_account_id: str = ""
        self.reload_accounts(instances or [])

    # -- account lifecycle ---------------------------------------------------

    @staticmethod
    def _build_client(cfg: Dict[str, Any], sec: Dict[str, str]) -> PassboltClient:
        return PassboltClient(
            base_url=cfg.get("base_url") or "",
            private_key_armored=sec.get("private_key") or "",
            passphrase=sec.get("passphrase") or "",
            server_key_armored=sec.get("server_key") or "",
            user_email=cfg.get("user_email") or "",
            fingerprint=cfg.get("fingerprint") or "",
            verify_ssl=cfg.get("verify_ssl", True),
        )

    def reload_accounts(self, instances: List[Dict[str, Any]]):
        """Rebuild the in-memory account clients from a list of instance dicts."""
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
        """Non-sensitive summary for the Admin Panel."""
        summary = []
        for iid, cli in self.accounts.items():
            summary.append({
                "instance_id": iid,
                "name": "",
                "enabled": True,
                "is_default": iid == self.default_account_id,
                "configured": cli.is_configured(),
                "base_url": cli.base_url,
                "user_email": cli.user_email,
                "fingerprint": cli.fingerprint,
                "has_private_key": bool(cli.private_key_armored),
                "has_passphrase": bool(cli.passphrase),
            })
        return summary

    def get_account_schema(self) -> Dict[str, Any]:
        return {
            "service_id": "passbolt",
            "label": "Passbolt",
            "config": [
                {"key": "base_url", "label": "URL del servidor Passbolt", "type": "url", "required": True,
                 "placeholder": "https://passbolt.yourdomain.com"},
                {"key": "user_email", "label": "Correo de usuario Passbolt", "type": "email", "required": True,
                 "placeholder": "user@domain.com"},
            ],
            "secrets": [
                {"key": "private_key", "label": "Clave privada GPG (pégala aquí)", "type": "textarea", "required": True,
                 "placeholder": "-----BEGIN PGP PRIVATE KEY BLOCK----- ..."},
                {"key": "passphrase", "label": "Frase de paso (passphrase)", "type": "password", "required": False},
            ],
        }

    def _resolve_client(self, account: Optional[str]) -> PassboltClient:
        if not account:
            account = self.default_account_id
        client = self.accounts.get(account or "")
        if not client:
            raise RuntimeError(
                f"Cuenta Passbolt '{account}' no existe. Cuentas disponibles: {list(self.accounts.keys()) or '(ninguna)'}"
            )
        return client

    # -- BaseMcpService ------------------------------------------------------

    def is_configured(self) -> bool:
        return bool(self.accounts) and any(c.is_configured() for c in self.accounts.values())

    def get_tools(self) -> List[Dict[str, Any]]:
        if not self.enabled or not self.is_configured():
            return []
        # Enrich the account selector with the actual configured accounts so
        # agents can discover and pick a specific vault.
        import copy
        account_ids = list(self.accounts.keys())
        tools = []
        for tool in copy.deepcopy(PASSBOLT_TOOLS):
            props = tool.get("inputSchema", {}).get("properties", {})
            account_prop = props.get("account")
            if account_prop and account_ids:
                account_prop["enum"] = account_ids
                if self.default_account_id:
                    account_prop.setdefault("default", self.default_account_id)
            tools.append(tool)
        return tools

    async def call_tool(self, tool_name: str, arguments: Dict[str, Any]) -> Any:
        if not self.enabled or not self.is_configured():
            raise RuntimeError("Passbolt service is not enabled or not fully configured.")

        args = dict(arguments or {})
        account = args.pop("account", None)

        if tool_name == "passbolt_list_accounts":
            return self.get_account_summary()

        client = self._resolve_client(account)

        if tool_name == "passbolt_search_resources":
            query = args.get("query", "")
            folder_id = args.get("folder_id")
            limit = int(args.get("limit") or 20)
            return await client.search_resources(query=query, folder_id=folder_id, limit=limit)

        elif tool_name == "passbolt_get_secret":
            resource_id = args.get("resource_id")
            if not resource_id:
                raise ValueError("Argument 'resource_id' is required for passbolt_get_secret.")
            return await client.get_secret(resource_id=resource_id)

        elif tool_name == "passbolt_create_resource":
            name = args.get("name")
            password = args.get("password")
            if not name or not password:
                raise ValueError("Arguments 'name' and 'password' are required for passbolt_create_resource.")
            return await client.create_resource(
                name=name,
                password=password,
                username=args.get("username", ""),
                uri=args.get("uri", ""),
                description=args.get("description", ""),
                folder_id=args.get("folder_id"),
                totp_secret=args.get("totp_secret"),
                custom_fields=args.get("custom_fields"),
            )

        elif tool_name == "passbolt_update_resource":
            resource_id = args.get("resource_id")
            if not resource_id:
                raise ValueError("Argument 'resource_id' is required for passbolt_update_resource.")
            return await client.update_resource(
                resource_id=resource_id,
                name=args.get("name"),
                password=args.get("password"),
                username=args.get("username"),
                uri=args.get("uri"),
                description=args.get("description"),
                folder_id=args.get("folder_id"),
                totp_secret=args.get("totp_secret"),
                custom_fields=args.get("custom_fields"),
            )

        elif tool_name == "passbolt_delete_resource":
            resource_id = args.get("resource_id")
            if not resource_id:
                raise ValueError("Argument 'resource_id' is required for passbolt_delete_resource.")
            return await client.delete_resource(resource_id=resource_id)

        elif tool_name == "passbolt_list_folders":
            parent_id = args.get("parent_id")
            return await client.list_folders(parent_id=parent_id)

        elif tool_name == "passbolt_create_folder":
            name = args.get("name")
            if not name:
                raise ValueError("Argument 'name' is required for passbolt_create_folder.")
            return await client.create_folder(name=name, parent_id=args.get("parent_id"))

        else:
            raise ValueError(f"Unknown Passbolt tool: '{tool_name}'")

    async def test_connection(self) -> Dict[str, Any]:
        if self.default_account_id and self.default_account_id in self.accounts:
            return await self.accounts[self.default_account_id].test_connection()
        if self.accounts:
            cli = next(iter(self.accounts.values()))
            return await cli.test_connection()
        return {
            "ok": False,
            "message": "No hay cuentas Passbolt configuradas.",
            "details": {},
        }

    async def test_account(self, account: str) -> Dict[str, Any]:
        client = self._resolve_client(account)
        return await client.test_connection()
