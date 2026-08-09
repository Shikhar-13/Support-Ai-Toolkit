from typing import Optional
from src.llm_client import call_structured
from src.schemas import TriageClassification, KBMatch

SYSTEM_PROMPT = (
    "You are drafting a first-response message for a support agent to send to a "
    "customer. Be concise, empathetic, and specific to the ticket. If a knowledge "
    "base article is provided, reference it naturally. Also recommend which internal "
    "team should own this ticket."
)

TOOL_SCHEMA = {
    "type": "object",
    "properties": {
        "responder_team": {
            "type": "string",
            "enum": ["Billing", "Platform Engineering", "Integrations", "Onboarding",
                     "Data Recovery", "Product/Feature Requests", "Tier 2 Support"],
        },
        "draft_response": {"type": "string"},
    },
    "required": ["responder_team", "draft_response"],
}


def draft_response(subject: str, body: str, classification: TriageClassification,
                    kb_match: Optional[KBMatch]) -> dict:
    kb_note = (
        f"\n\nRelevant KB article: {kb_match.title} "
        f"(category: {kb_match.category}, doc: {kb_match.doc_id})"
        if kb_match else "\n\nNo close KB match found."
    )
    user_prompt = (
        f"Subject: {subject}\n\nBody:\n{body}\n\n"
        f"Classification: product_area={classification.product_area}, "
        f"category={classification.issue_category}, urgency={classification.urgency}"
        f"{kb_note}"
    )
    return call_structured(SYSTEM_PROMPT, user_prompt, TOOL_SCHEMA, "draft_response")
