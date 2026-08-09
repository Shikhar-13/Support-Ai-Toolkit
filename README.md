# Support AI Toolkit

Basic working scaffold for the triage agent (Task 1) and account brief
generator (Task 2). Built to be extended, not final -- see "Known gaps"
at the bottom.

## Setup

```bash
pip install -r requirements.txt --break-system-packages
cp .env.example .env
# edit .env and set GEMINI_API_KEY
```

> Note: `src/llm_client.py` wraps the Gemini API (`google-genai`), not the
> Anthropic API — `requirements.txt` and `.env.example` reflect that.

## Run

```bash
uvicorn main:app --reload
```

Then:

```bash
# Task 1
curl -X POST http://localhost:8000/triage \
  -H "Content-Type: application/json" \
  -d '{"subject": "SSO configuration not working for new users", "body": "New joiners cant authenticate, 40 people blocked."}'

# Task 2 (uses the placeholder account/tickets in data/)
curl http://localhost:8000/account_brief/ACC-9999
```

## Tests

```bash
pytest tests/ -v
```

The smoke tests mock every LLM call, so they run without an API key or
network access. They check pipeline wiring (does classification flow into
response drafting, does a hallucinated quote get rejected, does the cache
key ordering behave) -- not model output quality.

## Eval harness (Task 3)

```bash
python -m src.task3_evals.run_evals
```

Runs 6 hand-written test cases per task (5+ required, 1 adversarial each)
through the *real* pipeline -- this needs `ANTHROPIC_API_KEY` set, unlike
the mocked pytest suite above. Writes `eval_report.json` and
`eval_report.md` to the repo root.

Scoring per case combines rule-based checks (schema/enum validity, does the
flagged-ticket set match expectations, is every quote verifiable against
the source ticket, is repeat output identical for the determinism case)
with one LLM-as-judge call scoring subjective quality (0-1) of the drafted
response or brief. A case passes only if every rule-based check passes AND
the averaged quality score clears 0.6 -- so a case can't pass on judge
score alone if it fails a hard rule check, or vice versa.

Adversarial cases:
- Task 1, `T6-adversarial-caps-vs-impact`: a ticket with "URGENT!!!" in the
  subject over a trivial typo, testing whether the classifier is fooled by
  urgent-sounding language instead of reading actual business impact.
- Task 2, `A6-adversarial-no-tickets`: an account with zero tickets in the
  window, testing that incomplete data produces a graceful empty brief
  rather than a crash or a hallucinated risk.

`src/task3_evals/cases_triage.json` and `cases_account.json` are the case
definitions -- `acceptable_urgency`/`acceptable_category` are lists the
harness authors chose by reading each ticket's actual content, not pulled
from any provided dataset's labels (see note below on label noise).

`tests/test_eval_harness.py` verifies the harness's own scoring logic
(threshold math, error handling, report generation) with LLM calls mocked,
same pattern as `tests/test_smoke.py` -- run that with plain `pytest` any
time without a key. It found one real off-by-threshold assumption in an
earlier version of this test during development (see git history / commit
message if version-controlled), which is exactly the kind of thing this
separate mocked suite is for.

**A note on ground truth**: if you're building eval cases from a provided
ticket dataset that ships its own `category`/`urgency` fields, check those
fields against the actual ticket text first -- in the dataset excerpt used
to spec this project, several fields didn't match ticket content (e.g. an
org-wide outage tagged as the lowest urgency tier). Scoring a classifier
against noisy dataset labels would penalize a good classifier for
disagreeing with bad labels. The cases here use hand-reviewed expected
outcomes instead.

## Project layout

```
src/
  llm_client.py        single wrapper around the Anthropic API
  cache.py              flat-file cache, keyed by input hash (Task 2 determinism)
  schemas.py             shared pydantic models
  retrieval/kb_index.py   TF-IDF search over data/kb/*.md
  agents/                 one file per LLM call -- edit these freely
    triage_classifier.py       Task 1: classify ticket
    triage_responder.py        Task 1: route + draft response
    account_risk_extractor.py  Task 2: per-ticket risk flag + quote validation
    account_synthesizer.py     Task 2: brief synthesis
  task1_triage/pipeline.py     orchestrates the two Task 1 agents (no prompt logic)
  task2_account_brief/pipeline.py  orchestrates the two Task 2 agents (no prompt logic)
  task3_evals/                Task 3: eval harness
    judges.py                    rule-based checks + LLM-as-judge scorer
    cases_triage.json            6 hand-written Task 1 cases (1 adversarial)
    cases_account.json           6 hand-written Task 2 cases (1 adversarial)
    run_evals.py                 runs cases through the real pipeline, scores, reports
app/streamlit_app.py    thin UI over both pipelines (bonus)
main.py                 FastAPI app mounting both pipelines
```

**Why agents are split from pipelines**: each agent file owns one prompt,
one schema, one LLM call. The pipeline files only orchestrate -- call order,
concurrency, caching, error handling. You can rewrite a prompt in
`agents/triage_classifier.py` without touching how classification and
retrieval run in parallel in `task1_triage/pipeline.py`, and vice versa.

## Data

`data/accounts.json` and `data/tickets_sample.json` are placeholders with
one fabricated account so the pipeline is runnable end to end. Replace them
with the real starter dataset (500 tickets / 50 accounts) once you swap in
`data/tickets.json` and update the two `load_json(...)` calls in `main.py`
(or generalize them to load full datasets and filter by account + a real
90-day window off `created_at`).

`data/kb/` has two placeholder markdown docs so the TF-IDF retriever has
something to index and return non-empty results against. Add the real KB
docs here -- the index rebuilds automatically from whatever `.md` files it
finds.

## Design note (Task 4)

See [`DESIGN.md`](./DESIGN.md) -- covers why agents are split per-file with
parallel orchestration (Task 1: classification + KB retrieval run
concurrently; Task 2: one risk-extraction call per ticket runs concurrently),
plus the four required points: failure modes, latency vs quality trade-offs,
data sensitivity, and scaling to 10x volume.

## Known gaps (next to build)

- Task 2's "last 90 days" filtering is not implemented -- `main.py`
  currently just filters by account_id. Needs a real date-window filter
  once real `created_at` values are wired in.
- Cache is a flat JSON directory, fine for local dev; swap for Redis if
  this ever runs behind more than one process (see `DESIGN.md` -> Scaling).
- No queue/worker split yet -- both endpoints are synchronous. Fine at
  current scale, becomes the bottleneck at 10x ticket volume (see
  `DESIGN.md` -> Scaling).
- The two Task 1 and all six Task 2 cases that show FAIL in the current
  `eval_report.md` failed on Gemini free-tier rate limits (`429
  RESOURCE_EXHAUSTED`), not pipeline bugs -- see the raw errors in
  `eval_report.json`. Re-run `python -m src.task3_evals.run_evals` with a
  paid-tier key or added inter-call delay to get a clean pass rate.
- No streaming output, CI eval step, or prompt version changelog yet --
  remaining bonus items worth picking up:
  - `app/streamlit_app.py` (thin UI, +5) is already built and wired to
    both pipelines -- run with `streamlit run app/streamlit_app.py`.
  - Streaming (+3), CI eval workflow on every commit (+2), and prompt
    versioning with a changelog (+2) are not started.