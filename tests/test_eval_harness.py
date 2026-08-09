from unittest.mock import patch
from src.task3_evals import run_evals as re


def test_score_case_pass():
    checks = [("a", True, "ok"), ("b", True, "ok")]
    result = re._score_case("case1", False, checks, judge_score=0.9, error=None)
    assert result["passed"] is True
    assert result["quality_score"] > 0.8


def test_score_case_fail_on_hard_check():
    checks = [("a", False, "bad"), ("b", True, "ok")]
    result = re._score_case("case1", False, checks, judge_score=1.0, error=None)
    assert result["passed"] is False


def test_score_case_below_threshold_fails_even_if_checks_pass():
    # one passing rule check (1.0) averaged with a low judge score (0.1) = 0.55,
    # below the 0.6 threshold -- checks passing alone isn't enough
    checks = [("a", True, "ok")]
    result = re._score_case("case1", False, checks, judge_score=0.1, error=None)
    assert result["passed"] is False
    assert result["quality_score"] < 0.6


def test_score_case_error_short_circuits():
    result = re._score_case("case1", False, [], judge_score=None, error="boom")
    assert result["passed"] is False
    assert result["quality_score"] == 0.0
    assert result["error"] == "boom"


def test_run_triage_cases_wiring():
    fake_result = {
        "classification": {
            "product_area": "SSO", "issue_category": "Onboarding",
            "urgency": "P2", "reasoning": "New users blocked.",
        },
        "kb_match": None,
        "responder_team": "Integrations",
        "draft_response": "We're looking into this now.",
    }
    with patch("src.task3_evals.run_evals.run_triage", return_value=fake_result), \
         patch("src.task3_evals.judges.llm_judge", return_value={"score": 0.85, "justification": "ok"}):
        results = re.run_triage_cases()

    assert len(results) >= 5
    assert any(r["adversarial"] for r in results), "must include at least one adversarial case"


def test_run_account_cases_wiring():
    fake_brief = {
        "account_id": "EVAL-A1",
        "executive_summary": "One risk flagged.",
        "open_risks": [{
            "ticket_id": "EVAL-A1-T1", "risk_type": "Churn risk",
            "quote": "we will cancel our contract", "explanation": "explicit cancellation threat",
        }],
        "talking_points": ["Address the risk directly."],
    }
    with patch("src.task3_evals.run_evals.run_account_brief", return_value=fake_brief), \
         patch("src.task3_evals.judges.llm_judge", return_value={"score": 0.8, "justification": "ok"}):
        results = re.run_account_cases()

    assert len(results) >= 5
    assert any(r["adversarial"] for r in results), "must include at least one adversarial case"


def test_write_reports_produces_files(tmp_path):
    fake_results = [
        {"id": "c1", "adversarial": False, "passed": True, "quality_score": 0.9,
         "checks": [], "judge_score": 0.9, "error": None},
    ]
    re.write_reports(fake_results, fake_results, out_dir=str(tmp_path))

    assert (tmp_path / "eval_report.json").exists()
    assert (tmp_path / "eval_report.md").exists()

    md_content = (tmp_path / "eval_report.md").read_text()
    assert "PASS" in md_content
    assert "1/1 passed" in md_content
