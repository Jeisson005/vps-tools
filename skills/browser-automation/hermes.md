---
name: browser-automation
description: "Automate web browsing, navigation, form filling, logins, and live screen sessions via Steel Browser sandbox with persistent user profiles and proactive Live Viewer for Captchas/2FA."
version: 2.3.0
author: VPS Tools
license: MIT
metadata:
  tags: [browser, web, automation, scraping, navigation, cdp, live-viewer, 2fa, captcha, banking, logins, persistent]
  category: browser
  related_skills: [desktop-gui-control, passbolt-credentials]
---

# Browser Automation Skill (Steel Cloud Sandbox - Hermes)

Controls web browsing, page navigation, form interactions, authenticated user sessions, and interactive live viewing inside the sandboxed **Steel Browser** container.

---

## 🧭 Steel Browser Architecture: Persistent & Multi-Session

All web automation through Steel Browser uses **dynamic, isolated sessions with persistent profile support**:
* **Every task or chat creates its own session:** Each call to `steel-session create` generates a unique `sessionId` (UUID) in Steel. Multiple conversations or parallel tasks run in separate browser processes without collisions.
* **Persistent by Default:** Sessions automatically preload saved cookies, logins, and local storage from `~/.config/steel/profiles/persistent/context.json`.
* **State Syncing:** When a session finishes or the user finishes logging in via the live viewer, running `steel-session sync <sessionId>` or `steel-session release <sessionId>` automatically saves any new cookies and tokens back to disk for future use.

---

## 🔴 Proactive Live Viewer & Human-in-the-Loop Protocol

Whenever you are interacting via **Telegram, WhatsApp, Open WebUI, or the Hermes Web Dashboard**:

### Crucial Triggers to Generate a Live Link:
1. **User Enters Credentials:** The user says *"yo pongo las credenciales"*, *"yo me logueo"*, *"yo pongo la clave"*, etc.
2. **Security & Captchas:** Cloudflare Turnstile, reCAPTCHA, hCaptcha, or bot challenges appear.
3. **Two-Factor Authentication:** SMS verification codes, banking OTP tokens, or authenticator app prompts.
4. **Direct Request:** The user asks to *"ver"*, *"mirar"*, or *"dame el link/enlace"*.

### Step-by-Step Execution:
1. Create the interactive live session:
   ```bash
   steel-session create "<url>"
   ```
   This returns JSON with:
   - `sessionId`: Unique UUID for this session.
   - `liveViewerUrl`: `https://{{STEEL_DOMAIN}}/v1/sessions/debug?sessionId=<UUID>`
   - `cdpWsUrl`: `ws://127.0.0.1:3000/?sessionId=<UUID>&apiKey=...`

2. Send the link directly to the user as a clickable markdown link containing the full `liveViewerUrl` parameter:
   > *"He abierto una sesión interactiva en vivo para ti: [Abrir Sesión en Vivo](https://{{STEEL_DOMAIN}}/v1/sessions/debug?sessionId=<SESSION_ID>)\nPor favor abre el enlace, digita tus credenciales/2FA y avísame por aquí cuando hayas ingresado para continuar con tu consulta."*

   ⚠️ **CRITICAL:** Always include the full URL with the `?sessionId=<ID>` parameter. Never send the bare root domain.

3. **PAUSE and WAIT** for the user's confirmation message in chat before calling any further tools.

4. Once the user confirms, drive the session via Playwright connecting to `cdpWsUrl`:
   ```bash
   node ~/.hermes/skills/browser/steel-live-session-control/scripts/steel-drive.js dump "<cdpWsUrl>"
   ```

5. When done, sync and release the session to free RAM:
   ```bash
   steel-session release <sessionId>
   ```

---

## 🖥️ Screen & Desktop GUI Control Distinction

* **Do NOT launch `google-chrome` or X11 tools on `DISPLAY=:1`** when the user asks to browse or log in from messaging platforms.
* Use the **`desktop-gui-control`** skill ONLY if the user explicitly asks to interact with their graphical VPS desktop monitor (*"en mi escritorio VNC"*, *"en KasmVNC"*, or *"en mi pantalla visible"*).
