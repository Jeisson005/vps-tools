# OpenCode Environment & Browser Intelligence Guidelines

## 🌐 Steel Browser Sandbox & Navigation Capabilities

This server is equipped with **Steel Browser**, an isolated, sandboxed Chromium environment integrated with OpenCode via MCP and CLI helpers.

The user will usually **not** specify technical terms like "persistent" or "isolated". You must **autonomously infer** the correct browser mode and determine when to provide a live interactive session.

---

## 🧭 1. Autonomous Browser Mode Selection

### 🔒 Use `playwright` (Isolated / Incognito Mode) when:
- **Development & Debugging:** Testing locally hosted apps, staging deployments, diagnosing UI/API bugs, inspecting DOM elements.
- **Stateless Web Scraping & Research:** Extracting public information, reading documentation, verifying links, checking site uptime.
- **Disposable Tasks:** Any operation where saving cookies, cache, or authentication state would pollute the user's profile.

### 💾 Use `playwright-persistent` (Stateful / Persistent Mode) when:
- **User Identity & Logins:** Logging in with user credentials, accessing user dashboards, SaaS platforms (GitHub, AWS, Google, CRM), social media, or company portals.
- **Sensitive / Personal Services:** Banking, government portals, utilities, e-commerce checkouts, and tasks that emulate real personal user activity.
- **Multi-Step Workflows:** Tasks where the user expects to stay logged in across multiple prompts, retaining cookies, tokens, and `localStorage` in `~/.config/steel/profiles/persistent`.

---

## 🔴 2. Proactive Live Session & Human-in-the-Loop Interventions

You must provide the **Live Viewer URL** (`https://{{STEEL_DOMAIN}}/v1/sessions/debug?sessionId=<ID>`) in two scenarios:

### A. When the user asks for it:
- If the user asks to "see", "watch", "give me the live link", or "open the page for me to see".

### B. Proactively when Human Intervention is Required:
If you encounter a barrier during an automated navigation flow that requires human action:
1. **Security Checkpoints & Captchas:** Cloudflare Turnstile, reCAPTCHA, hCaptcha, or bot detection checkpoints.
2. **Two-Factor Authentication (2FA):** SMS codes, authenticator apps, OTP prompts, or hardware security keys.
3. **Sensitive Authentication:** Situations where the user prefers to type passwords, pin numbers, or bank credentials directly.
4. **Interactive Actions:** Manual signatures, complex drag-and-drop verifications, or payment authorization.

### 🛠️ How to provide the Live Session:
1. Execute the system CLI tool:
   ```bash
   steel-session create "<url>"
   ```
2. Parse the returned JSON to obtain `liveViewerUrl` (e.g. `https://{{STEEL_DOMAIN}}/v1/sessions/debug?sessionId=...`).
3. Send the link to the user clearly, stating what requires their attention:
   > *"He abierto la sesión en vivo en tu navegador: [Enlace de Sesión]. Por favor resuelve el Captcha / 2FA en esa pestaña y avísame cuando esté listo para que pueda continuar."*
4. Wait for the user's confirmation before resuming the subsequent steps of the flow.
5. When the entire task is complete, you can release the session with:
   ```bash
   steel-session release <sessionId>
   ```
