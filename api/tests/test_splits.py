"""Split calculators — SPEC §T7, §C23, §C24.

Three input modes, one storage format (§C22). Every mode emits
{member_id: cents} summing to the entry total, so §V11 holds by
construction and nothing downstream can tell which mode produced it.

Manual mode has no calculator: the caller already supplies the amounts,
and a function that returns its argument is not worth writing.
"""

import pytest

from splitly.splits import all_to_one, even


def test_even_split_divides_exactly_when_it_can():
    assert even(9000, ["jackson", "alice", "dan"], payer="jackson") == {
        "jackson": 3000,
        "alice": 3000,
        "dan": 3000,
    }


def test_even_split_remainder_goes_to_the_payer():
    """§V12, §C24 — 1000 across 3 leaves 1 cent. The payer absorbs it."""
    shares = even(1000, ["jackson", "alice", "dan"], payer="jackson")
    assert shares == {"jackson": 334, "alice": 333, "dan": 333}
    assert sum(shares.values()) == 1000


def test_even_split_remainder_when_the_payer_is_not_in_the_split():
    """§C24 — Jackson buys, Alice and Dan split it. Someone still absorbs."""
    shares = even(1000, ["dan", "alice"], payer="jackson")
    assert sum(shares.values()) == 1000
    assert shares == {"alice": 500, "dan": 500}

    shares = even(1001, ["dan", "alice"], payer="jackson")
    assert sum(shares.values()) == 1001
    assert shares["alice"] == 501, "first by sorted id absorbs, deterministically"


def test_even_split_is_deterministic_regardless_of_member_order():
    a = even(1000, ["dan", "alice", "jackson"], payer="sam")
    b = even(1000, ["jackson", "alice", "dan"], payer="sam")
    assert a == b


def test_even_split_rejects_an_empty_member_list():
    with pytest.raises(ValueError, match="member"):
        even(1000, [], payer="jackson")


def test_all_to_one_gives_the_whole_total_to_one_member():
    assert all_to_one(9000, "dan") == {"dan": 9000}
