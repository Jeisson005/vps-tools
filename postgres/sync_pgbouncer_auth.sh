#!/usr/bin/env bash
set -e

# Load env vars to get user/db
if [ -f .env ]; then
  set -a; source .env; set +a
fi

echo "Extracting SCRAM verifier for '$POSTGRES_USER' from Postgres container..."

# Extract formatted line: "username" "password_hash"
# Requires Postgres to be running and healthy
VERIFIER=$(docker compose exec -T db psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -At -c "SELECT '\"' || usename || '\" \"' || passwd || '\"' FROM pg_shadow WHERE usename = '$POSTGRES_USER';")

if [ -z "$VERIFIER" ]; then
  echo "Error: Could not retrieve verifier. Is the db service running?"
  exit 1
fi

echo "$VERIFIER" > pgbouncer/userlist.txt
echo "Updated pgbouncer/userlist.txt with:"
echo "$VERIFIER"

echo "Restarting PgBouncer to apply changes..."
docker compose restart pgbouncer
echo "Done! PgBouncer should now support SCRAM auth."
