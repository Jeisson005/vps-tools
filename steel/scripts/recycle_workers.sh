#!/usr/bin/env bash
# ==============================================================================
# Steel Browser - Worker recycling
#
# Steel auto-hospedado lanza 1 navegador por instancia; al liberar una sesión
# el proceso Chromium puede quedar colgado y dejar /tmp/steel-chrome/SingletonLock,
# lo que inutiliza la instancia hasta reiniciarla. Este script reinicia el worker
# SOLO cuando no tiene sesiones activas y:
#   - su API no responde, o
#   - acumula más de STEEL_RECYCLE_ZOMBIE_THRESHOLD zombies, o
#   - se pasa --force-empty (reciclado nocturno).
#
# Uso: recycle_workers.sh [--force-empty] [--dry-run]
# ==============================================================================
set -u

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
STEEL_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
ENV_FILE="${STEEL_ENV:-${STEEL_DIR}/.env}"

if [[ -f "${ENV_FILE}" ]]; then
  set -a
  # shellcheck disable=SC1090
  . "${ENV_FILE}"
  set +a
fi

KEY="${STEEL_API_KEY:-}"
WORKERS="${STEEL_WORKERS:-steel-browser-1:3001 steel-browser-2:3002 steel-browser-3:3003}"
THRESHOLD="${STEEL_RECYCLE_ZOMBIE_THRESHOLD:-20}"
FORCE="false"
DRY_RUN="false"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --force-empty) FORCE="true"; shift ;;
    --dry-run) DRY_RUN="true"; shift ;;
    *) shift ;;
  esac
done

count_active() {
  local port="$1" resp
  resp="$(curl -s --max-time 6 -H "x-steel-api-key: ${KEY}" "http://127.0.0.1:${port}/v1/sessions" 2>/dev/null)"
  if [[ -z "${resp}" ]]; then
    echo "down"
    return
  fi
  STEEL_JSON="${resp}" python3 - <<'PY'
import os, json
try:
    d = json.loads(os.environ["STEEL_JSON"])
except Exception:
    print("0")
    raise SystemExit(0)
# Solo `live` ocupa la instancia; Steel mantiene siempre una sesión placeholder `idle`.
print(sum(1 for s in d.get("sessions", []) if s.get("status") == "live"))
PY
}

count_zombies() {
  docker exec "$1" sh -c "ps -eo stat= 2>/dev/null | grep -c '^Z'" 2>/dev/null || echo 0
}

echo "[steel-recycle] inicio $(date '+%F %T') (force-empty=${FORCE}, umbral zombies=${THRESHOLD})"

for entry in ${WORKERS}; do
  name="${entry%%:*}"
  port="${entry##*:}"

  if ! docker inspect "${name}" >/dev/null 2>&1; then
    echo "  ${name}: omitido (contenedor inexistente)"
    continue
  fi
  if [[ "$(docker inspect -f '{{.State.Running}}' "${name}" 2>/dev/null)" != "true" ]]; then
    echo "  ${name}: omitido (detenido)"
    continue
  fi

  active="$(count_active "${port}")"

  if [[ "${active}" == "down" ]]; then
    echo "  ${name}: API no responde -> reciclando"
    if [[ "${DRY_RUN}" == "false" ]]; then
      docker restart "${name}" >/dev/null 2>&1 && echo "  ${name}: reiniciado" || echo "  ${name}: fallo al reiniciar"
    fi
    continue
  fi

  if [[ "${active}" -gt 0 ]]; then
    echo "  ${name}: omitido (${active} sesión(es) activa(s))"
    continue
  fi

  z="$(count_zombies "${name}")"
  z="${z:-0}"

  if [[ "${FORCE}" == "true" || "${z}" -gt "${THRESHOLD}" ]]; then
    echo "  ${name}: 0 activas, zombies=${z} -> reciclando"
    if [[ "${DRY_RUN}" == "false" ]]; then
      docker restart "${name}" >/dev/null 2>&1 && echo "  ${name}: reiniciado" || echo "  ${name}: fallo al reiniciar"
    fi
  else
    echo "  ${name}: sano (0 activas, zombies=${z})"
  fi
done

echo "[steel-recycle] fin $(date '+%F %T')"
