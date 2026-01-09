# Postgres (local compose)

Quick guide to deploy the Postgres + PgBouncer stack (SCRAM-SHA-256 auth recommended; PgBouncer configured for SCRAM).

## Prerequisites ✅
- Docker and Docker Compose (plugin) installed
- Copy the example environment and set credentials:
  - `cp .env.example .env`
  - Edit `.env` and set `POSTGRES_DB`, `POSTGRES_USER` and `POSTGRES_PASSWORD`
- This setup prefers SCRAM-SHA-256; see `pgbouncer/pgbouncer.ini` for auth options and the recommended `auth_user` + `auth_query`.  
- **Security:** do not commit real credentials; use Docker/Kubernetes secrets or a secret manager for production.

## First-time setup — Step by step 🔧

Follow these steps when you clone this repo for the first time in a new environment.

1) Configure environment

```bash
# Copy the example env and edit credentials
cp .env.example .env
# Edit .env and set: POSTGRES_DB, POSTGRES_USER, POSTGRES_PASSWORD
```
2) (Optional) Clean state — recommended on first run if you previously used another password

```bash
# Remove containers and named volumes created by this compose (DESTRUCTIVE)
docker compose down -v
```

3) Start services

```bash
docker compose up -d --build
```

4) Bootstrap PgBouncer auth (one-time after DB is ready)

```bash
# Extract SCRAM verifier and restart pgbouncer
bash sync_pgbouncer_auth.sh
```

5) Verify services and connections

```bash
# Check logs
docker compose logs --tail=200 pgbouncer
docker compose logs --tail=200 db

# Direct to Postgres
docker compose exec -T db psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -c '\conninfo'

# Through PgBouncer
docker compose exec -T db bash -lc "PGPASSWORD=$POSTGRES_PASSWORD psql -h pgbouncer -U $POSTGRES_USER -d $POSTGRES_DB -c '\\conninfo'"
```

6) If you change `POSTGRES_PASSWORD` after the DB has been initialized

- Either update the password inside Postgres:

```bash
docker compose exec -T db psql -U postgres -c "ALTER USER $POSTGRES_USER WITH PASSWORD '$POSTGRES_PASSWORD';"
```

- Or reinitialize the DB (destructive):

```bash
docker compose down -v && docker compose up -d --build
bash sync_pgbouncer_auth.sh
```


Notes:
- The `sync_pgbouncer_auth.sh` script extracts the SCRAM verifier for `$POSTGRES_USER` from Postgres and writes it to `pgbouncer/userlist.txt` (this is required so PgBouncer can bootstrap authentication). Keep the `userlist.txt` mount in `docker-compose.yml` so PgBouncer can read the verifier.
- For production, prefer `auth_user` + `auth_query` with a dedicated `pgbouncer_auth_user` and a `SECURITY DEFINER` helper function to avoid reading `pg_authid` directly.

## Useful commands ⚡
- Rebuild / restart the stack:
  - `docker compose up -d --build`
- Stop & remove containers + named volumes (clean start):
  - `docker compose down -v`
- Prefer `auth_user` + `auth_query` for PgBouncer authentication; if you change Postgres passwords, ensure PgBouncer can read updated verifiers and then restart PgBouncer if needed.

## Troubleshooting (short) 🛠️
- FATAL: unsupported startup parameter: extra_float_digits
  - Add to `pgbouncer/pgbouncer.ini`:
    `ignore_startup_parameters = extra_float_digits`
  - Then `docker compose restart pgbouncer`

- FATAL: password authentication failed
  - Ensure the password in `postgres/.env` matches the Postgres role password, and that PgBouncer auth method matches your Postgres auth (SCRAM vs MD5).
  - Prefer `auth_user` + `auth_query` (recommended) to avoid syncing static auth files.
  - To reset the environment (destructive): `docker compose down -v` then `docker compose up -d --build` (this will remove DB data).

---

That’s it — concise steps to bring up and verify the local Postgres + PgBouncer stack. If you want, I can add a quick `make` target to automate these steps next. 🚀