#!/usr/bin/env bash
# ==============================================================================
# Security - Monthly orchestrator: layer 1 (scan) -> layer 2 (opencode agent)
# Cron: 0 3 1 * * .../monthly_audit.sh >> .../cron/logs/security_$(date +\%Y\%m).log 2>&1
# The agent sends the Telegram verdict itself (routine vs urgent, it decides).
# ==============================================================================

set -u
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PERIOD="$(date +%Y-%m)"

echo "================================================================="
echo "🛡️  Monthly security audit ${PERIOD}: $(date -R)"
echo "================================================================="

"${SCRIPT_DIR}/security_scan.sh" "${PERIOD}" || echo "[monthly] WARNING: scan layer issues (see above), continuing to agent."
"${SCRIPT_DIR}/../agent/run_audit.sh" "${PERIOD}" || echo "[monthly] WARNING: agent layer failed, fallback notice sent."

echo "================================================================="
echo "🛡️  Monthly security audit ${PERIOD} finished: $(date -R)"
echo "================================================================="
exit 0
