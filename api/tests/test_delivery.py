"""Delivery rate — SPEC §T14, §V9, §C19.

A push is delivered only when the device says so (§R6). One with no receipt
after the grace period is undelivered; one still inside it is pending and
counts for neither side, or a busy minute would read as an outage.
"""

from datetime import UTC, datetime, timedelta

from splitly.delivery import GRACE, summarise

NOW = datetime(2026, 9, 29, 12, 0, tzinfo=UTC)


def push(member, minutes_ago, delivered=True):
    sent = NOW - timedelta(minutes=minutes_ago)
    return {
        "member_id": member,
        "sent_at": sent.isoformat(),
        "delivered_at": (sent + timedelta(seconds=2)).isoformat() if delivered else None,
    }


def test_the_grace_period_is_ten_minutes():
    assert GRACE == timedelta(minutes=10)


def test_v9_every_push_is_received_undelivered_or_pending():
    summary = summarise(
        [
            push("dan", 60),
            push("dan", 60, delivered=False),
            push("dan", 2, delivered=False),
        ],
        now=NOW,
    )

    assert summary["overall"] == {"received": 1, "undelivered": 1, "pending": 1, "rate": 0.5}


def test_the_rate_is_per_member_as_well():
    summary = summarise([push("dan", 60), push("gabe", 60, delivered=False)], now=NOW)

    assert summary["members"]["dan"]["rate"] == 1.0
    assert summary["members"]["gabe"]["rate"] == 0.0


def test_no_settled_pushes_means_no_rate_not_a_perfect_one():
    """0 of 0 is not 100%."""
    summary = summarise([push("dan", 1, delivered=False)], now=NOW)

    assert summary["overall"]["rate"] is None
