# Test accounts

Sign-in details for the fictional staff accounts used to demonstrate and test
the Digital Queue & Patient-Flow Management System. There are no patient
accounts and no seeded patients — see [Patients](#patients) below.

> **These are prototype credentials for a development database only.**
> Every account, name and record behind them is invented — no real patient, no
> real member of staff, no real phone number. The passwords are well-known
> placeholders written into `backend/queueapp/management/commands/seed_demo.py`,
> which refuses to run with `DEBUG` off. None of these accounts may exist on a
> machine holding real clinic data; the pilot creates its own accounts with real
> passwords that are never written down in this repository.

## Staff accounts

Sign in at <http://localhost:3001/login>. Password for all six: `prototype-demo-only`

> **The staff app is on port 3001, the patient app on port 3000.** They are two
> separate applications: nothing served on the patient port can reach a staff
> screen, which is why a patient browsing the queue is never one URL away from
> a dashboard. On the clinic LAN only staff terminals are given the 3001
> address.

| Username | Name | Role | Lands on |
| --- | --- | --- | --- |
| `reception1` | Achieng Odhiambo | Registration Clerk | `/staff/reception` |
| `nurse1` | Wanjiru Kamau | Nurse / Vitals | `/staff/vitals` |
| `clinician1` | Kiprop Cheruiyot | Clinician | `/staff/consultation` |
| `pharmacy1` | Nasirumbi Wekesa | Pharmacist | `/staff/pharmacy` |
| `supervisor1` | Atieno Ochieng | Supervisor / Management | — (see below) |
| `itsupport1` | Mutiso Kilonzo | IT / Support | — (see below) |

Only the four station roles have a dashboard. **Supervisor** and **IT / Support**
sign in successfully but hold no capabilities and are sent nowhere, because
their oversight boundary is governance item **G4** and is not yet signed off
(`shared/contracts.json` carries `"dashboard": null` for both). That is the
intended behaviour, not a broken login. `itsupport1` can reach the Django admin
at <http://localhost:8000/admin/> but has no permissions there.

Priority may only be set by the two clinical roles — `nurse1` and `clinician1`.
Use `reception1` to check that the control is genuinely absent for the others.

## Django admin superuser

| Username | Password | Purpose |
| --- | --- | --- |
| `admin` | `prototype-admin-only` | Full access to <http://localhost:8000/admin/> |

Unlike the six above, this one is not created by `seed_demo` — it is a local
convenience account for inspecting and correcting data during development.
Recreate it on a fresh database with:

```bash
cd backend
.venv/Scripts/python.exe manage.py shell -c "from queueapp.models import StaffUser, Role; u,_=StaffUser.objects.get_or_create(username='admin', defaults={'first_name':'Prototype','last_name':'Administrator','role':Role.IT_SUPPORT}); u.is_staff=u.is_superuser=True; u.set_password('prototype-admin-only'); u.save()"
```

## Patients

Patients have **no accounts**. A patient is identified only by the token printed
at check-in, entered at <http://localhost:3000/patient> or reached directly at
`/patient/<token>` — this is deliberate, and the reason no personal detail is
needed to check a place in the queue.

**No patients are seeded.** There is no fabricated patient data anywhere in this
project: the queue starts empty, and every visit in the database is one somebody
checked in at <http://localhost:3001/staff/reception> as `reception1`. To try the
system, check a few in yourself and walk them through vitals, consultation and
pharmacy; the token you are given is the one to type at `/patient`.

List whatever is currently in the queue with:

```bash
cd backend
.venv/Scripts/python.exe manage.py shell -c "from queueapp.models import Visit; [print(v.token, v.current_stage, v.stage_status) for v in Visit.objects.order_by('token')]"
```

Tokens are drawn at random — a letter and three digits, `K492` — and are unique
within a token period rather than within a day (`TOKEN_PERIOD_DAYS`, one week by
default). Two check-ins in a row will not produce neighbouring tokens; that is
the point, because the board publishes every token in the building and a
sequence would publish arrival order with it.

The board at <http://localhost:3000/display> tracks where everyone in the clinic
is, in four columns — Reception, Vital signs, Consultation, Pharmacy. A patient
appears on it from check-in and leaves it only when pharmacy has finished with
them. It shows tokens and rooms only — never a name, never a priority.

### Trying the abandoned-visit flow

Nothing has been abandoned in a fresh database, so the reception dashboard's
**Abandoned visits** panel is hidden. To see it, age a visit past the 24-hour
threshold — `last_updated` is `auto_now`, so it has to be written with an
`update()` rather than a `save()`, which would stamp it with now:

```bash
cd backend
.venv/Scripts/python.exe manage.py shell -c "
from django.utils import timezone
from queueapp.models import Visit
v = Visit.objects.filter(closed_at__isnull=True).exclude(current_stage='complete').first()
Visit.objects.filter(pk=v.pk).update(last_updated=timezone.now() - timezone.timedelta(hours=30))
print('stranded', v.token, 'at', v.current_stage)
"
```

Reload the reception dashboard and the panel appears. Closing the visit removes
it from the board and from its stage queue, and writes an audit entry naming
the signed-in clerk.

Two consequences of an empty start are intended behaviour, not faults:

- the four dashboards say "nobody is waiting" until someone is checked in;
- the patient's wait range reads "estimate unavailable" until five services
  have actually completed at that stage (FR7 — it will not guess).

## Recreating the accounts

The six staff accounts and six service counters come from one command:

```bash
cd backend
.venv/Scripts/python.exe manage.py seed_demo                 # create anything missing
.venv/Scripts/python.exe manage.py seed_demo --reset         # recreate staff and counters
.venv/Scripts/python.exe manage.py seed_demo --clear-visits  # empty the queue
```

`--clear-visits` deletes every visit, which empties the board and frees every
token for reissue. `--reset` does that too, and additionally recreates the
seeded staff and counters. Both refuse to run with `DEBUG` off.

The password is set on account creation, so changing `DEMO_PASSWORD` in `.env`
alone does not change it. `.env` needs that variable to match the value above
because `frontend/scripts/capture-screenshots.mjs` signs in with it.

To change a password by hand:

```bash
cd backend
.venv/Scripts/python.exe manage.py changepassword reception1
```

## Related

- [`development.md`](./development.md) — setup, database, running the app
- [`operations/lan-deployment.md`](./operations/lan-deployment.md) — the clinic
  deployment, which creates real accounts and shares none of these
