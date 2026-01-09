# Nginx + Reverse Proxy + Certbot

Nginx stack in Docker to manage multiple domains with automatic SSL certificates (Let's Encrypt).

## Available Commands

### Site Management
- `bash scripts/site_add.sh --domain [DOMAIN] --upstream [HOST:PORT]`
  Creates the basic configuration for a domain (HTTP enabled, HTTPS disabled).
- `bash scripts/enable_https.sh [DOMAIN]`
  Enables HTTPS mode for a domain (requires existing certificates).
- `bash scripts/enable_http.sh [DOMAIN]`
  Reverts to HTTP mode for a domain.

### SSL Certificates (Certbot)
- `bash scripts/certbot_init.sh [DOMAIN]`
  Generates the initial certificate for a domain using HTTP-01 validation.
- `bash scripts/certbot_renew.sh`
  Renews all certificates nearing expiration.

### Utilities
- `docker compose up -d`
  Starts the Nginx container.
- `bash scripts/reload_nginx.sh`
  Reloads Nginx configuration without restarting.
- `bash scripts/logs.sh`
  Shows real-time logs.
- `python3 test_server.py`
  Starts a test server on port 9000 of the host.

## Extras
- Configure the `.env` file before starting.
- Port 80 must be open for Let's Encrypt validation.
- Main folders: `conf.d/` (configs), `certbot/` (certificates), and `logs/`.
