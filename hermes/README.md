# Hermes AI Agent (Nous Research)

Hermes Agent is a powerful, autonomous AI agent framework with Web Dashboard, CLI, and multi-platform messaging capabilities (Telegram, Discord, Slack, WhatsApp).

---

## 1. Quick Installation

1. Copy `.env.example` to `.env` and set your credentials:
```bash
cd vps-tools/hermes
cp .env.example .env
nano .env
```

2. Run the automated installer:
```bash
sudo bash scripts/install.sh
```

---

## 2. Services Architecture

Hermes runs two systemd background services:
1. **`hermes-dashboard.service`**: Web UI dashboard running on port `9119` (FastAPI + React 19).
2. **`hermes-gateway.service`**: Messaging gateway listening for Telegram / Discord incoming messages via long polling.

---

## 3. Telegram Integration

1. Get a Bot Token from [@BotFather](https://t.me/BotFather) on Telegram.
2. In `.env`:
   - Set `TELEGRAM_BOT_TOKEN=your_token`
   - Set `TELEGRAM_ALLOWED_USERS=your_telegram_username` (e.g. `jeisson`)
3. Restart the gateway service:
```bash
bash scripts/start.sh
```

---

## 4. Service Management

```bash
# Check status of both Dashboard and Gateway
bash scripts/status.sh

# Start services
bash scripts/start.sh

# Stop services
bash scripts/stop.sh

# Safely update Hermes and re-apply custom patches
bash scripts/update.sh
```

---

## 5. Updates & Patch Management

Hermes Agent is cloned directly from upstream Nous Research. To support seamless integration with other `vps-tools` components (Steel Browser), `vps-tools` maintains targeted patches:
* **`browser_tool_cdp.py`** (formerly `tools/browser_tool.py`): Preserves custom CDP ports when discovering remote Steel browser endpoints.

> **OpenCode Go requirement:** Hermes must send the `x-opencode-session` header (upstream fix `feat(opencode): send x-opencode-session on every OpenCode request`, after v0.21.0). Older versions fail against `https://opencode.ai/zen/go/v1` with `400 MissingSessionID`. Always update past that commit — `scripts/update.sh` does it.

> **WhatsApp bridge port:** upstream defaults to `3000` (collides with Steel API on this VPS). Set it in `~/.hermes/config.yaml` under **both** `platforms.whatsapp.bridge_port` and `platforms.whatsapp.extra.bridge_port` (upstream only reads `extra`). This VPS uses `3005`.

To ensure upstream updates never corrupt files or break silently, `scripts/update.sh` and `scripts/patch-hermes.py`:
1. Stash any temporary changes before pulling from upstream.
2. Validate AST and signature blocks before applying patches.
3. If upstream Nous Research modifies those functions in a new release, an explicit warning `[!] [WARNING]` is emitted instead of forcing a broken patch.
4. Automatically rebuild the dashboard frontend and reload services.

## 6. Passbolt como fuente del vault del navegador (vps-tools)

Upstream Hermes solo rellena contraseñas desde su vault local / 1Password /
Bitwarden, y en sesiones headless (Telegram/API) no puede pedir ni guardar
logins (`prompt_unavailable`). Este repo añade Passbolt como backend nativo:

- **Fuente**: `hermes/patches/passbolt_backend.py` → instalado en
  `agent/vault_backends/passbolt.py` por `install_passbolt_backend()` en
  `scripts/patch-hermes.py` (con validación de firmas + `ast.parse`, igual que
  los demás parches; sobrevive a `scripts/update.sh`).
- **Cómo funciona**: lista metadata vía el gateway MCP local
  (`passbolt_search_resources`, solo label/usuario/origen, nunca secretos);
  al rellenar resuelve `passbolt_get_secret` en el momento (contraseña + TOTP
  vivo). Handles `pb:<uuid>`. `needs_unlock = False`: funciona headless.
- **Rendimiento**: el listado completo tarda ~30 s (descifrado GPG en el
  gateway); se cachea en proceso (`list_ttl_seconds`, defecto 600 s). Los
  secretos siempre se leen frescos: cambiar una clave en Passbolt aplica al
  siguiente fill. Cero migración, cero sincronización.
- **Config** (`~/.hermes/config.yaml`, sección `vault.passbolt`):
  `gateway_url`, `scope`, `account` (opcional), `list_ttl_seconds`,
  `list_limit` y `origin_overrides` (`{uuid: origin}` para recursos cuyo URI
  no coincide con el IdP real, p. ej. cuentas Microsoft →
  `https://login.microsoftonline.com`).
- **Límite conocido**: `browser_vault_fill` solo escribe en páginas del
  navegador nativo de Hermes, no en sesiones Steel externas. Para sitios con
  muro anti-bot se sigue usando Steel (perfil persistente o `portal-drive.js`).
