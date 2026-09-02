#!/usr/bin/env bash
# ==============================================================================
# WhatsApp Baileys bridge provisioner — one container per WhatsApp account.
#
# Adds/removes a `wa-<account>` bridge container for each configured WhatsApp
# account, computing the SAME deterministic port used by the MCP service
# (src/services/whatsapp/__init__.py::bridge_url_for). The MCP gateway just talks
# to http://127.0.0.1:<port>.
#
# Usage:
#   whatsapp_bridge_provision.sh            # reconcile (start missing, stop orphaned)
#   whatsapp_bridge_provision.sh build      # (re)build the bridge image
#   whatsapp_bridge_provision.sh list       # show the derived mapping
#
# Requires: docker on the HOST, and the image built with `build`.
# ==============================================================================
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BRIDGE_DIR="${SCRIPT_DIR}/../src/services/whatsapp/bridge"
IMAGE="${MCP_WA_IMAGE:-mcp-whatsapp-bridge}"
BRIDGE_HOST="${WHATSAPP_BRIDGE_HOST:-127.0.0.1}"
MCP_DB="${MCP_DB:-${SCRIPT_DIR}/../data/mcp.db}"

sanitize() { # DNS/container-safe slug, matches src/services/whatsapp slug_for()
  local s
  s="$(printf '%s' "$1" | tr -cd 'a-zA-Z0-9' | tr 'A-Z' 'a-z')"
  [[ -z "$s" ]] && s="account"
  printf '%s' "$s"
}

port_for() { # deterministic port: 3001 + (sha1(slug) % 200)
  local s
  s="$(sanitize "$1")"
  local h
  h="$(printf '%s' "$s" | sha1sum | cut -c1-16)"
  printf '%s' "$((3001 + (0x${h:0:8} % 200)))"
}

accounts() { # instance_id list for service 'whatsapp'
  if [[ -f "$MCP_DB" ]]; then
    python3 - "$MCP_DB" <<'PY'
import sqlite3, sys
try:
    con = sqlite3.connect(sys.argv[1])
    for (i,) in con.execute("SELECT instance_id FROM service_instances WHERE service_id='whatsapp' AND enabled=1 ORDER BY id"):
        print(i)
except Exception:
    pass
PY
  fi
}

build_image() {
  echo "[+] Building image ${IMAGE} ..."
  docker build -t "${IMAGE}" "$BRIDGE_DIR"
  echo "[+] Done."
}

# Network shared with the MCP gateway so it can reach the bridge by container name.
MCP_NETWORK="${MCP_NETWORK:-mcp_default}"

start_one() {
  local id="$1"
  local slug; slug="$(sanitize "$id")"
  local port; port="$(port_for "$id")"
  local name="wa-$slug"
  local vol="wa-sess-$slug"
  if docker ps -a --format '{{.Names}}' | grep -qx "$name"; then
    echo "[i] ${name} already exists"
    docker start "$name" >/dev/null 2>&1 || true
    return
  fi
  echo "[+] Starting bridge '${name}' (${BRIDGE_HOST}:${port}) for account '${id}'"
  docker run -d --name "$name" \
    --restart unless-stopped \
    --network "$MCP_NETWORK" \
    --network-alias "$name" \
    -p "${port}:${port}" \
    -v "${vol}:/app/sessions" \
    "${IMAGE}" --port "$port" --session-dir /app/sessions \
    >/dev/null
}

stop_one() {
  local id="$1"
  local slug; slug="$(sanitize "$id")"
  local name="wa-$slug"
  echo "[-] Stopping bridge for account '${id}'"
  docker rm -f "$name" >/dev/null 2>&1 || true
}

reconcile() {
  local ids; ids="$(accounts)"
  declare -A wanted=()
  if [[ -n "$ids" ]]; then
    while IFS= read -r id; do
      [[ -z "$id" ]] && continue
      wanted["$(sanitize "$id")"]=1
      start_one "$id"
    done <<< "$ids"
  else
    echo "[i] No WhatsApp accounts configured."
  fi

  # Remove orphaned bridge containers whose account no longer exists (or is disabled).
  local name
  for name in $(docker ps -a --format '{{.Names}}' 2>/dev/null | grep '^wa-' || true); do
    local slug="${name#wa-}"
    if [[ -z "${wanted[$slug]:-}" ]]; then
      echo "[-] Removing orphaned bridge ${name}"
      docker rm -f "$name" >/dev/null 2>&1 || true
    fi
  done
}

case "${1:-reconcile}" in
  build) build_image ;;
  list)
    while IFS= read -r id; do
      [[ -n "$id" ]] && echo "wa-$(sanitize "$id") -> http://${BRIDGE_HOST:-wa-$(sanitize "$id")}:$(port_for "$id")"
    done < <(accounts)
    ;;
  stop-all)
    while IFS= read -r id; do [[ -n "$id" ]] && stop_one "$id"; done < <(accounts)
    ;;
  reconcile|*) reconcile ;;
esac
