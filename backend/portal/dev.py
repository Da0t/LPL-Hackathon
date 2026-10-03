"""Local click-through sign-in for development: no Cognito, no DynamoDB, no passwords.

Enabled only by ``COHERENT_DEV_LOGIN=1`` when ``COHERENT_PORTAL_CONFIG`` is unset.
Records are the synthetic seed profiles held in memory; they reset on restart.
Never enable this on a server anyone else can reach.
"""

import copy
import json
import threading

from botocore.exceptions import ClientError
from backend.errors import ApiError
from backend.portal.seed import make_profiles
from backend.portal.service import COOKIE, Portal

TOKEN_PREFIX = "dev-"


class MemoryTable:
    """The slice of the DynamoDB table API that Portal uses."""

    def __init__(self):
        self.rows = {}
        self.lock = threading.Lock()

    def get_item(self, Key, **kwargs):
        row = self.rows.get((Key["pk"], Key["sk"]))
        return {"Item": copy.deepcopy(row)} if row else {}

    def put_item(self, Item, ConditionExpression=None, ExpressionAttributeValues=None):
        key = (Item["pk"], Item["sk"])
        with self.lock:
            old = self.rows.get(key)
            conflict = (ConditionExpression == "attribute_not_exists(pk)" and old) or (
                ConditionExpression == "revision = :r"
                and (old or {}).get("revision") != ExpressionAttributeValues[":r"]
            )
            if conflict:
                raise ClientError(
                    {"Error": {"Code": "ConditionalCheckFailedException"}}, "PutItem"
                )
            self.rows[key] = copy.deepcopy(Item)


class DevPortal(Portal):
    def __init__(self, store):
        self.config = {}
        self.cognito = None
        self.table = MemoryTable()
        self.store = store
        self.failures = {}
        self.lock = threading.Lock()
        self.users = {
            "staff": {
                "sub": "dev-staff",
                "client_id": None,
                "role": "staff",
                "email": "advisor@example.com",
                "display_name": "Coherent Staff",
            }
        }
        for doc in make_profiles():
            self.users[doc["client_id"]] = {
                "sub": "dev-" + doc["client_id"],
                "client_id": doc["client_id"],
                "role": "client",
                "email": doc["email"],
                "display_name": doc["display_name"],
            }
            self.table.put_item(
                Item={
                    "pk": "CLIENT#" + doc["client_id"],
                    "sk": "PROFILE",
                    "revision": 1,
                    "document": json.dumps(doc),
                }
            )
            self.sync_reference(doc)

    def dev_users(self):
        return [
            {k: u[k] for k in ("email", "display_name", "role")}
            for u in self.users.values()
        ]

    def actor(self, request):
        token = request.cookies.get(COOKIE)
        if not token:
            raise ApiError(401, "SIGN_IN_REQUIRED", "Please sign in to continue.")
        actor = self.users.get(token.removeprefix(TOKEN_PREFIX))
        if not token.startswith(TOKEN_PREFIX) or not actor:
            raise ApiError(
                401,
                "SESSION_EXPIRED",
                "Your session has expired. Please sign in again.",
            )
        return actor

    def login(self, email, password, ip):
        # Any password works: this mode exists so nobody has to remember one.
        for key, user in self.users.items():
            if user["email"] == email.lower():
                return {"AccessToken": TOKEN_PREFIX + key, "ExpiresIn": 30 * 86400}
        raise ApiError(401, "INVALID_LOGIN", "Email or password was not recognized.")

    def requests(self, client_id):
        rows = [
            json.loads(row["document"])
            for (pk, sk), row in list(self.table.rows.items())
            if pk == "CLIENT#" + client_id and sk.startswith("REQUEST#")
        ]
        return sorted(rows, key=lambda r: r["created_at"], reverse=True)
