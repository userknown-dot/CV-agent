# Project status and remaining work

Updated 2026-10-07, after the security fix, the data reset and a clean re-run of the demo, both evaluations and the
reconcile check. Results are in REPORT.md; evidence in `eval/out/`.

## Status against the assignment
Every requirement is built and was run with real API calls (REPORT.md section 0 maps each one to its evidence).

## Done in this round
- `JWT_SECRET` replaced with a 64-character random value; the server now refuses to start with an empty, placeholder
  or short secret, and `.env.example` no longer ships a usable value.
- Sentiment analyses real feedback again (paste or .txt / .csv upload); AI sample feedback is stored separately and is
  never counted in time saved. Injection flag uses a majority of runs (one sampled run flagged ordinary feedback before).
- External-log import: paste or upload, automatic column detection, clear errors; the raw usage log now carries a
  timestamp on every line.
- Data reset (old data kept in `data/backup-2026-10-07-before-reset/`), then a clean demo, evaluation and reconcile run.
- New hard evaluation set with multi-label scoring; README, REPORT and the interview cheat sheet rewritten.

## Still open, in order of value
| Item | Why it matters | Who |
|---|---|---|
| **Fix or remove the OpenAI key** | It is being rejected, so every call first fails on OpenAI and then falls back; this is the whole dashboard error rate. Either put a working key in `.env` or set `LLM_PROVIDER=openrouter`, then restart | You |
| **Rotate the OpenAI and OpenRouter keys** after submitting | They have been handled in several places | You |
| **Never send `.env`** with the project; add a `.dockerignore` | `COPY . .` in the Dockerfile copies `.env` and `data/` into any image | Me (small) / you |
| **Per-action run IDs** | The dashboard counts LLM calls as runs (5 per sentiment, 2 per role fit, plus fallback attempts) and its error rate is per provider call. A run ID per user action would show runs and user-facing failures separately | Me (medium) |
| **Real anonymised CVs** (10-20, labelled by you) | The strongest possible evidence for the evaluation | You |
| **Secondary categories** | Found for 5 of 8 mixed CVs; worth a prompt change and a re-run | Me (medium) |
| Raw log line before the database row; cached-token pricing; store the provider's response ID | Stronger logging guarantees and an independent audit path | Me (small) |
| Login throttling, pinned dependency versions, restrict `/dev/*` endpoints | Hardening | Me (small) |
| A retention policy for stored CV text | It is personal data | Design decision |

## Before the interview
1. Fix the OpenAI key or switch to OpenRouter only, restart, and if you want error-free screenshots re-run
   `python -m scripts.demo_multiuser` after another reset.
2. Do the practice run at the end of `docs/INTERVIEW_CHEATSHEET.md` once.
3. Take screenshots: admin overview, alice's dashboard, a CV card with evidence and role fit, the feedback table, the
   imported tab, the reconcile PASS.
4. Submit without `.env`; attach `eval/out/` because `data/` is git-ignored.
