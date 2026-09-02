# Product intake — forecasting an ask before any of it exists

Everything else in this repository forecasts work that is already in the tracker. Intake is the harder case: someone has described a product ask, nobody has written a single ticket for it, and a portfolio decision has to be made anyway.

The usual answers are both bad. *"We'll estimate it once it's refined"* means the prioritisation call gets made on no evidence and refinement then justifies it. *"About six weeks"* is a number with no stated uncertainty, which is how a guess becomes a commitment in the retelling.

This does a third thing: it takes the ask, sizes it against how work on that specific team has actually turned out, simulates delivery, and returns **a range with its own uncertainty attributed** — so the answer to "how do we make this more certain?" is a fact rather than an opinion.

```bash
make intake-scale ASK=…              # what S/M/L/XL mean on this team, in items
make intake ASK=data/asks/INTAKE-2026-014.json
make intake-sequence                 # what each ordering of the queue costs
```

---

## 1. The sizing ladder

Three methods, in increasing order of evidence. The tool records which one was used and prints its caveat verbatim; the caveat is not decoration, it is the part that stops the number being over-read.

| Method | Use when | How the range is built |
|---|---|---|
| `tshirt` | Intake-stage, before the team has seen it | The board's completed epics split into quartiles: S/M/L/XL. The chosen band's actual item counts become the sample. |
| `reference-class` | No sizing judgement has been made at all | Every completed epic on the board is the sample. Widest range, fewest assumptions. |
| `explicit` | The team has refined it into stories | Triangular distribution over `minItems` / `likelyItems` / `maxItems`. |

### T-shirt sizes are calibrated, not assumed

An organisation-wide t-shirt scale is a fiction: an "L" on a platform team and an "L" on a mobile team have never meant the same thing. So the scale is derived per board, from that board's own delivery history:

```
S  [4, 6]    median 5      (4 completed epics)
M  [8, 12]   median 10     (4 completed epics)
L  [13, 21]  median 16.5   (4 completed epics)
XL [24, 38]  median 29     (4 completed epics)
    quartiles of 16 completed epics on this board
```

A board with fewer than **eight** completed epics gets a refusal rather than bands, because four quartiles cut from seven observations are noise wearing a uniform.

This matters most in what it *does not* claim. The caveat printed with every t-shirt forecast says it plainly:

> Its width here reflects only how varied past L epics were — not how wrong the T-shirt judgement itself might be.

If the ask is genuinely an XL and intake called it an L, nothing in the range will tell you. That error is bounded by refinement, not by simulation — which is exactly why the tool is designed to be re-run afterwards and why an intake figure must never be presented as a commitment.

### What counts as a "finished epic"

Not "every child item is Done" — real epics accumulate a stray ticket for years and would never qualify. An epic joins the reference class when it has **stopped growing** (no item created in 30 days), is at least **90% complete**, and has at least **three** items. The definition is in `epic_sizes()` and its thresholds are arguments, so a team whose Jira hygiene differs can move them and see what changes.

### Which field says two issues belong to the same epic

`epicKey` where a dataset carries one, `epic` — the epic's own summary — otherwise. The field is chosen **once for the whole issue set** rather than per issue, and that is the part worth knowing about: `epicKey or epic` reads as the obvious fallback and splits a single epic in two the moment one dataset carries the key on some of its issues and the name on others. A twenty-item epic arriving as two tens shrinks every t-shirt band, and reads exactly like a team that has started working in smaller pieces.

It matters because of where the two fields can go. A payload assembled for the hosted calculator carries `epicKey` and **cannot** carry `epic`: free text is stripped on the way in, which is the point of that boundary rather than an oversight. Until sizing learned to group on the key, it grouped nothing over that route, found no completed epics, and refused — for every board, always. The refusal was accurate and the capability was unavailable in principle.

Where the grouping was by key, the basis line says so, so the working can be followed down the right column.

## 2. Two capacity scenarios, always both

A single date invites the reader to treat it as the answer. Two dates make the gap between them the subject, which is where the actionable information is.

**Earliest possible** — dedicated capacity from the start date, nothing queued ahead, no interruption. This is not a plan. It is the ceiling: the date you could not beat even if this ask were the only thing the team touched.

**Realistic** — the ask queues behind everything already committed and unfinished on that board, and throughput is thinned by the team's own measured interruption rate. Interruption is modelled as a **thinned throughput series** (days are stochastically zeroed at the measured rate) rather than a multiplier applied to the final date, so the variance carries through the simulation instead of being smoothed away.

```
earliest possible (dedicated, starts now)
  50%  by 2026-09-04  (19 working days)
  85%  by 2026-09-16  (27 working days)

realistic (queued behind 19 committed items; throughput discounted by the measured 12% interruption rate)
  50%  by 2026-10-09  (44 working days)
  85%  by 2026-10-28  (57 working days)

cost of the existing queue: 30 working days at the 85th percentile
```

**The cost of the queue is the number to quote.** Thirty working days is the price of everything already in flight, stated in the currency the requester cares about. It converts "why can't you start it now?" from a negotiation into an arithmetic question about what comes out of the queue.

Interruption is measured per board, from `unplanned / (committed + unplanned)` averaged across that board's sprint history — 12.4% on one board in the demo data, 3.2% on another. Neither number was chosen.

## 3. Where the uncertainty comes from

This is the part with no equivalent in a normal estimate, and the part worth leading with.

Three simulations run: both inputs varying, size frozen at its median, throughput frozen at its mean. The two partial spreads are attributed proportionally. It is a decomposition rather than an exact variance split, but it answers the only question that changes anyone's behaviour — *which of these should we go and reduce?*

> **size dominates** — 61% of the range comes from not knowing how big the ask is. Refining the ask will narrow this forecast far more than anything the delivery team does.

> **delivery dominates** — 83% of the range comes from normal delivery variability rather than sizing. The ask is understood well enough; the spread is what this team genuinely looks like.

The first sends the ask back to refinement with a reason. The second stops a team being asked to "tighten up the estimate" when the estimate was never the problem — the spread is the team's real behaviour, and the fix for it is flow, not estimating.

It discriminates in practice: on the demo data a vague ask attributes 54% to size, the same ask refined attributes 10%, and the total spread narrows from 34 working days to 19.

## 4. The readiness gate

`readiness()` runs before anything is forecast, and splits fields into two classes.

**Required** — `title`, `team`, `sizing`. Missing any of these and no forecast is produced at all. A forecast without a named team is a forecast against nobody's capacity.

**Recommended** — `problemStatement`, `successMeasure`, `neededBy`, `valueEstimate`, `dependencies`, `assumptions`. Each is forecastable without, but each absence is reported with its consequence stated. A value amount supplied *without* a basis is flagged specifically: an unsourced number is the one most likely to be quoted back in a steering meeting.

The gate exists because the failure mode of any intake tool is that it makes an unchallenged ask look processed. A number attached to an ask nobody interrogated is how bad work gets scheduled efficiently.

## 5. Sequencing — and the score that is deliberately absent

Give it several asks against one team and it evaluates every ordering: when each ask lands at the 85th percentile if it goes first, and how many working days that ordering costs the others.

It also names, separately and first, anything that **misses its date in every possible ordering**:

```
NO ORDERING DELIVERS THESE BY THEIR DATE:
  INTAKE-2026-016 — needed 2026-10-09, best case 2026-11-03, short by 25 days
  Sequencing cannot fix this. The levers are scope, capacity or the date.
```

That is the highest-value output in the whole feature, because it is the conversation that otherwise happens six weeks late.

**At most twelve asks, on every transport.** Every ask is simulated in every ordering, so the cost is cubic in the count: 4 asks take about a second natively, 8 take 7 s, 12 take 21 s and 16 take 48 s, and Forge's runtime is ten times slower throughout. Above twelve the tool refuses in its own sentence — `intake.MAX_ASKS` and `intake.too_many_asks()` — before reading the board, and the hosted service and the Forge function quote that sentence rather than paraphrasing it. The fifty the service once allowed was about twenty-five minutes natively and had never been run. Twelve rather than sixteen because three and a half minutes is as long as a reader should watch a tile; [ADR 0031](adr/0031-the-forecast-runs-inside-the-forge-function.md) has the measurements.

**No priority score is computed — not WSJF, not weighted value, not anything.** The reasoning is stated in the code and repeated here because it will be asked for: those formulas multiply an unvalidated value estimate by an unvalidated size estimate and present the product as arithmetic. The delivery consequence of an ordering is genuinely computable and is returned. The relative worth of competing asks is a judgement owned by people, and dressing it as a calculation launders the judgement rather than improving it. The tool gives the decision-makers the delivery facts and each ask's stated value basis, side by side, and stops there.

## 6. The ask format

```json
{
  "id": "INTAKE-2026-014",
  "title": "Saved payment methods across web and mobile",
  "requestedBy": "Nadia Farouk, Product",
  "team": "42",
  "problemStatement": "Returning customers re-enter card details on every order…",
  "successMeasure": "Returning-customer checkout abandonment below 22% within one quarter.",
  "sizing": { "method": "tshirt", "size": "L", "basis": "Intake sizing with Product and the tech lead." },
  "valueEstimate": { "amount": 210000, "basis": "1,900 abandonments/mo × 31%→22% × $52 AOV, annualised", "confidence": "low" },
  "neededBy": "2026-10-30",
  "dependencies": ["Payments platform team — tokenisation service"],
  "assumptions": ["No new PCI scope", "Mobile can reuse the web tokenisation flow"]
}
```

`sizing` takes `{"method": "reference-class"}` with no size, or `{"method": "explicit", "minItems": 9, "likelyItems": 14, "maxItems": 22}`. Three worked examples live in `data/asks/` — one of each method, one of which cannot be delivered on time at any priority.

For a quick answer without writing a file:

```bash
python3 agent/tools/intake.py data/demo-intake-bundle.json --board 42 --tshirt L --needed-by 2026-11-30
```

## 7. What it cannot see

Stated here and restated in every brief, because a forecast that hides its blind spots is worse than no forecast.

- **Dependencies outside the board.** The simulation models one team's throughput. A dependency on another team is invisible to it, and the forecast will be optimistic by however long that dependency takes. They are recorded on the ask so a human can apply the correction.
- **The t-shirt judgement itself.** Covered above: the range reflects variance within a band, not the risk of the wrong band.
- **Work that has not been raised yet.** The queue is what is committed and unfinished today. Anything added to the sprint after this runs pushes the ask out further.
- **Whether the ask is worth doing.** Nothing here evaluates that, by design.
- **Ramp-up.** Throughput is sampled from a team already working in a domain it knows. An ask in genuinely unfamiliar territory will start slower than the sample implies.

## 8. Reproducibility

Same ask, same dataset, same answer. `SEED = 20260816`, 20,000 trials per scenario, 8,000 per ordering when sequencing. Percentiles are 50 / 70 / 85 / 95 throughout, and every horizon is stated in **working days** alongside its date so the unit is never in doubt.

Everything is in `agent/tools/intake.py`. As with `metrics.py` and `forecast.py`, the agent narrates the output and does not compute any part of it — `make intake` runs the same code path the agent does, so a figure in a brief can always be reproduced from a shell.

## 9. Using it in the agent

`agent/SKILL.md` has an **Intake mode** section. Its four standing rules:

1. Run `readiness()` first and report what is missing before reporting any number.
2. Report **both** scenarios, never one. The gap between them is the point.
3. Lead with the uncertainty attribution, not the date. The date is what gets remembered; the attribution is what changes what anyone does next.
4. `unachievable_at_any_priority` is the headline whenever it is non-empty.

Output template: [`agent/templates/intake-brief.md`](../agent/templates/intake-brief.md).

---

## Appendix: the demo dataset

Intake needs a board with *finished* epics behind it. The main demo bundle deliberately has none — its epics are long-lived themes ("Payments", "Checkout Stability") that never close, which is realistic for many boards and useless for calibrating a reference class.

`scripts/make_intake_demo.py` therefore writes a **separate** bundle, `data/demo-intake-bundle.json`, adding 16 delivered epics (4–38 items) to board 42, dated before the demo window so the delivery forecaster's trailing throughput is untouched. The main demo and the figures quoted in the video and executive summary stay valid.

```bash
make bundle        # rebuilds both the demo bundle and the intake bundle
```
