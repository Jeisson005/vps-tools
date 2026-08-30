# 🛡️ Centinela - VPS Resource & Health Monitor

Centinela is a lightweight, zero-dependency monitoring and alerting module for VPS infrastructure. It checks system health (e.g. disk capacity) and sends real-time Telegram notifications when critical thresholds are exceeded.

---

## 🚀 Features

- **Disk Space Monitoring:** Alerts when any monitored mount point (e.g. `/`, `/mnt/data`) exceeds the configurable threshold (default: `85%`).
- **Telegram Bot Integration:** Sends rich Markdown notifications directly to your Telegram chat.
- **Remediation Suggestions:** Includes actionable commands to quickly free up disk space (`docker system prune`, `journalctl vacuum`, etc.).
- **Zero Overhead:** Simple Bash scripts that execute in milliseconds via `cron`.

---

## ⚙️ Quick Setup

1. **Configure Environment:**
   ```bash
   cp .env.example .env
   chmod 600 .env
   ```
2. **Set Configuration Variables in `.env`:**
   ```bash
   TELEGRAM_BOT_TOKEN="123456789:ABCdef..."
   TELEGRAM_CHAT_ID="12345678"
   DISK_ALERT_THRESHOLD=85
   MONITORED_MOUNTS="/"
   ```
3. **Test Telegram Connectivity:**
   ```bash
   ./scripts/test_notify.sh
   ```
4. **Run Disk Check Manually:**
   ```bash
   ./scripts/check_disk.sh
   ```

---

## ⏰ Cron Integration

Add Centinela to your crontab to check disk health periodically (e.g., daily at 4:00 AM):

```cron
0 9 * * * /home/username/vps-tools/centinela/scripts/check_disk.sh >> /home/username/vps-tools/cron/logs/centinela.log 2>&1
```
