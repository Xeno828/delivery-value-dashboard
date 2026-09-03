---
name: Delivery Value Dashboard
description: A ruled, plain-spoken delivery report where every figure carries its basis and colour is spent only on meaning.
colors:
  ledger-paper: "#fcfcfb"
  desk-plane: "#f3f3f0"
  ink: "#0b0b0b"
  ink-secondary: "#52514e"
  ink-muted: "#6f6d67"
  rule-grid: "#e1e0d9"
  rule-axis: "#c3c2b7"
  hairline: "rgba(11,11,11,0.10)"
  link-blue: "#256abf"
  accent-blue: "#256abf"
  info-ink: "#256abf"
  on-accent: "#ffffff"
  on-status-dark: "#141414"
  delivery-blue: "#2a78d6"
  scope-orange: "#eb6834"
  done-green: "#1baf7a"
  signal-amber: "#eda100"
  contrast-pink: "#e87ba4"
  deep-green: "#008300"
  indigo: "#4a3aa7"
  alert-red: "#e34948"
  delivery-blue-100: "#cde2fb"
  delivery-blue-250: "#86b6ef"
  delivery-blue-350: "#5598e7"
  delivery-blue-450: "#2a78d6"
  delivery-blue-600: "#184f95"
  status-good: "#0ca30c"
  status-warning: "#fab219"
  status-serious: "#ec835a"
  status-critical: "#d03b3b"
  good-ink: "#006300"
  warn-ink: "#8a5a00"
  serious-ink: "#9a4419"
  crit-ink: "#a02b2b"
  good-wash: "#eaf7ea"
  warn-wash: "#fdf4e0"
  serious-wash: "#fcefe8"
  crit-wash: "#fbecec"
  info-wash: "#eaf1fc"
typography:
  display:
    fontFamily: "system-ui, -apple-system, 'Segoe UI', sans-serif"
    fontSize: "38px"
    fontWeight: 640
    lineHeight: 1
    letterSpacing: "-0.025em"
  headline:
    fontFamily: "system-ui, -apple-system, 'Segoe UI', sans-serif"
    fontSize: "27px"
    fontWeight: 640
    lineHeight: 1.05
    letterSpacing: "-0.02em"
  title:
    fontFamily: "system-ui, -apple-system, 'Segoe UI', sans-serif"
    fontSize: "14px"
    fontWeight: 650
    lineHeight: 1.5
    letterSpacing: "-0.005em"
  body:
    fontFamily: "system-ui, -apple-system, 'Segoe UI', sans-serif"
    fontSize: "14px"
    fontWeight: 400
    lineHeight: 1.5
    letterSpacing: "normal"
  caption:
    fontFamily: "system-ui, -apple-system, 'Segoe UI', sans-serif"
    fontSize: "12.5px"
    fontWeight: 400
    lineHeight: 1.5
    letterSpacing: "normal"
  label:
    fontFamily: "system-ui, -apple-system, 'Segoe UI', sans-serif"
    fontSize: "11.5px"
    fontWeight: 600
    lineHeight: 1.4
    letterSpacing: "0.04em"
  mono:
    fontFamily: "ui-monospace, SFMono-Regular, Menlo, monospace"
    fontSize: "11.5px"
    fontWeight: 400
    lineHeight: 1.5
    letterSpacing: "normal"
  scale:
    display: "38px"
    headline: "27px"
    drop-glyph: "22px"
    page-title: "20px"
    stat: "19px"
    modal-title: "17px"
    panel-title: "16px"
    verdict: "15px"
    body: "14px"
    forecast-lead: "13.5px"
    finding: "13px"
    caption: "12.5px"
    caption-small: "12px"
    note: "11.5px"
    table-head: "11px"
    axis: "10.5px"
    severity-glyph: "10px"
    info-ring: "9.5px"
    arrow-glyph: "8px"
    form: "0.86rem"
    form-label: "0.82rem"
rounded:
  bar: "2px"
  bar-lg: "3px"
  focus: "4px"
  code: "5px"
  xs: "6px"
  icon: "7px"
  sm: "8px"
  md: "9px"
  drop: "10px"
  lg: "12px"
  xl: "14px"
  pill: "999px"
spacing:
  xxs: "4px"
  xs: "6px"
  sm: "8px"
  md: "10px"
  lg: "12px"
  xl: "14px"
  xxl: "16px"
  xxxl: "20px"
components:
  button-secondary:
    backgroundColor: "{colors.ledger-paper}"
    textColor: "{colors.ink}"
    typography: "{typography.caption}"
    rounded: "{rounded.sm}"
    padding: "7px 12px"
  button-secondary-hover:
    backgroundColor: "{colors.desk-plane}"
    textColor: "{colors.ink}"
  button-primary:
    backgroundColor: "{colors.accent-blue}"
    textColor: "{colors.on-accent}"
    typography: "{typography.caption}"
    rounded: "{rounded.sm}"
    padding: "7px 12px"
  button-icon:
    backgroundColor: "{colors.ledger-paper}"
    textColor: "{colors.ink-secondary}"
    rounded: "7px"
    padding: "0"
    size: "26px"
  button-icon-pressed:
    backgroundColor: "{colors.info-wash}"
    textColor: "{colors.link-blue}"
  segment-toggle:
    backgroundColor: "{colors.desk-plane}"
    textColor: "{colors.ink-secondary}"
    typography: "{typography.caption}"
    rounded: "{rounded.sm}"
    padding: "6px 11px"
  segment-toggle-pressed:
    backgroundColor: "{colors.accent-blue}"
    textColor: "{colors.on-accent}"
  input:
    backgroundColor: "{colors.desk-plane}"
    textColor: "{colors.ink}"
    typography: "{typography.caption}"
    rounded: "{rounded.sm}"
    padding: "6px 9px"
  chip-good:
    backgroundColor: "{colors.good-wash}"
    textColor: "{colors.good-ink}"
    rounded: "{rounded.pill}"
    padding: "2px 8px"
  chip-warn:
    backgroundColor: "{colors.warn-wash}"
    textColor: "{colors.warn-ink}"
    rounded: "{rounded.pill}"
    padding: "2px 8px"
  chip-serious:
    backgroundColor: "{colors.serious-wash}"
    textColor: "{colors.serious-ink}"
    rounded: "{rounded.pill}"
    padding: "2px 8px"
  chip-critical:
    backgroundColor: "{colors.crit-wash}"
    textColor: "{colors.crit-ink}"
    rounded: "{rounded.pill}"
    padding: "2px 8px"
  chip-info:
    backgroundColor: "{colors.info-wash}"
    textColor: "{colors.info-ink}"
    rounded: "{rounded.pill}"
    padding: "2px 8px"
  card:
    backgroundColor: "{colors.ledger-paper}"
    textColor: "{colors.ink}"
    rounded: "{rounded.lg}"
    padding: "12px 14px 14px"
  kpi-tile:
    backgroundColor: "{colors.ledger-paper}"
    textColor: "{colors.ink}"
    typography: "{typography.headline}"
    rounded: "{rounded.lg}"
    padding: "11px 13px 12px"
  refusal:
    backgroundColor: "{colors.warn-wash}"
    textColor: "{colors.ink}"
    typography: "{typography.caption}"
    rounded: "0 8px 8px 0"
    padding: "11px 13px"
  tooltip:
    backgroundColor: "{colors.ledger-paper}"
    textColor: "{colors.ink}"
    rounded: "{rounded.md}"
    padding: "9px 11px"
---

# Design System: Delivery Value Dashboard

## Overview

**Creative North Star: "The Audited Ledger"**

The page is a set of accounts a reader can check line by line. Seventeen ruled cards rest on a warm grey plane, each headed by a question in ordinary English ("Can we trust the forecast?", "Where does the time go?") and each answering with a figure, its unit, and the basis printed beneath it in smaller, quieter type. Nothing on the page is decorative: a colour is either a chart series, a severity, or a link, and every one of them has a name. The system font does the talking because the file has to travel by email and open with no network, and because a report that borrows a display face starts to look like a pitch.

The personality is plain-spoken and exact. Copy is sentences, not labels; a refusal is printed in full, in the tool's own words, inside a wash with a left rule, so it reads as the tile saying something rather than as an error. Numbers are tabular, tightly tracked, and never larger than the reader needs: the largest figure on the page (a value total at 38px) is still smaller than most dashboards' smallest headline. The eight KPI tiles across the top are the executive's scan line; everything below is the working.

Density is high on purpose. A full sprint fits on one 1440px screen, the twelve-column grid keeps every row summed to twelve, and cards stretch to their row so a short tile reads as a card with room in it rather than a hole in the page. Two themes are equal citizens: every token is redefined for dark, and both are tested to WCAG 2.2 AA.

**Key Characteristics:**
- Warm off-white paper on a warm grey plane, ruled by hairlines rather than lifted by shadow.
- System font stack throughout; no web fonts, no icon sets, Unicode glyphs only.
- One accent blue for controls and links, kept separate from the chart's delivery blue so contrast fixes never touch a validated series.
- Four severities, each a wash plus an ink pair, each carrying a glyph as well as a hue.
- Figures in tabular numerals with negative tracking; units and basis always beside them.
- Cards at 12px radius, controls at 8px, chips as pills: three corner sizes carry the page, with a short named ladder of small radii beneath them for bars, code, icon buttons and drop zones.

## Colors

A warm neutral ground with colour reserved for series, severity and action.

### Primary
- **Accent Blue** (`accent-blue`, #256abf): the one control colour. Primary buttons, pressed segments, the active tab underline, focus rings and links. It is a shade darker than the chart's Delivery Blue so it clears 4.5:1 as text, and the two must never be swapped.
- **Delivery Blue** (`delivery-blue`, #2a78d6): the lead chart series. Work remaining, items done, committed, work in progress; the line a reader follows first. Validated for colour-vision deficiency with its neighbours and not to be altered for contrast.
- **Delivery Blue ramp** (`delivery-blue-100` to `delivery-blue-600`): a five-step sequential scale of the same hue for stacked stages (not started, in progress, done) and for the waiting-versus-worked split. Lighter is earlier or idler; darker is later or active.

### Secondary
- **Scope Orange** (`scope-orange`, #eb6834): the second series and the only warm one in a chart. Total scope on the burndown, unplanned work on the load tile. When it rises, work was added.
- **Done Green** (`done-green`, #1baf7a): the value sparkline and the priced share of a KPI bar.
- **Signal Amber** (`signal-amber`, #eda100): the carry-over KPI bar and a fourth series where one is needed.
- **Contrast Pink** (`contrast-pink`, #e87ba4), **Deep Green** (`deep-green`), **Indigo** (`indigo`), **Alert Red** (`alert-red`): the tail of the eight-series palette, present in the token set for charts with more series than the page currently draws. Use in order; do not skip to a favourite.

### Tertiary
- **Status Good / Warning / Serious / Critical** (`status-good` #0ca30c, `status-warning` #fab219, `status-serious` #ec835a, `status-critical` #d03b3b): the severity glyph fills and the source-badge dot. These are fills for small marks, never text.
- **Severity ink and wash pairs** (`good-ink` on `good-wash`, `warn-ink` on `warn-wash`, `serious-ink` on `serious-wash`, `crit-ink` on `crit-wash`, `info-ink` on `info-wash`): the chip, callout and refusal colours. Ink is darkened until it passes 4.5:1 on its wash; the wash is a tint of the same hue at roughly 8% strength.

### Neutral
- **Ledger Paper** (`ledger-paper`, #fcfcfb): every card, tile, popover, panel and tooltip.
- **Desk Plane** (`desk-plane`, #f3f3f0): the page background, input fields, code, the forecast's ask strip; anything that sits a step below paper.
- **Ink** (`ink`, #0b0b0b), **Ink Secondary** (`ink-secondary`, #52514e), **Ink Muted** (`ink-muted`, #6f6d67): three text weights. Ink for figures and findings, secondary for captions and the "why" under a finding, muted for labels, notes, axis text and the footer.
- **Rule Grid** (`rule-grid`, #e1e0d9) and **Rule Axis** (`rule-axis`, #c3c2b7): chart gridlines and row dividers; the axis line and the dashed drop-zone border.
- **Hairline** (`hairline`, rgba(11,11,11,.10)): the border on every card and control. Translucent so it reads on paper and plane alike.

Dark theme values for every token live in `src/styles.css` under `:root[data-theme="dark"]`; paper becomes #1a1a19 on a #0d0d0d plane, inks invert, series shift a step to hold contrast, and washes become deep tints of their hue. They are recorded in the sidecar and are not restated here.

### Named Rules
**The Two Blues Rule.** `accent-blue` is for controls and text; `delivery-blue` is for series. A contrast fix on one must never reach the other, because the series palette is validated for colour-vision deficiency as a set.

**The Ink-on-Wash Rule.** Severity is always ink on its own wash, never white on the status fill. White on the warning yellow measures 1.8:1.

**The Named Colour Rule.** Every colour on the page is a token with a job. A hex literal in markup or script is a bug.

## Typography

**Display Font:** system-ui (with -apple-system, "Segoe UI", sans-serif)
**Body Font:** system-ui (the same stack)
**Label/Mono Font:** ui-monospace (with SFMono-Regular, Menlo, monospace) for issue ids and pasted data only

**Character:** One family, weighted rather than paired. Figures are set at 640 with negative tracking so they sit tight and read as a number rather than a word; running text is 400 at 14px on a 1.5 line; labels are 600, small and tracked open. The font is whatever the reader's operating system draws, by design.

### Hierarchy
- **Display** (640, 38px, line-height 1, tracking -0.025em): the value hero figure only. One per page.
- **Headline** (640, 27px, line-height 1.05, tracking -0.02em): the eight KPI values. Also the 20px page title at -0.01em.
- **Title** (650, 14px, tracking -0.005em): card headings, each phrased as a question or a plain statement. Panel titles step up to 16px, modal titles to 17px.
- **Body** (400, 14px, line-height 1.5): the verdict paragraph (15px, 1.55), findings (13px), issue summaries. Findings bold their number with 650 inline.
- **Caption** (400, 12.5px, line-height 1.5): card captions, the "why" beneath a finding, button and select text, the forecast's basis line in italic.
- **Label** (600, 11.5px, tracking 0.04em, uppercase): filter and context-bar labels, table headers (11px, 0.03em), legend text (not uppercase).
- **Note** (400, 11.5px, line-height 1.45, muted ink): the basis under a figure, footers, axis text (10.5px).
- **Mono** (11.5px): account ids, pasted JSON, code.

### Named Rules
**The Tabular Rule.** Any run of digits a reader might compare is set in `font-variant-numeric: tabular-nums`: KPI values, tables, tooltips, issue metadata, the forecast table.

**The Basis Rule.** No figure stands alone. Beneath or beside every number is its unit and, in note type, the slice it was computed over.

**The Question Rule.** A card heading asks the question the card answers, in ordinary English. "How long finished work took", not "Cycle time".

**The Enumerated Ramp Rule.** Every size the page sets is a step of `typography.scale` in the frontmatter — the seven roles above, the in-between steps they lean on (the 20px page title, the 15px verdict, the 13px finding, the 11px table head, the 10.5px axis), the three glyph sizes (22px drop arrow, 10px severity mark, 8px reorder arrow, and the 9.5px info ring) and the brief form's two rem values, which are the only rem on the page. A size that is not on the ramp is added to the ramp first, with a name that says where it is used, or it is not used. The detector reads the ramp, not the prose.

## Layout

A single centred column up to 1560px wide with 16px top and 20px side padding, on a twelve-column grid with a 10px gutter. Cards declare a span (3 to 12) and every row must sum to twelve at every breakpoint; the browser suite asserts it at three widths. Cards stretch to the height of their row and keep their contents top-aligned.

The page stacks in a fixed order: topbar (title, sprint line, goal, badges and actions), the context bar (Project → Board → Sprint), the filter row, the KPI band (eight tiles in one row, four at 1280px, two at 640px), the exec summary at span 12 beneath it — the band is the executive's scan line and comes before the paragraph that explains it — then chart pairs at 7 + 5, then 6 + 6, 8 + 4, and two full-width rows for the brief recipients and the risk register. The risk register flows into two columns from 1000px and three from 1500px.

Below 1180px every span from 3 to 8 becomes 6 and span 9 becomes 12, so the grid halves rather than promoting wide tiles to full width and stranding their partners. Below 760px everything is span 12 and card tools drop under the title onto their own row. Below 900px the exec summary collapses from a 1.15fr / 2fr pair to one column.

Internal rhythm is on a 2px base: 4, 6, 8, 10, 12, 14, 16, 20. Card padding is 12px 14px 14px; KPI tiles 11px 13px 12px; topbar 14px 18px; filter rows 10px 14px; the panel 16px 18px. Gaps between siblings are 6 to 10px; between a heading block and its content 10px; between rows of a list 9 to 11px with a hairline rule.

Wide content never widens the page: tables scroll inside a 290px-tall wrapper, sparklines cap at their column, and a control that cannot wrap is a WCAG 1.4.10 failure. Print drops the chrome and shadows and lets cards break cleanly.

## Elevation & Depth

The system is flat with a border. A card is defined by its 1px hairline and its paper-on-plane tonal step, not by lift; the shadow that rides on every card (`0 1px 2px rgba(11,11,11,.05), 0 6px 18px rgba(11,11,11,.05)`) is at 5% and should be treated as incidental softening of the edge, never as a structural cue. Depth is conveyed by tone: plane below paper, wash inside paper, hairline between.

The only things that rise are transient: a KPI tile lifts 1px with a slightly stronger shadow on hover, the tooltip and popovers float at 9px radius with a darker cast, the drill-in panel slides from the right under a scrim at 35% ink, and the modal sits under a 45% scrim.

### Shadow Vocabulary
- **Card rest** (`0 1px 2px rgba(11,11,11,.05), 0 6px 18px rgba(11,11,11,.05)`): every card, tile, topbar, filter row and popover. Dark theme raises the alpha to 40% / 35% on black.
- **Tile hover** (`0 2px 4px rgba(11,11,11,.06), 0 10px 24px rgba(11,11,11,.09)`): KPI tiles only, with a 1px translate.
- **Float** (`0 6px 24px rgba(0,0,0,.18)`): the tooltip. The panel uses `-8px 0 34px rgba(0,0,0,.18)`.
- **Modal** (`0 20px 60px rgba(0,0,0,.3)`): the import dialog.

### Named Rules
**The Border Defines It Rule.** Remove the shadow and the page must still read. If a component needs its shadow to be seen, give it a hairline instead.

**The Nothing Stacks Rule.** Cards never overlap and never nest a second card. The panel, the popovers and the modal are the only layers, and all of them are transient.

## Shapes

Three corner sizes carry the whole page, and every radius on it is a named step of the `rounded` scale in the frontmatter: bar (2px) and bar-lg (3px) for progress and KPI bars, focus (4px) for a focused disclosure summary, code (5px), xs (6px), icon (7px), sm (8px), md (9px), drop (10px), lg (12px), xl (14px) and pill. Cards, the topbar, filter rows and popovers are gently rounded (12px). Controls, inputs, selects, the forecast's ask strip and callouts are tighter (8px); icon buttons, code, small inputs and list rows sit at 6 to 7px; the tooltip, textareas, drop zones and radio cards at 9 to 10px; the modal alone at 14px. Chips, badges, the health pill, the toast and filter chips are full pills (999px).

Borders are 1px hairline everywhere, dashed at 1.5px for the drop zone and the offline notice, and dashed at 1px for the "folded" separators above a raw field. A refusal is squared on its left where a 3px rule in the severity ink stands, and rounded 8px on the right. Progress and KPI bars are 3 to 6px tall with 2 to 3px radius. Severity glyphs are 16px circles with a bold 10px character; the info mark is a 14px ring.

Chart geometry follows the same restraint: 2px series lines, 4.5px point markers, straight-line plan as a dashed grey, and rebuilt data points drawn hollow with a 3 2 dash so the distinction is texture rather than a new colour.

## Components

Refined and restrained: every control looks like the browser's own, only tidier. Future work sharpens states and spacing within these values rather than accepting defaults or adding weight.

### Buttons
- **Shape:** gently rounded (8px), 1px hairline, 12.5px at weight 550, 7px 12px padding, inline-flex with a 6px gap.
- **Secondary (default):** paper background, ink text; hover fills with plane.
- **Primary:** accent blue fill and border, white text; hover brightens 8%. One per surface: "Load data", "Apply", "Close" in the panel footer.
- **Icon:** 26px square at 7px radius, secondary ink, hairline; hover to plane and full ink. Pressed state (a table view toggled on) fills info wash with link-blue text and border.
- **Linkish:** an underlined link-blue button at 600 weight with a 2px underline offset, used for "See the 3 issues" inside a finding.
- **Info mark:** the 14px ring beside a heading is a button named for the card ("About Burndown, with scope changes shown"). Hover, focus and click all show the same tooltip, which is announced as the mark's description while it shows; Escape dismisses it.
- **Focus:** a 2px link-blue outline offset 1 to 2px on every focusable control; never removed.

### Segmented toggle
- **Style:** a hairline pill-cornered group (8px) on plane, buttons 6px 11px at 600 weight in secondary ink, divided by hairlines.
- **State:** the pressed segment fills accent blue with white text; unpressed hover lifts to paper and full ink. Used for Items / Points and the forecast's When / How many / Sequence asks.

### Chips
- **Style:** pill, 11px at 650, 2px 8px padding, hairline, 5px gap to its glyph.
- **Variants:** good, warn, serious, critical, info, each ink on its wash. The glyph is part of the chip: ● for good, ▲ for warn and serious, ■ for critical.
- **Filter chip:** 11.5px on info wash with an inline × in secondary ink.
- **Source badge:** a pill on plane with an 8px status dot and 12px secondary text.
- **Health pill:** 13px at 650, 7px 14px, on the severity wash with matching ink. Says "· in story points" after the score when the measure has left the default, because the score moves with it.

### Cards / Containers
- **Corner Style:** 12px.
- **Background:** paper on the plane.
- **Border:** 1px hairline.
- **Shadow Strategy:** the card-rest shadow, incidental (see Elevation).
- **Internal Padding:** 12px 14px 14px.
- **Header:** a title block that yields (flex 1 1 220px) beside a tools cluster that wraps; heading at 14px/650 with a 14px info ring, caption in secondary ink with 10px below.

### KPI tile
The executive's scan line. Paper card at 11px 13px 12px, label at 11.5px/600 in secondary ink, value at 27px/640 tight-tracked, sub-line in muted 11.5px with a 16px minimum height so a missing sub-line does not shift the row, an optional delta at 600 with a ▲/▼ glyph in severity ink, and a 3px bar on grid grey whose fill takes the series or severity colour. Hover lifts 1px. Over an empty selection the whole band becomes one card carrying the refusal callout.

### Inputs / Fields
- **Style:** 12.5px, 6px 9px, 8px radius, hairline, plane background, ink text, max width 190px in the filter row and 230px in the context bar. Native selects, native search, native date fields.
- **Focus:** 2px link-blue outline, offset 1px, border turns link-blue.
- **Labels:** 11.5px uppercase tracked labels in muted ink beside the field.
- **Form fields (brief recipients):** full width, paper background, 6px radius, .86rem text, placeholder in muted ink.
- **Error / Disabled:** rejected input is stated in warn ink at 600 on its own line; a disabled arrow sits at 32% opacity and keeps its place rather than disappearing.

### Navigation
The page has no navigation bar; the topbar carries identity and actions, and the context bar carries the Project → Board → Sprint pickers with uppercase labels, 1px separators and a secondary-ink meta line. Tabs inside the import dialog are text buttons at 600 with a 2px transparent underline that turns link-blue when selected.

### Refusal callout
The signature component. A block at 11px 13px with a 3px left rule in warn ink, warn wash behind, square on the left and 8px on the right, 12.5px text on a 1.55 line. It prints the tool's sentence verbatim and ends with the clause about the evidence being absent rather than noisy. A note beneath the sentence, inside the callout, is set in secondary ink, never muted: muted on the wash falls under 4.5:1 in the dark theme. The affirmative twin uses good ink and good wash for "saved" confirmations. The offline notice is the same block with a dashed hairline instead of a rule and no wash.

### Finding row
A two-column grid (18px glyph, then text): a 16px severity circle with a bold glyph in dark or white ink by severity, the "what" in full ink at 13px, the "why" beneath in secondary ink at 12.5px, and a linkish "See the N issues". Risk rows add a chip, a bold "Do this:" line and an "Inspect" link, ruled by grid-grey hairlines.

### Drill-in panel
A right-hand sheet up to 760px or 96vw, paper, sliding in over 200ms under a 35% scrim. Header at 16px 18px with a 16px title and secondary sub-line, a scrolling body, and a footer row of buttons aligned right. Issue rows carry a bold tabular key, a 13px summary and a wrapping meta line in secondary ink.

### Tooltip
Paper at 9px radius with the float shadow, 9px 11px padding, 12px text up to 290px wide; a 650 header, tabular rows with the value bold on the right, and a hairline-ruled footer in secondary 11.5px. Fades in over 80ms.

## Do's and Don'ts

### Do:
- **Do** set every figure in tabular numerals with its unit beside it and its basis in note type beneath.
- **Do** use the system font stack only, and Unicode glyphs (▲ ● ■ ▤ ✕) where an icon is needed.
- **Do** keep control colour on `accent-blue` and `link-blue` and series colour on `delivery-blue` and its neighbours; fix contrast on the first, never on the second.
- **Do** print a refusal in the refusal callout in the tool's own words, including its closing clause.
- **Do** make each row of tiles sum to twelve columns at every breakpoint, and stretch cards to their row.
- **Do** pair every severity hue with a glyph and every rebuilt data point with a hollow, dashed marker.
- **Do** phrase a card heading as the question it answers.

### Don't:
- **Don't** load a web font, an icon font or an icon package. The file makes zero network calls and the security suite asserts it.
- **Don't** write a hex literal in markup or script; every colour is a named token.
- **Don't** put white text on a status fill; severity is ink on wash.
- **Don't** dim a disabled or unsupported element with opacity alone; keep its colour and carry the reason in text.
- **Don't** let a control set the page's minimum width; wrap it, or give the tools their own row.
- **Don't** add a radius outside the `rounded` scale or a second shadow at rest; the border defines the card, and a new corner size is a new step with a name before it is a value in a rule.
