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

# 3. Create global executable in /usr/local/bin/hermes
echo "--> [3/3] Setting up global executable wrapper in /usr/local/bin/hermes..."
cat << 'WRAPPER' > /usr/local/bin/hermes
#!/usr/bin/env bash
HERMES_DIR="${HOME}/.hermes/hermes-agent"
if [[ ! -d "$HERMES_DIR" ]]; then
  # Fallback to system user home if run as root or different user
  for d in /home/*/.hermes/hermes-agent; do
    if [[ -d "$d" ]]; then
      HERMES_DIR="$d"
      break
    fi
  done
fi

if [[ -x "${HERMES_DIR}/venv/bin/python" ]]; then
  PYTHON_BIN="${HERMES_DIR}/venv/bin/python"
elif command -v uv &>/dev/null; then
  PYTHON_BIN="uv run python"
else
  PYTHON_BIN="python3"
fi

cd "${HERMES_DIR}" 2>/dev/null || true
exec ${PYTHON_BIN} "${HERMES_DIR}/cli.py" "$@"
WRAPPER
chmod +x /usr/local/bin/hermes
echo "--> Hermes agent wrapper installed at /usr/local/bin/hermes"

echo ""
echo "========================================================================"
echo "  HERMES AGENT INSTALLED SUCCESSFULLY"
echo "  Run 'hermes setup' or 'hermes chat' to start"
echo "========================================================================"
