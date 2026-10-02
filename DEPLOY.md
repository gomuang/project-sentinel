# Deploying the Sentinel server

Do these steps in order. The important one is step 1: create the app's database role first and let
it create the tables. If `postgres` creates them instead, the app later fails with
`must be owner of table st_devices` (see [Fixing an existing install](#fixing-an-existing-install)).

## 1. Create the role and database (once, as `postgres`)

```bash
psql -U postgres -h localhost -d postgres
```

On a Mac with the EDB installer, `psql` is at `/Library/PostgreSQL/18/bin/psql`.

```sql
CREATE ROLE sentinel_user LOGIN PASSWORD 'choose-a-strong-password';
CREATE DATABASE sentinel_db OWNER sentinel_user;
```

That's the only step that needs `postgres`. `sentinel_user` is not a superuser; owning
`sentinel_db` lets it create everything else.

## 2. Configure `.env` (repo root)

```
DATABASE_URL=postgresql://sentinel_user:choose-a-strong-password@localhost:5432/sentinel_db
ENROLLMENT_SECRET=paste-a-generated-secret-here
```

- Plain `postgresql://`: no `jdbc:` prefix, no quotes.
- If the password has `@ : / #`, percent-encode it (`@` → `%40`, `#` → `%23`).
- Generate the secret with `python -c "import secrets; print(secrets.token_urlsafe(32))"`.
- `.env` is gitignored. Keep it that way.

## 3. Create the tables (as `sentinel_user`)

```bash
pip install fastapi uvicorn sqlalchemy psycopg2-binary python-dotenv
python init_db.py
```

`init_db.py` connects with `DATABASE_URL`, so it runs as `sentinel_user` and that role owns the
tables, the ID sequence and `usage_report()`. It's safe to re-run after every update.
Don't point `DATABASE_URL` at `postgres` to run it.

## 4. Run the API

```bash
uvicorn app.main:app --host 127.0.0.1 --port 8000
```

Leave off `--reload` outside development. Start it from the repo root so it finds `.env`.
It listens on localhost only; Caddy is the one door in, over HTTPS.

In `Caddyfile`, set the hostname to this server's DNS name and point `tls` at its certificate and
key (an internal CA that Jamf deploys to the Macs is fine). Then, from the repo root:

```bash
brew install caddy            # macOS; `apt install caddy` on Linux
caddy validate --config Caddyfile
caddy run --config Caddyfile
```

For a quick test without an issued certificate, change the `tls` line to `tls internal` and run
`sudo caddy trust` on each test Mac so the agent trusts Caddy's own CA.

## 5. Point the agents at it

Build the agent on a Mac. The binary is not kept in the repo, so it always matches the source:

```bash
swiftc -O clients/main.swift -o clients/sentinel_agent
```

In `clients/install_sentinel.zsh`, set `SERVER_URL` to `https://<this server's hostname>/api` and
`ENROLLMENT_SECRET` to the same value as in `.env`. Deliver it with Jamf (macOS). The agent picks
both up from its LaunchAgent and refuses to start on anything but an `https://` URL.

Macs installed from an older copy of this repo run a binary that still executes remote shell
commands. Reinstall them with a freshly built agent.

## 6. Check it

```bash
pip install httpx
python -m tests.test_auth
psql "$(grep '^DATABASE_URL' .env | cut -d= -f2-)" -v ON_ERROR_STOP=1 -f tests/test_usage_report.sql
psql "$(grep '^DATABASE_URL' .env | cut -d= -f2-)" -c "SELECT * FROM usage_report(current_date, current_date);"
```

The first should print `usage_report tests OK` (it rolls back everything it creates). After an
agent registers and you lock and unlock that Mac, the second shows one session.

## Fixing an existing install

If `postgres` created the tables (for example, `init_db.py` ran with a `postgres` URL), run this
once as `postgres` while connected to `sentinel_db`. It hands the database, every table (with its
sequence) and `usage_report()` to `sentinel_user`:

```sql
ALTER DATABASE sentinel_db OWNER TO sentinel_user;
DO $$
DECLARE r record;
BEGIN
    FOR r IN SELECT tablename FROM pg_tables WHERE schemaname = 'public' LOOP
        EXECUTE format('ALTER TABLE public.%I OWNER TO sentinel_user', r.tablename);
    END LOOP;
    FOR r IN SELECT p.oid::regprocedure AS fn FROM pg_proc p
             JOIN pg_namespace n ON n.oid = p.pronamespace WHERE n.nspname = 'public' LOOP
        EXECUTE format('ALTER FUNCTION %s OWNER TO sentinel_user', r.fn);
    END LOOP;
END $$;
```

If `sentinel_user` doesn't exist yet, create it first with the `CREATE ROLE` line from step 1.
Then `python init_db.py` works as `sentinel_user`.
