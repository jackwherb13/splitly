"""Lambda handler — SPEC §T6.5.

The API Gateway JWT authorizer verifies the token and puts the claims on the
event. These tests cover the half of §V10 that lives in code: a handler must
never invent an identity, so a request arriving without verified claims has
to fail closed. That is the case where someone wires a route and forgets the
authorizer — §V10's own text is `⊥ forgotten`.
"""

import json
import os

import boto3
import pytest
from moto import mock_aws

from splitly import handler
from splitly.handler import Unauthenticated, handle, me
from splitly.store import Store


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


# --- routes (§C51, §C23, §V11, §V12) --------------------------------


TABLE = "splitly-test"
SUB = "cognito-sub-1"


@pytest.fixture(autouse=True)
def aws_credentials(monkeypatch):
    for key in ("AWS_ACCESS_KEY_ID", "AWS_SECRET_ACCESS_KEY", "AWS_SESSION_TOKEN"):
        monkeypatch.setitem(os.environ, key, "testing")
    monkeypatch.setitem(os.environ, "AWS_DEFAULT_REGION", "us-east-1")
    monkeypatch.delenv("AWS_PROFILE", raising=False)


@pytest.fixture
def store(monkeypatch):
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
        live = Store(ddb.Table(TABLE))
        live.put_user_house(SUB, "h1")
        monkeypatch.setattr(handler, "_store", live)
        yield live


def request(route, body=None, sub=SUB):
    event = {
        "routeKey": route,
        "requestContext": {"authorizer": {"jwt": {"claims": {"sub": sub}}}},
    }
    if body is not None:
        event["body"] = json.dumps(body)
    return event


EVEN_ENTRY = {
    "description": "groceries",
    "kind": "expense",
    "total": 1000,
    "payer": "jackson",
    "mode": "even",
    "members": ["jackson", "alice", "dan"],
}


def test_post_entries_creates_an_entry_and_get_returns_it(store):
    created = handle(request("POST /entries", EVEN_ENTRY), None)
    assert created["statusCode"] == 201

    listed = json.loads(handle(request("GET /entries"), None)["body"])
    assert len(listed["entries"]) == 1
    assert listed["entries"][0]["description"] == "groceries"


def test_even_mode_gives_the_remainder_to_the_payer(store):
    """§V12 end to end — 1000 across 3 through the real route."""
    handle(request("POST /entries", EVEN_ENTRY), None)
    entry = json.loads(handle(request("GET /entries"), None)["body"])["entries"][0]
    assert entry["shares"] == {"jackson": 334, "alice": 333, "dan": 333}


def test_house_id_in_the_body_is_ignored(store):
    """§C51 — the only house a request can touch is the session's."""
    handle(request("POST /entries", EVEN_ENTRY | {"house_id": "someone-elses"}), None)

    entry = json.loads(handle(request("GET /entries"), None)["body"])["entries"][0]
    assert entry["house_id"] == "h1"
    assert store.list_entries("someone-elses") == []


def test_a_user_with_no_house_is_refused(store):
    """Never fall back to a default house — that is a cross-tenant leak."""
    assert handle(request("GET /entries", sub="stranger"), None)["statusCode"] == 403


def test_routes_reject_a_request_with_no_verified_claims(store):
    event = {"routeKey": "GET /entries", "requestContext": {}}
    assert handle(event, None)["statusCode"] == 401


def test_shares_that_do_not_sum_to_the_total_are_a_client_error(store):
    """§V11 — a 400, not a 500. The caller got it wrong, not the server."""
    bad = {
        "description": "rent",
        "kind": "expense",
        "total": 9000,
        "payer": "jackson",
        "mode": "manual",
        "amounts": {"jackson": 3000, "alice": 3000, "dan": 2999},
    }
    assert handle(request("POST /entries", bad), None)["statusCode"] == 400


def test_all_to_one_mode(store):
    body = {
        "description": "dan's parking fine",
        "kind": "expense",
        "total": 5000,
        "payer": "jackson",
        "mode": "all_to_one",
        "member": "dan",
    }
    assert handle(request("POST /entries", body), None)["statusCode"] == 201
    entry = json.loads(handle(request("GET /entries"), None)["body"])["entries"][0]
    assert entry["shares"] == {"dan": 5000}


def test_an_unknown_mode_is_a_client_error(store):
    assert handle(request("POST /entries", EVEN_ENTRY | {"mode": "psychic"}), None)[
        "statusCode"
    ] == 400


def test_an_unknown_route_is_a_404(store):
    assert handle(request("DELETE /entries"), None)["statusCode"] == 404
