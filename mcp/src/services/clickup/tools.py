_ACCOUNT = {
    "type": "string",
    "description": "Nombre/alias de la cuenta ClickUp a usar. Omitir para usar la cuenta principal. "
                   "Ver cuentas con 'clickup_list_accounts'.",
}

CLICKUP_TOOLS = [
    {
        "name": "clickup_list_accounts",
        "description": "List the configured ClickUp accounts managed by this gateway. Returns account id and whether it is the default, WITHOUT exposing API tokens. Use this to discover the 'account' values you can pass to the other clickup tools.",
        "inputSchema": {"type": "object", "properties": {}},
    },
    {
        "name": "clickup_list_workspaces",
        "description": "List ClickUp Workspaces (teams) accessible to the account (id, name, members_count, members with id/username/email). Start here to discover team_id and assignee IDs.",
        "inputSchema": {"type": "object", "properties": {"account": _ACCOUNT}},
    },
    {
        "name": "clickup_get_user",
        "description": "Get the ClickUp user that owns the API token (id, username, email). Use the id as assignees when creating tasks.",
        "inputSchema": {"type": "object", "properties": {"account": _ACCOUNT}},
    },
    {
        "name": "clickup_list_team_members",
        "description": "List workspace members (id, username, email) to resolve assignee IDs for task creation.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "team_id": {"type": "string", "description": "Workspace (team) ID. Omit to list members of all accessible workspaces."},
                "account": _ACCOUNT,
            },
        },
    },
    {
        "name": "clickup_list_spaces",
        "description": "List Spaces in a Workspace. Needs team_id (see clickup_list_workspaces).",
        "inputSchema": {
            "type": "object",
            "properties": {
                "team_id": {"type": "string", "description": "Workspace (team) ID. Omit to use the account default if configured."},
                "archived": {"type": "boolean", "description": "Include archived spaces (default false)."},
                "account": _ACCOUNT,
            },
        },
    },
    {
        "name": "clickup_get_space",
        "description": "Get a single Space by id (name, statuses, privacy).",
        "inputSchema": {
            "type": "object",
            "properties": {"space_id": {"type": "string"}, "account": _ACCOUNT},
            "required": ["space_id"],
        },
    },
    {
        "name": "clickup_create_space",
        "description": "Create a Space in a Workspace. IMPORTANT: Ask the user for explicit confirmation before creating.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "team_id": {"type": "string"},
                "name": {"type": "string"},
                "color": {"type": "string"},
                "private": {"type": "boolean"},
                "account": _ACCOUNT,
            },
            "required": ["name"],
        },
    },
    {
        "name": "clickup_update_space",
        "description": "Update a Space (name, color, private, archived). IMPORTANT: Ask the user for explicit confirmation before modifying.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "space_id": {"type": "string"},
                "name": {"type": "string"},
                "color": {"type": "string"},
                "private": {"type": "boolean"},
                "archived": {"type": "boolean"},
                "account": _ACCOUNT,
            },
            "required": ["space_id"],
        },
    },
    {
        "name": "clickup_delete_space",
        "description": "Delete a Space. IMPORTANT: Ask the user for explicit confirmation before deleting.",
        "inputSchema": {
            "type": "object",
            "properties": {"space_id": {"type": "string"}, "account": _ACCOUNT},
            "required": ["space_id"],
        },
    },
    {
        "name": "clickup_list_folders",
        "description": "List Folders in a Space (each with its lists).",
        "inputSchema": {
            "type": "object",
            "properties": {
                "space_id": {"type": "string", "description": "Space ID (see clickup_list_spaces)."},
                "archived": {"type": "boolean"},
                "account": _ACCOUNT,
            },
            "required": ["space_id"],
        },
    },
    {
        "name": "clickup_create_folder",
        "description": "Create a Folder in a Space. IMPORTANT: Ask the user for explicit confirmation before creating.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "space_id": {"type": "string"},
                "name": {"type": "string"},
                "account": _ACCOUNT,
            },
            "required": ["space_id", "name"],
        },
    },
    {
        "name": "clickup_list_lists",
        "description": "List Lists: pass folder_id (lists inside a Folder) OR space_id (folderless lists directly under the Space).",
        "inputSchema": {
            "type": "object",
            "properties": {
                "folder_id": {"type": "string"},
                "space_id": {"type": "string"},
                "archived": {"type": "boolean"},
                "account": _ACCOUNT,
            },
        },
    },
    {
        "name": "clickup_get_list",
        "description": "Get a single List by id.",
        "inputSchema": {
            "type": "object",
            "properties": {"list_id": {"type": "string"}, "account": _ACCOUNT},
            "required": ["list_id"],
        },
    },
    {
        "name": "clickup_create_list",
        "description": "Create a List under a Folder (folder_id) or directly under a Space (space_id). IMPORTANT: Ask the user for explicit confirmation before creating.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "name": {"type": "string"},
                "folder_id": {"type": "string"},
                "space_id": {"type": "string"},
                "content": {"type": "string"},
                "account": _ACCOUNT,
            },
            "required": ["name"],
        },
    },
    {
        "name": "clickup_update_list",
        "description": "Update a List (name, content, status, archived). IMPORTANT: Ask the user for explicit confirmation before modifying.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "list_id": {"type": "string"},
                "name": {"type": "string"},
                "content": {"type": "string"},
                "status": {"type": "string"},
                "archived": {"type": "boolean"},
                "account": _ACCOUNT,
            },
            "required": ["list_id"],
        },
    },
    {
        "name": "clickup_delete_list",
        "description": "Delete a List. IMPORTANT: Ask the user for explicit confirmation before deleting.",
        "inputSchema": {
            "type": "object",
            "properties": {"list_id": {"type": "string"}, "account": _ACCOUNT},
            "required": ["list_id"],
        },
    },
    {
        "name": "clickup_list_tasks",
        "description": "List tasks in a List (id, name, status, due_date as Unix ms, time_estimate as ms, priority, assignees, assignee_ids, url). Up to 100 per page.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "list_id": {"type": "string"},
                "page": {"type": "integer", "description": "Page number (default 0)."},
                "include_closed": {"type": "boolean", "description": "Include closed tasks (default true)."},
                "subtasks": {"type": "boolean", "description": "Include subtasks (default true)."},
                "archived": {"type": "boolean"},
                "account": _ACCOUNT,
            },
            "required": ["list_id"],
        },
    },
    {
        "name": "clickup_get_task",
        "description": "Get a single task by id (full details: description, custom fields, subtasks, url).",
        "inputSchema": {
            "type": "object",
            "properties": {"task_id": {"type": "string"}, "account": _ACCOUNT},
            "required": ["task_id"],
        },
    },
    {
        "name": "clickup_create_task",
        "description": "Create a task in a List. If assignees is omitted, the server auto-assigns it to the token owner. IMPORTANT: Ask the user for explicit confirmation before creating.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "list_id": {"type": "string"},
                "name": {"type": "string", "description": "Task title (required)."},
                "description": {"type": "string"},
                "status": {"type": "string", "description": "Status name valid in the List (e.g. 'to do')."},
                "priority": {"type": "integer", "description": "1=urgent, 2=high, 3=normal, 4=low."},
                "assignees": {"type": "array", "items": {"type": "integer"}, "description": "User IDs to assign."},
                "tags": {"type": "array", "items": {"type": "string"}},
                "due_date": {"type": "integer", "description": "Due date as Unix timestamp in milliseconds."},
                "due_date_time": {"type": "boolean"},
                "time_estimate": {"type": "integer", "description": "Time estimate in milliseconds."},
                "parent": {"type": "string", "description": "Parent task id to create a subtask."},
                "account": _ACCOUNT,
            },
            "required": ["list_id", "name"],
        },
    },
    {
        "name": "clickup_update_task",
        "description": "Update a task (name, description, status, priority, due_date, assignees, archived). IMPORTANT: Ask the user for explicit confirmation before modifying.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "task_id": {"type": "string"},
                "name": {"type": "string"},
                "description": {"type": "string"},
                "status": {"type": "string"},
                "priority": {"type": "integer", "description": "1=urgent, 2=high, 3=normal, 4=low."},
                "due_date": {"type": "integer", "description": "Due date as Unix timestamp in milliseconds."},
                "time_estimate": {"type": "integer"},
                "parent": {"type": "string"},
                "archived": {"type": "boolean"},
                "assignees": {"type": "object", "description": "{\"add\": [user_ids], \"rem\": [user_ids]}"},
                "account": _ACCOUNT,
            },
            "required": ["task_id"],
        },
    },
    {
        "name": "clickup_delete_task",
        "description": "Delete a task. IMPORTANT: Ask the user for explicit confirmation before deleting.",
        "inputSchema": {
            "type": "object",
            "properties": {"task_id": {"type": "string"}, "account": _ACCOUNT},
            "required": ["task_id"],
        },
    },
    {
        "name": "clickup_list_task_comments",
        "description": "List comments on a task (id, text, author, date, resolved, assignee, reply_count). The API returns 25 per page (newest first); when a page is full the response includes 'next_page' with the 'start' (ms timestamp) + 'start_id' to request the next one.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "task_id": {"type": "string"},
                "start": {"type": "integer", "description": "Pagination: ms timestamp of the last comment of the previous page (use together with 'start_id'; take both from the 'next_page' hint)."},
                "start_id": {"type": "string", "description": "Pagination: id of the last comment of the previous page (use together with 'start')."},
                "account": _ACCOUNT,
            },
            "required": ["task_id"],
        },
    },
    {
        "name": "clickup_create_task_comment",
        "description": "Add a comment to a task (optionally assigning it to a user via 'assignee'). IMPORTANT: Ask the user for explicit confirmation before commenting.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "task_id": {"type": "string"},
                "comment_text": {"type": "string"},
                "notify_all": {"type": "boolean"},
                "assignee": {"type": "integer", "description": "User id to assign the comment to (see clickup_list_team_members)."},
                "account": _ACCOUNT,
            },
            "required": ["task_id", "comment_text"],
        },
    },
    {
        "name": "clickup_update_task_comment",
        "description": "Edit a comment (needs the comment id from clickup_list_task_comments): change 'comment_text', reassign it ('assignee') or mark it as 'resolved' (requires the comment to have an assignee). ClickUp's PUT returns an empty body: pass 'task_id' to get the updated comment back. IMPORTANT: Ask the user for explicit confirmation before modifying.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "comment_id": {"type": "string"},
                "comment_text": {"type": "string"},
                "assignee": {"type": "integer", "description": "User id to assign the comment to."},
                "resolved": {"type": "boolean", "description": "True marks the comment as resolved."},
                "task_id": {"type": "string", "description": "Optional: task id to return the updated comment state."},
                "account": _ACCOUNT,
            },
            "required": ["comment_id"],
        },
    },
    {
        "name": "clickup_delete_task_comment",
        "description": "Permanently delete a comment (needs the comment id from clickup_list_task_comments). IMPORTANT: Ask the user for explicit confirmation before deleting.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "comment_id": {"type": "string"},
                "account": _ACCOUNT,
            },
            "required": ["comment_id"],
        },
    },
]
