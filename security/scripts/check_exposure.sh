#!/usr/bin/env bash
# ==============================================================================
# Security - Exposure audit (standalone, read-only)
# Answers: what is REACHABLE from the Internet (not just bound).
# Key subtlety: Docker published ports BYPASS UFW (DOCKER-USER chain), so a
# 0.0.0.0 docker-proxy listener is internet-reachable even with UFW default-deny.
# Host-process listeners obey UFW.
# Usage: check_exposure.sh <baseline_dir> <output_file>
# Exit 0 always. Verdicts: OK / REVIEW / FIREWALLED / EXPOSED-UNEXPECTED.
# ==============================================================================

set -u
BASELINE_DIR="${1:?baseline dir required}"
OUT_FILE="${2:?output file required}"
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
ALLOW_FILE="${BASELINE_DIR}/ports.allow"

SS="$(sudo -n ss -tlnp 2>/dev/null || ss -tln 2>/dev/null)"
SSU="$(sudo -n ss -ulnp 2>/dev/null || ss -uln 2>/dev/null)"
UFW="$(sudo -n ufw status 2>/dev/null || ufw status 2>/dev/null || echo 'ufw: unavailable')"

# Docker bypass active? (empty DOCKER-USER chain = published ports skip UFW)
DOCKER_BYPASS="no"
if sudo -n iptables -L DOCKER-USER -n 2>/dev/null | grep -qE '^(ACCEPT|DROP|REJECT|RETURN|LOG) '; then
  DOCKER_BYPASS="restricted"
else
  DOCKER_BYPASS="yes"
fi

# UFW ports explicitly open to the world (ALLOW IN Anywhere, with ranges)
UFW_WORLD=""
while read -r line; do
  line="$(echo "${line}" | tr -s ' ')"
  # numbered: "22/tcp ALLOW IN Anywhere" | plain: "22/tcp ALLOW Anywhere"
  if [[ "${line}" == *"ALLOW"*Anywhere* ]]; then
    spec="$(echo "${line}" | awk '{print $1}')"
    port="${spec%%/*}"; proto="$(echo "${spec}" | grep -oE '/(tcp|udp)' | tr -d '/' || echo tcp)"
    [[ -z "${proto}" ]] && proto="tcp"
    if [[ "${port}" == *:* ]]; then
      lo="${port%%:*}"; hi="${port##*:}"
      for ((p=lo; p<=hi; p++)); do UFW_WORLD="${UFW_WORLD} ${proto}/${p}"; done
    elif [[ "${port}" =~ ^[0-9]+$ ]]; then
      UFW_WORLD="${UFW_WORLD} ${proto}/${port}"
    fi
  fi
done <<< "${UFW}"

scope_of() { # $1=port -> scope or "none"
  local port="$1" s
  while read -r proto addr scope _rest; do
    [[ "${proto}" =~ ^#.*$ || -z "${proto}" ]] && continue
    local p="${addr##*:}"
    if [[ "${p}" == *-* ]]; then
      local lo="${p%-*}" hi="${p#*-}"
      if (( port >= lo && port <= hi )); then echo "${scope}"; return; fi
    elif [[ "${p}" == "*" || "${p}" == "${port}" ]]; then
      # '*' port only matches local scope (127.0.0.1:*); handled by caller
      if [[ "${p}" == "${port}" ]]; then echo "${scope}"; return; fi
    fi
  done < <(grep -vE '^\s*(#|$)' "${ALLOW_FILE}" | awk '{print $1, $2, $3}')
  echo "none"
}

{
echo "## Exposure audit: $(date -R) on $(hostname)"
echo ""
echo "Docker bypasses UFW (empty DOCKER-USER): ${DOCKER_BYPASS}"
echo "UFW world-open: $(echo "${UFW_WORLD}" | tr ' ' '\n' | grep -c . || echo 0) rules"
echo ""
echo "### Per-listener verdicts (public binds only)"
EXPOSED_UNEXPECTED=0
declare -A SEEN
while read -r laddr proc; do
  port="${laddr##*:}"
  [[ -z "${port}" || ! "${port}" =~ ^[0-9]+$ ]] && continue
  [[ -n "${SEEN[tcp/${port}]:-}" ]] && continue
  SEEN[tcp/"${port}"]=1
  scope="$(scope_of "${port}")"
  # Reachability
  reach="FIREWALLED"
  if [[ "${proc}" == *"docker-proxy"* ]]; then
    [[ "${DOCKER_BYPASS}" == "yes" ]] && reach="INTERNET (docker-published, bypasses UFW)"
  elif [[ " ${UFW_WORLD} " == *" tcp/${port} "* ]]; then
    reach="INTERNET (UFW ALLOW Anywhere)"
  fi
  owner="${proc}"
  [[ -z "${owner}" ]] && owner="?"
  case "${scope}:${reach}" in
    public:INTERNET*|firewalled:FIREWALLED|local:*)
      echo "OK [${scope}] tcp/${port} (${owner}) ${reach}" ;;
    review:*)
      echo "REVIEW [needs agent judgement] tcp/${port} (${owner}) ${reach}" ;;
    firewalled:INTERNET*)
      echo "FAIL [should be firewalled but is INTERNET-reachable!] tcp/${port} (${owner})" ;;
    public:FIREWALLED)
      echo "NOTE [allowlisted public but currently firewalled] tcp/${port} (${owner})" ;;
    *)
      if [[ "${reach}" == INTERNET* ]]; then
        echo "EXPOSED-UNEXPECTED [internet-reachable, NOT in baseline!] tcp/${port} (${owner})"
        EXPOSED_UNEXPECTED=$((EXPOSED_UNEXPECTED + 1))
      else
        echo "FIREWALLED-UNEXPECTED [bound publicly, firewalled, update baseline?] tcp/${port} (${owner})"
      fi ;;
  esac
done < <(echo "${SS}" | awk 'NR>1' | while read -r _ _ _ laddr rest; do
  case "${laddr}" in 0.0.0.0:*|\*:*|\[::\]:*) ;; *) continue ;; esac
  proc="$(echo "${rest}" | grep -oE '"[^"]+"' | head -1 | tr -d '"' || true)"
  echo "${laddr} ${proc:-?}"
done)

echo ""
echo "### Public UDP binds"
echo "${SSU}" | awk 'NR>1 {print $4}' | grep -oE '(0\.0\.0\.0|\*|\[::\]):[0-9]+' | sort -u || echo "(none)"
echo ""
echo "### Docker published ports (ALL bypass UFW while DOCKER-USER is empty)"
docker ps --format '{{.Names}} -> {{.Ports}}' 2>/dev/null | grep -E '0\.0\.0\.0' || echo "(none on 0.0.0.0)"
echo ""
echo "### Sensitive data ports publicly bound? (5432/6379/27017/27018/9200/11211)"
if docker ps --format '{{.Ports}}' 2>/dev/null | grep -qE '0\.0\.0\.0:(5432|6379|2701[78]|9200|11211)'; then
  echo "FAIL: database/cache port bound to 0.0.0.0!"
else
  echo "OK: no database/cache ports on 0.0.0.0"
fi
echo ""
echo "### Privileged / high-capability containers"
docker ps -q 2>/dev/null | while read -r c; do
  name="$(docker inspect "$c" --format '{{.Name}}' 2>/dev/null | tr -d /)"
  echo "$name privileged=$(docker inspect "$c" --format '{{.HostConfig.Privileged}}' 2>/dev/null) cap_add=$(docker inspect "$c" --format '{{.HostConfig.CapAdd}}' 2>/dev/null)"
done
echo ""
echo "### Public TLS certificates (via nginx server_names)"
DOMAINS="$(grep -rhoE 'server_name [^;]+;' "${REPO_ROOT}/nginx/" 2>/dev/null | sed 's/server_name//;s/;//' | tr ' ' '\n' | grep -E '\.' | grep -v '_' | sort -u | head -20)"
if [[ -z "${DOMAINS}" ]]; then
  echo "(no server_names found in nginx/, skipped)"
else
  for d in ${DOMAINS}; do
    END="$(echo | timeout 10 openssl s_client -connect 127.0.0.1:443 -servername "$d" 2>/dev/null | openssl x509 -noout -enddate 2>/dev/null | cut -d= -f2)"
    if [[ -n "${END}" ]]; then
      DAYS_LEFT=$(( ($(date -d "${END}" +%s 2>/dev/null || echo 0) - $(date +%s)) / 86400 ))
      echo "$d expires in ${DAYS_LEFT} days (${END})"
    else
      echo "$d: TLS probe failed"
    fi
  done
fi
echo ""
echo "EXPOSED_UNEXPECTED_COUNT=${EXPOSED_UNEXPECTED}"
} > "${OUT_FILE}" 2>&1

cat "${OUT_FILE}"
