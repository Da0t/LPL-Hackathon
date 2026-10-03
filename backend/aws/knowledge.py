"""Retrieve only registered public-guidance sources from an actual Bedrock KB."""

import json
import os
from pathlib import Path
import boto3
from botocore.config import Config
from backend.aws.telemetry import emit

ROOT = Path(__file__).resolve().parents[2]
SOURCES = {
    d["id"]: d for d in json.loads((ROOT / "data/compliance/sources.json").read_text())
}


def retrieve(case, client=None, knowledge_base_id=None):
    config_path = Path(
        os.getenv("COHERENT_KB_CONFIG", str(ROOT / "var/knowledge-base.json"))
    )
    try:
        config = json.loads(config_path.read_text()) if config_path.exists() else {}
    except (OSError, ValueError):
        return {
            "status": "unavailable",
            "citations": [],
            "message": "Knowledge base configuration is unreadable; human review is required.",
        }
    kb_id = (
        knowledge_base_id
        or os.getenv("BEDROCK_KNOWLEDGE_BASE_ID")
        or config.get("knowledge_base_id")
    )
    if not kb_id:
        return {
            "status": "unavailable",
            "citations": [],
            "message": "Knowledge base is not configured; regulatory checks require human review.",
        }
    query = "Regulation Best Interest care suitability investment profile costs risks and rewards. "
    if any(
        c in case.get("categories", [])
        for c in (
            "withdrawal_or_distribution",
            "rollover_or_transfer",
            "retirement_income",
        )
    ):
        query += "IRA retirement plan distribution early withdrawal additional tax exceptions."
    emit("tool", tool="bedrock-agent-runtime.Retrieve")
    try:
        client = client or boto3.client(
            "bedrock-agent-runtime",
            region_name=config.get("region", "us-east-1"),
            config=Config(
                connect_timeout=4, read_timeout=15, retries={"max_attempts": 1}
            ),
        )
        result = client.retrieve(
            knowledgeBaseId=kb_id,
            retrievalQuery={"text": query},
            retrievalConfiguration={
                "vectorSearchConfiguration": {"numberOfResults": 5}
            },
        )
        citations = []
        seen = set()
        for row in result.get("retrievalResults", []):
            sid = row.get("metadata", {}).get("source_id")
            doc = SOURCES.get(sid)
            text = row.get("content", {}).get("text", "")
            if not doc or not text or sid in seen:
                continue
            # The retrieved source must contain the reviewed excerpt; unknown metadata is not trusted.
            if " ".join(doc["excerpt"].split()) not in " ".join(text.split()):
                continue
            seen.add(sid)
            citations.append(
                {
                    "id": sid,
                    "title": doc["title"],
                    "url": doc["url"],
                    "authority": doc["authority"],
                    "reviewed_at": doc["reviewed_at"],
                    "quote": doc["excerpt"],
                    "score": row.get("score"),
                    "location": row.get("location", {})
                    .get("s3Location", {})
                    .get("uri"),
                }
            )
            emit("source", source_id=sid)
        return {
            "status": "retrieved" if citations else "empty",
            "citations": citations,
            "message": "Reviewed guidance retrieved from Amazon Bedrock Knowledge Bases. Retrieval scores are not compliance confidence."
            if citations
            else "No verified source excerpts were retrieved; regulatory checks require human review.",
        }
    except Exception:
        return {
            "status": "unavailable",
            "citations": [],
            "message": "Knowledge base retrieval is unavailable; no regulatory conclusion was generated from memory.",
        }
