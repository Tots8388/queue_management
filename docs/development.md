# Development setup

Local development for the Digital Queue & Patient-Flow Management System.
Source of truth for behaviour is [`../spec.md`](../spec.md).

## Prerequisites

- Python 3.12 or newer
- Node.js 20 or newer
- PostgreSQL 14+ (recommended; see [Database](#database) for the prototype
  fallback)

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

### Frontend

```bash
cd frontend
npm install
npm run dev
```

Or run both at once from the repo root with `start.bat` (Windows) or
`./start.sh` (macOS/Linux), and shut them down with `stop.bat` / `./stop.sh`.

## Database

**PostgreSQL is the target database** for both the pilot and any production use.
The audit and accountability requirements need durable, queryable, timestamped
records, and the spec fixes PostgreSQL as the decision.

Set `DATABASE_URL` in `.env`:

```
DATABASE_URL=postgres://queue_user:PASSWORD@localhost:5432/queue_management
```

Create the database once:

```bash
createdb queue_management
createuser queue_user --pwprompt
psql -c "GRANT ALL PRIVILEGES ON DATABASE queue_management TO queue_user;"
```

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
`DATABASE_URL` is a hard startup error rather than a silent downgrade.

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
