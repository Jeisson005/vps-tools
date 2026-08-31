# Unified AI Agent Skills Catalog

Centralized, curated skills library for AI agents running on the VPS (**OpenCode** and **Hermes Agent**).

---

## 📦 Curated Skills

| Skill | Target | Description | MCP Dependencies |
| :--- | :--- | :--- | :--- |
| **`passbolt`** | OpenCode & Hermes | Search, decrypt passwords and generate live 2FA TOTP codes from Passbolt vault with strict mutation safeguards. | `passbolt` via MCP Gateway (`:8005/passbolt`) |
| **`desktop-gui-control`** | OpenCode & Hermes | Remote control of graphical X11 apps, mouse, and keyboard on `DISPLAY=:1` (KasmVNC / WireGuard). | `cua-driver` / X11 |
| **`browser-automation`** | OpenCode & Hermes | Sandboxed Chromium automation with Steel Browser. <br>• **OpenCode:** Ephemeral/isolated by default for testing/scraping.<br>• **Hermes:** Persistent by default for multi-turn user workflows.<br>• **Both:** Proactive Live Viewer URLs for human 2FA/CAPTCHA resolution. | `playwright` / `steel-session` |
| **`scheduled-tasks`** | OpenCode & Hermes | Autonomous background task orchestration, cron routines, Docker dependency isolation, and self-healing engine with 4-bot Telegram routing. | `sentinel` via MCP (`:8006/sse`) |
| **`webui-workspace`** | Hermes only | Lifecycle management for files attached via Open WebUI chat and native download cards. | `webui-file-upload` |

---

## 🚀 Synchronization & Deployment

To synchronize and install skills to agents:

```bash
# Sync all agents
sudo bash scripts/sync_skills.sh

# Sync only OpenCode (~/.config/opencode/skills)
sudo bash scripts/sync_skills.sh --target opencode --user your_user

# Sync only Hermes Agent (~/.hermes/skills)
sudo bash scripts/sync_skills.sh --target hermes --user your_user
```
