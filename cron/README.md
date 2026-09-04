# Cron Examples

This folder contains `cron` configuration examples to automate maintenance tasks on the VPS.

## Contents

- `crontab.example`: Example crontab configurations for database backups (Postgres, Redis, MongoDB), Nginx certbot renewals, and log cleanup.
- `cron_test.sh`: Script to verify that cron is working correctly.
- `cleanup_logs.sh`: Script to delete old log files (default: older than 30 days).
- `check_ram.sh`: RAM & Swap health check with Telegram alerts (hourly). Companion to `check_disk.sh`. Reuses `sentinel/.env` credentials; thresholds + anti-spam cooldown via `cron/.env`.
- `check_disk.sh`: Disk space health check with Telegram alerts (daily). Reuses `sentinel/.env` credentials; thresholds + anti-spam cooldown via `cron/.env`.
- `nightly_refresh.sh`: Nightly restart of `opencode-web`, `open-webui`, `rustdesk-web` + light cleanup (docker builder cache, /tmp leftovers, journal vacuum). Never touches `steel-*`, `wa-*`, `hermes-*`, `sentinel`, `nginx`, `headscale`.
- `.env.example`: Optional overrides for the above (copy to `.env`, gitignored).
- `logrotate.example`: Configuration template for the system's `logrotate` service (recommended for production).

## Configuration

### Option A: Internal Cleanup (Recommended for simplicity)
To install the scheduled tasks and automatic log cleanup:

1. Edit the `crontab.example` file with the correct absolute paths.
2. Add them to your crontab by running:
   ```bash
   crontab -e
   ```
3. Copy and paste the content from the example.

### Option B: System Logrotate (Recommended for production)
If you have root access and prefer the standard system tool:
1. `sudo cp logrotate.example /etc/logrotate.d/vps-tools`
2. `sudo nano /etc/logrotate.d/vps-tools` (Change the path to your installation)

