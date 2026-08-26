#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."

usage() {
  cat >&2 <<'EOF'
Usage:
  # 1. Create or add user/password to an htpasswd file in auth/:
  bash scripts/auth_basic.sh --file myapp --user admin --password secret

  # 2. Add user and automatically protect a domain or specific path location:
  bash scripts/auth_basic.sh --domain example.com --user admin --password secret
  bash scripts/auth_basic.sh --domain example.com --path /mcp --user admin --password secret

Options:
  --file <name>       Name of htpasswd file inside auth/ (default: domain name or 'global')
  --domain <domain>   Domain name of the vhost
  --path <path>       Specific location path (e.g. /mcp, /api, /admin)
  --user <username>   Username to add
  --password <pass>   Password (if omitted, will prompt securely)
  --realm <text>      Realm message (default: "Restricted Access")
  -h, --help          Show this help message
EOF
}

FILE_NAME=""
DOMAIN=""
PATH_PREFIX=""
USER_NAME=""
PASSWORD=""
REALM="Restricted Access"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --file)
      FILE_NAME="$2"; shift 2;;
    --domain)
      DOMAIN="$2"; shift 2;;
    --path)
      PATH_PREFIX="$2"; shift 2;;
    --user)
      USER_NAME="$2"; shift 2;;
    --password)
      PASSWORD="$2"; shift 2;;
    --realm)
      REALM="$2"; shift 2;;
    -h|--help)
      usage; exit 0;;
    *)
      echo "Unknown argument: $1" >&2
      usage; exit 2;;
  esac
done

if [[ -z "$USER_NAME" ]]; then
  echo "Error: Missing --user <username>" >&2
  usage
  exit 1
fi

if [[ -z "$FILE_NAME" ]]; then
  if [[ -n "$DOMAIN" ]]; then
    FILE_NAME="$DOMAIN"
  else
    FILE_NAME="global"
  fi
fi

# Ensure extension .htpasswd
if [[ "$FILE_NAME" != *.htpasswd ]]; then
  HTPASSWD_FILE="${FILE_NAME}.htpasswd"
else
  HTPASSWD_FILE="$FILE_NAME"
fi

mkdir -p auth

# Prompt for password if not provided
if [[ -z "$PASSWORD" ]]; then
  read -s -rp "Enter password for '$USER_NAME': " PASSWORD
  echo ""
fi

# Generate APR1-MD5 / SHA-512 compatible htpasswd entry using python
python3 - <<EOF
import sys, os, hashlib, base64

username = "$USER_NAME"
password = "$PASSWORD"
htpasswd_path = "auth/$HTPASSWD_FILE"

# Use crypt / apr1 or SSHA format compatible with Nginx
def get_apr1_hash(user, password):
    try:
        from passlib.apache import HtpasswdFile
        ht = HtpasswdFile()
        ht.set_password(user, password)
        return ht.to_string().decode('utf-8').strip()
    except ImportError:
        # Fallback to standard SHA-1 hash supported natively by Nginx {SHA}
        # Format: username:{SHA}base64(sha1(password))
        digest = hashlib.sha1(password.encode('utf-8')).digest()
        b64 = base64.b64encode(digest).decode('ascii')
        return f"{username}:{{SHA}}{b64}"

new_entry = get_apr1_hash(username, password)

# Read existing entries and update/append
entries = []
if os.path.exists(htpasswd_path):
    with open(htpasswd_path, 'r') as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith(f"{username}:"):
                entries.append(line)

entries.append(new_entry)

with open(htpasswd_path, 'w') as f:
    f.write('\n'.join(entries) + '\n')

print(f"--> User '{username}' saved to {htpasswd_path}")
EOF

# If domain or path specified, ensure auth snippet is attached to location
if [[ -n "$DOMAIN" ]]; then
  echo "--> Attaching Basic Auth to Nginx configuration..."
  
  AUTH_CONF_SNIPPET="auth_basic \"${REALM}\";\n  auth_basic_user_file /etc/nginx/auth/${HTPASSWD_FILE};"

  if [[ -n "$PATH_PREFIX" ]]; then
    # Sanitize name
    sanitized_name="$(echo "$PATH_PREFIX" | tr '/:' '__' | tr -cs 'a-zA-Z0-9._-' '_' | sed 's/^_\+//; s/_\+$//')"
    loc_file="conf.d/${DOMAIN}.locations.${sanitized_name}.conf"
    
    if [[ -f "$loc_file" ]]; then
      if ! grep -q "auth_basic" "$loc_file"; then
        # Insert auth directives inside location block
        sed -i "/location .* {/a \  ${AUTH_CONF_SNIPPET}" "$loc_file"
        echo "--> Attached Basic Auth to $loc_file"
      fi
    else
      echo "Note: Location file $loc_file not found yet. Run site_add.sh first or create it."
    fi
  else
    # Domain-level attachment: check HTTP and HTTPS configs
    for conf in "conf.d/${DOMAIN}.http.conf" "conf.d/${DOMAIN}.https.conf"; do
      if [[ -f "$conf" ]]; then
        if ! grep -q "auth_basic" "$conf"; then
          sed -i "/server {/a \  ${AUTH_CONF_SNIPPET}" "$conf"
          echo "--> Attached Basic Auth to $conf"
        fi
      fi
    done
  fi

  # Reload Nginx if container is running
  if docker compose ps --services --filter "status=running" | grep -q "core"; then
    echo "--> Validating and reloading Nginx..."
    docker compose exec core nginx -t && docker compose exec core nginx -s reload
  fi
fi

echo "--> HTTP Basic Auth configuration complete."
