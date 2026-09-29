"""Lambda handler — SPEC §T6.5.

The API Gateway JWT authorizer verifies the token and puts the claims on the
event. These tests cover the half of §V10 that lives in code: a handler must
never invent an identity, so a request arriving without verified claims has
to fail closed. That is the case where someone wires a route and forgets the
authorizer — §V10's own text is `⊥ forgotten`.
"""

import json
import os
from datetime import UTC, datetime

import boto3
import pytest
from moto import mock_aws

from splitly import handler
from splitly.handler import ADMIN, ROUTES, SESSION, Unauthenticated, handle, me
from splitly.ledger import Member
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
        "member_id": "jackson",
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
        live.put_user_house(SUB, "h1", member_id="jackson")
        live.put_user_house(ADMIN_SUB, "h1", member_id="jackson", admin=True)
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


# --- §T10: push subscriptions ---


PUSH = {
    "endpoint": "https://push.example.com/abc",
    "keys": {"p256dh": "key", "auth": "secret"},
}


def test_a_subscription_is_stored_against_the_session_member(store):
    """§C51 again — the body says nothing about who this is."""
    response = handle(request("POST /subscriptions", {"subscription": PUSH}), None)
    assert response["statusCode"] == 201

    stored = store.list_push_subscriptions("h1")
    assert len(stored) == 1
    assert stored[0]["member_id"] == "jackson"
    assert stored[0]["subscription"] == PUSH


def test_a_subscription_cannot_be_filed_under_another_member(store):
    """A body naming someone else is ignored, exactly as house_id is."""
    handle(
        request("POST /subscriptions", {"subscription": PUSH, "member_id": "dan"}),
        None,
    )
    assert store.list_push_subscriptions("h1")[0]["member_id"] == "jackson"


def test_resubscribing_does_not_pile_up_duplicates(store):
    """§C15 re-subscribes on every app launch."""
    handle(request("POST /subscriptions", {"subscription": PUSH}), None)
    handle(request("POST /subscriptions", {"subscription": PUSH}), None)
    assert len(store.list_push_subscriptions("h1")) == 1


def test_a_subscription_without_an_endpoint_is_a_client_error(store):
    assert handle(request("POST /subscriptions", {"subscription": {}}), None)[
        "statusCode"
    ] == 400


# --- add member (§T11.5, §V19, §V20) -------------------------------------


class FakeCognito:
    """Stands in for the cognito-idp client. Raises the real botocore error
    shape, because the handler branches on the error code."""

    def __init__(self, existing=None, invalid=False):
        self.existing = existing or {}  # username -> sub
        self.invalid = invalid
        self.created = []

    @staticmethod
    def _error(code):
        from botocore.exceptions import ClientError

        return ClientError({"Error": {"Code": code, "Message": code}}, "op")

    def admin_create_user(self, **kwargs):
        if self.invalid:
            raise self._error("InvalidParameterException")
        if kwargs["Username"] in self.existing:
            raise self._error("UsernameExistsException")
        self.created.append(kwargs)
        sub = f"sub-{len(self.created)}"
        self.existing[kwargs["Username"]] = sub
        return {"User": {"Username": sub}}

    def admin_get_user(self, **kwargs):
        return {"Username": self.existing[kwargs["Username"]]}


@pytest.fixture
def cognito(monkeypatch):
    fake = FakeCognito()
    monkeypatch.setattr(handler, "_cognito", fake)
    monkeypatch.setitem(os.environ, "SPLITLY_USER_POOL_ID", "us-east-1_pool")
    return fake


def add(body):
    return handle(request("POST /members", body=body, sub=ADMIN_SUB), None)


def test_an_admin_adds_a_member_who_can_then_sign_in(store, cognito):
    response = add({"name": "Gabe", "email": "gmetcal@gmu.edu"})

    assert response["statusCode"] == 201
    assert [m.name for m in store.list_members("h1")] == ["Gabe"]
    (created,) = cognito.created
    found = store.membership(cognito.existing["gmetcal@gmu.edu"])
    assert (found.house_id, found.member_id, found.admin) == ("h1", "gabe", False)
    # §C4 — no invite mail with a temporary password in it.
    assert created["MessageAction"] == "SUPPRESS"
    assert {"Name": "email_verified", "Value": "true"} in created["UserAttributes"]


def test_v19_the_email_is_lowercased_before_cognito_sees_it(store, cognito):
    """B7 — the pool is case-sensitive, so `Gmetcal@` would make a user who
    can only ever sign in by typing the capital."""
    add({"name": "Gabe", "email": "  Gmetcal@GMU.edu "})

    (created,) = cognito.created
    assert created["Username"] == "gmetcal@gmu.edu"
    assert {"Name": "email", "Value": "gmetcal@gmu.edu"} in created["UserAttributes"]


def test_the_new_member_is_never_an_admin_whatever_the_body_says(store, cognito):
    add({"name": "Gabe", "email": "g@example.com", "admin": True})

    assert store.membership(cognito.existing["g@example.com"]).admin is False


def test_the_house_comes_from_the_session_not_the_body(store, cognito):
    """§C51."""
    add({"name": "Gabe", "email": "g@example.com", "house_id": "other"})

    assert store.membership(cognito.existing["g@example.com"]).house_id == "h1"
    assert store.list_members("other") == []


def test_v20_a_taken_name_is_a_conflict(store, cognito):
    add({"name": "Dan", "email": "dan1@example.com"})

    response = add({"name": "Dan", "email": "dan2@example.com"})

    assert response["statusCode"] == 409
    assert store.membership(cognito.existing["dan1@example.com"]).member_id == "dan"


def test_v20_an_email_already_in_a_house_is_a_conflict_not_a_move(store, cognito):
    add({"name": "Gabe", "email": "g@example.com"})

    response = add({"name": "Gabriel", "email": "g@example.com"})

    assert response["statusCode"] == 409
    assert store.membership(cognito.existing["g@example.com"]).member_id == "gabe"


def test_v20_an_orphaned_login_is_linked_on_retry(store, cognito):
    """Cognito succeeded and the table write did not. The retry must finish
    the job rather than be refused forever."""
    cognito.existing["g@example.com"] = "sub-orphan"

    response = add({"name": "Gabe", "email": "g@example.com"})

    assert response["statusCode"] == 201
    assert store.membership("sub-orphan").member_id == "gabe"


def test_an_invalid_email_is_a_client_error_not_a_500(store, monkeypatch):
    """A 500 comes back without CORS headers, which Safari reports as
    "Load failed" and hides the real reason."""
    monkeypatch.setattr(handler, "_cognito", FakeCognito(invalid=True))
    monkeypatch.setitem(os.environ, "SPLITLY_USER_POOL_ID", "us-east-1_pool")

    assert add({"name": "Gabe", "email": "not-an-email"})["statusCode"] == 400


@pytest.mark.parametrize("body", [{"name": "", "email": "g@example.com"}, {"name": "Gabe"}])
def test_a_name_and_an_email_are_both_required(store, cognito, body):
    assert add(body)["statusCode"] == 400
    assert cognito.created == []


def test_v23_every_route_the_handler_serves_exists_at_the_gateway():
    """T10's "Load failed" was a route the gateway did not have. A route
    missing from either side is unreachable or unhandled."""
    import re
    from pathlib import Path

    api_tf = (Path(__file__).parents[2] / "infra" / "api.tf").read_text(encoding="utf-8")
    gateway = set(re.findall(r'route_key\s*=\s*"([^"]+)"', api_tf))

    assert gateway == set(ROUTES) | {"GET /me", "POST /receipts"}


# --- manual nudge (§T12, §V24, §V25) --------------------------------------

DAN_SUB = "cognito-dan"


@pytest.fixture
def owed(store, monkeypatch):
    """Jackson fronted groceries; Dan owes the house. Dan's phone is subscribed."""
    from splitly import notifications

    store.put_member("h1", Member(member_id="jackson", name="Jackson"))
    store.put_member("h1", Member(member_id="dan", name="Dan"))
    store.put_user_house(DAN_SUB, "h1", member_id="dan")
    handle(request("POST /entries", body={
        "description": "groceries", "kind": "expense", "total": 2000, "payer": "jackson",
        "mode": "all_to_one", "member": "dan",
    }), None)
    store.put_push_subscription("h1", "dan", {"endpoint": "https://push.example.com/dan"})

    sent = []
    monkeypatch.setattr(notifications, "send", lambda sub, payload: sent.append((sub, payload)))
    return sent


def nudge(member_id, sub=SUB):
    return handle(request("POST /nudges", body={"member_id": member_id}, sub=sub), None)


def test_someone_owed_money_can_nudge_a_debtor(store, owed):
    response = nudge("dan")

    assert response["statusCode"] == 201
    ((subscription, payload),) = owed
    assert subscription["endpoint"] == "https://push.example.com/dan"


def test_the_nudge_says_the_house_not_me(store, owed):
    """§V24 — balances are net against the house, not person to person."""
    nudge("dan")

    ((_, payload),) = owed
    assert "Jackson" in payload["title"]
    assert "the house" in payload["body"]
    assert "$20.00" in payload["body"]


def test_v24_someone_not_owed_money_cannot_nudge(store, owed):
    """Dan owes; he does not get to chase anyone."""
    store.put_member("h1", Member(member_id="alice", name="Alice"))

    assert nudge("jackson", sub=DAN_SUB)["statusCode"] == 403
    assert owed == []


def test_v24_someone_not_in_debt_cannot_be_nudged(store, owed):
    assert nudge("jackson")["statusCode"] == 400
    assert owed == []


def test_v25_a_second_nudge_within_the_hour_is_refused(store, owed):
    nudge("dan")

    response = nudge("dan")

    assert response["statusCode"] == 429
    assert len(owed) == 1


def test_a_debtor_without_notifications_is_a_conflict_and_keeps_the_hour_free(store, owed):
    """Nothing could be delivered, so nothing should be used up."""
    store.put_member("h1", Member(member_id="eve", name="Eve"))
    handle(request("POST /entries", body={
        "description": "rent", "kind": "expense", "total": 500, "payer": "jackson",
        "mode": "all_to_one", "member": "eve",
    }), None)

    assert nudge("eve")["statusCode"] == 409
    assert store.claim_nudge("h1", "eve", by="x", now=datetime.now(UTC)) is True


@pytest.mark.parametrize("failure", ["gone", "error"])
def test_a_failed_nudge_push_is_reported_not_raised(store, owed, monkeypatch, capsys, failure):
    """§V7 — a dead subscription is not retried, and nothing fails silently."""
    from splitly import notifications

    def broken(subscription, payload):
        if failure == "gone":
            raise notifications.SubscriptionGone("gone")
        raise RuntimeError("push service 500")

    monkeypatch.setattr(notifications, "send", broken)

    response = nudge("dan")

    assert response["statusCode"] == 201
    assert json.loads(response["body"])["sent"] == 0
    assert "PushSendFailed" in capsys.readouterr().out


# --- subscription lifecycle (§T13, §V7, §V26) -----------------------------


def test_v7_a_gone_nudge_subscription_is_retired(store, owed, monkeypatch):
    from splitly import notifications

    def gone(subscription, payload):
        raise notifications.SubscriptionGone(subscription["endpoint"])

    monkeypatch.setattr(notifications, "send", gone)
    nudge("dan")

    assert store.list_push_subscriptions("h1") == []


def test_v26_saving_a_dead_endpoint_is_a_410(store):
    """The client's cue to drop the browser subscription and make a new one."""
    subscription = {"endpoint": "https://push.example.com/old", "keys": {}}
    store.put_push_subscription("h1", "jackson", subscription)
    store.retire_push_subscription("h1", "jackson", subscription["endpoint"], now=datetime.now(UTC))

    response = handle(request("POST /subscriptions", body={"subscription": subscription}), None)

    assert response["statusCode"] == 410


# --- delivery receipts (§T14, §V28, §V29) ---------------------------------


def receipt(body):
    """What the service worker sends: no Authorization, so no claims."""
    return handle({"routeKey": "POST /receipts", "body": json.dumps(body)}, None)


def test_v29_a_nudge_is_recorded_with_the_id_it_carries(store, owed):
    nudge("dan")

    ((_, payload),) = owed
    (pushed,) = store.list_pushes("h1", since=datetime(2000, 1, 1, tzinfo=UTC))
    assert (pushed["push_id"], pushed["kind"]) == (payload["push_id"], "nudge")


def test_v28_a_receipt_needs_no_session(store):
    store.record_push("h1", "p1", member_id="dan", kind="entry", now=datetime.now(UTC))

    assert receipt({"house_id": "h1", "push_id": "p1"})["statusCode"] == 204
    (pushed,) = store.list_pushes("h1", since=datetime(2000, 1, 1, tzinfo=UTC))
    assert pushed["delivered_at"]


def test_v28_an_unknown_receipt_is_a_404_and_writes_nothing(store):
    before = store._table.scan()["Items"]

    assert receipt({"house_id": "h1", "push_id": "guessed"})["statusCode"] == 404
    assert store._table.scan()["Items"] == before


@pytest.mark.parametrize("body", [{}, {"house_id": "h1"}, {"push_id": "p1"}])
def test_a_receipt_missing_its_ids_is_a_400(store, body):
    assert receipt(body)["statusCode"] == 400


def test_the_delivery_view_summarises_the_last_week(store):
    from datetime import timedelta

    now = datetime.now(UTC)
    store.record_push("h1", "p1", member_id="dan", kind="entry", now=now - timedelta(hours=1))
    store.record_push("h1", "p2", member_id="dan", kind="entry", now=now - timedelta(hours=1))
    store.receive_push("h1", "p1", now=now)

    response = handle(request("GET /deliveries", sub=ADMIN_SUB), None)

    assert response["statusCode"] == 200
    overall = json.loads(response["body"])["overall"]
    assert (overall["received"], overall["undelivered"], overall["rate"]) == (1, 1, 0.5)


def test_v28_receipts_is_the_only_route_without_a_jwt():
    """Every other route keeps the authorizer. Read from the gateway config,
    because that — not the handler — is where the check actually happens."""
    import re
    from pathlib import Path

    api_tf = (Path(__file__).parents[2] / "infra" / "api.tf").read_text(encoding="utf-8")
    blocks = re.findall(r'resource "aws_apigatewayv2_route" "\w+" \{(.*?)\n\}', api_tf, re.S)
    auth = {
        re.search(r'route_key\s*=\s*"([^"]+)"', b).group(1): (
            re.search(r'authorization_type\s*=\s*"([^"]+)"', b) or [None, "NONE"]
        )[1]
        for b in blocks
    }

    assert {route for route, kind in auth.items() if kind != "JWT"} == {"POST /receipts"}
