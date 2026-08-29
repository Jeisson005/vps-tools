from typing import Dict, Any, List

PASSBOLT_TOOLS: List[Dict[str, Any]] = [
    {
        "name": "passbolt_search_resources",
        "description": "Search Passbolt password manager resources and credentials by name, URI, username, or keyword. Returns matching resource metadata and IDs WITHOUT exposing plaintext passwords.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Search query keyword, resource name, or URL domain (e.g. 'postgres', 'aws', 'github.com')."
                },
                "folder_id": {
                    "type": "string",
                    "description": "Optional folder UUID to restrict the search within a specific folder."
                },
                "limit": {
                    "type": "integer",
                    "description": "Maximum number of results to return (default: 20)."
                }
            }
        }
    },
    {
        "name": "passbolt_get_secret",
        "description": "Retrieve and decrypt the credentials/password for a specific Passbolt resource using its resource UUID. Call passbolt_search_resources first to find the relevant resource ID.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "resource_id": {
                    "type": "string",
                    "description": "The unique UUID of the Passbolt resource to decrypt."
                }
            },
            "required": ["resource_id"]
        }
    },
    {
        "name": "passbolt_list_folders",
        "description": "List accessible Passbolt folders and folder hierarchy to locate categorized credentials.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "parent_id": {
                    "type": "string",
                    "description": "Optional parent folder UUID to inspect subfolders. Omit to list root folders."
                }
            }
        }
    }
]
