_ACCOUNT = {
    "type": "string",
    "description": "Nombre/alias de la cuenta de WhatsApp a usar. Omitir para usar la cuenta principal. "
                   "Ver cuentas con 'whatsapp_list_accounts'.",
}

WHATSAPP_TOOLS = [
    {
        "name": "whatsapp_list_accounts",
        "description": "List the configured WhatsApp accounts managed by this gateway. Returns account id, phone and whether it is linked, WITHOUT exposing secrets. Use this to discover the 'account' values you can pass to the other whatsapp tools.",
        "inputSchema": {"type": "object", "properties": {}},
    },
    {
        "name": "whatsapp_status",
        "description": "Checks whether the WhatsApp bridge is running and the phone is linked (and returns the QR string if a link is pending).",
        "inputSchema": {"type": "object", "properties": {"account": _ACCOUNT}},
    },
    {
        "name": "whatsapp_list_chats",
        "description": "List known chats (contacts/groups).",
        "inputSchema": {"type": "object", "properties": {"account": _ACCOUNT}},
    },
    {
        "name": "whatsapp_get_messages",
        "description": "Get recent messages from a chat by chat id (e.g. '57300...@s.whatsapp.net').",
        "inputSchema": {
            "type": "object",
            "properties": {"chat_id": {"type": "string"}, "limit": {"type": "integer"}, "account": _ACCOUNT},
            "required": ["chat_id"],
        },
    },
    {
        "name": "whatsapp_send_message",
        "description": "Send a WhatsApp message to a chat id. IMPORTANT: Ask the user for explicit confirmation before sending.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "chat_id": {"type": "string", "description": "JID, e.g. '57300...@s.whatsapp.net' or '@g.us' for groups."},
                "message": {"type": "string"},
                "account": _ACCOUNT,
            },
            "required": ["chat_id", "message"],
        },
    },
]
