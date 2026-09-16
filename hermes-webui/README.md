# 💬 Hermes WebUI — Community Web Client for Hermes Agent

Lightweight, Hermes-native web chat ([nesquena/hermes-webui](https://github.com/nesquena/hermes-webui), MIT, community project — not affiliated with Nous Research): Claude-style 3-panel layout (sessions sidebar, chat, workspace file browser), 1:1 parity with the Hermes CLI, tool-call cards, session projects/tags, light/dark mode, password auth, mobile responsive.

It runs the Hermes agent **in-process**, reading the same `~/.hermes` state (config, providers, memory, sessions) as the CLI, gateway, and dashboard — no extra setup, no extra model keys.

---

## 🚀 Setup

### 1. Configure Environment
```bash
cp .env.example .env
chmod 600 .env
nano .env
```
* `HERMES_WEBUI_PASSWORD=` — blank on first start = strong password auto-generated and stored back into `.env`. **Never expose it without a password.**
* `HERMES_HOME_DIR` — agent state dir (same one the CLI/gateway/dashboard use).
* `HERMES_WORKSPACE_DIR` — file-browser workspace (created if missing).
* `HERMES_WEBUI_DOMAIN` — public domain served by nginx (`chat.*`).

### 2. Start
```bash
./scripts/start.sh
```
Waits for `/health`, then prints the local + public URLs and where the password lives.

### 3. Expose via Nginx
Point your chat domain at the container (loopback only, no public ports):
```bash
# chat.jeisson.top -> hermes-webui:8787 (keep client_max_body_size for attachments;
# do NOT add proxy basic-auth — it breaks the PWA service-worker updates)
```
Then open `https://chat.jeisson.top` and sign in with `HERMES_WEBUI_PASSWORD`.

---

## 🛑 Stop / Status

```bash
./scripts/stop.sh    # docker compose down
./scripts/status.sh  # container status + /health check
```

## 🔄 Update

```bash
docker compose pull hermes-webui && ./scripts/start.sh
```
(Pins float on `latest`; session/state lives in `~/.hermes`, never in the image.)
