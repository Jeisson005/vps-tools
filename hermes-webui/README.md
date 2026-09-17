# 💬 Hermes WebUI Sofia — Community Web Client for Hermes Agent (host-native)

Lightweight, Hermes-native web chat ([nesquena/hermes-webui](https://github.com/nesquena/hermes-webui), MIT, community project — not affiliated with Nous Research): Claude-style 3-panel layout (sessions sidebar, chat, workspace file browser), tool-call cards, session projects/tags, light/dark mode, password auth, mobile responsive.

It runs the Hermes agent **in-process as the host user**, reading the same `~/.hermes` state (config, providers, memory, sessions) as the CLI, gateway, and dashboard — no extra setup, no extra model keys.

> **Host-native, no Docker.** The service runs via systemd as `jeisson` on loopback `127.0.0.1:8787`, using the Hermes agent venv as its interpreter — so the webchat has the exact same hands as Telegram/WhatsApp/CLI: desktop `:1` + `cua-driver`, `steel-session`, `docker`, host MCP (`127.0.0.1:8005`) and Steel (`127.0.0.1:3000`). External behavior is unchanged: `https://chat.jeisson.top` via nginx.
>
> **Display name:** the assistant is branded **Sofia** (server-only: `HERMES_WEBUI_BOT_NAME` in `.env` + `bot_name` in `~/.hermes/webui/settings.json` + static title/manifest patch in the host checkout — see `scripts/update.sh`; none of it is committed).

---

## 🚀 Setup

### 1. Configure Environment
```bash
cp .env.example .env
chmod 600 .env
nano .env
```
* `HERMES_WEBUI_PASSWORD=` — blank on first install = strong password auto-generated and stored back into `.env`. **Never expose it without a password.**
* `HERMES_WEBUI_BOT_NAME=` — display name (this server: `Sofia`).
* `HERMES_WEBUI_DOMAIN=` — public domain served by nginx (`chat.*`).

### 2. Install (pinned upstream source + systemd unit)
```bash
sudo bash scripts/install.sh [--version exp-v0.52.314]
```
Clones `nesquena/hermes-webui` to `~/hermes-webui` at the pinned tag, renders `templates/hermes-webui.service` to `/etc/systemd/system`, enables and starts it.

### 3. Expose via Nginx
`chat.jeisson.top` proxies to the host loopback (see `nginx/conf.d/chat.jeisson.top.https.conf`):
```
proxy_pass http://host.docker.internal:8787;  # keep client_max_body_size for attachments;
# do NOT add proxy basic-auth — it breaks the PWA service-worker updates
```
Then open `https://chat.jeisson.top` and sign in with `HERMES_WEBUI_PASSWORD`.

---

## 🛑 Start / Stop / Status

```bash
bash scripts/start.sh    # systemctl start + /health wait
bash scripts/stop.sh     # systemctl stop
bash scripts/status.sh   # unit status + /health + runtime (user, DISPLAY, X11, tools)
```

## 🔄 Update

```bash
sudo bash scripts/update.sh [--version exp-v0.52.314]
```
Fetches upstream, checks out the pinned tag, **re-applies the Sofia branding** (server-only), and restarts the service.
