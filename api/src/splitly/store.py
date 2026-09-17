"""Append-only DynamoDB store — SPEC §T2, §C28.

Key schema (what T2.5 builds):

    pk = HOUSE#<house_id>      sk = ENTRY#<entry_id>
    pk = HOUSE#<house_id>      sk = MEMBER#<member_id>

One partition per house, so listing a house's ledger is a single query and
entries and members are separated only by their sort-key prefix.

`created_at` is deliberately absent from the key. A scheduled job that fires
twice (§C8 — EventBridge is at-least-once) can derive its entry_id from its
idempotency key and let the conditional write below reject the second attempt,
satisfying §V2. Had the key carried a timestamp, the retry would land on a
different key and post the bill twice. Ordering is done in Python instead;
at four users that costs nothing (§C20).

There is no update and no delete, and that absence is what enforces §V8.
"""

from collections.abc import Iterable
from datetime import datetime
from decimal import Decimal

from boto3.dynamodb.conditions import Key
from botocore.exceptions import ClientError

from splitly.ledger import Entry, Member


class DuplicateEntry(Exception):
    """An entry_id already exists. The ledger is append-only (§V8)."""


def _as_int(value: int | Decimal) -> int:
    """DynamoDB hands numbers back as Decimal; cents are always int here."""
    return int(value)


class Store:
    def __init__(self, table):
        self._table = table

    # --- entries -----------------------------------------------------

    def put_entry(self, entry: Entry) -> None:
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
        try:
            self._table.put_item(
                Item=item,
                ConditionExpression="attribute_not_exists(pk) AND attribute_not_exists(sk)",
            )
        except ClientError as exc:
            if exc.response["Error"]["Code"] == "ConditionalCheckFailedException":
                raise DuplicateEntry(entry.entry_id) from exc
            raise

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

    # --- internals ---------------------------------------------------

    def _query(self, house_id: str, sk_prefix: str) -> Iterable[dict]:
        response = self._table.query(
            KeyConditionExpression=Key("pk").eq(f"HOUSE#{house_id}")
            & Key("sk").begins_with(sk_prefix)
        )
        return response["Items"]

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
        )

    @staticmethod
    def _to_member(item: dict) -> Member:
        return Member(
            member_id=item["member_id"],
            name=item["name"],
            active=bool(item["active"]),
        )
