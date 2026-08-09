from concurrent.futures import ThreadPoolExecutor
from typing import Optional
from src.agents.triage_classifier import classify_ticket
from src.agents.triage_responder import draft_response
from src.retrieval.kb_index import KBIndex
from src.schemas import KBMatch

_kb_index: Optional[KBIndex] = None


def get_kb_index() -> KBIndex:
    global _kb_index
    if _kb_index is None:
        _kb_index = KBIndex()
    return _kb_index


def run_triage(subject: str, body: str) -> dict:
    kb = get_kb_index()

    with ThreadPoolExecutor(max_workers=2) as executor:
        classify_future = executor.submit(classify_ticket, subject, body)
        kb_future = executor.submit(kb.search, f"{subject}\n{body}", 1)

        classification = classify_future.result()
        kb_results = kb_future.result()

    kb_match = KBMatch(**kb_results[0]) if kb_results else None

    response = draft_response(subject, body, classification, kb_match)

    return {
        "classification": classification.model_dump(),
        "kb_match": kb_match.model_dump() if kb_match else None,
        "responder_team": response["responder_team"],
        "draft_response": response["draft_response"],
    }
