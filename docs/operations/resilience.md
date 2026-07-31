# Resilience: power, hardware, and the single point of failure

## Say the uncomfortable thing plainly

**The clinic machine is a single point of failure.** One box runs the database,
the API, the real-time layer and the frontend. If it stops, every screen in the
building stops with it — reception, all three clinical stations, the patient
view and the waiting-room board.

This is an accepted trade-off, not an oversight. Running on-premise is what
keeps patient data inside the Medical Center and what lets the queue work with
no internet at all. The price is that one machine matters a great deal.

The mitigation is not clever architecture. It is:

1. a **UPS**, so a power flicker is not an outage;
2. a **rehearsed paper fallback**, so an outage is not a crisis;
3. a **known recovery path**, so an outage is short.

All three are cheap. Redundant servers are not, and for a prototype they would
be the wrong thing to spend on.

---

## Power

| Item | Requirement |
|---|---|
| UPS | Rated to hold the clinic machine and the network switch for **at least 15 minutes** |
| What it powers | The machine **and** the switch/router. A running server nobody can reach is no better than a dead one |
| Shutdown | Configure the UPS to trigger a clean shutdown at ~20% battery — an abrupt loss during a database write is how corruption happens |
| Testing | Pull the mains once a term, with the clinic closed. Confirm the machine stays up and shuts down cleanly when told to |

The waiting-room screen does **not** need to be on the UPS. It is the least
important thing in the building during a power cut; staff call numbers out.

---

## Hardware failure

Have a **recovery path**, written down and known before it is needed:

- A **spare machine** — any reasonably modern desktop. It does not need to be
  identical or fast; it needs to exist, be reachable, and have Python,
  PostgreSQL and Node installed.
- The **latest backup** accessible from that spare (see
  [`backup-and-recovery.md`](./backup-and-recovery.md)).
- The `.env` values held by the system owner, offline. Without the database
  password the spare is useless, and that is exactly the thing nobody
  remembers to keep.

Rebuild time on a prepared spare is roughly an hour: install, restore, point
the terminals at the new address. Which is the argument for using a hostname
rather than a bare IP on the terminals — then only DNS changes, not six
machines.

### If the spare is not ready

Then the recovery path is: **paper fallback for the rest of the day**, and
reconcile when the machine is repaired or replaced. That is a legitimate
outcome. What is not legitimate is discovering on the day that nobody knows
where the backups are.

---

## Network failure

If the LAN or Wi-Fi fails but the machine is fine:

- Staff terminals on wired connections may still work. Check before assuming a
  full outage.
- Patient phones will not reach the patient view. The printed token and the
  waiting-room screen cover this — which is why the printed token is a core
  channel and SMS is not.
- If the switch is down, everything is down: paper fallback.

---

## Named owner

Someone at the Medical Center is the **system owner**, by name. Their
responsibilities:

- knows where the backups are and has restored one at least once;
- holds the `.env` values offline;
- is the person staff call when the screens are down;
- decides when to declare an outage and switch to paper.

Naming that person is part of governance item **G5**, still pending. Until it
is named, this document has a hole in it, and that hole is the most likely
reason a real outage would go badly.

---

## Rehearsal

Once before the system is used in earnest, and once a term:

- [ ] Pull the mains — does the UPS hold, and does shutdown work?
- [ ] Stop the backend during a quiet period — do staff see the red banner and
      reach for the paper sheets without being prompted?
- [ ] Run 20 minutes on paper, then reconcile — does the queue order come out
      right?
- [ ] Restore a backup to a scratch database — do the counts look like a real
      day?

The point of the rehearsal is not the technology. It is that the staff have
done it once before they have to do it with a full waiting room.
