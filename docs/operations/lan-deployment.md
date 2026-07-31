# Running on the clinic's own machine

v1 runs entirely on the Medical Center's LAN. Django, PostgreSQL, Channels and
the Next.js frontend all live on one local machine; staff terminals, patient
phones and the waiting-room screen reach it over the local network.

**Core queue operation has no cloud or internet dependency.** The only
component that reaches outside is the optional SMS gateway, and the system runs
fully with it switched off. That is what makes the offline fallback a last
resort rather than a daily occurrence: an internet outage is not a system
outage here.

> This document covers running the prototype on clinic hardware for
> demonstration and rehearsal, with **fictional data**. It is not authorisation
> to run a pilot with real patient data — that needs governance item G5, still
> pending. See [`../governance/SIGNOFF.md`](../governance/SIGNOFF.md).

---

## The machine

| Requirement | Why |
|---|---|
| Always-on desktop or small server, wired to the LAN | Its availability is load-bearing; everything else depends on it |
| Fixed IP address (static, or a DHCP reservation) | Terminals and the display screen are configured to point at it |
| UPS | See [`resilience.md`](./resilience.md) — this is not optional |
| PostgreSQL 14+ | SQLite is prototype-only and will not survive several terminals writing at once |
| Python 3.12+, Node 20+ | Backend and frontend |

Give the machine a name on the network (e.g. `queue.clinic.local`) if the LAN
has local DNS. Otherwise use the IP everywhere and write it on a label on the
machine itself.

---

## One-time setup

### 1. Database

```bash
createuser queue_user --pwprompt
createdb queue_management --owner queue_user
```

### 2. Environment

Copy `.env.example` to `.env` on the machine and fill it in. **Never commit
this file, and never copy it to a terminal.**

```bash
DJANGO_ENV=production
DJANGO_SECRET_KEY=<generate: python -c "import secrets; print(secrets.token_urlsafe(50))">
DJANGO_ALLOWED_HOSTS=192.168.1.50,queue.clinic.local,localhost
DATABASE_URL=postgres://queue_user:<password>@localhost:5432/queue_management
REDIS_URL=redis://localhost:6379/0
CORS_ALLOWED_ORIGINS=http://192.168.1.50:3000,http://queue.clinic.local:3000
NEXT_PUBLIC_API_BASE_URL=http://192.168.1.50:8000
NEXT_PUBLIC_WS_BASE_URL=ws://192.168.1.50:8000
```

With `DJANGO_ENV=production`, a missing secret key, database URL or allowed
host is a **startup error**, not a silent insecure default. That is deliberate:
a misconfigured clinic server should refuse to start rather than run in a state
nobody inspected.

### 3. Install and migrate

```bash
cd backend
python -m venv .venv
.venv\Scripts\pip install -r requirements.txt
.venv\Scripts\python manage.py migrate
.venv\Scripts\python manage.py collectstatic --noinput
.venv\Scripts\python manage.py createsuperuser
```

Then create the staff accounts, one per role, through the Django admin at
`/admin/`. Do **not** run `seed_demo` on the clinic machine — it refuses to run
with `DEBUG` off, but do not rely on that as the only guard.

### 4. Frontend

```bash
cd frontend
npm ci
npm run build
```

---

## Running it

For a demonstration or rehearsal, `start.bat` from the repo root is enough.

For an always-on machine, both processes should start on boot and restart if
they die. On Windows, register them with **Task Scheduler** (trigger: *At
startup*, *Run whether user is logged on or not*) or install them as services
with **NSSM**:

```bat
nssm install QueueBackend  "C:\Dev\Queue_management\backend\.venv\Scripts\python.exe" ^
    "C:\Dev\Queue_management\backend\-m daphne -b 0.0.0.0 -p 8000 config.asgi:application"
nssm set QueueBackend AppDirectory "C:\Dev\Queue_management\backend"

nssm install QueueFrontend "C:\Program Files\nodejs\npm.cmd" "run start"
nssm set QueueFrontend AppDirectory "C:\Dev\Queue_management\frontend"
```

Daphne is the ASGI server; it serves HTTP and WebSockets together. `runserver`
is for development only.

### Redis

The in-memory channel layer only works in a single process. As soon as the
backend runs more than one worker, set `REDIS_URL` — without it, a staff
dashboard connected to worker A will never hear about a change made on
worker B, and two terminals will quietly disagree about the queue.

---

## The network

- **Firewall:** allow inbound TCP 8000 and 3000 from the clinic LAN only. Do
  not forward these ports from the internet. If remote access is ever wanted,
  that is a new decision requiring institutional sign-off, not a firewall
  change.
- **Terminals:** each station opens `http://<server>:3000` and signs in with
  its own role account. Do not share one account between stations — the audit
  trail is only as meaningful as the accounts behind it.
- **Waiting-room screen:** open `http://<server>:3000/display` in a browser in
  kiosk/full-screen mode. It needs no sign-in and reconnects by itself, so it
  can be left running.
- **Patient phones:** patients reach `http://<server>:3000/patient` on the
  clinic Wi-Fi. Patients without a smartphone use the printed token and the
  waiting-room screen — the system must never require a phone.

### Checking it is up

```bash
curl http://<server>:8000/api/health/
```

Anything other than `"status": "ok"` means the machine needs attention. Staff
can see the same thing from the connection banner on their dashboard.

---

## Secrets

All credentials — database password, Django secret key, JWT signing key, SMS
API key — live in the machine's `.env` or its environment. **Nothing goes in the
repository.** `.env.example` lists names with empty values and is the only such
file that is committed.

If a credential is exposed, rotate it on the machine and restart both services;
nothing else needs to change.
