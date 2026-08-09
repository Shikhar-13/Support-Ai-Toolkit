"""
Scoring functions for the eval harness. Rule-based checks are pure Python --
free, instant, never flaky. The LLM-as-judge call is reserved for genuinely
subjective quality (is this response actually helpful and grounded) rather
than anything that's checkable in code.
"""
from src.llm_client import call_structured

JUDGE_SYSTEM_PROMPT = (
    "You are grading the quality of an AI-generated {kind} against the source "
    "material. Score from 0.0 (unusable) to 1.0 (excellent) based on accuracy, "
    "relevance, and whether it is grounded in the source -- not on writing style alone."
)

JUDGE_TOOL_SCHEMA = {
    "type": "object",
    "properties": {
        "score": {"type": "number"},
        "justification": {"type": "string"},
    },
    "required": ["score", "justification"],
}


def llm_judge(kind: str, source: str, output: str) -> dict:
    system = JUDGE_SYSTEM_PROMPT.format(kind=kind)
    user_prompt = f"Source material:\n{source}\n\nGenerated {kind}:\n{output}"
    result = call_structured(system, user_prompt, JUDGE_TOOL_SCHEMA, "grade_output", temperature=0)
    score = max(0.0, min(1.0, float(result["score"])))
    return {"score": score, "justification": result["justification"]}


# ---- rule-based checks: Task 1 ----

def check_urgency_in_range(actual_urgency: str, acceptable: list):
    ok = actual_urgency in acceptable
    return ok, f"urgency={actual_urgency}, acceptable={acceptable}"


def check_category_in_set(actual_category: str, acceptable):
    if not acceptable:
        return True, "no category constraint for this case"
    ok = actual_category in acceptable
    return ok, f"category={actual_category}, acceptable={acceptable}"


def check_non_empty(value: str, field_name: str):
    ok = bool(value and value.strip())
    return ok, f"{field_name} non-empty: {ok}"


# ---- rule-based checks: Task 2 ----

def check_flagged_tickets(actual_flags: list, expected_ticket_ids: set):
    actual_ids = {f["ticket_id"] for f in actual_flags}
    ok = actual_ids == expected_ticket_ids
    return ok, f"flagged={sorted(actual_ids)}, expected={sorted(expected_ticket_ids)}"


def check_quotes_verified(actual_flags: list, tickets_by_id: dict):
    for flag in actual_flags:
        ticket = tickets_by_id.get(flag["ticket_id"])
        if ticket is None or flag["quote"] not in ticket["body"]:
            return False, f"unverifiable quote on {flag['ticket_id']}"
    return True, "all quotes verified against source ticket text"


def check_determinism(brief_a: dict, brief_b: dict):
    ok = brief_a == brief_b
    return ok, "identical output on repeat call" if ok else "output changed between repeat calls"
