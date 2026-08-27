---
name: browser-automation
description: "Web browser automation, web scraping, logins, and live screen sessions via Steel Browser sandbox: isolated clean scraping, persistent user sessions, and proactive live interactive viewing for Captchas/2FA/Human-in-the-loop."
version: 2.0.0
author: VPS Tools
license: MIT
metadata:
  hermes:
    tags: [browser, web, automation, scraping, playwright, cdp, live-viewer, 2fa, captcha, navigation]
    category: browser
    related_skills: [desktop-gui-control]
---

# Browser Automation Skill (Web & Cloud Sandbox)

Automates and controls web browsing, web scraping, user authentication, and interactive live viewing inside the sandboxed **Steel Browser** container.

## 🧭 Autonomous Browser Mode Selection

The user will usually not specify technical terms like "isolated" or "persistent". Autonomously select the correct mode based on the user's task:

### 1. Isolated Mode (Ephemeral / Clean Browsing)
* **When to use:** Testing websites, frontend/API debugging, public web scraping, reading documentation, verifying links, checking site uptime.
* **How to run:**
  ```bash
  steel-session create "<url>"
  # Or via Playwright MCP:
  steel-mcp --isolated
  ```
* **Behavior:** Fresh in-memory session. No cookies, cache, or logins are stored after the session is released.

### 2. Persistent Mode (User Identity & Saved Logins)
* **When to use:** Accessing user accounts, SaaS portals (GitHub, AWS, Google, CRM), social media, banking, utility bills, or multi-step tasks where cookies and session tokens must be preserved across prompts.
* **How to run:**
  ```bash
  steel-mcp --user-data-dir ~/.config/steel/profiles/persistent --shared-browser-context
  ```
* **Behavior:** All cookies, `localStorage`, and session states are safely retained in `~/.config/steel/profiles/persistent`.

### 3. User GUI Desktop Control
* **When to use:** Only when the user explicitly asks to interact with their real visible desktop monitor or open an application inside their graphical X11 screen (`https://desktop.your-domain.com`).
* **Skill to use:** Load the **`desktop-gui-control`** skill instead.

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
