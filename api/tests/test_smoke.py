"""Harness smoke tests for T1.

These prove the test gate itself works — that pytest collects, that the
package imports, and that Hypothesis actually runs (SPEC §C32). Ledger
behaviour is not tested here; that arrives with T2/T3.
"""

from hypothesis import given
from hypothesis import strategies as st

import splitly


def test_package_imports():
    assert splitly.__version__ == "0.0.0"


@given(st.lists(st.integers()))
def test_hypothesis_harness_runs(values):
    """Not ledger logic — this exists to prove Hypothesis is wired up."""
    assert sum(-v for v in values) == -sum(values)
