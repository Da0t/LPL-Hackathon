"""Provision a small Bedrock KB over reviewed public guidance, never client data.

Uses encrypted S3 documents + S3 Vectors + Titan v2. Keeps resumable resource IDs
in ignored var/knowledge-base.json. Re-run to sync the reviewed corpus.
"""

import json
import os
import time
from pathlib import Path
import boto3
from botocore.exceptions import ClientError

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "var/knowledge-base.json"
REGION = os.getenv("AWS_REGION", "us-east-1")


def main():
    session = boto3.Session(region_name=REGION)
    account = session.client("sts").get_caller_identity()["Account"]
    cfg = json.loads(OUT.read_text()) if OUT.exists() else {"region": REGION}

    def save():
        OUT.parent.mkdir(exist_ok=True)
        OUT.write_text(json.dumps(cfg, indent=2) + "\n")

    s3 = session.client("s3")
    vectors = session.client("s3vectors")
    iam = session.client("iam")
    kb = session.client("bedrock-agent")
    bucket = cfg.setdefault("bucket", f"coherent-compliance-{account}-{REGION}")
    vector_bucket = cfg.setdefault(
        "vector_bucket", f"coherent-compliance-vectors-{account}"
    )
    index = "compliance-v1"
    role_name = "CoherentComplianceKnowledgeBase"
    save()
    try:
        s3.head_bucket(Bucket=bucket)
    except ClientError as e:
        if e.response["Error"]["Code"] not in ("404", "NoSuchBucket", "NotFound"):
            raise
        s3.create_bucket(
            Bucket=bucket,
            **(
                {}
                if REGION == "us-east-1"
                else {"CreateBucketConfiguration": {"LocationConstraint": REGION}}
            ),
        )
    s3.put_public_access_block(
        Bucket=bucket,
        PublicAccessBlockConfiguration={
            k: True
            for k in [
                "BlockPublicAcls",
                "IgnorePublicAcls",
                "BlockPublicPolicy",
                "RestrictPublicBuckets",
            ]
        },
    )
    s3.put_bucket_encryption(
        Bucket=bucket,
        ServerSideEncryptionConfiguration={
            "Rules": [
                {"ApplyServerSideEncryptionByDefault": {"SSEAlgorithm": "AES256"}}
            ]
        },
    )
    for doc in json.loads((ROOT / "data/compliance/sources.json").read_text()):
        key = "reviewed/" + doc["id"] + ".txt"
        text = (
            doc["title"]
            + "\nAuthority: "
            + doc["authority"]
            + "\nSource: "
            + doc["url"]
            + "\nReviewed: "
            + doc["reviewed_at"]
            + "\n\n"
            + doc["excerpt"]
        )
        s3.put_object(
            Bucket=bucket, Key=key, Body=text.encode(), ContentType="text/plain"
        )
        s3.put_object(
            Bucket=bucket,
            Key=key + ".metadata.json",
            Body=json.dumps(
                {
                    "metadataAttributes": {
                        "source_id": doc["id"],
                        "source_url": doc["url"],
                        "reviewed_at": doc["reviewed_at"],
                    }
                }
            ).encode(),
            ContentType="application/json",
        )
    try:
        vectors.get_vector_bucket(vectorBucketName=vector_bucket)
    except vectors.exceptions.NotFoundException:
        vectors.create_vector_bucket(vectorBucketName=vector_bucket)
    try:
        idx = vectors.get_index(vectorBucketName=vector_bucket, indexName=index)[
            "index"
        ]
    except vectors.exceptions.NotFoundException:
        vectors.create_index(
            vectorBucketName=vector_bucket,
            indexName=index,
            dataType="float32",
            dimension=1024,
            distanceMetric="cosine",
            metadataConfiguration={
                "nonFilterableMetadataKeys": [
                    "AMAZON_BEDROCK_TEXT",
                    "AMAZON_BEDROCK_METADATA",
                ]
            },
        )
        idx = vectors.get_index(vectorBucketName=vector_bucket, indexName=index)[
            "index"
        ]
    cfg["index_arn"] = idx["indexArn"]
    save()
    trust = {
        "Version": "2012-10-17",
        "Statement": [
            {
                "Effect": "Allow",
                "Principal": {"Service": "bedrock.amazonaws.com"},
                "Action": "sts:AssumeRole",
                "Condition": {
                    "StringEquals": {"aws:SourceAccount": account},
                    "ArnLike": {
                        "aws:SourceArn": f"arn:aws:bedrock:{REGION}:{account}:knowledge-base/*"
                    },
                },
            }
        ],
    }
    try:
        role = iam.get_role(RoleName=role_name)["Role"]
    except iam.exceptions.NoSuchEntityException:
        role = iam.create_role(
            RoleName=role_name,
            AssumeRolePolicyDocument=json.dumps(trust),
            Description="Coherent reviewed public-guidance knowledge base",
        )["Role"]
    model = f"arn:aws:bedrock:{REGION}::foundation-model/amazon.titan-embed-text-v2:0"
    policy = {
        "Version": "2012-10-17",
        "Statement": [
            {"Effect": "Allow", "Action": ["bedrock:InvokeModel"], "Resource": model},
            {
                "Effect": "Allow",
                "Action": ["s3:ListBucket"],
                "Resource": f"arn:aws:s3:::{bucket}",
            },
            {
                "Effect": "Allow",
                "Action": ["s3:GetObject"],
                "Resource": f"arn:aws:s3:::{bucket}/reviewed/*",
            },
            {
                "Effect": "Allow",
                "Action": [
                    "s3vectors:PutVectors",
                    "s3vectors:GetVectors",
                    "s3vectors:DeleteVectors",
                    "s3vectors:QueryVectors",
                    "s3vectors:GetIndex",
                ],
                "Resource": cfg["index_arn"],
            },
        ],
    }
    iam.put_role_policy(
        RoleName=role_name,
        PolicyName="ReviewedCorpusAccess",
        PolicyDocument=json.dumps(policy),
    )
    cfg["role_arn"] = role["Arn"]
    save()
    if not cfg.get("knowledge_base_id"):
        for attempt in range(6):
            try:
                r = kb.create_knowledge_base(
                    name="coherent-cited-compliance-v1",
                    roleArn=role["Arn"],
                    knowledgeBaseConfiguration={
                        "type": "VECTOR",
                        "vectorKnowledgeBaseConfiguration": {
                            "embeddingModelArn": model
                        },
                    },
                    storageConfiguration={
                        "type": "S3_VECTORS",
                        "s3VectorsConfiguration": {"indexArn": cfg["index_arn"]},
                    },
                    tags={"Project": "Coherent-Hackathon"},
                )
                cfg["knowledge_base_id"] = r["knowledgeBase"]["knowledgeBaseId"]
                save()
                break
            except ClientError as e:
                if e.response["Error"]["Code"] != "ValidationException" or attempt == 5:
                    raise
                print("Waiting for IAM propagation", flush=True)
                time.sleep(8)
    if not cfg.get("data_source_id"):
        r = kb.create_data_source(
            knowledgeBaseId=cfg["knowledge_base_id"],
            name="reviewed-public-guidance",
            dataSourceConfiguration={
                "type": "S3",
                "s3Configuration": {
                    "bucketArn": f"arn:aws:s3:::{bucket}",
                    "inclusionPrefixes": ["reviewed/"],
                },
            },
            vectorIngestionConfiguration={
                "chunkingConfiguration": {"chunkingStrategy": "NONE"}
            },
            dataDeletionPolicy="RETAIN",
        )
        cfg["data_source_id"] = r["dataSource"]["dataSourceId"]
        save()
    for _ in range(20):
        status = kb.get_knowledge_base(knowledgeBaseId=cfg["knowledge_base_id"])[
            "knowledgeBase"
        ]["status"]
        if status == "ACTIVE":
            break
        if status == "FAILED":
            raise RuntimeError("Knowledge base creation failed")
        time.sleep(3)
    job = kb.start_ingestion_job(
        knowledgeBaseId=cfg["knowledge_base_id"], dataSourceId=cfg["data_source_id"]
    )["ingestionJob"]
    cfg["ingestion_job_id"] = job["ingestionJobId"]
    save()
    print(
        "Ingestion started; configuration saved to var/knowledge-base.json", flush=True
    )
    for _ in range(36):
        job = kb.get_ingestion_job(
            knowledgeBaseId=cfg["knowledge_base_id"],
            dataSourceId=cfg["data_source_id"],
            ingestionJobId=cfg["ingestion_job_id"],
        )["ingestionJob"]
        if job["status"] in ("COMPLETE", "FAILED", "STOPPED"):
            print(
                job["status"], job.get("statistics", {}), job.get("failureReasons", [])
            )
            return
        time.sleep(5)
    print("Ingestion still running. Check the saved job ID before using retrieval.")


if __name__ == "__main__":
    main()
