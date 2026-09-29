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

location = /api/admin/services/microsoft/oauth/callback {
  auth_basic off;
  proxy_pass http://mcp-gateway:8000;
  # …mismos proxy_set_header que el resto del vhost…
}
```

Es seguro: el `code` es de un solo uso, va atado al `client_id` + `redirect_uri` del cliente y la
aplicación valida el `state` antes de canjearlo. Caso real: `mcp.jeisson.top` (panel MCP) — sin
estos bloques, «Conectar con Google» / «Conectar con Microsoft» del panel fallaban siempre con 401.

---

### 6. Integrar proyectos externos sin acoplarlos

**Regla de oro: el proyecto manda; el VPS se adapta.** Un proyecto externo (en su propio repo,
pensado para correr también en otra máquina o en local sin nginx) **no debe saber que nginx
existe**, y este stack **no debe conocer** los proyectos concretos de un VPS.

Consecuencia práctica:

| Va en el **repo del proyecto** (portable) | Va **aquí** (local, gitignored) |
|---|---|
| Red interna propia (`driver: bridge`), `expose`, puertos normales | Acoplamiento con la red del proyecto y binds específicos del VPS |

El `docker-compose.yml` base de nginx es **genérico**: solo declara la red `default` y arranca en
cualquier VPS, con o sin proyectos externos. Las redes de los proyectos de *este* VPS se declaran
en `docker-compose.override.yml` (gitignored, Compose lo carga solo).

**Añadir un proyecto externo (pasos):**

1. El proyecto ya corre con **su propia red interna** (compose normal, sin referencias a nginx,
   sin publicar puertos). Ejemplo: `sorteos` (`artic-network`) y `excel-sanitizer` (`*_default`).
2. Averigua el nombre de su red:
   ```bash
   docker inspect <contenedor> --format '{{range $k,$v := .NetworkSettings.Networks}}{{$k}} {{end}}'
   ```
3. Añádela a `nginx/docker-compose.override.yml` (servicio `core` + bloque `networks`, `external: true`)
   y aplica:
   ```bash
   bash scripts/reload_nginx.sh
   ```
4. Crea el vhost apuntando al **nombre de servicio**:
   ```bash
   bash scripts/site_add.sh --domain ejemplo.com --upstream http://mi-servicio:8000
   ```
5. Para que un recreate del proyecto no rompa el proxy (nginx cachea la IP al cargar la config),
   usa resolución en runtime en el `location`:
   ```nginx
   resolver 127.0.0.11 valid=10s ipv6=off;
   set $upstream http://mi-servicio:8000;
   proxy_pass $upstream;
   ```

**Por qué así:** el repo del proyecto sigue siendo desplegable en cualquier parte (`docker compose up`
sin redes externas inexistentes) y este stack sigue siendo genérico; solo la máquina concreta sabe
qué proyectos hay. El acoplamiento nunca se escribe en un archivo versionado.

**Alternativa (proyectos no-Docker o que ya publican puerto):** publicar en loopback
(`127.0.0.1:PUERTO`) y apuntar el vhost a `host.docker.internal:PUERTO`. Ojo: desde el contenedor
de nginx `host.docker.internal` = `172.17.0.1`, así que un bind a `127.0.0.1` **no** es alcanzable;
para eso hay que publicar en `0.0.0.0` (queda dependiendo del firewall) o en `172.17.0.1`. Si el
proyecto debe seguir siendo portable, ese bind va en un override local del propio proyecto.

---

## Directory Structure
- `conf.d/`: Server blocks (`*.http.conf`, `*.https.conf`) and location snippets (`*.locations.*.conf`).
- `auth/`: Hashed `.htpasswd` files and generated `.key` files (mounted into `/etc/nginx/auth:ro`).
- `certbot/`: Certificates and webroot challenge directory.
- `logs/`: Access and error logs.
