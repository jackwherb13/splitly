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
from splitly.store import AlreadyExists, DuplicateEntry, Store

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
    assert public == {
        "put_entry",
        "list_entries",
        "put_member",
        "list_members",
        "put_user_house",
        "add_member",
        "claim_nudge",
        "membership",
        "put_push_subscription",
        "list_push_subscriptions",
    }


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


def test_membership_round_trips_with_member_id_and_admin(store):
    """§C51 — the session's `sub` is the only input. It has to yield both the
    house and *which housemate this is*, or nothing can be addressed to them."""
    store.put_user_house("cognito-sub-1", "h1", member_id="jackson", admin=True)
    found = store.membership("cognito-sub-1")
    assert found.house_id == "h1"
    assert found.member_id == "jackson"
    assert found.admin is True


def test_membership_defaults_to_not_admin(store):
    """Privilege is opt-in. A seeded user is an ordinary member."""
    store.put_user_house("cognito-sub-2", "h1")
    assert store.membership("cognito-sub-2").admin is False


def test_membership_for_an_unknown_user_is_none(store):
    """Never a default house, and never a default admin."""
    assert store.membership("cognito-sub-nobody") is None


SUBSCRIPTION = {
    "endpoint": "https://push.example.com/abc",
    "keys": {"p256dh": "key", "auth": "secret"},
}


def test_push_subscriptions_round_trip(store):
    store.put_push_subscription("h1", "jackson", SUBSCRIPTION)
    stored = store.list_push_subscriptions("h1")
    assert len(stored) == 1
    assert stored[0]["member_id"] == "jackson"
    assert stored[0]["subscription"] == SUBSCRIPTION


def test_resubscribing_the_same_endpoint_does_not_duplicate(store):
    """§C15 re-subscribes on every launch. Keying on the endpoint makes that
    idempotent by construction rather than by a dedupe pass."""
    store.put_push_subscription("h1", "jackson", SUBSCRIPTION)
    store.put_push_subscription("h1", "jackson", SUBSCRIPTION)
    assert len(store.list_push_subscriptions("h1")) == 1


def test_one_member_can_have_several_devices(store):
    """A phone and a laptop are two endpoints, and both should get notified."""
    other = SUBSCRIPTION | {"endpoint": "https://push.example.com/laptop"}
    store.put_push_subscription("h1", "jackson", SUBSCRIPTION)
    store.put_push_subscription("h1", "jackson", other)
    assert len(store.list_push_subscriptions("h1")) == 2


def test_push_subscriptions_are_scoped_to_one_house(store):
    store.put_push_subscription("h1", "jackson", SUBSCRIPTION)
    store.put_push_subscription("other", "stranger", SUBSCRIPTION)
    assert [s["member_id"] for s in store.list_push_subscriptions("h1")] == ["jackson"]


def test_push_subscriptions_do_not_collide_with_entries_or_members(store):
    """Everything shares one partition; only the sort-key prefix separates them."""
    store.put_entry(make_entry())
    store.put_member("h1", Member(member_id="dan", name="Dan"))
    store.put_push_subscription("h1", "jackson", SUBSCRIPTION)
    assert len(store.list_entries("h1")) == 1
    assert len(store.list_members("h1")) == 1
    assert len(store.list_push_subscriptions("h1")) == 1


# --- add member (§T11.5, §V20) -------------------------------------------


def test_add_member_writes_the_member_and_the_login_link(store):
    store.add_member("h1", Member(member_id="gabe", name="Gabe"), user_id="sub-gabe")

    assert [m.name for m in store.list_members("h1")] == ["Gabe"]
    found = store.membership("sub-gabe")
    assert (found.house_id, found.member_id, found.admin) == ("h1", "gabe", False)


def test_v20_a_taken_member_id_is_refused_and_the_original_untouched(store):
    """Otherwise a second Dan inherits the first Dan's balance."""
    store.add_member("h1", Member(member_id="dan", name="Dan"), user_id="sub-dan-1")

    with pytest.raises(AlreadyExists):
        store.add_member("h1", Member(member_id="dan", name="Dan"), user_id="sub-dan-2")

    assert [m.name for m in store.list_members("h1")] == ["Dan"]
    assert store.membership("sub-dan-2") is None


def test_v20_a_linked_user_is_refused_and_not_moved(store):
    """Re-linking an existing login would move a real person's identity."""
    store.add_member("h1", Member(member_id="gabe", name="Gabe"), user_id="sub-gabe")

    with pytest.raises(AlreadyExists):
        store.add_member("h2", Member(member_id="gabriel", name="Gabriel"), user_id="sub-gabe")

    assert store.membership("sub-gabe").house_id == "h1"
    assert store.list_members("h2") == []


def test_v20_neither_write_lands_without_the_other(store):
    """One transaction: a refused link must not leave a member row behind,
    or the retry would then collide with its own half."""
    store.put_user_house("sub-taken", "h1", member_id="someone")

    with pytest.raises(AlreadyExists):
        store.add_member("h1", Member(member_id="new", name="New"), user_id="sub-taken")

    assert store.list_members("h1") == []


# --- nudges (§T12, §V25) --------------------------------------------------

NOON = datetime(2026, 9, 29, 12, 0, tzinfo=UTC)


def test_v25_a_debtor_can_be_nudged_once_an_hour(store):
    from datetime import timedelta

    assert store.claim_nudge("h1", "dan", by="jackson", now=NOON) is True
    assert store.claim_nudge("h1", "dan", by="jackson", now=NOON + timedelta(minutes=59)) is False
    assert store.claim_nudge("h1", "dan", by="jackson", now=NOON + timedelta(minutes=61)) is True


def test_v25_the_hour_is_house_wide_not_per_nudger(store):
    """Three housemates must not be able to buzz one person three times."""
    assert store.claim_nudge("h1", "dan", by="jackson", now=NOON) is True
    assert store.claim_nudge("h1", "dan", by="gabe", now=NOON) is False


def test_v25_each_debtor_has_their_own_hour(store):
    assert store.claim_nudge("h1", "dan", by="jackson", now=NOON) is True
    assert store.claim_nudge("h1", "alice", by="jackson", now=NOON) is True


def test_a_claim_leaves_the_ledger_alone(store):
    """Nudges share the house partition; they must not read as entries."""
    store.claim_nudge("h1", "dan", by="jackson", now=NOON)
    assert store.list_entries("h1") == []
    assert store.list_members("h1") == []
