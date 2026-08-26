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
```
