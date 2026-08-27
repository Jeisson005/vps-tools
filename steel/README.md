# Steel Browser Sandbox (AI Agent Infrastructure)

Production-ready, batteries-included browser sandbox designed for AI agents and web automation with REST API, Chrome DevTools Protocol (CDP), and Live Session Viewer (Human-in-the-Loop).

---

## 1. Quick Installation

1. Copy `.env.example` to `.env`:
```bash
cd vps-tools/steel
cp .env.example .env
nano .env
```

2. Run the automated installer:
```bash
bash scripts/install.sh
```

---

## 2. Ports & Architecture

- **Port `3000` (HTTP & WebSocket)**: Steel REST API, session management, and Live Interactive UI (`/v1/sessions`, `/ui`).
- **Port `9223` (WebSocket)**: Chrome DevTools Protocol (CDP) router endpoint.
- **Resource Limits**: 2.5 GB RAM limit, `shm_size: 2gb`, `cap_add: [SYS_ADMIN]`.

---

## 3. Usage Examples

### REST API (Create a Session)
```bash
curl -X POST http://127.0.0.1:3000/v1/sessions \
  -H "x-steel-api-key: YOUR_STEEL_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"useProxy": false}'
```

### Response contains:
- `id`: Session UUID.
- `websocketUrl`: Full CDP WebSocket URL for Playwright / Puppeteer.
- `sessionViewerUrl`: Interactive web link for human-in-the-loop inspection and manual intervention.

### Connecting with Playwright (Python / Node.js)
```python
from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    # Connect directly to Steel Browser CDP
    browser = p.chromium.connect_over_cdp("ws://127.0.0.1:9223?apiKey=YOUR_STEEL_API_KEY")
    page = browser.new_page()
    page.goto("https://example.com")
    print(page.title())
    browser.close()
```

---

## 4. Lifecycle Management

```bash
# Check status
bash scripts/status.sh

# Run automated session test
bash scripts/test_session.sh

# Start container
bash scripts/start.sh

# Stop container
bash scripts/stop.sh
```
