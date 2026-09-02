_ACCOUNT = {
    "type": "string",
    "description": "Nombre/alias de la cuenta de Telegram a usar. Omitir para usar la cuenta principal. "
                   "Ver cuentas con 'telegram_list_accounts'.",
}

TELEGRAM_TOOLS = [
    {
        "name": "telegram_list_accounts",
        "description": "List the configured Telegram accounts managed by this gateway. Returns account id, whether it is the default, the phone and whether it is signed in, WITHOUT exposing secrets. Use this to discover the 'account' values you can pass to the other telegram tools.",
        "inputSchema": {"type": "object", "properties": {}},
    },
    {
        "name": "telegram_status",
        "description": "Checks whether the Telegram account is authorized and connected (session valid).",
        "inputSchema": {"type": "object", "properties": {"account": _ACCOUNT}},
    },
    {
        "name": "telegram_request_code",
        "description": "Requests a login code (Telegram sends it to the app/phone). Use before telegram_sign_in when the account has no valid session.",
        "inputSchema": {"type": "object", "properties": {"account": _ACCOUNT}},
    },
    {
        "name": "telegram_sign_in",
        "description": "Completes the Telegram login using the code received. Persists the session so future calls work. IMPORTANT: Ask the user for the code.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "code": {"type": "string", "description": "The one-time login code received on the phone/other device."},
                "phone_code_hash": {"type": "string", "description": "Optional."},
                "account": _ACCOUNT,
            },
            "required": ["code"],
        },
    },
    {
        "name": "telegram_logout",
        "description": "Logs out and removes the Telegram session for the account.",
        "inputSchema": {"type": "object", "properties": {"account": _ACCOUNT}},
    },
    {
        "name": "telegram_list_chats",
        "description": "List the user's chats/dialogs.",
        "inputSchema": {"type": "object", "properties": {"limit": {"type": "integer"}, "account": _ACCOUNT}},
    },
    {
        "name": "telegram_send_message",
        "description": "Send a message to a chat (username, phone, or chat id). IMPORTANT: Ask the user for explicit confirmation before sending.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "entity": {"type": "string", "description": "Chat identifier: @username, phone, or chat id."},
                "message": {"type": "string"},
                "account": _ACCOUNT,
            },
            "required": ["entity", "message"],
        },
    },
    {
        "name": "telegram_get_messages",
        "description": "Get recent messages from a chat.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "entity": {"type": "string"},
                "limit": {"type": "integer"},
                "account": _ACCOUNT,
            },
            "required": ["entity"],
        },
    },
]
