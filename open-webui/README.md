# 🌐 Open WebUI for VPS Tools

A modern, intuitive, ChatGPT/Claude-like web interface for non-technical users and teams, fully integrated with autonomous backend agents (like **Hermes Agent**), custom models, RAG document search, and shared workspace file execution.

---

## 🌟 Key Features

* **Intuitive Web & Mobile UI:** Clean, responsive interface with Markdown, code highlighting, dark mode, and PWA support (installable on iOS/Android).
* **Direct File Uploads & Drag & Drop:** Upload `.py`, `.pdf`, `.csv`, `.docx`, `.xlsx`, images, and audio files directly into chat.
* **Shared Workspace Execution:** Mounted `/workspace` volume allows backend agents to read, modify, and execute uploaded scripts on the VPS in real time.
* **Autonomous Agent Integration:** Connects directly to **Hermes Agent OpenAI Proxy** (`http://host.docker.internal:9119/v1`) or external LLM providers (OpenRouter, Anthropic, OpenAI).
* **Multi-User & Role Management:** Built-in authentication (Admin / User roles) with optional invite-only registration.
* **Lightweight & Fast:** Consumes only ~250–350 MB of RAM.

---

## 📁 Directory Structure

```text
open-webui/
├── .env.example             # Configuration template
├── docker-compose.yml       # Production container definition
├── README.md                # Documentation & usage guide
├── scripts/
│   ├── install.sh           # Setup directories, generate secret keys & .env
│   ├── start.sh             # Launch Open WebUI container
│   ├── stop.sh              # Stop container
│   └── status.sh            # Check status and health endpoint
├── templates/
│   └── open-webui.nginx.conf.template  # Nginx reverse proxy template with SSL & SSE
└── data/ (generated on install)
    ├── open-webui/          # Persistent SQLite DB, user accounts, and settings
    └── workspace/           # Shared folder for uploaded files and script execution
```

---

## 🚀 Quick Start (Local & Production)

### 1. Initial Setup
Run the installer script to create data folders, generate secure JWT secret keys, and initialize `.env`:
```bash
./scripts/install.sh
```

### 2. Configure Environment (`.env`)
Edit `open-webui/.env` with your settings:
```bash
# Public Domain
OPEN_WEBUI_DOMAIN="chat.yourdomain.com"

# Model Backend (Point to Hermes Proxy on host)
OPENAI_API_BASE_URL="http://host.docker.internal:9119/v1"
DEFAULT_MODELS="hermes"
```

### 3. Start the Service
```bash
./scripts/start.sh
```

### 4. Check Status
```bash
./scripts/status.sh
```

To stop the service at any time:
```bash
./scripts/stop.sh
```

---

## 🔒 Security & User Management

1. **First User is Admin:** The very first account registered via the web interface automatically becomes the Super Admin.
2. **Disable Public Signups:** After registering your account, change `ENABLE_SIGNUP=false` in `.env` and restart with `./scripts/start.sh` so unauthorized users cannot create accounts.
3. **Localhost Binding:** The container binds exclusively to `127.0.0.1:8080`, ensuring all external traffic passes through Nginx with SSL encryption.

---

## 📄 File Uploads & Server Execution

When a user uploads a file through the Open WebUI interface:
1. Files are stored in the persistent volume `./data/open-webui/uploads` and mirrored in `./data/workspace`.
2. The agent receives the text and file structure, allowing it to:
   - Analyze and explain code/documents.
   - Edit files directly in the shared workspace.
   - Execute scripts and return terminal output and download links to the user.
