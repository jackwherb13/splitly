"""Lambda handler behind the API Gateway HTTP API — SPEC §I `api`.

The JWT authorizer verifies the Cognito token before Lambda is ever invoked,
so a request that reaches here is authenticated. That is only true while the
route carries the authorizer, and §V10's text is `⊥ forgotten` — so missing
claims are an error, never an anonymous caller. Fail closed.

§C51 is the other half: `house_id` comes from the session's `sub`, never from
the request. A body claiming a house it does not own gets the caller's own
house, not the one it asked for.
"""

import json
import os
import uuid
from datetime import UTC, datetime

import boto3

from splitly.ledger import Entry
from splitly.splits import all_to_one, even
from splitly.store import Store

_store = None


def _get_store():
    # Built lazily so importing the module needs no AWS, and reused across
    # warm invocations.
    global _store
    if _store is None:
        table = boto3.resource("dynamodb").Table(os.environ["SPLITLY_TABLE"])
        _store = Store(table)
    return _store


class Unauthenticated(Exception):
    """No verified JWT claims on the request. The route lost its authorizer."""


class NoHouse(Exception):
    """Authenticated, but not a member of any house."""


class BadRequest(Exception):
    """The caller got it wrong. A 400, never a 500."""


def _claims(event):
    try:
        return event["requestContext"]["authorizer"]["jwt"]["claims"]
    except (KeyError, TypeError):
        raise Unauthenticated("no verified JWT claims on the request") from None


def _house(event):
    """§C51 — the session decides the house. There is no other input."""
    house_id = _get_store().house_for_user(_claims(event)["sub"])
    if house_id is None:
        raise NoHouse("this user belongs to no house")
    return house_id


def _json(status, body):
    return {
        "statusCode": status,
        "headers": {"content-type": "application/json"},
        "body": json.dumps(body),
    }


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


def me(event, _context):
    try:
        claims = _claims(event)
    except Unauthenticated:
        return _json(401, {"error": "unauthenticated"})
    return _json(200, {"sub": claims["sub"], "email": claims.get("email")})


def create_entry(event):
    body = json.loads(event.get("body") or "{}")
    entry = Entry(
        entry_id=str(uuid.uuid4()),
        house_id=_house(event),
        created_at=datetime.now(UTC),
        description=body["description"],
        kind=body["kind"],
        total=body["total"],
        payer=body["payer"],
        shares=_shares(body),
    )
    _get_store().put_entry(entry)
    return _json(201, _as_dict(entry))


def list_entries(event):
    entries = _get_store().list_entries(_house(event))
    return _json(200, {"entries": [_as_dict(entry) for entry in entries]})


ROUTES = {
    "POST /entries": create_entry,
    "GET /entries": list_entries,
}


def handle(event, context):
    route = event.get("routeKey")
    if route == "GET /me":
        return me(event, context)

    action = ROUTES.get(route)
    if action is None:
        return _json(404, {"error": "no such route"})

    try:
        return action(event)
    except Unauthenticated:
        return _json(401, {"error": "unauthenticated"})
    except NoHouse:
        return _json(403, {"error": "not a member of any house"})
    except (BadRequest, ValueError, KeyError) as exc:
        return _json(400, {"error": str(exc)})
