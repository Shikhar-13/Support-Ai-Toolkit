"""
Task 1, agent 1: classifies a raw ticket into product area, issue category,
and urgency, with reasoning. This is the only place classification prompt
logic lives -- edit this file to change how tickets get classified without
touching the pipeline that calls it.
"""
from src.llm_client import call_structured
from src.schemas import TriageClassification

SYSTEM_PROMPT = (
    "You are a technical support triage classifier. Read the ticket and classify it. "
    "Base urgency on real business impact described in the ticket: number of users "
    "affected, whether it is a full outage or a minor inconvenience, and whether a "
    "workaround exists.\n"
    "P1 = critical outage or data loss blocking many users, no workaround.\n"
    "P2 = major functionality broken, workaround is difficult.\n"
    "P3 = moderate issue, workaround exists.\n"
    "P4 = minor issue, question, or feature request."
)

TOOL_SCHEMA = {
    "type": "object",
    "properties": {
        "product_area": {"type": "string"},
        "issue_category": {
            "type": "string",
            "enum": ["Bug", "How-To", "Billing", "Integration", "Onboarding",
                     "Data Loss", "Performance", "Feature Request"],
        },
        "urgency": {"type": "string", "enum": ["P1", "P2", "P3", "P4"]},
        "reasoning": {"type": "string"},
    },
    "required": ["product_area", "issue_category", "urgency", "reasoning"],
}


def classify_ticket(subject: str, body: str) -> TriageClassification:
    user_prompt = f"Subject: {subject}\n\nBody:\n{body}"
    result = call_structured(SYSTEM_PROMPT, user_prompt, TOOL_SCHEMA, "classify_ticket")
    return TriageClassification(**result)
