"""Adversarial approval, streaming transport, and independent-review boundaries."""

import json
from backend.aws.auditor import audit_packet, deterministic
from tests.backend.conftest import STAFF, CLIENT

RECORD = {
    "case_id": "CASE-T",
    "client_display_name": "Mara Ellis",
    "amount_requested": 6000,
    "account_context": {
        "account_type": "rollover_ira",
        "masked_identifier": "****1234",
        "balance": 84000,
    },
}


def test_wrong_field_source_cannot_launder_balance_as_requested_amount():
    issues, checks = deterministic(
        RECORD,
        {
            "prepared_fields": [
                {
                    "label": "Amount",
                    "value": "$84,000",
                    "source_path": "account_context.balance",
                }
            ]
        },
    )
    assert issues and not checks[0]["matches"]


def test_formatted_amount_matches_but_unknown_account_and_amount_fail():
    assert (
        audit_packet(
            RECORD,
            {
                "prepared_fields": [
                    {
                        "label": "Amount",
                        "value": "$6,000.00",
                        "source_path": "amount_requested",
                    }
                ]
            },
        )["verdict"]
        == "pass"
    )
    result = audit_packet(
        RECORD, {"draft_client_message": "We will move $9,999 from ****9999."}
    )
    assert result["verdict"] == "needs_fix" and len(result["findings"]) == 2


def test_model_failure_blocks_even_a_deterministically_clean_packet(monkeypatch):
    from backend.aws import auditor

    monkeypatch.setattr(
        auditor.ba,
        "_run_tool_loop",
        lambda *a, **k: (_ for _ in ()).throw(RuntimeError("unavailable")),
    )
    result = auditor.audit_packet(
        RECORD,
        {"draft_client_message": "Please confirm your request."},
        "bedrock",
        client=object(),
    )
    assert result["mode"] == "unavailable" and result["verdict"] == "needs_fix"


def test_critic_can_anchor_findings_containing_quotes(monkeypatch):
    from backend.aws import auditor

    quote = 'Your "guaranteed" return is 20%.'
    monkeypatch.setattr(
        auditor.ba,
        "_run_tool_loop",
        lambda *a, **k: {
            "checked": True,
            "findings": [
                {
                    "location": "draft_client_message",
                    "quote": quote,
                    "issue": "Invented return.",
                }
            ],
        },
    )
    result = auditor.audit_packet(
        RECORD, {"draft_client_message": quote}, "bedrock", client=object()
    )
    assert (
        result["mode"] == "bedrock+deterministic" and result["verdict"] == "needs_fix"
    )


def test_approval_requires_matching_current_audit_and_records_receipt(client):
    path = "/staff/cases/CASE-1042"
    client.get(path, headers=STAFF)
    assert (
        client.post(
            path + "/action", headers=STAFF, json={"action": "approve"}
        ).status_code
        == 409
    )
    plan = client.post(path + "/plan", headers=STAFF).json()
    assert plan["audit"]["verdict"] == "pass", plan
    response = client.post(
        path + "/action",
        headers=STAFF,
        json={"action": "approve", "plan_id": plan["plan_id"]},
    )
    assert response.status_code == 200, response.text
    assert response.json()["event"]["details"]["audit"]["verdict"] == "pass"
    assert (
        client.post(
            path + "/action",
            headers=STAFF,
            json={"action": "approve", "plan_id": plan["plan_id"]},
        ).status_code
        == 409
    )


def test_case_mutation_invalidates_packet(client):
    path = "/staff/cases/CASE-1042"
    client.get(path, headers=STAFF)
    plan = client.post(path + "/plan", headers=STAFF).json()
    client.post(
        path + "/action",
        headers=STAFF,
        json={"action": "note", "text": "Client called again."},
    )
    r = client.post(
        path + "/action",
        headers=STAFF,
        json={"action": "approve", "plan_id": plan["plan_id"]},
    )
    assert r.status_code == 409 and r.json()["error_code"] == "STALE_PACKET"


def test_hallucinated_draft_cannot_be_sent_with_compliance_override(client):
    r = client.post(
        "/staff/cases/CASE-1042/action",
        headers=STAFF,
        json={
            "action": "clarify",
            "text": "Your balance is $999,999.",
            "compliance": {"override": True},
        },
    )
    assert r.status_code == 409 and r.json()["error_code"] == "DRAFT_AUDIT_FAILED"


def test_stream_is_staff_only_and_offline_does_not_fabricate_tokens(client):
    path = "/staff/cases/CASE-1042/agents/stream"
    assert (
        client.post(path, headers=CLIENT, json={"operation": "plan"}).status_code == 403
    )
    r = client.post(path, headers=STAFF, json={"operation": "plan"})
    assert r.status_code == 200 and r.headers["content-type"].startswith(
        "text/event-stream"
    )
    events = [
        json.loads(line[6:])
        for line in r.text.splitlines()
        if line.startswith("data: ")
    ]
    assert not any(e["type"] == "token" for e in events)
    result = next(e["result"] for e in events if e["type"] == "result")
    assert (
        result["audit"]["verdict"] == "pass" and result["diagnostics"]["models"] == []
    )
    assert events[-1]["type"] == "done"


def test_review_cannot_cache_a_pass_for_a_case_that_changed_during_generation(app, monkeypatch):
    from backend.aws import cited_compliance
    from backend.aws.auditor import fingerprint
    service=app.state.staff
    before=fingerprint(service._case('CASE-1042'))
    def review(*args):
        service.action('CASE-1042','note','A new fact arrived during generation.')
        return {'verdict':'pass','checks':[],'findings':[]}
    monkeypatch.setattr(cited_compliance,'review',review)
    service.compliance_review('CASE-1042','When would you like a call?')
    after=fingerprint(service._case('CASE-1042'))
    assert before!=after
    assert ('CASE-1042',before,'When would you like a call?') in service._verdicts
    assert ('CASE-1042',after,'When would you like a call?') not in service._verdicts


def test_live_reply_workflow_calls_cited_reviewer_without_silent_fallback(app, monkeypatch):
    from backend.aws import advisor_agents, cited_compliance, auditor
    calls=[]
    monkeypatch.setattr(advisor_agents,'draft_reply',lambda *a:{'message':'When would you like a call?'})
    def review(case,draft,mode):
        calls.append(mode)
        return {'verdict':'pass','checks':[],'findings':[],'retrieval':{'status':'retrieved'}}
    monkeypatch.setattr(cited_compliance,'review',review)
    monkeypatch.setattr(auditor,'audit_packet',lambda *a:{'verdict':'pass','mode':'bedrock+deterministic'})
    result=app.state.staff.reply_draft('CASE-1042',ai_mode='bedrock')
    assert calls==['bedrock'] and result['note'] is None
    assert result['review']['retrieval']['status']=='retrieved'


def test_passing_packet_does_not_authorize_an_invented_edited_message(client):
    path='/staff/cases/CASE-1042'
    plan=client.post(path+'/plan',headers=STAFF).json()
    response=client.post(path+'/action',headers=STAFF,json={
        'action':'approve','plan_id':plan['plan_id'],
        'text':'Your account balance is $999,999.', 'compliance':{'override':True}})
    assert response.status_code==409 and response.json()['error_code']=='DRAFT_AUDIT_FAILED'
    history=client.get(path,headers=STAFF).json()['history']
    assert not any(e['event']=='action_approved' for e in history)
