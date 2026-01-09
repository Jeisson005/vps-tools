# Postgres + PgBouncer

Postgres stack in Docker with PgBouncer, intended to be easy to run in a VPS.

## Getting Started (First Install)

Follow these steps to get the database running for the first time:

1. **Configure Environment**:
   ```bash
   cp .env.example .env
   # Ensure pgbouncer/userlist.txt exists as a file to prevent Docker creating it as a folder
   mkdir -p pgbouncer && touch pgbouncer/userlist.txt
   ```
   Edit `.env` and set your `POSTGRES_DB`, `POSTGRES_USER`, and `POSTGRES_PASSWORD`.

2. **Start the Stack**:
   ```bash
   docker compose up -d
   ```
   This will initialize the database and create the `pgbouncer.get_auth` secure function.

3. **Synchronize PgBouncer Auth**:
   Since PgBouncer requires a valid SCRAM hash to perform user lookups, run the sync script:
   ```bash
   bash sync_pgbouncer_auth.sh
   ```
   This script extracts your user's hash and updates `pgbouncer/userlist.txt`.

4. **Verify Connectivity**:
   - Direct: `docker compose exec db psql -U your_user -d your_db`
   - Via PgBouncer: `psql -h 127.0.0.1 -p 5432 -U your_user -d your_db`

## Available Commands

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