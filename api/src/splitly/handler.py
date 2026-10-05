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
from datetime import UTC, datetime, timedelta

import boto3
from botocore.exceptions import ClientError

from splitly.delivery import summarise
from splitly.ledger import Entry, Member, Pending, balances, drilldown
from splitly.splits import all_to_one, even
from splitly.store import AlreadyExists, DeadSubscription, NotPending, Store

SESSION = "session"
ADMIN = "admin"

# Kinds an ordinary member may post. `write_off` is absent deliberately: §C50
# makes it admin-only, so it is reachable through POST /write-offs and nowhere
# else (§V18, B6). `payment` likewise: it is written by a verify and nowhere
# else, or "I paid" + Verify could be skipped by posting one (§V33).
MEMBER_KINDS = frozenset({"expense"})

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


class Gone(Exception):
    """A retired push endpoint was offered again (§V26)."""


class TooSoon(Exception):
    """This debtor was nudged within the hour (§V25)."""


class NotFound(Exception):
    """Nothing by that id in the caller's house (§V32)."""


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


def _net(store, house_id):
    """§V34 — the one balance every route uses: ledger plus pending payments."""
    entries = store.list_entries(house_id)
    pending = store.list_pending(house_id)
    return entries, pending, balances(entries, pending)


def _money(cents):
    return f"${cents // 100}.{cents % 100:02d}"


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


def create_nudge(event):
    """§T12 — someone the house owes chases someone who owes it.

    §V24 is checked here from derived balances, never from what the UI chose
    to show. Balances are net against the house, so the message says so.
    `notifications` is imported here, not at the top: pywebpush comes from a
    layer, and a broken layer should cost this route, not every route.
    """
    from splitly import notifications

    who = _membership(event)
    target = _body(event).get("member_id")
    store = _get_store()

    _, _, net = _net(store, who.house_id)  # §V34
    if net.get(who.member_id, 0) <= 0:
        raise Forbidden("only someone the house owes can nudge")
    owes = -net.get(target, 0)
    if owes <= 0:
        raise BadRequest("they don't owe the house anything")

    subscriptions = [
        found["subscription"]
        for found in store.list_push_subscriptions(who.house_id)
        if found["member_id"] == target
    ]
    # Checked before the hour is claimed: nothing sent, nothing used up.
    if not subscriptions:
        raise Conflict("they haven't turned on notifications")
    if not store.claim_nudge(who.house_id, target, by=who.member_id, now=datetime.now(UTC)):
        raise TooSoon("already nudged in the last hour")

    names = {m.member_id: m.name for m in store.list_members(who.house_id)}
    sent = 0
    for subscription in subscriptions:
        push_id = str(uuid.uuid4())
        payload = {
            "title": f"{names.get(who.member_id, who.member_id)} nudged you",
            "body": f"You owe the house ${owes // 100}.{owes % 100:02d}",
            "push_id": push_id,
            "house_id": who.house_id,
            "receipt_url": os.environ.get("SPLITLY_RECEIPT_URL"),
        }
        # §V29 — recorded before the send, so a failure still counts.
        store.record_push(who.house_id, push_id, target, "nudge", now=datetime.now(UTC))
        try:
            notifications.send(subscription, payload)
            sent += 1
        except notifications.SubscriptionGone:
            notifications.report_failure("gone", target)
            store.retire_push_subscription(  # §V7
                who.house_id, target, subscription["endpoint"], now=datetime.now(UTC)
            )
        except Exception:
            notifications.report_failure("error", target)
    return _json(201, {"sent": sent})


def receive_receipt(event):
    """§T14, §V28 — the one route without a session.

    The service worker has no token: it lives in localStorage, lasts an
    hour, and pushes arrive days after the app was last opened. The push id
    is the credential instead — random, and only ever inside the encrypted
    payload. The house comes from that payload too: a deliberate exception to
    §C51, safe because the store only marks an existing, unreceived push.
    """
    body = _body(event)
    house_id, push_id = body.get("house_id"), body.get("push_id")
    if not (isinstance(house_id, str) and isinstance(push_id, str)):
        return _json(400, {"error": "house_id and push_id are required"})
    if not _get_store().receive_push(house_id, push_id, now=datetime.now(UTC)):
        return _json(404, {"error": "no such push, or already received"})
    return {"statusCode": 204}


def list_deliveries(event):
    """§C19, §V9 — measured, not assumed. The last week, overall and per member."""
    now = datetime.now(UTC)
    pushes = _get_store().list_pushes(_house(event), since=now - timedelta(days=7))
    return _json(200, summarise(pushes, now))


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
    try:
        _get_store().put_push_subscription(who.house_id, who.member_id, subscription)
    except DeadSubscription as exc:
        raise Gone("this subscription is dead; subscribe again") from exc
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
    entries, pending, net = _net(_get_store(), _house(event))
    waiting = [p for p in pending if p.status == "pending"]
    return _json(
        200,
        {
            "balances": [
                {
                    "member_id": member_id,
                    "net": amount,
                    "entry_ids": [e.entry_id for e in drilldown(entries, member_id)],
                    # §V3 — a pending payment moves the figure, so it is listed too.
                    "pending_ids": [
                        p.pending_id for p in waiting if member_id in (p.from_member, p.to_member)
                    ],
                }
                for member_id, amount in sorted(net.items())
            ]
        },
    )


def _pending_dict(pending):
    return {
        "pending_id": pending.pending_id,
        "from": pending.from_member,
        "to": pending.to_member,
        "amount": pending.amount,
        "status": pending.status,
        "created_at": pending.created_at.isoformat(),
    }


def _push_to(store, house_id, member_id, kind, title, body):
    """Tell one member, on every device. None subscribed means nobody told (§V36)."""
    from splitly import notifications

    for found in store.list_push_subscriptions(house_id):
        if found["member_id"] != member_id:
            continue
        push_id = str(uuid.uuid4())
        payload = {
            "title": title,
            "body": body,
            "push_id": push_id,
            "house_id": house_id,
            "receipt_url": os.environ.get("SPLITLY_RECEIPT_URL"),
        }
        store.record_push(house_id, push_id, member_id, kind, now=datetime.now(UTC))  # §V29
        try:
            notifications.send(found["subscription"], payload)
        except notifications.SubscriptionGone:
            notifications.report_failure("gone", member_id)
            store.retire_push_subscription(  # §V7
                house_id, member_id, found["subscription"]["endpoint"], now=datetime.now(UTC)
            )
        except Exception:
            notifications.report_failure("error", member_id)


def create_pending_payment(event):
    """§T16.6 — "I paid you". Counts as paid at once (§V34), lands on the
    ledger only when the recipient verifies (§V30).

    The claimant is the session (§V32). Checked against the pending-adjusted
    balances, so claims cannot add up to more than the debt.
    """
    who = _membership(event)
    body = _body(event)
    to, amount = body.get("to"), body.get("amount")
    if not isinstance(amount, int) or isinstance(amount, bool) or amount <= 0:
        raise BadRequest("amount must be a positive number of cents")

    store = _get_store()
    _, _, net = _net(store, who.house_id)
    owes = -net.get(who.member_id, 0)
    if owes <= 0:
        raise BadRequest("you don't owe the house anything")
    if net.get(to, 0) <= 0:
        raise BadRequest("the house doesn't owe them anything")
    if amount > owes:
        raise BadRequest(f"you only owe {_money(owes)}")

    pending = Pending(
        pending_id=str(uuid.uuid4()),
        house_id=who.house_id,
        created_at=datetime.now(UTC),
        from_member=who.member_id,
        to_member=to,
        amount=amount,
        status="pending",
    )
    store.put_pending(pending)

    names = {m.member_id: m.name for m in store.list_members(who.house_id)}
    name = names.get(who.member_id, who.member_id)
    _push_to(
        store, who.house_id, to, "pending",
        title=f"{name} says they paid", body=f"{name} says they paid you {_money(amount)}",
    )
    return _json(201, _pending_dict(pending))


def list_pending_payments(event):
    pending = _get_store().list_pending(_house(event))
    return _json(200, {"pending": [_pending_dict(p) for p in pending if p.status == "pending"]})


def resolve_pending_payment(event):
    """§T16.6, §V31, §V32 — only the recipient answers, and only once."""
    who = _membership(event)
    pending_id = (event.get("pathParameters") or {}).get("pending_id")
    action = _body(event).get("action")
    if action not in ("verify", "reject"):
        raise BadRequest(f"unknown action: {action!r}")

    store = _get_store()
    pending = next(
        (p for p in store.list_pending(who.house_id) if p.pending_id == pending_id), None
    )
    if pending is None:
        raise NotFound("no such pending payment")
    if pending.to_member != who.member_id:
        raise Forbidden("only the person paid can answer this")

    names = {m.member_id: m.name for m in store.list_members(who.house_id)}
    try:
        if action == "verify":
            payment = Entry(
                entry_id=pending.pending_id,  # §V31 — a retry lands on the same key
                house_id=pending.house_id,
                created_at=datetime.now(UTC),
                description=f"Payment to {names.get(pending.to_member, pending.to_member)}",
                kind="payment",
                total=pending.amount,
                payer=pending.from_member,
                shares={pending.to_member: pending.amount},
                pending_id=pending.pending_id,
            )
            # The stream tells the payer (§V35); nothing to send from here.
            store.resolve_pending(pending, "verified", payment=payment)
            status = "verified"
        else:
            store.resolve_pending(pending, "rejected")
            status = "rejected"
            name = names.get(who.member_id, who.member_id)
            _push_to(
                store, who.house_id, pending.from_member, "rejected",
                title=f"{name} didn't get it",
                body=f"{name} didn't get your {_money(pending.amount)}",
            )
    except NotPending as exc:
        raise Conflict("already answered") from exc
    return _json(200, {"pending_id": pending.pending_id, "status": status})


ROUTES = {
    "POST /entries": (create_entry, SESSION),
    "GET /entries": (list_entries, SESSION),
    "GET /members": (list_members, SESSION),
    "GET /balances": (list_balances, SESSION),
    "POST /subscriptions": (create_subscription, SESSION),
    "POST /nudges": (create_nudge, SESSION),
    "GET /pending-payments": (list_pending_payments, SESSION),
    "POST /pending-payments": (create_pending_payment, SESSION),
    "PUT /pending-payments/{pending_id}": (resolve_pending_payment, SESSION),
    "PUT /members/{member_id}": (set_member_active, ADMIN),
    "POST /members": (create_member, ADMIN),
    "GET /deliveries": (list_deliveries, ADMIN),
    "POST /write-offs": (create_write_off, ADMIN),
}


def handle(event, context):
    route = event.get("routeKey")
    if route == "GET /me":
        return me(event, context)
    if route == "POST /receipts":
        try:
            return receive_receipt(event)
        except ValueError:
            return _json(400, {"error": "body is not JSON"})

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
    except Forbidden as exc:
        return _json(403, {"error": str(exc)})
    except NotFound as exc:
        return _json(404, {"error": str(exc)})
    except Conflict as exc:
        return _json(409, {"error": str(exc)})
    except Gone as exc:
        return _json(410, {"error": str(exc)})
    except TooSoon as exc:
        return _json(429, {"error": str(exc)})
    except (BadRequest, ValueError, KeyError) as exc:
        return _json(400, {"error": str(exc)})
