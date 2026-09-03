---
name: scheduled-tasks
description: "Schedule, create, and manage self-healing background tasks and cron jobs on the VPS using Sentinel MCP/CLI. Supports Python, Bash, and Node.js with git versioning, .env secrets, Docker isolation, and Steel Browser Human-in-the-Loop."
version: 2.5.1
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

7. **Decide tú si reutilizas un watcher existente:** Antes de crear una tarea nueva que vigile un canal, revisa `sentinel-ctl list` y **juzga con criterio**:
   - **Reutiliza/amplía** (`sentinel-ctl update` / `sentinel_update_task`) cuando el nuevo criterio comparta el **mismo canal, cadencia compatible y datos** (p. ej. otro filtro sobre la misma bandeja o grupo).
   - **Crea una tarea separada** cuando cambien la **cadencia/latencia** requerida (p. ej. cada 5 min vs. diario), el **destinatario o severidad** de la alerta, los **secretos** necesarios, o si fusionar criterios enredaría la lógica.
   - En caso de duda, prefiere tareas pequeñas y legibles; evita duplicar polling innecesario, pero no fuerces una fusión que complique la tarea.

8. **IA puntual en tareas (sin pedir claves al usuario):** Si una tarea necesita una llamada de IA muy concreta
   (resumir, clasificar, redactar), usa la tool MCP **`ai_complete`** del gateway: **la `api_key`/`model`/`base_url`
   ya están configuradas** en el gateway (`MCP_AI_BASE_URL`, `MCP_AI_API_KEY`, `MCP_AI_MODEL`) — **nunca preguntes
   al usuario por claves de IA**. Desde un script de Sentinel, llama al endpoint MCP `/ai` con la `MCP_API_KEY` del
   gateway, o si prefieres `litellm`, lee esas mismas vars. Mantén la llamada mínima; no uses IA para cosas
   deterministas.

9. **🔔 Bots de notificación y cómo obtienen credenciales tus scripts:**
   - Hay varios bots con rol distinto; usa el correcto en vez de inventar envíos:
     - **Bot 1 · Urgent** (`TELEGRAM_BOT_URGENT_TOKEN`): **reservado a la gestión interna de Sentinel** (fallos de tareas, auto-heal crítico). Ni tú ni tus tareas deben enviar por esta vía por su cuenta.
     - **Bot 2 · Routine** (`TELEGRAM_BOT_ROUTINE_TOKEN`): **el que sí puedes usar** para avisos informativos, resúmenes y coincidencias de watchers.
     - **Bot 4 · HITL** (`TELEGRAM_BOT_HITL_TOKEN`): **solo** checkpoints interactivos (2FA/captcha) vía `sentinel-hitl` (ver regla 4); jamás como canal de avisos.
     - **Bot 3 · Hermes** (`TELEGRAM_BOT_HERMES_USERNAME`): chat conversacional con el usuario; **tampoco** envíes alertas automáticas por esa vía salvo que el usuario lo pida expresamente.
   - El destino de tus avisos es **`TELEGRAM_CHAT_ID`** (chat compartido/admin).
   - **¿Cómo obtiene el script las credenciales?** Sin pedirle nada al usuario:
     1. **Recomendado:** inclúyelas en `env_vars` al crear la tarea (`TELEGRAM_BOT_ROUTINE_TOKEN` —y el HITL solo para checkpoints— más `TELEGRAM_CHAT_ID`); llegan como `.env` `chmod 600` dentro de la carpeta de la tarea.
     2. Si el script corre dentro del árbol de Sentinel, puedes importar `sentinel/core/telegram_hub.py` (`TelegramHub.send_routine`, con fallback entre bots).
   - Envío directo (si no usas el hub): `POST https://api.telegram.org/bot<TOKEN>/sendMessage` con `chat_id` + `text` (+ `parse_mode`).
   - **Nunca imprimas ni registres los tokens** en logs, respuestas o commits — ni siquiera el de rutina.
