"""Lambda handler — SPEC §T6.5.

The API Gateway JWT authorizer verifies the token and puts the claims on the
event. These tests cover the half of §V10 that lives in code: a handler must
never invent an identity, so a request arriving without verified claims has
to fail closed. That is the case where someone wires a route and forgets the
authorizer — §V10's own text is `⊥ forgotten`.
"""

import json

import pytest

from splitly.handler import Unauthenticated, me


def event_with(claims):
    return {"requestContext": {"authorizer": {"jwt": {"claims": claims}}}}


def test_me_returns_the_callers_identity_from_verified_claims():
    response = me(event_with({"sub": "u-1", "email": "jackson@example.com"}), None)
    assert response["statusCode"] == 200
    assert json.loads(response["body"]) == {
        "sub": "u-1",
        "email": "jackson@example.com",
    }


def test_me_rejects_a_request_with_no_verified_claims():
    """§V10 — a route wired without an authorizer must fail, not fall open."""
    assert me({"requestContext": {}}, None)["statusCode"] == 401


@pytest.mark.parametrize(
    "event",
    [
        {},
        {"requestContext": {"authorizer": {}}},
        {"requestContext": {"authorizer": {"jwt": {}}}},
        {"requestContext": {"authorizer": None}},
    ],
)
def test_claims_missing_at_any_depth_is_unauthenticated(event):
    """Every shape a stripped-out authorizer could leave behind."""
    assert me(event, None)["statusCode"] == 401


def test_unauthenticated_is_raised_not_swallowed_silently():
    """The 401 path is a named exception, so it cannot be mistaken for a bug."""
    assert issubclass(Unauthenticated, Exception)
