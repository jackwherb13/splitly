"""Lambda handler behind the API Gateway HTTP API — SPEC §T6.5, §I `api`.

The JWT authorizer verifies the Cognito token before Lambda is ever invoked,
so a request that reaches here has already been authenticated. That is only
true while the route carries the authorizer, and §V10's text is `⊥ forgotten`
— so the absence of claims is treated as an error rather than as an anonymous
caller. Fail closed.

Business routes are T7's. This one exists to prove the plumbing.
"""

import json


class Unauthenticated(Exception):
    """No verified JWT claims on the request. The route lost its authorizer."""


def _claims(event):
    try:
        return event["requestContext"]["authorizer"]["jwt"]["claims"]
    except (KeyError, TypeError):
        raise Unauthenticated("no verified JWT claims on the request") from None


def _json(status, body):
    return {
        "statusCode": status,
        "headers": {"content-type": "application/json"},
        "body": json.dumps(body),
    }


def me(event, _context):
    try:
        claims = _claims(event)
    except Unauthenticated:
        return _json(401, {"error": "unauthenticated"})
    return _json(200, {"sub": claims["sub"], "email": claims.get("email")})
