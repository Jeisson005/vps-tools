# OpenCode AI (CLI & Web Interface)

Open-source, terminal-native & web-based AI coding assistant with multi-model support (Claude, OpenAI, Gemini, Ollama), MCP tools, and LSP code intelligence.

---

## 1. Quick Installation

1. Copy `.env.example` to `.env` and set your credentials:
```bash
cd vps-tools/opencode
cp .env.example .env
nano .env
```

2. Run the automated installer:
```bash
sudo bash scripts/install.sh
```

---

## 2. Model Context Protocol (MCP) Servers

The installer automatically installs and configures:
- **`brave-search`** (`@brave/brave-search-mcp-server`): Real-time web search capabilities for queries and up-to-date documentation.
- **`playwright`** (`@playwright/mcp`): Browser automation and testing capabilities with headless Chromium.

To verify connected MCP servers:
```bash
opencode mcp list
```

---

## 3. Access & Usage

### Web Interface
- **URL**: Accessible via your domain (e.g., `https://opencode.your-domain.com` or `https://chat.your-domain.com`).
- **Authentication**: Uses HTTP Basic Auth configured in `.env` (`OPENCODE_SERVER_USERNAME` and `OPENCODE_SERVER_PASSWORD`).
- **Persistence**: Managed by systemd as `opencode-web.service` (auto-starts on boot).

### Terminal / CLI
```bash
# Open directory and start AI interactive assistant
cd /path/to/project
opencode

# Connect custom LLM provider keys
/connect
```

---

## 4. Service Management

```bash
# Check status
bash scripts/status.sh

# Start service
bash scripts/start.sh

# Stop service
bash scripts/stop.sh
```
