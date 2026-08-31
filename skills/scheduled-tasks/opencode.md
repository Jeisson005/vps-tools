---
name: scheduled-tasks
description: "Schedule, create, and manage self-healing background tasks and cron jobs on the VPS using Sentinel MCP/CLI. Supports Python, Bash, and Node.js with git versioning, .env secrets, Docker isolation, and Steel Browser Human-in-the-Loop."
version: 2.1.0
author: VPS Tools
license: MIT
metadata:
  tags: [scheduled-tasks, cron, tasks, recurring, automation, sentinel, autoheal, opencode, self-healing, git, steel, hitl, docker]
  category: automation
  related_skills: [browser-automation, passbolt-credentials]
---

# Scheduled Tasks & Background Automation Skill (OpenCode)

Teaches OpenCode how to create, inspect, and manage autonomous scheduled tasks on the VPS with **zero-overhead runtime**, **git change tracking**, and **automatic OpenCode self-healing loops**.

---

## 🛠️ MCP Tools Reference

When connected to the Sentinel MCP server (`http://127.0.0.1:8006/sse`):

* **`sentinel_create_task(name, schedule_cron, language, script_code, env_vars, requires_browser)`**:
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

---

## 🩺 Protocol for OpenCode When Invoked by AutoHeal

When OpenCode is invoked in headless mode (`opencode run --auto-approve`) to auto-repair a broken task:
1. **Analyze Root Cause:** Read the error context provided (STDOUT/STDERR) and inspect the files in the current task directory.
2. **Apply Minimal, Robust Fix:** Fix the code (e.g. adjust DOM selector, handle null value, fix type casting).
3. **Provide Plain-Language Summary:** In your final response, include a line starting with:
   `EXPLICACION_RESUMIDA: <Explicación sencilla y no técnica de lo que se solucionó>`
