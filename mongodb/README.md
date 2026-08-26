# MongoDB

MongoDB document database in Docker, intended to be easy to run in a VPS.

## Getting Started (First Install)

Follow these steps to get the database running:

1. **Configure Environment**:
   ```bash
   cp .env.example .env
   ```
   Edit `.env` and set your `MONGO_INITDB_ROOT_USERNAME`, `MONGO_INITDB_ROOT_PASSWORD`, and `MONGO_INITDB_DATABASE`.

2. **Start the Stack**:
   ```bash
   docker compose up -d
   ```

3. **Verify Connectivity**:
   - Via Docker Compose:
     ```bash
     docker compose exec db mongosh -u your_user -p your_password --authenticationDatabase admin
     ```
   - From Host CLI (if `mongosh` is installed):
     ```bash
     mongosh "mongodb://your_user:your_password@127.0.0.1:27017/admin"
     ```
   - Connection URI format for applications:
     ```text
     mongodb://your_user:your_password@127.0.0.1:27017/appdb?authSource=admin
     ```

## Available Commands

### Backups (one compressed archive per database)

Backups are written to `BACKUP_DIR` (default: `./backups`, i.e. `vps-tools/mongodb/backups/`).

- `bash scripts/backup_dbs.sh`
  Creates one `.archive.gz` per user database using `mongodump`.
- Optional `.env` vars:
  - `BACKUP_DIR=./backups`
  - `RETENTION_DAYS=14`
  - `BACKUP_EXCLUDE_DBS=admin,config,local` (comma-separated)

### Cleanup (delete dumps older than N days)
- `RETENTION_DAYS=30 bash scripts/cleanup_backups.sh`

### Restore from Backup
To restore a specific database dump archive:
```bash
docker compose exec -T db mongorestore \
  -u your_user \
  -p your_password \
  --authenticationDatabase admin \
  --nsInclude="your_db.*" \
  --archive \
  --gzip \
  < backups/your_db_20260101T000000Z.archive.gz
```

## Cron Examples
- Daily backup at 4:30 AM UTC (11:30 PM UTC-5):
  - `30 4 * * * cd /path/to/vps-tools/mongodb && bash scripts/backup_dbs.sh >> logs/backup.log 2>&1`
- Daily cleanup of dumps older than 30 days:
  - `0 5 * * * cd /path/to/vps-tools/mongodb && RETENTION_DAYS=30 bash scripts/cleanup_backups.sh >> logs/cleanup.log 2>&1`

## Notes
- Authentication is strictly enabled with `--auth`.
- Database data is stored persistently in the `mongodata` volume, and configuration is stored in `mongoconfig`.
