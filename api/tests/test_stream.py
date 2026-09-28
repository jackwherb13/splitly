"""Entry-created notifications via DynamoDB Streams — SPEC §T11, §C10, §C29.

The stream carries every write to the table, not only entries: members and
push subscriptions share the house partition. Only a newly inserted entry is
a §C10 trigger.

Failures are logged and swallowed, never raised. A raise makes Lambda retry
the whole batch, which re-notifies everyone who already got it and retries a
dead subscription — the retry §V7 forbids.
"""

import os
from datetime import UTC, datetime

import boto3
import pytest
from boto3.dynamodb.types import TypeSerializer
from moto import mock_aws

from splitly import stream
from splitly.ledger import Entry, Member
from splitly.notifications import SubscriptionGone
from splitly.store import Store

TABLE = "splitly-test"


@pytest.fixture(autouse=True)
def aws_credentials(monkeypatch):
    for key in ("AWS_ACCESS_KEY_ID", "AWS_SECRET_ACCESS_KEY", "AWS_SESSION_TOKEN"):
        monkeypatch.setitem(os.environ, key, "testing")
    monkeypatch.setitem(os.environ, "AWS_DEFAULT_REGION", "us-east-1")
    monkeypatch.delenv("AWS_PROFILE", raising=False)


@pytest.fixture
def table(monkeypatch):
    with mock_aws():
        ddb = boto3.resource("dynamodb", region_name="us-east-1")
        live = ddb.create_table(
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
        store = Store(live)
        for member_id, name in [("jackson", "Jackson"), ("alice", "Alice"), ("dan", "Dan")]:
            store.put_member("h1", Member(member_id=member_id, name=name))
            store.put_push_subscription("h1", member_id, sub(member_id))
        monkeypatch.setattr(stream, "_store", store)
        yield live


def sub(member_id, device="phone"):
    return {"endpoint": f"https://push.example.com/{member_id}/{device}", "keys": {}}


class Recorder:
    """Stands in for notifications.send."""

    def __init__(self, fail=None):
        self.sent = []
        self.fail = fail or {}

    def __call__(self, subscription, payload):
        self.sent.append((subscription["endpoint"], payload))
        if subscription["endpoint"] in self.fail:
            raise self.fail[subscription["endpoint"]]


@pytest.fixture
def sent(monkeypatch):
    recorder = Recorder()
    monkeypatch.setattr(stream, "send", recorder)
    return recorder


def entry(kind="expense", payer="jackson", shares=None):
    shares = shares or {"jackson": 1000, "alice": 1000, "dan": 1000}
    return Entry(
        entry_id="e1",
        house_id="h1",
        created_at=datetime(2026, 9, 28, tzinfo=UTC),
        description="groceries",
        kind=kind,
        total=sum(shares.values()),
        payer=payer,
        shares=shares,
    )


def record(table, sk, event_name="INSERT"):
    """A stream record carrying the item exactly as the table holds it."""
    item = table.get_item(Key={"pk": "HOUSE#h1", "sk": sk})["Item"]
    image = {key: TypeSerializer().serialize(value) for key, value in item.items()}
    return {"eventName": event_name, "dynamodb": {"NewImage": image}}


def inserted(table, new_entry):
    Store(table).put_entry(new_entry)
    return {"Records": [record(table, f"ENTRY#{new_entry.entry_id}")]}


def endpoints(recorder):
    return sorted(endpoint for endpoint, _ in recorder.sent)


def test_an_expense_notifies_everyone_who_owes_a_share(table, sent):
    stream.handle(inserted(table, entry()), None)

    assert endpoints(sent) == [sub("alice")["endpoint"], sub("dan")["endpoint"]]


def test_the_payer_is_not_notified_of_their_own_payment(table, sent):
    stream.handle(inserted(table, entry()), None)

    assert sub("jackson")["endpoint"] not in endpoints(sent)


def test_the_payload_names_the_payer_and_the_recipients_share(table, sent):
    stream.handle(inserted(table, entry()), None)

    _, payload = sent.sent[0]
    assert payload["title"] == "groceries"
    assert "Jackson" in payload["body"]
    assert "$10.00" in payload["body"]


def test_a_payment_tells_the_recipient_they_were_paid(table, sent):
    payment = entry(kind="payment", payer="dan", shares={"jackson": 2050})
    stream.handle(inserted(table, payment), None)

    ((endpoint, payload),) = sent.sent
    assert endpoint == sub("jackson")["endpoint"]
    assert "Dan" in payload["body"]
    assert "$20.50" in payload["body"]


def test_every_device_a_member_holds_is_notified(table, sent):
    Store(table).put_push_subscription("h1", "alice", sub("alice", "laptop"))

    stream.handle(inserted(table, entry()), None)

    assert sub("alice", "laptop")["endpoint"] in endpoints(sent)
    assert sub("alice", "phone")["endpoint"] in endpoints(sent)


def test_member_and_subscription_writes_are_not_entries(table, sent):
    """They share the house partition, so they share the stream."""
    pushsub = next(
        item["sk"] for item in table.scan()["Items"] if item["sk"].startswith("PUSHSUB#alice")
    )
    stream.handle({"Records": [record(table, "MEMBER#alice"), record(table, pushsub)]}, None)

    assert sent.sent == []


def test_only_inserts_are_triggers(table, sent):
    """§V8 means an entry is never modified, but the member active toggle is
    a MODIFY on the same stream."""
    Store(table).put_entry(entry())
    stream.handle({"Records": [record(table, "ENTRY#e1", event_name="MODIFY")]}, None)

    assert sent.sent == []


@pytest.mark.parametrize(
    "failure", [SubscriptionGone("gone"), RuntimeError("push service 500")]
)
def test_a_failed_send_neither_stops_the_others_nor_raises(table, monkeypatch, failure):
    """§V7 — raising would make Lambda retry the batch: a dead subscription
    retried, and every live one notified twice."""
    recorder = Recorder(fail={sub("alice")["endpoint"]: failure})
    monkeypatch.setattr(stream, "send", recorder)

    stream.handle(inserted(table, entry()), None)

    assert sub("dan")["endpoint"] in endpoints(recorder)


def test_a_failed_send_is_retried_by_nothing(table, monkeypatch):
    recorder = Recorder(fail={sub("alice")["endpoint"]: SubscriptionGone("gone")})
    monkeypatch.setattr(stream, "send", recorder)

    stream.handle(inserted(table, entry()), None)

    assert endpoints(recorder).count(sub("alice")["endpoint"]) == 1


def test_importing_the_module_needs_no_aws(monkeypatch):
    """The store is built lazily, like the API's, so a cold import cannot
    fail on configuration before the handler runs."""
    import importlib

    monkeypatch.delenv("SPLITLY_TABLE", raising=False)
    importlib.reload(stream)


@pytest.mark.parametrize(
    "failure, reason",
    [(SubscriptionGone("gone"), "gone"), (RuntimeError("push service 500"), "error")],
)
def test_a_failed_send_is_loud_not_silent(table, monkeypatch, capsys, caplog, failure, reason):
    """Swallowed so the batch is not retried (§V7), but never quietly: an
    ERROR log and a CloudWatch metric (EMF) per failure, for T21 to alarm on."""
    import json
    import logging

    monkeypatch.setattr(stream, "send", Recorder(fail={sub("alice")["endpoint"]: failure}))

    with caplog.at_level(logging.ERROR, logger="splitly.stream"):
        stream.handle(inserted(table, entry()), None)

    assert any(r.levelno == logging.ERROR for r in caplog.records)
    metrics = [json.loads(line) for line in capsys.readouterr().out.splitlines()]
    (metric,) = [m for m in metrics if "PushSendFailed" in m]
    assert metric["PushSendFailed"] == 1
    assert metric["Reason"] == reason
    (declared,) = metric["_aws"]["CloudWatchMetrics"]
    assert declared["Namespace"] == "Splitly"
    assert declared["Metrics"] == [{"Name": "PushSendFailed", "Unit": "Count"}]
