---
name: steel-browser
description: "Cloud/local browser automation via Steel Browser sandbox: isolated scraping, persistent user sessions, and proactive live session viewing for Captchas/2FA/Human-in-the-loop."
version: 1.0.0
author: VPS Tools
license: MIT
metadata:
  hermes:
    tags: [browser, steel, automation, scraping, playwright, cdp, live-viewer, 2fa, captcha]
    category: browser
    related_skills: [visual-session-control, computer-use]
---

# Steel Browser Skill

Automates and controls web browsing inside the sandboxed **Steel Browser** container with built-in live streaming, isolated testing, and persistent user profile capabilities.

## 🧭 Decision Matrix: Which Browser Mode to Use

The user will usually not specify technical terms. You must autonomously choose the correct flow:

### 1. Isolated Mode (Ephemeral / Clean Browsing)
* **When to use:** Testing websites, frontend development, public data scraping, verifying links, security inspection, checking website uptime.
* **How to run:**
  ```bash
  steel-session create "<url>"
  # Or via Playwright MCP:
  steel-mcp --isolated
  ```
* **Behavior:** Fresh in-memory session. No cookies or cache are persisted after the session is released.

### 2. Persistent Mode (User Identity & Saved Logins)
* **When to use:** Accessing user accounts, SaaS portals (GitHub, AWS, Google, CRM), social media, banking, utility bills, or multi-step tasks where cookies and session tokens must be preserved across prompts.
* **How to run:**
  ```bash
  steel-mcp --user-data-dir ~/.config/steel/profiles/persistent --shared-browser-context
  ```
* **Behavior:** All cookies, `localStorage`, and session states are safely retained in `/home/jeisson/.config/steel/profiles/persistent`.

### 3. User GUI Desktop (KasmVNC on `DISPLAY=:1`)
* **When to use:** Only when the user explicitly asks to interact with their real visible desktop or open a browser on their graphical monitor (`https://desktop.jeisson.top`).
* **Skill to use:** Load the `visual-session-control` skill.

---

## 🔴 Proactive Live Viewer & Human-in-the-Loop Protocol

Whenever you are interacting via Telegram, Discord, or the Hermes Web Dashboard:

### Scenarios Requiring Live Links:
1. **User Request:** The user asks to "see", "watch", or "give me the live link".
2. **Security Obstacles:** Cloudflare Turnstile, reCAPTCHA, hCaptcha, or bot detection checkpoints.
3. **Authentication:** Two-Factor Authentication (2FA / OTP codes), SMS verification, or sensitive passwords.
4. **Interactive Actions:** Payment gateways, signature pads, or complex manual confirmations.

### Protocol Steps:
1. Launch the interactive live session:
   ```bash
   steel-session create "<url>"
   ```
2. Extract the `liveViewerUrl` from the output (e.g. `https://{{STEEL_DOMAIN}}/v1/sessions/debug?sessionId=<ID>`).
3. Send the link directly to the user with clear instructions:
   > *"He abierto la sesión en vivo en tu navegador: [Enlace del Visor]. Por favor resuelve el Captcha / 2FA en esa pestaña y avísame cuando esté listo para continuar."*
4. Wait for user confirmation before executing subsequent steps.
5. When the entire workflow is finished, release the session:
   ```bash
   steel-session release <sessionId>
   ```
