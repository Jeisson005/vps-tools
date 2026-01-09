#!/usr/bin/env bash
# cleanup_logs.sh - Deletes old log files from vps-tools directories
set -euo pipefail

# Default retention: 30 days
LOG_RETENTION_DAYS="${LOG_RETENTION_DAYS:-30}"

# Get the script directory to find the root vps-tools path
# Assumes structure: vps-tools/cron/cleanup_logs.sh
ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"

echo "Starting log cleanup (Retention: $LOG_RETENTION_DAYS days)..."

# Find and delete log files under the repo that are older than the retention window.
# Covers common patterns:
#   - *.log
#   - *.log.1, *.log.2, ...
#   - *.log.1.gz, ...
find "$ROOT_DIR" -type f \( -name "*.log" -o -name "*.log.*" \) -mtime "+$LOG_RETENTION_DAYS" -print -delete

echo "Log cleanup finished."
