-- Setup for PgBouncer auth_query
-- This allows PgBouncer to look up user passwords without being a superuser.

CREATE SCHEMA IF NOT EXISTS pgbouncer;

-- Function must be SECURITY DEFINER to access pg_shadow (restricted in newer PG)
CREATE OR REPLACE FUNCTION pgbouncer.get_auth(p_usename text)
RETURNS TABLE(username text, password text) AS $$
BEGIN
    RETURN QUERY
    SELECT usename::text, passwd::text 
    FROM pg_catalog.pg_shadow
    WHERE usename = p_usename;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- IMPORTANT: By default, any user could call this and see hashes.
-- Revoke from public and grant only to the lookup user.
REVOKE ALL ON FUNCTION pgbouncer.get_auth(text) FROM PUBLIC;

-- Grant execution to the non-superuser (app user)
DO $$
DECLARE
    app_user text;
BEGIN
    -- We try to find the non-superuser created during init (POSTGRES_USER)
    SELECT usename INTO app_user 
    FROM pg_catalog.pg_user 
    WHERE usename != 'postgres' 
      AND usename NOT LIKE 'pg_%' 
    LIMIT 1;

    IF app_user IS NOT NULL THEN
        RAISE NOTICE 'Granting pgbouncer.get_auth permissions to user: %', app_user;
        EXECUTE format('GRANT USAGE ON SCHEMA pgbouncer TO %I', app_user);
        EXECUTE format('GRANT EXECUTE ON FUNCTION pgbouncer.get_auth(text) TO %I', app_user);
    ELSE
        RAISE WARNING 'No application user found to grant pgbouncer lookup permissions.';
    END IF;
END
$$;
