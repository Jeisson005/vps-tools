# Hermes AI Agent (Nous Research)

Hermes Agent is a powerful, autonomous AI agent framework with Web Dashboard, CLI, and multi-platform messaging capabilities (Telegram, Discord, Slack, WhatsApp).

---

## 1. Quick Installation

1. Copy `.env.example` to `.env` and set your credentials:
```bash
cd vps-tools/hermes
cp .env.example .env
nano .env
```

2. Run the automated installer:
```bash
sudo bash scripts/install.sh
```

---

## 2. Services Architecture

Hermes runs two systemd background services:
1. **`hermes-dashboard.service`**: Web UI dashboard running on port `9119` (FastAPI + React 19).
2. **`hermes-gateway.service`**: Messaging gateway listening for Telegram / Discord incoming messages via long polling.

---

## 3. Telegram Integration

1. Get a Bot Token from [@BotFather](https://t.me/BotFather) on Telegram.
2. In `.env`:
   - Set `TELEGRAM_BOT_TOKEN=your_token`
   - Set `TELEGRAM_ALLOWED_USERS=your_telegram_username` (e.g. `jeisson`)
3. Restart the gateway service:
```bash
bash scripts/start.sh
```

---

## 4. Service Management

```bash
# Check status of both Dashboard and Gateway
bash scripts/status.sh

# Start services
bash scripts/start.sh

# Stop services
bash scripts/stop.sh

# Safely update Hermes and re-apply custom patches
bash scripts/update.sh
```

---

## 5. Updates & Patch Management

Hermes Agent is cloned directly from upstream Nous Research. To support seamless integration with other `vps-tools` components (Steel Browser, Open WebUI), `vps-tools` maintains targeted patches:
* **`api_server.py`**: Routes intermediate execution narration to OpenAI `reasoning_content` so Open WebUI renders it in the collapsible "Thinking" dropdown.
* **`browser_tool.py`**: Preserves custom CDP ports when discovering remote Steel browser endpoints.

To ensure upstream updates never corrupt files or break silently, `scripts/update.sh` and `scripts/patch-hermes.py`:
1. Stash any temporary changes before pulling from upstream.
2. Validate AST and signature blocks before applying patches.
3. If upstream Nous Research modifies those functions in a new release, an explicit warning `[!] [WARNING]` is emitted instead of forcing a broken patch.
4. Automatically rebuild the dashboard frontend and reload services.
