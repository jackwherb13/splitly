"""Ledger core — SPEC §T2.

The entry shape is the one decision everything downstream reads, and it is
driven by two invariants:

  §V11  an entry's per-person shares sum to its total, with no rounding drift
  §V1   the whole ledger sums to zero

Shares are stored, the total is stored, and they are checked against each
other at construction. Deriving the total from the shares instead would make
§V11 vacuous — there would be nothing left to disagree.

§V1 then needs no enforcement at all: an entry credits its payer the total and
debits each member their share, so every entry nets to zero and the ledger
does too. That is why a payment and a write-off (§C50) need no special case —
they are ordinary entries whose shares happen to point the other way.

Money is integer cents throughout. Never floats: §V11 and §V12 are unprovable
against binary floating point.

Balances are derived here and never stored (§C6).
"""

from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from datetime import datetime
from types import MappingProxyType


@dataclass(frozen=True)
class Member:
    member_id: str
    name: str
    active: bool = True


@dataclass(frozen=True)
class Membership:
    """What a signed-in user is, in one house (§C51, §V10).

    Admin is a property of a person *in a house*, not of the account, which
    is why it lives here and not in a Cognito group.
    """

    house_id: str
    member_id: str
    admin: bool = False


@dataclass(frozen=True)
class Entry:
    """One immutable ledger row (§C6, §V8).

    kind is "expense", "payment" or "write_off" (§C50). It is not validated
    here — no invariant constrains it yet, and T8.5 introduces the write-off
    path that first cares.
    """

    entry_id: str
    house_id: str
    created_at: datetime
    description: str
    kind: str
    total: int
    payer: str
    shares: Mapping[str, int]
    # §V35 — set on the payment a verify writes, so the stream can tell the
    # payer it was confirmed instead of telling the recipient what they just did.
    pending_id: str | None = None

    def __post_init__(self) -> None:
        if self.total <= 0:
            raise ValueError(f"entry total must be positive, got {self.total}")

        shares_total = sum(self.shares.values())
        if shares_total != self.total:
            raise ValueError(
                f"§V11: shares sum to {shares_total} but entry total is {self.total}"
            )

        # Freezing the dataclass stops rebinding the attribute but still hands
        # out a mutable dict, which would let §V8 be violated through the back
        # door. Copy it, then wrap it read-only.
        object.__setattr__(self, "shares", MappingProxyType(dict(self.shares)))


@dataclass(frozen=True)
class Pending:
    """'I paid you' that the recipient has not answered yet (§T16.6, §V30).

    Not an entry: the ledger only changes when the recipient verifies. Until
    then it still counts as paid, through `balances` (§V34).
    """

    pending_id: str
    house_id: str
    created_at: datetime
    from_member: str
    to_member: str
    amount: int
    status: str  # "pending" | "verified" | "rejected"


def balances(entries: Iterable[Entry], pending: Iterable[Pending] = ()) -> dict[str, int]:
    """Net position per member, derived from entries alone (§C6, §V3).

    Positive means the house owes them; negative means they owe the house.

    §V34 — a pending payment counts as paid until it is rejected, and this is
    the one place that says so. Every consumer (the balances route, nudges,
    reminders) reads it from here, so the screen and a nudge cannot disagree.
    It moves both people, like the payment it stands for, so §V1 still holds.
    """
    net: dict[str, int] = {}
    for entry in entries:
        net[entry.payer] = net.get(entry.payer, 0) + entry.total
        for member_id, share in entry.shares.items():
            net[member_id] = net.get(member_id, 0) - share
    for claim in pending:
        if claim.status != "pending":
            continue
        net[claim.from_member] = net.get(claim.from_member, 0) + claim.amount
        net[claim.to_member] = net.get(claim.to_member, 0) - claim.amount
    return net


def drilldown(entries: Iterable[Entry], member_id: str) -> list[Entry]:
    """The entries behind one member's balance (§C7, §V3).

    An entry touches a member if they paid for it or owe part of it. Filtering
    on the payer alone is the tempting mistake: someone who never pays for
    anything would then show a balance with nothing to explain it, and §V1
    would still hold.
    """
    return [
        entry
        for entry in entries
        if entry.payer == member_id or member_id in entry.shares
    ]
