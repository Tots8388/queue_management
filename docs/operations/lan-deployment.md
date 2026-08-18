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
# Both frontends call the API from the browser, so both origins belong here.
CORS_ALLOWED_ORIGINS=http://192.168.1.50:3000,http://queue.clinic.local:3000,http://192.168.1.50:3001,http://queue.clinic.local:3001
# Lets the staff app link to the waiting-room board, which the patient app serves.
NEXT_PUBLIC_PATIENT_APP_URL=http://192.168.1.50:3000
NEXT_PUBLIC_API_BASE_URL=http://192.168.1.50:8000
NEXT_PUBLIC_WS_BASE_URL=ws://192.168.1.50:8000
```

Leave the `POSTGRES_*` variables out. They configure the containerised
development database only, and `start.bat` reads `POSTGRES_PASSWORD` to decide
whether to bring a container up — on this machine PostgreSQL is a service of its
own and nothing should start a second one alongside it.

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

### 4. Frontends

Two applications, built from one install at the repo root — they are npm
workspaces, which is also what lets the shared components resolve their
dependencies.

```bash
npm ci
npm run build     # builds the patient app and the staff app
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

- **Firewall:** allow inbound TCP 8000, 3000 and 3001 from the clinic LAN
  only. Do not forward these ports from the internet. If remote access is ever
  wanted, that is a new decision requiring institutional sign-off, not a
  firewall change.
- **Two applications:** port 3000 serves patients, port 3001 serves staff.
  Give patients and the waiting-room screen the 3000 address and nothing else.
  Restricting 3001 to the staff VLAN or to the terminals' addresses, if the
  network can express that, is worth doing — but the separation already means
  no patient-facing screen offers a route into a dashboard. It is not what
  authorises staff, either: every action is authorised again on the server
  against the signed-in account's role.
- **Terminals:** each station opens `http://<server>:3001` and signs in with
  its own role account. Do not share one account between stations — the audit
  trail is only as meaningful as the accounts behind it.
- **Waiting-room screen:** open `http://<server>:3000/display` in a browser in
  kiosk/full-screen mode. It needs no sign-in and reconnects by itself, so it
  can be left running. It shows everyone currently in the clinic in four
  columns, so give it the widest screen available — under 1024px wide the four
  columns fold into two rows of two, which still works but halves how much is
  legible from across the room.
- **Patient phones:** patients reach `http://<server>:3000/patient` on the
  clinic Wi-Fi. Patients without a smartphone use the printed token and the
  waiting-room screen — the system must never require a phone.

### Checking it is up

```bash
curl http://<server>:8000/api/health/
```

Anything other than `"status": "ok"` means the machine needs attention. Staff
can see the same thing from the connection banner on their dashboard.

### A daily job for reception: abandoned visits

A visit ends when pharmacy is finished with the patient, not when the day does.
That is what keeps the waiting-room board honest, and it means a patient who
goes home halfway through leaves a visit nothing will ever close — it stays on
the board and in a stage queue.

Once nothing has happened to a visit for **24 hours** (`STALE_VISIT_HOURS`), an
**Abandoned visits** panel appears on the reception dashboard listing it, with
how long it has been idle. Reception checks the desk and the waiting area, then
closes it. The panel is hidden entirely when there is nothing in it, so its
presence is the prompt — there is no separate report to remember to run.

Worth building into the opening routine: a clerk glancing at the dashboard at
the start of the day will catch yesterday's strays before the board carries
them into a second morning. The system does **not** do this on a timer, on
purpose — a visit still open is a patient the clinic has lost track of, and
that is worth a person noticing rather than a scheduled job tidying it away.

Nothing is deleted by closing a visit. The record and its audit entry are
retained on their own schedules, and the entry names the clerk who closed it.

---

## Secrets

All credentials — database password, Django secret key, JWT signing key, SMS
API key — live in the machine's `.env` or its environment. **Nothing goes in the
repository.** `.env.example` lists names with empty values and is the only such
file that is committed.

If a credential is exposed, rotate it on the machine and restart both services;
nothing else needs to change.
