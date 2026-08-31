# 🛡️ Sentinel - VPS Task Orchestration, Monitoring & Autonomous Self-Healing Suite

Sentinel is a lightweight, zero-overhead task orchestrator, monitoring engine, and autonomous self-healing suite for Linux VPS.

---

## 🚀 Key Features

* **Polyglot Task Runtime:** Runs Python, Bash, Node.js, and arbitrary executables with isolated `.env` secret management.
* **Git-Backed Change Tracking:** Every task maintains its own git repository. Changes made by the auto-healer are versioned; successful fixes are committed with friendly, non-technical explanations, while failed fixes are rolled back automatically (`git reset --hard HEAD`).
* **Intelligent Error Classification:**
  * **Transient Glitches:** Network timeouts, DNS blips, 502/503/504 errors, and 429 rate limits are categorized as transient: they do *not* modify code, trigger backoff retries, and notify the routine bot with schedule optimization suggestions.
  * **Autonomous Healing:** Logic bugs, syntax errors, and changed DOM selectors trigger an automated headless OpenCode repair loop (`opencode run --auto-approve`).
* **4-Bot Color-Coded Telegram Routing:**
  * 🔴 **Bot 1 (Urgent / Action Required):** Critical unhealed failures, broken tasks, or decisions requiring human authorization.
  * 🟡 **Bot 2 (Routine / Info):** Auto-reparations completed, transient notices, reminders every 12-24h (anti-spam), and system health suggestions.
  * 🔵 **Bot 3 (Hermes Agent):** Target of 1-click interactive inline buttons embedded in messages from Bot 1, Bot 2, and Bot 4.
  * 🟢 **Bot 4 (Human-in-the-Loop):** Manages interactive 2FA/CAPTCHA checkpoints during Steel Browser automation with live viewer links and callback buttons.
* **Internal MCP & REST Server:** Exposes Streamable HTTP / SSE JSON-RPC 2.0 (`/sse` and `/mcp`) on port `8006` for direct agent integration.
* **Isolated Crontab:** Maintains scheduled jobs in `sentinel/cron/sentinel.tab` without polluting or endangering the host crontab.

---

## ⚙️ Quick Setup

1. **Configure Environment:**
   ```bash
   cd vps-tools/sentinel
   cp .env.example .env
   nano .env
   ```

2. **Install and Start:**
   ```bash
   sudo bash scripts/install.sh
   ```

---

## 💻 CLI Commands

```bash
# List all managed scheduled tasks and their git versions
sentinel-ctl list

# Execute a task immediately with full self-healing
sentinel-ctl run <task_id>

# View recent execution logs and git repair history
sentinel-ctl logs <task_id> -n 50

# Remove a task from the scheduled crontab
sentinel-ctl remove <task_id>

# Run a script directly with auto-healing wrapper
sentinel-run --id my_task --path /path/to/script.py
```

---

## 🛠️ MCP Tools for AI Agents (OpenCode & Hermes)

When connected to `http://127.0.0.1:8006/sse`:

| Tool Name | Description |
| :--- | :--- |
| `sentinel_create_task` | Create and schedule a polyglot task with git tracking, secrets, and auto-healing. |
| `sentinel_list_tasks` | Inspect all scheduled tasks, schedules, runtimes, and statuses. |
| `sentinel_run_task` | Trigger immediate on-demand task run. |
| `sentinel_update_task` | Modify schedule, script code, or secrets. |
| `sentinel_delete_task` | Remove task from crontab. |
| `sentinel_get_task_logs` | Retrieve stdout/stderr logs and git repair commit history. |

---

## 🌐 Human-in-the-Loop (Steel Browser 2FA)

In Python scripts, import the helper to request 2FA authorization via **🟢 Bot 4**:

```python
from sentinel_hitl import wait_for_user
import sys, os

# If 2FA checkpoint is detected:
live_url = f"https://{os.environ['STEEL_DOMAIN']}/v1/sessions/debug?sessionId={session_id}"
approved = wait_for_user(
    session_id=session_id,
    session_url=live_url,
    task_name="Pago de Servicios",
    reason="Ingresar código 2FA del banco",
    timeout_minutes=15
)

if not approved:
    # Exits cleanly without false error alarms or spamming auto-healing
    sys.exit(2)
```

---

## 📊 Service Management

```bash
# Check service status
bash scripts/status.sh

# Start service
bash scripts/start.sh

# Stop service
bash scripts/stop.sh
```
