# {{ask id}} — {{ask title}}
**Requested by {{requester}} · {{team / board}} · forecast as at {{as_of}}**

## Is this ready to forecast

{{readiness verdict, verbatim from `readiness()`}}

- **Missing (blocks a forecast):** {{field — why it matters}}
- **Gaps (forecastable, but weaker):** {{field — why it matters}}

*If anything is under "missing", stop here. Report the gaps and ask for them. A number attached to an unchallenged ask is how bad work gets scheduled efficiently.*

## How big, and on what evidence

**{{p50}} items at the median, {{p85}} at the 85th percentile** — range {{low}}–{{high}} `[measured]`

Basis: {{sizing basis, verbatim}}

{{Caveat, verbatim. For a t-shirt size this must state that the number is an intake-stage estimate, is expected to move at refinement, and that the band's width reflects only how varied past epics of that size were — not how wrong the t-shirt judgement itself might be.}}

## When it would land

| Confidence | Earliest possible | Realistic |
|---|---|---|
| 50% | {{date}} | {{date}} |
| 85% | {{date}} | {{date}} |

- **Earliest possible** — dedicated capacity, starting now, nothing queued ahead `[forecast]`
- **Realistic** — {{queue_items}} committed items ahead of it, throughput discounted by the measured {{discount}}% interruption rate `[forecast]`

**The existing queue costs this ask {{cost_of_queue_days}} working days** at the 85th percentile `[derived]`. That figure is the price of everything already in flight, and it is the number to quote when someone asks why it cannot start sooner.

{{If neededBy is set: "Probability of landing by {{neededBy}}: **{{n}}%** at the realistic scenario." If that probability is low, say so plainly in the first line of this section rather than leaving it in the table.}}

## What would narrow this

{{Uncertainty attribution, verbatim — then the consequence:}}

- **If size dominates:** refining this ask will narrow the forecast more than anything the delivery team does. Say roughly by how much — a refined equivalent typically halves the spread.
- **If delivery dominates:** the ask is understood well enough. The spread is what this team genuinely looks like, and it is not an estimating problem.

## What this does not account for

- **Dependencies outside the board:** {{list, or "none recorded"}} — the forecast cannot see them and will be optimistic by however long they take.
- **Assumptions:** {{list}} — re-run this forecast when any of them changes.
- {{Any other stated caveat}}

## Value

{{If an amount and a basis are both present: state both. If an amount is present without a basis: say so, and do not use it to argue for priority. If neither: "Not quantified" and why — a compliance obligation is a legitimate answer.}}

*No priority score is computed. The delivery consequence of each ordering is computable; the relative worth of competing asks is not, and multiplying two unvalidated estimates does not make it so.*

---
<sub>Every figure produced by `agent/tools/intake.py` against {{dataset}}, not written by hand. Sizing method: {{method}}. Re-run after refinement.</sub>
