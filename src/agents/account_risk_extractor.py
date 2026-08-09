from src.llm_client import call_structured

SYSTEM_PROMPT = (
    "You review a single support ticket for signs of churn risk or escalation risk: "
    "strong dissatisfaction, repeated failures, threats to cancel or downgrade, low "
    "satisfaction scores, or business-critical impact. If you find a real risk "
    "signal, quote the exact phrase from the ticket body that supports it, word for "
    "word. If there is no real risk signal, set has_risk to false."
)

TOOL_SCHEMA = {
    "type": "object",
    "properties": {
        "has_risk": {"type": "boolean"},
        "risk_type": {"type": "string"},
        "quote": {"type": "string"},
        "explanation": {"type": "string"},
    },
    "required": ["has_risk", "risk_type", "quote", "explanation"],
}


def extract_risk(ticket: dict):
    user_prompt = (
        f"Ticket {ticket['ticket_id']}\nSubject: {ticket['subject']}\n\n"
        f"Body:\n{ticket['body']}\n\n"
        f"Satisfaction score: {ticket.get('satisfaction_score')}\n"
        f"Status: {ticket.get('status')}"
    )
    result = call_structured(SYSTEM_PROMPT, user_prompt, TOOL_SCHEMA, "extract_risk")

    if not result.get("has_risk"):
        return None

    quote = result.get("quote", "")
    if not quote or quote not in ticket["body"]:
        # The model claimed a quote that isn't actually in the ticket text.
        # Drop the flag rather than including unverifiable evidence.
        return None

    return {
        "ticket_id": ticket["ticket_id"],
        "risk_type": result["risk_type"],
        "quote": quote,
        "explanation": result["explanation"],
    }
