# Assignment 2 report: Multi-user agent platform

Fill the bracketed parts with your real numbers. Paste outputs, do not retype them.

## 1. Architecture
[Paste the architecture diagram. One paragraph: FastAPI + SQLite, LangGraph agents, one usage callback, JSONL audit log, single-page UI.]

## 2. Authentication and roles
- bcrypt password hashes, JWT bearer tokens, identity read only from the token (never URL or body).
- Roles: `admin` sees all users' usage, results and dashboard data; `user` sees only their own.
  Enforced by one helper (`scope_to_user`) used by every per-user query.
- Evidence: [tests/test_usage_logging.py::test_api_scoping_user_vs_admin, tests/test_decisions_dashboard.py]

## 3. CV agent
- Graph: prepare -> classify -> validate -> retry once -> finalize. Schema: `GET /cv/schema` [paste JSON Schema].
- Output: primary, secondary, confidence per category (9), rationale, verbatim evidence.
- Decisions stored with user, original recommendation, final decision, reason (mandatory for modify/reject), timestamp.
- Batch upload with progress (job table + polling endpoint).

## 4. Prompt-injection defence
Describe the four layers (see README) and what each one stops. Be honest that the regex layer is weak and
the evidence check is the real barrier. Results: [paste the "Prompt-injection CVs" table from eval/out/report.md].

## 5. Usage logging and dashboard
- One callback logs every LLM call (timestamp, user, agent, model, input/output tokens, latency, status, cost).
- Tokens come from the provider's response (`usage` block), never estimated; a call with no usage data is flagged.
- Definitions: run = one logged LLM call (retries count); acceptance rate = accepted / (accepted + modified + rejected);
  latency = mean over all calls.
- Time saved: [state the assumption values from .env] and the rule (accept = full gain, modify = x0.5, reject = -review time, pending = 0).
  This is an estimate from assumptions, not measured time.
- Imported-log tab: [describe the file you imported and the column mapping used].

## 6. Evaluation
### 6.1 Classification accuracy
[Paste the per-category table from eval/out/report.md. State the dataset: N CVs, synthetic or real, how labelled.]

### 6.2 Logging accuracy
[Paste the output of `python -m scripts.reconcile --sample 20`, showing per-call raw vs database tokens and PASS.]

## 7. Multi-user demonstration
[Paste the output of `python -m scripts.demo_multiuser` (overlapping alice/bob timestamps) and a dashboard screenshot as admin
and as a normal user.]

## 8. Limitations and future work
[Examples: synthetic test set, only .txt/.md input, SQLite, regex injection layer is weak, no PDF parsing, cost uses a price table.]
