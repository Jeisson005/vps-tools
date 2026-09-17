#!/usr/bin/env bash
# One-shot login helper for the NotebookLM MCP gateway account.
#
# Runs INSIDE the throwaway `notebooklm-login` container (compose profile "login"),
# never as part of the always-on `mcp-gateway` service:
#
#   docker compose --profile login run --rm notebooklm-login
#
# It opens a Chromium window on a virtual X display (Xvfb) so Google's sign-in does
# not see a headless browser, waits for the human to finish password + 2FA, and lets
# the CLI write storage_state.json *itself* into the shared profile on the data
# volume. Nothing is exported, copied or pasted: the login and the CLI are the same
# tool in the same filesystem, which is what keeps the session valid (Google revokes
# jars copied between clients, especially after a 2FA step-up).
#
# Env: NOTEBOOKLM_PROFILE (default personal), NOTEBOOKLM_LOGIN_TIMEOUT (default 600),
#      LOGIN_VNC=1 to also expose the virtual screen on :5900 (loopback), LOGIN_SHOTS=1
#      to keep grabbing /app/data/login-shots/*.png so the agent can forward a capture
#      when the flow needs something only a human can read (captcha).
set -euo pipefail

PROFILE="${NOTEBOOKLM_PROFILE:-personal}"
TIMEOUT="${NOTEBOOKLM_LOGIN_TIMEOUT:-600}"
DATA_DIR="${MCP_DATA_DIR:-/app/data}"
PROFILE_DIR="${DATA_DIR}/notebooklm/profiles/${PROFILE}"
SHOT_DIR="${DATA_DIR}/login-shots"

echo "== NotebookLM login (profile: ${PROFILE}) =="
echo "profile dir: ${PROFILE_DIR}"
command -v Xvfb >/dev/null 2>&1 || { echo "!! Xvfb no está instalado en esta imagen"; exit 1; }
command -v notebooklm >/dev/null 2>&1 || { echo "!! el binario notebooklm no está en esta imagen"; exit 1; }
if [ -f "${PROFILE_DIR}/storage_state.json" ]; then
  echo "-- ya existe una sesión guardada; se reemplazará si el login termina bien"
fi

mkdir -p "${PROFILE_DIR}" "${SHOT_DIR}"
chmod 700 "${PROFILE_DIR}" 2>/dev/null || true

export DISPLAY=":99"
rm -f /tmp/.X99-lock 2>/dev/null || true
Xvfb "${DISPLAY}" -screen 0 1440x900x24 -nolisten tcp >/tmp/xvfb.log 2>&1 &
XVFB_PID=$!
sleep 2

if [ "${LOGIN_VNC:-0}" = "1" ]; then
  x11vnc -display "${DISPLAY}" -forever -shared -rfbport 5900 -localhost -nopw >/tmp/x11vnc.log 2>&1 &
  echo "-- x11vnc escuchando en 127.0.0.1:5900 (túnel/ssh -L para verlo)"
fi

if [ "${LOGIN_SHOTS:-0}" = "1" ]; then
  (
    for i in $(seq 1 120); do
      sleep 5
      xwd -root -display "${DISPLAY}" 2>/dev/null | convert xwd:- "${SHOT_DIR}/shot-$(printf '%03d' "$i").png" 2>/dev/null || true
    done
  ) &
fi

echo "-- abriendo navegador (ventana virtual). Completa el login de Google;"
echo "-- cuando el CLI detecte la sesión, este contenedor termina solo."
echo

set +e
notebooklm -p "${PROFILE}" login --browser-timeout "${TIMEOUT}"
rc=$?
set -e

if [ $rc -ne 0 ]; then
  echo
  echo "!! el login terminó con código ${rc}."
  echo "   Si Google rechazó el navegador (\"este navegador o app puede no ser seguro\"),"
  echo "   revisa una captura de la pantalla virtual:  ${SHOT_DIR}"
  echo "   o reejecuta con LOGIN_VNC=1 y míralo por VNC."
  kill "${XVFB_PID}" 2>/dev/null || true
  exit $rc
fi

echo
echo "== sesión guardada =="
ls -l "${PROFILE_DIR}/storage_state.json" 2>/dev/null || echo "!! no se encontró storage_state.json"
echo "El contenedor del gateway usará esa sesión tal cual (sin export, sin copias)."
echo "Verifica con: curl -s -X POST http://127.0.0.1:8005/api/admin/services/notebooklm/test"
kill "${XVFB_PID}" 2>/dev/null || true
