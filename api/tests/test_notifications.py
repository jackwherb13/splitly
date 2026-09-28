"""Push delivery — SPEC §T9, §C9, §C31.

§C9 says one module with one `send()`, and explicitly no Protocol, adapter
or selection wiring until a second implementation exists. So these tests
call a function; there is no seam to test around.

`pywebpush` is monkeypatched rather than mocked through a layer of our own,
for the same reason. SSM runs under moto so the config path is exercised
for real instead of stubbed away.
"""

import json
import os

import boto3
import pytest
from moto import mock_aws

from splitly import notifications
from splitly.notifications import SubscriptionGone, send

SUBSCRIPTION = {
    "endpoint": "https://push.example.com/abc",
    "keys": {"p256dh": "key", "auth": "secret"},
}


@pytest.fixture(autouse=True)
def aws_credentials(monkeypatch):
    for key in ("AWS_ACCESS_KEY_ID", "AWS_SECRET_ACCESS_KEY", "AWS_SESSION_TOKEN"):
        monkeypatch.setitem(os.environ, key, "testing")
    monkeypatch.setitem(os.environ, "AWS_DEFAULT_REGION", "us-east-1")
    monkeypatch.delenv("AWS_PROFILE", raising=False)


@pytest.fixture(autouse=True)
def fresh_config(monkeypatch):
    """The config is cached for warm Lambda invocations; tests must not share it."""
    monkeypatch.setattr(notifications, "_config_cache", None)


@pytest.fixture
def ssm(monkeypatch):
    with mock_aws():
        client = boto3.client("ssm", region_name="us-east-1")
        client.put_parameter(
            Name="/splitly/vapid/private_key", Value="a-private-key", Type="SecureString"
        )
        client.put_parameter(
            Name="/splitly/vapid/subject", Value="mailto:splitly@example.com", Type="String"
        )
        yield client


class Recorder:
    """Stands in for pywebpush.webpush and remembers what it was handed."""

    def __init__(self, raises=None):
        self.calls = []
        self.raises = raises

    def __call__(self, **kwargs):
        self.calls.append(kwargs)
        if self.raises:
            raise self.raises


def gone(status):
    """A WebPushException shaped the way pywebpush actually raises it."""
    from pywebpush import WebPushException

    class Response:
        status_code = status

    return WebPushException("push failed", response=Response())


def test_send_posts_the_payload_to_the_subscription(ssm, monkeypatch):
    recorder = Recorder()
    monkeypatch.setattr(notifications, "webpush", recorder)

    send(SUBSCRIPTION, {"title": "Groceries", "body": "Jackson added 30.00"})

    (call,) = recorder.calls
    assert call["subscription_info"] == SUBSCRIPTION
    assert json.loads(call["data"]) == {"title": "Groceries", "body": "Jackson added 30.00"}


def test_send_signs_with_the_vapid_key_from_ssm(ssm, monkeypatch):
    """§C31 — the private key lives in Parameter Store, never in code."""
    recorder = Recorder()
    monkeypatch.setattr(notifications, "webpush", recorder)

    send(SUBSCRIPTION, {"title": "hi"})

    (call,) = recorder.calls
    assert call["vapid_private_key"] == "a-private-key"
    assert call["vapid_claims"]["sub"] == "mailto:splitly@example.com"


def test_a_410_becomes_subscription_gone(ssm, monkeypatch):
    """§V7 lives at T13, but it can only act on what `send` tells it. A dead
    subscription has to be distinguishable from a push service having a bad day."""
    monkeypatch.setattr(notifications, "webpush", Recorder(raises=gone(410)))

    with pytest.raises(SubscriptionGone):
        send(SUBSCRIPTION, {"title": "hi"})


def test_a_404_becomes_subscription_gone(ssm, monkeypatch):
    """404 means the endpoint no longer exists — as dead as a 410."""
    monkeypatch.setattr(notifications, "webpush", Recorder(raises=gone(404)))

    with pytest.raises(SubscriptionGone):
        send(SUBSCRIPTION, {"title": "hi"})


def test_other_failures_are_not_mistaken_for_a_dead_subscription(ssm, monkeypatch):
    """A 500 is the push service failing. Retiring the subscription for that
    would silently unsubscribe a working device."""
    monkeypatch.setattr(notifications, "webpush", Recorder(raises=gone(500)))

    with pytest.raises(Exception) as caught:
        send(SUBSCRIPTION, {"title": "hi"})
    assert not isinstance(caught.value, SubscriptionGone)


def test_the_config_is_read_once_and_reused(ssm, monkeypatch):
    """Warm Lambda invocations should not re-read Parameter Store every push."""
    monkeypatch.setattr(notifications, "webpush", Recorder())
    reads = []
    original = notifications._read_config

    def counted():
        reads.append(1)
        return original()

    monkeypatch.setattr(notifications, "_read_config", counted)

    send(SUBSCRIPTION, {"title": "one"})
    send(SUBSCRIPTION, {"title": "two"})
    assert len(reads) == 1


def test_module_exposes_send_and_no_selection_wiring():
    """§C9 — one module, one function. No Protocol, adapter or registry until
    a second implementation exists to justify one."""
    public = {name for name in dir(notifications) if not name.startswith("_")}
    assert "send" in public
    assert not {name for name in public if "Notifier" in name or "Adapter" in name}
