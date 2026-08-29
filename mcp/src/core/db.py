import os
import json
import sqlite3
from typing import Dict, Any, Optional, List
from .crypto import encrypt_value, decrypt_value

def get_db_path() -> str:
    data_dir = os.environ.get("MCP_DATA_DIR", "/app/data")
    os.makedirs(data_dir, exist_ok=True)
    return os.path.join(data_dir, "mcp.db")

def get_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(get_db_path(), timeout=10.0)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode = WAL;")
    conn.execute("PRAGMA synchronous = NORMAL;")
    return conn

def init_db():
    """Create database tables if they do not exist."""
    with get_connection() as conn:
        cursor = conn.cursor()
        
        # Services configuration
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS services_config (
                service_id TEXT PRIMARY KEY,
                enabled INTEGER NOT NULL DEFAULT 1,
                config_json TEXT NOT NULL DEFAULT '{}',
                encrypted_secrets_json TEXT NOT NULL DEFAULT '{}',
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)
        
        # Gateway global settings
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS gateway_settings (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)
        
        # Lightweight audit and activity log (capped)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS activity_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                service TEXT NOT NULL,
                action TEXT NOT NULL,
                status TEXT NOT NULL,
                details TEXT DEFAULT ''
            );
        """)
        
        conn.commit()

def get_service_config(service_id: str) -> Optional[Dict[str, Any]]:
    """Retrieve full configuration for a service, decrypting secrets."""
    init_db()
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT service_id, enabled, config_json, encrypted_secrets_json, updated_at FROM services_config WHERE service_id = ?",
            (service_id,)
        )
        row = cursor.fetchone()
        if not row:
            return None
        
        config = json.loads(row["config_json"] or "{}")
        encrypted_secrets = json.loads(row["encrypted_secrets_json"] or "{}")
        
        # Decrypt secrets
        decrypted_secrets = {}
        for k, v in encrypted_secrets.items():
            decrypted_secrets[k] = decrypt_value(v)
            
        return {
            "service_id": row["service_id"],
            "enabled": bool(row["enabled"]),
            "config": config,
            "secrets": decrypted_secrets,
            "updated_at": row["updated_at"]
        }

def save_service_config(service_id: str, enabled: bool, config: Dict[str, Any], secrets: Dict[str, str]):
    """Save service config, encrypting secrets."""
    init_db()
    # Encrypt all secrets
    encrypted_secrets = {}
    for k, v in secrets.items():
        if v:  # Only encrypt non-empty strings
            encrypted_secrets[k] = encrypt_value(v)
            
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO services_config (service_id, enabled, config_json, encrypted_secrets_json, updated_at)
            VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)
            ON CONFLICT(service_id) DO UPDATE SET
                enabled = excluded.enabled,
                config_json = excluded.config_json,
                encrypted_secrets_json = excluded.encrypted_secrets_json,
                updated_at = CURRENT_TIMESTAMP;
        """, (service_id, 1 if enabled else 0, json.dumps(config), json.dumps(encrypted_secrets)))
        conn.commit()

def get_setting(key: str, default: str = "") -> str:
    init_db()
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT value FROM gateway_settings WHERE key = ?", (key,))
        row = cursor.fetchone()
        if row:
            return row["value"]
    return default

def set_setting(key: str, value: str):
    init_db()
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO gateway_settings (key, value, updated_at)
            VALUES (?, ?, CURRENT_TIMESTAMP)
            ON CONFLICT(key) DO UPDATE SET
                value = excluded.value,
                updated_at = CURRENT_TIMESTAMP;
        """, (key, value))
        conn.commit()

def log_activity(service: str, action: str, status: str, details: str = ""):
    try:
        init_db()
        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO activity_log (service, action, status, details)
                VALUES (?, ?, ?, ?)
            """, (service, action, status, details[:500]))
            
            # Prune logs beyond 1000 entries to maintain minimal disk footprint
            cursor.execute("DELETE FROM activity_log WHERE id NOT IN (SELECT id FROM activity_log ORDER BY id DESC LIMIT 1000)")
            conn.commit()
    except Exception:
        pass

def get_recent_activity(limit: int = 50) -> List[Dict[str, Any]]:
    init_db()
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT id, timestamp, service, action, status, details
            FROM activity_log
            ORDER BY id DESC
            LIMIT ?
        """, (limit,))
        rows = cursor.fetchall()
        return [dict(r) for r in rows]
