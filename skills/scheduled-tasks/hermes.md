---
name: scheduled-tasks
description: "Schedule, create, and manage self-healing background tasks and cron jobs on the VPS using Sentinel MCP/CLI. Supports Python, Bash, and Node.js with git versioning, .env secrets, Docker isolation, and Steel Browser Human-in-the-Loop."
version: 2.7.0
author: VPS Tools
license: MIT
metadata:
  tags: [scheduled-tasks, cron, tasks, recurring, automation, sentinel, autoheal, hermes, self-healing, git, steel, hitl, docker]
  category: automation
  related_skills: [browser-automation, passbolt-credentials, messaging-platforms]
---

# Scheduled Tasks & Background Automation Skill (Hermes)

Teaches Hermes how to create, inspect, modify, and troubleshoot autonomous scheduled tasks managed by Sentinel on the Linux VPS.

---

## 🛠️ MCP Tools & CLI Commands

Hermes can manage Sentinel tasks via MCP or CLI commands:

### CLI Commands:
* `sentinel-ctl list`: Lists all active scheduled tasks, schedules, and git commit versions.
* `sentinel-ctl run <task_id>`: Triggers on-demand execution with auto-healing.
* `sentinel-ctl logs <task_id> -n 50`: Shows stdout/stderr and recent git auto-repair history.
* `sentinel-ctl remove <task_id>`: Removes task from the scheduled crontab.

---

## 📋 Rules for Authoring New Scheduled Tasks

Whenever the user asks to *"programar una tarea"*, *"crear un cron"*, *"sincronizar periódicamente"* or *"automatizar un script diario/semanal"*:

1. **Do NOT write raw crontab lines via bash pipes.** Always use Sentinel tooling.
2. **`description` obligatoria:** 1-3 frases del pedido original (qué hace, para qué, criterio de éxito). Vive en `task.json` + `TASK.md` y guía al auto-heal.
2. **Secrets & Environment Variables:** Pass sensitive API keys or credentials in `.env` files with `chmod 600`.
3. **Docker & Dependencies Isolation Rule:**
   - If a script requires heavy or specialized system dependencies (e.g. `ffmpeg`, `pandas`, custom browser drivers, external database clients, or microservices), **use Docker or Docker Compose by default** inside the task directory (e.g. `docker run --rm -v $(pwd):/app ...` or a local `docker-compose.yml`).
   - This ensures full portability and prevents dependency pollution on the host VPS.
4. **Browser Automation Tasks:**
   - If the task interacts with web pages or portals, use Steel Browser persistent endpoint (`ws://127.0.0.1:3000/?apiKey=...`).
   - If a 2FA checkpoint or Captcha is expected, import `sentinel-hitl` to pause and send the interactive session to **🟢 Bot 4 (HITL)**.

5. **User communication service integrations:**
   - If the task needs to **notify, query, or send** via **WhatsApp, Telegram, email (Gmail/Outlook), or Google Workspace**, use that platform's **gateway MCP services** (`whatsapp_*`, `telegram_*`, `google_*`, `outlook_*`) instead of scraping or inventing calls.
   - For **user notifications**, prefer **Telegram** (via MCP or the agent's native bot).
   - Check the **`messaging-platforms`** skill for correct usage (confirm before sending, history tone, etc.).

6. **Event-driven tasks (communication watchers):** When the user asks for something like *"when X arrives via channel Y with feature Z"* (e.g., "when I get an email from X", "when I'm mentioned in group A", "when a WhatsApp from B arrives"):
   - Create a **scheduled** task that runs every **N** minutes (whichever the user indicates; default **5**).
   - Inside, use the **channel's MCP** to read what's new: `whatsapp_get_history`/`whatsapp_get_messages`, `telegram_get_messages`, `google_gmail_list`, `outlook_mail_list`.
   - Keep a **cursor** (last seen `id`/timestamp) to process **only new items** and avoid duplicate alerts.
   - Validate the criterion (sender, mention, keyword) and **notify** (preferably via **Telegram**) only on match.
   - It's a **frequent** task (cron), not a foreground service running indefinitely.

7. **Decide yourself whether to reuse an existing watcher:** Before creating a new task that watches a channel, check `sentinel-ctl list` and **judge**:
   - **Reuse/extend** (`sentinel-ctl update` / `sentinel_update_task`) when the new criterion shares the **same channel, compatible cadence, and data** (e.g., another filter on the same mailbox or group).
   - **Create a separate task** when the required **cadence/latency** changes (e.g., every 5 min vs. daily), the **recipient or severity** of the alert, the **secrets** needed, or if merging criteria would tangle the logic.
   - When in doubt, prefer small readable tasks; avoid pointless polling duplication, but don't force a merge that complicates the task.

8. **One-off AI calls in tasks (never ask the user for keys):** If a task needs a very specific AI call
   (summarize, classify, draft), use the gateway's **`ai_complete`** MCP tool: **`api_key`/`model`/`base_url`
   are already configured** on the gateway (`MCP_AI_BASE_URL`, `MCP_AI_API_KEY`, `MCP_AI_MODEL`) — **never ask
   the user for AI keys**. From a Sentinel script, call the MCP `/ai` endpoint with the gateway `MCP_API_KEY`,
   or if you prefer `litellm`, read those same vars. Keep the call minimal; don't use AI for deterministic things.

9. **🔔 Notification bots and how your scripts get credentials:**
   - Use the right bot instead of inventing sends:
     - **Routine bot** (`TELEGRAM_BOT_ROUTINE_TOKEN`): **the one you may use** for informational alerts, summaries, and watcher matches.
     - **HITL bot** (`TELEGRAM_BOT_HITL_TOKEN`): **only** interactive checkpoints (2FA/captcha) via `sentinel-hitl` (see rule 4); never as an alert channel.
   - Your alert destination is **`TELEGRAM_CHAT_ID`** (shared/admin chat).
   - **How does the script get the credentials?** Without asking the user anything:
     1. **Recommended:** include them in `env_vars` when creating the task (`TELEGRAM_BOT_ROUTINE_TOKEN` — and HITL only for checkpoints — plus `TELEGRAM_CHAT_ID`); they arrive as `chmod 600` `.env` inside the task folder.
     2. If the script runs inside the Sentinel tree, you may import `sentinel/core/telegram_hub.py` (`TelegramHub.send_routine`, with automatic fallback between bots).
   - Direct send (if not using the hub): `POST https://api.telegram.org/bot<TOKEN>/sendMessage` with `chat_id` + `text` (+ `parse_mode`).
    - **Never print or log tokens** in logs, answers, or commits — not even the routine one.

## 🔍 Hybrid error classification v2.7

Failures route to 5 categories: `transient` (retry), `hitl_required` (exit 2 clean pause, no repair), `human_required` (Passbolt/`.env`), `infra` (host runbook `df -h`/`free -h`/`docker ps`, no code repair), `repairable` (OpenCode auto-repair, git commit/rollback, rate-limited). AI referee reutiliza la IA del panel MCP sin keys extra (opt-out `SENTINEL_AI_ENABLED=false`) y recibe el objetivo de la tarea.
