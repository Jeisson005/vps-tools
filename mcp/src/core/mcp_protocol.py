import json
import uuid
import logging
from typing import Dict, Any, Optional, Tuple
from .registry import registry
from .schema_cleaner import sanitize_tools_list_response
from .db import log_activity

logger = logging.getLogger("mcp.protocol")

PROTOCOL_VERSION = "2024-11-05"

class McpProtocolHandler:
    """Handles JSON-RPC 2.0 requests following Model Context Protocol standards."""

    def __init__(self, scope: str = "unified"):
        self.scope = scope

    async def handle_request(self, payload: Dict[str, Any], session_id: Optional[str] = None) -> Tuple[Optional[Dict[str, Any]], str]:
        """
        Process a single JSON-RPC message.
        Returns (response_dict, effective_session_id).
        """
        sid = session_id or str(uuid.uuid4())
        
        req_id = payload.get("id")
        method = payload.get("method")
        params = payload.get("params") or {}

        # Handle notifications (no response required if no id)
        if method == "notifications/initialized":
            logger.debug(f"[{self.scope}] Client initialized notification on session {sid}")
            return None, sid

        if not method:
            return {
                "jsonrpc": "2.0",
                "id": req_id,
                "error": {"code": -32600, "message": "Invalid Request: missing method"}
            }, sid

        try:
            if method == "initialize":
                client_version = params.get("protocolVersion", PROTOCOL_VERSION)
                res = {
                    "protocolVersion": PROTOCOL_VERSION,
                    "capabilities": {
                        "tools": {"listChanged": False}
                    },
                    "serverInfo": {
                        "name": f"vps-mcp-gateway-{self.scope}",
                        "version": "1.0.0"
                    }
                }
                return {"jsonrpc": "2.0", "id": req_id, "result": res}, sid

            elif method == "ping":
                return {"jsonrpc": "2.0", "id": req_id, "result": {}}, sid

            elif method == "tools/list":
                raw_tools = registry.get_tools_for_scope(self.scope)
                # Universal schema sanitization (learnings from bash-mcp)
                sanitized = sanitize_tools_list_response({"tools": raw_tools}, strip_output_schema=True)
                return {"jsonrpc": "2.0", "id": req_id, "result": sanitized}, sid

            elif method == "tools/call":
                tool_name = params.get("name")
                arguments = params.get("arguments") or {}

                if not tool_name:
                    return {
                        "jsonrpc": "2.0",
                        "id": req_id,
                        "error": {"code": -32602, "message": "Missing 'name' in tools/call"}
                    }, sid

                logger.info(f"[{self.scope}] Executing tool '{tool_name}' with args keys: {list(arguments.keys())}")
                try:
                    call_result = await registry.execute_tool(tool_name, arguments, scope=self.scope)
                    
                    # Convert response to MCP content block
                    if isinstance(call_result, (dict, list)):
                        text_content = json.dumps(call_result, indent=2, ensure_ascii=False)
                    else:
                        text_content = str(call_result)

                    mcp_result = {
                        "content": [
                            {
                                "type": "text",
                                "text": text_content
                            }
                        ],
                        "isError": False
                    }
                    log_activity(self.scope, f"tool:{tool_name}", "success")
                    return {"jsonrpc": "2.0", "id": req_id, "result": mcp_result}, sid
                    
                except Exception as tool_err:
                    logger.warning(f"[{self.scope}] Tool execution failed: {tool_err}")
                    log_activity(self.scope, f"tool:{tool_name}", "error", str(tool_err))
                    mcp_error_result = {
                        "content": [
                            {
                                "type": "text",
                                "text": f"Error executing tool '{tool_name}': {str(tool_err)}"
                            }
                        ],
                        "isError": True
                    }
                    return {"jsonrpc": "2.0", "id": req_id, "result": mcp_error_result}, sid

            else:
                return {
                    "jsonrpc": "2.0",
                    "id": req_id,
                    "error": {"code": -32601, "message": f"Method '{method}' not found"}
                }, sid

        except Exception as e:
            logger.exception(f"Unexpected error handling MCP method {method}: {e}")
            return {
                "jsonrpc": "2.0",
                "id": req_id,
                "error": {"code": -32603, "message": f"Internal error: {str(e)}"}
            }, sid
