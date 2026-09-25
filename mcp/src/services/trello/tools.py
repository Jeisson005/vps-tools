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
        "description": "Search Trello for cards and boards by keyword (Trelo search syntax supported).",
        "inputSchema": {
            "type": "object",
            "properties": {
                "query": {"type": "string"},
                "model_types": {"type": "string", "description": "Comma list, e.g. 'cards,boards' (default)."},
                "cards_limit": {"type": "integer"},
                "boards_limit": {"type": "integer"},
                "account": _ACCOUNT,
            },
            "required": ["query"],
        },
    },
]
