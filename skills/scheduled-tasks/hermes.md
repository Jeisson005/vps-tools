---
name: scheduled-tasks
description: "Schedule, create, and manage self-healing background tasks and cron jobs on the VPS using Sentinel MCP/CLI. Supports Python, Bash, and Node.js with git versioning, .env secrets, Docker isolation, and Steel Browser Human-in-the-Loop."
version: 2.1.0
author: VPS Tools
license: MIT
metadata:
  tags: [scheduled-tasks, cron, tasks, recurring, automation, sentinel, autoheal, hermes, self-healing, git, steel, hitl, docker]
  category: automation
  related_skills: [browser-automation, passbolt-credentials]
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
2. **Secrets & Environment Variables:** Pass sensitive API keys or credentials in `.env` files with `chmod 600`.
3. **Docker & Dependencies Isolation Rule:**
   - If a script requires heavy or specialized system dependencies (e.g. `ffmpeg`, `pandas`, custom browser drivers, external database clients, or microservices), **use Docker or Docker Compose by default** inside the task directory (e.g. `docker run --rm -v $(pwd):/app ...` or a local `docker-compose.yml`).
   - This ensures full portability and prevents dependency pollution on the host VPS.
4. **Browser Automation Tasks:**
   - If the task interacts with web pages or portals, use Steel Browser persistent endpoint (`ws://127.0.0.1:3000/?apiKey=...`).
   - If a 2FA checkpoint or Captcha is expected, import `sentinel-hitl` to pause and send the interactive session to **🟢 Bot 4 (HITL)**.
