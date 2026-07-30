"""
The application service layer.

Holds the single authoritative queue state. Every channel — patient view, staff
dashboards, public display — reads the same functions here, so no channel can
show a queue that disagrees with another.

* ``queue`` — reading: ordering, positions, the state a channel renders.
* ``operations`` — writing: check-in, stage transitions, priority, presence.
"""
