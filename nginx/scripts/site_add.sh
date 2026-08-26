#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."

usage() {
  cat >&2 <<'EOF'
Usage:
  # Domain -> upstream (route /)
  bash scripts/site_add.sh --domain example.com --upstream host.docker.internal:9000
  bash scripts/site_add.sh --domain example.com --upstream-host 127.0.0.1 --upstream-port 5500

  # Path routing (same domain, multiple services by path)
  bash scripts/site_add.sh --domain example.com --path /app --upstream host.docker.internal:9001
  bash scripts/site_add.sh --domain example.com --path /api --name api --upstream-host host.docker.internal --upstream-port 9000

  # Protect with API Key:
  bash scripts/site_add.sh --domain example.com --path /mcp --upstream host.docker.internal:8001 --api-key "mysecretkey"

  # Protect with Basic Auth:
  bash scripts/site_add.sh --domain example.com --path /admin --upstream host.docker.internal:8080 --auth-user admin --auth-pass secret

Options:
  --domain <domain>         Domain name (default: localhost)
  --path <path>             Specific URL path (e.g. /app, /mcp)
  --name <id>               Identifier for location config snippet
  --upstream <url>          Upstream URL (e.g. http://host.docker.internal:8001)
  --upstream-host <host>    Upstream host (default: host.docker.internal)
  --upstream-port <port>    Upstream port
  --api-key <key>           Protect endpoint with API Key (X-API-Key or Bearer)
  --auth-user <user>        Protect endpoint with HTTP Basic Auth user
  --auth-pass <pass>        Password for HTTP Basic Auth user
  -h, --help                Show this help message
EOF
}

DOMAIN="localhost"
PATH_PREFIX=""
NAME=""
UPSTREAM_HOST="host.docker.internal"
UPSTREAM_PORT=""
UPSTREAM=""
API_KEY=""
AUTH_USER=""
AUTH_PASS=""

while [[ $# -gt 0 ]]; do
  case "$1" in
    --domain)
      DOMAIN="$2"; shift 2;;
    --path)
      PATH_PREFIX="$2"; shift 2;;
    --name)
      NAME="$2"; shift 2;;
    --upstream)
      UPSTREAM="$2"; shift 2;;
    --upstream-host)
      UPSTREAM_HOST="$2"; shift 2;;
    --upstream-port)
      UPSTREAM_PORT="$2"; shift 2;;
    --api-key)
      API_KEY="$2"; shift 2;;
    --auth-user)
      AUTH_USER="$2"; shift 2;;
    --auth-pass)
      AUTH_PASS="$2"; shift 2;;
    -h|--help)
      usage; exit 0;;
    *)
      echo "Unknown argument: $1" >&2
      usage
      exit 2;;
  esac
done

if [[ -n "$UPSTREAM" ]]; then
  # If upstream is provided as host:port without a scheme, normalize to http://host:port
  if [[ "$UPSTREAM" != http://* && "$UPSTREAM" != https://* ]]; then
    UPSTREAM="http://${UPSTREAM}"
  fi
else
  if [[ -z "$UPSTREAM_PORT" ]]; then
    echo "Missing --upstream or --upstream-port" >&2
    usage
    exit 2
  fi
  UPSTREAM="http://${UPSTREAM_HOST}:${UPSTREAM_PORT}"
fi

TEMPLATES_DIR="templates"
HTTP_TPL="${TEMPLATES_DIR}/server.http.conf"
HTTPS_TPL="${TEMPLATES_DIR}/server.https.conf"
LOCATION_TPL="${TEMPLATES_DIR}/location.proxy.conf"
RENDER="scripts/render_tpl.py"

if [[ ! -f "$HTTP_TPL" || ! -f "$HTTPS_TPL" || ! -f "$LOCATION_TPL" || ! -f "$RENDER" ]]; then
  echo "Missing templates or renderer in ${TEMPLATES_DIR}/ or scripts/render_tpl.py" >&2
  exit 1
fi

ACCESS_LOG_FILE="${DOMAIN}.access.log"
HTTP_CONF="conf.d/${DOMAIN}.http.conf"
HTTP_DISABLED_CONF="conf.d/${DOMAIN}.http.conf.disabled"
HTTPS_CONF="conf.d/${DOMAIN}.https.conf"
HTTPS_DISABLED_CONF="conf.d/${DOMAIN}.https.conf.disabled"

sanitize_name() {
  # Convert to a safe file identifier
  echo "$1" | tr '/:' '__' | tr -cs 'a-zA-Z0-9._-' '_' | sed 's/^_\+//; s/_\+$//'
}

make_default_location_proxy_root() {
  local upstream="$1"
  python3 "$RENDER" "$LOCATION_TPL" /dev/stdout "PATH=/" "UPSTREAM=${upstream}"
}

make_default_location_404() {
  cat <<'EOF'
location / {
  return 404;
}
EOF
}

ensure_base_servers_for_path_mode() {
  local include_glob="include /etc/nginx/conf.d/${DOMAIN}.locations.*.conf;"

  if [[ ! -f "$HTTP_CONF" && ! -f "$HTTP_DISABLED_CONF" ]]; then
    python3 "$RENDER" "$HTTP_TPL" "$HTTP_CONF" \
      "SERVER_NAME=${DOMAIN}" \
      "ACCESS_LOG_FILE=${ACCESS_LOG_FILE}" \
      "INCLUDE_LOCATIONS_GLOB=${include_glob}" \
      "DEFAULT_LOCATION_BLOCK=$(make_default_location_404)"
  fi

  if [[ ! -f "$HTTPS_DISABLED_CONF" && ! -f "$HTTPS_CONF" ]]; then
    python3 "$RENDER" "$HTTPS_TPL" "$HTTPS_DISABLED_CONF" \
      "SERVER_NAME=${DOMAIN}" \
      "ACCESS_LOG_FILE=${ACCESS_LOG_FILE}" \
      "INCLUDE_LOCATIONS_GLOB=${include_glob}" \
      "DEFAULT_LOCATION_BLOCK=$(make_default_location_404)"
  fi
}

add_path_location() {
  local path_prefix="$1"
  local upstream="$2"

  if [[ "$path_prefix" != /* ]]; then
    echo "--path must start with /" >&2
    exit 2
  fi

  if [[ -z "$NAME" ]]; then
    NAME="$(sanitize_name "$path_prefix")"
  fi

  local loc_file="conf.d/${DOMAIN}.locations.${NAME}.conf"
  if [[ -f "$loc_file" ]]; then
    echo "${loc_file} already exists" >&2
    exit 1
  fi

  python3 "$RENDER" "$LOCATION_TPL" "$loc_file" \
    "PATH=${path_prefix}" \
    "UPSTREAM=${upstream}"
}

create_domain_vhost_root_proxy() {
  if [[ -f "$HTTP_CONF" || -f "$HTTP_DISABLED_CONF" ]]; then
    echo "HTTP configuration already exists for ${DOMAIN}." >&2
    exit 1
  fi
  if [[ -f "$HTTPS_DISABLED_CONF" || -f "$HTTPS_CONF" ]]; then
    echo "HTTPS configuration (disabled/active) already exists for ${DOMAIN}." >&2
    exit 1
  fi

  python3 "$RENDER" "$HTTP_TPL" "$HTTP_CONF" \
    "SERVER_NAME=${DOMAIN}" \
    "ACCESS_LOG_FILE=${ACCESS_LOG_FILE}" \
    "INCLUDE_LOCATIONS_GLOB=" \
    "DEFAULT_LOCATION_BLOCK=$(make_default_location_proxy_root "$UPSTREAM")"

  python3 "$RENDER" "$HTTPS_TPL" "$HTTPS_DISABLED_CONF" \
    "SERVER_NAME=${DOMAIN}" \
    "ACCESS_LOG_FILE=${ACCESS_LOG_FILE}" \
    "INCLUDE_LOCATIONS_GLOB=" \
    "DEFAULT_LOCATION_BLOCK=$(make_default_location_proxy_root "$UPSTREAM")"
}

if [[ -n "$PATH_PREFIX" ]]; then
  ensure_base_servers_for_path_mode
  add_path_location "$PATH_PREFIX" "$UPSTREAM"
  echo "OK: added path ${DOMAIN}${PATH_PREFIX} -> ${UPSTREAM}"
else
  create_domain_vhost_root_proxy
  echo "OK: added domain ${DOMAIN} (/) -> ${UPSTREAM}"
fi

# Apply Authentication if requested
if [[ -n "$API_KEY" ]]; then
  echo "--> Applying API Key protection..."
  if [[ -n "$PATH_PREFIX" ]]; then
    bash scripts/auth_apikey.sh --domain "$DOMAIN" --path "$PATH_PREFIX" --key "$API_KEY"
  else
    bash scripts/auth_apikey.sh --domain "$DOMAIN" --key "$API_KEY"
  fi
fi

if [[ -n "$AUTH_USER" ]]; then
  echo "--> Applying Basic Auth protection..."
  if [[ -n "$PATH_PREFIX" ]]; then
    bash scripts/auth_basic.sh --domain "$DOMAIN" --path "$PATH_PREFIX" --user "$AUTH_USER" ${AUTH_PASS:+--password "$AUTH_PASS"}
  else
    bash scripts/auth_basic.sh --domain "$DOMAIN" --user "$AUTH_USER" ${AUTH_PASS:+--password "$AUTH_PASS"}
  fi
fi

# Validate and reload
docker compose up -d core

docker compose exec core nginx -t

docker compose exec core nginx -s reload
