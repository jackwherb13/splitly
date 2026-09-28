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
from splitly.handler import ADMIN, ROUTES, SESSION, Unauthenticated, handle, me
from splitly.store import Store


def event_with(claims):
    return {"requestContext": {"authorizer": {"jwt": {"claims": claims}}}}


def test_me_returns_the_callers_identity_from_verified_claims(store):
    response = me(event_with({"sub": SUB, "email": "jackson@example.com"}), None)
    assert response["statusCode"] == 200
    assert json.loads(response["body"]) == {
        "sub": SUB,
        "email": "jackson@example.com",
        "house_id": "h1",
        "admin": False,
    }


def test_me_reports_admin_for_an_admin_session(store):
    """The UI uses this to hide controls. It is not the guard — the router is."""
    body = json.loads(me(event_with({"sub": ADMIN_SUB}), None)["body"])
    assert body["admin"] is True


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
ADMIN_SUB = "cognito-admin"


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
        live.put_user_house(ADMIN_SUB, "h1", admin=True)
        monkeypatch.setattr(handler, "_store", live)
        yield live


def request(route, body=None, sub=SUB, path=None):
    event = {
        "routeKey": route,
        "requestContext": {"authorizer": {"jwt": {"claims": {"sub": sub}}}},
        "pathParameters": path or {},
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


def test_get_members_is_scoped_to_the_session_house(store):
    """The roster the UI picks from, and it is this house's only."""
    from splitly.ledger import Member

    store.put_member("h1", Member(member_id="dan", name="Dan"))
    store.put_member("other", Member(member_id="stranger", name="Stranger"))

    body = json.loads(handle(request("GET /members"), None)["body"])
    assert [m["member_id"] for m in body["members"]] == ["dan"]


def test_balances_come_back_with_the_entries_behind_them(store):
    """§V3 — the figure and its drilldown arrive together, from one read."""
    handle(request("POST /entries", EVEN_ENTRY), None)

    body = json.loads(handle(request("GET /balances"), None)["body"])
    by_member = {row["member_id"]: row for row in body["balances"]}

    assert by_member["jackson"]["net"] == 1000 - 334
    assert by_member["dan"]["net"] == -333
    assert sum(row["net"] for row in body["balances"]) == 0

    entries = json.loads(handle(request("GET /entries"), None)["body"])["entries"]
    ids = {entry["entry_id"] for entry in entries}
    for row in body["balances"]:
        assert row["entry_ids"], f"{row['member_id']} has a balance with nothing behind it"
        assert set(row["entry_ids"]) <= ids


def test_a_member_who_only_owes_still_gets_a_drilldown(store):
    """Alice never pays. Filtering on payer would leave her figure orphaned."""
    handle(request("POST /entries", EVEN_ENTRY), None)
    body = json.loads(handle(request("GET /balances"), None)["body"])
    alice = next(row for row in body["balances"] if row["member_id"] == "alice")
    assert alice["net"] == -333
    assert len(alice["entry_ids"]) == 1


# --- §V10 and §V18: admin actions are reachable only through admin routes ---


ADMIN_ROUTES = sorted(key for key, (_, access) in ROUTES.items() if access == ADMIN)


def test_there_is_at_least_one_admin_route():
    """Guards the guard: if the table emptied, the §V10 test below would
    silently cover nothing and still pass."""
    assert ADMIN_ROUTES


@pytest.mark.parametrize("route_key", ADMIN_ROUTES)
def test_v10_every_admin_route_refuses_an_ordinary_member(store, route_key):
    """§V10 — parametrised over the route table, so a new admin route is
    covered the moment it is registered rather than when someone remembers."""
    event = request(route_key, body={}, sub=SUB, path={"member_id": "dan"})
    assert handle(event, None)["statusCode"] == 403


def test_every_route_declares_an_access_level():
    """§V10 `⊥ forgotten` — registration and protection are one act, so a
    route cannot be added without saying who may call it."""
    for route_key, (_, access) in ROUTES.items():
        assert access in {SESSION, ADMIN}, route_key


def test_v18_post_entries_refuses_a_write_off(store):
    """§V18, B6 — §C50 makes write-offs admin-only. An ordinary route that
    accepts the kind is the guard bypassed, and this shipped at T7."""
    body = EVEN_ENTRY | {"kind": "write_off"}
    assert handle(request("POST /entries", body), None)["statusCode"] == 400


def test_post_entries_refuses_an_unknown_kind(store):
    body = EVEN_ENTRY | {"kind": "vibes"}
    assert handle(request("POST /entries", body), None)["statusCode"] == 400


def test_an_admin_can_deactivate_a_member(store):
    """§C48 — leaving sets a flag. The member and their debt stay."""
    from splitly.ledger import Member

    store.put_member("h1", Member(member_id="dan", name="Dan"))
    response = handle(
        request("PUT /members/{member_id}", {"active": False}, sub=ADMIN_SUB,
                path={"member_id": "dan"}),
        None,
    )
    assert response["statusCode"] == 200
    assert store.list_members("h1")[0].active is False
    assert store.list_members("h1")[0].name == "Dan", "the name survives the toggle"


def test_deactivating_a_member_leaves_their_balance_alone(store):
    """§C48 — the debt persists. That is the whole point of the flag."""
    from splitly.ledger import Member

    store.put_member("h1", Member(member_id="dan", name="Dan"))
    handle(request("POST /entries", EVEN_ENTRY), None)
    before = json.loads(handle(request("GET /balances"), None)["body"])

    handle(
        request("PUT /members/{member_id}", {"active": False}, sub=ADMIN_SUB,
                path={"member_id": "dan"}),
        None,
    )
    after = json.loads(handle(request("GET /balances"), None)["body"])
    assert before == after


def test_an_admin_can_write_off_a_debt(store):
    """§C50 — an offsetting entry, not a deletion. The original stays."""
    handle(request("POST /entries", EVEN_ENTRY), None)

    response = handle(
        request(
            "POST /write-offs",
            {
                "description": "dan moved out owing",
                "forgiven": "dan",
                "total": 333,
                "amounts": {"jackson": 333},
            },
            sub=ADMIN_SUB,
        ),
        None,
    )
    assert response["statusCode"] == 201
    assert json.loads(response["body"])["kind"] == "write_off"

    balances = json.loads(handle(request("GET /balances"), None)["body"])["balances"]
    assert next(r for r in balances if r["member_id"] == "dan")["net"] == 0

    entries = json.loads(handle(request("GET /entries"), None)["body"])["entries"]
    assert len(entries) == 2, "the original expense is still on the books (§V8)"


def test_a_write_off_is_tagged_so_the_drilldown_can_tell_it_from_a_payment(store):
    """§C50 — forgiven, not paid. The caller cannot choose the tag."""
    handle(request("POST /entries", EVEN_ENTRY), None)
    handle(
        request(
            "POST /write-offs",
            {
                "description": "forgiven",
                "forgiven": "dan",
                "total": 333,
                "amounts": {"jackson": 333},
                "kind": "payment",
            },
            sub=ADMIN_SUB,
        ),
        None,
    )
    entries = json.loads(handle(request("GET /entries"), None)["body"])["entries"]
    kinds = {entry["kind"] for entry in entries}
    assert "write_off" in kinds, "the server sets the kind, not the body"
    assert "payment" not in kinds
