# Steel Browser Sandbox (AI Agent Infrastructure)

Production-ready, batteries-included browser sandbox designed for AI agents and web automation with REST API, Chrome DevTools Protocol (CDP), and Live Session Viewer (Human-in-the-Loop).

---

## 1. Quick Installation

1. Copy `.env.example` to `.env`:
```bash
cd vps-tools/steel
cp .env.example .env
nano .env
```

2. Run the automated installer:
```bash
bash scripts/install.sh
```

---

## 2. Ports & Architecture

- **Port `3000` (HTTP & WebSocket)**: Steel REST API, session management, and Live Interactive UI (`/v1/sessions`, `/ui`), servidos por el router.
- **Modelo de concurrencia**: Steel auto-hospedado (v0.5.x) ejecuta **1 sesión por instancia POR DISEÑO**. Hay **3 workers fijos** (`steel-browser-1/2/3`), por lo que el máximo real es **3 sesiones simultáneas**, una por worker.
- **Router (`steel-browser`)**: proxy puro. Asigna cada sesión nueva a un worker libre (0 sesiones activas), serializa las creaciones (evita `SingletonLock`) y reintenta en otro worker si uno está degradado. Si los 3 están ocupados responde `503` (nunca desplaza una sesión viva). **No monta `docker.sock`**.
- **Ciclo de vida (leases + reaper)**: una sesión con lease (`x-steel-lease-ttl`) se mantiene viva mientras el cliente renueve con `POST /v1/sessions/<id>/heartbeat`; al vencer el lease + gracia, el router la libera. Las sesiones **sin lease** se liberan por inactividad (HTTP/CDP) tras `SESSION_IDLE_RELEASE_SEC` (30 min). El reaper además descubre sesiones huérfanas (p. ej. creadas antes de un reinicio del router). El wrapper MCP (`steel-mcp`) renueva el lease mientras hay actividad y **recrea la sesión de forma transparente** en el siguiente tool call si expiró.
- **Session CDP**: cada sesión expone su WS de CDP vía el router en el puerto `3000` (`ws://127.0.0.1:3000/?sessionId=<id>&apiKey=<key>`).
- **Worker CDP ports `9221`-`9224`** (loopback): CDP por worker, uso interno del router.
- **Resource Limits**: 2 GB RAM por worker, `shm_size: 1gb`, `cap_add: [SYS_ADMIN]`.

---

## 3. Usage Examples

### REST API (Create a Session)
```bash
curl -X POST http://127.0.0.1:3000/v1/sessions \
  -H "x-steel-api-key: YOUR_STEEL_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"useProxy": false}'
```

### Response contains:
- `id`: Session UUID.
- `websocketUrl`: Full CDP WebSocket URL for Playwright / Puppeteer.
- `sessionViewerUrl`: Interactive web link for human-in-the-loop inspection and manual intervention.

### Connecting with Playwright (Python / Node.js)
```python
from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    # cdp_ws_url = ws://127.0.0.1:3000/?sessionId=<id>&apiKey=<key> (from the session response)
    browser = p.chromium.connect_over_cdp(cdp_ws_url)
    page = browser.new_page()
    page.goto("https://example.com")
    print(page.title())
    browser.close()
```

---

## 4. Lifecycle Management

```bash
# Check status
bash scripts/status.sh

# Run automated session test
bash scripts/test_session.sh

# Start container
bash scripts/start.sh

# Stop container
bash scripts/stop.sh

# Update image and recreate container
bash scripts/update.sh

# Session CLI (leases): create with TTL, renew, release
node scripts/steel-session.js create "https://example.com" --ttl 1h
node scripts/steel-session.js heartbeat <sessionId> --ttl 1h
node scripts/steel-session.js release <sessionId>
```

---

## 5. Security & Network Isolation

* **Perimeter Protection**: Public access to domains `steel.<domain>` and `browser.<domain>` is strictly guarded by HTTP Basic Authentication at the Nginx reverse proxy level.
* **Internal Network Isolation**: Ports `3000` (API) and `9221`-`9224` (worker CDP) are bound exclusively to loopback (`127.0.0.1`), blocking any direct public access to Docker container ports.
* **Local Agents**: Agents running locally on the VPS (Hermes, OpenCode, CLI tools) connect via loopback (`http://127.0.0.1:3000`). Session CDP goes through the same port (`ws://127.0.0.1:3000/?sessionId=...`).
* **Session lifetime**: Steel no expira sesiones por sí mismo. El router libera por inactividad (30 min, `SESSION_IDLE_RELEASE_SEC`), por lease vencido (`SESSION_LEASE_DEFAULT_TTL_SEC` + `SESSION_HEARTBEAT_GRACE_SEC`) y opcionalmente por tope duro (`SESSION_MAX_AGE_SEC`, 0 = off). Como última red, `scripts/cleanup_sessions.sh` libera las `live/idle` mayores a `STEEL_SESSION_MAX_AGE_SEC` (24h por defecto) vía cron nocturno. Cerrar el Live Viewer **no** libera la sesión.
* **Worker recycling**: al liberar una sesión, Chromium puede dejar `SingletonLock`/zombies y dejar la instancia inutilizable. `scripts/recycle_workers.sh` reinicia un worker **solo si no tiene sesiones activas** (API caída, >`STEEL_RECYCLE_ZOMBIE_THRESHOLD` zombies, o `--force-empty` tras la limpieza nocturna). Cron horario en el minuto 25. El router no necesita Docker: el reciclado corre en el host.
