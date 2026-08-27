---
name: browser-automation
description: "Automate web browsing, navigation, form filling, logins, and live screen sessions via Steel Browser sandbox with proactive Live Viewer for Captchas/2FA."
version: 2.1.0
author: VPS Tools
license: MIT
metadata:
  hermes:
    tags: [browser, web, automation, scraping, navigation, cdp, live-viewer, 2fa, captcha]
    category: browser
    related_skills: [desktop-gui-control]
---

# Browser Automation Skill (Web & Cloud Sandbox)

Controls web browsing, page navigation, form interactions, and authenticated user sessions inside the sandboxed **Steel Browser** container.

## 🧭 How to Browse and Navigate

Always use the **native Hermes browser tools** for web automation tasks:
* **`browser_navigate(url)`**: Open any website or web application.
* **`browser_snapshot()`**: Read the semantic content and find element references (e.g. `@e1`, `@e2`).
* **`browser_type(ref, text)`**: Type into inputs or search fields.
* **`browser_click(ref)`**: Click buttons, checkboxes, or links.
* **`browser_vision()`**: Capture screenshots of the rendered page.
* **`browser_cdp(command, params)`**: Send direct Chrome DevTools Protocol commands when needed.

> [!NOTE]
> All browser sessions automatically maintain durable session state and cookies securely within the Steel Browser sandbox.

---

## 🔴 Proactive Live Viewer & Human-in-the-Loop (2FA / Captchas)

Whenever you encounter security challenges or the user requests interactive visual access:

### When to Generate a Live Link:
1. **Security Obstacles:** Cloudflare Turnstile, reCAPTCHA, hCaptcha, or bot challenges.
2. **Two-Factor Authentication:** SMS verification codes, authenticator app OTP prompts, or sensitive credentials.
3. **User Request:** The user asks to "ver", "mirar", or "dame el enlace en vivo".

### Procedure:
1. Launch an interactive live session:
   ```bash
   steel-session create "<url>"
   ```
2. Extract the `liveViewerUrl` from the output (e.g. `https://{{STEEL_DOMAIN}}/v1/sessions/debug?sessionId=<ID>`).
3. Send the link directly to the user with a courteous instruction:
   > *"He generado una sesión interactiva en vivo: [Enlace del Visor]. Por favor completa el Captcha o código 2FA en esa pestaña y avísame cuando estés listo para continuar."*
4. Wait for the user's confirmation before proceeding with the next actions.
5. Once the interactive task is complete, release the session:
   ```bash
   steel-session release <sessionId>
   ```

---

## 🖥️ Screen & Desktop GUI Control

If the user explicitly asks to control their visible desktop screen, move their physical mouse on their monitor, or open desktop apps on **`DISPLAY=:1`**, switch to the **`desktop-gui-control`** skill.
