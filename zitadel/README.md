# Zitadel (Self-hosted)

Zitadel identity stack for this repo. This folder contains configuration and helpers to run Zitadel (core + login) in Docker for local testing and small VPS deployments.

## Available Commands

### Setup / Configuration
- `cp .env.core.example .env.core`  
  Edit `.env.core` to configure domain, database connection and initial created tokens paths (see variables like `ZITADEL_FIRSTINSTANCE_LOGINCLIENTPATPATH` and `ZITADEL_FIRSTINSTANCE_PATPATH`).

### Start / Stop
- `docker compose up -d --build`  
  Starts `core` and `login` services.
- `docker compose down`  
  Stops containers.

### Logs & Health
- `docker compose logs -f --tail=200 core`  
  Follow core logs.
- `docker compose logs -f --tail=200 login`  
  Follow login logs.
- Healthcheck: core exposes `/debug/healthz` on host port `8080`.

## PAT rotation script (rotate_pats.sh) 🔧
The repo includes a helper script to atomically update local PAT files used by the services: `scripts/rotate_pats.sh`.

Important: the script **does not** call the Zitadel API to create PATs — you must provision the new tokens by your preferred method (console, Terraform, external automation) and provide them to this script.

### What it does
- Writes tokens to token files (default paths: `./login-client.pat` and `./admin.pat`).
- By default, if you run the script without arguments it will read existing token files from the repo root (`./login-client.pat`, `./admin.pat`) and re-write them atomically.
- Calculates expiration timestamps for any token rotated and writes metadata files next to them (e.g. `./login-client.pat.expiry`, `./admin.pat.expiry`) in ISO8601 UTC format.
- Does not modify `.env.core` or commit any expiry files to git (these files are ignored by `.gitignore`).

### Usage & examples
- Rotate tokens by passing token strings directly:
  ```bash
  bash scripts/rotate_pats.sh --login-pat "$NEW_LOGIN_PAT" --admin-pat "$NEW_ADMIN_PAT"
  ```

- Rotate by reading tokens from files (common for automation):
  ```bash
  bash scripts/rotate_pats.sh --login-pat-file /secure/path/new_login.pat --admin-pat-file /secure/path/new_admin.pat
  ```

- Run the script with default files (reads `./login-client.pat` and `./admin.pat` if present and rewrites them with updated expiries):
  ```bash
  ./scripts/rotate_pats.sh
  ```

- Expiry configuration (defaults to `now + 1 year`):
  - `--expiry-years N` set both expiries to now + N years
  - `--login-expiry-years N` / `--admin-expiry-years N` override per-token
  - `--expiry-date ISO8601` / `--login-expiry-date` / `--admin-expiry-date` to set exact date
  - `--no-write-expiry` skip writing the `.expiry` files
  - `--dry-run` simulate actions without changing files

### Notes for cron/automation
- Example cron that reads tokens provisioned to `/secure` and rotates daily at 04:00:
  ```cron
  0 4 * * * cd /path/to/vps-tools/zitadel && bash scripts/rotate_pats.sh --login-pat-file /secure/new_login.pat --admin-pat-file /secure/new_admin.pat --expiry-years 1 >> logs/rotate_pats.log 2>&1
  ```
- Keep provisioning credentials and token files outside the repo (e.g. in a secure directory or secret manager).

## Files & Secrets
- Default token paths referenced by the Zitadel setup are in `.env.core` (`ZITADEL_FIRSTINSTANCE_LOGINCLIENTPATPATH` and `ZITADEL_FIRSTINSTANCE_PATPATH`).
- The repository `.gitignore` prevents `login-client.pat`, `admin.pat` and `*.pat.expiry` from being committed.

## Tips & Troubleshooting
- Use `--dry-run` to validate the changes the script will perform before running it for real.
- If `login` is running in Docker Compose, the script will restart the `login` service after rotating tokens so it re-reads the token file (use `--no-restart` to avoid that during maintenance windows).
- Verify expiry metadata files contain an ISO8601 UTC timestamp (e.g. `2027-01-09T15:00:00Z`).

---

If you want, I can add this README file to the repo and add a short line to the top-level README referencing it. Should I proceed?  
(Also: do you want me to add an example cron line to the project docs?)
