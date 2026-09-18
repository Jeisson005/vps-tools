#!/usr/bin/env bash
# ==============================================================================
# Steel Browser - Session cleanup
# Libera sesiones Steel (status live/idle) más antiguas que MAX_AGE_SEC.
# NO reinicia contenedores con sesiones activas: respeta sesiones en vuelo.
# Al final puede reciclar workers vacíos (SingletonLock/zombies) vía
# recycle_workers.sh --force-empty (opt-out con STEEL_RECYCLE_EMPTY=false).
#
# Uso: cleanup_sessions.sh [--dry-run] [--max-age-sec N]
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

PORT="${STEEL_PORT:-3000}"
API="http://127.0.0.1:${PORT}"
KEY="${STEEL_API_KEY:-}"
MAX_AGE_SEC="${STEEL_SESSION_MAX_AGE_SEC:-86400}"
DRY_RUN="false"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --dry-run) DRY_RUN="true"; shift ;;
    --max-age-sec) MAX_AGE_SEC="${2:-86400}"; shift 2 ;;
    *) shift ;;
  esac
done

if [[ -z "${KEY}" ]]; then
  echo "[steel-cleanup] STEEL_API_KEY no configurada (${ENV_FILE})"
  exit 0
fi

RESP="$(curl -s --max-time 8 -H "x-steel-api-key: ${KEY}" "${API}/v1/sessions" 2>/dev/null)"
if [[ -z "${RESP}" ]]; then
  echo "[steel-cleanup] API no responde en ${API}"
  exit 0
fi

IDS="$(STEEL_JSON="${RESP}" STEEL_MAX_AGE="${MAX_AGE_SEC}" python3 - <<'PY'
import os, json, datetime
try:
    d = json.loads(os.environ["STEEL_JSON"])
except Exception:
    raise SystemExit(0)
max_age = int(os.environ.get("STEEL_MAX_AGE", "86400"))
now = datetime.datetime.now(datetime.timezone.utc)
for s in d.get("sessions", []):
    if s.get("status") not in ("live", "idle"):
        continue
    ca = s.get("createdAt")
    try:
        t = datetime.datetime.fromisoformat(str(ca).replace("Z", "+00:00"))
    except Exception:
        continue
    age = int((now - t).total_seconds())
    if age > max_age:
        print(s.get("id"), age)
PY
)"

if [[ -z "${IDS}" ]]; then
  echo "[steel-cleanup] sin sesiones > $((MAX_AGE_SEC / 3600))h (nada que liberar)"
else
  COUNT=0
  while read -r sid age; do
    [[ -z "${sid}" ]] && continue
    if [[ "${DRY_RUN}" == "true" ]]; then
      echo "[steel-cleanup] (dry-run) liberaría ${sid} (edad ${age}s)"
    elif curl -s --max-time 10 -X POST -H "x-steel-api-key: ${KEY}" \
        "${API}/v1/sessions/${sid}/release" >/dev/null 2>&1; then
      echo "[steel-cleanup] liberada ${sid} (edad ${age}s)"
    else
      echo "[steel-cleanup] fallo al liberar ${sid}"
    fi
    COUNT=$((COUNT + 1))
  done <<< "${IDS}"
  echo "[steel-cleanup] total: ${COUNT}"
fi

# Reciclar workers vacíos para limpiar SingletonLock/zombies (opt-out).
if [[ "${STEEL_RECYCLE_EMPTY:-true}" == "true" && "${DRY_RUN}" != "true" ]]; then
  if [[ -x "${SCRIPT_DIR}/recycle_workers.sh" ]]; then
    echo "[steel-cleanup] reciclando workers vacíos..."
    "${SCRIPT_DIR}/recycle_workers.sh" --force-empty 2>&1 | sed 's/^/[steel-recycle] /'
  else
    echo "[steel-cleanup] recycle_workers.sh no encontrado/ejecutable, se omite"
  fi
fi
