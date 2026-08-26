# Hermes Agent (Nous Research)

Autonomous AI agent environment with both an interactive Terminal CLI and a Web Dashboard (React + Vite + FastAPI) developed by Nous Research.

## Requirements
- Ubuntu 22.04+ / Debian 12+
- Python 3.11+ (managed via `uv`)
- Node.js 20+
- `ripgrep`, `ffmpeg`, `build-essential`

## Structure
- `templates/hermes-dashboard.service` — Systemd service unit template for the Web Dashboard.
- `scripts/install.sh` — Native installation, build, and Systemd registration script.
- `scripts/start.sh` — Start Web Dashboard service.
- `scripts/stop.sh` — Stop Web Dashboard service.
- `scripts/status.sh` — Check status of CLI and Web Dashboard.
- `.env.example` — Configuration template.

## Installation
1. Copy `.env.example` to `.env`:
   ```bash
   cp .env.example .env
   ```
2. Edit `.env` with your preferred user, credentials, and ports.
3. Run the installer with sudo:
   ```bash
   sudo ./scripts/install.sh
   ```

## Usage
### Terminal CLI
- Run setup wizard to configure API keys:
  ```bash
  hermes setup
  ```
- Start an interactive chat session:
  ```bash
  hermes chat
  ```
- Check system diagnostics:
  ```bash
  hermes doctor
  ```

### Web Dashboard
- Accessible by default on port `9119` (or reverse proxied via Nginx at `https://agent.yourdomain.top/`).
- Includes chat UI, sessions manager, models selector, skills manager, and environment configurations.
