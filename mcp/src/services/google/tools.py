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
        "description": "Get a full Gmail message (body text, headers, attachments) by message id.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "message_id": {"type": "string", "description": "Gmail message id."},
                "format": {"type": "string", "enum": ["full", "metadata", "text"], "description": "Return format (default full)."},
                "include_attachments": {"type": "boolean", "description": "Also return attachment content (base64)."},
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
                "attachments": {"type": "array", "items": {"type": "object", "properties": {"filename": {"type": "string"}, "mimeType": {"type": "string"}, "data": {"type": "string", "description": "File content base64."}}, "required": ["filename", "data"]}, "description": "Attachments to include."},
                "account": _ACCOUNT,
            },
            "required": ["to", "subject", "body"],
        },
    },
    {
        "name": "google_gmail_drafts",
        "description": "List Gmail drafts.",
        "inputSchema": {"type": "object", "properties": {"account": _ACCOUNT}},
    },
    {
        "name": "google_gmail_draft_create",
        "description": "Save an email as a draft in Gmail.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "to": {"type": "string"},
                "subject": {"type": "string"},
                "body": {"type": "string"},
                "attachments": {"type": "array", "items": {"type": "object", "properties": {"filename": {"type": "string"}, "data": {"type": "string"}}, "required": ["filename", "data"]}},
                "account": _ACCOUNT,
            },
            "required": ["to", "subject", "body"],
        },
    },
    {
        "name": "google_gmail_draft_send",
        "description": "Send a saved Gmail draft.",
        "inputSchema": {
            "type": "object",
            "properties": {"draft_id": {"type": "string"}, "account": _ACCOUNT},
            "required": ["draft_id"],
        },
    },
    {
        "name": "google_gmail_labels",
        "description": "List Gmail labels.",
        "inputSchema": {"type": "object", "properties": {"account": _ACCOUNT}},
    },
    {
        "name": "google_gmail_set_read",
        "description": "Mark a Gmail message as read or unread.",
        "inputSchema": {
            "type": "object",
            "properties": {"message_id": {"type": "string"}, "read": {"type": "boolean", "description": "true=read, false=unread"}, "account": _ACCOUNT},
            "required": ["message_id"],
        },
    },
    {
        "name": "google_gmail_thread",
        "description": "Get a full Gmail thread (conversation) by thread id.",
        "inputSchema": {
            "type": "object",
            "properties": {"thread_id": {"type": "string"}, "account": _ACCOUNT},
            "required": ["thread_id"],
        },
    },
    {
        "name": "google_gmail_transcribe_attachment",
        "description": "Transcribe an audio attachment of a Gmail message using the configured ASR (same backend as Hermes by default).",
        "inputSchema": {
            "type": "object",
            "properties": {
                "message_id": {"type": "string"},
                "attachment_index": {"type": "integer", "description": "Index of the attachment (0-based)."},
                "language": {"type": "string"},
                "account": _ACCOUNT,
            },
            "required": ["message_id"],
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
