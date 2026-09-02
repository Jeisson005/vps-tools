_ACCOUNT = {
    "type": "string",
    "description": "Nombre/alias de la cuenta Google a usar. Omitir para usar la cuenta principal. "
                   "Ver cuentas con 'google_list_accounts'.",
}

GOOGLE_TOOLS = [
    {
        "name": "google_list_accounts",
        "description": "List the configured Google accounts (vaults) managed by this gateway. Returns account id, whether it is the default, the account email and scopes, WITHOUT exposing tokens. Use this to discover the 'account' values you can pass to the other google tools.",
        "inputSchema": {"type": "object", "properties": {}},
    },
    {
        "name": "google_gmail_list",
        "description": "List Gmail messages of an account (subject, from, snippet, id).",
        "inputSchema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Gmail search query (e.g. 'from:user@x.com', 'is:unread', 'subject:factura')."},
                "max_results": {"type": "integer", "description": "Max results to return (default 10)."},
                "account": _ACCOUNT,
            }
        },
    },
    {
        "name": "google_gmail_get",
        "description": "Get a full Gmail message (body text, headers, attachments metadata) by message id.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "message_id": {"type": "string", "description": "Gmail message id."},
                "format": {"type": "string", "enum": ["full", "metadata", "text"], "description": "Return format (default full)."},
                "account": _ACCOUNT,
            },
            "required": ["message_id"],
        },
    },
    {
        "name": "google_gmail_send",
        "description": "Send an email from the account (requires 'send as' permission). IMPORTANT: Ask the user for explicit confirmation before sending.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "to": {"type": "string", "description": "Recipient email(s), comma separated."},
                "subject": {"type": "string"},
                "body": {"type": "string", "description": "Plain text or HTML body."},
                "cc": {"type": "string"},
                "bcc": {"type": "string"},
                "account": _ACCOUNT,
            },
            "required": ["to", "subject", "body"],
        },
    },
    {
        "name": "google_calendar_events",
        "description": "List calendar events in a time range.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "calendar_id": {"type": "string", "description": "Calendar id (default 'primary')."},
                "time_min": {"type": "string", "description": "ISO 8601 datetime (e.g. 2026-09-01T00:00:00Z)."},
                "time_max": {"type": "string", "description": "ISO 8601 datetime."},
                "max_results": {"type": "integer"},
                "account": _ACCOUNT,
            }
        },
    },
    {
        "name": "google_calendar_create",
        "description": "Create a calendar event. IMPORTANT: Ask the user for explicit confirmation before creating.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "summary": {"type": "string"},
                "description": {"type": "string"},
                "start": {"type": "string", "description": "ISO 8601 datetime (e.g. 2026-09-01T09:00:00Z)."},
                "end": {"type": "string", "description": "ISO 8601 datetime."},
                "attendees": {"type": "array", "items": {"type": "string"}, "description": "Attendee emails."},
                "calendar_id": {"type": "string"},
                "account": _ACCOUNT,
            },
            "required": ["summary", "start", "end"],
        },
    },
]
