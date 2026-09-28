"""Property tests over §V1 and §V11 — SPEC §T3.

§C32 requires these two invariants be proved by Hypothesis properties rather
than worked examples. The examples in `test_ledger.py` stay — they document
intent; these prove the claim across the input space.

Every property here was run against a deliberately broken `ledger.py` before
being trusted. §B2 was a check that existed and passed blind.
"""

from datetime import UTC, datetime

import pytest
from hypothesis import assume, given
from hypothesis import strategies as st

from splitly.ledger import Entry, balances, drilldown
from splitly.splits import even

# A fixed roster (§C20 — four people) so members collide across entries and
# shrunk counterexamples stay readable.
ROSTER = ["jackson", "alice", "dan", "sam"]

# Cents, capped far above any real bill so failures shrink to small numbers.
CENTS = st.integers(min_value=1, max_value=1_000_000)

WHEN = datetime(2026, 9, 18, tzinfo=UTC)


def build(shares, **overrides):
    """An entry whose total agrees with its shares unless a test says otherwise."""
    fields = {
        "entry_id": "e1",
        "house_id": "h1",
        "created_at": WHEN,
        "description": "groceries",
        "kind": "expense",
        "total": sum(shares.values()),
        "payer": "jackson",
        "shares": shares,
    }
    return Entry(**(fields | overrides))


@st.composite
def share_maps(draw):
    members = draw(
        st.lists(st.sampled_from(ROSTER), min_size=1, max_size=len(ROSTER), unique=True)
    )
    return {member: draw(CENTS) for member in members}


@st.composite
def entries(draw):
    return build(
        draw(share_maps()),
        entry_id=f"e{draw(st.integers(min_value=0, max_value=10**6))}",
        kind=draw(st.sampled_from(["expense", "payment", "write_off"])),
        payer=draw(st.sampled_from(ROSTER)),
    )


ledgers = st.lists(entries(), max_size=12)


# --- §V1: sum(∀ entries) = 0 ---


@given(ledger=ledgers)
def test_v1_any_ledger_sums_to_zero(ledger):
    assert sum(balances(ledger).values()) == 0


@given(ledger=ledgers, extra=entries())
def test_v1_survives_appending_any_entry(ledger, extra):
    """Append-only means §V1 must hold after every write, not only at rest."""
    assert sum(balances(ledger + [extra]).values()) == 0


def test_v1_holds_for_the_empty_ledger():
    assert sum(balances([]).values()) == 0


@given(ledger=ledgers, data=st.data())
def test_balances_are_order_independent(ledger, data):
    """§C6 — a balance derived by summing cannot depend on insertion order."""
    assert balances(data.draw(st.permutations(ledger))) == balances(ledger)


# --- §V11: ∀ entry → sum(per-person amounts) = entry total ---


@given(shares=share_maps())
def test_v11_accepts_any_shares_summing_to_total(shares):
    """The positive half — and that the read-only copy preserves every cent."""
    entry = build(shares)
    assert dict(entry.shares) == shares
    assert sum(entry.shares.values()) == entry.total


@given(shares=share_maps(), delta=st.integers(min_value=-(10**6), max_value=10**6))
def test_v11_rejects_any_total_disagreeing_with_shares(shares, delta):
    assume(delta != 0)
    total = sum(shares.values()) + delta
    assume(total > 0)  # a non-positive total trips a different check
    with pytest.raises(ValueError, match="V11"):
        build(shares, total=total)


# --- §V12: even split → remainder cents to payer, ⊥ dropped ---


ROSTERS = st.lists(st.sampled_from(ROSTER), min_size=1, max_size=len(ROSTER), unique=True)


@given(total=CENTS, members=ROSTERS, payer=st.sampled_from(ROSTER))
def test_v12_an_even_split_never_drops_or_invents_a_cent(total, members, payer):
    assert sum(even(total, members, payer).values()) == total


@given(total=CENTS, members=ROSTERS, payer=st.sampled_from(ROSTER))
def test_v12_every_member_of_the_split_gets_a_share(total, members, payer):
    """A dropped member is a dropped debt, and §V1 would still hold."""
    assert set(even(total, members, payer)) == set(members)


@given(total=CENTS, members=ROSTERS, payer=st.sampled_from(ROSTER))
def test_v12_the_remainder_is_one_lump_not_a_slow_leak(total, members, payer):
    """§C24 — at most `members - 1` cents separate anyone, by construction."""
    shares = even(total, members, payer)
    assert max(shares.values()) - min(shares.values()) <= len(shares) - 1


@given(total=CENTS, members=ROSTERS, payer=st.sampled_from(ROSTER), data=st.data())
def test_v12_is_deterministic_regardless_of_member_order(total, members, payer, data):
    shuffled = data.draw(st.permutations(members))
    assert even(total, shuffled, payer) == even(total, members, payer)


# --- §V3: a balance is retrievable from the entries behind it ---


@given(ledger=ledgers)
def test_v3_a_members_balance_equals_the_net_of_their_drilldown(ledger):
    """§V3 — the number shown and the entries shown must agree.

    Not tautological: a drilldown that filtered on payer alone would pass
    §V1 and still show entries that cannot account for the figure above them.
    """
    net = balances(ledger)
    for member_id, shown in net.items():
        assert balances(drilldown(ledger, member_id)).get(member_id, 0) == shown


@given(ledger=ledgers)
def test_v3_drilldown_never_shows_an_entry_that_does_not_touch_the_member(ledger):
    for member_id in balances(ledger):
        for entry in drilldown(ledger, member_id):
            assert entry.payer == member_id or member_id in entry.shares
