"""Split calculators — SPEC §C23, §C24.

§C22 stores exact per-person amounts and never the split style, so these
functions exist only to turn a UI choice into that one format. Once an entry
is written, nothing can tell which mode produced it — which is the point:
a new split style is a UI feature, never a migration.

Money is integer cents. §V12 is only provable because nothing here divides
in floating point.
"""

from collections.abc import Sequence


def even(total: int, member_ids: Sequence[str], payer: str) -> dict[str, int]:
    """Split evenly; the leftover cents go to one person, never nowhere (§V12).

    §C24 gives the remainder to the payer, who is usually in the split. When
    they are not — you buy something and split it between the others — the
    first member by sorted id absorbs it instead, so the answer is still
    deterministic.
    """
    members = sorted(set(member_ids))
    if not members:
        raise ValueError("an even split needs at least one member")

    base, remainder = divmod(total, len(members))
    shares = {member: base for member in members}
    shares[payer if payer in shares else members[0]] += remainder
    return shares


def all_to_one(total: int, member_id: str) -> dict[str, int]:
    return {member_id: total}
