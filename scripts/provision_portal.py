"""Create private DynamoDB records and Cognito demo identities; no messages sent."""

import json
import os
import secrets
from pathlib import Path
import boto3
from botocore.exceptions import ClientError
from backend.portal.seed import make_profiles

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "var"
OUT.mkdir(exist_ok=True)
CONFIG = OUT / "portal-aws.json"
region = os.getenv("AWS_DEFAULT_REGION", "us-east-1")
session = boto3.Session(region_name=region)
ddb = session.resource("dynamodb")
cognito = session.client("cognito-idp")
config = (
    json.loads(CONFIG.read_text())
    if CONFIG.exists()
    else {
        "region": region,
        "table_name": "coherent-client-portal-v1",
        "pool_name": "coherent-client-portal-v1",
    }
)


def save():
    CONFIG.write_text(json.dumps(config, indent=2) + "\n")


try:
    ddb.Table(config["table_name"]).load()
except ClientError as e:
    if e.response["Error"]["Code"] != "ResourceNotFoundException":
        raise
    ddb.create_table(
        TableName=config["table_name"],
        KeySchema=[
            {"AttributeName": "pk", "KeyType": "HASH"},
            {"AttributeName": "sk", "KeyType": "RANGE"},
        ],
        AttributeDefinitions=[
            {"AttributeName": "pk", "AttributeType": "S"},
            {"AttributeName": "sk", "AttributeType": "S"},
        ],
        BillingMode="PAY_PER_REQUEST",
        SSESpecification={"Enabled": True},
        Tags=[
            {"Key": "Project", "Value": "Coherent-Hackathon"},
            {"Key": "Data", "Value": "SyntheticOnly"},
        ],
    )
    print("Created DynamoDB table", flush=True)
table = ddb.Table(config["table_name"])
table.wait_until_exists()
if not config.get("user_pool_id"):
    existing = [
        p
        for p in cognito.list_user_pools(MaxResults=60)["UserPools"]
        if p["Name"] == config["pool_name"]
    ]
    if existing:
        config["user_pool_id"] = existing[0]["Id"]
    else:
        config["user_pool_id"] = cognito.create_user_pool(
            PoolName=config["pool_name"],
            Policies={
                "PasswordPolicy": {
                    "MinimumLength": 12,
                    "RequireUppercase": True,
                    "RequireLowercase": True,
                    "RequireNumbers": True,
                    "RequireSymbols": True,
                }
            },
            AdminCreateUserConfig={"AllowAdminCreateUserOnly": True},
            UsernameAttributes=["email"],
            UsernameConfiguration={"CaseSensitive": False},
            MfaConfiguration="OFF",
            UserPoolTags={"Project": "Coherent-Hackathon", "Data": "SyntheticOnly"},
        )["UserPool"]["Id"]
    save()
    print("Cognito user pool ready", flush=True)
if not config.get("app_client_id"):
    config["app_client_id"] = cognito.create_user_pool_client(
        UserPoolId=config["user_pool_id"],
        ClientName="coherent-local-portal",
        GenerateSecret=False,
        ExplicitAuthFlows=["ALLOW_USER_PASSWORD_AUTH", "ALLOW_REFRESH_TOKEN_AUTH"],
        PreventUserExistenceErrors="ENABLED",
        AccessTokenValidity=60,
        IdTokenValidity=60,
        RefreshTokenValidity=1,
        TokenValidityUnits={
            "AccessToken": "minutes",
            "IdToken": "minutes",
            "RefreshToken": "days",
        },
        EnableTokenRevocation=True,
        ReadAttributes=["email", "name"],
        WriteAttributes=["name"],
    )["UserPoolClient"]["ClientId"]
    save()
access = OUT / "demo-access.json"
passwords = json.loads(access.read_text()) if access.exists() else {}
for p in make_profiles() + [
    {
        "client_id": None,
        "display_name": "Coherent Staff",
        "email": "advisor@example.com",
    }
]:
    email = p["email"]
    role = "client" if p["client_id"] else "staff"
    try:
        user = cognito.admin_get_user(UserPoolId=config["user_pool_id"], Username=email)
    except cognito.exceptions.UserNotFoundException:
        cognito.admin_create_user(
            UserPoolId=config["user_pool_id"],
            Username=email,
            UserAttributes=[
                {"Name": "email", "Value": email},
                {"Name": "email_verified", "Value": "true"},
                {"Name": "name", "Value": p["display_name"]},
            ],
            MessageAction="SUPPRESS",
        )
        user = cognito.admin_get_user(UserPoolId=config["user_pool_id"], Username=email)
    if email not in passwords:
        password = "Coherent!" + secrets.token_urlsafe(16) + "7aA"
        cognito.admin_set_user_password(
            UserPoolId=config["user_pool_id"],
            Username=email,
            Password=password,
            Permanent=True,
        )
        passwords[email] = {
            "password": password,
            "client_id": p["client_id"],
            "role": role,
        }
        fd = os.open(access, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        with os.fdopen(fd, "w") as f:
            json.dump(passwords, f, indent=2)
    sub = next(a["Value"] for a in user["UserAttributes"] if a["Name"] == "sub")
    table.put_item(
        Item={
            "pk": "IDENTITY#" + sub,
            "sk": "IDENTITY",
            "document": json.dumps(
                {
                    "sub": sub,
                    "client_id": p["client_id"],
                    "role": role,
                    "email": email,
                    "display_name": p["display_name"],
                }
            ),
        }
    )
    if p["client_id"]:
        try:
            table.put_item(
                Item={
                    "pk": "CLIENT#" + p["client_id"],
                    "sk": "PROFILE",
                    "revision": 1,
                    "document": json.dumps(p),
                },
                ConditionExpression="attribute_not_exists(pk)",
            )
        except ClientError as e:
            if e.response["Error"]["Code"] != "ConditionalCheckFailedException":
                raise
    print("Ready:", email, role, flush=True)
print("Configuration: var/portal-aws.json; private demo sign-ins: var/demo-access.json")
