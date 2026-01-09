#!/usr/bin/env bash
set -e

# Load env vars to get user/db
if [ -f .env ]; then
  set -a; source .env; set +a
fi

# Ensure the pgbouncer directory exists and userlist.txt is a file, not a directory
mkdir -p pgbouncer
if [ -d pgbouncer/userlist.txt ]; then
  echo "Warning: pgbouncer/userlist.txt is a directory. Removing it..."
  rm -rf pgbouncer/userlist.txt
fi
touch pgbouncer/userlist.txt

echo "Extracting SCRAM verifier for '$POSTGRES_USER' from Postgres container..."

# Extract formatted line: "username" "password_hash"
# We use the pgbouncer.get_auth function which is SECURITY DEFINER 
# and allows non-superusers to retrieve their own hash (or others they are granted).
VERIFIER=$(docker compose exec -T db psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -At -c "SELECT '\"' || username || '\" \"' || password || '\"' FROM pgbouncer.get_auth('$POSTGRES_USER');")

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
