# Delivery Reporting & Forecasting Agent
### Executive summary

---

## The problem it solves

Delivery reporting today costs a delivery manager a day a fortnight and produces a document that answers the wrong question. It says what happened. Leadership needs to know **what will happen, what it will cost, and what decision is needed this week**.

Three specific failures show up in almost every sprint report:

1. **"Behind schedule" is reported without saying why.** A team that was given 22% more work mid-sprint and a team that is genuinely slow produce identical-looking reports. Those need opposite responses.
2. **Forecasts are single dates, and single dates are wrong.** "We'll finish on the 14th" carries no probability, so nobody can price the risk of it slipping.
3. **Nothing is falsifiable.** Last quarter's forecasts are never scored, so the forecast has no track record and is treated as opinion — correctly.

## What it does

Every weekday it reads the delivery data and produces two documents:

| Document | Audience | Answers |
|---|---|---|
| **Executive brief** — under 400 words | Leadership | Will we make it, what changed, what it is worth, what decision is needed |
| **Team report** | The delivery team | What to unblock, what is ageing, where the queues are, what to commit to next |

Same facts, two documents — never one with a summary bolted on top.

It also answers the question that arrives **before** any of the work exists. Given a described product ask and a named team, it produces an **intake brief**: how big the ask looks against how that team's past work actually turned out, when it would land if it were the only thing they touched, when it would land queued behind everything already committed, and — the part with no equivalent in a normal estimate — whether the uncertainty is coming from not understanding the ask or from normal delivery variability. One tells you to send it back to refinement. The other tells you the estimate was never the problem.

## The value, in the terms it will be judged on

**Time.** Roughly a day per fortnight per team of manual report assembly, returned. At five teams that is an FTE-half.

**Decisions made earlier.** On the sample sprint the agent states there is a **0.7% chance** the sprint lands complete on time, with an 85th-percentile finish three weeks later. That conversation currently happens on the last day of the sprint. This moves it to the middle, when scope can still be changed.

**Commitments that hold.** The team in the demo committed 18 items against a three-sprint average of 10 — an 80% over-commitment that guaranteed a "failed" sprint regardless of effort. The agent sizes the next commitment from a distribution over 20,000 simulated sprints and recommends the **85%-confidence figure**, not the median. A team that hits its commitment is worth more to a business than one that occasionally exceeds it and usually misses.

**Prioritisation with the delivery consequence attached.** Given several asks against one team, it reports what each ordering costs the others in working days, and names anything that misses its date *in every possible ordering* — the conversation that currently happens six weeks late, when the only remaining lever is the date. On the demo data it flags a fixed-deadline compliance ask as 25 working days short at best case, before a single ticket has been written.

**A finding worth real money.** Across the demo boards, **32% to 67% of elapsed time is active work** — the rest is queueing, waiting for a review or a decision. Queue time is the cheapest delivery improvement available and almost nobody measures it. The report puts a number on it every week and names the queue.

**Credibility.** Every figure traces to an issue key. Every published probability is logged and scored. The brief carries its own calibration score in the footer, and if that score degrades the agent **stops quoting probabilities** and says why.

## How it works

```
Jira / Asana ──▶ data file ──▶ metrics.py    (the facts)
                          └──▶ forecast.py   (the probabilities)
                                    │
                                    ▼
                              THE AGENT
                    reads · compares to last week · writes
                        never calculates anything
                                    │
                      ┌─────────────┴─────────────┐
                      ▼                           ▼
              executive brief               team report
```

**One architectural rule: the agent never does arithmetic.** Not a percentage, not an average, not a date. Every figure comes from a deterministic, tested, version-controlled tool. The agent's job is to read those numbers, compare them to last week's, explain what they mean, and frame the decision.

That boundary is what makes a report written by a language model auditable. Ask the same question twice and get the same answer. A wrong number is wrong in one line of code and gets fixed once, for everyone.

**Forecasting method.** Monte Carlo over historical item throughput — 20,000 seeded trials. Item counts rather than story points, because six sprints supply six point-observations (too few to form a distribution) but roughly sixty item-observations. It also cannot be inflated by estimating generously.

**It refuses.** Below ten completed items in the window, there is no forecast — and the refusal is printed verbatim rather than softened into a wide range. *"Not enough data"* and *"wide confidence interval"* are different statements and only one of them is true.

## What it deliberately will not do

| | Why |
|---|---|
| Rank or compare individuals | Throughput is a property of the system, not the person. The data cannot support the claim, and the first report that makes it is the last report anyone reads. |
| Quote a single delivery date | The data cannot support one. Percentiles, or nothing. |
| Write to Jira or Asana | Read-only by decision. It publishes documents; it cannot cause an incident. |
| Recommend working longer or harder | There is no hours data in this system, by design. Rising work in progress means the plan is wrong; rising unplanned work means intake is. |
| Report unchanged numbers as news | If nothing moved, that is one line, not a document. |
| Score or rank competing product asks | WSJF and its relatives multiply an unvalidated value estimate by an unvalidated size estimate and present the product as arithmetic. The delivery cost of each ordering is computable and is given. The relative worth of the asks is a judgement, and it stays with the people accountable for it. |
| Treat an intake estimate as a commitment | A t-shirt size is an intake-stage figure that is expected to move once the team refines the ask. Every intake number carries that sentence, and the forecast is re-run afterwards. |

## Cost and rollout

No licences. No infrastructure. The dashboard is a single HTML file; the tools are a few hundred lines of dependency-free Python. The only running cost is the model calls to write two documents a day.

| Phase | Duration | Exit criterion |
|---|---|---|
| **0. Shadow** | 2 sprints | Runs, nobody reads it. History accumulates; 10+ forecasts resolved and scored |
| **1. Team report** | 2 sprints | The team says it changes what they do at stand-up |
| **2. Add the exec brief** | 2 sprints | Calibration acceptable; a leader confirms a decision was informed by it |
| **3. Automate** | ongoing | Two sprints with no correction needed |

**Do not start at phase 3.** A forecasting agent with no calibration history is a confident stranger. The score in the brief footer currently reads *"no score yet"*, and it should stay that way until there are ten resolved predictions.

## The honest caveats

- **It needs history.** On a single sprint of data the forecaster refuses outright. Twelve weeks is where it becomes useful.
- **Value figures are the weakest number on the page.** They are planning-time estimates that nobody reconciles against actuals. The reports label them a floor rather than a total, and state how many completed items carry no estimate — but closing that loop at 90 days is a process someone has to own.
- **Item counting assumes items are roughly comparable in size.** If a team starts splitting work smaller, throughput rises without output rising. The agent checks for exactly that pattern before quoting any forecast, and marks its forecasts provisional when it finds it.
- **Intake forecasts cannot see outside the team.** The simulation models one board's throughput. A dependency on another team is invisible to it and the forecast will be optimistic by however long that dependency takes. Dependencies are recorded on the ask so a human applies the correction; nothing automates it.
- **A t-shirt range covers variance within the band, not the risk of the wrong band.** If intake calls an XL an L, the range will not tell you. Refinement bounds that error; simulation cannot.
- **Team load is measured as work in progress and unplanned work, not hours.** No timesheet data is collected or implied. That is the right call, but it means the dashboard cannot see effort directly — only its consequences in the flow of work.

---

### The one-line version

*An agent that reads delivery data every morning, tells leadership what will actually happen and what decision that requires — and keeps a public scorecard of how often it was right.*
