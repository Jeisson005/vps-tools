#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."

usage() {
  cat >&2 <<'EOF'
Usage:
  # Protect a specific domain or path with API Key authentication:
  bash scripts/auth_apikey.sh --domain example.com --key "secret_token_123"
  bash scripts/auth_apikey.sh --domain example.com --path /mcp --key "secret_token_123"

  # Auto-generate a secure random API key:
  bash scripts/auth_apikey.sh --domain example.com --path /mcp

Options:
  --domain <domain>   Domain name of the vhost (required)
  --path <path>       Specific location path (e.g. /mcp, /api, /v1)
  --key <api_key>     API Key to require (auto-generated if omitted)
  --name <id>         Custom identifier for snippet (default: derived from path/domain)
  -h, --help          Show this help message
EOF
}

DOMAIN=""
PATH_PREFIX=""
API_KEY=""
NAME=""

while [[ $# -gt 0 ]]; do
  case "$1" in
    --domain)
      DOMAIN="$2"; shift 2;;
    --path)
      PATH_PREFIX="$2"; shift 2;;
    --key)
      API_KEY="$2"; shift 2;;
    --name)
      NAME="$2"; shift 2;;
    -h|--help)
      usage; exit 0;;
    *)
      echo "Unknown argument: $1" >&2
      usage; exit 2;;
  esac
done

if [[ -z "$DOMAIN" ]]; then
  echo "Error: Missing --domain <domain>" >&2
  usage
  exit 1
fi

mkdir -p auth

# Generate random API key if not provided
if [[ -z "$API_KEY" ]]; then
  API_KEY="$(python3 -c "import secrets; print(secrets.token_urlsafe(24))")"
  echo "--> Auto-generated API Key: $API_KEY"
fi

# Save key to auth/ directory for reference
KEY_FILE="auth/${DOMAIN}.key"
if [[ -n "$PATH_PREFIX" ]]; then
  sanitized_path="$(echo "$PATH_PREFIX" | tr '/:' '__' | tr -cs 'a-zA-Z0-9._-' '_' | sed 's/^_\+//; s/_\+$//')"
  KEY_FILE="auth/${DOMAIN}.${sanitized_path}.key"
fi
echo "$API_KEY" > "$KEY_FILE"
chmod 600 "$KEY_FILE"
echo "--> API key saved to $KEY_FILE"

# Prepare API Key validation snippet
APIKEY_SNIPPET="  # API Key Authentication\n  set \$auth_apikey_ok 0;\n  if (\$http_x_api_key = \"${API_KEY}\") {\n    set \$auth_apikey_ok 1;\n  }\n  if (\$http_authorization = \"Bearer ${API_KEY}\") {\n    set \$auth_apikey_ok 1;\n  }\n  if (\$auth_apikey_ok = 0) {\n    add_header Content-Type application/json always;\n    return 401 '{\"error\": \"Unauthorized\", \"message\": \"Valid API Key required in X-API-Key or Authorization Bearer header\"}\\\\n';\n  }"

if [[ -n "$PATH_PREFIX" ]]; then
  sanitized_name="$(echo "$PATH_PREFIX" | tr '/:' '__' | tr -cs 'a-zA-Z0-9._-' '_' | sed 's/^_\+//; s/_\+$//')"
  loc_file="conf.d/${DOMAIN}.locations.${sanitized_name}.conf"
  
  if [[ -f "$loc_file" ]]; then
    if ! grep -q "auth_apikey_ok" "$loc_file"; then
      # Insert auth check inside location block
      sed -i "/location .* {/a \\${APIKEY_SNIPPET}" "$loc_file"
      echo "--> Attached API Key check to $loc_file"
    else
      echo "--> Note: Location $loc_file already contains API Key check."
    fi
  else
    echo "Note: Location file $loc_file not found. Creating it or run site_add.sh first."
  fi
else
  # Domain-level attachment: check HTTP and HTTPS configs
  for conf in "conf.d/${DOMAIN}.http.conf" "conf.d/${DOMAIN}.https.conf"; do
    if [[ -f "$conf" ]]; then
      if ! grep -q "auth_apikey_ok" "$conf"; then
        sed -i "/server {/a \\${APIKEY_SNIPPET}" "$conf"
        echo "--> Attached API Key check to $conf"
      fi
    fi
  done
fi

# Reload Nginx if container is running
if docker compose ps --services --filter "status=running" | grep -q "core"; then
  echo "--> Validating and reloading Nginx..."
  docker compose exec core nginx -t && docker compose exec core nginx -s reload
fi

echo ""
echo "==> API Key Protection Active for ${DOMAIN}${PATH_PREFIX:-/}"
echo "    Header required: 'X-API-Key: ${API_KEY}' or 'Authorization: Bearer ${API_KEY}'"
