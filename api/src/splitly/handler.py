"""Lambda handler behind the API Gateway HTTP API — SPEC §I `api`.

The JWT authorizer verifies the Cognito token before Lambda is ever invoked,
so a request that reaches here is authenticated. That is only true while the
route carries the authorizer, and §V10's text is `⊥ forgotten` — so missing
claims are an error, never an anonymous caller. Fail closed.

§C51 is the other half: `house_id` comes from the session's `sub`, never from
the request. A body claiming a house it does not own gets the caller's own
house, not the one it asked for.

Privilege works the same way. Every route in ROUTES declares SESSION or ADMIN
and the router enforces it before dispatch, so registering a route and
protecting it are one act — a new admin route cannot be added unguarded, and
the §V10 test is parametrised over this table rather than written per route.
B6 is why: a comment promising a later row would handle it did not stop the
hole shipping.
"""

import json
import os
import re
import uuid
from datetime import UTC, datetime

import boto3
from botocore.exceptions import ClientError

from splitly.ledger import Entry, Member, balances, drilldown
from splitly.splits import all_to_one, even
from splitly.store import AlreadyExists, Store

SESSION = "session"
ADMIN = "admin"

# Kinds an ordinary member may post. `write_off` is absent deliberately: §C50
# makes it admin-only, so it is reachable through POST /write-offs and nowhere
# else (§V18, B6).
MEMBER_KINDS = frozenset({"expense", "payment"})

_store = None
_cognito = None


def _get_store():
    # Built lazily so importing the module needs no AWS, and reused across
    # warm invocations.
    global _store
    if _store is None:
        table = boto3.resource("dynamodb").Table(os.environ["SPLITLY_TABLE"])
        _store = Store(table)
    return _store


def _get_cognito():
    global _cognito
    if _cognito is None:
        _cognito = boto3.client("cognito-idp")
    return _cognito


class Unauthenticated(Exception):
    """No verified JWT claims on the request. The route lost its authorizer."""


class NoHouse(Exception):
    """Authenticated, but not a member of any house."""


class Forbidden(Exception):
    """A member where an admin is required (§V10)."""


class BadRequest(Exception):
    """The caller got it wrong. A 400, never a 500."""


class Conflict(Exception):
    """The thing being created already exists (§V20)."""


def _claims(event):
    try:
        return event["requestContext"]["authorizer"]["jwt"]["claims"]
    except (KeyError, TypeError):
        raise Unauthenticated("no verified JWT claims on the request") from None


def _membership(event):
    """§C51 — the session decides the house, and the privilege. One read."""
    found = _get_store().membership(_claims(event)["sub"])
    if found is None:
        raise NoHouse("this user belongs to no house")
    return found


def _house(event):
    return _membership(event).house_id


def _json(status, body):
    return {
        "statusCode": status,
        "headers": {"content-type": "application/json"},
        "body": json.dumps(body),
    }


def _body(event):
    return json.loads(event.get("body") or "{}")


def _shares(body):
    """§C23's three input modes collapse to §C22's one storage format."""
    mode = body.get("mode")
    total = body["total"]
    if mode == "even":
        return even(total, body["members"], body["payer"])
    if mode == "all_to_one":
        return all_to_one(total, body["member"])
    if mode == "manual":
        return body["amounts"]
    raise BadRequest(f"unknown split mode: {mode!r}")


def _as_dict(entry):
    return {
        "entry_id": entry.entry_id,
        "house_id": entry.house_id,
        "created_at": entry.created_at.isoformat(),
        "description": entry.description,
        "kind": entry.kind,
        "total": entry.total,
        "payer": entry.payer,
        "shares": dict(entry.shares),
    }


def _write(house_id, *, description, kind, total, payer, shares):
    entry = Entry(
        entry_id=str(uuid.uuid4()),
        house_id=house_id,
        created_at=datetime.now(UTC),
        description=description,
        kind=kind,
        total=total,
        payer=payer,
        shares=shares,
    )
    _get_store().put_entry(entry)
    return _json(201, _as_dict(entry))


def me(event, _context):
    try:
        claims = _claims(event)
    except Unauthenticated:
        return _json(401, {"error": "unauthenticated"})
    # Not a guard — the router is. This only lets the UI avoid offering
    # buttons the API would refuse.
    found = _get_store().membership(claims["sub"])
    return _json(
        200,
        {
            "sub": claims["sub"],
            "email": claims.get("email"),
            "house_id": found.house_id if found else None,
            "member_id": found.member_id if found else None,
            "admin": bool(found and found.admin),
        },
    )


def create_entry(event):
    body = _body(event)
    kind = body["kind"]
    if kind not in MEMBER_KINDS:
        raise BadRequest(f"kind {kind!r} cannot be posted here")
    return _write(
        _house(event),
        description=body["description"],
        kind=kind,
        total=body["total"],
        payer=body["payer"],
        shares=_shares(body),
    )


def create_write_off(event):
    """§C50 — forgiving a debt is an entry, not a deletion (§C6, §V8).

    The kind is set here and never read from the body, so a write-off cannot
    be disguised as a payment: §C7's drilldown has to be able to show that
    the money was forgiven rather than paid.

    Allocation is manual by design. An even split would make a housemate who
    fronted nothing reimburse the one who fronted everything.
    """
    body = _body(event)
    return _write(
        _house(event),
        description=body["description"],
        kind="write_off",
        total=body["total"],
        payer=body["forgiven"],
        shares=body["amounts"],
    )


def set_member_active(event):
    """§C48 — leaving sets a flag. Entries and balance are untouched, so the
    debt persists by construction rather than by anyone remembering."""
    house_id = _house(event)
    member_id = (event.get("pathParameters") or {}).get("member_id")
    active = _body(event)["active"]

    existing = next(
        (m for m in _get_store().list_members(house_id) if m.member_id == member_id),
        None,
    )
    if existing is None:
        raise BadRequest(f"no such member: {member_id!r}")

    updated = Member(member_id=existing.member_id, name=existing.name, active=bool(active))
    _get_store().put_member(house_id, updated)
    return _json(
        200,
        {"member_id": updated.member_id, "name": updated.name, "active": updated.active},
    )


def _login_for(email):
    """The Cognito user for this email, created if absent. Already present
    is not an error here: it may be an orphan of a failed add, and §V20
    lets the store decide whether it is already someone's."""
    client = _get_cognito()
    pool = os.environ["SPLITLY_USER_POOL_ID"]
    try:
        created = client.admin_create_user(
            UserPoolId=pool,
            Username=email,
            UserAttributes=[
                {"Name": "email", "Value": email},
                {"Name": "email_verified", "Value": "true"},
            ],
            # §C4 — no invite mail carrying a temporary password.
            MessageAction="SUPPRESS",
        )
        return created["User"]["Username"]
    except ClientError as exc:
        code = exc.response["Error"]["Code"]
        if code == "UsernameExistsException":
            return client.admin_get_user(UserPoolId=pool, Username=email)["Username"]
        if code == "InvalidParameterException":
            raise BadRequest(f"not a usable email: {email!r}") from exc
        raise


def create_member(event):
    """§T11.5 — one act replaces the three writes done by hand for Gabe.

    The email is lowercased because the pool is case-sensitive (§V19, B7).
    The house comes from the session and the new member is never an admin,
    whatever the body says.
    """
    body = _body(event)
    name = (body.get("name") or "").strip()
    email = (body.get("email") or "").strip().lower()
    member_id = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
    if not member_id or not email:
        raise BadRequest("a name and an email are both required")

    house_id = _house(event)
    user_id = _login_for(email)
    try:
        _get_store().add_member(house_id, Member(member_id=member_id, name=name), user_id)
    except AlreadyExists as exc:
        raise Conflict(f"{name} or {email} is already a member") from exc
    return _json(201, {"member_id": member_id, "name": name, "active": True})


def create_subscription(event):
    """§C15, §T10 — store the browser's PushSubscription against this session.

    Both the house and the member come from the session (§C51), so a body
    naming someone else is ignored the same way a body naming another house
    is. Keyed on the endpoint, so re-subscribing at every launch overwrites
    rather than accumulating.
    """
    who = _membership(event)
    subscription = _body(event).get("subscription") or {}
    if not subscription.get("endpoint"):
        raise BadRequest("subscription has no endpoint")
    _get_store().put_push_subscription(who.house_id, who.member_id, subscription)
    return _json(201, {"member_id": who.member_id})


def list_entries(event):
    entries = _get_store().list_entries(_house(event))
    return _json(200, {"entries": [_as_dict(entry) for entry in entries]})


def list_members(event):
    members = _get_store().list_members(_house(event))
    return _json(
        200,
        {
            "members": [
                {"member_id": m.member_id, "name": m.name, "active": m.active}
                for m in members
            ]
        },
    )


def list_balances(event):
    """§C7, §V3 — the net and the entries behind it come from one call.

    Returning the entry ids alongside the figure makes §V3 structural: the
    UI cannot show a balance next to entries that do not account for it,
    because it never computes either one.
    """
    entries = _get_store().list_entries(_house(event))
    net = balances(entries)
    return _json(
        200,
        {
            "balances": [
                {
                    "member_id": member_id,
                    "net": amount,
                    "entry_ids": [e.entry_id for e in drilldown(entries, member_id)],
                }
                for member_id, amount in sorted(net.items())
            ]
        },
    )


ROUTES = {
    "POST /entries": (create_entry, SESSION),
    "GET /entries": (list_entries, SESSION),
    "GET /members": (list_members, SESSION),
    "GET /balances": (list_balances, SESSION),
    "POST /subscriptions": (create_subscription, SESSION),
    "PUT /members/{member_id}": (set_member_active, ADMIN),
    "POST /members": (create_member, ADMIN),
    "POST /write-offs": (create_write_off, ADMIN),
}


def handle(event, context):
    route = event.get("routeKey")
    if route == "GET /me":
        return me(event, context)

    registered = ROUTES.get(route)
    if registered is None:
        return _json(404, {"error": "no such route"})
    action, access = registered

    try:
        # §V10 — enforced here, once, from the table. Not in each handler,
        # where it would be one omission away from being absent.
        if access == ADMIN and not _membership(event).admin:
            raise Forbidden("admin only")
        return action(event)
    except Unauthenticated:
        return _json(401, {"error": "unauthenticated"})
    except NoHouse:
        return _json(403, {"error": "not a member of any house"})
    except Forbidden:
        return _json(403, {"error": "admin only"})
    except Conflict as exc:
        return _json(409, {"error": str(exc)})
    except (BadRequest, ValueError, KeyError) as exc:
        return _json(400, {"error": str(exc)})
