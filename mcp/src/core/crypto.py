import os
import base64
import hashlib
from typing import Optional
from cryptography.fernet import Fernet

_fernet_instance: Optional[Fernet] = None

def _get_or_create_master_key() -> bytes:
    """Derive or load a 32-byte Fernet key."""
    env_key = os.environ.get("MCP_MASTER_KEY", "").strip()
    
    if env_key:
        # Hash user-provided string to ensure valid 32-byte urlsafe base64 key
        digest = hashlib.sha256(env_key.encode("utf-8")).digest()
        return base64.urlsafe_b64encode(digest)
    
    # Check if a persistent key file exists in data dir
    data_dir = os.environ.get("MCP_DATA_DIR", "/app/data")
    os.makedirs(data_dir, exist_ok=True)
    key_file = os.path.join(data_dir, ".master_key")
    
    if os.path.exists(key_file):
        try:
            with open(key_file, "rb") as f:
                stored = f.read().strip()
                if len(stored) == 44:  # Fernet key standard length
                    return stored
        except Exception:
            pass

    # Generate a fresh key and persist it locally
    fresh_key = Fernet.generate_key()
    try:
        with open(key_file, "wb") as f:
            f.write(fresh_key)
        os.chmod(key_file, 0o600)
    except Exception:
        pass
        
    return fresh_key

def get_fernet() -> Fernet:
    global _fernet_instance
    if _fernet_instance is None:
        key = _get_or_create_master_key()
        _fernet_instance = Fernet(key)
    return _fernet_instance

def encrypt_value(raw: Optional[str]) -> str:
    """Encrypt a sensitive string into ciphertext."""
    if not raw:
        return ""
    try:
        f = get_fernet()
        return f.encrypt(raw.encode("utf-8")).decode("utf-8")
    except Exception as e:
        # If encryption fails, fallback to raw or raise
        return raw

def decrypt_value(cipher: Optional[str]) -> str:
    """Decrypt a ciphertext back into plain string."""
    if not cipher:
        return ""
    try:
        f = get_fernet()
        return f.decrypt(cipher.encode("utf-8")).decode("utf-8")
    except Exception:
        # Value might not have been encrypted yet (e.g. initial import)
        return cipher
