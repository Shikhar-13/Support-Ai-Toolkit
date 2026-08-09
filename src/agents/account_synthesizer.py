from src.llm_client import call_structured

SYSTEM_PROMPT = (
    "You write a concise TAM account brief from account data and flagged risks. "
    "Executive summary: 3-5 sentences. Talking points: 3-5 short, specific, "
    "actionable bullets the TAM can raise on the call. Do not invent facts that "
    "are not present in the input."
)

TOOL_SCHEMA = {
    "type": "object",
    "properties": {
        "executive_summary": {"type": "string"},
        "talking_points": {
            "type": "array",
            "items": {"type": "string"},
        },
    },
    "required": ["executive_summary", "talking_points"],
}


def synthesize_brief(account: dict, risk_flags: list) -> dict:
    risk_lines = "\n".join(
        f"- [{r['risk_type']}] {r['explanation']} (quote: \"{r['quote']}\")"
        for r in risk_flags
    ) or "No flagged risks in the last 90 days."

    user_prompt = (
        f"Account: {account.get('company', account['account_id'])} "
        f"({account.get('plan_tier', 'unknown plan')})\n\n"
        f"Flagged risks:\n{risk_lines}"
    )
    return call_structured(SYSTEM_PROMPT, user_prompt, TOOL_SCHEMA, "synthesize_brief")
