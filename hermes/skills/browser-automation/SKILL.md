---
name: browser-automation
description: "Automate web browsing, navigation, form filling, logins, and live screen sessions via Steel Browser sandbox with proactive Live Viewer for Captchas/2FA."
version: 2.2.0
author: VPS Tools
license: MIT
metadata:
  hermes:
    tags: [browser, web, automation, scraping, navigation, cdp, live-viewer, 2fa, captcha, banking, logins]
    category: browser
    related_skills: [desktop-gui-control]
---

# Browser Automation Skill (Web & Cloud Sandbox)

Controls web browsing, page navigation, form interactions, authenticated user sessions, and interactive live viewing inside the sandboxed **Steel Browser** container.

## 🧭 Standard Web Browsing & Navigation

For all automated web tasks, use the native Hermes browser tools:
* **`browser_navigate(url)`**: Open any website or web application.
* **`browser_snapshot()`**: Read the semantic content and find element references (e.g. `@e1`, `@e2`).
* **`browser_type(ref, text)`**: Type into inputs or search fields.
* **`browser_click(ref)`**: Click buttons, checkboxes, or links.
* **`browser_vision()`**: Capture screenshots of the rendered page.
* **`browser_cdp(command, params)`**: Send direct Chrome DevTools Protocol commands when needed.

> [!NOTE]
> All browser sessions automatically maintain durable session state and cookies securely in `./data/steel-chrome`.

---

## 🔴 Proactive Live Viewer & Human-in-the-Loop Protocol

Whenever you are interacting via **Telegram, Discord, Web Dashboard, or any chat interface**:

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
2. Extract the `liveViewerUrl` from the output (e.g. `https://{{STEEL_DOMAIN}}/v1/sessions/debug?sessionId=<ID>`).
3. Send the link directly to the user as a clickable markdown link containing the full `liveViewerUrl` parameter:
   > *"He abierto una sesión interactiva en vivo para ti: [Abrir Sesión en Vivo](https://{{STEEL_DOMAIN}}/v1/sessions/debug?sessionId=<SESSION_ID>)\nPor favor abre el enlace, digita tus credenciales/2FA y avísame por aquí cuando hayas ingresado para continuar con tu consulta."*
   ⚠️ **CRITICAL:** Always include the full URL with the `?sessionId=<ID>` parameter. Never send the bare root domain.
4. **PAUSE and WAIT** for the user's confirmation message in chat before calling any further tools.
5. Once the task is completed, release the session:
   ```bash
   steel-session release <sessionId>
   ```

---

## 🖥️ Screen & Desktop GUI Control Distinction

* **Do NOT launch `google-chrome` or X11 tools on `DISPLAY=:1`** when the user simply asks to log in or browse from Telegram.
* Use the **`desktop-gui-control`** skill ONLY if the user explicitly mentions *"en mi escritorio VNC"*, *"en KasmVNC"*, or *"en mi pantalla visible"*.
