#!/usr/bin/env bash
# ==============================================================================
# Security - Monthly programmatic audit (layer 1, deterministic, read-only)
# Produces security/reports/YYYY-MM/ used as input by the opencode agent.
# Never fails hard (exit 0): every step degrades to a NOTE on error.
# Usage: security_scan.sh [YYYY-MM]   (default: current month)
# ==============================================================================

set -u
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SEC_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
REPO_ROOT="$(cd "${SEC_DIR}/.." && pwd)"
PERIOD="${1:-$(date +%Y-%m)}"
REPORT_DIR="${SEC_DIR}/reports/${PERIOD}"
mkdir -p "${REPORT_DIR}"

log() { echo "[scan ${PERIOD}] $*"; }
log "Report dir: ${REPORT_DIR}"

# --- 0. Local overrides (gitignored, see baseline/*.example) ---
TRIVY_IGNORE=""
if [[ -f "${SEC_DIR}/baseline/local/.trivyignore" ]]; then
  TRIVY_IGNORE="--ignorefile ${SEC_DIR}/baseline/local/.trivyignore"
  log "using local trivy ignorefile"
fi

# --- 1. Inventory ---
{
echo "# Inventory ${PERIOD} ($(date -R), $(hostname))"
echo ""
echo "## Docker images (running containers)"
docker ps --format '{{.Image}}' 2>/dev/null | sort -u || echo "(docker unavailable)"
echo ""
echo "## All local images"
docker images --format '{{.Repository}}:{{.Tag}} {{.ID}} {{.Size}}' 2>/dev/null || echo "(docker unavailable)"
echo ""
echo "## Key versions"
echo "opencode: $(opencode --version 2>&1 | head -1 || echo n/a)"
echo "docker: $(docker --version 2>&1 || echo n/a)"
echo "kernel: $(uname -r)"
echo "hermes: $(/home/jeisson/.hermes/hermes-agent/venv/bin/python -m hermes_cli --version 2>&1 | head -1 || echo n/a)"
} > "${REPORT_DIR}/versions.txt" 2>&1
log "inventory OK"

# --- 2. Trivy: images (HIGH/CRITICAL) ---
HIGH=0; CRITICAL=0; TRIVY_NOTE="ok"
if ! command -v trivy >/dev/null 2>&1; then
  TRIVY_NOTE="SKIPPED: trivy not installed (run security/scripts/install.sh)"
  log "${TRIVY_NOTE}"
else
  : > "${REPORT_DIR}/trivy-images.jsonl"
  for img in $(docker ps --format '{{.Image}}' 2>/dev/null | sort -u); do
    safe="$(echo "${img}" | tr '/:.' '___')"
    log "trivy image: ${img}"
    if timeout 600 trivy image --severity HIGH,CRITICAL --format json --quiet ${TRIVY_IGNORE} "${img}" > "${REPORT_DIR}/trivy-${safe}.json" 2>/dev/null; then
      h="$(jq '[.Results[]?.Vulnerabilities[]?] | length' "${REPORT_DIR}/trivy-${safe}.json" 2>/dev/null || echo 0)"
      echo "{\"image\":\"${img}\",\"high_critical\":${h}}" >> "${REPORT_DIR}/trivy-images.jsonl"
    else
      echo "{\"image\":\"${img}\",\"error\":\"scan failed or timed out\"}" >> "${REPORT_DIR}/trivy-images.jsonl"
      log "WARNING: trivy failed for ${img}"
    fi
  done
  HIGH="$(jq -r 'select(.high_critical != null) | .high_critical' "${REPORT_DIR}/trivy-images.jsonl" 2>/dev/null | awk '{s+=$1} END{print s+0}')"
  # trivy fs on the repo (vuln + misconfig; secrets are gitleaks' job)
  # NOTE: runtime data dirs may be root-owned -> prefer sudo when available
  log "trivy fs: repo"
  TRIVY_FS="timeout 300 trivy fs --severity HIGH,CRITICAL --scanners vuln,misconfig --format json --quiet ${TRIVY_IGNORE}"
  if sudo -n true 2>/dev/null; then
    sudo -n ${TRIVY_FS} "${REPO_ROOT}" > "${REPORT_DIR}/trivy-fs.json" 2>"${REPORT_DIR}/trivy-fs.err" || log "WARNING: trivy fs issues (see trivy-fs.err)"
  else
    ${TRIVY_FS} "${REPO_ROOT}" > "${REPORT_DIR}/trivy-fs.json" 2>"${REPORT_DIR}/trivy-fs.err" || log "WARNING: trivy fs issues (see trivy-fs.err)"
  fi
fi

# --- 3. Gitleaks: committed history (the leak vector is GitHub, not local .env) ---
SECRETS_COUNT="n/a"; GITLEAKS_NOTE="ok"
if ! command -v gitleaks >/dev/null 2>&1; then
  GITLEAKS_NOTE="SKIPPED: gitleaks not installed (run security/scripts/install.sh)"
  log "${GITLEAKS_NOTE}"
else
  log "gitleaks: git history"
  if gitleaks detect --source "${REPO_ROOT}" --log-opts="--all --full-history" --report-format json --report-path "${REPORT_DIR}/gitleaks.json" --exit-code 0 --no-color 2>"${REPORT_DIR}/gitleaks.err"; then
    SECRETS_COUNT="$(jq 'length' "${REPORT_DIR}/gitleaks.json" 2>/dev/null || echo 0)"
  else
    GITLEAKS_NOTE="gitleaks error (see gitleaks.err)"
  fi
fi
log "gitleaks findings in history: ${SECRETS_COUNT}"

# --- 4. Exposure ---
log "exposure audit"
"${SCRIPT_DIR}/check_exposure.sh" "${SEC_DIR}/baseline" "${REPORT_DIR}/exposure.txt" >/dev/null 2>&1 || true
UNEXPECTED="$(grep -E '^EXPOSED_UNEXPECTED_COUNT=' "${REPORT_DIR}/exposure.txt" 2>/dev/null | cut -d= -f2 || true)"
[[ "${UNEXPECTED}" =~ ^[0-9]+$ ]] || UNEXPECTED=0
log "unexpected public listeners: ${UNEXPECTED}"

# --- 5. Previous report (for month-over-month diff in report.md) ---
PREV_DIR="$(ls -d "${SEC_DIR}"/reports/*/ 2>/dev/null | grep -v "${PERIOD}" | sort | tail -1 || true)"

# --- 6. Assemble report.md + summary.json ---
cat > "${REPORT_DIR}/summary.json" <<EOF
{
  "period": "${PERIOD}",
  "host": "$(hostname)",
  "date": "$(date -R)",
  "trivy_note": "${TRIVY_NOTE}",
  "trivy_high_critical_total": ${HIGH:-0},
  "gitleaks_note": "${GITLEAKS_NOTE}",
  "gitleaks_history_findings": "${SECRETS_COUNT}",
  "unexpected_public_listeners": ${UNEXPECTED:-0}
}
EOF

{
echo "# Security audit (programmatic layer) — ${PERIOD}"
echo "_Host: $(hostname), date: $(date -R)_"
echo ""
echo "## Summary"
jq -r 'to_entries[] | "- \(.key): \(.value)"' "${REPORT_DIR}/summary.json"
echo ""
echo "Previous report: ${PREV_DIR:-none (first audit)}"
if [[ -n "${PREV_DIR}" && -f "${PREV_DIR}/summary.json" ]]; then
  echo '```diff'
  diff <(jq -S . "${PREV_DIR}/summary.json") <(jq -S . "${REPORT_DIR}/summary.json") || true
  echo '```'
fi
echo ""
echo "## Files in this report"
ls -1 "${REPORT_DIR}"
echo ""
echo "## Trivy per-image (HIGH/CRITICAL counts)"
cat "${REPORT_DIR}/trivy-images.jsonl" 2>/dev/null || echo "(skipped)"
echo ""
echo "## Exposure verdicts (tail)"
grep -E '^(OK|REVIEW|FAIL|NOTE|EXPOSED|FIREWALLED|EXPOSED_UNEXPECTED_COUNT)' "${REPORT_DIR}/exposure.txt" 2>/dev/null || echo "(no exposure data)"
} > "${REPORT_DIR}/report.md" 2>&1

log "Done. Report: ${REPORT_DIR}/report.md"
exit 0
