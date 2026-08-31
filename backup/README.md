# 📦 Automated VPS Backup to Google Drive

Comprehensive cloud backup suite for Linux VPS with **GPG (AES-256)** military-grade symmetric encryption, **Google Drive** synchronization via **Rclone**, active Docker database auto-discovery, and **GFS (Grandfather-Father-Son)** retention policy.

---

## 🎯 Key Features

1. **Full Home & Config Backup by Default:**
   * Archives user home directory (`$HOME`: projects, configs, `.bashrc`, SSH keys, `.env` files).
   * **Smart Exclusions:** Automatically skips heavy caches (`.cache/`, `.npm/`), `node_modules/`, Python virtual environments (`venv/`, `.venv/`), and massive log files to keep archives fast and lightweight.
2. **Active Database Auto-Discovery:**
   * Automatically detects running Docker containers for **PostgreSQL**, **MySQL/MariaDB**, **MongoDB**, and **Redis**.
   * Executes consistent database dumps (`pg_dumpall`, `mysqldump`, `mongodump`, `redis bgsave`) into staging before compression.
3. **End-to-End Encryption (GPG AES-256):**
   * No plaintext passwords, keys, or databases are sent to Google Drive.
   * Files are encrypted on the host before transmission.
4. **GFS Retention Policy (19 Backups Max):**
   * **7 Daily:** Retains the last 7 daily archives in `vps-tools-backups/daily/`.
   * **12 Monthly:** Retains 1 snapshot per month for the last 12 months in `vps-tools-backups/monthly/`.
   * **Manual Backups:** Saved permanently in `vps-tools-backups/manual/` (never expired).

---

## 🚀 Quick Setup

### 1. Link Google Drive with Rclone (Once)

Run the interactive setup helper:
```bash
./scripts/setup_rclone.sh
```
The helper installs `rclone` and guides configuration under the remote name `gdrive`.

### 2. Configure Environment Variables

Copy the template and set your master encryption key:
```bash
cp .env.example .env
chmod 600 .env
nano .env
```
Ensure you define:
* `BACKUP_ENCRYPTION_KEY`: A secure passphrase to encrypt/decrypt backups.
* `RCLONE_REMOTE=gdrive:vps-tools-backups`

---

## 💻 Usage

### Run Daily Backup (GFS rotation)
```bash
./scripts/backup.sh
# Or explicitly:
./scripts/backup.sh daily
```

### Run Manual Backup (Permanent, does not expire)
```bash
./scripts/backup.sh manual
```

### List Backups on Google Drive (Daily, Monthly, Manual)
```bash
./scripts/restore.sh list
```

### Test Backup Integrity (Download & verify without extracting)
```bash
./scripts/restore.sh test backup_daily_20260830_030000.tar.gz.gpg
```

### Restore Files to a Target Directory
```bash
./scripts/restore.sh restore backup_daily_20260830_030000.tar.gz.gpg /tmp/restore_dest
```

---

## ⏰ Cron Scheduling

To execute backups automatically every morning at **3:30 AM**:

```cron
30 3 * * * /path/to/vps-tools/backup/scripts/backup.sh >> /path/to/vps-tools/cron/logs/backup.log 2>&1
```
