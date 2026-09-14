# 📁 Filebrowser for VPS Tools

Self-hosted web file manager (upload, download, preview, rename, edit, share) behind Nginx HTTPS + shared HTTP Basic Auth.

---

## ✨ Key Features

* **Dual domains:** `files.your-domain.com` + `filebrowser.your-domain.com` → same container (same pattern as `vnc` + `desktop` → KasmVNC).
* **Single login:** Filebrowser native users (default `admin`, rename it + per-user scopes). No Nginx Basic Auth by design.
* **Real files:** `FILEBROWSER_FILES_DIR` points the root at host files (e.g. `/home/user`); default `./data/srv` sandbox.
* **Lightweight:** ~20-45 MB image (`filebrowser/filebrowser:s6`), ~256 MB RAM limit.
* **Persistent volumes:** `./data/srv` (user files), `./data/database` (users/shares), `./data/config` (settings).

---

## 📁 Directory Structure

```text
filebrowser/
├── .env.example            # Configuration template (no secrets)
├── docker-compose.yml      # Production container definition
├── README.md               # Documentation & usage guide
├── scripts/
│   ├── install.sh          # Create .env (600) + data dirs
│   ├── start.sh            # Launch container
│   ├── stop.sh             # Stop container
│   └── status.sh           # ps + resource usage + health check
├── templates/
│   └── filebrowser.nginx.conf.template  # Nginx reference (real vhosts in nginx/conf.d/)
└── data/ (generated on install, gitignored)
    ├── srv/                # User files served as /srv inside container
    ├── database/           # filebrowser.db
    └── config/             # settings.json
```

---

## 🚀 Quick Start

### 1. Initial Setup

```bash
./scripts/install.sh
nano .env   # set domains, FILEBROWSER_PORT, PUID=$(id -u) PGID=$(id -g)
```

### 2. Start the Service

```bash
./scripts/start.sh
```

### 3. First Login

Create your own admin user (DB is locked while the container runs, so stop it first):

```bash
docker compose stop filebrowser
docker run --rm -v "$PWD/data/database:/database" --entrypoint /bin/filebrowser \
  filebrowser/filebrowser:s6 -d /database/filebrowser.db \
  users add <user> '<password>' --perm.admin --scope .
docker run --rm -v "$PWD/data/database:/database" --entrypoint /bin/filebrowser \
  filebrowser/filebrowser:s6 -d /database/filebrowser.db users rm admin
docker compose up -d
```

### 4. Serve Real Files

By default the root is the isolated `./data/srv`. To expose host files, set in `.env` (untracked):

```bash
FILEBROWSER_FILES_DIR=/home/jeisson
```

then `docker compose up -d` (recreate). The container runs with `PUID/PGID`, so set them with `id -u / id -g` to keep ownership correct.

### 5. Check Status / Stop

```bash
./scripts/status.sh
./scripts/stop.sh
```

---

## 🔒 Nginx HTTPS (both domains, no Basic Auth)

Both vhosts proxy to the container DNS name `http://filebrowser:80` on the shared `nginx_default` network with a single Filebrowser login:

```bash
cd ../nginx
# 1. Create both vhosts pointing to the same upstream
bash scripts/site_add.sh --domain files.your-domain.com --upstream filebrowser:80
bash scripts/site_add.sh --domain filebrowser.your-domain.com --upstream filebrowser:80

# 2. Issue certs + enable HTTPS
bash scripts/certbot_init.sh files.your-domain.com
bash scripts/certbot_init.sh filebrowser.your-domain.com
bash scripts/enable_https.sh files.your-domain.com
bash scripts/enable_https.sh filebrowser.your-domain.com
```

> If you ever want the double lock again, attach the shared credentials:
> `bash scripts/auth_basic.sh --domain files.your-domain.com --user <u> --password <p>` (prompts securely if `--password` omitted).

---

## 📄 Notes

* Loopback bind only: `127.0.0.1:${FILEBROWSER_PORT}:80`. All external traffic goes through Nginx + TLS.
* Large files allowed: `client_max_body_size 2048M` in the vhost.
* To expose extra host folders later, add read-only mounts in `docker-compose.yml`, e.g.:
  `../open-webui/data/workspace:/srv/workspace:ro`.
* Back up `./data/` (files + db + settings) before major image upgrades.
