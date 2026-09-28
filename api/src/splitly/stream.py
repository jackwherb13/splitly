"""Entry-created notifications — SPEC §C10 trigger 1, §C29, §I `strm`.

DynamoDB Streams invokes this for every write to the table. Members and push
subscriptions share the house partition, so only an inserted `ENTRY#` item is
a trigger.

Who hears about it: everyone the entry debits, except the payer. The entry
does not record who typed it in, so this is the nearest honest proxy.

A failed send is never raised, but never quiet either: an ERROR log and a
`PushSendFailed` metric (for T21's alarm). Raising makes Lambda retry the
batch — every live subscription notified twice, and a dead one retried, which
§V7 forbids. Marking dead subscriptions is T13's job.
"""

import json
import logging
import os
import time

import boto3
from boto3.dynamodb.types import TypeDeserializer

from splitly.notifications import SubscriptionGone, send
from splitly.store import Store

log = logging.getLogger(__name__)
log.setLevel(logging.INFO)

_store = None


def _get_store():
    # Built lazily so importing the module needs no AWS, as in handler.py.
    global _store
    if _store is None:
        table = boto3.resource("dynamodb").Table(os.environ["SPLITLY_TABLE"])
        _store = Store(table)
    return _store


def _failed(reason, member):
    log.error("push to %s failed (%s); not retried", member, reason, exc_info=True)
    # CloudWatch Embedded Metric Format: a log line Lambda turns into a metric.
    print(json.dumps({
        "_aws": {
            "Timestamp": int(time.time() * 1000),
            "CloudWatchMetrics": [{
                "Namespace": "Splitly",
                "Dimensions": [["Reason"]],
                "Metrics": [{"Name": "PushSendFailed", "Unit": "Count"}],
            }],
        },
        "Reason": reason,
        "PushSendFailed": 1,
    }))


def _dollars(cents):
    return f"${cents // 100}.{cents % 100:02d}"


def _body(kind, payer_name, share):
    if kind == "payment":
        return f"{payer_name} paid you {_dollars(share)}"
    if kind == "write_off":
        return f"You absorbed {_dollars(share)} of {payer_name}'s written-off debt"
    return f"{payer_name} paid — your share is {_dollars(share)}"


def _notify(image):
    house_id = image["house_id"]
    payer = image["payer"]
    owed = {
        member: int(share)
        for member, share in image["shares"].items()
        if member != payer and share > 0
    }
    if not owed:
        return

    store = _get_store()
    names = {m.member_id: m.name for m in store.list_members(house_id)}
    payer_name = names.get(payer, payer)

    for found in store.list_push_subscriptions(house_id):
        member = found["member_id"]
        if member not in owed:
            continue
        payload = {
            "title": image["description"],
            "body": _body(image["kind"], payer_name, owed[member]),
        }
        try:
            send(found["subscription"], payload)
        except SubscriptionGone:
            _failed("gone", member)
        except Exception:
            _failed("error", member)


def handle(event, _context):
    deserialize = TypeDeserializer().deserialize
    for record in event["Records"]:
        if record["eventName"] != "INSERT":
            continue
        image = {k: deserialize(v) for k, v in record["dynamodb"]["NewImage"].items()}
        if image["sk"].startswith("ENTRY#"):
            _notify(image)
