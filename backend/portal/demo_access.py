"""Explicit, signed access to the four fictional public-demo personas.

Only enable on an instance that contains synthetic records. A character id is
looked up in a fixed server-side allowlist; browser-supplied role/client fields
are never trusted. This is separate from the Cognito password sign-in path.
"""

import base64
import binascii
import hashlib
import hmac
import json
import secrets
import time

from backend.errors import ApiError
from backend.portal.seed import make_profiles

PREFIX = "demo-v1"
LIFETIME_SECONDS = 3600


def _b64(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode().rstrip("=")


def _unb64(value: str) -> bytes:
    return base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))


class DemoAccess:
    def __init__(self, secret: str):
        if len(secret) < 32:
            raise ValueError("COHERENT_DEMO_SECRET must be at least 32 characters")
        self.secret = secret.encode()
        clients = [
            {
                "id": profile["client_id"],
                "sub": "demo-" + profile["client_id"],
                "client_id": profile["client_id"],
                "role": "client",
                "email": profile["email"],
                "display_name": profile["display_name"],
            }
            for profile in make_profiles()
        ]
        staff = {
            "id": "staff",
            "sub": "demo-staff",
            "client_id": None,
            "role": "staff",
            "email": "advisor@example.com",
            "display_name": "Coherent Staff",
        }
        self._people = {person["id"]: person for person in [*clients, staff]}

    def characters(self) -> list[dict]:
        return [
            {key: person[key] for key in ("id", "display_name", "role")}
            for person in self._people.values()
        ]

    def issue(self, character_id: str) -> str:
        if character_id not in self._people:
            raise ApiError(404, "DEMO_CHARACTER_NOT_FOUND", "Choose one of the demo characters.")
        payload = _b64(
            json.dumps(
                {"id": character_id, "exp": int(time.time()) + LIFETIME_SECONDS,
                 "nonce": secrets.token_hex(8)},
                separators=(",", ":"),
            ).encode()
        )
        signed = f"{PREFIX}.{payload}"
        digest = hmac.new(self.secret, signed.encode(), hashlib.sha256).digest()
        return f"{signed}.{_b64(digest)}"

    def actor(self, token: str) -> dict:
        try:
            prefix, payload, mac = token.split(".", 2)
            if prefix != PREFIX:
                raise ValueError("Wrong token version")
            signed = f"{prefix}.{payload}"
            expected = hmac.new(self.secret, signed.encode(), hashlib.sha256).digest()
            if not hmac.compare_digest(expected, _unb64(mac)):
                raise ValueError("Invalid signature")
            data = json.loads(_unb64(payload))
            if not isinstance(data, dict) or data.get("exp", 0) <= time.time():
                raise ValueError("Expired")
            person = self._people.get(data.get("id"))
            if not person:
                raise ValueError("Unknown character")
            return {key: person[key] for key in ("sub", "client_id", "role", "email", "display_name")}
        except (ValueError, KeyError, TypeError, binascii.Error):
            raise ApiError(401, "SESSION_EXPIRED", "Your demo session has expired. Choose a character again.") from None
