---
name: scheduled-tasks
description: "Schedule, create, and manage self-healing background tasks and cron jobs on the VPS using Sentinel MCP/CLI. Supports Python, Bash, and Node.js with git versioning, .env secrets, Docker isolation, and Steel Browser Human-in-the-Loop."
version: 2.7.0
author: VPS Tools
license: MIT
metadata:
  tags: [scheduled-tasks, cron, tasks, recurring, automation, sentinel, autoheal, opencode, self-healing, git, steel, hitl, docker]
  category: automation
  related_skills: [browser-automation, passbolt-credentials, messaging-platforms]
---

# Scheduled Tasks & Background Automation Skill (OpenCode)

Teaches OpenCode how to create, inspect, and manage autonomous scheduled tasks on the VPS with **zero-overhead runtime**, **git change tracking**, and **automatic OpenCode self-healing loops**.

---

## 🛠️ MCP Tools Reference

When connected to the Sentinel MCP server (`http://127.0.0.1:8006/sse`):

* **`sentinel_create_task(name, description, schedule_cron, language, script_code, env_vars, requires_browser)`**:
  Registers and schedules a new polyglot task in Sentinel. Automatically initializes a dedicated git repo in `sentinel/tasks/<task_id>/` and updates the isolated crontab.
* **`sentinel_list_tasks()`**:
  Lists all active scheduled tasks, schedules, runtimes, and git versions.
* **`sentinel_run_task(task_id)`**:
  Triggers immediate manual execution with full error classification and self-healing.
* **`sentinel_update_task(task_id, name, schedule_cron, script_code, env_vars)`**:
  Updates code, secrets, or schedule.
* **`sentinel_delete_task(task_id)`**:
  Removes a task from crontab and archives it.
* **`sentinel_get_task_logs(task_id, lines)`**:
  Retrieves execution logs and recent git commit history.

---

## 📋 Rules for Authoring New Scheduled Tasks

Whenever the user asks to *"programar una tarea"*, *"crear un cron"*, *"sincronizar periódicamente"* or *"automatizar un script diario/semanal"*:

1. **Do NOT write raw crontab lines via bash pipes.** Always use the MCP tool `sentinel_create_task` or the CLI `sentinel-ctl add`.
2. **`description` es obligatoria:** deriva 1-3 frases del pedido original del usuario (qué debe hacer, para qué sirve, criterio de éxito). Se guarda en `task.json` + `TASK.md` y se inyecta al clasificador IA y al prompt de auto-heal para no romper la intención. Si el usuario solo dice "avísame cuando X", el criterio de éxito es notificar solo en match, etc.
2. **Secrets & Environment Variables:** Pass sensitive API keys or credentials in the `env_vars` parameter so Sentinel isolates them in a `chmod 600 .env` file inside the task folder.
3. **Docker & Dependencies Isolation Rule:**
   - If a script requires heavy or specialized system dependencies (e.g. `ffmpeg`, `pandas`, custom browser drivers, external database clients, or microservices), **use Docker or Docker Compose by default** inside the task directory (e.g. `docker run --rm -v $(pwd):/app ...` or a local `docker-compose.yml`).
   - This ensures full portability and prevents dependency pollution on the host VPS.
4. **Browser Automation Tasks:**
   - If the task interacts with web pages or portals, set `requires_browser: true`.
   - Use Playwright connecting to Steel Browser persistent endpoint (`ws://127.0.0.1:3000/?apiKey=...`).
   - If a 2FA checkpoint or Captcha is expected, import `sentinel-hitl` to pause and send the interactive session to **🟢 Bot 4 (HITL)**:
     ```python
     # Example snippet in Python tasks:
     from sentinel_hitl import wait_for_user
     
     if page.locator("text=Ingresa tu código 2FA").is_visible():
         live_url = f"https://{os.environ['STEEL_DOMAIN']}/v1/sessions/debug?sessionId={session_id}"
         approved = wait_for_user(session_id, live_url, task_name="Consulta Facturación", reason="2FA Bancario")
      if not approved:
              sys.exit(2) # Clean pause on timeout
      ```
5. **User communication service integrations:**
   - If the task needs to **notify, query, or send** via **WhatsApp, Telegram, email (Gmail/Outlook), or Google Workspace**, use that platform's **gateway MCP services** (`whatsapp_*`, `telegram_*`, `google_*`, `outlook_*`) instead of scraping or inventing calls.
   - For **user notifications**, prefer **Telegram** (via MCP or the agent's native bot).
   - Check the **`messaging-platforms`** skill for correct usage (confirm before sending, history tone, etc.).
6. **Event-driven tasks (communication watchers):** When the user asks for *"when X arrives via channel Y with feature Z"* (e.g., "when I get an email from X", "when I'm mentioned in group A"):
   - Create a **scheduled** task that runs every **N** minutes (whichever the user indicates; default **5**).
   - Use the **channel's MCP** to read what's new: `whatsapp_get_history`/`whatsapp_get_messages`, `telegram_get_messages`, `google_gmail_list`, `outlook_mail_list`.
   - Keep a **cursor** (last seen `id`/timestamp) to process only new items and avoid duplicate alerts.
   - Validate the criterion (sender, mention, keyword) and **notify** (preferably via **Telegram**) only on match. It's a **frequent** task (cron), not a foreground service.
7. **Decide yourself whether to reuse an existing watcher:** Before creating a new task that watches a channel, check `sentinel_list_tasks` and **judge**:
   - **Reuse/extend** (`sentinel_update_task`) when the new criterion shares the **same channel, compatible cadence, and data** (e.g., another filter on the same mailbox or group).
   - **Create a separate task** when the required **cadence/latency** changes (e.g., every 5 min vs. daily), the **recipient or severity**, the **secrets**, or if merging criteria would tangle the logic.
   - When in doubt, prefer small readable tasks; avoid pointless polling duplication, but don't force a merge that complicates the task.
8. **One-off AI calls in tasks (never ask the user for keys):** If a task needs a very specific AI call
   (summarize, classify, draft), use the gateway's **`ai_complete`** MCP tool: **`api_key`/`model`/`base_url`
   are already configured** on the gateway (`MCP_AI_BASE_URL`, `MCP_AI_API_KEY`, `MCP_AI_MODEL`) — **never ask
   the user for AI keys**. From a script, call the MCP `/ai` endpoint with the gateway `MCP_API_KEY`, or
   use `litellm` reading those same vars. Keep the call minimal; don't use AI for deterministic things.
9. **🔔 Notification bots and how your scripts get credentials:**
   - Use the right bot instead of inventing sends:
     - **Routine bot** (`TELEGRAM_BOT_ROUTINE_TOKEN`): **the one you may use** for informational alerts, summaries, and watcher matches.
     - **HITL bot** (`TELEGRAM_BOT_HITL_TOKEN`): **only** interactive checkpoints (2FA/captcha) via `sentinel-hitl` (see rule 4); never as an alert channel.
   - Your alert destination is **`TELEGRAM_CHAT_ID`** (shared/admin chat).
   - **How does the script get the credentials?** Without asking the user anything: include them in `env_vars` when creating the task (`TELEGRAM_BOT_ROUTINE_TOKEN` — and HITL only for checkpoints — plus `TELEGRAM_CHAT_ID`); they arrive as `chmod 600` `.env`. Or import `sentinel/core/telegram_hub.py` (`TelegramHub.send_routine`, with automatic fallback between bots) if running inside the Sentinel tree.
   - Direct send: `POST https://api.telegram.org/bot<TOKEN>/sendMessage` with `chat_id` + `text`.
   - **Never print or log tokens** in logs, answers, or commits — not even the routine one.

---

## 🔍 Hybrid error classification v2.7 (how failures are routed)

`core/classifier.py` is Tier 0 regex + exit-codes (offline, zero-cost), Tier 1 AI referee (env-gated, only ambiguous cases):

* `transient` → routine bot, retry next cycle (timeouts, 502/503/504, 429, DNS). Selector timeouts NEVER count here (guard).
* `hitl_required` → urgent bot with HITL helper hint, NO code repair. Scripts must `sys.exit(2)` on HITL timeout = clean pause (no heal, no spam; Bot 4 already notified).
* `human_required` → urgent bot (401/403, invalid/expired token, suspended, billing). Update Passbolt/`.env`.
* `infra` (new) → urgent bot with runbook (`df -h`, `free -h`, `docker ps`), NO code repair (disk full, OOM 137, docker down, 127 command not found).
* `repairable` → OpenCode headless auto-repair with rich prompt (language, requires_browser, classification, fix_hint), git commit on success / rollback on fail, rate-limited (`MAX_REPAIR_ATTEMPTS`, reminder 12-24h).
* Exit codes: `0`=ok, `2`=HITL pause, `124`=timeout→transient, `137`=OOM→infra, `126/127`→infra.
* AI referee: reutiliza la IA del panel MCP (`principal` deepseek) vía gateway local `127.0.0.1:8005` sin pedir keys ni duplicarlas (`SENTINEL_AI_*` solo es fallback si el MCP cae; `SENTINEL_AI_ENABLED=false` lo desactiva). Incluye `description`/objetivo en el contexto. Secrets are redacted before the call, 20s timeout, invalid JSON falls back to regex. Never use AI for deterministic Tier 0 hits.

## 🩺 Protocol for OpenCode When Invoked by AutoHeal

When OpenCode is invoked in headless mode (`opencode run --auto-approve`) to auto-repair a broken task:
1. **Analyze Root Cause:** Read the error context provided (STDOUT/STDERR) plus classification (`repairable`, reason, fix_hint), task language, `requires_browser`, and file list. Inspect the files in the current task directory.
2. **Apply Minimal, Robust Fix:** Fix the code (e.g. adjust DOM selector with explicit waits, handle null value, fix type casting). Never touch `.env`, never print secrets, keep script executable. If a heavy dep is missing use Docker inside the task dir. If you find 2FA/Captcha, wire `sentinel_hitl.wait_for_user` + `sys.exit(2)` instead of masking it.
3. **Provide Plain-Language Summary:** In your final response, include a line starting with:
   `EXPLICACION_RESUMIDA: <Explicación sencilla y no técnica de lo que se solucionó>`
