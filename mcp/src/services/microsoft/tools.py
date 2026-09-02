_ACCOUNT = {
    "type": "string",
    "description": "Nombre/alias de la cuenta de Microsoft 365 a usar. Omitir para usar la cuenta principal. "
                   "Ver cuentas con 'outlook_list_accounts'.",
}

MICROSOFT_TOOLS = [
    {
        "name": "outlook_list_accounts",
        "description": "List the configured Microsoft 365 / Outlook accounts managed by this gateway. Returns account id, whether it is the default, the account email and scopes, WITHOUT exposing tokens. Use this to discover the 'account' values you can pass to the other outlook tools.",
        "inputSchema": {"type": "object", "properties": {}},
    },
    {
        "name": "outlook_mail_list",
        "description": "List Outlook / Microsoft 365 mailbox messages.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "filter": {"type": "string", "description": "OData filter (e.g. 'isRead eq false')."},
                "search": {"type": "string", "description": "Search text."},
                "top": {"type": "integer", "description": "Max items (default 10)."},
                "account": _ACCOUNT,
            }
        },
    },
    {
        "name": "outlook_mail_get",
        "description": "Get a full Outlook message by id (optionally with attachments).",
        "inputSchema": {
            "type": "object",
            "properties": {
                "message_id": {"type": "string"},
                "include_attachments": {"type": "boolean"},
                "account": _ACCOUNT,
            },
            "required": ["message_id"],
        },
    },
    {
        "name": "outlook_mail_send",
        "description": "Send an email from the account. IMPORTANT: Ask the user for explicit confirmation before sending.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "to": {"type": "string"},
                "subject": {"type": "string"},
                "body": {"type": "string"},
                "cc": {"type": "string"},
                "attachments": {"type": "array", "items": {"type": "object", "properties": {"filename": {"type": "string"}, "data": {"type": "string", "description": "File content base64."}}, "required": ["filename", "data"]}},
                "account": _ACCOUNT,
            },
            "required": ["to", "subject", "body"],
        },
    },
    {
        "name": "outlook_mail_set_read",
        "description": "Mark an Outlook message as read or unread.",
        "inputSchema": {
            "type": "object",
            "properties": {"message_id": {"type": "string"}, "read": {"type": "boolean"}, "account": _ACCOUNT},
            "required": ["message_id"],
        },
    },
    {
        "name": "outlook_drafts",
        "description": "List Outlook drafts.",
        "inputSchema": {"type": "object", "properties": {"account": _ACCOUNT}},
    },
    {
        "name": "outlook_draft_send",
        "description": "Send an Outlook draft.",
        "inputSchema": {
            "type": "object",
            "properties": {"message_id": {"type": "string"}, "account": _ACCOUNT},
            "required": ["message_id"],
        },
    },
    {
        "name": "outlook_folders",
        "description": "List Outlook mail folders with unread/total counts.",
        "inputSchema": {"type": "object", "properties": {"account": _ACCOUNT}},
    },
    {
        "name": "outlook_mail_transcribe_attachment",
        "description": "Transcribe an audio attachment of an Outlook message using the configured ASR (same backend as Hermes by default).",
        "inputSchema": {
            "type": "object",
            "properties": {"message_id": {"type": "string"}, "attachment_index": {"type": "integer"}, "language": {"type": "string"}, "account": _ACCOUNT},
            "required": ["message_id"],
        },
    },
    {
        "name": "outlook_calendar_events",
        "description": "List upcoming calendar events.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "top": {"type": "integer"},
                "calendar_id": {"type": "string", "description": "Calendar id (default 'calendars/me')."},
                "account": _ACCOUNT,
            }
        },
    },
    {
        "name": "outlook_calendar_create",
        "description": "Create a calendar event. IMPORTANT: Ask the user for explicit confirmation before creating.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "subject": {"type": "string"},
                "body": {"type": "string"},
                "start": {"type": "string", "description": "ISO 8601 datetime (e.g. 2026-09-01T09:00:00Z)."},
                "end": {"type": "string"},
                "attendees": {"type": "array", "items": {"type": "string"}},
                "calendar_id": {"type": "string"},
                "account": _ACCOUNT,
            },
            "required": ["subject", "start", "end"],
        },
    },
]
