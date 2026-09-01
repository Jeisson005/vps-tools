#!/usr/bin/env bash
# ==============================================================================
# Helper to Manage Headscale Users / Namespaces
# ==============================================================================

set -euo pipefail

BASE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${BASE_DIR}"

ACTION="${1:-list}"
USERNAME="${2:-}"

case "${ACTION}" in
  create)
    if [[ -z "${USERNAME}" ]]; then
      echo "Usage: $0 create <username>"
      exit 1
    fi
    docker compose exec headscale headscale users create "${USERNAME}"
    ;;
  list)
    docker compose exec headscale headscale users list
    ;;
  delete)
    if [[ -z "${USERNAME}" ]]; then
      echo "Usage: $0 delete <username>"
      exit 1
    fi
    docker compose exec headscale headscale users destroy "${USERNAME}" --force
    ;;
  rename)
    NEWNAME="${3:-}"
    if [[ -z "${USERNAME}" || -z "${NEWNAME}" ]]; then
      echo "Usage: $0 rename <oldname> <newname>"
      exit 1
    fi
    docker compose exec headscale headscale users rename "${USERNAME}" "${NEWNAME}"
    ;;
  *)
    echo "Usage: $0 {create|list|delete|rename} [username] [newname]"
    exit 1
    ;;
esac
