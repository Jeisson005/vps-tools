#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SKILLS_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
VPS_TOOLS_DIR="$(cd "${SKILLS_DIR}/.." && pwd)"

TARGET="all"
TARGET_USER="${SUDO_USER:-$(id -un)}"
STEEL_DOMAIN=""

# Feature flags: "auto", "true", or "false"
FEATURE_PASSBOLT="auto"
FEATURE_STEEL="auto"
FEATURE_DESKTOP="auto"
FEATURE_WEBUI="auto"

usage() {
  cat << EOF
Usage: $(basename "$0") [OPTIONS]

Sync and configure curated skills for AI agents (OpenCode and Hermes) with modular feature detection.

Options:
  --target <all|opencode|hermes>   Target agent(s) to synchronize (default: all)
  --user <username>                Target system user (default: current user or SUDO_USER)
  --steel-domain <domain>          Override Steel browser domain (e.g. browser.domain.com)
  --with-passbolt / --without-passbolt
  --with-steel / --without-steel
  --with-desktop / --without-desktop
  --with-webui / --without-webui
  --help                           Show this help message
EOF
  exit 0
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --target)
      TARGET="${2:-all}"
      shift 2
      ;;
    --user)
      TARGET_USER="${2:-}"
      shift 2
      ;;
    --steel-domain)
      STEEL_DOMAIN="${2:-}"
      shift 2
      ;;
    --with-passbolt)
      FEATURE_PASSBOLT="true"
      shift
      ;;
    --without-passbolt)
      FEATURE_PASSBOLT="false"
      shift
      ;;
    --with-steel)
      FEATURE_STEEL="true"
      shift
      ;;
    --without-steel)
      FEATURE_STEEL="false"
      shift
      ;;
    --with-desktop)
      FEATURE_DESKTOP="true"
      shift
      ;;
    --without-desktop)
      FEATURE_DESKTOP="false"
      shift
      ;;
    --with-webui)
      FEATURE_WEBUI="true"
      shift
      ;;
    --without-webui)
      FEATURE_WEBUI="false"
      shift
      ;;
    --help|-h)
      usage
      ;;
    *)
      echo "[-] Unknown parameter: $1" >&2
      usage
      ;;
  esac
done

USER_HOME="$(eval echo ~${TARGET_USER})"

# -----------------------------------------------------------------------------
# AUTO-DETECTION OF AVAILABLE MODULES ON VPS
# -----------------------------------------------------------------------------
# 1. Passbolt / MCP Gateway
if [[ "$FEATURE_PASSBOLT" == "auto" ]]; then
  if [[ -f "${VPS_TOOLS_DIR}/mcp/.env" ]] && grep -q "^MCP_API_KEY=" "${VPS_TOOLS_DIR}/mcp/.env"; then
    FEATURE_PASSBOLT="true"
  else
    FEATURE_PASSBOLT="false"
  fi
fi

# 2. Steel Browser Sandbox
if [[ "$FEATURE_STEEL" == "auto" ]]; then
  if command -v steel-session &>/dev/null || [[ -f "${VPS_TOOLS_DIR}/steel/.env" ]]; then
    FEATURE_STEEL="true"
  else
    FEATURE_STEEL="false"
  fi
fi

# Resolve Steel Domain if Steel is enabled
if [[ "$FEATURE_STEEL" == "true" && -z "$STEEL_DOMAIN" ]]; then
  if [[ -f "${VPS_TOOLS_DIR}/steel/.env" ]]; then
    STEEL_DOMAIN_FROM_ENV=$(grep "^STEEL_DOMAIN=" "${VPS_TOOLS_DIR}/steel/.env" 2>/dev/null | cut -d'=' -f2- | tr -d '"' | tr -d "'" || true)
    if [[ -n "$STEEL_DOMAIN_FROM_ENV" ]]; then
      STEEL_DOMAIN="$STEEL_DOMAIN_FROM_ENV"
    fi
  fi
fi
STEEL_DOMAIN="${STEEL_DOMAIN:-browser.localhost}"

# 3. Desktop GUI / KasmVNC
if [[ "$FEATURE_DESKTOP" == "auto" ]]; then
  if command -v cua-driver &>/dev/null || [[ -f "${VPS_TOOLS_DIR}/desktop/.env" ]]; then
    FEATURE_DESKTOP="true"
  else
    FEATURE_DESKTOP="false"
  fi
fi

# 4. Open WebUI
if [[ "$FEATURE_WEBUI" == "auto" ]]; then
  if [[ -d "${VPS_TOOLS_DIR}/open-webui" && -f "${VPS_TOOLS_DIR}/open-webui/docker-compose.yml" ]]; then
    FEATURE_WEBUI="true"
  else
    FEATURE_WEBUI="false"
  fi
fi

echo "========================================================================"
echo "  SYNCHRONIZING CURATED AGENT SKILLS"
echo "  Target:   ${TARGET}"
echo "  User:     ${TARGET_USER} (${USER_HOME})"
echo "  Passbolt: ${FEATURE_PASSBOLT}"
echo "  Steel:    ${FEATURE_STEEL} (domain: ${STEEL_DOMAIN})"
echo "  Desktop:  ${FEATURE_DESKTOP}"
echo "  WebUI:    ${FEATURE_WEBUI}"
echo "========================================================================"

# -----------------------------------------------------------------------------
# OPENCODE SKILLS SYNC
# -----------------------------------------------------------------------------
sync_opencode() {
  echo "--> Syncing skills for OpenCode (~/.config/opencode/skills)..."
  local opencode_skills="${USER_HOME}/.config/opencode/skills"
  mkdir -p "${opencode_skills}"
  
  # Purge old versions to ensure strict sync
  rm -rf "${opencode_skills}/passbolt" \
         "${opencode_skills}/desktop-gui-control" \
         "${opencode_skills}/browser-automation" \
         "${opencode_skills}/centinela-tasks" \
         "${opencode_skills}/scheduled-tasks" 2>/dev/null || true

  # 1. Passbolt Skill (only if Passbolt is enabled)
  if [[ "$FEATURE_PASSBOLT" == "true" ]]; then
    mkdir -p "${opencode_skills}/passbolt"
    cp "${SKILLS_DIR}/passbolt/SKILL.md" "${opencode_skills}/passbolt/SKILL.md"
    echo "  [+] OpenCode: passbolt skill enabled"
  else
    echo "  [-] OpenCode: passbolt skill skipped (module not detected/disabled)"
  fi

  # 2. Desktop GUI Control Skill (only if Desktop is enabled)
  if [[ "$FEATURE_DESKTOP" == "true" ]]; then
    mkdir -p "${opencode_skills}/desktop-gui-control"
    cp "${SKILLS_DIR}/desktop-gui-control/SKILL.md" "${opencode_skills}/desktop-gui-control/SKILL.md"
    echo "  [+] OpenCode: desktop-gui-control skill enabled"
  else
    echo "  [-] OpenCode: desktop-gui-control skill skipped (module not detected/disabled)"
  fi

  # 3. Browser Automation (only if Steel is enabled)
  if [[ "$FEATURE_STEEL" == "true" ]]; then
    mkdir -p "${opencode_skills}/browser-automation"
    sed -e "s|{{STEEL_DOMAIN}}|${STEEL_DOMAIN}|g" \
        "${SKILLS_DIR}/browser-automation/opencode.md" > "${opencode_skills}/browser-automation/SKILL.md"
    echo "  [+] OpenCode: browser-automation skill enabled (Steel Browser)"
  else
    echo "  [-] OpenCode: browser-automation skill skipped (Steel Browser not detected/disabled)"
  fi

  # 4. Scheduled Tasks Skill
  mkdir -p "${opencode_skills}/scheduled-tasks"
  cp "${SKILLS_DIR}/scheduled-tasks/opencode.md" "${opencode_skills}/scheduled-tasks/SKILL.md"
  echo "  [+] OpenCode: scheduled-tasks skill enabled"

  # 5. Messaging Platforms Skill
  mkdir -p "${opencode_skills}/messaging-platforms"
  cp "${SKILLS_DIR}/messaging-platforms/SKILL.md" "${opencode_skills}/messaging-platforms/SKILL.md"
  echo "  [+] OpenCode: messaging-platforms skill enabled"

  chown -R "${TARGET_USER}:${TARGET_USER}" "${USER_HOME}/.config/opencode" 2>/dev/null || true
}

# -----------------------------------------------------------------------------
# HERMES SKILLS SYNC
# -----------------------------------------------------------------------------
sync_hermes() {
  echo "--> Syncing skills for Hermes Agent (~/.hermes/skills)..."
  local hermes_skills="${USER_HOME}/.hermes/skills"

  # Clean deprecated/residual paths
  rm -rf "${hermes_skills}/security/passbolt" \
         "${hermes_skills}/computer-use/desktop-gui-control" \
         "${hermes_skills}/browser/browser-automation" \
         "${hermes_skills}/tools/webui-workspace" \
         "${hermes_skills}/automation/centinela-tasks" \
         "${hermes_skills}/automation/scheduled-tasks" \
         "${hermes_skills}/browser/steel-browser" \
         "${hermes_skills}/computer-use/visual-session-control" 2>/dev/null || true

  # 1. Passbolt Skill
  if [[ "$FEATURE_PASSBOLT" == "true" ]]; then
    mkdir -p "${hermes_skills}/security/passbolt"
    cp "${SKILLS_DIR}/passbolt/SKILL.md" "${hermes_skills}/security/passbolt/SKILL.md"
    echo "  [+] Hermes: passbolt skill enabled"
  else
    echo "  [-] Hermes: passbolt skill skipped (module not detected/disabled)"
  fi

  # 2. Desktop GUI Control Skill
  if [[ "$FEATURE_DESKTOP" == "true" ]]; then
    mkdir -p "${hermes_skills}/computer-use/desktop-gui-control"
    cp "${SKILLS_DIR}/desktop-gui-control/SKILL.md" "${hermes_skills}/computer-use/desktop-gui-control/SKILL.md"
    echo "  [+] Hermes: desktop-gui-control skill enabled"
  else
    echo "  [-] Hermes: desktop-gui-control skill skipped (module not detected/disabled)"
  fi

  # 3. Browser Automation (Steel Browser)
  if [[ "$FEATURE_STEEL" == "true" ]]; then
    mkdir -p "${hermes_skills}/browser/browser-automation"
    sed -e "s|{{STEEL_DOMAIN}}|${STEEL_DOMAIN}|g" \
        "${SKILLS_DIR}/browser-automation/hermes.md" > "${hermes_skills}/browser/browser-automation/SKILL.md"
    echo "  [+] Hermes: browser-automation skill enabled (Steel Browser)"
  else
    echo "  [-] Hermes: browser-automation skill skipped (Steel Browser not detected/disabled)"
  fi

  # 4. WebUI Workspace Skill
  if [[ "$FEATURE_WEBUI" == "true" ]]; then
    mkdir -p "${hermes_skills}/tools/webui-workspace"
    cp "${SKILLS_DIR}/webui-workspace/SKILL.md" "${hermes_skills}/tools/webui-workspace/SKILL.md"
    echo "  [+] Hermes: webui-workspace skill enabled"
  else
    echo "  [-] Hermes: webui-workspace skill skipped (Open WebUI not detected/disabled)"
  fi

  # 5. Scheduled Tasks Skill
  mkdir -p "${hermes_skills}/automation/scheduled-tasks"
  cp "${SKILLS_DIR}/scheduled-tasks/hermes.md" "${hermes_skills}/automation/scheduled-tasks/SKILL.md"
  echo "  [+] Hermes: scheduled-tasks skill enabled"

  # 6. Messaging Platforms Skill
  mkdir -p "${hermes_skills}/communications/messaging-platforms"
  cp "${SKILLS_DIR}/messaging-platforms/SKILL.md" "${hermes_skills}/communications/messaging-platforms/SKILL.md"
  echo "  [+] Hermes: messaging-platforms skill enabled"

  chown -R "${TARGET_USER}:${TARGET_USER}" "${USER_HOME}/.hermes/skills" 2>/dev/null || true
}

case "$TARGET" in
  opencode)
    sync_opencode
    ;;
  hermes)
    sync_hermes
    ;;
  all)
    sync_opencode
    sync_hermes
    ;;
  *)
    echo "[-] Invalid target: ${TARGET}. Use opencode, hermes, or all." >&2
    exit 1
    ;;
esac

echo "========================================================================"
echo "  SKILLS SYNCHRONIZATION COMPLETED"
echo "========================================================================"
