"""Append-only DynamoDB store — SPEC §T2.

Runs against moto, so CI never touches real AWS. The dummy credentials in
`aws_credentials` are a safety belt: if a mock ever fails to engage, the call
fails on bad credentials rather than reaching a live account.

Key schema under test — this is what T2.5 builds:

    pk = HOUSE#<house_id>      sk = ENTRY#<entry_id>
    pk = HOUSE#<house_id>      sk = MEMBER#<member_id>
"""

import os
from datetime import UTC, datetime

import boto3
import pytest
from moto import mock_aws

from splitly.ledger import Entry, Member, balances
from splitly.store import DuplicateEntry, Store

TABLE = "splitly-test"


@pytest.fixture(autouse=True)
def aws_credentials(monkeypatch):
    for key in ("AWS_ACCESS_KEY_ID", "AWS_SECRET_ACCESS_KEY", "AWS_SESSION_TOKEN"):
        monkeypatch.setitem(os.environ, key, "testing")
    monkeypatch.setitem(os.environ, "AWS_DEFAULT_REGION", "us-east-1")
    monkeypatch.delenv("AWS_PROFILE", raising=False)


@pytest.fixture
def store():
    with mock_aws():
        ddb = boto3.resource("dynamodb", region_name="us-east-1")
        ddb.create_table(
            TableName=TABLE,
            KeySchema=[
                {"AttributeName": "pk", "KeyType": "HASH"},
                {"AttributeName": "sk", "KeyType": "RANGE"},
            ],
            AttributeDefinitions=[
                {"AttributeName": "pk", "AttributeType": "S"},
                {"AttributeName": "sk", "AttributeType": "S"},
            ],
            BillingMode="PAY_PER_REQUEST",
        )
        yield Store(ddb.Table(TABLE))


def make_entry(**overrides):
    fields = {
        "entry_id": "e1",
        "house_id": "h1",
        "created_at": datetime(2026, 9, 16, 12, 30, tzinfo=UTC),
        "description": "groceries",
        "kind": "expense",
        "total": 9000,
        "payer": "jackson",
        "shares": {"jackson": 3000, "alice": 3000, "dan": 3000},
    }
    return Entry(**(fields | overrides))


def test_put_and_list_round_trips_an_entry(store):
    original = make_entry()
    store.put_entry(original)
    assert store.list_entries("h1") == [original]


def test_amounts_round_trip_as_int_not_decimal(store):
    """DynamoDB returns numbers as Decimal; cents must come back as int."""
    store.put_entry(make_entry())
    loaded = store.list_entries("h1")[0]
    assert isinstance(loaded.total, int)
    assert all(isinstance(share, int) for share in loaded.shares.values())
    assert loaded.shares == {"jackson": 3000, "alice": 3000, "dan": 3000}


def test_put_entry_rejects_a_duplicate_id(store):
    """§V8 append-only, and the seam §V2 idempotency will use at T17."""
    store.put_entry(make_entry())
    with pytest.raises(DuplicateEntry):
        store.put_entry(make_entry(description="a retry of the same job"))
    assert len(store.list_entries("h1")) == 1


def test_a_rejected_duplicate_leaves_the_original_untouched(store):
    store.put_entry(make_entry())
    with pytest.raises(DuplicateEntry):
        store.put_entry(make_entry(description="clobbered?", total=1, shares={"dan": 1}))
    assert store.list_entries("h1")[0].description == "groceries"


def test_store_exposes_no_mutation_path(store):
    """§V8 — the absence of a mutation path is the enforcement.

    An allowlist, not a search for "update" and "delete": `amend_entry` would
    walk straight past a name filter. Adding a public method has to be
    deliberate, and adding a mutating one has to fail here first.
    """
    public = {name for name in dir(store) if not name.startswith("_")}
    assert public == {"put_entry", "list_entries", "put_member", "list_members"}


def test_list_entries_is_scoped_to_one_house(store):
    store.put_entry(make_entry(entry_id="e1", house_id="h1"))
    store.put_entry(make_entry(entry_id="e2", house_id="h2"))
    assert [e.entry_id for e in store.list_entries("h1")] == ["e1"]


def test_members_round_trip_with_active_flag(store):
    """§C48 — leaving sets a flag, it does not remove the member."""
    store.put_member("h1", Member(member_id="dan", name="Dan", active=False))
    store.put_member("h1", Member(member_id="alice", name="Alice"))
    loaded = {m.member_id: m for m in store.list_members("h1")}
    assert loaded["dan"].active is False
    assert loaded["alice"].active is True


def test_members_and_entries_do_not_collide(store):
    """Both live under one partition key; only the sk prefix separates them."""
    store.put_entry(make_entry())
    store.put_member("h1", Member(member_id="dan", name="Dan"))
    assert len(store.list_entries("h1")) == 1
    assert len(store.list_members("h1")) == 1


def test_balances_derive_from_stored_entries(store):
    store.put_entry(make_entry())
    store.put_entry(
        make_entry(
            entry_id="e2",
            kind="payment",
            description="dan settles up",
            payer="dan",
            total=3000,
            shares={"jackson": 3000},
        )
    )
    net = balances(store.list_entries("h1"))
    assert net["dan"] == 0
    assert sum(net.values()) == 0


def test_list_entries_returns_every_page(store):
    """SPEC §V15 — see B3. DynamoDB caps a Query at 1MB; a ledger past that
    came back as a silent prefix, and `balances()` reported wrong numbers.

    §V1 cannot catch this: a prefix of a zero-sum ledger also sums to zero.
    The description is padded so the page breaks after a couple of hundred
    entries instead of a couple of thousand.
    """
    padding = "x" * 8000
    written = 200
    for i in range(written):
        store.put_entry(make_entry(entry_id=f"e{i:05d}", description=padding))

    loaded = store.list_entries("h1")
    assert len(loaded) == written
    assert balances(loaded)["jackson"] == written * 6000
