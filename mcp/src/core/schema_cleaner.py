"""
Universal MCP Schema Sanitizer.

Based on production learnings from bash-mcp / supergateway.
Transforms draft-07 and complex JSON Schemas into a clean, universally accepted
subset compatible with all strict LLM parsers (Google Gemini, OpenAI, Claude, Cursor, Open WebUI).
"""

from typing import Any, Dict, List, Optional

DROP_KEYWORDS = {
    "$schema", "$id", "$ref", "$defs", "$comment", "definitions",
    "additionalProperties", "unevaluatedProperties", "unevaluatedItems",
    "patternProperties", "propertyNames", "dependentSchemas",
    "dependentRequired", "dependencies", "contains", "prefixItems",
    "additionalItems", "if", "then", "else", "not", "const", "examples",
}

def sanitize_type_field(val: Any) -> str:
    """Ensure type is a simple string, collapsing lists like ['string', 'null']."""
    if isinstance(val, list):
        non_null = [t for t in val if t != "null"]
        return str(non_null[0]) if non_null else "string"
    if isinstance(val, str):
        return val
    return "string"

def pick_best_branch(branches: List[Any]) -> Dict[str, Any]:
    """Collapse anyOf/oneOf branches to the most expressive single branch."""
    real = [b for b in branches if isinstance(b, dict) and b.get("type") != "null"]
    if not real:
        return {"type": "string"}
    # Arrays win over objects, objects win over primitives
    for b in real:
        if b.get("type") == "array":
            return b
    for b in real:
        if b.get("type") == "object":
            return b
    return real[0]

def clean_schema_node(node: Any) -> Any:
    """Recursively strip forbidden keywords and sanitize a schema node."""
    if not isinstance(node, dict):
        return node

    out: Dict[str, Any] = {}

    # Handle anyOf / oneOf
    for union_key in ("anyOf", "oneOf"):
        if union_key in node and isinstance(node[union_key], list):
            chosen = pick_best_branch(node[union_key])
            for k, v in chosen.items():
                if k not in node:
                    out[k] = clean_schema_node(v)

    # Process all keys
    for k, v in node.items():
        if k in DROP_KEYWORDS or k in ("anyOf", "oneOf"):
            continue
        
        if k == "type":
            out["type"] = sanitize_type_field(v)
        elif k == "properties" and isinstance(v, dict):
            out["properties"] = {pk: clean_schema_node(pv) for pk, pv in v.items()}
        elif k == "items" and isinstance(v, dict):
            out["items"] = clean_schema_node(v)
        elif isinstance(v, dict):
            out[k] = clean_schema_node(v)
        elif isinstance(v, list):
            out[k] = [clean_schema_node(item) if isinstance(item, dict) else item for item in v]
        else:
            out[k] = v

    # Enforce type="object" and properties dict for root object schemas
    if "properties" in out and out.get("type") != "object":
        out["type"] = "object"

    return out

def sanitize_tool_definition(tool: Dict[str, Any], strip_output_schema: bool = True) -> Dict[str, Any]:
    """Sanitize a single MCP tool definition for total client compatibility."""
    clean_tool = {k: v for k, v in tool.items() if k not in DROP_KEYWORDS}
    
    # Ensure name and description
    clean_tool["name"] = str(tool.get("name", ""))
    clean_tool["description"] = str(tool.get("description", ""))

    # Clean inputSchema
    raw_input_schema = tool.get("inputSchema") or {}
    clean_input = clean_schema_node(raw_input_schema)
    
    # Strict Gemini / Claude rule: inputSchema must have type: object and properties dict
    if not isinstance(clean_input, dict):
        clean_input = {}
    clean_input["type"] = "object"
    if "properties" not in clean_input or not isinstance(clean_input["properties"], dict):
        clean_input["properties"] = {}

    clean_tool["inputSchema"] = clean_input

    # Strip outputSchema to save token context and avoid strict parser rejections
    if strip_output_schema and "outputSchema" in clean_tool:
        del clean_tool["outputSchema"]

    return clean_tool

def sanitize_tools_list_response(result: Dict[str, Any], strip_output_schema: bool = True) -> Dict[str, Any]:
    """Sanitizes the result object of a tools/list JSON-RPC response."""
    tools = result.get("tools", [])
    sanitized_tools = [
        sanitize_tool_definition(t, strip_output_schema=strip_output_schema)
        for t in tools if isinstance(t, dict)
    ]
    return {"tools": sanitized_tools}
