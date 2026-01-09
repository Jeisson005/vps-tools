# Postgres + PgBouncer

Postgres stack in Docker with PgBouncer, intended to be easy to run in a VPS.

## Available Commands

### Setup
- `cp .env.example .env`
  Configure `POSTGRES_DB`, `POSTGRES_USER`, `POSTGRES_PASSWORD`.

### Stack
- `docker compose up -d --build`
  Starts Postgres (`db`) + PgBouncer (`pgbouncer`).
- `docker compose down`
  Stops containers.
- `docker compose down -v`
  Stops and deletes named volumes (DESTRUCTIVE).

### Logs
- `docker compose logs -f --tail=200 db`
- `docker compose logs -f --tail=200 pgbouncer`

### Connectivity checks
- Direct to Postgres:
  - `docker compose exec -T db psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -c '\conninfo'`
- Through PgBouncer:
  - `docker compose exec -T db bash -lc "PGPASSWORD=$POSTGRES_PASSWORD psql -h pgbouncer -U $POSTGRES_USER -d $POSTGRES_DB -c '\\conninfo'"`

### PgBouncer auth sync (SCRAM)
- `bash sync_pgbouncer_auth.sh`
  Extracts the SCRAM verifier for `$POSTGRES_USER` and writes it to `pgbouncer/userlist.txt`.

### Backups (one dump per database)

Backups are written to `BACKUP_DIR` (default: `./backups`, i.e. `vps-tools/postgres/backups/`).

- `bash scripts/backup_dbs.sh`
  Creates one `.dump` per database (custom format).
- Optional `.env` vars:
  - `BACKUP_DIR=./backups`
  - `RETENTION_DAYS=14`
  - `BACKUP_EXCLUDE_DBS=postgres` (comma-separated)

### Cleanup (delete dumps older than N days)
- `RETENTION_DAYS=30 bash scripts/cleanup_backups.sh`

## Cron examples
- Backup daily:
  - `15 3 * * * cd /path/to/vps-tools/postgres && bash scripts/backup_dbs.sh >> backups/cron.log 2>&1`
- Cleanup daily (older than 30 days):
  - `30 3 * * * cd /path/to/vps-tools/postgres && RETENTION_DAYS=30 bash scripts/cleanup_backups.sh >> backups/cleanup.log 2>&1`

## Notes
- Prefer dumping from `db` (direct Postgres), not through PgBouncer.
- For production: store backups off-host and test restores.