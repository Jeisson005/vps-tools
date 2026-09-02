_ACCOUNT = {
    "type": "string",
    "description": "Nombre/alias de la configuración de IA a usar. Omitir para usar la principal. "
                   "Ver cuentas con 'ai_list_accounts'.",
}

AI_TOOLS = [
    {
        "name": "ai_list_accounts",
        "description": "List the configured AI provider accounts (base_url/model), WITHOUT exposing API keys. Use this to discover the 'account' values you can pass to ai_complete.",
        "inputSchema": {"type": "object", "properties": {}},
    },
    {
        "name": "ai_complete",
        "description": "Run a single LLM completion with the selected AI provider. Use for specific AI tasks (summarize, classify, draft) WITHOUT asking the user for API keys.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "prompt": {"type": "string", "description": "The user prompt / task."},
                "system": {"type": "string", "description": "Optional system instruction."},
                "max_tokens": {"type": "integer", "description": "Max output tokens (default 1024)."},
                "account": _ACCOUNT,
            },
            "required": ["prompt"],
        },
    },
]
