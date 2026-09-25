_ACCOUNT = {
    "type": "string",
    "description": "Nombre/alias de la cuenta Trello a usar. Omitir para usar la cuenta principal. "
                   "Ver cuentas con 'trello_list_accounts'.",
}

TRELLO_TOOLS = [
    {
        "name": "trello_list_accounts",
        "description": "List the configured Trello accounts managed by this gateway. Returns account id and whether it is the default, WITHOUT exposing API keys/tokens. Use this to discover the 'account' values you can pass to the other trello tools.",
        "inputSchema": {"type": "object", "properties": {}},
    },
    {
        "name": "trello_get_user",
        "description": "Get the Trello user that owns the API token (id, fullName, username).",
        "inputSchema": {"type": "object", "properties": {"account": _ACCOUNT}},
    },
    {
        "name": "trello_list_boards",
        "description": "List Trello boards visible to the account (id, name, url, closed). Start here to discover board_id.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "filter": {"type": "string", "description": "Board filter: open (default), closed, all, starred."},
                "account": _ACCOUNT,
            },
        },
    },
    {
        "name": "trello_get_board",
        "description": "Get a single board by id, including its open lists and members.",
        "inputSchema": {
            "type": "object",
            "properties": {"board_id": {"type": "string"}, "account": _ACCOUNT},
            "required": ["board_id"],
        },
    },
    {
        "name": "trello_create_board",
        "description": "Create a board (with default lists). IMPORTANT: Ask the user for explicit confirmation before creating.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "name": {"type": "string"},
                "desc": {"type": "string"},
                "account": _ACCOUNT,
            },
            "required": ["name"],
        },
    },
    {
        "name": "trello_list_lists",
        "description": "List Lists on a board (id, name, pos). Needs board_id (see trello_list_boards).",
        "inputSchema": {
            "type": "object",
            "properties": {
                "board_id": {"type": "string"},
                "filter": {"type": "string", "description": "List filter: open (default), closed, all."},
                "account": _ACCOUNT,
            },
            "required": ["board_id"],
        },
    },
    {
        "name": "trello_create_list",
        "description": "Create a List on a board. IMPORTANT: Ask the user for explicit confirmation before creating.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "board_id": {"type": "string"},
                "name": {"type": "string"},
                "pos": {"type": "string", "description": "Position: top, bottom (default) or a number."},
                "account": _ACCOUNT,
            },
            "required": ["board_id", "name"],
        },
    },
    {
        "name": "trello_update_list",
        "description": "Rename (name) and/or archive/unarchive (closed) a List. IMPORTANT: Ask the user for explicit confirmation before modifying.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "list_id": {"type": "string"},
                "name": {"type": "string"},
                "closed": {"type": "boolean", "description": "true to archive, false to unarchive."},
                "account": _ACCOUNT,
            },
            "required": ["list_id"],
        },
    },
    {
        "name": "trello_list_cards",
        "description": "List cards: pass list_id (cards of one List) OR board_id (all cards of the Board). Returns id, name, due, members, labels, url.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "list_id": {"type": "string"},
                "board_id": {"type": "string"},
                "filter": {"type": "string", "description": "Only for board_id: open (default), closed, all, visible."},
                "account": _ACCOUNT,
            },
        },
    },
    {
        "name": "trello_get_card",
        "description": "Get a single card by id (full details: description, members, checklists, recent comments).",
        "inputSchema": {
            "type": "object",
            "properties": {"card_id": {"type": "string"}, "account": _ACCOUNT},
            "required": ["card_id"],
        },
    },
    {
        "name": "trello_create_card",
        "description": "Create a card in a List. IMPORTANT: Ask the user for explicit confirmation before creating.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "list_id": {"type": "string"},
                "name": {"type": "string", "description": "Card title (required)."},
                "desc": {"type": "string"},
                "due": {"type": "string", "description": "Due date ISO 8601 (e.g. 2026-10-01T12:00:00Z)."},
                "pos": {"type": "string", "description": "Position: top, bottom (default) or a number."},
                "member_ids": {"type": "array", "items": {"type": "string"}, "description": "Member IDs to assign."},
                "label_ids": {"type": "array", "items": {"type": "string"}, "description": "Label IDs to assign (see trello_list_labels)."},
                "account": _ACCOUNT,
            },
            "required": ["list_id", "name"],
        },
    },
    {
        "name": "trello_update_card",
        "description": "Update a card: rename, description, due date, complete/uncomplete (dueComplete), move to another list (idList), position, members, archive/unarchive (closed). IMPORTANT: Ask the user for explicit confirmation before modifying.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "card_id": {"type": "string"},
                "name": {"type": "string"},
                "desc": {"type": "string"},
                "due": {"type": "string", "description": "Due date ISO 8601. Empty string clears it."},
                "dueComplete": {"type": "boolean"},
                "closed": {"type": "boolean", "description": "true to archive, false to unarchive."},
                "idList": {"type": "string", "description": "Target list id to move the card."},
                "pos": {"type": "string"},
                "member_ids": {"type": "array", "items": {"type": "string"}},
                "label_ids": {"type": "array", "items": {"type": "string"}, "description": "Full replacement of the card's labels."},
                "account": _ACCOUNT,
            },
            "required": ["card_id"],
        },
    },
    {
        "name": "trello_archive_card",
        "description": "Archive a card (closed=true). IMPORTANT: Ask the user for explicit confirmation before archiving.",
        "inputSchema": {
            "type": "object",
            "properties": {"card_id": {"type": "string"}, "account": _ACCOUNT},
            "required": ["card_id"],
        },
    },
    {
        "name": "trello_list_card_comments",
        "description": "List comments on a card (id, text, date, author).",
        "inputSchema": {
            "type": "object",
            "properties": {
                "card_id": {"type": "string"},
                "limit": {"type": "integer", "description": "Max comments (default 50)."},
                "account": _ACCOUNT,
            },
            "required": ["card_id"],
        },
    },
    {
        "name": "trello_create_card_comment",
        "description": "Add a comment to a card. IMPORTANT: Ask the user for explicit confirmation before commenting.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "card_id": {"type": "string"},
                "text": {"type": "string"},
                "account": _ACCOUNT,
            },
            "required": ["card_id", "text"],
        },
    },
    {
        "name": "trello_update_card_comment",
        "description": "Edit a comment on a card (needs the comment id from trello_list_card_comments). IMPORTANT: Ask the user for explicit confirmation before modifying.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "card_id": {"type": "string"},
                "comment_id": {"type": "string"},
                "text": {"type": "string"},
                "account": _ACCOUNT,
            },
            "required": ["card_id", "comment_id", "text"],
        },
    },
    {
        "name": "trello_delete_card_comment",
        "description": "Delete a comment from a card. IMPORTANT: Ask the user for explicit confirmation before deleting.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "card_id": {"type": "string"},
                "comment_id": {"type": "string"},
                "account": _ACCOUNT,
            },
            "required": ["card_id", "comment_id"],
        },
    },
    {
        "name": "trello_delete_attachment",
        "description": "Delete an attachment from a card (see ids in trello_get_card attachments). IMPORTANT: Ask the user for explicit confirmation before deleting.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "card_id": {"type": "string"},
                "attachment_id": {"type": "string"},
                "account": _ACCOUNT,
            },
            "required": ["card_id", "attachment_id"],
        },
    },
    {
        "name": "trello_list_board_members",
        "description": "List board members (id, fullName, username) to resolve member IDs for card assignment.",
        "inputSchema": {
            "type": "object",
            "properties": {"board_id": {"type": "string"}, "account": _ACCOUNT},
            "required": ["board_id"],
        },
    },
    {
        "name": "trello_search",
        "description": "Search Trello for cards and boards by keyword (Trello search syntax supported). NOTE: Trello's search index lags a few minutes — brand-new cards may not appear immediately; archived cards ARE included (filter with include_closed=false). Search is case-insensitive.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "query": {"type": "string"},
                "model_types": {"type": "string", "description": "Comma list, e.g. 'cards,boards' (default)."},
                "cards_limit": {"type": "integer"},
                "boards_limit": {"type": "integer"},
                "include_closed": {"type": "boolean", "description": "Include archived cards (default true)."},
                "account": _ACCOUNT,
            },
            "required": ["query"],
        },
    },
    {
        "name": "trello_delete_card",
        "description": "PERMANENTLY delete a card (cannot be undone; unlike archive it disappears completely). IMPORTANT: Ask the user for explicit confirmation before deleting.",
        "inputSchema": {
            "type": "object",
            "properties": {"card_id": {"type": "string"}, "account": _ACCOUNT},
            "required": ["card_id"],
        },
    },
    {
        "name": "trello_delete_board",
        "description": "PERMANENTLY delete a board with all its lists and cards (cannot be undone). IMPORTANT: Ask the user for explicit confirmation before deleting.",
        "inputSchema": {
            "type": "object",
            "properties": {"board_id": {"type": "string"}, "account": _ACCOUNT},
            "required": ["board_id"],
        },
    },
    {
        "name": "trello_archive_list",
        "description": "Archive a List AND all its cards in one step (archiving a list alone via trello_update_list leaves its cards active; the Trello API has no permanent list delete). IMPORTANT: Ask the user for explicit confirmation.",
        "inputSchema": {
            "type": "object",
            "properties": {"list_id": {"type": "string"}, "account": _ACCOUNT},
            "required": ["list_id"],
        },
    },
    {
        "name": "trello_list_labels",
        "description": "List labels defined on a board (id, name, color). Use the ids for trello_create_card / trello_update_card label_ids.",
        "inputSchema": {
            "type": "object",
            "properties": {"board_id": {"type": "string"}, "account": _ACCOUNT},
            "required": ["board_id"],
        },
    },
    {
        "name": "trello_create_label",
        "description": "Create a label on a board (color: green, yellow, orange, red, purple, blue, sky, lime, pink, black). IMPORTANT: Ask the user for explicit confirmation before creating.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "board_id": {"type": "string"},
                "name": {"type": "string"},
                "color": {"type": "string"},
                "account": _ACCOUNT,
            },
            "required": ["board_id", "name", "color"],
        },
    },
    {
        "name": "trello_update_label",
        "description": "Rename and/or recolor a label. IMPORTANT: Ask the user for explicit confirmation before modifying.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "label_id": {"type": "string"},
                "name": {"type": "string"},
                "color": {"type": "string"},
                "account": _ACCOUNT,
            },
            "required": ["label_id"],
        },
    },
    {
        "name": "trello_delete_label",
        "description": "Delete a label from a board (removes it from all cards using it). IMPORTANT: Ask the user for explicit confirmation before deleting.",
        "inputSchema": {
            "type": "object",
            "properties": {"label_id": {"type": "string"}, "account": _ACCOUNT},
            "required": ["label_id"],
        },
    },
    {
        "name": "trello_create_checklist",
        "description": "Add a checklist to a card. (Reading checklists is already part of trello_get_card.) IMPORTANT: Ask the user for explicit confirmation before creating.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "card_id": {"type": "string"},
                "name": {"type": "string"},
                "pos": {"type": "string"},
                "account": _ACCOUNT,
            },
            "required": ["card_id", "name"],
        },
    },
    {
        "name": "trello_create_checkitem",
        "description": "Add an item to a checklist. IMPORTANT: Ask the user for explicit confirmation before creating.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "checklist_id": {"type": "string"},
                "name": {"type": "string"},
                "pos": {"type": "string"},
                "account": _ACCOUNT,
            },
            "required": ["checklist_id", "name"],
        },
    },
    {
        "name": "trello_update_checkitem",
        "description": "Rename and/or complete/incomplete a checklist item (state: complete, incomplete). IMPORTANT: Ask the user for explicit confirmation before modifying.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "card_id": {"type": "string"},
                "checklist_id": {"type": "string"},
                "checkitem_id": {"type": "string"},
                "state": {"type": "string"},
                "name": {"type": "string"},
                "account": _ACCOUNT,
            },
            "required": ["card_id", "checklist_id", "checkitem_id"],
        },
    },
    {
        "name": "trello_delete_checklist",
        "description": "Delete a checklist from a card. IMPORTANT: Ask the user for explicit confirmation before deleting.",
        "inputSchema": {
            "type": "object",
            "properties": {"checklist_id": {"type": "string"}, "account": _ACCOUNT},
            "required": ["checklist_id"],
        },
    },
    {
        "name": "trello_add_attachment_url",
        "description": "Attach a link (URL) to a card. (Listing attachments is already part of trello_get_card. Binary file upload is not supported by this gateway.) IMPORTANT: Ask the user for explicit confirmation before attaching.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "card_id": {"type": "string"},
                "url": {"type": "string"},
                "name": {"type": "string"},
                "account": _ACCOUNT,
            },
            "required": ["card_id", "url"],
        },
    },
    {
        "name": "trello_list_custom_fields",
        "description": "List custom field definitions of a board (id, name, type, dropdown options). Use the ids for trello_set_custom_field.",
        "inputSchema": {
            "type": "object",
            "properties": {"board_id": {"type": "string"}, "account": _ACCOUNT},
            "required": ["board_id"],
        },
    },
    {
        "name": "trello_set_custom_field",
        "description": "Set a custom field value on a card. field_type: text, number, checkbox (value true/false), date (ISO 8601), list (value = option id from trello_list_custom_fields). NOTE: the field definition must already exist on the board (create it in the Trello UI; the API has no field-definition create endpoint, and custom fields require a paid Standard+ workspace). IMPORTANT: Ask the user for explicit confirmation before modifying.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "card_id": {"type": "string"},
                "field_id": {"type": "string"},
                "field_type": {"type": "string"},
                "value": {"type": "string"},
                "account": _ACCOUNT,
            },
            "required": ["card_id", "field_id", "value"],
        },
    },
]
