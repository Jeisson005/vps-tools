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
        "name": "outlook_draft_create",
        "description": "Create an Outlook draft (it is NOT sent; use outlook_draft_send to send it later).",
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
        "name": "outlook_draft_send",
        "description": "Send an Outlook draft.",
        "inputSchema": {
            "type": "object",
            "properties": {"message_id": {"type": "string"}, "account": _ACCOUNT},
            "required": ["message_id"],
        },
    },
    {
        "name": "outlook_draft_delete",
        "description": "Delete an Outlook draft. IMPORTANT: Ask the user for explicit confirmation before deleting.",
        "inputSchema": {
            "type": "object",
            "properties": {"message_id": {"type": "string", "description": "Draft message id."}, "account": _ACCOUNT},
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
        "description": "List calendar events in a time range (ascending start order). For upcoming events pass time_min = now.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "top": {"type": "integer"},
                "calendar_id": {"type": "string", "description": "Calendar id (default 'me')."},
                "time_min": {"type": "string", "description": "ISO 8601 datetime (e.g. 2026-09-21T00:00:00Z). Omit for no lower bound."},
                "time_max": {"type": "string", "description": "ISO 8601 datetime."},
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
    {
        "name": "outlook_calendar_delete",
        "description": "Delete a calendar event by id. IMPORTANT: Ask the user for explicit confirmation before deleting.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "event_id": {"type": "string", "description": "Calendar event id."},
                "calendar_id": {"type": "string", "description": "Calendar id (default 'me')."},
                "account": _ACCOUNT,
            },
            "required": ["event_id"],
        },
    },
    {
        "name": "teams_list_joined",
        "description": "List Microsoft Teams teams joined by the account (id, displayName).",
        "inputSchema": {"type": "object", "properties": {"account": _ACCOUNT}},
    },
    {
        "name": "teams_list_channels",
        "description": "List channels of a Team (id, displayName).",
        "inputSchema": {
            "type": "object",
            "properties": {"team_id": {"type": "string"}, "account": _ACCOUNT},
            "required": ["team_id"],
        },
    },
    {
        "name": "teams_channel_messages",
        "description": "List recent messages of a Teams channel.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "team_id": {"type": "string"},
                "channel_id": {"type": "string"},
                "top": {"type": "integer", "description": "Max items (default 20)."},
                "account": _ACCOUNT,
            },
            "required": ["team_id", "channel_id"],
        },
    },
    {
        "name": "teams_channel_send",
        "description": "Send a message to a Teams channel. IMPORTANT: Ask the user for explicit confirmation before sending.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "team_id": {"type": "string"},
                "channel_id": {"type": "string"},
                "message": {"type": "string"},
                "account": _ACCOUNT,
            },
            "required": ["team_id", "channel_id", "message"],
        },
    },
    {
        "name": "teams_list_chats",
        "description": "List 1:1 and group chats of the account (id, topic, members).",
        "inputSchema": {
            "type": "object",
            "properties": {
                "top": {"type": "integer", "description": "Max items (default 20)."},
                "account": _ACCOUNT,
            }
        },
    },
    {
        "name": "teams_chat_messages",
        "description": "List recent messages of a Teams chat.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "chat_id": {"type": "string"},
                "top": {"type": "integer", "description": "Max items (default 20)."},
                "account": _ACCOUNT,
            },
            "required": ["chat_id"],
        },
    },
    {
        "name": "teams_chat_send",
        "description": "Send a message to a Teams chat. IMPORTANT: Ask the user for explicit confirmation before sending.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "chat_id": {"type": "string"},
                "message": {"type": "string"},
                "account": _ACCOUNT,
            },
            "required": ["chat_id", "message"],
        },
    },
    {
        "name": "onedrive_list",
        "description": "List OneDrive files/folders (id, name, size, mimeType).",
        "inputSchema": {
            "type": "object",
            "properties": {
                "item_id": {"type": "string", "description": "Folder id (omit = root)."},
                "top": {"type": "integer", "description": "Max items (default 50)."},
                "account": _ACCOUNT,
            }
        },
    },
    {
        "name": "onedrive_get",
        "description": "Get OneDrive file/folder metadata by item id.",
        "inputSchema": {
            "type": "object",
            "properties": {"item_id": {"type": "string"}, "account": _ACCOUNT},
            "required": ["item_id"],
        },
    },
    {
        "name": "onedrive_download",
        "description": "Download a OneDrive file (base64, max 4 MB).",
        "inputSchema": {
            "type": "object",
            "properties": {"item_id": {"type": "string"}, "account": _ACCOUNT},
            "required": ["item_id"],
        },
    },
    {
        "name": "onedrive_upload",
        "description": "Upload text or base64 content to OneDrive (max 10 MB). IMPORTANT: Ask the user for explicit confirmation before uploading.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "name": {"type": "string", "description": "File name in OneDrive."},
                "content_text": {"type": "string", "description": "Plain text content (alternative to data)."},
                "data": {"type": "string", "description": "File content base64 (alternative to content_text)."},
                "mime_type": {"type": "string", "description": "MIME type (default text/plain)."},
                "folder_id": {"type": "string", "description": "Destination folder id (omit = root)."},
                "account": _ACCOUNT,
            },
            "required": ["name"],
        },
    },
    {
        "name": "onedrive_delete",
        "description": "Delete a OneDrive file/folder by item id. IMPORTANT: Ask the user for explicit confirmation before deleting.",
        "inputSchema": {
            "type": "object",
            "properties": {"item_id": {"type": "string"}, "account": _ACCOUNT},
            "required": ["item_id"],
        },
    },
]
