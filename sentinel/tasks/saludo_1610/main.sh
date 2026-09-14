#!/usr/bin/env bash
# Saludo diario (lun-vie) a Claude Sonnet y Gemini 3.8 Flash.
# Versión Sentinel simplificada (sin aviso por Telegram).
set -u

DOCS="${DOCUMENTS_DIR:-/home/jeisson/Documents/Empty}"
CLAUDE_BIN="/home/jeisson/.local/bin/claude"
AGY_BIN="/home/jeisson/.local/bin/agy"

FECHA="$(date +'%A %d de %B de %Y')"
CLAUDE_MSG="Hola Claude 👋 Te saluda un amigo a través de Hermes. Hoy es ${FECHA}. Salúdame y dime la cartelera de cine de hoy: películas en cartelera y horarios que conozcas, en español y conciso."
AGY_MSG="Hola Gemini 👋 Te saluda un amigo a través de Hermes. Hoy es ${FECHA}. Salúdame y dime la cartelera de cine de hoy: películas en cartelera y horarios que conozcas, en español y conciso."

CLAUDE_OUT="$(cd "$DOCS" && "$CLAUDE_BIN" -p "$CLAUDE_MSG" --model sonnet --effort high 2>&1)"; CLR=$?
AGY_OUT="$(cd "$DOCS" && "$AGY_BIN" -p "$AGY_MSG" --model gemini-3.8-flash --effort low 2>&1)"; AG=$?

if [ "$CLR" -eq 0 ] && [ "$AG" -eq 0 ]; then
  echo "✅ Saludo completado exitosamente ($(date +'%F %H:%M:%S'))."
  exit 0
fi

echo "⚠️ No se pudo completar el saludo automático ($(date +'%F %H:%M:%S'))."
[ "$CLR" -ne 0 ] && { echo "[Claude] exit=${CLR}:"; printf '%s' "$CLAUDE_OUT" | tail -c 800; echo; }
[ "$AG" -ne 0 ] && { echo "[Gemini] exit=${AG}:"; printf '%s' "$AGY_OUT" | tail -c 800; echo; }
exit 1
