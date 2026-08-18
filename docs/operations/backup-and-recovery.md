# Backups and recovery

The queue database holds no clinical record, so losing it is not a clinical
catastrophe — but it holds the day's queue and the audit trail, and the audit
trail is the accountability evidence the spec requires. Treat it accordingly.

> **A backup you have never restored is not a backup.** The restore drill below
> is the part of this document that actually matters.

---

## What is backed up

| Data | Where | Retention |
|---|---|---|
| PostgreSQL database (visits, staff, audit trail) | `BACKUP_DIR` on the clinic machine | See below |
| `.env` | **Not** backed up automatically — it holds secrets | Kept by the system owner, offline |

Retention for the queue data and the audit trail is a governance decision (item
G5, still pending). The spec proposes live tokens purged end-of-day and audit
logs kept about 12 months. Until that is settled, keep backups for **30 days**
and do not delete anything older without asking.

---

## Daily backup

[`deploy/backup_db.bat`](../../deploy/backup_db.bat) takes a compressed dump and
prunes old ones. Schedule it with Task Scheduler, daily, after the clinic
closes:

```bat
schtasks /Create /TN "QueueBackup" /TR "C:\Dev\Queue_management\deploy\backup_db.bat" ^
    /SC DAILY /ST 19:00 /RU SYSTEM
```

Set `BACKUP_DIR` in `.env` to a path **on a different physical disk** from the
database, or on a network share. A backup on the same disk protects you from a
mistake, not from the disk failing — and disk failure is the more likely event.

Copy the backup off the machine periodically (external drive kept in a
different room). A fire or theft takes the machine and everything on it.

The clinic machine has PostgreSQL installed, so the script calls `pg_dump`
directly. On a development machine running the database from
[`deploy/docker-compose.yml`](../../deploy/docker-compose.yml) there is no
`pg_dump` on `PATH`, and the script falls back to running it inside the
container. The dump file is byte-for-byte the same either way, so a dump taken
on one can be restored on the other.

---

## Checking backups are working

Weekly, someone should confirm:

1. A file from last night exists in `BACKUP_DIR` and is not zero bytes.
2. The file size is in the same range as previous days. A sudden drop usually
   means the dump failed part-way and still wrote a file.

A backup job that has been failing silently for a month is worse than no backup
job, because everyone believes they are covered.

---

## Restore drill

**Do this once before the system is used in earnest, and once a term after.**
Restore to a *scratch* database, never over the live one:

```bash
createdb queue_restore_test --owner queue_user
pg_restore --clean --if-exists --no-owner --dbname queue_restore_test "<backup file>"

psql queue_restore_test -c "SELECT COUNT(*) FROM queueapp_visit;"
psql queue_restore_test -c "SELECT COUNT(*) FROM queueapp_auditlogentry;"

dropdb queue_restore_test
```

If those counts look like a working day, the backup is real.

With the database in a container, the same drill runs inside it — the dump is
piped in from the host:

```bash
docker exec queue-management-pg createdb -U queue_user queue_restore_test
docker exec -i queue-management-pg pg_restore --clean --if-exists --no-owner \
    -U queue_user --dbname queue_restore_test < "<backup file>"

docker exec queue-management-pg psql -U queue_user -d queue_restore_test \
    -c "SELECT COUNT(*) FROM queueapp_visit;"

docker exec queue-management-pg dropdb -U queue_user queue_restore_test
```

---

## Real recovery

When the live database is lost or corrupted:

1. **Switch the clinic to the paper fallback first.** See
   [`offline-fallback.md`](./offline-fallback.md). Do not attempt a restore
   while staff are waiting on the system — that pressure is how a scratch
   restore becomes an overwrite of something recoverable.
2. Stop both services (`stop.bat`).
3. Preserve what is there before replacing it:
   ```bash
   pg_dump -Fc queue_management > broken-$(date +%Y%m%d-%H%M).dump
   ```
   Even a corrupted database may contain the audit entries you need.
4. Restore the most recent good backup:
   ```bash
   dropdb queue_management
   createdb queue_management --owner queue_user
   pg_restore --no-owner --dbname queue_management "<backup file>"
   ```
5. Start the services and check `/api/health/`.
6. **Reconcile the gap.** Everything between the backup and the failure is
   missing. Use the paper sheets and the fallback reconciliation procedure to
   enter it, and note in the operations log which period was reconstructed.

---

## What a restore cannot give back

- Queue activity since the last backup — recoverable only from the paper
  sheets, which is why the sheets are kept.
- Audit entries since the last backup. Say so explicitly in the operations log
  rather than presenting the trail as complete. A gap that is visible is far
  better than a record that looks whole and is not.
