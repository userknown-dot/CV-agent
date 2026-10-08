# Mock interview: 30 questions, what they are really testing, and how to answer

Companion to `INTERVIEW_CHEATSHEET.md` (which holds the short factual answers). This one is for rehearsal: harder
questions, the traps, and what to volunteer before you are asked. All numbers are from the clean run on 2026-10-07.

---

## How 20+ minutes usually goes

| Minutes | What happens | What you control |
|---|---|---|
| 0-3 | "Tell me what you built" | Your 60-second opener. Rehearse it out loud. |
| 3-8 | Demo or screen share | Have the app already running and logged in. |
| 8-18 | Technical questions | The 30 below. |
| 18-22 | "What would you do differently / what's missing" | Your limitations list. Have it ready, do not improvise. |
| last 2 | "Any questions for us?" | The five at the end of this file. |

**The single best strategy for this project: volunteer the weaknesses before they find them.** You have real,
measured numbers and a written list of known gaps. Interviewers rate "knows exactly what is wrong with it" far above
"claims it is perfect". Every answer below is designed so the honest version is also the impressive version.

---

## 1. Opening: the 60-second answer

> **"Tell me about what you built."**

"A multi-user platform where logged-in users run AI agents over CVs and feedback. The two required agents are a CV
classifier that places a CV in one of nine categories with secondary categories and evidence quotes, and a feedback
sentiment agent. On top of that, every single LLM call is logged with the token counts that the provider itself
returns, and a dashboard shows tokens, cost, usage per user and per agent, error rates, acceptance rate and estimated
time saved.

The part I would point at first is the honesty of the numbers. Every call is written to an append-only raw log at call
time with the provider's own usage block, and a reconcile script compares that, call by call, with the database the
dashboard reads. On the last clean run that was 281 calls, 149,936 input and 50,241 output tokens, and it passes.
I also built a deliberately harder evaluation set, because my first set scored 100% and that told me nothing."

Then stop. Let them pick the thread.

---

## 2. Usage logging and honest metrics (the heart of this assignment)

**Q1. How do you know your token counts are correct?**
*Testing: did you estimate tokens, which the brief forbids.*
They come from the `usage` block of the provider's response, read in one LangChain callback. Nothing is estimated. If a
successful call ever came back without usage data, the row is flagged `usage_reported=false` and counted as zero, never
guessed. Across the last 281 calls there were zero such rows.

**Q2. Your reconcile script compares your own log with your own database. Both are yours. How do I know you aren't
consistently wrong in both?**
*Testing: do you understand the limit of your own evidence. This is the best question they can ask, and the one most
candidates fumble.*
"You're right, and I say so in the report. What it proves is pipeline integrity: the number the provider returned is
the number the dashboard shows, with nothing lost or double-counted in between. It does not prove the provider's
invoice agrees. To close that gap I would store the provider's response ID on every row. OpenRouter lets you look up
any call by that ID afterwards, so I could sample, say, 50 calls a day and compare against their records. That is the
one thing I would add next on the logging side."

**Q3. A call is retried. How does that appear?**
As a second logged call, because it is a second real API call that costs real money. That is also why I define a "run"
on the dashboard as one logged LLM call, and I state that definition on the dashboard itself.

**Q4. Your dashboard says cv_agent had a 13.6% error rate, but you also say every user request succeeded. Which is it?**
*Testing: can you explain a number that looks bad. Volunteer this before they spot it.*
Both. Those errors were my OpenAI key being rejected; the provider chain then fell back to OpenRouter and every user
request completed. So that figure is a per-provider-call error rate, not a per-user-request failure rate. It is
genuinely useful for spotting a dead key, which is exactly how I found this one, but it is the wrong number to put in
front of a product owner. The fix is a run ID per user action, so the dashboard can show both: requests that failed for
the user, and provider calls that failed underneath.

**Q5. What happens if the database write fails but the API call succeeded?**
Currently I would lose both the row and the raw log line, because the raw line is written second. That is a real gap.
The fix is one line of ordering: write the raw append-only line first, then the database. Then the reconcile script
catches the mismatch instead of both sides being silently consistent.

**Q6. How is cost calculated, and how wrong could it be?**
When the provider reports a real cost, which OpenRouter does on every call, I store that. Otherwise it is tokens times a
price table in config, verified against OpenAI's model page. Two known sources of error: the table goes stale, and I do
not apply the cached-input discount, so the estimate runs slightly high rather than low. I would rather over-estimate
spend than under-estimate it.

**Q7. What does one CV actually cost you?**
Measured, not guessed: one classification averages $0.000285. The full upload path is four calls (classify, HR review,
two role-fit calls) and comes to about **$0.0009 per CV**. At 10,000 CVs a day that is roughly **$9 a day, under $300 a
month**. One sentiment analysis with five votes is $0.0004. Those come straight from the usage log, which is the point
of building it.

---

## 3. Multi-user and concurrency

**Q8. Two users run agents at the same time. How do you know their logs don't mix?**
The usage logger is constructed per request from the authenticated user, so the user ID is captured before any call
starts; there is no shared mutable state to race on. SQLite runs in WAL mode so readers do not block the writer. The
demo script proves it end to end: alice and bob overlap from 21:03:24 to 21:03:47 and their totals come out separate
(63 and 64 calls).

**Q9. What breaks if you run two uvicorn workers?**
Little, by design. Budgets and rate limits are counted from the database, not from memory, so they hold across workers.
The raw log uses one `write()` per line, so appends do not interleave. What does not scale past one machine is SQLite
itself.

**Q10. Can a user exceed their token budget?**
Yes, slightly, and deliberately. The budget is checked before a call and the cost is known only after it returns, so
calls already in flight can overshoot by a few. Batches re-check per file so a runaway batch stops quickly. Making it
exact would need reservation-style accounting, which is not worth it at this scale.

**Q11. Where exactly do you enforce that a user cannot see another user's data?**
One helper, `scope_to_user`, wrapped around every per-user query: admins get all rows, users get a `where user_id = me`.
It is one function rather than a check scattered through each route, so there is one place to audit and one place to get
it wrong. The decision endpoint goes further and returns 404, not 403, on someone else's recommendation, so it does not
leak that the record exists.

---

## 4. The CV agent

**Q12. Why validate the model's output at all? You already use a JSON schema.**
Schema validity is not truth. The schema tells me the shape is right; it cannot tell me the model invented a quote. So
after the schema I run semantic checks: all nine category scores present, the primary must hold the top confidence, and
every evidence quote must actually be findable in the CV. That last one is what makes the output auditable.

**Q13. Your quote matching is fuzzy. Doesn't that let hallucinations through?**
*Testing: did you weaken a safety check for convenience and not notice.*
It was exact matching at first, and it failed on a real PDF because the model wrote "CI_CD" where the CV said "CI/CD",
which threw away an entire valid review. Now it matches on words, ignoring case, punctuation and line breaks, and it
tolerates a cut-off last word. Three things keep it honest: the passage must genuinely be in the CV, quotes under three
words must match exactly, and the text that gets stored and displayed is cut from the CV itself, never the model's
wording. So a user always reads the CV's own words.

**Q14. The confidence scores are 1.00 on almost every CV. Is that useful?**
No, and I would not call them probabilities. They are the model's own stated confidence, and there is published work
showing models are systematically overconfident when asked to verbalise confidence. On the hard set it averaged 98% on
correct answers and 90% on the one it got wrong, which is far too small a gap to be useful. Where I needed a confidence
I could defend, in the sentiment agent, I measured it instead: five independent runs, and the confidence is the share
that agreed on the label.

**Q15. Walk me through the prompt-injection defence, and then tell me how to beat it.**
*Testing: can you attack your own work.*
Four layers: invisible characters stripped and the CV wrapped in a random per-request tag; the system prompt stating
the CV is data; the evidence check; and a pattern scan plus the model's own flag. The pattern scan is the weakest, a
rephrased attack walks past it. The evidence check is the real barrier, because a hijacked answer cannot cite genuine
CV evidence for the attacker's chosen category. Result: five attack CVs, zero hijacked, all five flagged.
How to beat it: don't inject, just lie. Pad the CV with plausible, well-written bullet points about the role you want.
The quotes are then real and the check passes. No output validation catches that, it is a reference-checking problem,
not a prompt-injection one.

**Q16. Hidden white-on-white text in a PDF?**
A text extractor cannot see colour, so it comes through as ordinary text and goes through the same defences. I tested
that specific case with a generated PDF.

**Q17. Why LangGraph for a flow this small?**
It is prepare, classify, validate, then one conditional edge to either finish, retry once, or fail. The honest answer
is that a `for` loop would also do it; the graph makes the retry path explicit and inspectable, and it was a stated
requirement. I would not reach for it on something this size otherwise.

---

## 5. Evaluation (expect the hardest pushback here)

**Q18. You report 100% precision and recall. Do you believe that?**
*Testing: statistical honesty. The right answer is no.*
"No, and that number is in the report mainly as a warning. Those CVs are synthetic, and the job title at the top names
the category, so the task is almost trivial. A model that scores 100% there has told me nothing about real CVs. That is
why I built a second, harder set."

**Q19. What makes the hard set harder, and what did it find?**
Neutral job titles, so "Analyst" or "Software Engineer" instead of "Mobile QA Automation Engineer". Eight mixed CVs
with a genuine secondary category. And eight near-miss profiles labelled Other that borrow a category's vocabulary
without doing the job: DevOps, manual QA, data analyst, UX designer, technical writer and so on. Result: 39 of 40
correct, 98%. All eight near-misses were correctly rejected as Other, which is the result I cared about most.
The failure it exposed is secondary categories: the expected secondary was returned on only **5 of 8** mixed CVs. That
is the number I would work on next.

**Q20. Your hard set is still written by you. Isn't that the same problem?**
Yes, and I say so. I wrote both the CVs and the labels, so I cannot have been surprised by them in the way real data
surprises you. The genuinely convincing version is 20 to 30 real anonymised CVs labelled by someone who screens for a
living, ideally two people so I can report how often they agree with each other. Model accuracy means very little if
two humans only agree 80% of the time.

**Q21. What is your baseline?**
*Testing: do you know whether the LLM is earning its cost. Most candidates have no answer.*
"I don't have one, and that is a gap. The right baseline is a keyword or TF-IDF classifier over the same categories.
These nine categories are heavily keyword-driven, Selenium, Appium, Amadeus Altea, so a simple classifier might get
most of the way for zero cost and zero latency. If it does, the honest conclusion is that the LLM earns its place on
the evidence quotes and the rationale, not on the label. I would want to know that before recommending this to anyone."

**Q22. Your demo shows a 50% acceptance rate. What does that tell you?**
Nothing about quality. The demo script hard-codes accept, modify and reject, so that figure measures my script. I label
it as scripted on the dashboard write-up. A real acceptance rate needs real recruiters deciding, and that is the metric
I would actually watch in production.

---

## 6. Security and data protection

**Q23. What is the worst security problem in this codebase right now?**
*Testing: self-awareness. Have a ranked answer ready.*
"Right now, three things, in order. One: there is no throttling on the login endpoint, so passwords can be guessed as
fast as the network allows. Two: there is no `.dockerignore`, so building an image would copy my `.env` and the database
into it. Three: the CV text is stored as personal data with no retention or deletion policy. The one I already fixed
was the worst: the token signing secret was still the example placeholder, which means anyone reading the repo could
have signed themselves an admin token. The app now refuses to start unless that secret is set properly."

**Q24. Why does the app refuse to start rather than warn?**
Because a warning in a log is a warning nobody reads. A broken login that fails loudly on the first run costs a
developer thirty seconds; a placeholder secret that ships silently is a full compromise of every account.

**Q25. You store the CV text. Is that a problem?**
It is personal data, so it needs a reason and a lifetime. The reason is that the HR review, the feedback generator and
the role-fit scoring all need the text after classification. The lifetime is what is missing: no retention period, no
deletion endpoint, no candidate-facing notice. For a demo that is acceptable if stated; for anything real it is the
first thing to fix, along with encryption at rest.

---

## 7. Product judgment (these separate candidates)

**Q26. Would you let this screen real candidates?**
*Testing: judgment. This is the question that decides a lot of interviews.*
"As decision support with a person making every decision, yes. As an automatic reject filter, no, and I built it so
that is hard to do by accident. The HR review deliberately gives no hire or no-hire verdict; it gives reasons to
consider, points to verify and concerns, each with a quote from the CV so the recruiter can check it in seconds. The
role-fit score is defined as the share of a checklist the CV can *prove*, which is a statement about the document, not
about the person. A thin CV from a strong candidate scores low, and that is the correct behaviour for a tool that
measures evidence."

**Q27. Where could this be biased, and what did you do about it?**
Two layers of answer. What I did: the review prompt is told not to use protected characteristics, and the output is
rejected if it mentions age, gender, nationality, health and so on. What that does not fix: the underlying model
carries whatever bias is in its training data, and name-based and school-based bias in CV screening is well documented.
I have not tested for it. The test I would run is straightforward: take the same CV, vary only the name, and check
whether the category, the role-fit score or the review wording moves. If it does, that is a blocker, not a backlog item.

**Q28. This is employment screening. Any regulatory concern?**
Yes, and it is worth knowing the specifics. The EU AI Act's Annex III lists AI used to screen or filter job
applications and evaluate candidates as high risk. New York City's Local Law 144 goes further operationally: if an
automated employment decision tool substantially assists a hiring decision, you need an independent bias audit within
the past year, a published summary of it, and ten business days' notice to candidates with a route to an alternative
process.
That shapes the design directly: keep a person making every decision, so the tool assists rather than decides; keep an
audit trail of who decided what and why, which is what the decisions table is; and be able to explain any single
output, which is what the evidence quotes are for. The bias audit itself is the piece I have not done.

**Q29. You were asked for two agents and built five. Why should I not read that as scope creep?**
Fair challenge. The two required agents are the classifier and the sentiment agent, and they are complete. The other
three exist because a category label alone does not help a recruiter decide anything, so the HR review and the role-fit
score turn a label into something actionable. The cost is honest: four LLM calls per CV instead of one, and I can show
the exact figure, $0.0009 per CV. If that trade were not worth it I would turn role fit off, and there is a setting for
exactly that.

**Q30. One thing you would rebuild from scratch?**
The run accounting. I treated one LLM call as the unit of work from the start, and it was the wrong unit. A user action
is the thing people care about, and it can be one call or eleven. Every metric downstream, runs per day, error rate,
latency, inherited that choice, and retro-fitting a run ID now touches five agents. If I started again, every agent
entry point would mint a run ID in the first line and every call would carry it.

---

## Five questions to ask them

1. "Who would actually use this day to day, and would they be allowed to make the final call on a candidate, or would
   they want the tool to filter first?"
2. "Do you have historical screening decisions I could evaluate against? That is the difference between my 98% on
   synthetic CVs and a number anyone should trust."
3. "What is your retention policy for candidate data? That changes how I would store the CV text."
4. "Would this run on your own infrastructure, or is a hosted model API acceptable? That decides the whole provider
   layer."
5. "If you have an existing screening process, where does it hurt most, volume, consistency or defensibility?"

---

## If the demo breaks

- **Nothing responds:** `uvicorn app.main:app` in a fresh terminal. Keep the terminal visible; a restart in ten seconds
  looks competent.
- **Every AI call errors:** a key expired. Say so, say the fallback chain exists exactly for that, show the "Calls by
  model" table, and carry on with the dashboard and the stored results, which need no API.
- **A CV classifies oddly:** good. Open the evidence quotes and talk through why the model saw it that way, then record
  a Modify with a reason. That is the human-in-the-loop story demonstrating itself.
- **Anything you cannot explain:** "I don't know, let me check" and then actually look. It beats a confident guess every
  time, and this project gives you a log to look in.
