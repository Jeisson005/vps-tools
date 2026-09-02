from typing import Dict, Any, List
from ..base import BaseMcpService
from ...core import ai as ai_core

AI_TOOLS = [
    {
        "name": "ai_complete",
        "description": "Run a single LLM completion using the gateway's configured AI provider. Use this for specific AI tasks (summarize, classify, draft) WITHOUT asking the user for API keys.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "prompt": {"type": "string", "description": "The user prompt / task."},
                "system": {"type": "string", "description": "Optional system instruction."},
                "max_tokens": {"type": "integer", "description": "Max output tokens (default 1024)."},
            },
            "required": ["prompt"],
        },
    },
]


class AiService(BaseMcpService):
    """Transparent LLM helper (uses MCP_AI_* env; no user key prompt)."""

    service_id: str = "ai"
    name: str = "AI (LLM helper)"
    description: str = "Run a single LLM completion with the gateway's configured AI provider."

    def is_configured(self) -> bool:
        return ai_core.is_configured()

    def get_tools(self) -> List[Dict[str, Any]]:
        if not self.enabled or not self.is_configured():
            return []
        return AI_TOOLS

    async def call_tool(self, tool_name: str, arguments: Dict[str, Any]) -> Any:
        if not self.enabled or not self.is_configured():
            raise RuntimeError("AI service no configurado (falta MCP_AI_API_KEY).")
        if tool_name == "ai_complete":
            return {"text": ai_core.complete(
                arguments.get("prompt", ""),
                system=arguments.get("system"),
                max_tokens=int(arguments.get("max_tokens") or 1024),
            )}
        raise ValueError(f"Unknown AI tool: '{tool_name}'")

    async def test_connection(self) -> Dict[str, Any]:
        if not self.is_configured():
            return {"ok": False, "message": "AI no configurado (falta MCP_AI_API_KEY).", "details": {}}
        try:
            sample = ai_core.complete("Responde solo: ok", max_tokens=5)
            return {"ok": True, "message": "AI provider responde.", "details": {"sample": sample[:40]}}
        except Exception as e:
            return {"ok": False, "message": f"Error de conexión con AI: {e}", "details": {"error": str(e)}}
