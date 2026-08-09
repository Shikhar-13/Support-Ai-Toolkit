from concurrent.futures import ThreadPoolExecutor, as_completed
from src import cache
from src.agents.account_risk_extractor import extract_risk
from src.agents.account_synthesizer import synthesize_brief

CACHE_VERSION = "account_brief_v1"  # bump this if the prompts change meaningfully


def run_account_brief(account: dict, tickets: list) -> dict:
    ticket_ids = sorted(t["ticket_id"] for t in tickets)
    cache_key = cache.make_key(CACHE_VERSION, account["account_id"], *ticket_ids)

    cached = cache.get(cache_key)
    if cached is not None:
        return cached

    risk_flags = []
    with ThreadPoolExecutor(max_workers=5) as executor:
        futures = {executor.submit(extract_risk, t): t for t in tickets}
        for future in as_completed(futures):
            try:
                result = future.result()
            except Exception:
                result = None  # one failed ticket call does not fail the whole brief
            if result:
                risk_flags.append(result)

    risk_flags.sort(key=lambda r: r["ticket_id"])  # deterministic ordering before synthesis

    synthesis = synthesize_brief(account, risk_flags)

    brief = {
        "account_id": account["account_id"],
        "executive_summary": synthesis["executive_summary"],
        "open_risks": risk_flags,
        "talking_points": synthesis["talking_points"],
    }

    cache.set(cache_key, brief)
    return brief
