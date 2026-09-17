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


def balances(entries: Iterable[Entry]) -> dict[str, int]:
    """Net position per member, derived from entries alone (§C6, §V3).

    Positive means the house owes them; negative means they owe the house.
    """
    net: dict[str, int] = {}
    for entry in entries:
        net[entry.payer] = net.get(entry.payer, 0) + entry.total
        for member_id, share in entry.shares.items():
            net[member_id] = net.get(member_id, 0) - share
    return net
