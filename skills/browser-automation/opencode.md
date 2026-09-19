---
name: browser-automation
description: "Automate web browsing and testing via Steel Browser sandbox. Defaults to isolated/ephemeral sessions for development, with persistent profile fallback for logins, and proactive Live Viewer for Captchas/2FA."
version: 2.5.0
author: VPS Tools
license: MIT
metadata:
  tags: [browser, web, automation, scraping, testing, playwright, steel, live-viewer, 2fa, captcha]
  category: browser
  related_skills: [desktop-gui-control, passbolt-credentials]
---

# Browser Automation & Testing Skill (Steel Cloud Sandbox - OpenCode)

Controls web browsing, page testing, DOM inspection, scraping, and interactive live viewing inside the sandboxed **Steel Browser** container.

> **Endpoint (this VPS):** Steel API on port `3000` (`browser.jeisson.top`). Sessions are dynamic with unique UUIDs — never use a shared static port. OpenCode drives them via `steel-mcp --isolated` (ephemeral) or persistent profile (`~/.config/steel/profiles/persistent`).

> **♻️ Session lifecycle (leases):** there are **3 Steel workers, 1 session per worker (max 3 concurrent sessions)**. MCP sessions (`playwright` / `playwright-persistent`) hold an automatic lease/heartbeat: when you stop using the browser they are released on their own (~30 min of inactivity), and **the wrapper transparently recreates a session on the next tool call** (the `sessionId` changes — re-check `steel_get_session_info`). Sessions created with the `steel-session` CLI have **no lease** and are released after ~30 min without activity unless you pass `--ttl` and renew it. **Closing the Live Viewer tab does NOT release the session** — always release explicitly when you own it.

---

## 🧭 1. Autonomous Browser Mode Selection

### 🔒 Use `playwright` (Isolated / Incognito Mode) BY DEFAULT when:
- **Development & Debugging:** Testing locally hosted web apps, APIs, frontend layouts, inspecting DOM elements.
- **Stateless Web Scraping & Research:** Extracting public information, reading online documentation, verifying URLs.
- **Disposable Tasks:** Any operation where saving cookies, cache, or authentication state would pollute the user's profile.

### 💾 Use `playwright-persistent` (Stateful / Persistent Mode) ONLY when:
- **User Identity & Logins:** Logging into SaaS platforms (GitHub, AWS, Google, CRM), social media, or company portals.
- **Multi-Step Workflows:** Tasks where the user explicitly expects to stay logged in across multiple prompts, retaining cookies in `~/.config/steel/profiles/persistent`.

---

## 🔴 2. Proactive Live Session & Human-in-the-Loop Protocol

Provide the **Live Viewer URL** (`https://{{STEEL_DOMAIN}}/v1/sessions/debug?sessionId=<ID>`) in these scenarios:

### A. When the user asks for it:
- *"Déjame ver"*, *"muéstrame la pantalla"*, *"dame el link en vivo"*, *"quiero ver qué pasa"*.

### B. Proactively when Human Intervention is Required:
1. **Security Checkpoints & Captchas:** Cloudflare Turnstile, reCAPTCHA, hCaptcha, or bot detection.
2. **Two-Factor Authentication (2FA):** SMS codes, authenticator OTP prompts, hardware security keys.
3. **Sensitive Manual Authentication:** When the user prefers to type passwords or bank credentials directly.

### 🛠️ Execution Steps:

⚠️ **Multiple Steel sessions can be active at once** (other conversations, leftover persistent sessions, etc). Never guess a `sessionId` from `steel-session list` — it has no way to tell you which entry belongs to the browser you are currently driving.

**Case 1 — You are already navigating via the `playwright` / `playwright-persistent` MCP tools** (the common case: you started browsing normally and only now hit a captcha/2FA):
1. Call the `steel_get_session_info` tool (no arguments) on that same MCP connection. It returns the exact `sessionId`, `liveViewerUrl` and `cdpWsUrl` this connection is bound to — the one your browser_* calls have been driving all along.
2. If `success` is `false` (Steel API was unreachable at startup), you are on a local, non-shareable browser — tell the user a live link isn't available and offer `steel-session create` as a fresh alternative instead.

**Case 2 — You have not started navigating yet, or want a dedicated session for this specifically:**
1. Execute the system CLI tool:
   ```bash
   steel-session create "<url>" --ttl 1h
   ```
   (`--ttl` keeps the session alive for long human waits; without it the session is auto-released after ~30 min without activity. For very long waits renew with `steel-session heartbeat <id> --ttl 1h`.)
2. Parse the returned JSON to obtain `sessionId` and `liveViewerUrl`.

**Both cases then:**
3. Send the link to the user clearly:
   > *"He abierto la sesión en vivo en tu navegador: [Abrir Sesión en Vivo](https://{{STEEL_DOMAIN}}/v1/sessions/debug?sessionId=<SESSION_ID>)\nPor favor resuelve el Captcha / 2FA en esa pestaña y avísame cuando esté listo para continuar."*
4. **PAUSE** and wait for the user's confirmation before driving the subsequent steps.
5. When complete and only if you created a dedicated session in Case 2, release it to free RAM:
   ```bash
   steel-session release <sessionId>
   ```
   (In Case 1, do NOT release the session yourself — it belongs to your ongoing `playwright`/`playwright-persistent` MCP connection and is released automatically when that connection closes.)
