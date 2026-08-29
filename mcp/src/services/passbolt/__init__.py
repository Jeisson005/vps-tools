from typing import Dict, Any, List, Optional
from ..base import BaseMcpService
from .client import PassboltClient
from .tools import PASSBOLT_TOOLS

class PassboltService(BaseMcpService):
    service_id: str = "passbolt"
    name: str = "Passbolt Password Manager"
    description: str = "Team password manager with OpenPGP client-side encryption and GPG challenge-response"

    def __init__(self, config: Dict[str, Any], secrets: Dict[str, str], enabled: bool = True):
        super().__init__(config, secrets, enabled)
        
        base_url = config.get("base_url") or ""
        user_email = config.get("user_email") or ""
        fingerprint = config.get("fingerprint") or ""
        verify_ssl = config.get("verify_ssl", True)
        
        private_key = secrets.get("private_key") or ""
        passphrase = secrets.get("passphrase") or ""
        server_key = secrets.get("server_key") or ""

        self.client = PassboltClient(
            base_url=base_url,
            private_key_armored=private_key,
            passphrase=passphrase,
            server_key_armored=server_key,
            user_email=user_email,
            fingerprint=fingerprint,
            verify_ssl=verify_ssl
        )

    def is_configured(self) -> bool:
        return self.client.is_configured()

    def get_tools(self) -> List[Dict[str, Any]]:
        if not self.enabled or not self.is_configured():
            return []
        return PASSBOLT_TOOLS

    async def call_tool(self, tool_name: str, arguments: Dict[str, Any]) -> Any:
        if not self.enabled or not self.is_configured():
            raise RuntimeError("Passbolt service is not enabled or not fully configured.")

        if tool_name == "passbolt_search_resources":
            query = arguments.get("query", "")
            folder_id = arguments.get("folder_id")
            limit = int(arguments.get("limit") or 20)
            return await self.client.search_resources(query=query, folder_id=folder_id, limit=limit)

        elif tool_name == "passbolt_get_secret":
            resource_id = arguments.get("resource_id")
            if not resource_id:
                raise ValueError("Argument 'resource_id' is required for passbolt_get_secret.")
            return await self.client.get_secret(resource_id=resource_id)

        elif tool_name == "passbolt_list_folders":
            parent_id = arguments.get("parent_id")
            return await self.client.list_folders(parent_id=parent_id)

        else:
            raise ValueError(f"Unknown Passbolt tool: '{tool_name}'")

    async def test_connection(self) -> Dict[str, Any]:
        return await self.client.test_connection()
