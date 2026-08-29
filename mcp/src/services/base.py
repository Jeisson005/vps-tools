from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional

class BaseMcpService(ABC):
    """Abstract base class for all encapsulated MCP services."""
    
    service_id: str = "base"
    name: str = "Base Service"
    description: str = "Base MCP Service"
    
    def __init__(self, config: Dict[str, Any], secrets: Dict[str, str], enabled: bool = True):
        self.config = config or {}
        self.secrets = secrets or {}
        self.enabled = enabled

    @abstractmethod
    def is_configured(self) -> bool:
        """Check if service has sufficient credentials/configuration to operate."""
        pass

    @abstractmethod
    def get_tools(self) -> List[Dict[str, Any]]:
        """Return list of MCP tool definitions provided by this service."""
        pass

    @abstractmethod
    async def call_tool(self, tool_name: str, arguments: Dict[str, Any]) -> Any:
        """Execute a tool provided by this service."""
        pass

    @abstractmethod
    async def test_connection(self) -> Dict[str, Any]:
        """Perform a live diagnostics test and return status."""
        pass

    def get_status(self) -> Dict[str, Any]:
        """Return operational status summary for admin dashboard."""
        return {
            "id": self.service_id,
            "name": self.name,
            "description": self.description,
            "enabled": self.enabled,
            "configured": self.is_configured(),
            "tools_count": len(self.get_tools()) if self.is_configured() else 0,
        }
