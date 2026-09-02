# Helper inserted into every Passbolt tool schema so agents can select which
# vault account to operate on when more than one is configured.
_ACCOUNT_SCHEMA = {
    "type": "string",
    "description": "Nombre/alias de la cuenta Passbolt a usar (por ejemplo 'principal', 'rodrigo'). "
                   "Omitir para usar la cuenta principal por defecto. Si solo hay una cuenta, esta se usa automáticamente."
}

PASSBOLT_TOOLS = [
    {
        "name": "passbolt_search_resources",
        "description": "Search Passbolt password manager credentials and resources by name, username, URL domain, or keyword. Returns matching items with their IDs and metadata WITHOUT exposing plaintext passwords in the search list.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Search query keyword, resource name, username, or URL (e.g. 'postgres', 'aws', 'github.com', 'admin')."
                },
                "folder_id": {
                    "type": "string",
                    "description": "Optional folder UUID to search within a specific directory."
                },
                "limit": {
                    "type": "integer",
                    "description": "Maximum number of results to return (default: 20)."
                },
                "account": _ACCOUNT_SCHEMA
            }
        }
    },
    {
        "name": "passbolt_get_secret",
        "description": "Retrieve and decrypt full credentials for a specific Passbolt resource UUID. Returns the decrypted password, username, URL, description, live TOTP code (if configured), and custom fields.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "resource_id": {
                    "type": "string",
                    "description": "The unique UUID of the Passbolt resource to decrypt."
                },
                "account": _ACCOUNT_SCHEMA
            },
            "required": ["resource_id"]
        }
    },
    {
        "name": "passbolt_create_resource",
        "description": "Create a new password/credential resource in Passbolt vault with client-side OpenPGP encryption. IMPORTANT: Always ask the user for explicit confirmation before creating a new credential.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "name": {
                    "type": "string",
                    "description": "The title or name for the credential (e.g., 'Production PostgreSQL Database')."
                },
                "password": {
                    "type": "string",
                    "description": "The secret password or API key to store."
                },
                "username": {
                    "type": "string",
                    "description": "Optional username or login email associated with the credential."
                },
                "uri": {
                    "type": "string",
                    "description": "Optional URL, host, or connection string (e.g., 'https://app.example.com')."
                },
                "description": {
                    "type": "string",
                    "description": "Optional notes or description."
                },
                "folder_id": {
                    "type": "string",
                    "description": "Optional folder UUID where the credential should be placed."
                },
                "totp_secret": {
                    "type": "string",
                    "description": "Optional TOTP 2FA secret key or otpauth:// URI."
                },
                "custom_fields": {
                    "type": "object",
                    "description": "Optional custom key-value pairs or additional metadata."
                },
                "account": _ACCOUNT_SCHEMA
            },
            "required": ["name", "password"]
        }
    },
    {
        "name": "passbolt_update_resource",
        "description": "Update an existing credential resource in Passbolt vault. Re-encrypts secret data and metadata using OpenPGP. IMPORTANT: Always ask the user for explicit confirmation before modifying credentials.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "resource_id": {
                    "type": "string",
                    "description": "The unique UUID of the resource to update."
                },
                "name": {
                    "type": "string",
                    "description": "New title or name for the credential."
                },
                "password": {
                    "type": "string",
                    "description": "New password to set (omit to keep unchanged)."
                },
                "username": {
                    "type": "string",
                    "description": "New username or login email."
                },
                "uri": {
                    "type": "string",
                    "description": "New URL or host."
                },
                "description": {
                    "type": "string",
                    "description": "New description or notes."
                },
                "folder_id": {
                    "type": "string",
                    "description": "Move credential to this folder UUID."
                },
                "totp_secret": {
                    "type": "string",
                    "description": "New TOTP secret or otpauth:// URI."
                },
                "custom_fields": {
                    "type": "object",
                    "description": "Updated custom fields dictionary."
                },
                "account": _ACCOUNT_SCHEMA
            },
            "required": ["resource_id"]
        }
    },
    {
        "name": "passbolt_delete_resource",
        "description": "Delete a credential resource from Passbolt vault. IMPORTANT: Always ask the user for explicit confirmation before deleting any credential.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "resource_id": {
                    "type": "string",
                    "description": "The unique UUID of the resource to delete."
                },
                "account": _ACCOUNT_SCHEMA
            },
            "required": ["resource_id"]
        }
    },
    {
        "name": "passbolt_list_folders",
        "description": "List accessible folders and directory hierarchy in Passbolt.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "parent_id": {
                    "type": "string",
                    "description": "Optional parent folder UUID to inspect subfolders. Omit to list root folders."
                },
                "account": _ACCOUNT_SCHEMA
            }
        }
    },
    {
        "name": "passbolt_create_folder",
        "description": "Create a new folder in Passbolt vault. IMPORTANT: Ask the user for confirmation before creating new folders.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "name": {
                    "type": "string",
                    "description": "Name of the new folder."
                },
                "parent_id": {
                    "type": "string",
                    "description": "Optional parent folder UUID to create a subfolder."
                },
                "account": _ACCOUNT_SCHEMA
            },
            "required": ["name"]
        }
    },
    {
        "name": "passbolt_list_accounts",
        "description": "List the configured Passbolt accounts (vaults) managed by this gateway. Use this to discover the 'account' values you can pass to the other passbolt tools. Returns account id, whether it is the default, the user email and server, WITHOUT exposing secrets.",
        "inputSchema": {
            "type": "object",
            "properties": {}
        }
    }
]
