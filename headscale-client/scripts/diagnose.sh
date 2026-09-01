#!/usr/bin/env bash
# ==============================================================================
# Robust Network & DPI Blocking Diagnostic Engine
# Layer 1 (DNS) -> Layer 2 (TCP) -> Layer 3 (TLS / SNI) -> Layer 4 (HTTP)
# ==============================================================================
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CLIENT_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"

DEFAULT_LIST="${CLIENT_DIR}/domains.default.txt"
CUSTOM_LIST="${CLIENT_DIR}/domains.custom.txt"

# Colors
C_GREEN="\e[32m"
C_RED="\e[31m"
C_YELLOW="\e[33m"
C_BLUE="\e[34m"
C_CYAN="\e[36m"
C_BOLD="\e[1m"
C_RESET="\e[0m"

JSON_MODE=false
FILTER_CAT=""
CUSTOM_TARGET=""

# Parse arguments
while [[ $# -gt 0 ]]; do
  case "$1" in
    --json)
      JSON_MODE=true
      shift
      ;;
    --category|-c)
      FILTER_CAT="$2"
      shift 2
      ;;
    --help|-h)
      echo "Uso: $0 [opciones] [dominio_especifico]"
      echo ""
      echo "Opciones:"
      echo "  --json             Salida en formato JSON para APIs y herramientas"
      echo "  --category <cat>   Filtrar por categoría (Core, Mensajería, Redes Sociales, Streaming, etc.)"
      echo "  <dominio>          Diagnosticar un único dominio específico"
      exit 0
      ;;
    *)
      CUSTOM_TARGET="$1"
      shift
      ;;
  esac
done

# Function to test a single domain
# Returns: dns_status|tcp_status|tls_status|http_code|time_ms|verdict
test_domain() {
  local DOMAIN="$1"
  local DNS_STATUS="FAIL"
  local TCP_STATUS="FAIL"
  local TLS_STATUS="FAIL"
  local HTTP_CODE="000"
  local TOTAL_TIME="0"
  local VERDICT="DESCONOCIDO"

  # 1. Layer 1: DNS Check
  local RESOLVED_IP=""
  if command -v getent >/dev/null 2>&1; then
    RESOLVED_IP=$(getent hosts "${DOMAIN}" 2>/dev/null | awk '{print $1}' | head -n 1 || true)
  elif command -v host >/dev/null 2>&1; then
    RESOLVED_IP=$(host "${DOMAIN}" 2>/dev/null | grep "has address" | awk '{print $4}' | head -n 1 || true)
  fi

  if [[ -n "${RESOLVED_IP}" ]]; then
    DNS_STATUS="OK"
  fi

  # 2. Layer 2: TCP Check (port 443)
  if [[ "${DNS_STATUS}" == "OK" ]]; then
    if nc -z -w 3 "${DOMAIN}" 443 >/dev/null 2>&1 || (timeout 3 bash -c "</dev/tcp/${DOMAIN}/443" >/dev/null 2>&1); then
      TCP_STATUS="OK"
    fi
  fi

  # 3. Layer 3: TLS / SNI Handshake Check (Detects DPI tampering / TLS Reset)
  if [[ "${TCP_STATUS}" == "OK" ]]; then
    local TLS_CHECK
    TLS_CHECK=$(timeout 4 openssl s_client -connect "${DOMAIN}:443" -servername "${DOMAIN}" </dev/null 2>&1 || true)
    if echo "${TLS_CHECK}" | grep -q "Verify return code: 0\|CONNECTED"; then
      TLS_STATUS="OK"
    elif echo "${TLS_CHECK}" | grep -qi "handshake failure\|connection reset\|reset by peer"; then
      TLS_STATUS="DPI_RESET"
    else
      TLS_STATUS="WARN"
    fi
  fi

  # 4. Layer 4: HTTP Status & Latency Check
  if [[ "${TCP_STATUS}" == "OK" ]]; then
    local CURL_OUT
    CURL_OUT=$(curl -Is --connect-timeout 4 --max-time 6 -A "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36" \
      "https://${DOMAIN}" -w "%{http_code}|%{time_total}" -o /dev/null 2>/dev/null || echo "000|0")

    HTTP_CODE=$(echo "${CURL_OUT}" | cut -d'|' -f1)
    TOTAL_TIME=$(echo "${CURL_OUT}" | cut -d'|' -f2)
    # Convert seconds to ms
    TOTAL_TIME=$(awk -v t="${TOTAL_TIME}" 'BEGIN { printf "%.0f", t * 1000 }')
  fi

  # Verdict determination
  if [[ "${DNS_STATUS}" == "FAIL" ]]; then
    VERDICT="BLOQUEO_DNS"
  elif [[ "${TCP_STATUS}" == "FAIL" ]]; then
    VERDICT="BLOQUEO_TCP"
  elif [[ "${TLS_STATUS}" == "DPI_RESET" ]]; then
    VERDICT="BLOQUEO_DPI"
  elif [[ "$HTTP_CODE" =~ ^(200|301|302|307|308|403|404|401)$ ]]; then
    VERDICT="LIBRE"
  else
    VERDICT="RESTRINGIDO"
  fi

  echo "${DNS_STATUS}|${TCP_STATUS}|${TLS_STATUS}|${HTTP_CODE}|${TOTAL_TIME}|${VERDICT}|${RESOLVED_IP}"
}

# Collect target domains
declare -a DOMAIN_LIST=()
if [[ -n "${CUSTOM_TARGET}" ]]; then
  DOMAIN_LIST+=("${CUSTOM_TARGET}|${CUSTOM_TARGET}|Personalizado")
else
  # Load default list
  if [[ -f "${DEFAULT_LIST}" ]]; then
    while IFS= read -r line || [[ -n "$line" ]]; do
      [[ -z "$line" || "$line" =~ ^# ]] && continue
      DOMAIN_LIST+=("$line")
    done < "${DEFAULT_LIST}"
  fi

  # Load custom list if exists
  if [[ -f "${CUSTOM_LIST}" ]]; then
    while IFS= read -r line || [[ -n "$line" ]]; do
      [[ -z "$line" || "$line" =~ ^# ]] && continue
      DOMAIN_LIST+=("$line")
    done < "${CUSTOM_LIST}"
  fi
fi

# Run diagnostics
if [[ "${JSON_MODE}" == "true" ]]; then
  RESULTS_JSON="[]"
  for item in "${DOMAIN_LIST[@]}"; do
    IFS='|' read -r DOMAIN NAME CAT <<< "${item}"
    if [[ -n "${FILTER_CAT}" && "${FILTER_CAT}" != "${CAT}" ]]; then
      continue
    fi
    RES=$(test_domain "${DOMAIN}")
    IFS='|' read -r D_DNS D_TCP D_TLS D_HTTP D_TIME D_VERDICT D_IP <<< "${RES}"

    ENTRY=$(cat <<EOF
{
  "domain": "${DOMAIN}",
  "name": "${NAME}",
  "category": "${CAT}",
  "ip": "${D_IP}",
  "dns": "${D_DNS}",
  "tcp": "${D_TCP}",
  "tls": "${D_TLS}",
  "http_code": "${D_HTTP}",
  "latency_ms": ${D_TIME},
  "verdict": "${D_VERDICT}"
}
EOF
)
    if command -v jq >/dev/null 2>&1; then
      RESULTS_JSON=$(jq ". += [${ENTRY}]" <<< "${RESULTS_JSON}")
    fi
  done
  echo "${RESULTS_JSON}"
  exit 0
fi

# CLI Formatted Output
echo -e "${C_BOLD}======================================================================================${C_RESET}"
echo -e "${C_BOLD}                   MOTOR AVANZADO DE DIAGNÓSTICO DE RED Y DPI                          ${C_RESET}"
echo -e "${C_BOLD}======================================================================================${C_RESET}"
printf "%-22s | %-12s | %-6s | %-6s | %-6s | %-8s | %-8s | %-12s\n" "Servicio / Dominio" "Categoría" "DNS" "TCP" "TLS" "HTTP" "Latencia" "Veredicto"
echo "--------------------------------------------------------------------------------------"

TOTAL_COUNT=0
FREE_COUNT=0
BLOCKED_COUNT=0

for item in "${DOMAIN_LIST[@]}"; do
  IFS='|' read -r DOMAIN NAME CAT <<< "${item}"
  if [[ -n "${FILTER_CAT}" && "${FILTER_CAT}" != "${CAT}" ]]; then
    continue
  fi
  TOTAL_COUNT=$((TOTAL_COUNT + 1))
  
  RES=$(test_domain "${DOMAIN}")
  IFS='|' read -r D_DNS D_TCP D_TLS D_HTTP D_TIME D_VERDICT D_IP <<< "${RES}"

  # Format DNS
  if [[ "${D_DNS}" == "OK" ]]; then S_DNS="${C_GREEN}OK${C_RESET}"; else S_DNS="${C_RED}FAIL${C_RESET}"; fi
  # Format TCP
  if [[ "${D_TCP}" == "OK" ]]; then S_TCP="${C_GREEN}OK${C_RESET}"; else S_TCP="${C_RED}FAIL${C_RESET}"; fi
  # Format TLS
  if [[ "${D_TLS}" == "OK" ]]; then S_TLS="${C_GREEN}OK${C_RESET}"; elif [[ "${D_TLS}" == "DPI_RESET" ]]; then S_TLS="${C_RED}DPI${C_RESET}"; else S_TLS="${C_YELLOW}${D_TLS}${C_RESET}"; fi
  # Format HTTP
  if [[ "${D_HTTP}" != "000" ]]; then S_HTTP="${C_GREEN}${D_HTTP}${C_RESET}"; else S_HTTP="${C_RED}---${C_RESET}"; fi

  # Format Verdict
  case "${D_VERDICT}" in
    LIBRE)
      S_VERDICT="${C_GREEN}🟢 LIBRE${C_RESET}"
      FREE_COUNT=$((FREE_COUNT + 1))
      ;;
    BLOQUEO_DNS)
      S_VERDICT="${C_RED}🔴 DNS${C_RESET}"
      BLOCKED_COUNT=$((BLOCKED_COUNT + 1))
      ;;
    BLOQUEO_TCP)
      S_VERDICT="${C_RED}🔴 FIREWALL${C_RESET}"
      BLOCKED_COUNT=$((BLOCKED_COUNT + 1))
      ;;
    BLOQUEO_DPI)
      S_VERDICT="${C_YELLOW}⚠️ DPI/SNI${C_RESET}"
      BLOCKED_COUNT=$((BLOCKED_COUNT + 1))
      ;;
    *)
      S_VERDICT="${C_YELLOW}🟡 RESTRINGIDO${C_RESET}"
      BLOCKED_COUNT=$((BLOCKED_COUNT + 1))
      ;;
  esac

  printf "%-22s | %-12s | %-15b | %-15b | %-15b | %-17b | %-6sms | %-20b\n" \
    "${NAME:0:22}" "${CAT:0:12}" "${S_DNS}" "${S_TCP}" "${S_TLS}" "${S_HTTP}" "${D_TIME}" "${S_VERDICT}"
done

echo "--------------------------------------------------------------------------------------"
echo -e "Total evaluados: ${TOTAL_COUNT} | ${C_GREEN}Libres: ${FREE_COUNT}${C_RESET} | ${C_RED}Bloqueados/Restringidos: ${BLOCKED_COUNT}${C_RESET}"
echo -e "${C_BOLD}======================================================================================${C_RESET}"
