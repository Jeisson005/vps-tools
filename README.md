# VPS TOOLS

Project to configure a VPS with multiple tools ready to use with Docker Compose.

Contains:
- [setup/](setup/) — Initial VPS provisioning, security hardening, swap, and Docker installation
- [desktop/](desktop/) — Remote Desktop (XFCE4, KasmVNC HTML5 Web Desktop, XRDP)
- [opencode/](opencode/) — OpenCode AI coding assistant (CLI & Systemd Web service)
- [hermes/](hermes/) — Hermes autonomous AI agent by Nous Research (CLI)
- [skills/](skills/) — Unified AI Agent skills catalog and synchronization manager for OpenCode and Hermes
- [nginx/](nginx/) — Nginx reverse proxy, TLS (Certbot), and API Key/Basic Auth protection
- [steel/](steel/) — Steel Browser Sandbox (isolated headless Chromium with Live Session Viewer & MCP)
- [bash-mcp/](bash-mcp/) — Host-native Model Context Protocol server for VPS administration
- [mcp/](mcp/) — Modular MCP Gateway & Admin Panel (isolated subroutes, schema sanitizer, starting with Passbolt)
- [sentinel/](sentinel/) — Autonomous self-healing scheduled tasks & multi-bot Telegram routing
- [open-webui/](open-webui/) — Open WebUI ChatGPT/Claude-like interface with multi-user auth and RAG
- [postgres/](postgres/) — Postgres database + PgBouncer
- [redis/](redis/) — Redis in-memory cache and key-value store
- [mongodb/](mongodb/) — MongoDB document database
- [zitadel/](zitadel/) — Zitadel identity stack
- [cron/](cron/) — Automatic maintenance tasks and examples

License: GNU AGPLv3 (see [LICENSE](LICENSE)).
Copyright (C) 2025 Jeisson Piñeros / Artic Company SAS.
