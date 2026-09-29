"""Measured delivery — SPEC §T14, §V9, §C19.

Delivered means the device sent a receipt (§R6: a push service accepting a
message says nothing about display). No receipt after GRACE is undelivered;
inside it, pending, and counted on neither side. The rate is a lower bound:
a phone offline at the time displays the push but cannot report it.
"""

from datetime import datetime, timedelta

GRACE = timedelta(minutes=10)


def _tally(pushes, now):
    counts = {"received": 0, "undelivered": 0, "pending": 0}
    for push in pushes:
        if push["delivered_at"]:
            counts["received"] += 1
        elif now - datetime.fromisoformat(push["sent_at"]) > GRACE:
            counts["undelivered"] += 1
        else:
            counts["pending"] += 1
    settled = counts["received"] + counts["undelivered"]
    # 0 of 0 is not 100%.
    counts["rate"] = counts["received"] / settled if settled else None
    return counts


def summarise(pushes, now):
    members = sorted({push["member_id"] for push in pushes})
    return {
        "overall": _tally(pushes, now),
        "members": {
            member: _tally([p for p in pushes if p["member_id"] == member], now)
            for member in members
        },
    }
