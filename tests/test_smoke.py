from unittest.mock import patch
from src.task1_triage.pipeline import run_triage
from src.task2_account_brief.pipeline import run_account_brief


def test_triage_pipeline_wiring():
    fake_classification = {
        "product_area": "SSO",
        "issue_category": "Onboarding",
        "urgency": "P2",
        "reasoning": "New users blocked from authenticating.",
    }
    fake_response = {
        "responder_team": "Integrations",
        "draft_response": "Thanks for reaching out, we're looking into your SSO issue.",
    }

    with patch("src.agents.triage_classifier.call_structured", return_value=fake_classification), \
         patch("src.agents.triage_responder.call_structured", return_value=fake_response):
        result = run_triage(
            "SSO configuration not working for new users",
            "New joiners can't authenticate, 40 people blocked.",
        )

    assert result["classification"]["urgency"] == "P2"
    assert result["responder_team"] == "Integrations"
    assert "draft_response" in result


def test_account_brief_pipeline_wiring():
    account = {"account_id": "ACC-TEST", "company": "Test Co", "plan_tier": "Business"}
    tickets = [{
        "ticket_id": "TKT-T1",
        "subject": "Test issue",
        "body": "This is unacceptable, we may cancel our subscription.",
        "status": "Open",
        "satisfaction_score": 1,
    }]

    fake_risk = {
        "has_risk": True,
        "risk_type": "Churn risk",
        "quote": "we may cancel our subscription",
        "explanation": "Customer explicitly mentioned cancelling.",
    }
    fake_synthesis = {
        "executive_summary": "Account shows one active churn signal this period.",
        "talking_points": ["Address the churn risk on TKT-T1 directly on the call."],
    }

    with patch("src.agents.account_risk_extractor.call_structured", return_value=fake_risk), \
         patch("src.agents.account_synthesizer.call_structured", return_value=fake_synthesis):
        brief = run_account_brief(account, tickets)

    assert brief["account_id"] == "ACC-TEST"
    assert len(brief["open_risks"]) == 1
    assert brief["open_risks"][0]["quote"] in tickets[0]["body"]


def test_account_brief_rejects_hallucinated_quote():
    from src.agents.account_risk_extractor import extract_risk

    ticket = {
        "ticket_id": "TKT-T2",
        "subject": "Fine, no issue",
        "body": "Everything is working as expected, thanks.",
        "status": "Resolved",
        "satisfaction_score": 5,
    }
    fake_risk = {
        "has_risk": True,
        "risk_type": "Churn risk",
        "quote": "we are going to cancel immediately",  # not actually in the ticket body
        "explanation": "Fabricated.",
    }
    with patch("src.agents.account_risk_extractor.call_structured", return_value=fake_risk):
        result = extract_risk(ticket)

    assert result is None
