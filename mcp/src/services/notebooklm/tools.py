_ACCOUNT = {
    "type": "string",
    "description": "Nombre/alias de la cuenta NotebookLM a usar. Omitir para usar la cuenta principal. "
                   "Ver cuentas con 'notebooklm_list_accounts'.",
}

NOTEBOOKLM_TOOLS = [
    {
        "name": "notebooklm_list_accounts",
        "description": "List the configured NotebookLM accounts managed by this gateway (id, default flag, email). WITHOUT exposing auth cookies. Use this to discover the 'account' values you can pass to the other notebooklm tools.",
        "inputSchema": {"type": "object", "properties": {}},
    },
    {
        "name": "notebooklm_auth_check",
        "description": "Check NotebookLM authentication status for an account (validates stored Google session cookies with a live network test). Call this after adding an account or when tools return AUTH errors.",
        "inputSchema": {"type": "object", "properties": {"account": _ACCOUNT}},
    },
    {
        "name": "notebooklm_list_notebooks",
        "description": "List NotebookLM notebooks (id, title, sources count). Start here to discover notebook_id.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "limit": {"type": "integer", "description": "Max notebooks to return (default 50)."},
                "account": _ACCOUNT,
            },
        },
    },
    {
        "name": "notebooklm_create_notebook",
        "description": "Create a new NotebookLM notebook. IMPORTANT: Ask the user for explicit confirmation before creating.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "title": {"type": "string", "description": "Title for the new notebook."},
                "account": _ACCOUNT,
            },
            "required": ["title"],
        },
    },
    {
        "name": "notebooklm_rename_notebook",
        "description": "Rename a NotebookLM notebook. IMPORTANT: Ask the user for explicit confirmation before modifying.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "notebook_id": {"type": "string"},
                "new_title": {"type": "string"},
                "account": _ACCOUNT,
            },
            "required": ["notebook_id", "new_title"],
        },
    },
    {
        "name": "notebooklm_delete_notebook",
        "description": "Delete a NotebookLM notebook and all its sources. IMPORTANT: Ask the user for explicit confirmation before deleting.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "notebook_id": {"type": "string"},
                "account": _ACCOUNT,
            },
            "required": ["notebook_id"],
        },
    },
    {
        "name": "notebooklm_describe_notebook",
        "description": "Get notebook metadata + simplified source list (title, type, status).",
        "inputSchema": {
            "type": "object",
            "properties": {
                "notebook_id": {"type": "string"},
                "account": _ACCOUNT,
            },
            "required": ["notebook_id"],
        },
    },
    {
        "name": "notebooklm_list_sources",
        "description": "List sources in a notebook (id, title, type, status).",
        "inputSchema": {
            "type": "object",
            "properties": {
                "notebook_id": {"type": "string"},
                "limit": {"type": "integer", "description": "Max sources (default 50)."},
                "status": {"type": "string", "description": "Filter by ingestion status: ready, processing, error, preparing, unknown (optional)."},
                "account": _ACCOUNT,
            },
            "required": ["notebook_id"],
        },
    },
    {
        "name": "notebooklm_get_source",
        "description": "Get metadata for a single source (title, type, ingestion + Drive health).",
        "inputSchema": {
            "type": "object",
            "properties": {
                "notebook_id": {"type": "string"},
                "source_id": {"type": "string"},
                "account": _ACCOUNT,
            },
            "required": ["notebook_id", "source_id"],
        },
    },
    {
        "name": "notebooklm_fulltext_source",
        "description": "Retrieve the indexed text of a source. Large texts are truncated server-side (returns truncated flag + char_count) to protect the LLM context window.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "notebook_id": {"type": "string"},
                "source_id": {"type": "string"},
                "max_chars": {"type": "integer", "description": "Max chars to return (default 15000, max 60000)."},
                "account": _ACCOUNT,
            },
            "required": ["notebook_id", "source_id"],
        },
    },
    {
        "name": "notebooklm_search_sources",
        "description": "Passage-search across the indexed text of all sources in a notebook, ordered by relevance rank.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "notebook_id": {"type": "string"},
                "query": {"type": "string"},
                "limit": {"type": "integer", "description": "Max passages (default 5)."},
                "account": _ACCOUNT,
            },
            "required": ["notebook_id", "query"],
        },
    },
    {
        "name": "notebooklm_add_source_url",
        "description": "Add a URL or YouTube video as a source to a notebook. IMPORTANT: Ask the user for explicit confirmation before adding.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "notebook_id": {"type": "string"},
                "url": {"type": "string"},
                "title": {"type": "string", "description": "Optional custom title."},
                "wait": {"type": "boolean", "description": "Wait until the source finishes processing (default true)."},
                "account": _ACCOUNT,
            },
            "required": ["notebook_id", "url"],
        },
    },
    {
        "name": "notebooklm_add_source_text",
        "description": "Add pasted text as a source to a notebook. IMPORTANT: Ask the user for explicit confirmation before adding.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "notebook_id": {"type": "string"},
                "text": {"type": "string", "description": "Text content to ingest."},
                "title": {"type": "string", "description": "Title for the text source (required by NotebookLM)."},
                "account": _ACCOUNT,
            },
            "required": ["notebook_id", "text", "title"],
        },
    },
    {
        "name": "notebooklm_ask",
        "description": "Ask a grounded question over a notebook's sources. The answer is synthesized by Gemini from YOUR sources with citations (zero-token RAG offload for the agent).",
        "inputSchema": {
            "type": "object",
            "properties": {
                "notebook_id": {"type": "string"},
                "question": {"type": "string"},
                "source_ids": {"type": "array", "items": {"type": "string"}, "description": "Optional: restrict the answer to these source IDs (hard filter)."},
                "conversation_id": {"type": "string", "description": "Optional: continue a previous conversation."},
                "account": _ACCOUNT,
            },
            "required": ["notebook_id", "question"],
        },
    },
    {
        "name": "notebooklm_history",
        "description": "View Q&A conversation history of a notebook.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "notebook_id": {"type": "string"},
                "limit": {"type": "integer", "description": "Max Q&A turns (default 10)."},
                "account": _ACCOUNT,
            },
            "required": ["notebook_id"],
        },
    },
    {
        "name": "notebooklm_suggest_prompts",
        "description": "Get AI-suggested prompts for a notebook (ready-to-send questions for notebooklm_ask).",
        "inputSchema": {
            "type": "object",
            "properties": {
                "notebook_id": {"type": "string"},
                "account": _ACCOUNT,
            },
            "required": ["notebook_id"],
        },
    },
]
