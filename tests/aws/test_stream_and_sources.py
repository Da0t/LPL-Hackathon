"""Real event assembly and strict source attribution, without AWS/network calls."""

from backend.aws.telemetry import capture, converse_stream, diagnostics


class Stream:
    closed = False

    def __iter__(self):
        yield {
            "contentBlockDelta": {
                "contentBlockIndex": 0,
                "delta": {"reasoningContent": {"text": "private"}},
            }
        }
        yield {
            "contentBlockStart": {
                "contentBlockIndex": 1,
                "start": {"toolUse": {"name": "submit_audit", "toolUseId": "1"}},
            }
        }
        for part in ['{"checked":', 'true,"findings":[]}']:
            yield {
                "contentBlockDelta": {
                    "contentBlockIndex": 1,
                    "delta": {"toolUse": {"input": part}},
                }
            }
        yield {"messageStop": {"stopReason": "tool_use"}}
        yield {"metadata": {"usage": {"inputTokens": 20, "outputTokens": 8}}}

    def close(self):
        self.closed = True


class Client:
    def __init__(self):
        self.stream = Stream()

    def converse_stream(self, **kwargs):
        return {"stream": self.stream}


def test_stream_emits_actual_deltas_never_reasoning_and_closes():
    client = Client()
    events = []
    with capture(events.append) as trace:
        response = converse_stream(client, modelId="test-haiku")
        report = diagnostics(trace)
    assert response["output"]["message"]["content"][0]["toolUse"]["input"] == {
        "checked": True,
        "findings": [],
    }
    assert (
        "".join(e["text"] for e in events if e["type"] == "token")
        == '{"checked":true,"findings":[]}'
    )
    assert "private" not in str(events) and client.stream.closed
    assert report["output_tokens"] == 8 and report["tools"] == ["submit_audit"]


def test_compliance_rejects_invented_or_mismatched_citation(monkeypatch):
    from backend.aws import cited_compliance as cc

    monkeypatch.setattr(
        cc,
        "retrieve",
        lambda _: {
            "status": "retrieved",
            "message": "test",
            "citations": [{"id": "SEC-1", "quote": "Consider costs."}],
        },
    )
    monkeypatch.setattr(
        cc.aa,
        "compliance_review",
        lambda *a: {
            "verdict": "pass",
            "findings": [],
            "checks": [
                {
                    "id": "suitability",
                    "status": "pass",
                    "evidence": "Safe.",
                    "citation_ids": ["FAKE", "SEC-1"],
                    "source_quote": "Guaranteed returns.",
                }
            ],
        },
    )
    result = cc.review({}, ai_mode="bedrock")
    assert (
        result["checks"][0]["citation_ids"] == []
        and result["checks"][0]["status"] == "attention"
    )
    assert result["verdict"] == "needs_changes"


def test_retrieval_failure_is_visible_and_cannot_claim_compliance_pass(monkeypatch):
    from backend.aws import cited_compliance as cc

    monkeypatch.setattr(
        cc,
        "retrieve",
        lambda _: {"status": "unavailable", "message": "Unavailable", "citations": []},
    )
    monkeypatch.setattr(
        cc.aa,
        "compliance_review",
        lambda *a: {"verdict": "pass", "findings": [], "checks": []},
    )
    result = cc.review({}, "Hello", ai_mode="bedrock")
    assert result["verdict"] == "needs_changes" and not result["regulatory_grounded"]


def test_typographic_apostrophe_does_not_discard_an_exact_citation(monkeypatch):
    from backend.aws import cited_compliance as cc

    quote = "Consider the customer’s investment profile."
    monkeypatch.setattr(
        cc,
        "retrieve",
        lambda _: {
            "status": "retrieved",
            "message": "test",
            "citations": [{"id": "SEC-1", "quote": quote}],
        },
    )
    monkeypatch.setattr(
        cc.aa,
        "compliance_review",
        lambda *a: {
            "verdict": "pass",
            "findings": [],
            "checks": [
                {
                    "id": "suitability",
                    "status": "attention",
                    "evidence": "Confirm investment profile.",
                    "citation_ids": ["SEC-1"],
                    "source_quote": "the customer's investment profile",
                }
            ],
        },
    )
    result = cc.review({}, ai_mode="bedrock")
    assert result["checks"][0]["citation_ids"] == ["SEC-1"]
    assert result["checks"][0]["source_quote"] == quote


def test_retrieval_discards_unregistered_and_modified_source_content(monkeypatch, tmp_path):
    from backend.aws import knowledge
    monkeypatch.setenv('COHERENT_KB_CONFIG',str(tmp_path/'absent.json'))
    sid, doc=next(iter(knowledge.SOURCES.items()))
    class KB:
        def retrieve(self,**kwargs):
            assert 'Mara' not in kwargs['retrievalQuery']['text']
            return {'retrievalResults':[
                {'metadata':{'source_id':'FAKE'},'content':{'text':doc['excerpt']}},
                {'metadata':{'source_id':sid},'content':{'text':'invented policy'}},
                {'metadata':{'source_id':sid},'content':{'text':doc['excerpt']},'score':0.9},
            ]}
    result=knowledge.retrieve({'client_display_name':'Mara'},client=KB(),knowledge_base_id='TEST')
    assert result['status']=='retrieved' and [c['id'] for c in result['citations']]==[sid]
    assert result['citations'][0]['url']==doc['url']
