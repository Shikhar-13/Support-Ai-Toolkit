# Design note

## Architecture approach: separate agents, parallel retrieval

Every LLM call in this system lives in its own file under `src/agents/`, one
prompt and one schema per file, and is wired together by a thin
orchestration layer (`task1_triage/pipeline.py`, `task2_account_brief/pipeline.py`)
that contains no prompt logic at all. The alternative — one long prompt per
task that classifies, retrieves, and drafts in a single call — is faster to
write but couples everything: tuning the classifier's prompt risks silently
changing the tone of the customer-facing response, and a single point of
failure takes the whole ticket down. Splitting the calls means each prompt
can be iterated, versioned, and evaluated independently, and a bad output
from one agent is isolated rather than compounding into the next.

This split also unlocks concurrency. In Task 1, ticket classification and
KB retrieval don't depend on each other — both only need the raw ticket
text — so they run in a `ThreadPoolExecutor` at the same time, and only the
response-drafting agent, which genuinely needs both outputs, waits on
their results. In Task 2, risk extraction runs once per ticket, and
tickets are independent of each other, so up to five run concurrently;
one ticket erroring out (bad model output, transient API failure) returns
`None` for that ticket instead of failing the whole brief. Retrieval
itself is deliberately not an LLM or embedding-API call — it's local
TF-IDF cosine similarity over the KB docs — which keeps latency low, keeps
retrieval "always on" even if the model provider is down, and avoids
sending ticket text anywhere just to find a matching doc.

## Failure modes

1. **Hallucinated evidence.** The biggest risk in a churn-risk tool is a
   flagged risk with a quote the customer never said. This is mitigated
   structurally, not just by prompting: every quote returned by
   `account_risk_extractor` is checked with a substring match against the
   real ticket body before it's trusted, and dropped silently if it
   doesn't match.
2. **Silent misclassification under label drift.** A ticket classifier can
   look fine on paper while systematically under- or over-rating urgency
   (e.g. treating "URGENT!!!" in the subject as signal instead of reading
   actual business impact). This is detected by the eval harness's
   adversarial case (`T6`) and by review of the `reasoning` field the
   classifier is required to return — if reasoning routinely cites tone
   over impact, that's a signal to retune the prompt.
3. **Provider-side rate limits / outages.** `llm_client.call_structured`
   retries with backoff, but a sustained outage or quota exhaustion (which
   is in fact what caused several failures in the current `eval_report.json`
   — free-tier quota, not a code defect) will surface as a 5xx from the API
   endpoints. Mitigation: retries plus a circuit breaker so failures degrade
   to a "try again shortly" response for the agent rather than hanging,
   and alerting on sustained error rate rather than per-call failures.

## Latency vs quality

Task 1 drafts a first-response message only after classification and KB
retrieval both complete, rather than starting to draft speculatively; the
response otherwise risks referencing the wrong KB doc or team. The
trade-off is one extra sequential LLM call (classify → draft) on top of
the parallel branch. If latency were the hard constraint, the fix would be
to stream the draft response token-by-token to the agent's screen while
classification metadata fills in a moment later, rather than blocking the
whole response on classification finishing first — the agent reads while
the last details resolve instead of waiting on a spinner.

## Data sensitivity

Ticket and account text is PII-bearing (names, emails, sometimes account
identifiers). Retrieval never leaves the process — TF-IDF has no external
call, so ticket text is never sent to a third party just to find a
matching KB doc. The one external dependency is the LLM provider itself,
which is unavoidable for classification, drafting, and synthesis; the
mitigation is minimizing what's sent (raw ticket/account fields, no
enrichment from other systems) and treating the provider under the same
data-processing agreement as any other subprocessor. `.env` holding the
API key is gitignored, and `.env.example` ships instead of real values.

## Scaling

At 10x ticket volume, the first thing to break is the free-file cache in
`src/cache.py` and the synchronous, single-process FastAPI endpoints —
fine for local dev, but they don't survive multiple worker processes or
concurrent writes. The fix is a real queue (tickets land in a queue,
workers pull and process, results are pushed to a datastore) plus a
shared cache like Redis instead of flat JSON files. The second thing to
break is LLM provider rate limits themselves, since concurrency inside one
account brief (5 parallel risk-extraction calls) multiplies fast across
many simultaneous briefs — this needs a global rate limiter/queue in front
of `llm_client`, not just per-request retries.
