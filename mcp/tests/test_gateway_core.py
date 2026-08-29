import os
import sys
import tempfile
import asyncio

# Ensure src is importable
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.core.crypto import encrypt_value, decrypt_value
from src.core.schema_cleaner import sanitize_tool_definition, sanitize_tools_list_response
from src.core.db import init_db, save_service_config, get_service_config, log_activity, get_recent_activity
from src.core.mcp_protocol import McpProtocolHandler
from src.core.registry import registry

def test_crypto():
    secret = "my_super_secret_gpg_passphrase_123!"
    cipher = encrypt_value(secret)
    assert cipher != secret, "Ciphertext should not equal plaintext"
    decrypted = decrypt_value(cipher)
    assert decrypted == secret, f"Expected {secret}, got {decrypted}"
    print("[PASS] Crypto encrypt/decrypt cycle OK")

def test_schema_cleaner():
    raw_tool = {
        "name": "test_tool",
        "description": "A tool with draft-07 and problematic keywords",
        "$schema": "http://json-schema.org/draft-07/schema#",
        "additionalProperties": False,
        "inputSchema": {
            "$schema": "http://json-schema.org/draft-07/schema#",
            "type": "object",
            "additionalProperties": False,
            "properties": {
                "field1": {
                    "anyOf": [{"type": "string"}, {"type": "null"}],
                    "description": "A union type"
                },
                "field2": {
                    "type": "integer"
                }
            }
        },
        "outputSchema": {"type": "string"}
    }
    cleaned = sanitize_tool_definition(raw_tool, strip_output_schema=True)
    assert "$schema" not in cleaned, "$schema should be stripped from tool root"
    assert "outputSchema" not in cleaned, "outputSchema should be stripped"
    assert "additionalProperties" not in cleaned["inputSchema"], "additionalProperties should be stripped"
    assert cleaned["inputSchema"]["type"] == "object"
    assert cleaned["inputSchema"]["properties"]["field1"]["type"] == "string", "anyOf should be collapsed to string"
    print("[PASS] Schema cleaner sanitization OK")

def test_db_and_registry():
    with tempfile.TemporaryDirectory() as tmpdir:
        os.environ["MCP_DATA_DIR"] = tmpdir
        init_db()
        
        # Test saving and loading config with secrets
        save_service_config("passbolt", True, {"base_url": "https://passbolt.test"}, {"passphrase": "secret-pass"})
        loaded = get_service_config("passbolt")
        assert loaded is not None
        assert loaded["enabled"] is True
        assert loaded["config"]["base_url"] == "https://passbolt.test"
        assert loaded["secrets"]["passphrase"] == "secret-pass"

        log_activity("passbolt", "test_action", "success", "All good")
        logs = get_recent_activity(10)
        assert len(logs) >= 1
        assert logs[0]["action"] == "test_action"

        # Test registry
        registry.initialize()
        services = registry.list_services_status()
        assert any(s["id"] == "passbolt" for s in services)
        print("[PASS] DB persistence and Registry OK")

async def test_protocol():
    with tempfile.TemporaryDirectory() as tmpdir:
        os.environ["MCP_DATA_DIR"] = tmpdir
        init_db()
        registry.initialize()

        handler = McpProtocolHandler(scope="passbolt")
        
        # Test initialize
        init_req = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {"protocolVersion": "2024-11-05"}
        }
        res, sid = await handler.handle_request(init_req)
        assert res["result"]["protocolVersion"] == "2024-11-05"
        assert "serverInfo" in res["result"]

        # Test tools/list
        tools_req = {
            "jsonrpc": "2.0",
            "id": 2,
            "method": "tools/list",
            "params": {}
        }
        tools_res, _ = await handler.handle_request(tools_req)
        assert "tools" in tools_res["result"]
        print("[PASS] MCP Protocol JSON-RPC initialize & tools/list OK")

if __name__ == "__main__":
    test_crypto()
    test_schema_cleaner()
    test_db_and_registry()
    asyncio.run(test_protocol())
    print("\nALL CORE GATEWAY TESTS PASSED SUCCESSFULLY!")
