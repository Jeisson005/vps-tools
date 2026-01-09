#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."

umask 077

usage() {
  cat <<'EOF'
Rotate Zitadel PAT files used by this repo.

This script does NOT create PATs via the Zitadel API.
Instead, it updates the local files and restarts the login service.

Why: PAT creation/rotation depends on your Zitadel permissions and API setup.
The safest approach is:
  1) Create new PAT(s) in the Zitadel Console (or your preferred provisioning method)
  2) Run this script to atomically replace the token file(s)

Usage:
  bash scripts/rotate_pats.sh --login-pat '...' [--admin-pat '...'] [--login-pat-path ./login-client.pat] [--admin-pat-path ./admin.pat]
  bash scripts/rotate_pats.sh --admin-pat '...' [--login-pat '...']

If you run the script without any token arguments, it will attempt to read default sources from
  ./login-client.pat and ./admin.pat (if present) and write them to the default destinations
  (`./login-client.pat` and `./admin.pat`).

Expiration behavior:
  When rotating tokens, the script calculates expiration timestamps (default: now + 1 year)
  and writes expiry metadata files next to the token files (e.g. `./login-client.pat.expiry`).
  It does NOT modify `./.env.core`.

Options:
  --login-pat            New PAT for login client (token string)
  --admin-pat            New PAT for admin machine (token string)
  --login-pat-file       Read new login PAT from this file (cannot be used with --login-pat)
  --admin-pat-file       Read new admin PAT from this file (cannot be used with --admin-pat)
  --login-pat-path       Path to write the login PAT (default: ./login-client.pat)
  --admin-pat-path       Path to write the admin PAT (default: ./admin.pat)
  --expiry-years N       Set expiry to now + N years (default: 1) for both PATs
  --login-expiry-years N Set expiry to now + N years for login PAT (overrides --expiry-years)
  --admin-expiry-years N Set expiry to now + N years for admin PAT (overrides --expiry-years)
  --expiry-date ISO8601  Set exact expiry date for both PATs (overrides years)
  --login-expiry-date ISO8601  Set exact expiry date for login PAT (overrides others)
  --admin-expiry-date ISO8601  Set exact expiry date for admin PAT (overrides others)
  --no-write-expiry      Do not write expiry metadata files next to the PATs
  --no-restart           Do not restart docker compose services
  --dry-run              Print what would be done without modifying files

Examples:
  bash scripts/rotate_pats.sh --login-pat "$NEW_LOGIN_PAT" --admin-pat "$NEW_ADMIN_PAT"
  bash scripts/rotate_pats.sh --login-pat-file ./login-client.pat --admin-pat-file ./admin.pat --expiry-years 2
  bash scripts/rotate_pats.sh --login-pat-file ./login-client.pat --login-expiry-years 3 --no-restart
EOF
}


login_pat=""
admin_pat=""
login_pat_file=""
admin_pat_file=""
login_pat_path="./login-client.pat"
admin_pat_path="./admin.pat"
no_restart="false"

# Expiry configuration (defaults)
expiry_years="1"
login_expiry_years=""
admin_expiry_years=""
expiry_date=""
login_expiry_date=""
admin_expiry_date=""
no_write_expiry="false"
dry_run="false"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --login-pat)
      login_pat="${2:-}"
      shift 2
      ;;
    --admin-pat)
      admin_pat="${2:-}"
      shift 2
      ;;
    --login-pat-file)
      login_pat_file="${2:-}"
      shift 2
      ;;
    --admin-pat-file)
      admin_pat_file="${2:-}"
      shift 2
      ;;
    --login-pat-path)
      login_pat_path="${2:-}"
      shift 2
      ;;
    --admin-pat-path)
      admin_pat_path="${2:-}"
      shift 2
      ;;
    --no-restart)
      no_restart="true"
      shift
      ;;
    --expiry-years)
      expiry_years="${2:-}"
      shift 2
      ;;
    --login-expiry-years)
      login_expiry_years="${2:-}"
      shift 2
      ;;
    --admin-expiry-years)
      admin_expiry_years="${2:-}"
      shift 2
      ;;
    --expiry-date)
      expiry_date="${2:-}"
      shift 2
      ;;
    --login-expiry-date)
      login_expiry_date="${2:-}"
      shift 2
      ;;
    --admin-expiry-date)
      admin_expiry_date="${2:-}"
      shift 2
      ;;
    --no-write-expiry)
      no_write_expiry="true"
      shift
      ;;
    --dry-run)
      dry_run="true"
      shift
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "Unknown argument: $1" >&2
      usage
      exit 2
      ;;
  esac

done

if [[ -n "$login_pat_file" && -n "$login_pat" ]]; then
  echo "Specify either --login-pat or --login-pat-file, not both" >&2
  exit 2
fi
if [[ -n "$admin_pat_file" && -n "$admin_pat" ]]; then
  echo "Specify either --admin-pat or --admin-pat-file, not both" >&2
  exit 2
fi

# Read tokens from files if requested
if [[ -n "$login_pat_file" ]]; then
  if [[ ! -f "$login_pat_file" ]]; then
    echo "Login PAT file not found: $login_pat_file" >&2
    exit 2
  fi
  login_pat="$(tr -d '\n' < "$login_pat_file")"
fi
if [[ -n "$admin_pat_file" ]]; then
  if [[ ! -f "$admin_pat_file" ]]; then
    echo "Admin PAT file not found: $admin_pat_file" >&2
    exit 2
  fi
  admin_pat="$(tr -d '\n' < "$admin_pat_file")"
fi

# If no tokens were provided via args or files, try to read defaults from repository root
if [[ -z "$login_pat" && -z "$admin_pat" && -z "$login_pat_file" && -z "$admin_pat_file" ]]; then
  default_login_src="./login-client.pat"
  default_admin_src="./admin.pat"
  found_default="false"

  if [[ -f "$default_login_src" ]]; then
    login_pat="$(tr -d '\n' < "$default_login_src")"
    echo "Read login PAT from $default_login_src" >&2
    found_default="true"
  fi
  if [[ -f "$default_admin_src" ]]; then
    admin_pat="$(tr -d '\n' < "$default_admin_src")"
    echo "Read admin PAT from $default_admin_src" >&2
    found_default="true"
  fi

  if [[ "$found_default" == "false" ]]; then
    echo "Nothing to rotate: provide --login-pat/--login-pat-file and/or --admin-pat/--admin-pat-file, or place token files in repository root (./login-client.pat and ./admin.pat)" >&2
    usage
    exit 2
  fi
fi

write_token_file() {
  local path="$1"
  local token="$2"

  tmp="${path}.tmp"
  printf '%s' "$token" > "$tmp"
  chmod 600 "$tmp" || true
  mv -f "$tmp" "$path"
}

if [[ -n "$login_pat" ]]; then
  echo "Updating $login_pat_path" >&2
  write_token_file "$login_pat_path" "$login_pat"
fi

if [[ -n "$admin_pat" ]]; then
  echo "Updating $admin_pat_path" >&2
  if [[ "$dry_run" == "true" ]]; then
    echo "Dry-run: would write admin PAT to $admin_pat_path" >&2
  else
    write_token_file "$admin_pat_path" "$admin_pat"
  fi
fi

compute_expiry_from_years() {
  local yrs="$1"
  # Use GNU date to compute UTC ISO8601
  date -u -d "+${yrs} years" '+%Y-%m-%dT%H:%M:%SZ'
}

write_expiry_file() {
  local token_path="$1"
  local expiry="$2"
  local expiry_path="${token_path}.expiry"

  if [[ "$dry_run" == "true" ]]; then
    echo "Dry-run: would write expiry $expiry to $expiry_path" >&2
    return
  fi

  tmp="${expiry_path}.tmp"
  printf '%s' "$expiry" > "$tmp"
  chmod 600 "$tmp" || true
  mv -f "$tmp" "$expiry_path"
  echo "Wrote expiry to $expiry_path" >&2
}

if [[ "$no_write_expiry" != "true" && "$dry_run" != "true" ]]; then
  echo "Calculating new expiration dates and writing expiry files..." >&2
fi

# Compute and write login expiry if login PAT was rotated
if [[ -n "$login_pat" ]]; then
  # Determine final expiry for login
  if [[ -n "$login_expiry_date" ]]; then
    final_login_expiry="$login_expiry_date"
  elif [[ -n "$login_expiry_years" ]]; then
    final_login_expiry="$(compute_expiry_from_years "$login_expiry_years")"
  elif [[ -n "$expiry_date" ]]; then
    final_login_expiry="$expiry_date"
  elif [[ -n "$expiry_years" ]]; then
    final_login_expiry="$(compute_expiry_from_years "$expiry_years")"
  else
    final_login_expiry="$(compute_expiry_from_years "1")"
  fi

  if [[ "$no_write_expiry" == "true" ]]; then
    echo "Skipping writing expiry for login PAT (no-write-expiry specified). Would set: $final_login_expiry" >&2
  else
    write_expiry_file "$login_pat_path" "$final_login_expiry"
  fi
fi

# Compute and write admin expiry if admin PAT was rotated
if [[ -n "$admin_pat" ]]; then
  if [[ -n "$admin_expiry_date" ]]; then
    final_admin_expiry="$admin_expiry_date"
  elif [[ -n "$admin_expiry_years" ]]; then
    final_admin_expiry="$(compute_expiry_from_years "$admin_expiry_years")"
  elif [[ -n "$expiry_date" ]]; then
    final_admin_expiry="$expiry_date"
  elif [[ -n "$expiry_years" ]]; then
    final_admin_expiry="$(compute_expiry_from_years "$expiry_years")"
  else
    final_admin_expiry="$(compute_expiry_from_years "1")"
  fi

  if [[ "$no_write_expiry" == "true" ]]; then
    echo "Skipping writing expiry for admin PAT (no-write-expiry specified). Would set: $final_admin_expiry" >&2
  else
    write_expiry_file "$admin_pat_path" "$final_admin_expiry"
  fi
fi

if [[ "$no_restart" == "true" ]]; then
  exit 0
fi

# Restart login so it re-reads the token file.
# Core does not need a restart for token rotation, but restarting login is cheap.
if docker compose ps --status=running --services 2>/dev/null | grep -q '^login$'; then
  docker compose restart login
else
  echo "login service is not running; skipping restart" >&2
fi
