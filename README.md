# Support AI Toolkit

AI tooling for Technical Support and TAM teams: a ticket triage agent
(Task 1), a TAM account health summarizer (Task 2), an evaluation harness
(Task 3), a design note (Task 4), and a thin Streamlit UI (bonus).

Built to be extended, not final -- see "Known gaps" at the bottom.

## Contents

- [Architecture](#architecture)
- [System design decisions](#system-design-decisions)
- [Setup](#setup)
- [Run](#run)
- [Tests](#tests)
- [Eval harness](#eval-harness-task-3)
- [Design note](#design-note-task-4)
- [Project layout](#project-layout)
- [Data](#data)

## Architecture

Two independent pipelines sit behind one FastAPI app and one Streamlit UI.
Both pipelines are built from small, single-purpose agent files that only
do one LLM call each -- see [System design decisions](#system-design-decisions)
for why.

### Task 1: Ticket triage

```
Ticket (subject + body)
        |
        |-------------------------+
        v                         v
  Classify (LLM call)      KB retrieval (TF-IDF,
  product_area,             local, no LLM/embedding
  issue_category,           call -- see "Data
  urgency, reasoning        sensitivity" below)
        |                         |
        +------------+------------+
                     v
         Route + draft response (LLM call)
         responder_team, draft_response,
         grounded in classification + KB match
                     |
                     v
         Structured JSON, returned via
         FastAPI POST /triage
```

Classification and KB retrieval run **concurrently** (`ThreadPoolExecutor`
in `task1_triage/pipeline.py`) because retrieval doesn't depend on the
classification output -- there's no reason to pay for them sequentially.
Routing and response drafting run *after* both finish, since the draft
needs both the classification and (if found) the KB match as grounding.

### Task 2: TAM account health brief

```
Account ID
        |
        v
  Cache check (hash of account_id + ticket_ids + prompt version)
        |
        | miss                              hit -> return cached brief,
        v                                          zero LLM calls
  Load account summary + last-90-days tickets
        |
        v
  Risk extraction, one call PER TICKET, run concurrently
  (ThreadPoolExecutor) -- a slow or failing ticket only
  costs that ticket, never the whole brief
        |
        v
  Quote validation gate: every flagged risk's quote must be
  an exact substring of its source ticket. Anything that
  doesn't verify is dropped, not surfaced.
        |
        v
  Synthesis (LLM call): validated risk flags + account data
  -> executive summary, open risks, talking points
        |
        v
  Written to cache under the input hash, returned
```

The **cache check runs first**, not last. That's what makes the output
actually deterministic for a repeat call on the same account and ticket
set -- not "consistent at low temperature" (which Gemini 3.x no longer
even guarantees, see the design note), but byte-identical, because a
cache hit never touches the LLM at all.

### End-to-end request flow

```
                    +-------------------+
   HTTP request --> |   FastAPI (main.py)|
   or Streamlit -->  +-------------------+
                              |
             +----------------+----------------+
             v                                  v
   task1_triage/pipeline.py          task2_account_brief/pipeline.py
   (orchestration only)               (orchestration only)
             |                                  |
   +---------+---------+              +---------+---------+
   v                   v               v                   v
 agents/            retrieval/        agents/             src/cache.py
 triage_classifier   kb_index.py      account_risk_        (Task 2
 triage_responder    (TF-IDF,          extractor,           determinism)
 (LLM calls via       local)           account_synthesizer
  llm_client.py)                       (LLM calls via
                                        llm_client.py)
             |                                  |
             +----------------+-----------------+
                              v
                    src/llm_client.py
                (single wrapper around the
                 Gemini API -- retries,
                 structured output)
```

## System design decisions

**Agent files are isolated from pipeline orchestration, one LLM call per
file.** `src/agents/` has exactly four files -- `triage_classifier.py`,
`triage_responder.py`, `account_risk_extractor.py`, `account_synthesizer.py`
-- each owning one system prompt, one schema, one call. The two
`pipeline.py` files only handle call order, concurrency, caching, and error
handling; they contain no prompt text. This paid off directly during
development: swapping the entire LLM provider from Anthropic to Gemini
touched exactly one file (`llm_client.py`) plus a few config strings --
zero agent files changed, and the full mocked test suite still passed
without modification, because every agent calls through the same
`call_structured()` interface regardless of what's behind it.

**Retrieval is TF-IDF, not an embedding API.** KB search
(`retrieval/kb_index.py`) runs locally via scikit-learn, not by calling an
embedding service. Two reasons: it's fast to get right at this KB size with
no extra network dependency, and it means ticket text is never sent
anywhere just to find a matching doc -- a real point in favor on the data
sensitivity question in the design note.

**Structured output via forced tool calls, not prompted JSON.** Every
agent gets its output back as a schema-validated dict (`llm_client.py`'s
`call_structured`), not by asking the model to "return JSON" and
regex-parsing the response. This eliminates a whole class of parsing
failures (stray prose before the JSON, trailing commentary, malformed
brackets) at the source.

**Every quote in a Task 2 risk flag is checked in code, not asked of the
model twice.** `account_risk_extractor.py` verifies the model's claimed
quote is an exact substring of the source ticket body before it's trusted;
anything that doesn't verify is silently dropped. A model grading its own
possible hallucination is not a reliable check -- a plain substring
comparison is.

**Determinism comes from a cache, not from `temperature=0`.**
`task2_account_brief/pipeline.py` checks a hash-keyed cache before doing
any LLM work at all. This was a deliberate hedge that turned out to matter:
Gemini 3.x deprecated the `temperature` parameter mid-project, which would
have quietly broken Task 2's "must be deterministic" requirement if that
requirement had been resting on sampling parameters instead of a cache
layer.

## Setup

```bash
pip install -r requirements.txt --break-system-packages
cp .env.example .env
# edit .env and set GEMINI_API_KEY, and MODEL_NAME to a current GA model
# (e.g. gemini-3.5-flash) -- see .env.example for the default
```

## Run

```bash
# API
uvicorn main:app --reload

# Streamlit UI (separate terminal, run from the project root)
streamlit run app/streamlit_app.py
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

Or open `http://localhost:8000/docs` for FastAPI's interactive Swagger UI.

## Tests

```bash
pytest tests/ -v
```

Every LLM call is mocked at each agent's `call_structured` import site, so
this suite runs without an API key or network access. It checks pipeline
wiring -- does classification flow into response drafting, does a
hallucinated quote get rejected, does the cache key ordering behave, does
the eval harness's own scoring math behave -- not model output quality.
Verified in a genuinely clean, isolated venv (`python -m venv` +
`pip install -r requirements.txt` from scratch) to confirm the project runs
from a clean install, per the assignment's disqualifier list.

## Eval harness (Task 3)

```bash
python -m src.task3_evals.run_evals
```

Runs 6 hand-written test cases per task (5+ required, 1 adversarial each)
through the *real* pipeline -- this needs `GEMINI_API_KEY` set, unlike the
mocked pytest suite above. Writes `eval_report.json` and `eval_report.md`
to the repo root.

Scoring per case combines rule-based checks (schema/enum validity, does the
flagged-ticket set match expectations, is every quote verifiable against
the source ticket, is repeat output identical for the determinism case)
with one LLM-as-judge call scoring subjective quality (0-1) of the drafted
response or brief. A case passes only if every rule-based check passes AND
the averaged quality score clears 0.6.

Adversarial cases:
- Task 1, `T6-adversarial-caps-vs-impact`: a ticket with "URGENT!!!" in the
  subject over a trivial typo, testing whether the classifier is fooled by
  urgent-sounding language instead of reading actual business impact.
- Task 2, `A6-adversarial-no-tickets`: an account with zero tickets in the
  window, testing that incomplete data produces a graceful empty brief
  rather than a crash or a hallucinated risk.

`tests/test_eval_harness.py` verifies the harness's own scoring logic
(threshold math, error handling, report generation) with LLM calls mocked,
same pattern as `tests/test_smoke.py`.

**A note on ground truth**: if you're building eval cases from a provided
ticket dataset that ships its own `category`/`urgency` fields, check those
fields against the actual ticket text first -- in the dataset excerpt used
to spec this project, several fields didn't match ticket content (e.g. an
org-wide outage tagged as the lowest urgency tier). Scoring a classifier
against noisy dataset labels would penalize a good classifier for
disagreeing with bad labels. The cases here use hand-reviewed expected
outcomes instead.

## Design note (Task 4)

See [`DESIGN_NOTE.md`](./DESIGN_NOTE.md) -- failure modes, the latency vs.
quality trade-off in Task 1's two-call design, data sensitivity boundaries,
and what breaks first at 10x ticket volume.

## Project layout

```
src/
  llm_client.py        single wrapper around the Gemini API
  cache.py              flat-file cache, keyed by input hash (Task 2 determinism)
  schemas.py             shared pydantic models
  retrieval/kb_index.py   TF-IDF search over data/kb/**/*.md (category subfolders)
  agents/                 one file per LLM call -- edit these freely
    CHANGELOG.md                prompt version history (bonus: prompt versioning)
    triage_classifier.py       Task 1: classify ticket (PROMPT_VERSION = "v1")
    triage_responder.py        Task 1: route + draft response (PROMPT_VERSION = "v1")
    account_risk_extractor.py  Task 2: per-ticket risk flag + quote validation (PROMPT_VERSION = "v1")
    account_synthesizer.py     Task 2: brief synthesis (PROMPT_VERSION = "v1")
  task1_triage/pipeline.py     orchestrates the two Task 1 agents (no prompt logic)
  task2_account_brief/pipeline.py  orchestrates the two Task 2 agents (no prompt logic)
  task3_evals/                Task 3: eval harness
    judges.py                    rule-based checks + LLM-as-judge scorer
    cases_triage.json            6 hand-written Task 1 cases (1 adversarial)
    cases_account.json           6 hand-written Task 2 cases (1 adversarial)
    run_evals.py                 runs cases through the real pipeline, scores, reports
app/streamlit_app.py    thin UI over both pipelines (bonus)
.github/workflows/ci.yml  runs mocked tests always; runs the live eval harness
                            and uploads its report if GEMINI_API_KEY is set as
                            a repo secret (bonus: CI eval on every commit)
main.py                 FastAPI app mounting both pipelines
DESIGN_NOTE.md           Task 4 deliverable
```

## Data

`data/accounts.json` and `data/tickets_sample.json` are placeholders with
one fabricated account (`ACC-9999`, 3 tickets) so the pipeline is runnable
end to end out of the box. Replace them with the real starter dataset (500
tickets / 50 accounts) and update the two `load_json(...)` calls in
`main.py` (or generalize them to load full datasets and filter by account
+ a real 90-day window off `created_at`).

`data/kb/` is organized by category subfolder -- `billing/`, `onboarding/`,
`troubleshooting/`, and so on, matching however you actually organize the
real docs. The index walks every subfolder recursively (`kb_index.py`
globs `**/*.md`), so nesting is fine and expected; a `.md` file dropped
directly at the `kb/` root still works too, tagged `category: uncategorized`.
`doc_id` is the path relative to `data/kb/` (e.g. `products/cloudsync.md`),
so files with the same filename in different categories never collide.
Three placeholder docs are included (`billing/`, `onboarding/`,
`troubleshooting/`) so retrieval has something real to match against out
of the box.

