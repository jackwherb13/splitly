"""Push delivery — SPEC §C9, §C31.

One module, one `send()`. §C9 forbids a Protocol, an adapter or any
selection wiring until a second implementation exists, and web push is the
only one there is. SMS was costed at §R8 and deferred; when it arrives, the
seam gets extracted then, against two real cases instead of one imagined.

VAPID keys live in SSM Parameter Store (§C31) and never in code or
Terraform (§C47). They are read once per warm Lambda rather than per push.

`send` raising `SubscriptionGone` is the only thing that makes §V7 possible
at T13: a dead subscription has to be distinguishable from a push service
having a bad day, or retrying the first would be pointless and retiring the
second would silently unsubscribe a working device.
"""

import json
import logging
import os
import time
from dataclasses import dataclass

import boto3
from pywebpush import WebPushException, webpush

PRIVATE_KEY_PARAM = "/splitly/vapid/private_key"
SUBJECT_PARAM = "/splitly/vapid/subject"

# The push service has forgotten this endpoint. Nothing will ever be
# delivered to it again.
DEAD_STATUSES = frozenset({404, 410})

_config_cache = None

log = logging.getLogger(__name__)


class SubscriptionGone(Exception):
    """The push service says this subscription is dead (§V7, acted on at T13)."""


@dataclass(frozen=True)
class _Config:
    private_key: str
    subject: str


def _read_config():
    client = boto3.client("ssm", region_name=os.environ.get("AWS_DEFAULT_REGION", "us-east-1"))
    found = client.get_parameters(
        Names=[PRIVATE_KEY_PARAM, SUBJECT_PARAM], WithDecryption=True
    )
    values = {parameter["Name"]: parameter["Value"] for parameter in found["Parameters"]}
    return _Config(values[PRIVATE_KEY_PARAM], values[SUBJECT_PARAM])


def _config():
    global _config_cache
    if _config_cache is None:
        _config_cache = _read_config()
    return _config_cache


def send(subscription, payload):
    """Deliver one payload to one subscription.

    `subscription` is the browser's PushSubscription as JSON; `payload` is a
    dict the service worker will render.
    """
    config = _config()
    try:
        webpush(
            subscription_info=subscription,
            data=json.dumps(payload),
            vapid_private_key=config.private_key,
            vapid_claims={"sub": config.subject},
        )
    except WebPushException as exc:
        status = getattr(getattr(exc, "response", None), "status_code", None)
        if status in DEAD_STATUSES:
            raise SubscriptionGone(subscription.get("endpoint")) from exc
        raise


def report_failure(reason, member):
    """Never raised by callers (§V7), never quiet: ERROR + a metric for T21."""
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
