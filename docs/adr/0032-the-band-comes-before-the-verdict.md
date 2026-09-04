# 0032 — The band comes before the verdict

The page's default order is its source order, and until 1.79.12 the source put the verdict card — *What this sprint means*, a paragraph and six findings — above the eight-tile KPI band. Read from the top, the page said "12 of 22 items are done (55%), carrying 41 of 83 story points. The sprint is 60% elapsed…" before it showed a single figure in a tile. The order was chosen once, early, on the argument that a report opens with its conclusion.

**Decided 2026-09-03: the band comes first.** The KPI band is the first tile under the filter row; the verdict is the second.

## Why

`PRODUCT.md` names two readers, and the second is the one the order serves: the executive who *"scans left to right across a single band; a figure buried inside a chart card is a figure not read."* Measured on the evening of 2026-09-03, the band's top edge sat at 717px on a 1440-wide screen — behind a 175px topbar whose action cluster wraps under the title, the filter row and a 437px verdict card — and at 1,735px on a 375-wide phone, two full screens down. The one row the executive was promised was the fifth thing on the page. Two independent critiques the same day named it, the second as its first priority issue.

The verdict does not lose by going second. It is the working under the figures: every sentence in it restates a tile ("55%", "60% elapsed", "behind the clock by roughly 5 percentage points") and adds the why. Read after the band it explains what was just scanned; read before it, it asked the reader to hold six figures in prose until the tiles confirmed them.

## What it rules out

**Shrinking the chrome instead.** A one-row topbar with Dark, Print and Export behind an overflow control recovers about 100px and leaves the band third. It may still be done; it does not answer the finding.

**A different order per reader.** The Executive preset already exists, and it too began with the verdict. Presets choose *which* tiles; the default order is the page's one reading order, and it is the same for both readers because the delivery manager who defends the numbers scans the band as well.

## Amended 2026-09-04: the chip goes with the band, and the chrome above it shrinks

The third critique measured the toolbar at 175px on a 1440-wide screen and 218px at 1280 — its action cluster, 1,221px wide with the source badge, the health chip and six buttons, wrapping to three rows beside the title — so the band this record put first still began 270 to 313px down, and at 375 wide 697px down. Three moves, none of them a new decision: the sprint goal into the verdict card it is context for; Print and Export CSV behind one *More* control; and the health chip out of the toolbar to the right end of the band. The chip is the verdict's shortest form, and this record already says the verdict comes after the figures; a summary of the band that stood two containers above it was the one place the order was still the old way round. The band now breaks to two rows at 1180px, where the grid halves, rather than at 1280, where a common laptop sat on the wrong side of the line.

## What holds it

The source order in `src/index.html` and the `TILES` list in `src/app.js` agree, `tests/e2e.py` asserts the default order is the source order, that the band is the first tile by name, and that it starts inside the first screen at 1500 wide. A reader's saved reorder still travels in the URL and still wins over the default.
