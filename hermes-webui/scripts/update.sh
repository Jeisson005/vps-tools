#!/usr/bin/env bash
# ==============================================================================
# Update Hermes WebUI Sofia (host-native): pull upstream, re-pin, re-brand, restart.
#
# Usage: sudo bash scripts/update.sh [--version exp-v0.52.314]
# Default pins the tested version. Pass --version main for latest upstream.
# The Sofia branding lives in server-only files (host checkout + settings.json),
# so it is re-applied here after every update. Project files are untouched.
# ==============================================================================

set -euo pipefail

BASE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${BASE_DIR}"

WEBUI_VERSION="exp-v0.52.314"
while [[ $# -gt 0 ]]; do
  case "$1" in
    --version) WEBUI_VERSION="${2:-}"; shift 2 ;;
    *) echo "[-] Unknown parameter: $1" >&2; exit 1 ;;
  esac
done

WEBUI_USER="${SUDO_USER:-$(id -un)}"
WEBUI_HOME="$(eval echo "~${WEBUI_USER}")"
WEBUI_SRC="${WEBUI_SRC_DIR:-${WEBUI_HOME}/hermes-webui}"

if [[ "${EUID}" -ne 0 ]]; then
  echo "[!] Run with sudo: sudo bash scripts/update.sh" >&2
  exit 1
fi

echo "[+] Updating ${WEBUI_SRC} -> ${WEBUI_VERSION} ..."
git -C "${WEBUI_SRC}" fetch --tags origin
sudo -u "${WEBUI_USER}" git -C "${WEBUI_SRC}" checkout "${WEBUI_VERSION}"

echo "[+] Re-applying Sofia branding (server-only) ..."
sudo -u "${WEBUI_USER}" python3 - "${WEBUI_SRC}" <<'PY'
import json, re, sys
src = sys.argv[1]

# 1. index.html: tab title, iOS web-app title, titlebar fallback
p = f"{src}/static/index.html"
s = open(p, encoding="utf-8").read()
s = s.replace("<title>Hermes</title>", "<title>Sofia</title>")
s = s.replace('content="Hermes">', 'content="Sofia">')
s = s.replace('id="appTitlebarTitle">Hermes<', 'id="appTitlebarTitle">Sofia<')
open(p, "w", encoding="utf-8").write(s)

# 2. manifest.json: PWA install name
p = f"{src}/static/manifest.json"
m = json.load(open(p, encoding="utf-8"))
if m.get("name") == "Hermes":
    m["name"] = "Sofia"
if m.get("short_name") == "Hermes":
    m["short_name"] = "Sofia"
if isinstance(m.get("description"), str) and m["description"].startswith("Hermes "):
    m["description"] = "Sofia " + m["description"][len("Hermes "):]
json.dump(m, open(p, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
open(p, "a", encoding="utf-8").write("\n")
print("[+] Branding applied: index.html + manifest.json")
PY

# 3. Persisted display name (env var is only the first-run default)
_SETTINGS="${WEBUI_HOME}/.hermes/webui/settings.json"
if [[ -f "${_SETTINGS}" ]]; then
  sudo -u "${WEBUI_USER}" python3 - "${_SETTINGS}" <<'PY'
import json, sys
p = sys.argv[1]
d = json.load(open(p, encoding="utf-8"))
if d.get("bot_name") != "Sofia":
    d["bot_name"] = "Sofia"
    json.dump(d, open(p, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    print("[+] settings.json bot_name -> Sofia")
else:
    print("[=] settings.json bot_name already Sofia")
PY
fi

echo "[+] Restarting hermes-webui ..."
systemctl restart hermes-webui.service
sleep 3
systemctl --no-pager status hermes-webui.service 2>&1 | head -n 8
