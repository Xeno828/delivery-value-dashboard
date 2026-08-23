# Delivery reporting & forecasting agent — design outline

> **Status:** outline plus a working implementation of the deterministic half.
> `agent/SKILL.md` runs today; `agent/tools/` is tested and backtested.
> The open decisions are listed at the end.

---

## 1. The split, and why it is not negotiable

"Reporting and forecasting" sounds like one job. It is two, with opposite failure modes, and merging them destroys both.

| | Reporting | Forecasting |
|---|---|---|
| Question | What happened? | What will happen? |
| Right answer | Exactly one | A distribution |
| Failure mode | A wrong number | A confident number |
| Who should compute it | Code | Code |
| What the agent adds | Narrative, change detection, framing a decision | Interpretation, assumption disclosure, refusal |

The agent is a **narrator and an interpreter, never a calculator**. It calls `metrics.py` for facts and `forecast.py` for probabilities and writes prose around what they return.

This is not modesty about language models. It is that:

- A report is only worth reading if the same question asked twice gives the same answer.
- A wrong figure must be traceable to one line of code and fixable once, for everyone.
- The moment the agent computes a percentage itself, nobody can audit the report, and its entire value is gone.

The rule is enforced structurally, not by instruction: the tools emit the numbers, the agent quotes them, and the tests assert the tools agree with the dashboard.

---

## 2. The question inventory

The dashboard is the specification. Every card on it is a question someone asked, and the agent's job is to answer all of them in prose plus the ones a dashboard structurally cannot answer.

### Answerable from a single snapshot — reporting

| Question | Dashboard source | Tool output |
|---|---|---|
| How much is done, in items and points? | Delivered tile | `delivery.*` |
| Are we ahead of or behind the calendar? | Pace-vs-clock tile | `delivery.pace_gap_pts` |
| Did scope change after we started, and by how much? | Burndown scope line | `scope.*` |
| What is blocked, and by whom? | Blocked tile, risk register | `risk.blocked` |
| What is overdue against a date we promised someone? | Past-due tile | `risk.overdue` |
| How old is the open work? | Ageing chart | `risk.age_bands` |
| How much of elapsed time is queueing rather than working? | Waiting-vs-working chart | `flow.flow_efficiency` |
| Was the commitment realistic? | Predictability chart | `predictability.*` |
| What did we deliver that is worth something, and on what basis? | Value card | `value.*` |
| How safely are we shipping? | DORA card | `dora` |

### Answerable only across snapshots — **the gap the dashboard cannot fill**

A dashboard shows a state. A report is about *change*, and the current dataset keeps no history of state, only of outcomes.

| Question | Needs |
|---|---|
| What changed since the last report? | `metrics.diff` over a stored facts pack |
| Is a risk new, persistent, or cleared? | The same |
| Is this getting better or worse, or just noisy? | 6+ stored facts packs |
| How often does scope grow mid-sprint, and by how much? | `snapshots/scope.json` |
| Were our previous forecasts any good? | `snapshots/forecast-log.json` |

**This is the single largest piece of new work.** Without a snapshot archive the agent can only ever restate the dashboard in sentences, which is worth nothing.

### Answerable only probabilistically — forecasting

| Question | Method |
|---|---|
| Will all outstanding work land by the sprint end? | Monte Carlo over item throughput → probability against that date |
| If not by then, by when? | Same → 50th / 70th / 85th / 95th percentile dates |
| How much *will* land by the date? | Monte Carlo → "at least N items with P confidence" |
| Which specific items are unlikely to make it? | Empirical cycle-time percentiles per item |
| Will release v2.2.0 be complete on time? | Monte Carlo on that release's remaining scope |
| What should we commit to next sprint? | Monte Carlo over a simulated sprint → **items** at 85% confidence |
| Is item counting still valid for this team? | Cycle-time drift and spread across the window |

### Deliberately *not* answered

| Question | Why not |
|---|---|
| Who is the most/least productive? | Throughput is a property of the system, not the person. The data cannot support the claim and the report gets banned the first time it makes one. |
| Will this specific unstarted item take N days? | An item never picked up has no cycle time to sample. It is a scheduling question. |
| What will the business value be? | Value estimates are unvalidated inputs. Forecasting on top of them compounds an error rather than measuring one. |
| How many story points next sprint? | Six sprints is six point-observations, which cannot support a distribution. Commitments are recommended in items. See §5. |

---

## 3. Architecture

```
   Jira / Asana ──▶ fetch_delivery_data.py ──▶ dashboard-data.json
                                                     │
                          ┌──────────────────────────┼──────────────────────────┐
                          ▼                          ▼                          ▼
                    metrics.py                 forecast.py               the dashboard
                  (facts pack)             (Monte Carlo, seeded)        (same data, browser)
                          │                          │
                          └───────────┬──────────────┘
                                      ▼
                            THE AGENT  (agent/SKILL.md)
                       narrates · diffs · frames the decision
                              never computes a number
                                      │
                    ┌─────────────────┴─────────────────┐
                    ▼                                   ▼
          reports/exec-brief-<date>.md        reports/team-report-<date>.md
                    │
                    └──▶ snapshots/  facts-<date>.json · forecast-log.json
                              (feeds next week's diff and calibration)
```

Read-only against the trackers, by decision. The agent publishes documents; it never writes to Jira or Asana. That is the version worth trusting first, and the one that cannot cause an incident.

---

## 4. Data contract

Reuses the dashboard's schema unchanged (`docs/data-format.md`), including the `orgConfig` block — which statuses mean done, the working week, the holiday calendar and the sprint length. The tools read it **from the dataset**, never from a config file of their own, so a facts pack and a forecast built from one file cannot be computed under two different calendars. Full reasoning in `docs/organisation-config.md`.

Three additions on top of the schema:

```
snapshots/
  facts-2026-08-10.json      # a full facts pack, written on every run
  scope.json                 # per-sprint committed vs added item counts
  forecast-log.json          # every published probability + its resolution
```

`forecast-log.json` entries:

```json
{ "issued": "2026-08-10",
  "label": "all 10 outstanding items complete by 2026-08-14",
  "probability": 0.04,
  "resolves_on": "2026-08-14",
  "resolved": null }
```

`resolved` is filled by the next run after `resolves_on`. Without this file the agent is unfalsifiable, and an unfalsifiable forecaster is a horoscope.

### Reporting scope is not forecasting scope

The facts pack counts **only the period being reported on** — an issue is in scope unless it was already finished before the period began. The forecaster sees **everything in the file**, because a throughput distribution needs months of history to exist at all.

Conflating them is a real error, not a rounding one: feeding the forecaster's twelve-week file to the reporter without this rule produced *"89% complete"* on a report about a sprint that was 55% complete. `tests/test_agent.py` now pins the two files to identical delivery figures.

### A unit rule worth writing down

Two tools built on one dataset will disagree unless this is explicit:

- **Reported elapsed time is in calendar days.** An item raised 21 days ago is 21 days old. Telling a stakeholder it is 15 because of weekends is a lie of convenience.
- **Simulated time is in working days.** No work completes on a Saturday.

Every figure the agent emits carries its unit. This was found by a test asserting the facts pack matched the dashboard — the two disagreed on flow efficiency (25% vs 22%) purely on this, and would have disagreed in a meeting.

**Which days are working days is now configurable, and the rule above is what keeps that safe.** The working week and the holiday calendar come from `orgConfig` and shorten *simulated* time only; a holiday never shortens an item's age. Both tools state the calendar they used — `meta.calendar` and `inputs.calendar` — so a report can name it rather than leaving the reader to assume Monday to Friday.

One consequence worth anticipating in a report: **shortening the working week shortens the throughput sample**, and a team that had just enough completion history under five days can fall under the refusal threshold under four. The right output there is the refusal, not a thinner forecast. Print it verbatim as always.

---

## 5. Forecasting method

**Monte Carlo over historical item throughput.** For each of 20,000 trials, sample daily completion counts from history until the outstanding work is consumed; the distribution of trial lengths gives the percentiles.

**Items, not story points.** Six sprints of history is six point-observations, and six observations cannot support a distribution. The same six sprints contain roughly sixty completed items; counted per working day that is thirty to sixty observations. Item counting also sidesteps estimate inflation entirely, since it never reads an estimate.

Design decisions that matter:

- **Zero-throughput days are kept in the sample.** Dropping them is the most common way a Monte Carlo turns optimistic — real teams have days where nothing finishes, and a model that never samples zero will never predict a stall.
- **A fixed seed.** Same inputs, same answer, every time. A forecast that moves when nothing changed is not a forecast.
- **Scope growth is sampled too,** from `scope.json`. On the sample data this moves the sprint-end probability from 4% to 0% and the 85th-percentile date from 24 to 26 August. If no scope history exists, the forecast assumes frozen scope — which never happens — and the agent must say so in the same sentence as the number.
- **The recommendation is in items too.** Forecasting in items and then recommending a commitment in points is the same inconsistency wearing a different hat. `recommend_commitment` simulates thousands of sprints and returns the **85%-confidence item count**. Not the median: committing at the median means missing the commitment half the time by construction, and a team that misses half its commitments stops being believed regardless of what it delivers. On the sample data that is 11 items, against a median of 14.
- **Ageing risk is reported on two clocks.** An item whose *active* time is normal but whose *end-to-end* time is past the 85th percentile is not a team problem: the delay is upstream, in the queue before work started. That distinction is the finding, and collapsing it into one number destroys it.

### The one real weakness of item counting, and the guard for it

Counting items assumes items are roughly interchangeable in size. That assumption breaks in a specific, detectable way: a team starts splitting work smaller, throughput rises, and the forecast reads it as the team getting faster. Nothing got faster. The unit shrank.

`size_stability` checks two things over the window:

1. **Drift** — median cycle time in the earlier half versus the later half. A fall of 30%+ *combined with* a throughput rise of 20%+ means splitting, not speed. Either alone is fine: cycle time falling with flat throughput is a genuine improvement, and the check deliberately does not flag it.
2. **Spread** — p85 ÷ p50 of cycle time. Above roughly 4, items vary so widely that one is worth several of another and counting them treats those as equal.

On the sample team: spread 2.33, no drift warning — item counting is safe. On a synthetic team that halves its item size and triples its throughput, the check fires with both warnings. Both cases are pinned in `tests/test_agent.py`.

If `safe_to_count_items` is false the agent must quote the warning and mark forecasts provisional. It does not silently switch back to points — points would be worse, not better.

### Refusal thresholds

Below these, the honest answer is "not enough data" — not a wider interval:

| Guard | Threshold |
|---|---|
| Completion forecast | ≥ 10 completed items and ≥ 8 day-observations in the window |
| Cycle-time / ageing risk | ≥ 6 items with both a start and an end date |
| Calibration score | ≥ 10 resolved forecasts |

On one sprint of data the engine refuses outright — verified in `tests/test_agent.py`. The agent must print the refusal verbatim rather than softening it into a hedge. *"Not enough data"* and *"wide interval"* are different statements and only one of them is true.

---

## 5b. Forecasting work that does not exist yet — product intake

Everything above forecasts work already in the tracker. The portfolio decision that actually costs money is made earlier than that: an ask has been described, no ticket exists, and it has to be sequenced against everything else anyway.

`agent/tools/intake.py` handles that case on the same terms as the rest — deterministic, seeded, and refusing rather than guessing. Full detail in [product-intake.md](product-intake.md); the parts that belong in this outline:

**Sizing is a ladder, and the rung is always declared.** `tshirt` uses bands calibrated from the board's *own* completed epics (an "L" is not portable between teams, so it is derived per board and refused below eight completed epics). `reference-class` samples every completed epic. `explicit` takes a refined min/likely/max as a triangular distribution. Each prints its own caveat verbatim.

**Two scenarios, always both.** *Earliest possible* — dedicated capacity, nothing queued — is a ceiling, not a plan. *Realistic* queues the ask behind committed unfinished work and thins throughput by the board's measured interruption rate. Interruption is modelled as a thinned throughput series rather than a multiplier on the final date, so its variance survives into the percentiles. The difference between the two is reported as **the cost of the existing queue in working days**, which is the number to quote when someone asks why it cannot start now.

**Uncertainty is attributed, not just stated.** Three simulations — both inputs varying, size frozen, throughput frozen — split the spread between *not knowing how big this is* and *normal delivery variability*. That distinction is the whole point: the first sends the ask back to refinement, the second says the estimate was never the problem and stops a team being told to tighten it up. On the demo data a vague ask attributes 54% to size and the same ask refined attributes 10%.

**A readiness gate runs first.** `title`, `team` and `sizing` are required or nothing is forecast. The rest are reported as gaps with their consequence stated, because the failure mode of any intake tool is making an unchallenged ask look processed.

**Sequencing returns consequences, not a score.** Every ordering is evaluated for what it costs the other asks, and anything that misses its date *in every possible ordering* is reported first and separately — that is the conversation that otherwise happens six weeks late. **No WSJF, no weighted score, nothing of that family.** Those formulas multiply an unvalidated value estimate by an unvalidated size estimate and present the product as arithmetic; the delivery consequence of an ordering is computable and is returned, the relative worth of the asks is a judgement and is left with the people who own it.

The intake-specific refusal thresholds sit alongside the ones above:

| Guard | Threshold |
|---|---|
| Reference class | ≥ 5 completed epics on the board |
| T-shirt scale | ≥ 8 completed epics (four bands cut from seven observations is noise) |
| Explicit sizing | `minItems ≤ likelyItems ≤ maxItems`, all present |
| Sequencing | ≥ 2 sizeable asks |

---

## 6. Guardrails

1. **Never compute.** Every figure comes from a tool.
2. **Never a single date.** Percentiles or nothing.
3. **Lead with the probability against the date already in the reader's head.** "There is a 4% chance all ten items land by the 14th" changes a decision; a percentile table alone does not.
4. **Every claim carries an evidence tag** — `[measured]`, `[derived]`, `[forecast p85]`, `[judgement]`. Three consecutive judgements means the section is an opinion piece; cut it.
5. **Never attribute throughput to a person.**
6. **Never recommend working longer or harder.** There is no hours data in this system, by design. Rising work in progress means the plan is wrong; rising unplanned work means intake is. Neither means the team is.
7. **Movement is the news.** If nothing moved, the report is one line saying so and whether that is concerning — not a restatement.
8. **Stale data is the first line, not a footnote.**
9. **Score yourself in public.** The exec brief footer carries the running Brier score. Above 0.20, stop publishing probabilities in the body and say why.
10. **Never rank asks.** The delivery consequence of an ordering is computable and must be given. The relative worth of competing asks is not, and a score that multiplies two unvalidated estimates launders a judgement rather than improving it.
11. **An intake figure is never a commitment.** A t-shirt forecast is an intake-stage estimate that is expected to move at refinement. If it is quoted without that sentence attached, the sentence was the part that mattered.

---

## 7. Outputs and cadence

| Artefact | Audience | Cadence | Length |
|---|---|---|---|
| `exec-brief-<date>.md` | Decision-makers who don't attend stand-up | Weekly + at sprint end | **< 400 words**, one decision requested or an explicit "nothing needed" |
| `team-report-<date>.md` | The delivery team | Daily or every other day | As long as needed, specific issue keys throughout |
| `intake-<ask-id>.md` | Product, the requester, whoever sequences the queue | On each new or re-refined ask | One page, both scenarios, uncertainty attributed |
| `facts-<date>.json` | The next run | Every run | — |

Two documents, never one with a summary bolted on. An exec brief that never asks for anything trains people to stop opening it; a team report written for executives is useless at stand-up.

Worked examples generated from the sample dataset: [`agent/examples/exec-brief-2026-08-10.md`](../agent/examples/exec-brief-2026-08-10.md) and [`agent/examples/team-report-2026-08-10.md`](../agent/examples/team-report-2026-08-10.md).

Delivery: files first. Optionally Slack/email later, gated on the calibration score being acceptable.

---

## 8. Failure modes

| Failure | Why it happens | Mitigation |
|---|---|---|
| Agent invents a number | It can do arithmetic, so it will | All figures from tools; tests assert tool/dashboard agreement |
| Forecast is confidently wrong | Thin data stretched into a range | Hard refusal thresholds; refusal printed verbatim |
| Forecast is optimistic | Zero-days dropped; scope assumed frozen | Zeros kept; scope sampled; assumption stated inline |
| Report is ignored | It restates the same state weekly | Diff-driven; nothing-moved is one line |
| Report is distrusted | It disagrees with the dashboard | Shared dataset, unit rule, agreement test |
| Agent becomes a performance-management tool | Per-person data exists | Prohibited outright; ownership counts only, no ranking |
| Forecasts drift and nobody notices | Nobody scores them | Forecast log + Brier score published in the brief |
| Backtest flatters the model | Overlapping windows, truncated horizons | Non-overlapping windows only; short horizons excluded |
| An intake estimate hardens into a commitment | A number in a document outlives its caveat | Caveat printed verbatim with every figure; both scenarios always; re-run required after refinement |
| A forecast is built against the wrong slice | Board selected, but as-of taken from the board's *earliest* sprint | `board_issues()` returns the most recent context; `tests/test_agent.py` asserts the throughput window contains real delivery |

---

## 9. Evaluation

**Backtest (implemented).** Walk forward through history with non-overlapping five-working-day windows, forecasting from data available at each cutoff only. Coverage against nominal:

| Percentile | Nominal | Observed |
|---|---|---|
| 50% | 50% | 50% |
| 70% | 70% | 67% |
| 85% | 85% | 83% |
| 95% | 95% | 100% |

Six independent windows. That is a smoke test that the forecaster is not wildly miscalibrated, **not** a calibration proof — n is small. Real calibration comes from scoring published forecasts in production.

Two methodological points, because both were caught failing during development and both make a forecaster look better than it is:

1. Only score a cutoff with a full horizon of real data after it. Otherwise the actual count is truncated by the file ending, not the team, and everything looks optimistic. An earlier run reported 38% coverage at p50 purely from this.
2. Never overlap horizons. Sliding a window forward two days gives ten trials that are really one; a single slow fortnight is counted ten times.

**Ongoing.** Brier score over the forecast log, bucketed to show over- versus under-confidence. Target ≤ 0.12; above 0.20 the agent stops publishing probabilities.

**Qualitative.** The only test that matters: *did a reader make a different decision because of this report?* Ask three readers monthly. If the answer is consistently no, the reports are wallpaper regardless of their accuracy.

---

## 10. Rollout

| Phase | Scope | Exit criterion |
|---|---|---|
| **0. Shadow** (2 sprints) | Agent runs, nobody reads it. Snapshot archive fills. | 6 facts packs stored; forecast log has 10+ resolved entries |
| **1. Team report only** | Published to the team channel | Team says it changes what they do at stand-up |
| **2. Add the exec brief** | Weekly | Brier ≤ 0.20; one reader confirms a decision was informed by it |
| **3. Automate** | Cron, daily team / weekly exec | Two sprints with no correction needed |
| **4. Reconsider write access** | Only then | A track record exists to justify it |

Do not start at phase 3. A forecasting agent with no calibration history is a confident stranger.

---

## 11. Open decisions

1. **Snapshot retention.** Facts packs contain issue titles. How long do they live, and where? (Recommendation: 12 months, same repo, private.)
2. **Holiday calendar.** Both tools exclude weekends only. Team holidays will make forecasts optimistic around Christmas.
3. **Multi-team scope.** Everything here is single-team. Portfolio roll-up needs a different unit of analysis and a different brief — do not bolt it on.
4. **Delivery channel.** Files now. Slack later, gated on calibration.
5. **Value reconciliation.** The 90-day estimate-vs-actual loop is a process the agent can prompt for but cannot perform. Someone has to own it.
6. **Who receives the "nothing needed from you" brief?** If the answer is "a distribution list nobody curated", fix that before automating anything.
