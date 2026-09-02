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
        
        # Multi-instance service accounts (e.g. multiple Passbolt accounts)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS service_instances (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                service_id TEXT NOT NULL,
                instance_id TEXT NOT NULL,
                name TEXT DEFAULT '',
                enabled INTEGER NOT NULL DEFAULT 1,
                is_default INTEGER NOT NULL DEFAULT 0,
                config_json TEXT NOT NULL DEFAULT '{}',
                encrypted_secrets_json TEXT NOT NULL DEFAULT '{}',
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE (service_id, instance_id)
            );
        """)
        
        # Graceful migration for DBs created before the `name` column existed.
        cursor.execute("PRAGMA table_info(service_instances)")
        existing_cols = {row[1] for row in cursor.fetchall()}
        if "name" not in existing_cols:
            cursor.execute("ALTER TABLE service_instances ADD COLUMN name TEXT DEFAULT ''")
        
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

def get_service_instances(service_id: str) -> List[Dict[str, Any]]:
    """List all accounts/instances for a service (secrets decrypted)."""
    init_db()
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT instance_id, name, enabled, is_default, config_json, encrypted_secrets_json "
            "FROM service_instances WHERE service_id = ? ORDER BY is_default DESC, id ASC",
            (service_id,)
        )
        rows = cursor.fetchall()
        instances = []
        for r in rows:
            config = json.loads(r["config_json"] or "{}")
            encrypt_secrets = json.loads(r["encrypted_secrets_json"] or "{}")
            secrets = {k: decrypt_value(v) for k, v in encrypt_secrets.items()}
            instances.append({
                "instance_id": r["instance_id"],
                "name": r["name"] or "",
                "enabled": bool(r["enabled"]),
                "is_default": bool(r["is_default"]),
                "config": config,
                "secrets": secrets,
            })
        return instances


def get_service_instance(service_id: str, instance_id: str) -> Optional[Dict[str, Any]]:
    """Retrieve a single service instance (secrets decrypted) or None."""
    for inst in get_service_instances(service_id):
        if inst["instance_id"] == instance_id:
            return inst
    return None


def save_service_instance(
    service_id: str,
    instance_id: str,
    enabled: bool,
    config: Dict[str, Any],
    secrets: Dict[str, str],
    is_default: bool = False,
    name: str = "",
):
    """Create or update a service instance, encrypting secrets. Optionally mark it default."""
    init_db()
    encrypted_secrets = {k: encrypt_value(v) for k, v in secrets.items() if v}
    with get_connection() as conn:
        cursor = conn.cursor()
        if is_default:
            cursor.execute(
                "UPDATE service_instances SET is_default = 0 WHERE service_id = ? AND is_default = 1",
                (service_id,)
            )
        cursor.execute("""
            INSERT INTO service_instances
                (service_id, instance_id, name, enabled, is_default, config_json, encrypted_secrets_json, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
            ON CONFLICT(service_id, instance_id) DO UPDATE SET
                name = excluded.name,
                enabled = excluded.enabled,
                is_default = excluded.is_default,
                config_json = excluded.config_json,
                encrypted_secrets_json = excluded.encrypted_secrets_json,
                updated_at = CURRENT_TIMESTAMP
        """, (
            service_id,
            instance_id,
            name or "",
            1 if enabled else 0,
            1 if is_default else 0,
            json.dumps(config),
            json.dumps(encrypted_secrets),
        ))
        conn.commit()


def delete_service_instance(service_id: str, instance_id: str):
    """Delete a service instance."""
    init_db()
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "DELETE FROM service_instances WHERE service_id = ? AND instance_id = ?",
            (service_id, instance_id)
        )
        conn.commit()


def ensure_default_instance(service_id: str, config: Dict[str, Any], secrets: Dict[str, str]):
    """Guarantee a default instance exists for a service (used for seeding)."""
    instances = get_service_instances(service_id)
    if instances:
        return
    save_service_instance(service_id, "primary", True, config, secrets, is_default=True)


def migrate_legacy_service_to_instances(service_id: str) -> bool:
    """Move a legacy single service row into a default instance (returns True if migrated)."""
    if get_service_instances(service_id):
        return False
    legacy = get_service_config(service_id)
    if not legacy:
        return False
    save_service_instance(
        service_id,
        "primary",
        legacy["enabled"],
        legacy["config"],
        legacy["secrets"],
        is_default=True,
    )
    return True


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
