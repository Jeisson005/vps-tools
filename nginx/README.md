# Nginx + Reverse Proxy + Certbot + Auth Security

Nginx stack in Docker to manage multiple domains with automatic SSL certificates (Let's Encrypt), and built-in scripts to protect any endpoint with **HTTP Basic Auth** or **API Key Authentication**.

---

## Available Commands

### 1. Site & Route Management
- **Add a domain proxying root (`/`)**:
  ```bash
  bash scripts/site_add.sh --domain example.com --upstream host.docker.internal:9000
  ```
- **Add a sub-path route on an existing domain**:
  ```bash
  bash scripts/site_add.sh --domain example.com --path /app --upstream host.docker.internal:9001
  ```
- **Enable HTTPS mode (after issuing cert)**:
  ```bash
  bash scripts/enable_https.sh example.com
  ```
- **Revert to HTTP mode**:
  ```bash
  bash scripts/enable_http.sh example.com
  ```

---

### 2. Endpoint Authentication & Protection

#### A. Protect with API Key (`X-API-Key` or `Authorization: Bearer <key>`)
Protect any endpoint (e.g. MCP `/mcp`, private APIs):
```bash
# Auto-generate a secure random API key for an endpoint:
bash scripts/auth_apikey.sh --domain example.com --path /mcp

# Or set your own key:
bash scripts/auth_apikey.sh --domain example.com --path /mcp --key "your_secret_api_token_here"
```

Clients must include one of these HTTP headers:
- `X-API-Key: your_secret_api_token_here`
- `Authorization: Bearer your_secret_api_token_here`

#### B. Protect with HTTP Basic Auth (User & Password)
```bash
# Add a user and password to protect a path:
bash scripts/auth_basic.sh --domain example.com --path /admin --user myuser --password mysecurepass

# Or protect an entire domain:
bash scripts/auth_basic.sh --domain example.com --user myuser --password mysecurepass
```

#### C. Create and Protect in a Single Command:
```bash
# Expose host-native bash-mcp protected by API Key:
bash scripts/site_add.sh --domain mcp.example.com --path /mcp --upstream host.docker.internal:8001 --api-key "your_secret_api_token_here"
```

---

### 3. SSL Certificates (Certbot)
- `bash scripts/certbot_init.sh [DOMAIN]`
  Generates the initial certificate for a domain using HTTP-01 validation.
- `bash scripts/certbot_renew.sh`
  Renews all certificates nearing expiration.

---

### 4. Utilities
- `docker compose up -d`
  Starts the Nginx container.
- `bash scripts/reload_nginx.sh`
  Reloads Nginx configuration without restarting.
- `bash scripts/logs.sh`
  Shows real-time logs.
- `python3 test_server.py`
  Starts a test server on port 9000 of the host.

---

### 5. OAuth callbacks bajo Basic Auth (importante)

Si proteges **todo** el vhost con Basic Auth (`location /`), cualquier *callback* de OAuth deja
de funcionar: Google/Microsoft no pueden enviar credenciales en su redirect, así que reciben un
401 y el flujo termina en un error de red en el navegador. Hay que eximir la ruta exacta:

```nginx
location = /api/admin/services/google/oauth/callback {
  auth_basic off;
  proxy_pass http://mcp-gateway:8000;
  # …mismos proxy_set_header que el resto del vhost…
}
```

Es seguro: el `code` es de un solo uso, va atado al `client_id` + `redirect_uri` del cliente y la
aplicación valida el `state` antes de canjearlo. Caso real: `mcp.jeisson.top` (panel MCP) — sin
este bloque, «Conectar con Google» del panel fallaba siempre con 401.

---

## Directory Structure
- `conf.d/`: Server blocks (`*.http.conf`, `*.https.conf`) and location snippets (`*.locations.*.conf`).
- `auth/`: Hashed `.htpasswd` files and generated `.key` files (mounted into `/etc/nginx/auth:ro`).
- `certbot/`: Certificates and webroot challenge directory.
- `logs/`: Access and error logs.
