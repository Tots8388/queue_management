# Development setup

Local development for the Digital Queue & Patient-Flow Management System.
Source of truth for behaviour is [`../spec.md`](../spec.md).

## Prerequisites

- Python 3.12 or newer
- Node.js 20 or newer
- PostgreSQL 14+, either installed locally or run from
  [`../deploy/docker-compose.yml`](../deploy/docker-compose.yml) — see
  [Database](#database). The SQLite fallback exists but is prototype
  scaffolding, not a supported way to run the system.

## First-time setup

```bash
cp .env.example .env
```

Fill in `.env` locally. It is git-ignored and must never be committed. The only
value you must set to run the backend is `DJANGO_SECRET_KEY`; generate one with:

```bash
python -c "import secrets; print(secrets.token_urlsafe(50))"
```

### Backend

```bash
cd backend
python -m venv .venv
.venv\Scripts\activate        # Windows
source .venv/bin/activate     # macOS / Linux
pip install -r requirements.txt
python manage.py migrate
python manage.py runserver 0.0.0.0:8000
```

### Frontends

There are two: the **patient app** (`frontend/`, port 3000) with the landing
page, token entry, patient status and the waiting-room board, and the **staff
app** (`staff-frontend/`, port 3001) with the sign-in and the four dashboards.
Patients are only ever given the 3000 address, and nothing served there links
to or resolves a staff route.

They are npm workspaces of the repo root, so one install at the root covers
both. That is also what lets the components in `shared/ui/` — used by both
apps — resolve `react` and `next`: hoisting puts them on a path above the
shared directory.

```bash
npm install          # from the repo root, once, for both apps

cd frontend && npm run dev -- --port 3000        # patients
cd staff-frontend && npm run dev -- --port 3001  # staff
```

Or run both at once from the repo root with `start.bat`, and shut them down with
`stop.bat`. Both are Windows batch files — the clinic machine is the target
platform, so that is the only pair kept in sync.

## Database

**PostgreSQL is the target database** for both the pilot and any production use.
The audit and accountability requirements need durable, queryable, timestamped
records, and the spec fixes PostgreSQL as the decision.

Set `DATABASE_URL` in `.env`:

```text
DATABASE_URL=postgres://queue_user:PASSWORD@127.0.0.1:5432/queue_management
```

There are two ways to have a database behind that URL. Pick one.

#### Option A — the development container (no local install)

[`deploy/docker-compose.yml`](../deploy/docker-compose.yml) runs PostgreSQL 17
with a persistent named volume. Set `POSTGRES_DB`, `POSTGRES_USER`,
`POSTGRES_PASSWORD` and `POSTGRES_PORT` in `.env` to match `DATABASE_URL`, then:

```bash
docker compose --env-file .env -f deploy/docker-compose.yml up -d
```

`--env-file .env` is required — Compose would otherwise look for `deploy/.env`.
The port is published on `127.0.0.1` only; staff terminals reach the API, never
the database. `start.bat` brings this container up and waits for its healthcheck
before migrating, so it is not something to remember separately.

#### Option B — PostgreSQL installed natively

What the clinic server runs (see
[`operations/lan-deployment.md`](./operations/lan-deployment.md)). Create the
database once:

```bash
createdb queue_management
createuser queue_user --pwprompt
psql -c "GRANT ALL PRIVILEGES ON DATABASE queue_management TO queue_user;"
```

Leave the `POSTGRES_*` variables unset in that case — `start.bat` reads
`POSTGRES_PASSWORD` to tell whether the container is this machine's database,
and will not start one on a machine that already serves PostgreSQL itself.

Either way, apply migrations with `python manage.py migrate`, then create the
fictional staff accounts and service counters with `python manage.py seed_demo`.
The accounts it creates are listed in [`test-accounts.md`](./test-accounts.md).
It seeds **no patients** — the queue starts empty and fills up only with visits
checked in through reception, so nothing a dashboard shows is fabricated.

### SQLite fallback — local prototype only

If `DATABASE_URL` is unset, the backend falls back to a local SQLite file at
`backend/db.sqlite3` so the prototype runs on a machine with no PostgreSQL
installed.

This fallback is **for local prototype work only**. It is not acceptable for the
pilot or for any real-data use, because:

- concurrent writes from several staff terminals serialise badly under SQLite's
  single-writer lock, and the clinic has multiple simultaneous stations;
- the LAN deployment expects a server process other machines connect to;
- backup/recovery and retention procedures in the operations runbook assume
  PostgreSQL tooling.

The backend logs a warning on startup whenever it is running on the fallback, so
this can never be true silently. Setting `DJANGO_ENV=production` with no
`DATABASE_URL` is a hard startup error rather than a silent downgrade, and
`start.bat` refuses to start at all when `DATABASE_URL` is unset.

To move an existing SQLite prototype database onto PostgreSQL, dump it with the
variable forced empty and load it back with it set:

```bash
cd backend
DATABASE_URL= python manage.py dumpdata \
  --exclude contenttypes --exclude auth.Permission --exclude sessions \
  --exclude admin.logentry --exclude token_blacklist \
  --indent 2 --output ../.tmp/sqlite_dump.json
python manage.py migrate
python manage.py loaddata ../.tmp/sqlite_dump.json
```

The exclusions are the tables `migrate` repopulates itself, plus JWT and session
state that should not survive a database move.

## Real-time (Django Channels)

Channels needs a channel layer. In development the in-memory layer is used
automatically (single process, no extra service). For the LAN deployment set
`REDIS_URL` and the Redis channel layer is used instead — the in-memory layer
cannot share state across worker processes.

The backend runs under ASGI (`config.asgi:application`). `manage.py runserver`
serves ASGI automatically once Channels is installed, so WebSockets work in
development without a separate command.

## Environment variables

Every variable is documented by name in [`../.env.example`](../.env.example).
No value in this repo is a real credential.

## Governance gate

Tasks tagged `[GOV SIGN-OFF]` in [`../TASKS.md`](../TASKS.md) are blocked until
approved. Check status any time:

```bash
python tools/check_signoff.py
```

See [`governance/README.md`](./governance/README.md).

## Tests

```bash
cd backend && python manage.py test      # Django tests
cd frontend && npm test                  # frontend tests (added in Phase 5)
```
