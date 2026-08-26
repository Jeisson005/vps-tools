# Redis

Redis cache and in-memory key-value store in Docker, intended to be easy to run in a VPS.

## Getting Started (First Install)

Follow these steps to get Redis running:

1. **Configure Environment**:
   ```bash
   cp .env.example .env
   ```
   Edit `.env` and set your `REDIS_PASSWORD` and resource limits as needed.

2. **Start the Stack**:
   ```bash
   docker compose up -d
   ```

3. **Verify Connectivity**:
   - Via Docker Compose:
     ```bash
     docker compose exec redis redis-cli -a your_password ping
     ```
   - From Host CLI (if `redis-tools` is installed):
     ```bash
     redis-cli -h 127.0.0.1 -p 6379 -a your_password ping
     ```
   - Test basic key operations:
     ```bash
     docker compose exec redis redis-cli -a your_password SET test_key "Hello Redis"
     docker compose exec redis redis-cli -a your_password GET test_key
     ```

## Available Commands

### Backups (RDB Snapshot Dump)

Backups are written to `BACKUP_DIR` (default: `./backups`, i.e. `vps-tools/redis/backups/`).

- `bash scripts/backup.sh`
  Triggers a background save (`bgsave`) and compresses the `.rdb` snapshot to `redis_YYYYMMDDTHHMMSSZ.rdb.gz`.
- Optional `.env` vars:
  - `BACKUP_DIR=./backups`
  - `RETENTION_DAYS=14`

### Cleanup (delete dumps older than N days)
- `RETENTION_DAYS=30 bash scripts/cleanup_backups.sh`

## Cron Examples
- Daily backup at 5:00 AM UTC (12:00 AM UTC-5):
  - `0 5 * * * cd /path/to/vps-tools/redis && bash scripts/backup.sh >> logs/backup.log 2>&1`
- Daily cleanup of dumps older than 30 days:
  - `30 5 * * * cd /path/to/vps-tools/redis && RETENTION_DAYS=30 bash scripts/cleanup_backups.sh >> logs/cleanup.log 2>&1`

## Notes
- Persistence is enabled by default using RDB snapshots (`save 60 1`) and Append-Only File (`appendonly yes`).
- Data is preserved across container restarts in the `redisdata` Docker volume.
