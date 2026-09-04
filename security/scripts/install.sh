#!/usr/bin/env bash
# ==============================================================================
# Security - Dependency installer (Trivy + Gitleaks)
# Run once manually: ./install.sh (requires passwordless sudo for apt).
# The monthly scan degrades gracefully if a tool is missing, but install this
# so the audit actually covers CVEs and leaked secrets.
# ==============================================================================

set -euo pipefail

log() { echo "[install] $*"; }

if command -v trivy >/dev/null 2>&1; then
  log "trivy already installed: $(trivy --version | head -1)"
else
  log "Installing Trivy (official Aqua Security repo)..."
  sudo -n apt-get install -y wget apt-transport-https gnupg lsb-release
  wget -qO - https://aquasecurity.github.io/trivy-repo/deb/public.key | gpg --dearmor | sudo -n tee /usr/share/keyrings/trivy.gpg >/dev/null
  echo "deb [signed-by=/usr/share/keyrings/trivy.gpg] https://aquasecurity.github.io/trivy-repo/deb $(lsb_release -sc) main" | sudo -n tee /etc/apt/sources.list.d/trivy.list >/dev/null
  sudo -n apt-get update -y
  sudo -n apt-get install -y trivy
  log "trivy installed: $(trivy --version | head -1)"
fi

if command -v gitleaks >/dev/null 2>&1; then
  log "gitleaks already installed: $(gitleaks version 2>&1 | head -1)"
else
  log "Installing Gitleaks (official GitHub release)..."
  GITLEAKS_VER="${GITLEAKS_VER:-8.28.0}"
  TMPDIR_WORK="$(mktemp -d)"
  trap 'rm -rf "${TMPDIR_WORK}"' EXIT
  wget -qO "${TMPDIR_WORK}/gitleaks.tar.gz" \
    "https://github.com/gitleaks/gitleaks/releases/download/v${GITLEAKS_VER}/gitleaks_${GITLEAKS_VER}_linux_x64.tar.gz"
  tar -xzf "${TMPDIR_WORK}/gitleaks.tar.gz" -C "${TMPDIR_WORK}"
  sudo -n install -m 0755 "${TMPDIR_WORK}/gitleaks" /usr/local/bin/gitleaks
  log "gitleaks installed: $(gitleaks version 2>&1 | head -1)"
fi

log "Priming Trivy vulnerability DB (first download, may take a few minutes)..."
trivy image --download-db-only 2>&1 | tail -2 || log "WARNING: DB download failed, will retry at scan time."

log "Done."
