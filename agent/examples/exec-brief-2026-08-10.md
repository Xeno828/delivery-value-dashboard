# Sprint 24 — delivery brief
**Storefront Team · as at 10 August 2026 · source: Jira board 42**

## Will we make it

**There is a 0.4% chance all ten outstanding items land by 14 August** `[forecast]`. The 85th-percentile finish is **26 August** `[forecast p85]` — eight working days late. That assumes scope keeps growing at its historical rate; frozen, it reads 4% and 24 August.

| Confidence | All outstanding work complete by |
|---|---|
| 50% | 21 August |
| 85% | 26 August |

Realistically **four to six of the ten items** land by the 14th `[forecast p85]`; the sprint closes partial. That is a planning outcome, not a performance one — the sprint committed 18 items against a three-sprint average of 9 `[measured]`, and a 100% over-commitment `[derived]` was always going to read as failure. Next sprint should be sized at **11 items** `[forecast p85]`.

**v2.2.0 has a 42% chance of being scope-complete by 14 August** `[forecast]`; its 85th-percentile date is 19 August. v2.3.0 is not at risk.

## What changed since 7 August

- Items completed moved 8 → 12 `[measured]` — better; four cleared in three days.
- Blocked list: BLC-429 and BLC-441 are new, BLC-499 cleared `[measured]` — net worse, and BLC-429 is both top priority and the thing holding v2.2.0.
- Scope grew 9 points after kickoff `[measured]` — worse, and it landed while delivery was already 11 points of percentage behind the clock `[derived]`.

## What it is worth

**$87,000** of estimated impact closed, across two items with a stated basis `[measured]`. Ten other completed items carry no estimate, so this is a floor, not a total — and none of it is reconciled against booked revenue.

## The decision we need from you

**v2.2.0 cannot ship complete on the 14th.** Either it ships without the inventory-sync fix (BLC-429, which oversells limited stock), or the release date moves to the 19th. BLC-429 has been open 21 days and is blocked externally, so "try harder" is not an option. We need the call by Wednesday to avoid building the release candidate twice.

---
<sub>Every figure traces to an issue key and was produced by `metrics.py` / `forecast.py`, not written by hand. Forecast calibration: fewer than 10 resolved predictions so far — no score yet, and no probability in this brief should be treated as validated until there is one.</sub>
