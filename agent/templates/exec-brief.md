# {{sprint}} — delivery brief
**{{team}} · as at {{as_of}} · source: {{source}}**

> One line if and only if something is wrong with the data itself (stale, demo, partial). Otherwise delete this line.

## Will we make it

{{One sentence with the probability against the date that already exists in the reader's head.}}
Example shape: *There is a **4%** chance all 10 outstanding items land by 14 August `[forecast]`. The 85th-percentile finish is 24 August `[forecast p85]` — eight working days past the sprint end. This assumes scope stops changing, which it has not in any of the last three sprints.*

| Confidence | All outstanding work done by |
|---|---|
| 50% | {{date}} |
| 85% | {{date}} |

## What changed since {{previous_date}}

Two to four bullets, movement only. Each states the direction and whether it reads as better or worse.

- {{metric}} moved from {{a}} to {{b}} `[measured]` — {{better or worse, and the one-line why}}
- {{risk list change: what cleared, what is new}} `[measured]`

*If nothing material moved, this section is one sentence saying so, and whether that is concerning.*

## What it is worth

{{Value closed, with the count of completed items carrying no estimate}} `[measured]`. Read as a floor, not a total.

## The decision we need from you

One item. Framed as a choice with its consequence, not a status update.

> Example: *v2.2.0 cannot ship complete on the 14th. Either it ships without the inventory-sync fix (BLC-429), or the date moves to the 19th. We need that call by Wednesday to avoid a partial release build.*

**If no decision is required, write: "Nothing needed from you this week."** Do not invent one.

---
<sub>Every figure traces to an issue key and was produced by `metrics.py` / `forecast.py`, not written by hand. Forecast calibration over the last {{n}} resolved predictions: Brier {{score}} ({{interpretation}}).</sub>
