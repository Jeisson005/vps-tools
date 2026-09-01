# VPS TOOLS

Project to configure a VPS with multiple tools ready to use with Docker Compose.

Contains:
- [setup/](setup/) — Initial VPS provisioning, security hardening, swap, and Docker installation
- [desktop/](desktop/) — Remote Desktop (XFCE4, KasmVNC HTML5 Web Desktop, XRDP)
- [headscale/](headscale/) — Self-hosted Headscale (open-source Tailscale control server) with Headscale-UI web dashboard
- [headscale-node/](headscale-node/) — Automated Tailscale node client connector with Exit Node routing support
- [backup/](backup/) — Automated system-wide GPG-encrypted backups to Google Drive via Rclone & Telegram alerts
- [opencode/](opencode/) — OpenCode AI coding assistant (CLI & Systemd Web service)
- [hermes/](hermes/) — Hermes autonomous AI agent by Nous Research (CLI, Telegram & WhatsApp Gateway, Web Dashboard)
- [skills/](skills/) — Unified AI Agent skills catalog and synchronization manager for OpenCode and Hermes
- [nginx/](nginx/) — Nginx reverse proxy, TLS (Certbot), and API Key/Basic Auth protection
- [steel/](steel/) — Steel Browser Sandbox (isolated headless Chromium with Live Session Viewer & MCP)
- [bash-mcp/](bash-mcp/) — Host-native Model Context Protocol server for VPS administration
- [mcp/](mcp/) — Modular MCP Gateway & Admin Panel (isolated subroutes, schema sanitizer, starting with Passbolt)
- [rustdesk/](rustdesk/) — RustDesk Self-Hosted Remote Desktop Server & Web Client (hbbs, hbbr, Web UI)
- [sentinel/](sentinel/) — Autonomous self-healing scheduled tasks & multi-bot Telegram routing
- [open-webui/](open-webui/) — Open WebUI ChatGPT/Claude-like interface with multi-user auth and RAG
- [postgres/](postgres/) — Postgres database + PgBouncer connection pooler
- [redis/](redis/) — Redis in-memory cache and key-value store
- [mongodb/](mongodb/) — MongoDB document database
- [cron/](cron/) — Automatic maintenance tasks, log cleanup, and examples

## AI Agent Capabilities

Unified intelligence layer empowering autonomous AI agents (Hermes & OpenCode) with tools, skills, and secure host access.

Agent Capabilities:
- **Host Administration & Shell Execution** ([bash-mcp/](bash-mcp/)) — Execute bash commands, inspect logs, monitor system health, and manage Docker containers with strict JSON schema compliance.
- **Browser Automation & Live Visualizer** ([steel/](steel/), [skills/browser-automation/](skills/browser-automation/)) — Headless Chromium sessions with DOM manipulation, form filling, captcha handling, and real-time live session inspection.
- **Remote Desktop & GUI Interaction** ([desktop/](desktop/), [skills/desktop-gui-control/](skills/desktop-gui-control/)) — Visual screen capture, mouse, and keyboard control over XFCE4 desktop via KasmVNC.
- **Secure Secret Management** ([mcp/](mcp/), [skills/passbolt/](skills/passbolt/)) — Access encrypted API keys, credentials, and tokens via Passbolt MCP Gateway without exposing plain secrets.
- **Self-Healing Task Supervision** ([sentinel/](sentinel/), [skills/scheduled-tasks/](skills/scheduled-tasks/)) — Proactive monitor for scheduled tasks with failure escalation, interactive Telegram diagnosis buttons, and automated healing.
- **Multi-Platform Messaging** ([hermes/](hermes/)) — Autonomous communication across Telegram Bot and WhatsApp (Baileys) with turn interruption handling and startup alerts.
- **Disaster Recovery Management** ([backup/](backup/)) — Perform on-demand or scheduled encrypted full-VPS backups with offsite sync to Google Drive.
- **VPN Mesh & Network Routing** ([headscale/](headscale/), [headscale-node/](headscale-node/)) — Secure internal routing across private WireGuard networks and exit node operations.

---

License: GNU AGPLv3 (see [LICENSE](LICENSE)).  
Copyright (C) 2025-2026 Jeisson Piñeros / Artic Company SAS.
