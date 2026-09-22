"""Ledger core — SPEC §T2.

Each test here is named in T2's verification contract and maps to an
invariant. Hypothesis properties over the same invariants are T3's row,
not this one; these are worked examples.
"""

import dataclasses
from datetime import UTC, datetime

import pytest

from splitly.ledger import Entry, Member, balances


def make_entry(**overrides):
    """An ordinary expense: Jackson fronts $90, split three ways."""
    fields = {
        "entry_id": "e1",
        "house_id": "h1",
        "created_at": datetime(2026, 9, 16, tzinfo=UTC),
        "description": "groceries",
        "kind": "expense",
        "total": 9000,
        "payer": "jackson",
        "shares": {"jackson": 3000, "alice": 3000, "dan": 3000},
    }
    return Entry(**(fields | overrides))


# --- §V11: per-entry shares sum to the entry total, no rounding drift ---


def test_entry_rejects_shares_not_summing_to_total():
    with pytest.raises(ValueError, match="shares"):
        make_entry(total=9000, shares={"jackson": 3000, "alice": 3000, "dan": 2999})


def test_entry_accepts_exact_split():
    entry = make_entry()
    assert sum(entry.shares.values()) == entry.total


def test_entry_rejects_non_positive_total():
    """A negative total would silently invert who owes whom."""
    with pytest.raises(ValueError, match="total"):
        make_entry(total=-9000, shares={"jackson": -9000})


# --- §V1: the whole ledger sums to zero ---


def test_ledger_of_many_entries_sums_to_zero():
    entries = [
        make_entry(entry_id="e1"),
        make_entry(
            entry_id="e2",
            description="internet",
            payer="alice",
            total=6000,
            shares={"jackson": 2000, "alice": 2000, "dan": 2000},
        ),
        make_entry(
            entry_id="e3",
            description="dan settles up",
            kind="payment",
            payer="dan",
            total=5000,
            shares={"jackson": 5000},
        ),
    ]
    assert sum(balances(entries).values()) == 0


def test_payment_reduces_the_payers_debt():
    expense = make_entry()
    after_expense = balances([expense])
    assert after_expense["dan"] == -3000

    payment = make_entry(
        entry_id="e2", kind="payment", payer="dan", total=3000, shares={"jackson": 3000}
    )
    assert balances([expense, payment])["dan"] == 0


def test_write_off_clears_a_balance_without_deleting_history():
    """§C50 — forgiving a debt is an ordinary entry, not a deletion."""
    expense = make_entry()
    write_off = make_entry(
        entry_id="e2",
        kind="write_off",
        description="dan moved out owing",
        payer="dan",
        total=3000,
        shares={"jackson": 3000},
    )
    ledger = [expense, write_off]
    assert balances(ledger)["dan"] == 0
    assert len(ledger) == 2, "the original expense is still on the books"


# --- §V8: entries are immutable once written ---


def test_entry_is_immutable():
    entry = make_entry()
    with pytest.raises(dataclasses.FrozenInstanceError):
        entry.total = 1


def test_entry_shares_cannot_be_mutated_through_the_mapping():
    """A frozen dataclass still hands out a mutable dict unless we stop it."""
    entry = make_entry()
    with pytest.raises(TypeError):
        entry.shares["dan"] = 1


# --- §C6: balances are derived, never stored ---


def test_balance_is_derived_not_stored():
    assert not hasattr(make_entry(), "balance")
    entries = [make_entry()]
    assert balances(entries) == balances(entries)


def test_balances_covers_every_member_touched_by_an_entry():
    """§V3 leans on this — a balance must be traceable to entries."""
    assert set(balances([make_entry()])) == {"jackson", "alice", "dan"}


# --- §C22: one storage format for every split style ---


def test_entry_stores_amounts_not_the_split_style():
    """How the numbers were reached — even, manual, all-to-one (§C23) — is a UI
    concern. An allowlist so a new field cannot arrive unnoticed.
    """
    fields = {f.name for f in dataclasses.fields(make_entry())}
    assert fields == {
        "entry_id",
        "house_id",
        "created_at",
        "description",
        "kind",
        "total",
        "payer",
        "shares",
    }


# --- §C48: members carry an active flag; leaving does not erase the debt ---


def test_inactive_member_still_has_balance():
    dan = Member(member_id="dan", name="Dan", active=False)
    assert dan.active is False
    assert balances([make_entry()])["dan"] == -3000


def test_members_default_to_active():
    assert Member(member_id="alice", name="Alice").active is True
