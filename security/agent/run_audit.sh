#!/usr/bin/env bash
# ==============================================================================
# Security - Agent audit runner (layer 2)
# Renders agent/PROMPT.md and runs opencode headless with auto-approval,
# using the SAME model as the MCP 'principal' AI account.
# Usage: run_audit.sh [YYYY-MM]   (default: current month)
# ==============================================================================

set -u
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SEC_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
REPO_ROOT="$(cd "${SEC_DIR}/.." && pwd)"
PERIOD="${1:-$(date +%Y-%m)}"
REPORT_DIR="${SEC_DIR}/reports/${PERIOD}"

export HOME="${HOME:-/home/jeisson}"
export PATH="/usr/local/bin:/usr/bin:/bin:${PATH}"

# Optional overrides (security/.env, gitignored)
if [[ -f "${SEC_DIR}/.env" ]]; then
  # shellcheck disable=SC1090
  source "${SEC_DIR}/.env"
fi
MODEL="${AUDIT_MODEL:-opencode-go/deepseek-v4-flash}"
TIMEOUT_MIN="${AGENT_TIMEOUT_MIN:-30}"

log() { echo "[agent ${PERIOD}] $*"; }

if [[ ! -f "${REPORT_DIR}/report.md" ]]; then
  log "ERROR: no programmatic report at ${REPORT_DIR}/report.md (did security_scan.sh run?)"
  exit 1
fi

# Render prompt to a .md file (+ local operator notes, gitignored, take precedence).
# NOTE: the full prompt goes via -f attachment, NOT as CLI arg: opencode run
# resolves message args containing "/" as file paths ("File not found").
RENDERED="$(mktemp -t audit-prompt-XXXXXX.md)"
sed -e "s|{{PERIOD}}|${PERIOD}|g" -e "s|{{REPORT_DIR}}|${REPORT_DIR}|g" \
  "${SCRIPT_DIR}/PROMPT.md" > "${RENDERED}"
LOCAL_NOTES="${SEC_DIR}/baseline/local/agent-notes.local.md"
if [[ -f "${LOCAL_NOTES}" ]]; then
  log "appending local agent notes"
  printf '\n\n## Local operator notes (uncommitted, take precedence on conflicts)\n' >> "${RENDERED}"
  cat "${LOCAL_NOTES}" >> "${RENDERED}"
fi

# NOTE: the message goes via STDIN, never as CLI arg: opencode run resolves
# message args as file paths when -f is used ("File not found"). Keep the
# message free of file-like tokens; full instructions live in ${RENDERED}.
log "Running opencode (model=${MODEL}, timeout=${TIMEOUT_MIN}min, --auto, read-only prompt)..."
if printf '%s' "You are the monthly security auditor. First read the attached audit procedure file, then the attached layer-1 report files. Execute the procedure end to end: verify findings, judge exposure, send exactly one Telegram verdict yourself, save your verdict file in the dated report folder, and reply with the verdict text." \
  | timeout "$((TIMEOUT_MIN * 60))" opencode run --auto \
    -m "${MODEL}" \
    --dir "${REPO_ROOT}" \
    -f "${RENDERED}" \
    -f "${REPORT_DIR}/report.md" \
    -f "${REPORT_DIR}/summary.json" \
    -f "${REPORT_DIR}/exposure.txt" 2>&1; then
  log "Agent audit finished."
  rm -f "${RENDERED}"
  exit 0
fi

# --- Fallback: agent failed -> routine notice so the month is not silent ---
log "ERROR: opencode agent failed. Sending fallback notice."
rm -f "${RENDERED}"
if [[ -f "${REPO_ROOT}/sentinel/.env" ]]; then
  # shellcheck disable=SC1090
  source "${REPO_ROOT}/sentinel/.env"
fi
TOKEN="${TELEGRAM_BOT_ROUTINE_TOKEN:-${TELEGRAM_BOT_TOKEN:-}}"
if [[ -n "${TOKEN}" && -n "${TELEGRAM_CHAT_ID:-}" ]]; then
  curl -s -X POST "https://api.telegram.org/bot${TOKEN}/sendMessage" \
    --data-urlencode "chat_id=${TELEGRAM_CHAT_ID}" \
    --data-urlencode "text=⚠️ Auditoría de seguridad ${PERIOD}: el escaneo programático está en security/reports/${PERIOD}/ pero el agente de revisión falló. Revisar manualmente." \
    -d "parse_mode=Markdown" >/dev/null 2>&1 || true
fi
exit 1
