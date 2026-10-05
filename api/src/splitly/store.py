"""Append-only DynamoDB store — SPEC §T2, §C28.

Key schema (what T2.5 builds):

    pk = HOUSE#<house_id>      sk = ENTRY#<entry_id>
    pk = HOUSE#<house_id>      sk = MEMBER#<member_id>
    pk = HOUSE#<house_id>      sk = PENDING#<pending_id>    (§T16.6 — not ledger rows)

One partition per house, so listing a house's ledger is a single query and
entries and members are separated only by their sort-key prefix.

`created_at` is deliberately absent from the key. A scheduled job that fires
twice (§C8 — EventBridge is at-least-once) can derive its entry_id from its
idempotency key and let the conditional write below reject the second attempt,
satisfying §V2. Had the key carried a timestamp, the retry would land on a
different key and post the bill twice. Ordering is done in Python instead;
at four users that costs nothing (§C20).

There is no update and no delete, and that absence is what enforces §V8.

Queries are paged to exhaustion (§V15). A Query returns at most 1MB, and
stopping at the first page returned a silent prefix of the ledger — see B3.
"""

import hashlib
from datetime import datetime, timedelta
from decimal import Decimal

from boto3.dynamodb.conditions import Key
from botocore.exceptions import ClientError

from splitly.ledger import Entry, Member, Membership, Pending


class DuplicateEntry(Exception):
    """An entry_id already exists. The ledger is append-only (§V8)."""


class DeadSubscription(Exception):
    """The push service retired this endpoint; it stays retired (§V26)."""


class AlreadyExists(Exception):
    """The member id is taken, or the login already belongs to a house (§V20)."""


class NotPending(Exception):
    """Already verified or rejected — the other answer got there first (§V31)."""


def _as_int(value: int | Decimal) -> int:
    """DynamoDB hands numbers back as Decimal; cents are always int here."""
    return int(value)


class Store:
    def __init__(self, table):
        self._table = table

    # --- entries -----------------------------------------------------

    def put_entry(self, entry: Entry) -> None:
        try:
            self._table.put_item(
                Item=self._entry_item(entry),
                ConditionExpression="attribute_not_exists(pk) AND attribute_not_exists(sk)",
            )
        except ClientError as exc:
            if exc.response["Error"]["Code"] == "ConditionalCheckFailedException":
                raise DuplicateEntry(entry.entry_id) from exc
            raise

    @staticmethod
    def _entry_item(entry: Entry) -> dict:
        item = {
            "pk": f"HOUSE#{entry.house_id}",
            "sk": f"ENTRY#{entry.entry_id}",
            "entry_id": entry.entry_id,
            "house_id": entry.house_id,
            "created_at": entry.created_at.isoformat(),
            "description": entry.description,
            "kind": entry.kind,
            "total": entry.total,
            "payer": entry.payer,
            "shares": dict(entry.shares),
        }
        if entry.pending_id is not None:
            item["pending_id"] = entry.pending_id
        return item

    def list_entries(self, house_id: str) -> list[Entry]:
        items = self._query(house_id, "ENTRY#")
        return sorted(
            (self._to_entry(item) for item in items),
            key=lambda entry: (entry.created_at, entry.entry_id),
        )

    # --- members -----------------------------------------------------

    def put_member(self, house_id: str, member: Member) -> None:
        self._table.put_item(
            Item={
                "pk": f"HOUSE#{house_id}",
                "sk": f"MEMBER#{member.member_id}",
                "member_id": member.member_id,
                "name": member.name,
                "active": member.active,
            }
        )

    def list_members(self, house_id: str) -> list[Member]:
        return [self._to_member(item) for item in self._query(house_id, "MEMBER#")]

    # --- user → house (§C51) ------------------------------------------

    def put_user_house(
        self, user_id: str, house_id: str, member_id: str = "", admin: bool = False
    ) -> None:
        self._table.put_item(
            Item={
                "pk": f"USER#{user_id}",
                "sk": "HOUSE",
                "house_id": house_id,
                "member_id": member_id,
                "admin": admin,
            }
        )

    def add_member(self, house_id: str, member: Member, user_id: str) -> None:
        """§T11.5, §V20 — a new member and their login link, both or neither.

        Neither write may overwrite: a taken id would hand one person another's
        balance, and an existing link would move a real login between houses.
        """
        # The table's client serializes plain values itself.
        def put(item):
            return {
                "Put": {
                    "TableName": self._table.name,
                    "Item": item,
                    "ConditionExpression": "attribute_not_exists(pk)",
                }
            }

        try:
            self._table.meta.client.transact_write_items(
                TransactItems=[
                    put({
                        "pk": f"HOUSE#{house_id}",
                        "sk": f"MEMBER#{member.member_id}",
                        "member_id": member.member_id,
                        "name": member.name,
                        "active": member.active,
                    }),
                    put({
                        "pk": f"USER#{user_id}",
                        "sk": "HOUSE",
                        "house_id": house_id,
                        "member_id": member.member_id,
                        "admin": False,
                    }),
                ]
            )
        except ClientError as exc:
            reasons = [r.get("Code") for r in exc.response.get("CancellationReasons", [])]
            if "ConditionalCheckFailed" in reasons:
                raise AlreadyExists(member.member_id) from exc
            raise

    def membership(self, user_id: str) -> Membership | None:
        """§C51 — the only way a request learns its house, and its privilege.

        A direct key lookup, not an index: the Cognito `sub` is the key. One
        read serves both, so guarding an admin route costs nothing extra.
        """
        item = self._table.get_item(Key={"pk": f"USER#{user_id}", "sk": "HOUSE"}).get("Item")
        if item is None:
            return None
        return Membership(
            house_id=item["house_id"],
            member_id=item.get("member_id", ""),
            admin=bool(item.get("admin", False)),
        )

    # --- push subscriptions (§C15, §C31) ------------------------------

    def put_push_subscription(self, house_id: str, member_id: str, subscription: dict) -> None:
        """Keyed on the endpoint, so §C15's re-subscribe-every-launch is
        idempotent by construction rather than by a dedupe pass. One member
        may hold several: a phone and a laptop are two endpoints.

        §V26 — a retired endpoint is refused, not overwritten back to life.
        The browser keeps offering one the push service has already dropped.
        """
        try:
            self._table.put_item(
                Item={
                    "pk": f"HOUSE#{house_id}",
                    "sk": self._pushsub_key(member_id, subscription["endpoint"]),
                    "member_id": member_id,
                    "subscription": subscription,
                },
                ConditionExpression="attribute_not_exists(dead_at)",
            )
        except ClientError as exc:
            if exc.response["Error"]["Code"] == "ConditionalCheckFailedException":
                raise DeadSubscription(subscription["endpoint"]) from exc
            raise

    def retire_push_subscription(
        self, house_id: str, member_id: str, endpoint: str, now: datetime
    ) -> None:
        """§V7 — a 404/410 endpoint is never sent to again.

        §V27 — the key is built here from the PUSHSUB# prefix, and only an
        existing item is replaced, so this can neither create an item nor
        reach an entry. The stream role holds PutItem for this alone.
        """
        try:
            self._table.put_item(
                Item={
                    "pk": f"HOUSE#{house_id}",
                    "sk": self._pushsub_key(member_id, endpoint),
                    "member_id": member_id,
                    "dead_at": now.isoformat(),
                },
                ConditionExpression="attribute_exists(sk)",
            )
        except ClientError as exc:
            # Already gone, or never saved: nothing to retire.
            if exc.response["Error"]["Code"] != "ConditionalCheckFailedException":
                raise

    def list_push_subscriptions(self, house_id: str) -> list[dict]:
        return [
            {"member_id": item["member_id"], "subscription": item["subscription"]}
            for item in self._query(house_id, "PUSHSUB#")
            if "dead_at" not in item
        ]

    @staticmethod
    def _pushsub_key(member_id: str, endpoint: str) -> str:
        digest = hashlib.sha256(endpoint.encode()).hexdigest()[:16]
        return f"PUSHSUB#{member_id}#{digest}"

    # --- nudges (§T12) ----------------------------------------------

    def claim_nudge(self, house_id: str, member_id: str, by: str, now: datetime) -> bool:
        """§V25 — take this debtor's hour, or learn it is taken.

        One conditional write, so two nudges at the same instant cannot both
        win. The record stays for T19, where a nudge resets the reminder cap
        (§C11). Timestamps are UTC ISO strings, which order as text.
        """
        cutoff = (now - timedelta(hours=1)).isoformat()
        try:
            self._table.put_item(
                Item={
                    "pk": f"HOUSE#{house_id}",
                    "sk": f"NUDGE#{member_id}",
                    "member_id": member_id,
                    "by": by,
                    "sent_at": now.isoformat(),
                },
                ConditionExpression="attribute_not_exists(pk) OR sent_at <= :cutoff",
                ExpressionAttributeValues={":cutoff": cutoff},
            )
        except ClientError as exc:
            if exc.response["Error"]["Code"] == "ConditionalCheckFailedException":
                return False
            raise
        return True

    # --- pending payments (§T16.6) ------------------------------------

    def put_pending(self, pending: Pending) -> None:
        self._table.put_item(
            Item=self._pending_item(pending),
            ConditionExpression="attribute_not_exists(pk)",
        )

    def list_pending(self, house_id: str) -> list[Pending]:
        """Every status. `balances` counts only the pending ones (§V34)."""
        return [self._to_pending(item) for item in self._query(house_id, "PENDING#")]

    def resolve_pending(self, pending: Pending, status: str, payment: Entry | None = None) -> None:
        """§V31 — answer a pending payment once.

        The status is replaced, not updated, so the api role needs PutItem
        alone. The replace is conditional on it still being pending, and a
        verify's payment goes in the same transaction, keyed by the pending
        id: a double tap, a retry or a verify racing a reject all end with
        exactly one outcome.
        """
        closed = Pending(**{**pending.__dict__, "status": status})
        items = [
            {
                "Put": {
                    "TableName": self._table.name,
                    "Item": self._pending_item(closed),
                    "ConditionExpression": "#status = :pending",
                    "ExpressionAttributeNames": {"#status": "status"},
                    "ExpressionAttributeValues": {":pending": "pending"},
                }
            }
        ]
        if payment is not None:
            items.append(
                {
                    "Put": {
                        "TableName": self._table.name,
                        "Item": self._entry_item(payment),
                        "ConditionExpression": "attribute_not_exists(pk)",
                    }
                }
            )
        try:
            self._table.meta.client.transact_write_items(TransactItems=items)
        except ClientError as exc:
            reasons = [r.get("Code") for r in exc.response.get("CancellationReasons", [])]
            if "ConditionalCheckFailed" in reasons:
                raise NotPending(pending.pending_id) from exc
            raise

    # --- delivery receipts (§T14) -------------------------------------

    def record_push(
        self, house_id: str, push_id: str, member_id: str, kind: str, now: datetime
    ) -> None:
        """§V29 — written before the send, so a failed send still counts."""
        self._table.put_item(
            Item={
                "pk": f"HOUSE#{house_id}",
                "sk": f"PUSH#{push_id}",
                "push_id": push_id,
                "member_id": member_id,
                "kind": kind,
                "sent_at": now.isoformat(),
            },
            ConditionExpression="attribute_not_exists(sk)",  # §V27
        )

    def receive_push(self, house_id: str, push_id: str, now: datetime) -> bool:
        """§V28 — the receipt route is public, so this may only mark an
        existing, unreceived push. Anything else writes nothing."""
        key = {"pk": f"HOUSE#{house_id}", "sk": f"PUSH#{push_id}"}
        item = self._table.get_item(Key=key).get("Item")
        if item is None:
            return False
        try:
            self._table.put_item(
                Item={**item, "delivered_at": now.isoformat()},
                ConditionExpression="attribute_exists(sk) AND attribute_not_exists(delivered_at)",
            )
        except ClientError as exc:
            if exc.response["Error"]["Code"] == "ConditionalCheckFailedException":
                return False
            raise
        return True

    def list_pushes(self, house_id: str, since: datetime) -> list[dict]:
        cutoff = since.isoformat()
        return [
            {
                "push_id": item["push_id"],
                "member_id": item["member_id"],
                "kind": item["kind"],
                "sent_at": item["sent_at"],
                "delivered_at": item.get("delivered_at"),
            }
            # "PUSH#" does not match "PUSHSUB#": the character after PUSH differs.
            for item in self._query(house_id, "PUSH#")
            if item["sent_at"] >= cutoff
        ]

    # --- internals ---------------------------------------------------

    def _query(self, house_id: str, sk_prefix: str) -> list[dict]:
        # A Query returns at most 1MB. Stopping at the first page is B3.
        kwargs = {
            "KeyConditionExpression": Key("pk").eq(f"HOUSE#{house_id}")
            & Key("sk").begins_with(sk_prefix)
        }
        items: list[dict] = []
        while True:
            response = self._table.query(**kwargs)
            items.extend(response["Items"])
            if "LastEvaluatedKey" not in response:
                return items
            kwargs["ExclusiveStartKey"] = response["LastEvaluatedKey"]

    @staticmethod
    def _to_entry(item: dict) -> Entry:
        return Entry(
            entry_id=item["entry_id"],
            house_id=item["house_id"],
            created_at=datetime.fromisoformat(item["created_at"]),
            description=item["description"],
            kind=item["kind"],
            total=_as_int(item["total"]),
            payer=item["payer"],
            shares={member: _as_int(share) for member, share in item["shares"].items()},
            pending_id=item.get("pending_id"),
        )

    @staticmethod
    def _pending_item(pending: Pending) -> dict:
        return {
            "pk": f"HOUSE#{pending.house_id}",
            "sk": f"PENDING#{pending.pending_id}",
            "pending_id": pending.pending_id,
            "house_id": pending.house_id,
            "created_at": pending.created_at.isoformat(),
            "from_member": pending.from_member,
            "to_member": pending.to_member,
            "amount": pending.amount,
            "status": pending.status,
        }

    @staticmethod
    def _to_pending(item: dict) -> Pending:
        return Pending(
            pending_id=item["pending_id"],
            house_id=item["house_id"],
            created_at=datetime.fromisoformat(item["created_at"]),
            from_member=item["from_member"],
            to_member=item["to_member"],
            amount=_as_int(item["amount"]),
            status=item["status"],
        )

    @staticmethod
    def _to_member(item: dict) -> Member:
        return Member(
            member_id=item["member_id"],
            name=item["name"],
            active=bool(item["active"]),
        )
