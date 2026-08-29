import os
import logging
from typing import Dict, Any, List, Optional
from ..services import AVAILABLE_SERVICES
from ..services.base import BaseMcpService
from .db import get_service_config, save_service_config, log_activity

logger = logging.getLogger("mcp.registry")

class ServiceRegistry:
    """Central registry managing lifecycle of all encapsulated MCP services."""

    def __init__(self):
        self._services: Dict[str, BaseMcpService] = {}
        self._tool_map: Dict[str, str] = {}  # tool_name -> service_id

    def initialize(self):
        """Load and instantiate all available services from DB or environment."""
        self._services.clear()
        self._tool_map.clear()

        for s_id, s_class in AVAILABLE_SERVICES.items():
            db_data = get_service_config(s_id)
            
            if db_data:
                enabled = db_data["enabled"]
                config = db_data["config"]
                secrets = db_data["secrets"]
            else:
                # Seed defaults from environment variables if not present in DB
                enabled = True
                config = {}
                secrets = {}

                if s_id == "passbolt":
                    config = {
                        "base_url": os.environ.get("PASSBOLT_URL", ""),
                        "user_email": os.environ.get("PASSBOLT_USER_EMAIL", ""),
                        "fingerprint": os.environ.get("PASSBOLT_FINGERPRINT", ""),
                        "verify_ssl": True
                    }
                    secrets = {
                        "passphrase": os.environ.get("PASSBOLT_PASSPHRASE", ""),
                        "private_key": "",
                        "server_key": ""
                    }
                    # Save seeded configuration to DB
                    save_service_config(s_id, enabled, config, secrets)

            try:
                instance = s_class(config=config, secrets=secrets, enabled=enabled)
                self._services[s_id] = instance
                
                # Map tools
                if instance.enabled and instance.is_configured():
                    for tool in instance.get_tools():
                        t_name = tool["name"]
                        self._tool_map[t_name] = s_id
                        
                logger.info(f"Loaded service '{s_id}' (enabled={enabled}, configured={instance.is_configured()})")
            except Exception as e:
                logger.error(f"Failed to initialize service '{s_id}': {e}")

    def get_service(self, service_id: str) -> Optional[BaseMcpService]:
        return self._services.get(service_id)

    def list_services_status(self) -> List[Dict[str, Any]]:
        """Return status list for Admin Panel."""
        statuses = []
        for s_id, s_class in AVAILABLE_SERVICES.items():
            service = self._services.get(s_id)
            if service:
                status = service.get_status()
                # Include non-sensitive config details for UI
                status["config"] = service.config
                status["has_private_key"] = bool(service.secrets.get("private_key"))
                status["has_passphrase"] = bool(service.secrets.get("passphrase"))
                statuses.append(status)
            else:
                statuses.append({
                    "id": s_id,
                    "name": getattr(s_class, "name", s_id),
                    "description": getattr(s_class, "description", ""),
                    "enabled": False,
                    "configured": False,
                    "tools_count": 0,
                    "config": {},
                    "has_private_key": False,
                    "has_passphrase": False
                })
        return statuses

    def update_service(self, service_id: str, enabled: bool, config: Dict[str, Any], secrets: Dict[str, str]):
        """Persist changes to DB and re-instantiate service in memory."""
        # Merge with existing secrets so omitting a secret does not wipe it out
        existing = get_service_config(service_id)
        if existing and "secrets" in existing:
            merged_secrets = dict(existing["secrets"])
            for k, v in secrets.items():
                if v is not None and v != "":  # only overwrite if non-empty
                    merged_secrets[k] = v
            secrets = merged_secrets

        save_service_config(service_id, enabled, config, secrets)
        
        # Reload service in memory
        s_class = AVAILABLE_SERVICES.get(service_id)
        if s_class:
            instance = s_class(config=config, secrets=secrets, enabled=enabled)
            self._services[service_id] = instance
            
            # Rebuild tool map
            self._tool_map = {
                t["name"]: s_id
                for s_id, s in self._services.items()
                if s.enabled and s.is_configured()
                for t in s.get_tools()
            }
            log_activity(service_id, "update_config", "success", f"Updated config (enabled={enabled})")

    def get_tools_for_scope(self, scope: str = "unified") -> List[Dict[str, Any]]:
        """Return list of active tools for a specific subroute/scope."""
        tools = []
        if scope in ("unified", "mcp"):
            for s in self._services.values():
                if s.enabled and s.is_configured():
                    tools.extend(s.get_tools())
        else:
            service = self._services.get(scope)
            if service and service.enabled and service.is_configured():
                tools.extend(service.get_tools())
        return tools

    async def execute_tool(self, tool_name: str, arguments: Dict[str, Any], scope: str = "unified") -> Any:
        """Route tool execution to the appropriate service."""
        # If scope is specific (e.g. 'passbolt'), ensure tool belongs to that service
        if scope not in ("unified", "mcp"):
            service = self._services.get(scope)
            if not service:
                raise ValueError(f"Service '{scope}' is not registered.")
            if not service.enabled or not service.is_configured():
                raise RuntimeError(f"Service '{scope}' is currently inactive or not configured.")
            return await service.call_tool(tool_name, arguments)

        # Unified routing by tool map
        service_id = self._tool_map.get(tool_name)
        if not service_id:
            raise ValueError(f"Tool '{tool_name}' not found or its service is disabled.")
            
        service = self._services.get(service_id)
        if not service:
            raise ValueError(f"Underlying service '{service_id}' not found.")
            
        return await service.call_tool(tool_name, arguments)

# Global singleton
registry = ServiceRegistry()
