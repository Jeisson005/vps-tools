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
                "from": {"type": "string", "description": "SendAs identity to send from (see google_gmail_sendas_list). Omit = default identity."},
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
                "from": {"type": "string", "description": "SendAs identity for the draft (see google_gmail_sendas_list). Omit = default identity."},
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
        "name": "google_gmail_draft_delete",
        "description": "Delete a Gmail draft (does not affect sent mail). IMPORTANT: Ask the user for explicit confirmation before deleting.",
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
        "name": "google_gmail_sendas_list",
        "description": "List the account's SendAs identities (extra 'send mail as' addresses and which is default).",
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
    {
        "name": "google_calendar_delete",
        "description": "Delete a calendar event by id. IMPORTANT: Ask the user for explicit confirmation before deleting.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "event_id": {"type": "string", "description": "Calendar event id."},
                "calendar_id": {"type": "string", "description": "Calendar id (default 'primary')."},
                "account": _ACCOUNT,
            },
            "required": ["event_id"],
        },
    },
    {
        "name": "google_drive_list",
        "description": "List Google Drive files (id, name, mimeType, size). Supports Drive search queries.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Drive search query (e.g. \"name contains 'factura'\", \"mimeType='application/pdf'\"). Empty = recent files."},
                "page_size": {"type": "integer", "description": "Max results (1-100, default 20)."},
                "order_by": {"type": "string", "description": "Order (default 'modifiedTime desc')."},
                "account": _ACCOUNT,
            },
        },
    },
    {
        "name": "google_drive_get",
        "description": "Get Google Drive file metadata by file id.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "file_id": {"type": "string", "description": "Drive file id."},
                "account": _ACCOUNT,
            },
            "required": ["file_id"],
        },
    },
    {
        "name": "google_drive_download",
        "description": "Download a Google Drive file (base64, max 4 MB). Google Docs/Sheets/Slides are auto-exported to text/CSV.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "file_id": {"type": "string", "description": "Drive file id."},
                "account": _ACCOUNT,
            },
            "required": ["file_id"],
        },
    },
    {
        "name": "google_drive_create_folder",
        "description": "Create a folder in Google Drive. IMPORTANT: Ask the user for explicit confirmation before creating.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "name": {"type": "string", "description": "Folder name."},
                "parent_id": {"type": "string", "description": "Parent folder id (optional)."},
                "account": _ACCOUNT,
            },
            "required": ["name"],
        },
    },
    {
        "name": "google_drive_upload",
            "description": "Upload text or base64 content to Google Drive (max 10 MB). Without content, creates an empty native file (e.g. mime_type application/vnd.google-apps.spreadsheet). IMPORTANT: Ask the user for explicit confirmation before uploading.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "name": {"type": "string", "description": "File name in Drive."},
                "content_text": {"type": "string", "description": "Plain text content (alternative to data)."},
                "data": {"type": "string", "description": "File content base64 (alternative to content_text)."},
                "mime_type": {"type": "string", "description": "MIME type (e.g. text/plain, application/pdf)."},
                "parent_id": {"type": "string", "description": "Parent folder id (optional)."},
                "account": _ACCOUNT,
            },
            "required": ["name"],
        },
    },
    {
        "name": "google_drive_delete",
        "description": "Move a Google Drive file to trash by file id. IMPORTANT: Ask the user for explicit confirmation before deleting.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "file_id": {"type": "string", "description": "Drive file id."},
                "account": _ACCOUNT,
            },
            "required": ["file_id"],
        },
    },
    {
        "name": "google_contacts_search",
        "description": "Search Google contacts by name, email or phone (returns name, emails, phones).",
        "inputSchema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Search text (e.g. 'juan', 'acme.com')."},
                "page_size": {"type": "integer", "description": "Max results (1-30, default 10)."},
                "account": _ACCOUNT,
            },
            "required": ["query"],
        },
    },
    {
        "name": "google_contacts_list",
        "description": "List Google contacts (name, emails, phones).",
        "inputSchema": {
            "type": "object",
            "properties": {
                "page_size": {"type": "integer", "description": "Max results (1-100, default 20)."},
                "account": _ACCOUNT,
            },
        },
    },
    {
        "name": "google_sheets_info",
        "description": "Get spreadsheet title and tab names by spreadsheet id.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "spreadsheet_id": {"type": "string", "description": "Spreadsheet id (from its URL)."},
                "account": _ACCOUNT,
            },
            "required": ["spreadsheet_id"],
        },
    },
    {
        "name": "google_sheets_read",
        "description": "Read cell values from a Google Sheet range (e.g. 'Hoja1!A1:D20').",
        "inputSchema": {
            "type": "object",
            "properties": {
                "spreadsheet_id": {"type": "string", "description": "Spreadsheet id (from its URL)."},
                "range": {"type": "string", "description": "A1 notation range (e.g. 'Hoja1!A1:D20')."},
                "account": _ACCOUNT,
            },
            "required": ["spreadsheet_id", "range"],
        },
    },
    {
        "name": "google_sheets_append",
        "description": "Append rows to a Google Sheet. IMPORTANT: Ask the user for explicit confirmation before writing.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "spreadsheet_id": {"type": "string"},
                "range": {"type": "string", "description": "A1 notation range to append to (e.g. 'Hoja1!A:D')."},
                "values": {"type": "array", "items": {"type": "array", "items": {"type": "string"}}, "description": "Rows to append (e.g. [[\"a\",\"b\"],[\"c\",\"d\"]])."},
                "account": _ACCOUNT,
            },
            "required": ["spreadsheet_id", "range", "values"],
        },
    },
    {
        "name": "google_sheets_update",
        "description": "Overwrite a Google Sheet range with new values. IMPORTANT: Ask the user for explicit confirmation before writing.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "spreadsheet_id": {"type": "string"},
                "range": {"type": "string", "description": "A1 notation range to overwrite (e.g. 'Hoja1!A1:B2')."},
                "values": {"type": "array", "items": {"type": "array", "items": {"type": "string"}}, "description": "New values."},
                "account": _ACCOUNT,
            },
            "required": ["spreadsheet_id", "range", "values"],
        },
    },
    {
        "name": "google_docs_get",
        "description": "Read a Google Doc as plain text by document id (truncated at 8000 chars).",
        "inputSchema": {
            "type": "object",
            "properties": {
                "document_id": {"type": "string", "description": "Document id (from its URL)."},
                "account": _ACCOUNT,
            },
            "required": ["document_id"],
        },
    },
    {
        "name": "google_docs_append",
        "description": "Append text at the end of a Google Doc. IMPORTANT: Ask the user for explicit confirmation before writing.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "document_id": {"type": "string", "description": "Document id (from its URL)."},
                "text": {"type": "string", "description": "Text to append."},
                "account": _ACCOUNT,
            },
            "required": ["document_id", "text"],
        },
    },
    {
        "name": "google_photos_list",
        "description": "List recent Google Photos (id, description, date, view/download URLs).",
        "inputSchema": {
            "type": "object",
            "properties": {
                "page_size": {"type": "integer", "description": "Max results (1-100, default 20)."},
                "account": _ACCOUNT,
            },
        },
    },
    {
        "name": "google_photos_get",
        "description": "Get a Google Photo by media item id (metadata + view/download URLs).",
        "inputSchema": {
            "type": "object",
            "properties": {
                "media_item_id": {"type": "string", "description": "Media item id."},
                "account": _ACCOUNT,
            },
            "required": ["media_item_id"],
        },
    },
    {
        "name": "google_photos_search",
        "description": "Search Google Photos by date, content category and media type.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "year": {"type": "integer", "description": "Year (e.g. 2025)."},
                "month": {"type": "integer", "description": "Month 1-12 (optional)."},
                "day": {"type": "integer", "description": "Day 1-31 (optional)."},
                "content_category": {"type": "string", "description": "Category (e.g. PEOPLE, PETS, FOOD, TRAVEL, RECEIPTS, SCREENSHOTS, SELFIES, LANDSCAPES, DOCUMENTS)."},
                "media_type": {"type": "string", "enum": ["ALL_MEDIA", "PHOTO", "VIDEO"], "description": "Media type (default ALL_MEDIA)."},
                "page_size": {"type": "integer", "description": "Max results (1-100, default 20)."},
                "account": _ACCOUNT,
            },
        },
    },
    {
        "name": "google_photos_albums",
        "description": "List Google Photos albums (id, title, item count).",
        "inputSchema": {
            "type": "object",
            "properties": {
                "page_size": {"type": "integer", "description": "Max results (1-50, default 20)."},
                "account": _ACCOUNT,
            },
        },
    },
]
