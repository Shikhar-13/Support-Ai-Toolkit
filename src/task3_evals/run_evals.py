"""
Task 3 evaluation harness. Runs every case in cases_triage.json and
cases_account.json through the real pipeline, scores the output with
rule-based checks plus an LLM-as-judge call for subjective quality, and
writes eval_report.md / eval_report.json to the repo root.

Run with: python -m src.task3_evals.run_evals
This hits the real model -- it is a live eval run, not the mocked smoke
test suite in tests/ -- so ANTHROPIC_API_KEY must be set.
"""
import json
import os

from src.task1_triage.pipeline import run_triage
from src.task2_account_brief.pipeline import run_account_brief
from src.task3_evals import judges

CASES_DIR = os.path.dirname(os.path.abspath(__file__))
QUALITY_THRESHOLD = 0.6


def run_triage_cases():
    with open(os.path.join(CASES_DIR, "cases_triage.json")) as f:
        cases = json.load(f)

    results = []
    for case in cases:
        checks = []
        judge_score = None
        error = None
        try:
            result = run_triage(case["subject"], case["body"])
            c = result["classification"]

            ok, detail = judges.check_urgency_in_range(c["urgency"], case["acceptable_urgency"])
            checks.append(("urgency_in_range", ok, detail))

            ok, detail = judges.check_category_in_set(c["issue_category"], case.get("acceptable_category"))
            checks.append(("category_in_set", ok, detail))

            ok, detail = judges.check_non_empty(c["reasoning"], "reasoning")
            checks.append(("reasoning_present", ok, detail))

            ok, detail = judges.check_non_empty(result["draft_response"], "draft_response")
            checks.append(("draft_response_present", ok, detail))

            judge_result = judges.llm_judge(
                "support first-response message",
                f"Subject: {case['subject']}\nBody: {case['body']}",
                result["draft_response"],
            )
            judge_score = judge_result["score"]
        except Exception as e:
            error = str(e)

        results.append(_score_case(case["id"], case.get("adversarial", False), checks, judge_score, error))
    return results


def run_account_cases():
    with open(os.path.join(CASES_DIR, "cases_account.json")) as f:
        cases = json.load(f)

    results = []
    for case in cases:
        checks = []
        judge_score = None
        error = None
        try:
            account = case["account"]
            tickets = case["tickets"]
            tickets_by_id = {t["ticket_id"]: t for t in tickets}

            brief = run_account_brief(account, tickets)

            expected_ids = set(case["expected_flagged_ticket_ids"])
            ok, detail = judges.check_flagged_tickets(brief["open_risks"], expected_ids)
            checks.append(("flagged_tickets_match", ok, detail))

            ok, detail = judges.check_quotes_verified(brief["open_risks"], tickets_by_id)
            checks.append(("quotes_verified", ok, detail))

            if case.get("check_determinism"):
                brief_again = run_account_brief(account, tickets)
                ok, detail = judges.check_determinism(brief, brief_again)
                checks.append(("determinism", ok, detail))

            if tickets:
                source = "\n".join(f"- {t['subject']}: {t['body']}" for t in tickets)
                judge_result = judges.llm_judge("TAM account brief", source, brief["executive_summary"])
                judge_score = judge_result["score"]
        except Exception as e:
            error = str(e)

        results.append(_score_case(case["id"], case.get("adversarial", False), checks, judge_score, error))
    return results


def _score_case(case_id, adversarial, checks, judge_score, error):
    if error:
        return {
            "id": case_id, "adversarial": adversarial, "passed": False,
            "quality_score": 0.0, "checks": [], "judge_score": None, "error": error,
        }

    components = [1.0 if ok else 0.0 for _, ok, _ in checks]
    if judge_score is not None:
        components.append(judge_score)
    quality_score = round(sum(components) / len(components), 3) if components else 0.0

    all_checks_passed = all(ok for _, ok, _ in checks)
    passed = all_checks_passed and quality_score >= QUALITY_THRESHOLD

    return {
        "id": case_id, "adversarial": adversarial, "passed": passed,
        "quality_score": quality_score,
        "checks": [{"name": n, "passed": ok, "detail": d} for n, ok, d in checks],
        "judge_score": judge_score, "error": None,
    }


def write_reports(triage_results, account_results, out_dir="."):
    report = {"task1_triage": triage_results, "task2_account_brief": account_results}
    with open(os.path.join(out_dir, "eval_report.json"), "w") as f:
        json.dump(report, f, indent=2)

    lines = ["# Eval report"]
    for task_name, results in [
        ("Task 1: Ticket Triage", triage_results),
        ("Task 2: Account Brief", account_results),
    ]:
        lines.append(f"\n## {task_name}\n")
        lines.append("| Case | Adversarial | Passed | Quality score |")
        lines.append("|---|---|---|---|")
        for r in results:
            lines.append(f"| {r['id']} | {r['adversarial']} | {'PASS' if r['passed'] else 'FAIL'} | {r['quality_score']} |")
        n_passed = sum(1 for r in results if r["passed"])
        lines.append(f"\n**{n_passed}/{len(results)} passed**")

    with open(os.path.join(out_dir, "eval_report.md"), "w") as f:
        f.write("\n".join(lines) + "\n")


if __name__ == "__main__":
    print("Running Task 1 triage eval cases...")
    triage_results = run_triage_cases()
    print("Running Task 2 account brief eval cases...")
    account_results = run_account_cases()
    write_reports(triage_results, account_results)
    print("Wrote eval_report.json and eval_report.md")
