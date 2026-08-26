#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
HERMES_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
cd "${HERMES_DIR}"

echo "========================================================================"
echo "  INSTALLING HERMES AGENT (NOUS RESEARCH)"
echo "========================================================================"

if [[ $EUID -ne 0 ]]; then
  echo "[-] ERROR: This installation script must be run with sudo or as root." >&2
  exit 1
fi

load_env_safe() {
  local env_file="$1"
  if [[ -f "$env_file" ]]; then
    while IFS='=' read -r key val || [[ -n "$key" ]]; do
      key="$(echo "$key" | xargs)"
      [[ -z "$key" || "$key" =~ ^# ]] && continue
      val="${val%\"}"
      val="${val#\"}"
      val="${val%\'}"
      val="${val#\'}"
      case "$key" in
        HERMES_USER) HERMES_USER="$val" ;;
      esac
    done < "$env_file"
  fi
}

HERMES_USER="${SUDO_USER:-jeisson}"

if [[ -f .env ]]; then
  load_env_safe .env
elif [[ -f .env.example ]]; then
  load_env_safe .env.example
fi

USER_HOME="$(eval echo ~${HERMES_USER})"

# 1. Install prerequisites
echo "--> [1/3] Installing system prerequisites (ripgrep, ffmpeg, git, curl, build-essential)..."
apt-get update -qq
apt-get install -y -qq git curl ca-certificates ripgrep ffmpeg build-essential

# 2. Run official Hermes installer as the target user
echo "--> [2/3] Downloading and installing Hermes Agent for user '${HERMES_USER}'..."
su - "${HERMES_USER}" -c 'curl -fsSL https://hermes-agent.nousresearch.com/install.sh | bash'

# 3. Create global symlink in /usr/local/bin/hermes
echo "--> [3/3] Setting up global executable symlink..."
HERMES_BIN=""
for path in \
  "${USER_HOME}/.hermes/bin/hermes" \
  "${USER_HOME}/.local/bin/hermes" \
  "${USER_HOME}/.hermes/hermes-agent/bin/hermes" \
  "${USER_HOME}/.hermes/hermes-agent/venv/bin/hermes"; do
  if [[ -f "$path" ]]; then
    HERMES_BIN="$path"
    break
  fi
done

if [[ -n "$HERMES_BIN" ]]; then
  ln -sf "$HERMES_BIN" /usr/local/bin/hermes
  chmod +x "$HERMES_BIN" /usr/local/bin/hermes
  echo "--> Hermes agent linked to /usr/local/bin/hermes"
else
  # If wrapper needed via uv/python in virtual environment
  if [[ -d "${USER_HOME}/.hermes/hermes-agent" ]]; then
    cat << WRAPPER > /usr/local/bin/hermes
#!/usr/bin/env bash
exec su - ${HERMES_USER} -c "cd ~/.hermes/hermes-agent && uv run hermes \"\$@\""
WRAPPER
    chmod +x /usr/local/bin/hermes
    echo "--> Hermes wrapper created at /usr/local/bin/hermes"
  fi
fi

echo ""
echo "========================================================================"
echo "  HERMES AGENT INSTALLED SUCCESSFULLY"
echo "  Run 'hermes setup' or 'hermes chat' to start"
echo "========================================================================"
