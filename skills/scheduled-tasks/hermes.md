---
name: scheduled-tasks
description: "Schedule, create, and manage self-healing background tasks and cron jobs on the VPS using Sentinel MCP/CLI. Supports Python, Bash, and Node.js with git versioning, .env secrets, Docker isolation, and Steel Browser Human-in-the-Loop."
version: 2.3.0
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
2. **Secrets & Environment Variables:** Pass sensitive API keys or credentials in `.env` files with `chmod 600`.
3. **Docker & Dependencies Isolation Rule:**
   - If a script requires heavy or specialized system dependencies (e.g. `ffmpeg`, `pandas`, custom browser drivers, external database clients, or microservices), **use Docker or Docker Compose by default** inside the task directory (e.g. `docker run --rm -v $(pwd):/app ...` or a local `docker-compose.yml`).
   - This ensures full portability and prevents dependency pollution on the host VPS.
4. **Browser Automation Tasks:**
   - If the task interacts with web pages or portals, use Steel Browser persistent endpoint (`ws://127.0.0.1:3000/?apiKey=...`).
   - If a 2FA checkpoint or Captcha is expected, import `sentinel-hitl` to pause and send the interactive session to **🟢 Bot 4 (HITL)**.

5. **Integraciones con servicios de comunicación del usuario:**
   - Si la tarea necesita **avisar, consultar o enviar** por **WhatsApp, Telegram, correo (Gmail/Outlook) o Google Workspace**, usa los **servicios MCP del gateway** de esa plataforma (`whatsapp_*`, `telegram_*`, `google_*`, `outlook_*`) en lugar de scrapear o inventar llamadas.
   - Para **notificaciones al usuario**, prioriza **Telegram** (vía MCP o el bot nativo de Hermes).
   - Consulta la skill **`messaging-platforms`** para el uso correcto (confirmar antes de enviar, tono del historial, etc.).

6. **Tareas por eventos (watchers de comunicación):** Cuando el usuario pida algo como *"cuando llegue X por Y canal con Z característica"* (p. ej. "cuando me llegue un correo de X", "cuando me mencionen en el grupo A", "cuando llegue un WhatsApp de B"):
   - Crea una tarea **programada** que corra cada **N** minutos (el que indique el usuario; por defecto **5**).
   - Dentro, usa el **MCP del canal** para leer lo nuevo: `whatsapp_get_history`/`whatsapp_get_messages`, `telegram_get_messages`, `google_gmail_list`, `outlook_mail_list`.
   - Mantén un **cursor** (último `id`/timestamp visto) para procesar **solo lo nuevo** y no repetir avisos.
   - Valida el criterio (remitente, mención, palabra clave) y **notifica** (preferiblemente por **Telegram**) solo si matchea.
   - Es una tarea **frecuente** (cron), no un servicio en primer plano que corra indefinidamente.

7. **Reutiliza watchers existentes:** Antes de crear una tarea nueva que vigile un canal, revisa `sentinel-ctl list`. Si **ya existe una** que consulta ese mismo servicio, **amplíala/actualízala** (`sentinel-ctl update` / `sentinel_update_task`) para cubrir el nuevo criterio en vez de duplicar el polling (evita varias tareas llamando al mismo canal y carpetas de datos duplicadas).

8. **IA puntual en tareas:** Si una tarea necesita una llamada de IA muy concreta (resumir, clasificar, redactar una respuesta), usa **`litellm`** en el script. Pon la `api_key` (y, si aplica, `model` y `base_url`) en el `.env` de la tarea (regla de secretos). Mantén la llamada mínima y manejable (no uses IA para cosas triviales que el script pueda hacer determinista).
