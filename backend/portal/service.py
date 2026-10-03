"""Cognito-validated identity and private, client-partitioned DynamoDB storage."""

import base64
import json
import threading
import time
from datetime import datetime, timezone
from pathlib import Path

import boto3
from botocore.config import Config
from botocore.exceptions import ClientError
from backend.errors import ApiError
from backend.store import normalize_account, normalize_client, normalize_event

COOKIE = "coherent_session"


class Portal:
    def __init__(self, config_path, store):
        self.config = json.loads(Path(config_path).read_text())
        aws = boto3.Session(region_name=self.config["region"])
        self.table = aws.resource(
            "dynamodb",
            config=Config(
                connect_timeout=5, read_timeout=10, retries={"max_attempts": 2}
            ),
        ).Table(self.config["table_name"])
        self.cognito = aws.client(
            "cognito-idp",
            config=Config(
                connect_timeout=5, read_timeout=10, retries={"max_attempts": 2}
            ),
        )
        self.store = store
        self.failures = {}
        self.lock = threading.Lock()
        for client in store.list_clients():
            profile = self.get(client["client_id"])
            if profile:
                self.sync_reference(profile)

    def actor(self, request):
        if getattr(request.state, "portal_actor", None):
            return request.state.portal_actor
        token = request.cookies.get(COOKIE)
        if not token:
            raise ApiError(401, "SIGN_IN_REQUIRED", "Please sign in to continue.")
        try:
            # Cognito validates signature, expiry, and revocation. We additionally scope
            # the token to our app/pool and resolve authorization from our own identity map.
            user = self.cognito.get_user(AccessToken=token)
            claims = json.loads(base64.urlsafe_b64decode(token.split(".")[1] + "==="))
            issuer = f"https://cognito-idp.{self.config['region']}.amazonaws.com/{self.config['user_pool_id']}"
            if (
                claims.get("iss") != issuer
                or claims.get("client_id") != self.config["app_client_id"]
                or claims.get("token_use") != "access"
            ):
                raise ValueError("Wrong application")
            sub = next(a["Value"] for a in user["UserAttributes"] if a["Name"] == "sub")
            item = self.table.get_item(
                Key={"pk": "IDENTITY#" + sub, "sk": "IDENTITY"}, ConsistentRead=True
            ).get("Item")
            if not item:
                raise ValueError("Unknown identity")
            actor = json.loads(item["document"])
        except (ClientError, ValueError, KeyError, IndexError, StopIteration):
            raise ApiError(
                401,
                "SESSION_EXPIRED",
                "Your session has expired. Please sign in again.",
            ) from None
        request.state.portal_actor = actor
        return actor

    def login(self, email, password, ip):
        key = (ip, email.lower())
        now = time.time()
        with self.lock:
            self.failures = {k: v for k, v in self.failures.items() if now - v[1] < 900}
            count, at = self.failures.get(key, (0, now))
            if count >= 8:
                raise ApiError(
                    429,
                    "LOGIN_THROTTLED",
                    "Too many attempts. Try again in 15 minutes.",
                )
        try:
            result = self.cognito.initiate_auth(
                ClientId=self.config["app_client_id"],
                AuthFlow="USER_PASSWORD_AUTH",
                AuthParameters={"USERNAME": email.lower(), "PASSWORD": password},
            )
            auth = result.get("AuthenticationResult")
            if not auth:
                raise ApiError(
                    401,
                    "LOGIN_CHALLENGE",
                    "This account needs administrator-assisted activation.",
                )
            with self.lock:
                self.failures.pop(key, None)
            return auth
        except ClientError:
            with self.lock:
                self.failures[key] = (count + 1, at)
            raise ApiError(
                401, "INVALID_LOGIN", "Email or password was not recognized."
            ) from None

    def get(self, client_id):
        row = self.table.get_item(
            Key={"pk": "CLIENT#" + client_id, "sk": "PROFILE"}, ConsistentRead=True
        ).get("Item")
        return json.loads(row["document"]) if row else None

    def save(self, doc, revision):
        doc["revision"] = revision + 1
        doc["updated_at"] = datetime.now(timezone.utc).isoformat()
        try:
            self.table.put_item(
                Item={
                    "pk": "CLIENT#" + doc["client_id"],
                    "sk": "PROFILE",
                    "revision": revision + 1,
                    "document": json.dumps(doc),
                },
                ConditionExpression="revision = :r",
                ExpressionAttributeValues={":r": revision},
            )
        except ClientError as e:
            if e.response["Error"]["Code"] == "ConditionalCheckFailedException":
                raise ApiError(
                    409,
                    "EDIT_CONFLICT",
                    "Your records changed in another window. Refresh before saving again.",
                ) from None
            raise
        self.sync_reference(doc)
        return doc

    def sync_reference(self, doc):
        """Keep existing intake tools grounded in the same cloud-backed records."""
        client = {
            **self.store.get_client(doc["client_id"]),
            "display_name": doc["profile"]["legal_name"],
            "state": doc["profile"]["state"],
            "preferred_contact_channel": doc["profile"]["preferred_contact"],
        }
        with self.store._lock, self.store._conn:
            self.store._conn.execute(
                "INSERT OR REPLACE INTO clients(client_id,doc) VALUES (?,?)",
                (doc["client_id"], json.dumps(normalize_client(client))),
            )
            for a in doc["accounts"]:
                normalized = normalize_account(a)
                self.store._conn.execute(
                    "INSERT OR REPLACE INTO accounts(account_id,client_id,doc) VALUES (?,?,?)",
                    (a["account_id"], doc["client_id"], json.dumps(normalized)),
                )
            # Replace this client's reference history so legacy seed events cannot
            # appear alongside the cloud record as contradictory facts.
            self.store._conn.execute(
                "DELETE FROM events WHERE account_id IN (SELECT account_id FROM accounts WHERE client_id=?)",
                (doc["client_id"],),
            )
            for e in doc["activity"]:
                normalized = normalize_event(e)
                self.store._conn.execute(
                    "INSERT OR REPLACE INTO events(event_id,account_id,doc) VALUES (?,?,?)",
                    (e["event_id"], e["account_id"], json.dumps(normalized)),
                )

    def document(self, client_id, words, summary, account_id, amount, case_id=None):
        profile = self.get(client_id)
        account = next(
            (a for a in profile["accounts"] if a["account_id"] == account_id), None
        )
        if account_id and not account:
            raise ApiError(403, "ACCOUNT_NOT_OWNED", "Choose one of your own accounts.")
        return {
            "client_id": client_id,
            "client_name": profile["profile"]["legal_name"],
            "case_id": case_id,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "original_words": words,
            "request_description": summary,
            "amount_requested": amount,
            "account": account,
            "history": [
                e for e in profile["activity"] if e["account_id"] == account_id
            ],
            "status": "Submitted for review" if case_id else "Draft · not sent",
            "synthetic_only": True,
        }

    def archive(self, client_id, case):
        sk = "REQUEST#" + case["case_id"]
        existing = self.table.get_item(
            Key={"pk": "CLIENT#" + client_id, "sk": sk}, ConsistentRead=True
        ).get("Item")
        if existing:
            return json.loads(existing["document"])
        doc = case.get("_portal_document") or self.document(
            client_id,
            case["original_words"],
            case["confirmed_plain_language_request"],
            case.get("selected_account_id"),
            case.get("amount_requested"),
            case["case_id"],
        )
        try:
            self.table.put_item(
                Item={
                    "pk": "CLIENT#" + client_id,
                    "sk": sk,
                    "document": json.dumps(doc),
                },
                ConditionExpression="attribute_not_exists(pk)",
            )
        except ClientError as e:
            if e.response["Error"]["Code"] != "ConditionalCheckFailedException":
                raise
            return json.loads(
                self.table.get_item(
                    Key={"pk": "CLIENT#" + client_id, "sk": sk}, ConsistentRead=True
                )["Item"]["document"]
            )
        return doc

    def requests(self, client_id):
        from boto3.dynamodb.conditions import Key

        query = {
            "KeyConditionExpression": Key("pk").eq("CLIENT#" + client_id)
            & Key("sk").begins_with("REQUEST#"),
            "ConsistentRead": True,
        }
        rows = []
        while True:
            page = self.table.query(**query)
            rows.extend(page["Items"])
            if not page.get("LastEvaluatedKey"):
                break
            query["ExclusiveStartKey"] = page["LastEvaluatedKey"]
        return sorted(
            [json.loads(r["document"]) for r in rows],
            key=lambda r: r["created_at"],
            reverse=True,
        )
