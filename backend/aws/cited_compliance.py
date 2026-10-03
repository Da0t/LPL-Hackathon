"""Sentinel's legal context is retrieved, versioned and cited, never inferred from memory."""

from backend.aws import advisor_agents as aa
from backend.aws.knowledge import retrieve
from backend.aws.telemetry import agent


def normalized_quote(text):
    return " ".join(
        text.translate(str.maketrans({"’": "'", "‘": "'", "“": '"', "”": '"'})).split()
    )


def review(case, draft=None, ai_mode="mock"):
    with agent("Sentinel"):
        retrieval = (
            retrieve(case)
            if ai_mode == "bedrock"
            else {
                "status": "offline",
                "citations": [],
                "message": "Offline record checks only; no live regulatory retrieval.",
            }
        )
        grounded = {**case, "policy_sources": retrieval["citations"]}
        note = None
        if ai_mode == "bedrock":
            try:
                result = aa.compliance_review(grounded, draft)
            except Exception:
                result = aa.stub_compliance_review(case, draft)
                note = "Model review unavailable; offline record checks only. Human review required."
                result["verdict"] = "needs_changes"
        else:
            result = aa.stub_compliance_review(case, draft)
        allowed = {c["id"]: c for c in retrieval["citations"]}
        for check in result["checks"]:
            ids = check.get("citation_ids", [])
            quote = check.get("source_quote", "")
            verified = [
                sid
                for sid in ids
                if sid in allowed
                and quote
                and normalized_quote(quote) in normalized_quote(allowed[sid]["quote"])
            ]
            check["citation_ids"] = verified
            check["source_quote"] = allowed[verified[0]]["quote"] if verified else ""
            if check["id"] == "suitability" and ai_mode == "bedrock" and not verified:
                check["status"] = "attention"
                check["evidence"] = (
                    "Suitability requires human assessment; this check has no verified guidance citation."
                )
        if not draft and any(c["status"] != "pass" for c in result["checks"]):
            result["verdict"] = "needs_changes"
        result["retrieval"] = retrieval
        result["citations"] = retrieval["citations"]
        result["review_note"] = note
        result["regulatory_grounded"] = retrieval["status"] == "retrieved"
        if ai_mode == "bedrock" and (retrieval["status"] != "retrieved" or note):
            result["verdict"] = "needs_changes"
        return result
