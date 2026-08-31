"""
Sentinel Configuration Loader
Loads settings from .env with fallback defaults.
"""
import os
from pathlib import Path
from typing import Optional

BASE_DIR = Path(__file__).resolve().parent.parent
TASKS_DIR = BASE_DIR / "tasks"
CRON_DIR = BASE_DIR / "cron"
LOGS_DIR = BASE_DIR / "logs"

# Ensure essential directories exist
TASKS_DIR.mkdir(parents=True, exist_ok=True)
CRON_DIR.mkdir(parents=True, exist_ok=True)
LOGS_DIR.mkdir(parents=True, exist_ok=True)


def load_env_file(filepath: Path) -> dict:
    env_vars = {}
    if not filepath.is_file():
        return env_vars
    with open(filepath, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            k = k.strip()
            v = v.strip().strip("'\"")
            env_vars[k] = v
    return env_vars


# Load base Sentinel .env
_env_path = BASE_DIR / ".env"
_env_vars = load_env_file(_env_path) if _env_path.exists() else load_env_file(BASE_DIR / ".env.example")


class Settings:
    # 🔴 Bot 1: Urgent (Action Required / Broken Tasks)
    BOT_URGENT_TOKEN: str = os.getenv("TELEGRAM_BOT_URGENT_TOKEN", _env_vars.get("TELEGRAM_BOT_URGENT_TOKEN", _env_vars.get("TELEGRAM_BOT_TOKEN", "")))
    
    # 🟡 Bot 2: Routine (Info / Autofixes / Transient warnings / Reminders)
    BOT_ROUTINE_TOKEN: str = os.getenv("TELEGRAM_BOT_ROUTINE_TOKEN", _env_vars.get("TELEGRAM_BOT_ROUTINE_TOKEN", ""))
    
    # 🔵 Bot 3: Hermes Username (For Inline Deep-link Buttons)
    BOT_HERMES_USERNAME: str = os.getenv("TELEGRAM_BOT_HERMES_USERNAME", _env_vars.get("TELEGRAM_BOT_HERMES_USERNAME", "")).lstrip("@")
    
    # 🟢 Bot 4: Human-in-the-Loop (2FA / CAPTCHA Live Viewer)
    BOT_HITL_TOKEN: str = os.getenv("TELEGRAM_BOT_HITL_TOKEN", _env_vars.get("TELEGRAM_BOT_HITL_TOKEN", ""))
    
    # Target Telegram Chat ID (Shared or primary user)
    TELEGRAM_CHAT_ID: str = os.getenv("TELEGRAM_CHAT_ID", _env_vars.get("TELEGRAM_CHAT_ID", ""))
    
    # Server & Engine Settings
    SENTINEL_PORT: int = int(os.getenv("SENTINEL_PORT", _env_vars.get("SENTINEL_PORT", _env_vars.get("CENTINELA_PORT", "8006"))))
    SENTINEL_HOST: str = os.getenv("SENTINEL_HOST", _env_vars.get("SENTINEL_HOST", _env_vars.get("CENTINELA_HOST", "0.0.0.0")))
    SENTINEL_API_KEY: str = os.getenv("SENTINEL_API_KEY", _env_vars.get("SENTINEL_API_KEY", _env_vars.get("CENTINELA_API_KEY", "")))
    
    # Self-Healing & Rate Limits
    MAX_REPAIR_ATTEMPTS: int = int(os.getenv("MAX_REPAIR_ATTEMPTS", _env_vars.get("MAX_REPAIR_ATTEMPTS", "2")))
    REMINDER_INTERVAL_HOURS: int = int(os.getenv("REMINDER_INTERVAL_HOURS", _env_vars.get("REMINDER_INTERVAL_HOURS", "12")))
    HITL_TIMEOUT_MINUTES: int = int(os.getenv("HITL_TIMEOUT_MINUTES", _env_vars.get("HITL_TIMEOUT_MINUTES", "15")))
    
    # Steel Browser & Host
    STEEL_DOMAIN: str = os.getenv("STEEL_DOMAIN", _env_vars.get("STEEL_DOMAIN", "browser.localhost"))
    OPENCODE_BIN: str = os.getenv("OPENCODE_BIN", _env_vars.get("OPENCODE_BIN", "/usr/local/bin/opencode"))


settings = Settings()
