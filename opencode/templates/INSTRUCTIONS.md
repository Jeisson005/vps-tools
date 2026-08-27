# OpenCode Environment & Browser Capabilities

## 🌐 Browser Automation & Steel Browser Sandbox

This server has **Steel Browser** installed and integrated with OpenCode.

### Browser Tools Available:
1. **`playwright` MCP Tool:**
   - Isolated, in-memory browser session.
   - Ideal for web scraping, clean tests, and stateless browsing.
2. **`playwright-persistent` MCP Tool:**
   - Stateful browser session that preserves cookies, sessions, `localStorage`, and logins under `/home/jeisson/.config/steel/profiles/persistent`.
   - Ideal when the user asks to maintain a login or perform actions across multiple steps with the same session.

### 🔴 Live Browser Session Viewer (Human-in-the-Loop):
When the user asks for a **live link**, **live view**, or wants to **watch/interact with the browser in real-time**:
- You have the CLI tool `steel-session` available in the system:
  - Run `steel-session create "<url>"` to launch an interactive session and open the requested URL.
  - It will return a JSON object containing `liveViewerUrl` (e.g., `https://steel.jeisson.top/v1/sessions/debug?sessionId=...` or `https://browser.jeisson.top/...`).
  - Provide this link directly to the user so they can watch the session live and interact with the page (mouse/keyboard).
  - When finished, you can release the session with `steel-session release <sessionId>`.
