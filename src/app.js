/* ============================================================================
   Delivery Value Dashboard — rendering engine
   Self-contained. No network calls, no external libraries, no browser storage.
   ========================================================================= */
(function () {
"use strict";

/* ---------------------------------------------------------------- utilities */
const $  = (s, r) => (r || document).querySelector(s);
const $$ = (s, r) => Array.from((r || document).querySelectorAll(s));
const esc = s => String(s == null ? "" : s).replace(/[&<>"']/g, c =>
  ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const D  = s => (s ? new Date(s + (s.length === 10 ? "T00:00:00Z" : "")) : null);
const days = (a, b) => (a && b) ? Math.round(((D(b) - D(a)) / 864e5) * 10) / 10 : null;
const fmtD = s => s ? D(s).toLocaleDateString(undefined, { day: "numeric", month: "short", timeZone: "UTC" }) : "—";
const n1 = v => (Math.round(v * 10) / 10).toLocaleString();
const pct = v => Math.round(v * 100) + "%";
const money = (v, cur) => new Intl.NumberFormat(undefined,
  { style: "currency", currency: cur || "USD", maximumFractionDigits: 0 }).format(v);
const sum = (a, f) => a.reduce((t, x) => t + (f ? f(x) : x), 0);
const uniq = a => Array.from(new Set(a.filter(v => v != null && v !== ""))).sort();
const clamp = (v, a, b) => Math.max(a, Math.min(b, v));
/** Only http(s) survives. A tracker URL arrives from the same data as every
 *  other field, so `javascript:` in it is as plausible as `<script>` in a
 *  summary — and esc() does not stop a scheme, only markup. */
function safeUrl(u) {
  if (!u) return null;
  const t = String(u).trim();
  return /^https?:\/\//i.test(t) ? t : null;
}
const iso = dt => dt.toISOString().slice(0, 10);
/** Weekdays between two ISO dates, inclusive. Swap in a holiday calendar here
 *  if the team observes one — every elapsed-time figure keys off this list. */
function workingDays(start, end) {
  if (!start || !end) return [];
  const out = []; const a = D(start), b = D(end);
  for (let t = new Date(a); t <= b; t.setUTCDate(t.getUTCDate() + 1))
    if (t.getUTCDay() !== 0 && t.getUTCDay() !== 6) out.push(iso(t));
  return out;
}

/* -------------------------------------------------------------- global state */
const S = {
  data: null,
  /** "items" or "points".
   *  Items is the default because it is the unit the forecasting agent uses,
   *  and two tools reporting the same sprint in different units is how a
   *  meeting turns into an argument about arithmetic. Story points remain
   *  available — they are familiar and they carry size information item
   *  counts throw away — but they are no longer the thing the page leads with. */
  unit: "items",
  /** Selected context id — one project+board+sprint, or a "roll:" rollup. */
  ctx: null,
  view: null,
  /** Tile ids currently on screen. Set at boot from the URL or from a saved
   *  copy's data-tiles attribute; never from storage, which would not
   *  survive the file being emailed. */
  shown: null,
  drillOpener: null,
  live: null,          // set when a local live-mode server answers
  filters: { assignee: "", epic: "", type: "", status: "", q: "" },
  tables: {},
  lastDrill: []
};

/** The active unit, as a small strategy object. Everything unit-dependent
 *  reads from here rather than testing S.unit inline. */
function U() {
  const items = S.unit === "items";
  return {
    key: S.unit,
    isItems: items,
    val: i => (items ? 1 : (i.storyPoints || 0)),
    label: items ? "items" : "story points",
    short: items ? "items" : "pts",
    one: items ? "item" : "story point",
    /** Label agreeing in number with v — "1 item", "4 items". */
    n: v => (Math.abs(v) === 1 ? (items ? "item" : "story point") : (items ? "items" : "story points")),
    fmt: v => (items ? String(Math.round(v)) : n1(v)),
    burn: f => (items ? { remaining: "remainingItems", scope: "scopeItems", ideal: "idealItems" }[f]
                      : { remaining: "remainingSP", scope: "scopeSP", ideal: "idealSP" }[f]),
    hist: f => (items ? { committed: "committedItems", completed: "completedItems" }[f]
                      : { committed: "committedSP", completed: "completedSP" }[f])
  };
}

/* ---------------------------------------------------- explanatory tooltips */
const HELP = {
  unit: "<b>Items or story points?</b><br>Everything denominated in work volume on this page &mdash; the burndown, the delivered figure, pace against the clock, scope added, the distribution and the commitment history &mdash; switches with this control.<br><br><b>Why items is the default</b><br>It is the unit the forecaster uses. Six sprints gives six story-point observations, which cannot support a distribution; the same six sprints gives sixty-odd item observations, which can. It also cannot be inflated by estimating generously.<br><br><b>When to switch to points</b><br>Item counts treat a one-line copy change and an eight-point hotfix as equal. If you are arguing about whether scope growth mattered, look at points. If you are forecasting, look at items.",
  exec: "<b>What it is</b><br>A plain-English reading of every chart below, written from the data rather than typed by hand.<br><br><b>How to improve it</b><br>If a line here surprises you, click through to the issues. A summary you cannot trace back to issues is a summary nobody trusts.",
  burn: "<b>What it is</b><br>Story points still outstanding on each day, against the straight-line plan. The orange line is total committed scope.<br><br><b>Why the orange line matters</b><br>A classic burndown hides mid-sprint additions — the line just flattens and the team looks slow. Showing scope separately splits 'we were slow' from 'we were given more'.<br><br><b>How to improve it</b><br>Agree a scope-change rule at planning: anything added mid-sprint displaces something of equal size, and that swap is recorded.",
  dist: "<b>What it is</b><br>Story points per person, split into done, in progress and not started.<br><br><b>How to read it</b><br>Look for one person carrying a tall in-progress block — that is work in progress piling up, which slows the whole team down more than an uneven total would.<br><br><b>How to improve it</b><br>Cap how many items one person has in progress at once (two is a common limit) and finish before starting.",
  flowtime: "<b>What it is</b><br>For each closed item: total time from being raised to being done (lead time), split into time actively worked (cycle time) and time waiting in a queue.<br><br><b>How to read it</b><br>Long pale bars are the real problem. Waiting is invisible in most reports and is usually the majority of elapsed time.<br><br><b>How to improve it</b><br>Attack the queues, not the coding. Refine sooner, review faster, and stop starting work you cannot immediately progress.",
  age: "<b>What it is</b><br>How long each unfinished item has existed, in bands sized for a two-week sprint.<br><br><b>Why these bands</b><br>Monthly bands are useless at sprint scale — everything lands in the first bucket. Anything past 14 days has already survived a full sprint.<br><br><b>How to improve it</b><br>Review the oldest item first at every stand-up. Age, not priority, is the best predictor of an item never finishing.",
  pred: "<b>What it is</b><br>What the team committed to versus what it completed, over the last six sprints.<br><br><b>How to read it</b><br>The number that matters is consistency, not height. A team that reliably delivers 34 points is more useful to a business than one that swings between 20 and 50.<br><br><b>How to improve it</b><br>Set the next commitment from the average of the last three completions, not from optimism.",
  dora: "<b>What it is</b><br>The four DORA measures: how often you release, how often a release breaks something, how long a change takes to reach customers, and how fast you recover.<br><br><b>How to read it</b><br>Deployment frequency and lead time measure speed; change failure rate and recovery time measure safety. Improving one at the cost of the other is not progress.<br><br><b>How to improve it</b><br>Smaller, more frequent releases usually improve all four at once.",
  load: "<b>What it is</b><br>Two load signals, both taken from issue status and nothing else: how much work is started but unfinished, and how much of each sprint arrived after planning.<br><br><b>Why not hours</b><br>This organisation does not operate overtime, and a chart of hours would imply a time-tracking regime that does not exist. Output per person went too &mdash; on its own it is a productivity-per-head number, and this dashboard does not measure people.<br><br><b>How to read it</b><br>Work in progress rising while completion stays flat means more is being started than finished, and every extra item in flight slows the ones already there. Rising unplanned work means the commitment is being displaced after it was agreed.<br><br><b>How to improve it</b><br>Cap work in progress per person, and fix intake at the front rather than asking for more effort at the back.",
  value: "<b>What it is</b><br>Estimated commercial impact of the items closed this sprint, counting only items where someone recorded how the number was arrived at.<br><br><b>How to read it</b><br>These are forecasts, not booked revenue. The basis line is more important than the figure.<br><br><b>How to improve it</b><br>Require a one-line basis on any item claiming value, and revisit the estimate 90 days later against actuals.",
  rel: "<b>What it is</b><br>Upcoming releases with how much of their scope is finished, against the target date.<br><br><b>How to improve it</b><br>A release at risk needs a scope decision, not a status update. Decide what ships without the blocked item.",
  risk: "<b>What it is</b><br>Risks derived automatically from the numbers on this page, each with a suggested action and a link to the underlying issues.<br><br><b>How to improve it</b><br>Work the top item. A risk list nobody closes becomes wallpaper."
};

/* ------------------------------------------------------------------ tooltip */
const tip = $("#tip");
function showTip(html, x, y) {
  tip.innerHTML = html;
  tip.style.opacity = "1";
  const r = tip.getBoundingClientRect();
  tip.style.left = clamp(x + 14, 8, innerWidth - r.width - 8) + "px";
  tip.style.top = clamp(y + 14, 8, innerHeight - r.height - 8) + "px";
}
function hideTip() { tip.style.opacity = "0"; }
document.addEventListener("mousemove", e => {
  const t = e.target.closest("[data-tt],[data-tip]");
  if (!t) { hideTip(); return; }
  const html = t.dataset.tip ? HELP[t.dataset.tip] : t.dataset.tt;
  if (!html) { hideTip(); return; }
  showTip(html, e.clientX, e.clientY);
});
document.addEventListener("mouseleave", hideTip);

/* ------------------------------------------------------------ colour tokens */
const CSSV = k => getComputedStyle(document.documentElement).getPropertyValue(k).trim();
const C = () => ({
  s1: CSSV("--s1"), s2: CSSV("--s2"), s3: CSSV("--s3"), s4: CSSV("--s4"),
  seq100: CSSV("--seq-100"), seq250: CSSV("--seq-250"), seq350: CSSV("--seq-350"),
  seq450: CSSV("--seq-450"), seq600: CSSV("--seq-600"),
  good: CSSV("--good"), warning: CSSV("--warning"), serious: CSSV("--serious"), critical: CSSV("--critical"),
  grid: CSSV("--grid"), axis: CSSV("--axis"), muted: CSSV("--muted"), surface: CSSV("--surface-1")
});
const STAGE = () => [
  { key: "Done", label: "Done", col: CSSV("--seq-600") },
  { key: "In Progress", label: "In progress", col: CSSV("--seq-450") },
  { key: "To Do", label: "Not started", col: CSSV("--seq-250") }
];

/* ------------------------------------------------------------ data plumbing */
/**
 * Accepts both shapes:
 *   v1.0 — one sprint: { meta, issues, burndown, history, releases, dora }
 *   v2.0 — a bundle:   { meta, contexts[], issues[] (each with contextId), byContext{} }
 * A v1 file is wrapped into a single implicit context so everything downstream
 * has exactly one code path. Old files keep working untouched — that matters
 * because people have them saved and emailed.
 */
/** Coerce one raw issue. Extracted so live-loaded issues can be cleaned without
 *  going through normalise(), which would re-tag their contextId. */
function normaliseIssue(i, meta) {
  const o = Object.assign({}, i);
  o.storyPoints = Number(o.storyPoints) || 0;
  o.businessValue = Number(o.businessValue) || 0;
  o.flagged = o.flagged === true || o.flagged === "true";
  o.addedMidSprint = o.addedMidSprint === true || o.addedMidSprint === "true";
  if (!o.statusCategory) {
    const t = (o.status || "").toLowerCase();
    o.statusCategory = /done|closed|resolved|complete/.test(t) ? "Done"
      : /progress|review|test|doing/.test(t) ? "In Progress" : "To Do";
  }
  o.labels = Array.isArray(o.labels) ? o.labels
    : (typeof o.labels === "string" && o.labels ? o.labels.split(/[;,|]\s*/) : []);
  const base = safeUrl(meta && meta.baseUrl);
  o.url = safeUrl(o.url) || (base ? base.replace(/\/$/, "") + "/browse/" + encodeURIComponent(o.key) : null);
  return o;
}

function normalise(d) {
  d.issues = (d.issues || []).map(i => normaliseIssue(i, d.meta));
  d.meta = d.meta || {};

  if (!Array.isArray(d.contexts) || !d.contexts.length) {
    // ---- v1 file: synthesise the single context it implicitly describes ----
    const id = "single";
    d.contexts = [{
      id: id,
      source: d.meta.source || "manual",
      projectName: d.meta.organisation || "",
      boardName: d.meta.team || d.meta.boardName || "",
      team: d.meta.team || "",
      sprintName: d.meta.sprintName || "Current period",
      sprintState: "active",
      sprintGoal: d.meta.sprintGoal || "",
      startDate: d.meta.startDate, endDate: d.meta.endDate,
      asOfDate: d.meta.asOfDate, workingDays: d.meta.workingDays || [],
      issueCount: d.issues.length
    }];
    d.defaultContextId = id;
    d.byContext = { single: {
      burndown: d.burndown || [], history: d.history || [],
      releases: d.releases || [], dora: d.dora || null
    }};
    d.issues.forEach(i => { i.contextId = id; });
  } else {
    d.byContext = d.byContext || {};
    d.contexts.forEach(c => {
      d.byContext[c.id] = d.byContext[c.id] || {};
      const b = d.byContext[c.id];
      b.burndown = b.burndown || []; b.history = b.history || [];
      b.releases = b.releases || []; b.dora = b.dora || null;
      c.issueCount = c.issueCount != null ? c.issueCount
        : d.issues.filter(i => i.contextId === c.id).length;
    });
    if (!d.defaultContextId || !d.contexts.some(c => c.id === d.defaultContextId)) {
      const active = d.contexts.find(c => c.sprintState === "active");
      d.defaultContextId = (active || d.contexts[d.contexts.length - 1]).id;
    }
  }
  return d;
}

/* =====================================================================
   contexts — a context is one project + board + sprint
   ================================================================== */
const ROLL = "roll:";   // synthetic id prefix for a cross-sprint rollup

function contextById(id) {
  return (S.data.contexts || []).find(c => c.id === id) || null;
}

/** Every selectable context, including one rollup per board. */
function selectableContexts() {
  const real = S.data.contexts || [];
  const boards = {};
  real.forEach(c => {
    const k = (c.projectKey || c.projectName || "") + "|" + (c.boardId || c.boardName || "");
    (boards[k] = boards[k] || []).push(c);
  });
  const rolls = Object.entries(boards)
    .filter(([, cs]) => cs.length > 1)
    .map(([k, cs]) => {
      const f = cs[0];
      const sorted = cs.slice().sort((a, b) => String(a.startDate).localeCompare(String(b.startDate)));
      return {
        id: ROLL + k, isRollup: true, members: sorted.map(c => c.id),
        source: f.source, projectKey: f.projectKey, projectName: f.projectName,
        boardId: f.boardId, boardName: f.boardName, team: f.team,
        sprintName: "All " + sorted.length + " sprints",
        sprintState: "rollup",
        startDate: sorted[0].startDate,
        endDate: sorted[sorted.length - 1].endDate,
        asOfDate: sorted[sorted.length - 1].asOfDate,
        workingDays: [],
        issueCount: sum(sorted, c => c.issueCount || 0)
      };
    });
  return real.concat(rolls);
}

/** Resolve the active context into the shape every renderer reads. */
function buildView() {
  const all = selectableContexts();
  let ctx = all.find(c => c.id === S.ctx) || contextById(S.data.defaultContextId) || all[0];
  S.ctx = ctx.id;

  const ids = ctx.isRollup ? ctx.members : [ctx.id];
  const issues = S.data.issues.filter(i => ids.indexOf(i.contextId) >= 0);
  const last = S.data.byContext[ids[ids.length - 1]] || {};

  return {
    ctx: ctx,
    contexts: all,
    issues: issues,
    // A rollup spans several sprints, so a burndown is undefined for it. Better
    // an explicit blank with a reason than a chart that means nothing.
    burndown: ctx.isRollup ? [] : (last.burndown || []),
    history: last.history || [],
    releases: ctx.isRollup ? [] : (last.releases || []),
    dora: last.dora || null,
    meta: Object.assign({}, S.data.meta, {
      sprintName: ctx.sprintName, sprintGoal: ctx.sprintGoal,
      team: ctx.team || ctx.boardName, organisation: ctx.projectName || S.data.meta.organisation,
      boardName: ctx.boardName, projectKey: ctx.projectKey,
      startDate: ctx.startDate, endDate: ctx.endDate, asOfDate: ctx.asOfDate,
      workingDays: ctx.workingDays || []
    })
  };
}

const asOf = () => S.view.meta.asOfDate || S.view.meta.endDate || new Date().toISOString().slice(0, 10);

function filtered() {
  const f = S.filters, q = f.q.trim().toLowerCase();
  return S.view.issues.filter(i =>
    (!f.assignee || i.assignee === f.assignee) &&
    (!f.epic || i.epic === f.epic) &&
    (!f.type || i.type === f.type) &&
    (!f.status || i.statusCategory === f.status) &&
    (!q || (i.key + " " + i.summary).toLowerCase().includes(q))
  );
}

/* ------------------------------------------------------------ derived stats */
function derive(items) {
  const now = asOf(), end = S.view.meta.endDate;
  const done = items.filter(i => i.statusCategory === "Done");
  const open = items.filter(i => i.statusCategory !== "Done");
  const closedTimed = done.filter(i => i.resolved && i.started && i.created);
  const cycle = closedTimed.map(i => days(i.started, i.resolved));
  const lead = closedTimed.map(i => days(i.created, i.resolved));
  const hist = S.view.history || [];
  const prev = hist.length > 1 ? hist[hist.length - 2] : null;
  const cur = hist.length ? hist[hist.length - 1] : null;
  const hk = U().hist("completed");
  const last3 = hist.slice(-4, -1).map(h => (h[hk] != null ? h[hk] : h.completedSP)).filter(v => v != null);
  const avg3 = last3.length ? sum(last3) / last3.length : null;

  const m = {
    total: items.length,
    doneCount: done.length,
    donePct: items.length ? done.length / items.length : 0,
    totalSP: sum(items, i => i.storyPoints),
    doneSP: sum(done, i => i.storyPoints),
    openSP: sum(open, i => i.storyPoints),
    totalU: sum(items, U().val),
    doneU: sum(done, U().val),
    openU: sum(open, U().val),
    flagged: items.filter(i => i.flagged),
    critical: open.filter(i => /highest|critical|p1/i.test(i.priority || "")),
    added: items.filter(i => i.addedMidSprint),
    overdue: open.filter(i => i.dueDate && D(i.dueDate) < D(now)),
    notStarted: open.filter(i => !i.started),
    spillover: open,
    avgCycle: cycle.length ? sum(cycle) / cycle.length : null,
    avgLead: lead.length ? sum(lead) / lead.length : null,
    flowEff: null,
    done, open, closedTimed,
    valueItems: done.filter(i => i.businessValue > 0),
    prev, cur, avg3
  };
  m.addedSP = sum(m.added, i => i.storyPoints);
  m.addedU = sum(m.added, U().val);
  m.scopeAddedPct = (m.totalU - m.addedU) > 0 ? m.addedU / (m.totalU - m.addedU) : 0;
  m.value = sum(m.valueItems, i => i.businessValue);
  const totLead = sum(lead), totCyc = sum(cycle);
  m.flowEff = totLead > 0 ? totCyc / totLead : null;
  m.ages = open.map(i => ({ i, age: days(i.created, now) }));
  m.oldest = m.ages.slice().sort((a, b) => b.age - a.age)[0] || null;

  // elapsed working-time position in the sprint
  const wd = S.view.meta.workingDays || [];
  const idx = wd.indexOf(now);
  m.timeElapsed = wd.length ? (idx >= 0 ? (idx + 1) / wd.length : 1) : null;
  m.paceGap = (m.timeElapsed != null && m.totalU) ? (m.doneU / m.totalU) - m.timeElapsed : null;

  // health score, fully disclosed
  const parts = [];
  parts.push({ n: "Delivery pace", v: m.paceGap == null ? 0 : clamp(1 + m.paceGap * 2.2, 0, 1), w: 0.34,
    d: m.paceGap == null ? "no sprint calendar" : (m.paceGap >= 0 ? "ahead of the time-elapsed line" : Math.round(-m.paceGap * 100) + " percentage points behind the time-elapsed line") });
  parts.push({ n: "Scope stability", v: clamp(1 - m.scopeAddedPct * 4, 0, 1), w: 0.22,
    d: m.addedU ? U().fmt(m.addedU) + " " + U().n(m.addedU) + " added mid-sprint (" + pct(m.scopeAddedPct) + " growth)" : "no mid-sprint additions" });
  parts.push({ n: "Blockers", v: clamp(1 - (m.flagged.length / Math.max(items.length, 1)) * 6, 0, 1), w: 0.22,
    d: m.flagged.length + " flagged of " + items.length });
  parts.push({ n: "Ageing work", v: clamp(1 - (m.ages.filter(a => a.age > 14).length / Math.max(open.length, 1)), 0, 1), w: 0.22,
    d: m.ages.filter(a => a.age > 14).length + " open items older than 14 days" });
  m.healthParts = parts;
  m.health = sum(parts, p => p.v * p.w);
  m.healthBand = m.health >= 0.72 ? "Green" : m.health >= 0.45 ? "Amber" : "Red";
  return m;
}

/* --------------------------------------------------------- svg construction */
function svgEl(w, h) {
  return { w, h, parts: [], add(s) { this.parts.push(s); return this; },
    out(cls) { return '<svg class="' + (cls || "") + '" width="' + w + '" height="' + h +
      '" viewBox="0 0 ' + w + ' ' + h + '" role="img">' + this.parts.join("") + "</svg>"; } };
}
const cw = el => Math.max(280, (el.clientWidth || 600));
function yTicks(max, n) {
  const step = Math.pow(10, Math.floor(Math.log10(max / n || 1)));
  const cands = [step, step * 2, step * 2.5, step * 5, step * 10];
  const s = cands.find(c => max / c <= n) || step * 10;
  const t = []; for (let v = 0; v <= max + 1e-9; v += s) t.push(Math.round(v * 100) / 100);
  return t;
}
function ttRows(rows) { return rows.map(r => '<div class="t-r"><span>' + esc(r[0]) + "</span><span>" + esc(r[1]) + "</span></div>").join(""); }
function ttBox(h, rows, foot) {
  return '<div class="t-h">' + esc(h) + "</div>" + ttRows(rows) + (foot ? '<div class="t-f">' + foot + "</div>" : "");
}

/* =====================================================================
   RENDER: header, filters
   ================================================================== */
function renderHeader(m) {
  const meta = S.view.meta;
  $("#t-title").textContent = (meta.sprintName || "Sprint") + " — delivery and value";
  $("#t-sub").textContent = [meta.organisation, meta.team,
    fmtD(meta.startDate) + " – " + fmtD(meta.endDate)].filter(Boolean).join("  ·  ") +
    "  ·  data as at " + fmtD(asOf());
  $("#t-goal").innerHTML = meta.sprintGoal ? "<b>Sprint goal:</b> " + esc(meta.sprintGoal) : "";

  // Two separate facts, and the badge used to report only the first: what the
  // loaded dataset says about itself, and whether a live server is answering.
  // The bundled demo file labels itself "Demo data (no live connection)", so
  // with serve_live running the badge sat there denying the connection that had
  // just handed it eighteen sprints. S.live is the connection; meta is the data.
  const connected = !!S.live;
  const liveData = meta.source && meta.source !== "demo";
  const sb = $("#t-src");
  sb.querySelector(".dot").style.background = (connected || liveData) ? CSSV("--good") : CSSV("--warning");
  sb.querySelector("span:last-child").textContent = connected
    ? "Live: " + (S.live.label || S.live.source)
    : (meta.sourceLabel || (liveData ? "Live: " + meta.source : "Demo data"));
  sb.dataset.tt = "<b>Where this data came from</b><br>" + esc(meta.sourceLabel || "Demo data") +
    "<br>Pulled " + (meta.generatedAt ? new Date(meta.generatedAt).toLocaleString() : "unknown") +
    (connected ? "<br><br>Connected to " + esc(S.live.label || S.live.source) +
                 ". The connection is live; whether the data behind it is demo or real is the line above."
               : ".<br><br>Amber means this is not a live connection.");

  const band = m.healthBand;
  const map = { Green: ["--good-wash", "--good-ink", "●", "On track"],
                Amber: ["--warn-wash", "--warn-ink", "▲", "Needs attention"],
                Red:   ["--crit-wash", "--crit-ink", "■", "Off track"] };
  const [bg, ink, icon, word] = map[band];
  const hc = $("#t-health");
  hc.style.background = CSSV(bg); hc.style.color = CSSV(ink);
  hc.innerHTML = '<span aria-hidden="true">' + icon + "</span> Sprint health: " + word + " (" + Math.round(m.health * 100) + "/100)";
  hc.dataset.tt = "<b>How this score is built</b><br>" +
    m.healthParts.map(p => "· " + esc(p.n) + " (" + Math.round(p.w * 100) + "% weight): " +
      Math.round(p.v * 100) + "/100 — " + esc(p.d)).join("<br>") +
    "<br><br>Green ≥ 72, Amber ≥ 45, otherwise Red. Scored on <b>" + U().label + "</b> — the delivery-pace and " +
    "scope components move with the measure, so the score does too. Shown so you can argue with the method " +
    "rather than the colour.";
}

function renderFilters() {
  const I = S.view.issues;
  const opts = [["f-assignee", "assignee", uniq(I.map(x => x.assignee)), "Everyone"],
                ["f-epic", "epic", uniq(I.map(x => x.epic)), "All epics"],
                ["f-type", "type", uniq(I.map(x => x.type)), "All types"],
                ["f-status", "status", ["To Do", "In Progress", "Done"], "Any status"]];
  opts.forEach(([id, key, vals, all]) => {
    const el = $("#" + id);
    if (el.dataset.built !== "1") {
      el.innerHTML = '<option value="">' + all + "</option>" +
        vals.map(v => '<option value="' + esc(v) + '">' + esc(v) + "</option>").join("");
      el.dataset.built = "1";
      el.addEventListener("change", () => { S.filters[key] = el.value; render(); });
    }
    el.value = S.filters[key];
  });
  const q = $("#f-q");
  if (q.dataset.built !== "1") {
    q.dataset.built = "1";
    let t; q.addEventListener("input", () => { clearTimeout(t); t = setTimeout(() => { S.filters.q = q.value; render(); }, 200); });
  }
  $$("[data-unit]").forEach(b => {
    b.setAttribute("aria-pressed", String(b.dataset.unit === S.unit));
    if (b.dataset.bound !== "1") {
      b.dataset.bound = "1";
      b.addEventListener("click", () => { if (S.unit !== b.dataset.unit) { S.unit = b.dataset.unit; render(); } });
    }
  });
  const chips = Object.entries(S.filters).filter(([, v]) => v)
    .map(([k, v]) => '<span class="fchip">' + esc(k === "q" ? "search" : k) + ": <b>" + esc(v) +
      '</b><button data-clear="' + k + '" title="Clear">✕</button></span>').join("");
  $("#f-chips").innerHTML = chips + (chips ? '<button class="linkish" data-clear="all">Clear all</button>' : "");
}
document.addEventListener("click", e => {
  const b = e.target.closest("[data-clear]");
  if (!b) return;
  if (b.dataset.clear === "all") S.filters = { assignee: "", epic: "", type: "", status: "", q: "" };
  else S.filters[b.dataset.clear] = "";
  $("#f-q").value = S.filters.q; render();
});

/* =====================================================================
   RENDER: context bar — project / board / sprint
   ================================================================== */
function renderContextBar() {
  const bar = $("#ctxbar");
  const all = S.view.contexts, real = all.filter(c => !c.isRollup);
  // A single-sprint file has nothing to switch between; hide the whole row
  // rather than showing three dropdowns with one option each.
  if (real.length < 2 && !S.live) { bar.classList.add("hidden"); return; }
  bar.classList.remove("hidden");

  const cur = S.view.ctx;
  const projLabel = c => c.projectName || c.projectKey || "—";
  const boardLabel = c => c.boardName || c.team || "—";

  const projects = uniq(real.map(projLabel));
  const curProj = projLabel(cur);
  const boards = uniq(real.filter(c => projLabel(c) === curProj).map(boardLabel));
  const curBoard = boardLabel(cur);
  const sprints = all.filter(c => projLabel(c) === curProj && boardLabel(c) === curBoard)
    .sort((a, b) => (a.isRollup ? 1 : b.isRollup ? -1 : String(b.startDate).localeCompare(String(a.startDate))));

  const opt = (v, label, sel, extra) =>
    '<option value="' + esc(v) + '"' + (sel ? " selected" : "") + ">" + esc(label) +
    (extra ? " " + extra : "") + "</option>";

  const stateChip = c => c.isRollup ? "" :
    (c.sprintState === "active" ? " ● current" : c.sprintState === "future" ? " ○ not started" : "");

  bar.innerHTML =
    '<span class="ctx-lab">Source</span>' +
    '<span class="srcchip" title="' + esc((cur.source || "manual") + " connection") + '">' +
      esc((cur.source || "manual").toUpperCase()) + "</span>" +
    '<span class="ctx-sep"></span>' +
    '<label class="ctx-f">Project<select id="c-proj">' +
      projects.map(pn => opt(pn, pn, pn === curProj)).join("") + "</select></label>" +
    '<label class="ctx-f">Board<select id="c-board">' +
      boards.map(bn => opt(bn, bn, bn === curBoard)).join("") + "</select></label>" +
    '<label class="ctx-f">Sprint<select id="c-sprint">' +
      sprints.map(c => opt(c.id, c.sprintName + stateChip(c),
        c.id === cur.id, "(" + c.issueCount + ")")).join("") + "</select></label>" +
    '<span class="ctx-meta">' + esc(fmtD(cur.startDate) + " – " + fmtD(cur.endDate)) +
      (cur.isRollup ? " · rolled up, no burndown" : "") + "</span>" +
    (S.live ? '<button class="btn" id="c-live" style="margin-left:auto">Refresh from ' +
        esc(S.live.source || "server") + "</button>" : "");

  const pick = (proj, board) => {
    const c = all.find(x => projLabel(x) === proj && boardLabel(x) === board &&
                            x.sprintState === "active")
           || all.filter(x => projLabel(x) === proj && boardLabel(x) === board)
                 .sort((a, b) => String(b.startDate).localeCompare(String(a.startDate)))[0];
    if (c) selectContext(c.id);
  };
  $("#c-proj").onchange = e => {
    const proj = e.target.value;
    const b = real.filter(c => projLabel(c) === proj).map(boardLabel)[0];
    pick(proj, b);
  };
  $("#c-board").onchange = e => pick(curProj, e.target.value);
  $("#c-sprint").onchange = e => selectContext(e.target.value);
  if ($("#c-live")) $("#c-live").onclick = () => refreshLive();
}

/* =====================================================================
   RENDER: executive summary
   ================================================================== */
function renderExec(m) {
  const meta = S.view.meta, cur = m.cur;
  const behind = m.paceGap != null && m.paceGap < -0.05;
  const v = [];
  v.push("<strong>" + m.doneCount + " of " + m.total + " items are done (" + pct(m.donePct) + ")</strong>" +
    (U().isItems
      ? (m.totalSP ? ", carrying " + n1(m.doneSP) + " of " + n1(m.totalSP) + " story points." : ".")
      : ", worth " + n1(m.doneSP) + " of " + n1(m.totalSP) + " story points."));
  if (m.timeElapsed != null)
    v.push(" The sprint is <strong>" + pct(m.timeElapsed) + " elapsed</strong>, so delivery is " +
      (behind ? "<strong>behind the clock</strong> by roughly " + Math.round(-m.paceGap * 100) + " percentage points"
              : "<strong>tracking with the clock</strong>") + ".");
  if (m.addedU) v.push(" Scope grew by " + U().fmt(m.addedU) + " " + U().n(m.addedU) + " (" + pct(m.scopeAddedPct) + ") after the sprint started.");
  $("#exec-verdict").innerHTML = v.join("");

  $("#exec-basis").innerHTML = "Based on " + m.total + " issues" +
    (Object.values(S.filters).some(Boolean) ? " <b>matching the current filters</b>" : "") +
    " from " + esc(meta.sourceLabel || "the loaded dataset") + ", as at " + fmtD(asOf()) +
    ". Percentages are of " + U().label + " — switch the measure in the filter row to read them the other way.";

  const pts = [];
  const add = (sev, what, why, drill) => pts.push({ sev, what, why, drill });

  if (m.critical.length) {
    const top = m.critical.slice().sort((a, b) => (days(b.created, asOf()) - days(a.created, asOf())))[0];
    add("critical",
      m.critical.length + " highest-priority item" + (m.critical.length > 1 ? "s are" : " is") +
        " still open, the oldest being " + top.key + " at " + Math.round(days(top.created, asOf())) + " days.",
      "Highest-priority work that outlives a sprint is usually blocked on a decision, not on effort. " + top.summary + ".",
      { title: "Open highest-priority work", items: m.critical });
  }
  if (m.addedU) {
    add(behind ? "warning" : "info",
      "Scope grew " + pct(m.scopeAddedPct) + " mid-sprint — " + m.added.length +
        (m.added.length === 1 ? " item, " : " items, ") + n1(m.addedSP) +
        (m.addedSP === 1 ? " story point." : " story points."),
      behind ? "Delivery is behind the clock and the team was also given more work. Those are two different conversations; don't merge them."
             : "The team absorbed the extra work without slipping, which is worth saying out loud.",
      { title: "Work added after the sprint started", items: m.added });
  }
  if (m.flowEff != null) {
    add(m.flowEff < 0.4 ? "warning" : "good",
      "Only " + pct(m.flowEff) + " of elapsed time on closed items was spent actively working.",
      "The other " + pct(1 - m.flowEff) + " was queuing — waiting for review, for a decision, or for someone to be free. Queue time is the cheapest thing to fix and the least often measured.",
      { title: "Closed items, ranked by time spent waiting", items: m.closedTimed.slice().sort((a, b) => (days(a.created, a.resolved) - days(a.started, a.resolved)) < (days(b.created, b.resolved) - days(b.started, b.resolved)) ? 1 : -1) });
  }
  const old = m.ages.filter(a => a.age > 14);
  if (old.length) {
    add(old.length >= 3 ? "warning" : "info",
      old.length + " open item" + (old.length > 1 ? "s have" : " has") + " been alive longer than a full sprint.",
      "Age predicts abandonment better than priority does. The oldest is " +
        old.sort((a, b) => b.age - a.age)[0].i.key + " at " + Math.round(old[0].age) + " days.",
      { title: "Open work older than 14 days", items: old.map(a => a.i) });
  }
  if (m.value) {
    add("good", money(m.value, meta.currency) + " of estimated value closed this sprint across " + m.valueItems.length + " item" + (m.valueItems.length > 1 ? "s" : "") + ".",
      "Estimates with a stated basis, not booked revenue. " + (m.total - m.valueItems.length - m.open.length) + " other completed items carry no value estimate, so this figure is a floor, not a total.",
      { title: "Completed work with an estimated value", items: m.valueItems });
  }
  const hist = S.view.history || [];
  if (hist.length >= 4 && m.avg3) {
    const commit = m.cur ? (m.cur[U().hist("committed")] != null ? m.cur[U().hist("committed")] : m.cur.committedSP) : m.totalU;
    if (commit > m.avg3 * 1.25)
      add("warning", "This sprint committed " + U().fmt(commit) + " " + U().n(commit) +
        " against a three-sprint average delivery of " + U().fmt(m.avg3) + " " + U().n(m.avg3) + ".",
        "A commitment " + Math.round((commit / m.avg3 - 1) * 100) + "% above recent actuals is a forecasting problem, not a work-rate problem. It will read as failure whatever the team does.", null);
  }
  const wipSeries = hist.slice(-3).map(h => h.wipItems).filter(v => v != null);
  const thrSeries = hist.slice(-3).map(h => (h.completedItems != null ? h.completedItems : h.throughput))
    .filter(v => v != null);
  if (wipSeries.length === 3 && thrSeries.length === 3 &&
      wipSeries[2] > wipSeries[0] && thrSeries[2] <= thrSeries[0])
    add("warning", "Work in progress has risen from " + n1(wipSeries[0]) + " to " + n1(wipSeries[2]) +
      " items over three sprints while completion has not.",
      "More work is being started than finished. Every extra item in flight slows the ones already there, " +
      "so the fix is a work-in-progress cap rather than more effort.", null);

  const ico = { critical: ["--critical", "!"], warning: ["--warning", "▲"], serious: ["--serious", "▲"], good: ["--good", "✓"], info: ["--s1", "i"] };
  $("#exec-list").innerHTML = pts.slice(0, 6).map((p, ix) => {
    const [col, ch] = ico[p.sev];
    return "<li><span class='ic' data-sev='" + p.sev + "' style='background:" + CSSV(col) +
      "' aria-hidden='true'>" + ch + "</span>" +
      "<span><span class='what'>" + esc(p.what) + "</span><span class='why'>" + esc(p.why) +
      (p.drill ? " <button class='linkish' data-exec='" + ix + "'>See the " + p.drill.items.length + " issue" + (p.drill.items.length > 1 ? "s" : "") + "</button>" : "") +
      "</span></span></li>";
  }).join("");
  $("#exec-list").onclick = e => {
    const b = e.target.closest("[data-exec]"); if (!b) return;
    const p = pts[+b.dataset.exec];
    openDrill(p.drill.title, p.what, p.drill.items);
  };
}

/* =====================================================================
   RENDER: KPI strip
   ================================================================== */
function renderKpis(m) {
  const meta = S.view.meta;
  const arrow = (v, goodUp) => {
    if (v == null || Math.abs(v) < 0.005) return { t: "no change", c: CSSV("--muted"), i: "→" };
    const good = goodUp ? v > 0 : v < 0;
    return { t: (v > 0 ? "+" : "") + Math.round(v * 100) + "% vs last sprint",
             c: CSSV(good ? "--good-ink" : "--crit-ink"), i: v > 0 ? "▲" : "▼" };
  };
  const cur = m.cur, prev = m.prev, hk = U().hist("completed");
  const cv = h => (h && h[hk] != null ? h[hk] : (h ? h.completedSP : null));
  const spDelta = (cv(cur) && cv(prev)) ? cv(cur) / cv(prev) - 1 : null;

  const tiles = [
    { lab: "Delivered", val: pct(m.totalU ? m.doneU / m.totalU : 0),
      sub: U().fmt(m.doneU) + " of " + U().fmt(m.totalU) + " " + U().label +
           (U().isItems ? " · " + n1(m.doneSP) + " pts" : " · " + m.doneCount + " items"),
      barPct: m.totalU ? m.doneU / m.totalU : 0, barCol: CSSV("--s1"), delta: arrow(spDelta, true),
      tt: "Share of in-scope work completed, measured in " + U().label + ". Items is the default because it is the unit the forecaster uses; switch to points in the filter row if you need size information.",
      drill: { t: "Completed work", items: m.done } },
    // "pp" = percentage points. Never "pts" here — beside an item measure it
    // reads as story points, which is a different quantity entirely.
    { lab: "Pace vs clock", val: (m.paceGap == null ? "—" : (m.paceGap >= 0 ? "+" : "") + Math.round(m.paceGap * 100) + " pp"),
      sub: m.timeElapsed != null ? pct(m.timeElapsed) + " elapsed · percentage points" : "no calendar",
      barPct: m.timeElapsed || 0, barCol: CSSV("--muted"),
      tt: "Percentage of work complete (in " + U().label + ") minus percentage of the sprint elapsed. Negative means the burndown is behind the calendar. This is the single number the original dashboard was missing.",
      drill: { t: "Work not yet finished", items: m.open } },
    { lab: "Blocked", val: m.flagged.length, sub: "flagged as impeded",
      barPct: m.total ? m.flagged.length / m.total : 0, barCol: CSSV("--critical"),
      tt: "Items explicitly flagged. Every one of these is somebody else's decision to unblock.",
      drill: { t: "Blocked and flagged items", items: m.flagged } },
    { lab: "Top priority open", val: m.critical.length, sub: "highest severity, unfinished",
      barPct: m.total ? m.critical.length / m.total : 0, barCol: CSSV("--critical"),
      tt: "Highest-priority items still open. If this is above zero at sprint end, the priority scheme is not being honoured.",
      drill: { t: "Open highest-priority items", items: m.critical } },
    { lab: "Scope added", val: (m.addedU ? "+" + U().fmt(m.addedU) + " " + (U().isItems ? U().n(m.addedU) : U().short) : "0"),
      sub: m.added.length + (m.added.length === 1 ? " item" : " items") + " after kickoff · " + pct(m.scopeAddedPct) + " growth",
      barPct: clamp(m.scopeAddedPct * 3, 0, 1), barCol: CSSV("--s2"),
      tt: "Work added after the sprint began, in " + U().label + ". Counting items treats a hotfix and a typo fix as equal; counting points does not. Switch units in the filter row to see both readings.",
      drill: { t: "Added after the sprint started", items: m.added } },
    { lab: "Likely to carry over", val: U().fmt(m.openU) + " " + (U().isItems ? U().n(m.openU) : U().short),
      sub: m.open.length + " items still open",
      barPct: m.totalU ? m.openU / m.totalU : 0, barCol: CSSV("--warning"),
      tt: "Everything not yet done. At this point in the sprint, anything not started is the realistic carry-over candidate — " + m.notStarted.length + " items have never been picked up.",
      drill: { t: "Open work at risk of carry-over", items: m.open } },
    { lab: "Past due date", val: m.overdue.length, sub: "open, past their own due date",
      barPct: m.total ? m.overdue.length / m.total : 0, barCol: CSSV("--serious"),
      tt: "Open items whose due date has already passed. A due date nobody re-negotiates is a commitment quietly broken.",
      drill: { t: "Overdue open items", items: m.overdue } },
    { lab: "Value closed", val: money(m.value, meta.currency), sub: m.valueItems.length + " of " + m.done.length + " closed items priced",
      barPct: m.done.length ? m.valueItems.length / m.done.length : 0, barCol: CSSV("--s3"),
      tt: "Estimated commercial impact of completed items. Estimates only — see the value card for the working.",
      drill: { t: "Completed items carrying a value estimate", items: m.valueItems } }
  ];

  $("#kpis").innerHTML = tiles.map((t, i) =>
    '<button class="kpi" data-kpi="' + i + '" data-tt="<b>' + esc(t.lab) + "</b><br>" + esc(t.tt) + '">' +
      '<span class="k-lab">' + esc(t.lab) + "</span>" +
      '<span class="k-val">' + esc(String(t.val)) + "</span>" +
      '<span class="k-sub">' + esc(t.sub) + "</span>" +
      (t.delta ? '<br><span class="k-delta" style="color:' + t.delta.c + '">' + t.delta.i + " " + esc(t.delta.t) + "</span>" : "") +
      '<span class="k-bar"><i style="width:' + Math.round(clamp(t.barPct, 0, 1) * 100) + "%;background:" + t.barCol + '"></i></span>' +
    "</button>").join("");
  $("#kpis").onclick = e => {
    const b = e.target.closest("[data-kpi]"); if (!b) return;
    const t = tiles[+b.dataset.kpi];
    openDrill(t.drill.t, t.lab + " — " + t.val + " (" + t.sub + ")", t.drill.items);
  };
}

/* =====================================================================
   CHART: burndown with scope line
   ================================================================== */
function renderBurn(m) {
  const host = $("#burn-chart"), bd = S.view.burndown, u = U();
  const F = { rem: u.burn("remaining"), scope: u.burn("scope"), ideal: u.burn("ideal") };
  if (!bd.length) {
    host.innerHTML = '<div class="note">' + (S.view.ctx.isRollup
      ? "A burndown describes one sprint. This view rolls up " + S.view.ctx.members.length +
        " of them, so there is no single line to draw — pick an individual sprint above. " +
        "Everything else on this page is valid across the rollup."
      : "No burndown series in the dataset.") + "</div>";
    return;
  }
  if (u.isItems && !bd.some(d => d[F.rem] != null)) {
    host.innerHTML = '<div class="note">This dataset has no item series on its burndown — it predates the ' +
      'item/point toggle. Re-import it, or run <code>scripts/rebuild_burndown.py</code>, and it will appear. ' +
      'Switch to story points in the filter row to see the chart meanwhile.</div>';
    return;
  }
  const W = cw(host), H = 250, P = { t: 14, r: 16, b: 34, l: 40 };
  const iw = W - P.l - P.r, ih = H - P.t - P.b;
  const maxY = Math.max.apply(null, bd.map(d => Math.max(d[F.scope] || 0, d[F.rem] || 0, d[F.ideal] || 0))) * 1.08;
  const x = i => P.l + (bd.length === 1 ? iw / 2 : (i / (bd.length - 1)) * iw);
  const y = v => P.t + ih - (v / maxY) * ih;
  const c = C(), s = svgEl(W, H);

  yTicks(maxY, 5).forEach(t => {
    s.add('<line class="grid-line" x1="' + P.l + '" y1="' + y(t) + '" x2="' + (W - P.r) + '" y2="' + y(t) + '"/>');
    s.add('<text class="axis-lab" x="' + (P.l - 7) + '" y="' + (y(t) + 3.5) + '" text-anchor="end">' + t + "</text>");
  });
  bd.forEach((d, i) => { if (i % Math.ceil(bd.length / 7) === 0 || i === bd.length - 1)
    s.add('<text class="axis-lab" x="' + x(i) + '" y="' + (H - 14) + '" text-anchor="middle">' + fmtD(d.date) + "</text>"); });
  s.add('<line class="axis-line" x1="' + P.l + '" y1="' + y(0) + '" x2="' + (W - P.r) + '" y2="' + y(0) + '"/>');

  // ideal (a projection — dashed is meaningful here, not decoration)
  const ideal = bd.filter(d => d[F.ideal] != null);
  s.add('<polyline fill="none" stroke="' + c.axis + '" stroke-width="1.5" stroke-dasharray="4 4" points="' +
    ideal.map(d => x(bd.indexOf(d)) + "," + y(d[F.ideal])).join(" ") + '"/>');

  // scope (step line)
  const sc = bd.filter(d => d[F.scope] != null);
  let sp = [];
  sc.forEach((d, k) => { const i = bd.indexOf(d);
    if (k > 0) sp.push(x(i) + "," + y(sc[k - 1][F.scope]));
    sp.push(x(i) + "," + y(d[F.scope])); });
  s.add('<polyline fill="none" stroke="' + c.s2 + '" stroke-width="2" stroke-linejoin="round" points="' + sp.join(" ") + '"/>');

  // remaining area + line
  const rm = bd.filter(d => d[F.rem] != null);
  const pts = rm.map(d => x(bd.indexOf(d)) + "," + y(d[F.rem]));
  s.add('<path d="M' + x(bd.indexOf(rm[0])) + "," + y(0) + " L" + pts.join(" L") + " L" + x(bd.indexOf(rm[rm.length - 1])) + "," + y(0) + 'Z" fill="' + c.s1 + '" opacity="0.10"/>');
  s.add('<polyline fill="none" stroke="' + c.s1 + '" stroke-width="2" stroke-linejoin="round" points="' + pts.join(" ") + '"/>');

  // scope-change markers
  sc.forEach((d, k) => { if (k > 0 && d[F.scope] > sc[k - 1][F.scope]) {
    const i = bd.indexOf(d);
    s.add('<line x1="' + x(i) + '" y1="' + P.t + '" x2="' + x(i) + '" y2="' + y(0) + '" stroke="' + c.s2 + '" stroke-width="1" opacity="0.35"/>');
    s.add('<circle cx="' + x(i) + '" cy="' + y(d[F.scope]) + '" r="4.5" fill="' + c.s2 + '" stroke="' + c.surface + '" stroke-width="2"/>');
    s.add('<text class="ser-lab" x="' + (x(i) + 7) + '" y="' + (y(d[F.scope]) - 7) + '" fill="' + c.s2 + '" style="font-weight:600">+' + u.fmt(d[F.scope] - sc[k - 1][F.scope]) + " " + u.short + " added</text>");
  }});

  // endpoint direct labels
  const lastR = rm[rm.length - 1], lastI = bd.indexOf(lastR);
  s.add('<circle cx="' + x(lastI) + '" cy="' + y(lastR[F.rem]) + '" r="4.5" fill="' + c.s1 + '" stroke="' + c.surface + '" stroke-width="2"/>');
  s.add('<text class="val-lab" x="' + (x(lastI) - 6) + '" y="' + (y(lastR[F.rem]) - 10) + '" text-anchor="end">' + u.fmt(lastR[F.rem]) + " left</text>");

  // hover targets
  bd.forEach((d, i) => {
    const bw = iw / bd.length;
    const rows = [["Remaining", d[F.rem] == null ? "not yet" : u.fmt(d[F.rem]) + " " + u.short],
                  ["Plan says", u.fmt(d[F.ideal]) + " " + u.short],
                  ["Total scope", d[F.scope] == null ? "—" : u.fmt(d[F.scope]) + " " + u.short]];
    const gap = (d[F.rem] != null && d[F.ideal] != null) ? Math.round(d[F.rem] - d[F.ideal]) : null;
    const foot = gap == null ? "" : (gap > 0 ? "<b>" + gap + " " + u.label + " behind plan</b> on this day."
      : gap < 0 ? "<b>" + (-gap) + " " + u.label + " ahead of plan</b>." : "Exactly on plan.");
    s.add('<rect class="hit" x="' + (x(i) - bw / 2) + '" y="' + P.t + '" width="' + bw + '" height="' + ih +
      '" fill="transparent" data-tt="' + esc(ttBox(fmtD(d.date), rows, foot)) + '"/>');
  });

  host.innerHTML =
    '<div class="legend">' +
      '<span><i class="swatch" style="background:' + c.s1 + '"></i>Work remaining (' + u.label + ')</span>' +
      '<span><i class="swatch" style="background:' + c.s2 + '"></i>Total scope</span>' +
      '<span><i class="swatch" style="background:' + c.axis + '"></i>The plan (straight line)</span>' +
    "</div>" + s.out();
  S.tables.burn = { cols: ["Date", "Remaining items", "Plan items", "Scope items",
      "Remaining pts", "Plan pts", "Scope pts", "Gap to plan (" + u.short + ")"],
    rows: bd.map(d => [fmtD(d.date),
      d.remainingItems ?? "—", d.idealItems ?? "—", d.scopeItems ?? "—",
      d.remainingSP ?? "—", n1(d.idealSP), d.scopeSP ?? "—",
      d[F.rem] != null ? Math.round(d[F.rem] - d[F.ideal]) : "—"]) };
  drawTable("burn");
}

/* =====================================================================
   CHART: work distribution by person (replaces the donut)
   ================================================================== */
function renderDist(m, items) {
  const host = $("#dist-chart"), st = STAGE();
  const people = uniq(items.map(i => i.assignee));
  if (!people.length) { host.innerHTML = '<div class="note">No assignees in this selection.</div>'; return; }
  const rows = people.map(p => {
    const mine = items.filter(i => i.assignee === p);
    return { p, mine, seg: st.map(s => ({ s, v: sum(mine.filter(i => i.statusCategory === s.key), U().val),
      items: mine.filter(i => i.statusCategory === s.key) })), tot: sum(mine, U().val) };
  }).sort((a, b) => b.tot - a.tot);

  const W = cw(host), rowH = 34, P = { t: 6, r: 46, b: 22, l: 92 };
  const H = P.t + rows.length * rowH + P.b, iw = W - P.l - P.r;
  const maxT = Math.max.apply(null, rows.map(r => r.tot)) || 1;
  const s = svgEl(W, H), c = C();

  rows.forEach((r, ri) => {
    const yy = P.t + ri * rowH + 6, bh = 17;
    s.add('<text class="ser-lab" x="' + (P.l - 10) + '" y="' + (yy + bh / 2 + 4) + '" text-anchor="end" style="font-weight:600">' + esc(r.p) + "</text>");
    let acc = 0;
    r.seg.forEach(g => {
      if (g.v <= 0) return;
      const x0 = P.l + (acc / maxT) * iw, wpx = (g.v / maxT) * iw - 2;
      if (wpx <= 0) { acc += g.v; return; }
      s.add('<rect class="hit" x="' + x0 + '" y="' + yy + '" width="' + Math.max(wpx, 1) + '" height="' + bh +
        '" rx="3" fill="' + g.s.col + '" data-drill="' + esc(JSON.stringify({ p: r.p, st: g.s.key })) +
        '" data-tt="' + esc(ttBox(r.p + " — " + g.s.label, [[U().isItems ? "Items" : "Story points", U().fmt(g.v)],
          ["Story points", n1(sum(g.items, i => i.storyPoints))],
          ["Share of their work", pct(g.v / (r.tot || 1))]], "Click to list these issues.")) + '"/>');
      if (wpx > 26) s.add('<text class="val-lab" x="' + (x0 + wpx / 2) + '" y="' + (yy + bh / 2 + 4) +
        '" text-anchor="middle" fill="#fff">' + U().fmt(g.v) + "</text>");
      acc += g.v;
    });
    s.add('<text class="axis-lab" x="' + (P.l + (r.tot / maxT) * iw + 8) + '" y="' + (yy + bh / 2 + 4) + '">' + U().fmt(r.tot) + " " + U().short + "</text>");
  });
  s.add('<line class="axis-line" x1="' + P.l + '" y1="' + (P.t + rows.length * rowH) + '" x2="' + (W - P.r) + '" y2="' + (P.t + rows.length * rowH) + '"/>');

  host.innerHTML = '<div class="legend">' + st.map(g =>
    '<span><i class="swatch" style="background:' + g.col + '"></i>' + g.label + "</span>").join("") + "</div>" + s.out();
  host.onclick = e => {
    const t = e.target.closest("[data-drill]"); if (!t) return;
    const d = JSON.parse(t.dataset.drill);
    openDrill(d.p + " — " + d.st.toLowerCase(), "Story points assigned to " + d.p + " currently at stage “" + d.st + "”.",
      items.filter(i => i.assignee === d.p && i.statusCategory === d.st));
  };
  S.tables.dist = { cols: ["Person", "Done (" + U().short + ")", "In progress (" + U().short + ")",
      "Not started (" + U().short + ")", "Total (" + U().short + ")", "Items", "Points"],
    rows: rows.map(r => [r.p, U().fmt(r.seg[0].v), U().fmt(r.seg[1].v), U().fmt(r.seg[2].v),
      U().fmt(r.tot), r.mine.length, n1(sum(r.mine, i => i.storyPoints))]) };
  drawTable("dist");
}

/* =====================================================================
   CHART: lead vs cycle (waiting vs working)
   ================================================================== */
function renderFlowTime(m, items) {
  const host = $("#flowtime-chart");
  const rows = m.closedTimed.map(i => ({ i, lead: days(i.created, i.resolved), cyc: days(i.started, i.resolved) }))
    .map(r => (r.wait = Math.max(0, r.lead - r.cyc), r))
    .sort((a, b) => b.lead - a.lead);
  if (!rows.length) { host.innerHTML = '<div class="note">No completed items with both a start and a resolved date in this selection.</div>'; return; }
  const shown = rows.slice(0, 11), truncated = rows.length - shown.length;
  const c = C(), waitCol = CSSV("--seq-250"), workCol = CSSV("--seq-600");
  const W = cw(host), rowH = 22, P = { t: 8, r: 58, b: 30, l: 74 };
  const H = P.t + shown.length * rowH + P.b, iw = W - P.l - P.r;
  const maxL = Math.max.apply(null, shown.map(r => r.lead)) * 1.02 || 1;
  const s = svgEl(W, H);

  yTicks(maxL, 5).forEach(t => {
    const xx = P.l + (t / maxL) * iw;
    s.add('<line class="grid-line" x1="' + xx + '" y1="' + P.t + '" x2="' + xx + '" y2="' + (P.t + shown.length * rowH) + '"/>');
    s.add('<text class="axis-lab" x="' + xx + '" y="' + (H - 14) + '" text-anchor="middle">' + t + "</text>");
  });
  s.add('<text class="axis-lab" x="' + (P.l + iw / 2) + '" y="' + (H - 1) + '" text-anchor="middle">days from raised to done</text>');

  shown.forEach((r, ri) => {
    const yy = P.t + ri * rowH + 4, bh = 13;
    const wW = (r.wait / maxL) * iw, cW = (r.cyc / maxL) * iw;
    s.add('<text class="ser-lab" x="' + (P.l - 9) + '" y="' + (yy + bh / 2 + 4) + '" text-anchor="end" style="font-variant-numeric:tabular-nums">' + esc(r.i.key) + "</text>");
    const tt = ttBox(r.i.key + " · " + r.i.summary,
      [["Waiting", n1(r.wait) + " days"], ["Being worked", n1(r.cyc) + " days"], ["Total elapsed", n1(r.lead) + " days"],
       ["Actively worked", pct(r.cyc / (r.lead || 1))]],
      "Click to open this issue's detail.");
    if (wW > 0.5) s.add('<rect class="hit" x="' + P.l + '" y="' + yy + '" width="' + Math.max(wW - 2, 1) + '" height="' + bh +
      '" rx="3" fill="' + waitCol + '" data-key="' + esc(r.i.key) + '" data-tt="' + esc(tt) + '"/>');
    s.add('<rect class="hit" x="' + (P.l + wW) + '" y="' + yy + '" width="' + Math.max(cW - 2, 1) + '" height="' + bh +
      '" rx="3" fill="' + workCol + '" data-key="' + esc(r.i.key) + '" data-tt="' + esc(tt) + '"/>');
    s.add('<text class="axis-lab" x="' + (P.l + (r.lead / maxL) * iw + 8) + '" y="' + (yy + bh / 2 + 4) + '">' + n1(r.lead) + "d</text>");
  });

  const totalWait = sum(rows, r => r.wait), totalLead = sum(rows, r => r.lead);
  host.innerHTML = '<div class="legend">' +
    '<span><i class="swatch" style="background:' + waitCol + '"></i>Waiting in a queue</span>' +
    '<span><i class="swatch" style="background:' + workCol + '"></i>Actively being worked</span>' +
    '<span style="margin-left:auto;color:var(--text-primary);font-weight:600">' +
      pct(1 - totalWait / (totalLead || 1)) + " of elapsed time was active work</span></div>" + s.out() +
    (truncated > 0 ? '<div class="note" style="margin-top:6px">Showing the ' + shown.length + " longest of " + rows.length +
      " closed items. The remaining " + truncated + " are in the table view — nothing is hidden, only ranked.</div>" : "");
  host.onclick = e => {
    const t = e.target.closest("[data-key]"); if (!t) return;
    const it = items.find(i => i.key === t.dataset.key);
    openDrill(it.key, "Time breakdown for a single item.", [it]);
  };
  S.tables.flowtime = { cols: ["Issue", "Summary", "Raised", "Started", "Done", "Waiting (d)", "Working (d)", "Total (d)"],
    rows: rows.map(r => [r.i.key, r.i.summary, fmtD(r.i.created), fmtD(r.i.started), fmtD(r.i.resolved),
      n1(r.wait), n1(r.cyc), n1(r.lead)]) };
  drawTable("flowtime");
}

/* =====================================================================
   CHART: work item ageing (sprint-scale bands)
   ================================================================== */
function renderAge(m) {
  const host = $("#age-chart");
  const bands = [{ l: "0–7 days", lo: 0, hi: 7 }, { l: "8–14 days", lo: 7, hi: 14 },
                 { l: "15–30 days", lo: 14, hi: 30 }, { l: "Over 30 days", lo: 30, hi: 1e9 }];
  const ramp = [CSSV("--seq-250"), CSSV("--seq-350"), CSSV("--seq-450"), CSSV("--seq-600")];
  const data = bands.map((b, k) => { const its = m.ages.filter(a => a.age > b.lo && a.age <= b.hi).map(a => a.i);
    return { b, its, col: ramp[k] }; });
  const maxN = Math.max.apply(null, data.map(d => d.its.length)) || 1;
  const W = cw(host), rowH = 32, P = { t: 6, r: 44, b: 26, l: 92 };
  const H = P.t + data.length * rowH + P.b, iw = W - P.l - P.r;
  const s = svgEl(W, H);

  data.forEach((d, ri) => {
    const yy = P.t + ri * rowH + 6, bh = 17, wpx = (d.its.length / maxN) * iw;
    s.add('<text class="ser-lab" x="' + (P.l - 10) + '" y="' + (yy + bh / 2 + 4) + '" text-anchor="end">' + d.b.l + "</text>");
    if (d.its.length) s.add('<rect class="hit" x="' + P.l + '" y="' + yy + '" width="' + Math.max(wpx, 3) + '" height="' + bh +
      '" rx="3" fill="' + d.col + '" data-band="' + ri + '" data-tt="' +
      esc(ttBox("Open " + d.b.l.toLowerCase(), [["Items", d.its.length], ["Story points", n1(sum(d.its, i => i.storyPoints))]],
        d.b.lo >= 14 ? "<b>These have survived a whole sprint.</b> Click to list them." : "Click to list them.")) + '"/>');
    s.add('<text class="val-lab" x="' + (P.l + Math.max(wpx, 3) + 8) + '" y="' + (yy + bh / 2 + 4) + '">' + d.its.length + "</text>");
  });
  s.add('<line class="axis-line" x1="' + P.l + '" y1="' + (P.t + data.length * rowH) + '" x2="' + (W - P.r) + '" y2="' + (P.t + data.length * rowH) + '"/>');
  s.add('<text class="axis-lab" x="' + P.l + '" y="' + (H - 8) + '">number of open items</text>');

  const oldN = data[2].its.length + data[3].its.length;
  host.innerHTML = s.out() + '<div class="note" style="margin-top:8px">' +
    (oldN ? "<b>" + oldN + " open item" + (oldN > 1 ? "s have" : " has") + " outlived a full sprint.</b> Age is a better predictor of an item never finishing than its priority is." :
      "Nothing open has outlived a sprint. That is the healthy state.") + "</div>";
  host.onclick = e => {
    const t = e.target.closest("[data-band]"); if (!t) return;
    const d = data[+t.dataset.band];
    openDrill("Open work aged " + d.b.l.toLowerCase(), d.its.length + " items, " + n1(sum(d.its, i => i.storyPoints)) + " story points.", d.its);
  };
  S.tables.age = { cols: ["Age band", "Items", "Story points", "Keys"],
    rows: data.map(d => [d.b.l, d.its.length, n1(sum(d.its, i => i.storyPoints)), d.its.map(i => i.key).join(", ") || "—"]) };
  drawTable("age");
}

/* =====================================================================
   CHART: predictability (committed vs completed)
   ================================================================== */
function renderPred(m) {
  const host = $("#pred-chart"), h = S.view.history || [];
  if (h.length < 2) { host.innerHTML = '<div class="note">Needs at least two sprints of history.</div>'; return; }
  const W = cw(host), H = 208, P = { t: 16, r: 12, b: 44, l: 34 };
  const iw = W - P.l - P.r, ih = H - P.t - P.b;
  const hc = U().hist("committed"), hd = U().hist("completed");
  const cm = d => (d[hc] != null ? d[hc] : d.committedSP), cp = d => (d[hd] != null ? d[hd] : d.completedSP);
  const maxY = Math.max.apply(null, h.map(d => Math.max(cm(d), cp(d)))) * 1.12;
  const bandW = iw / h.length, bw = Math.min(20, bandW / 2.7);
  const y = v => P.t + ih - (v / maxY) * ih;
  const s = svgEl(W, H), commitCol = CSSV("--seq-250"), doneCol = CSSV("--seq-600");

  yTicks(maxY, 4).forEach(t => {
    s.add('<line class="grid-line" x1="' + P.l + '" y1="' + y(t) + '" x2="' + (W - P.r) + '" y2="' + y(t) + '"/>');
    s.add('<text class="axis-lab" x="' + (P.l - 6) + '" y="' + (y(t) + 3.5) + '" text-anchor="end">' + t + "</text>");
  });
  h.forEach((d, i) => {
    const cx = P.l + bandW * i + bandW / 2;
    const rel = cm(d) ? cp(d) / cm(d) : 0;
    const tt = ttBox(d.sprint, [["Committed", U().fmt(cm(d)) + " " + U().short],
      ["Completed", U().fmt(cp(d)) + " " + U().short],
      ["Hit rate", pct(rel)], ["Items finished", d.throughput]],
      rel >= 0.9 ? "Commitment met." : "<b>" + U().fmt(cm(d) - cp(d)) + " " + U().n(cm(d) - cp(d)) + " short</b> of the commitment.");
    s.add('<rect class="hit" x="' + (cx - bw - 1) + '" y="' + y(cm(d)) + '" width="' + bw + '" height="' + (y(0) - y(cm(d))) +
      '" rx="3" fill="' + commitCol + '" data-tt="' + esc(tt) + '"/>');
    s.add('<rect class="hit" x="' + (cx + 1) + '" y="' + y(cp(d)) + '" width="' + bw + '" height="' + (y(0) - y(cp(d))) +
      '" rx="3" fill="' + doneCol + '" data-tt="' + esc(tt) + '"/>');
    s.add('<text class="axis-lab" x="' + cx + '" y="' + (H - 28) + '" text-anchor="middle">' + esc(d.sprint.replace("Sprint ", "S")) + "</text>");
    s.add('<text class="axis-lab" x="' + cx + '" y="' + (H - 15) + '" text-anchor="middle" style="font-weight:650;fill:' +
      (rel >= 0.9 ? CSSV("--good-ink") : rel >= 0.75 ? CSSV("--warn-ink") : CSSV("--crit-ink")) + '">' + Math.round(rel * 100) + "%</text>");
  });
  s.add('<line class="axis-line" x1="' + P.l + '" y1="' + y(0) + '" x2="' + (W - P.r) + '" y2="' + y(0) + '"/>');

  const rates = h.map(d => cm(d) ? cp(d) / cm(d) : 0);
  const avg = sum(rates) / rates.length;
  const spread = Math.max.apply(null, h.map(cp)) - Math.min.apply(null, h.map(cp));
  host.innerHTML = '<div class="legend"><span><i class="swatch" style="background:' + commitCol + '"></i>Committed</span>' +
    '<span><i class="swatch" style="background:' + doneCol + '"></i>Completed</span>' +
    '<span style="margin-left:auto">% = share of the commitment met</span></div>' + s.out() +
    '<div class="note" style="margin-top:8px">Average hit rate <b>' + pct(avg) + "</b>; completed output swings by <b>" +
    U().fmt(spread) + " " + U().label + "</b> between the best and worst sprint. A commitment set from the last three actuals (<b>" +
    (m.avg3 ? U().fmt(m.avg3) + " " + U().label : "—") + "</b>) would be met far more often than one set from ambition." +
    (U().isItems ? " The forecasting agent sizes this properly — a distribution over simulated sprints rather than a mean of three numbers." : "") + "</div>";
  S.tables.pred = { cols: ["Sprint", "Committed items", "Completed items", "Committed pts", "Completed pts",
      "Hit rate (" + U().short + ")", "Flow efficiency"],
    rows: h.map(d => [d.sprint, d.committedItems ?? "—", d.completedItems ?? d.throughput ?? "—",
      d.committedSP, d.completedSP, pct(cm(d) ? cp(d) / cm(d) : 0),
      d.flowEfficiency != null ? pct(d.flowEfficiency) : "—"]) };
  drawTable("pred");
}

/* =====================================================================
   DORA tiles with sparklines
   ================================================================== */
function spark(vals, w, h, col, goodUp) {
  if (!vals || vals.length < 2) return "";
  const mn = Math.min.apply(null, vals), mx = Math.max.apply(null, vals), rg = (mx - mn) || 1;
  const x = i => (i / (vals.length - 1)) * (w - 4) + 2;
  const y = v => h - 3 - ((v - mn) / rg) * (h - 6);
  const s = svgEl(w, h);
  s.add('<polyline fill="none" stroke="' + col + '" stroke-width="1.75" stroke-linejoin="round" points="' +
    vals.map((v, i) => x(i) + "," + y(v)).join(" ") + '"/>');
  s.add('<circle cx="' + x(vals.length - 1) + '" cy="' + y(vals[vals.length - 1]) + '" r="2.75" fill="' + col + '"/>');
  return s.out();
}
function renderDora(m) {
  const d = S.view.dora, host = $("#dora-body");
  if (!d) { host.innerHTML = '<div class="note">No release metrics in the dataset.</div>'; return; }
  const rows = [
    { lab: "Releases per week", v: n1(d.deploymentFrequencyPerWeek), tr: d.deploymentFrequencyTrend, goodUp: true,
      help: "How often work reaches customers. More often, in smaller pieces, is safer — not riskier." },
    { lab: "Releases that broke something", v: d.changeFailureRatePct + "%", tr: d.changeFailureRateTrend, goodUp: false,
      help: "Share of releases needing a fix or rollback. Elite teams sit under 15%." },
    { lab: "Days from change to customer", v: n1(d.leadTimeForChangesDays) + "d", tr: d.leadTimeForChangesTrend, goodUp: false,
      help: "How long a finished change waits before it is live. This is a pipeline measure, not a coding one." },
    { lab: "Minutes to recover", v: d.mttrMinutes + "m", tr: d.mttrTrend, goodUp: false,
      help: "Time to restore service after a failed release. Recovering fast matters more than never failing." }
  ];
  host.innerHTML = rows.map(r => {
    const t = r.tr || [], first = t[0], last = t[t.length - 1];
    const ch = (first && last) ? (last - first) / Math.abs(first) : 0;
    const improving = r.goodUp ? ch > 0.02 : ch < -0.02;
    const flat = Math.abs(ch) <= 0.02;
    const col = flat ? CSSV("--muted") : improving ? CSSV("--good-ink") : CSSV("--crit-ink");
    const word = flat ? "steady" : improving ? "improving" : "worsening";
    const icon = flat ? "→" : (ch > 0 ? "▲" : "▼");
    return '<div style="display:flex;align-items:center;gap:10px;padding:9px 0;border-top:1px solid var(--grid)" ' +
      'data-tt="' + esc("<b>" + r.lab + "</b><br>" + r.help + "<br><br>Last six sprints: " + t.join(" → ")) + '">' +
      '<div style="flex:1;min-width:0"><div style="font-size:12px;color:var(--text-secondary)">' + esc(r.lab) + "</div>" +
      '<div style="font-size:20px;font-weight:640;letter-spacing:-.02em">' + esc(r.v) +
      ' <span style="font-size:11.5px;font-weight:600;color:' + col + '">' + icon + " " + word + "</span></div></div>" +
      '<div style="flex:none">' + spark(t, 84, 30, CSSV("--s1")) + "</div></div>";
  }).join("");
}

/* =====================================================================
   Team load — work in progress and interruption
   ---------------------------------------------------------------------
   This card replaced an "output per person / overtime hours" pair. Overtime
   was removed because the organisation does not operate overtime, and showing
   it implies a time-tracking regime that does not exist. Output per person
   went with it: on its own, with no counterweight, it is a productivity-per-
   head number, and this dashboard does not measure people.

   Both series here come from the tracker and nowhere else:
     · work in progress — how much is started but unfinished
     · unplanned share  — how much of the sprint arrived after it began
   Together they say whether a team is being overloaded or interrupted, which
   is what the old card was reaching for by proxy.
   ================================================================== */
function renderLoad() {
  const h = S.view.history || [], host = $("#load-body");
  if (h.length < 2) { host.innerHTML = '<div class="note">Needs sprint history.</div>'; return; }

  const mk = (title, key, fmt, col, note) => {
    const vals = h.map(d => d[key]).filter(v => v != null);
    if (vals.length < 2) return "";
    const W = Math.max(180, cw(host)), H = 74, P = { t: 12, r: 8, b: 16, l: 26 };
    const iw = W - P.l - P.r, ih = H - P.t - P.b;
    const mn = Math.min.apply(null, vals.concat([0])), mx = Math.max.apply(null, vals) * 1.12 || 1;
    const x = i => P.l + (i / (vals.length - 1)) * iw, y = v => P.t + ih - ((v - mn) / (mx - mn || 1)) * ih;
    const s = svgEl(W, H);
    s.add('<line class="grid-line" x1="' + P.l + '" y1="' + y(mn) + '" x2="' + (W - P.r) + '" y2="' + y(mn) + '"/>');
    s.add('<path d="M' + x(0) + "," + y(mn) + " L" + vals.map((v, i) => x(i) + "," + y(v)).join(" L") +
      " L" + x(vals.length - 1) + "," + y(mn) + 'Z" fill="' + col + '" opacity="0.10"/>');
    s.add('<polyline fill="none" stroke="' + col + '" stroke-width="2" points="' +
      vals.map((v, i) => x(i) + "," + y(v)).join(" ") + '"/>');
    s.add('<circle cx="' + x(vals.length - 1) + '" cy="' + y(vals[vals.length - 1]) + '" r="3.5" fill="' + col + '"/>');
    s.add('<text class="val-lab" x="' + (W - P.r) + '" y="' + (y(vals[vals.length - 1]) - 8) +
      '" text-anchor="end">' + fmt(vals[vals.length - 1]) + "</text>");
    s.add('<text class="axis-lab" x="' + P.l + '" y="' + (H - 3) + '">' + esc(h[0].sprint.replace("Sprint ", "S")) + "</text>");
    s.add('<text class="axis-lab" x="' + (W - P.r) + '" y="' + (H - 3) + '" text-anchor="end">' +
      esc(h[h.length - 1].sprint.replace("Sprint ", "S")) + "</text>");
    return '<div style="margin-bottom:12px" data-tt="' + esc("<b>" + title + "</b><br>" + note) + '">' +
      '<div style="font-size:12px;color:var(--text-secondary);font-weight:600">' + esc(title) + "</div>" +
      s.out() + "</div>";
  };

  const wip = h.map(d => d.wipItems).filter(v => v != null);
  const unp = h.map(d => d.unplannedItems).filter(v => v != null);
  const thr = h.map(d => d.completedItems != null ? d.completedItems : d.throughput).filter(v => v != null);

  const body =
    mk("Work in progress (items)", "wipItems", v => n1(v), CSSV("--s1"),
       "Items started but not finished at the end of each sprint. Rising work in progress with " +
       "flat completion means work is being started rather than finished, which slows everything " +
       "already in flight. It comes from issue status, not from anyone's hours.") +
    mk("Unplanned work (items)", "unplannedItems", v => n1(v), CSSV("--s2"),
       "Items that arrived after the sprint began. A team absorbing steady interruption cannot " +
       "hold a commitment, and that is a planning and triage problem rather than a capacity one.");

  if (!body) { host.innerHTML = '<div class="note">Sprint history does not carry work-in-progress or unplanned counts yet. Re-import, or run the fetcher, and they will appear.</div>'; return; }

  const rising = (a) => a.length >= 3 && a[a.length - 1] > a[0];
  const wipUp = rising(wip), unpUp = rising(unp), thrUp = rising(thr);
  host.innerHTML = body + '<div class="note">' + (
    wipUp && !thrUp
      ? "<b>Work in progress is rising while completion is not.</b> More is being started than finished — cap work in progress per person before adding anything else."
      : unpUp
      ? "<b>Interruption is rising.</b> The commitment is being displaced by work that arrives after planning; fix the intake, not the effort."
      : wipUp
      ? "Work in progress and completion are rising together, which is the healthy version of a busier team."
      : "Load and interruption are both steady. Nothing here suggests the team is being overloaded."
  ) + "</div>";
}

/* =====================================================================
   Business value
   ================================================================== */
function renderValue(m) {
  const host = $("#value-body"), cur = S.view.meta.currency;
  const h = S.view.history || [];
  const items = m.valueItems.slice().sort((a, b) => b.businessValue - a.businessValue);
  const unpriced = m.done.length - items.length;
  host.innerHTML =
    '<div class="sparkwrap" style="align-items:flex-end;justify-content:space-between">' +
      '<div><div class="hero">' + money(m.value, cur) + "</div>" +
      '<div class="note" style="margin-top:2px">estimated impact of work closed this sprint</div></div>' +
      "<div>" + spark(h.map(d => d.valueDelivered).filter(v => v != null), 110, 40, CSSV("--s3")) +
      '<div class="note" style="text-align:right">last 6 sprints</div></div>' +
    "</div>" +
    '<div class="vgrid" style="margin-top:12px"><div>' + items.map(i =>
      '<button class="linkish" data-vkey="' + esc(i.key) + '" style="display:block;text-align:left;text-decoration:none;width:100%">' +
      '<div style="display:flex;justify-content:space-between;gap:12px;padding:7px 0;border-top:1px solid var(--grid)">' +
      '<span style="color:var(--text-primary);font-weight:500;font-size:12.5px">' + esc(i.summary) + "</span>" +
      '<span class="mono" style="color:var(--text-primary);font-weight:650;white-space:nowrap">' + money(i.businessValue, cur) + "</span></div>" +
      '<div class="note" style="text-align:left;padding-bottom:5px">' + esc(i.key) + " · basis: " + esc(i.valueBasis || "none recorded") + "</div>" +
      "</button>").join("") + "</div>" +
    '<div class="note" style="border-top:1px solid var(--grid);padding-top:9px">' +
      "<b>Read this as a floor, not a total.</b> " + unpriced + " of the " + m.done.length +
      " completed items carry no value estimate, so their contribution is counted as zero. Figures are forecasts made at " +
      "planning time and are not reconciled against booked revenue — the basis line under each item is what to challenge.</div></div>";
  host.onclick = e => {
    const b = e.target.closest("[data-vkey]"); if (!b) return;
    const it = S.view.issues.find(i => i.key === b.dataset.vkey);
    openDrill(it.key, "Value estimate basis: " + (it.valueBasis || "none recorded"), [it]);
  };
}

/* =====================================================================
   Releases
   ================================================================== */
function renderRel(m) {
  const host = $("#rel-body"), rels = S.view.releases || [];
  if (!rels.length) {
    host.innerHTML = '<div class="note">' + (S.view.ctx.isRollup
      ? "Release progress is tied to a single sprint's snapshot; pick one sprint above to see it."
      : "No releases in the dataset.") + "</div>";
    return;
  }
  const now = asOf();
  host.innerHTML = rels.map(r => {
    const p = r.scopeIssues ? (r.doneIssues || 0) / r.scopeIssues : 0;
    const dLeft = days(now, r.targetDate);
    const cls = /risk/i.test(r.status) ? "c-warn" : /late|off/i.test(r.status) ? "c-crit" : "c-good";
    const ic = /risk/i.test(r.status) ? "▲" : /late|off/i.test(r.status) ? "■" : "●";
    return '<div class="rel" data-tt="' + esc("<b>" + r.name + "</b><br>" + (r.doneIssues || 0) + " of " + r.scopeIssues +
      " issues complete, " + (dLeft >= 0 ? Math.round(dLeft) + " days to target" : Math.abs(Math.round(dLeft)) + " days past target") +
      ".<br>" + (r.note || "")) + '">' +
      '<div><div style="font-weight:650">' + esc(r.name) + '</div><div class="note">' + fmtD(r.targetDate) +
      " · " + (r.doneIssues || 0) + "/" + r.scopeIssues + " issues · " +
      (dLeft >= 0 ? Math.round(dLeft) + "d left" : Math.abs(Math.round(dLeft)) + "d overdue") + "</div></div>" +
      '<span class="chip ' + cls + '"><span aria-hidden="true">' + ic + "</span>" + esc(r.status) + "</span>" +
      '<div class="progress"><i style="width:' + Math.round(p * 100) + '%"></i></div>' +
      (r.note ? '<div class="note" style="grid-column:1/-1">' + esc(r.note) + "</div>" : "") +
      "</div>";
  }).join("");
}

/* =====================================================================
   Risk register (computed)
   ================================================================== */
/** Committed volume for the current sprint, in the active unit. */
function commitU(m) {
  if (!m.cur) return m.totalU;
  const k = U().hist("committed");
  return m.cur[k] != null ? m.cur[k] : m.cur.committedSP;
}

function renderRisk(m, items) {
  const host = $("#risk-body"), risks = [];
  const push = (sev, t, d, a, its) => risks.push({ sev, t, d, a, its: its || [] });
  const rank = { critical: 0, serious: 1, warning: 2, info: 3, good: 4 };

  m.critical.filter(i => days(i.created, asOf()) > 14).forEach(i =>
    push("critical", i.key + " — highest priority, " + Math.round(days(i.created, asOf())) + " days old",
      i.summary + (i.flagged ? " It is also flagged as blocked." : ""),
      "Give it a named owner and a decision deadline this week, or explicitly drop its priority. Leaving it at the top of the list without movement corrodes the priority scheme for everything else.", [i]));

  if (m.overdue.length)
    push(m.overdue.length >= 3 ? "serious" : "warning", m.overdue.length + " open item" + (m.overdue.length > 1 ? "s are" : " is") + " past its due date",
      "Total " + n1(sum(m.overdue, i => i.storyPoints)) + " story points. Due dates that pass without a conversation stop being believed.",
      "Re-date or close each one at the next stand-up. A due date is a promise to someone outside the team.", m.overdue);

  if (m.scopeAddedPct > 0.08)
    push("warning", "Scope grew " + pct(m.scopeAddedPct) + " after the sprint started",
      m.added.length + (m.added.length === 1 ? " item, " : " items, ") + n1(m.addedSP) +
      (m.addedSP === 1 ? " story point" : " story points") + ", added mid-flight" +
      (m.paceGap != null && m.paceGap < 0 ? " while delivery was already behind the clock." : "."),
      "Adopt a one-in-one-out rule: anything added mid-sprint displaces work of equal size, and the swap is recorded so the burndown stays honest.", m.added);

  if (m.flowEff != null && m.flowEff < 0.45)
    push("warning", "Only " + pct(m.flowEff) + " of elapsed time is active work",
      "The rest is queue time — waiting for review, for a decision, or for a person to free up.",
      "Set a review service level (for example, any item in review is picked up within four working hours) and cap work in progress per person. This is usually the fastest available improvement to delivery speed.", m.closedTimed);

  const oldOpen = m.ages.filter(a => a.age > 14).map(a => a.i);
  if (oldOpen.length >= 2)
    push("warning", oldOpen.length + " open items have outlived a full sprint",
      "Ageing work is the strongest available predictor of work that never finishes.",
      "Start every stand-up with the oldest item rather than the newest. Anything past 30 days gets an explicit keep-or-kill decision.", oldOpen);

  if (m.flagged.length)
    push("serious", m.flagged.length + " items are flagged as blocked",
      m.flagged.map(i => i.key).join(", ") + ". Blocked work still consumes capacity in status meetings while producing nothing.",
      "Each blocker needs a named person outside the team and a date. If neither exists, the item should be moved out of the sprint.", m.flagged);

  const h = S.view.history || [];
  if (h.length >= 4 && m.avg3 && m.cur && commitU(m) > m.avg3 * 1.25)
    push("warning", "The commitment is " + Math.round((commitU(m) / m.avg3 - 1) * 100) + "% above recent actual delivery",
      "Committed " + U().fmt(commitU(m)) + " " + U().n(commitU(m)) + " against a three-sprint average of " +
      U().fmt(m.avg3) + " " + U().n(m.avg3) + ".",
      "Plan the next sprint from the trailing three-sprint average. Over-committing manufactures a failure narrative around a team that is delivering at its normal rate.", []);

  if (m.flowEff != null && m.avgCycle != null && m.avgCycle <= 3 && m.doneCount >= 3)
    push("good", "Closed items moved quickly once started — average " + n1(m.avgCycle) + " days of active work",
      "Hand-offs and work-in-progress control are working on the items that get picked up.",
      "Keep this. The constraint is upstream of the team, not inside it.", m.closedTimed);

  risks.sort((a, b) => rank[a.sev] - rank[b.sev]);
  const chip = { critical: ["c-crit", "■", "Critical"], serious: ["c-serious", "▲", "Serious"],
                 warning: ["c-warn", "▲", "Watch"], info: ["c-info", "i", "Note"], good: ["c-good", "✓", "Working well"] };
  host.innerHTML = risks.slice(0, 9).map((r, ix) => {
    const [cls, ic, lab] = chip[r.sev];
    return '<div class="riskrow"><div class="rh"><span class="chip ' + cls + '"><span aria-hidden="true">' + ic + "</span>" + lab + "</span>" +
      '<span class="rt">' + esc(r.t) + "</span></div>" +
      '<div class="rd">' + esc(r.d) + "</div>" +
      '<div class="ra"><b>Do this:</b> ' + esc(r.a) + "</div>" +
      (r.its.length ? '<div><button class="linkish" data-risk="' + ix + '">Inspect the ' + r.its.length + " issue" + (r.its.length > 1 ? "s" : "") + "</button></div>" : "") +
      "</div>";
  }).join("") || '<div class="note">No risks triggered against the current filters.</div>';
  host.onclick = e => {
    const b = e.target.closest("[data-risk]"); if (!b) return;
    const r = risks[+b.dataset.risk];
    openDrill(r.t, r.a, r.its);
  };
}

/* =====================================================================
   table views
   ================================================================== */
function drawTable(key) {
  const t = S.tables[key], host = $("#" + key + "-table");
  if (!t || !host) return;
  host.innerHTML = "<table class='tv'><thead><tr>" + t.cols.map((c, i) =>
    "<th" + (i ? ' class="num"' : "") + ">" + esc(c) + "</th>").join("") + "</tr></thead><tbody>" +
    t.rows.map(r => "<tr>" + r.map((v, i) => "<td" + (i ? ' class="num"' : "") + ">" + esc(v) + "</td>").join("") + "</tr>").join("") +
    "</tbody></table>";
}
document.addEventListener("click", e => {
  const b = e.target.closest("[data-table]"); if (!b) return;
  const k = b.dataset.table, on = b.getAttribute("aria-pressed") !== "true";
  b.setAttribute("aria-pressed", String(on));
  $("#" + k + "-table").classList.toggle("hidden", !on);
  $("#" + k + "-chart").classList.toggle("hidden", on);
});

/* =====================================================================
   drill-down panel
   ================================================================== */
function issueRow(i) {
  const age = days(i.created, asOf()), cyc = days(i.started, i.resolved), lead = days(i.created, i.resolved);
  const chips = [];
  if (i.flagged) chips.push('<span class="chip c-crit"><span aria-hidden="true">■</span>Blocked</span>');
  if (i.addedMidSprint) chips.push('<span class="chip c-warn"><span aria-hidden="true">+</span>Added mid-sprint</span>');
  if (i.dueDate && D(i.dueDate) < D(asOf()) && i.statusCategory !== "Done")
    chips.push('<span class="chip c-serious"><span aria-hidden="true">▲</span>Overdue</span>');
  if (i.statusCategory === "Done") chips.push('<span class="chip c-good"><span aria-hidden="true">✓</span>Done</span>');
  const meta = [["Status", i.status], ["Owner", i.assignee], ["Points", i.storyPoints], ["Priority", i.priority],
    ["Epic", i.epic], ["Raised", fmtD(i.created)], ["Due", fmtD(i.dueDate)],
    i.statusCategory === "Done" ? ["Closed", fmtD(i.resolved)] : ["Age", Math.round(age) + "d"]]
    .filter(r => r[1] != null && r[1] !== "" && r[1] !== "—");
  return '<div class="issue"><div class="i-top"><span class="i-key">' +
    (safeUrl(i.url) ? '<a href="' + esc(safeUrl(i.url)) + '" target="_blank" rel="noopener noreferrer">' +
      esc(i.key) + "</a>" : esc(i.key)) +
    "</span>" + chips.join("") + '</div><div class="i-sum">' + esc(i.summary) + "</div>" +
    '<div class="i-meta">' + meta.map(r => "<span>" + esc(r[0]) + ": <b>" + esc(r[1]) + "</b></span>").join("") +
    (lead != null ? "<span>Elapsed: <b>" + n1(lead) + "d</b> (worked " + n1(cyc) + "d, waited " + n1(Math.max(0, lead - cyc)) + "d)</span>" : "") +
    "</div>" + (i.businessValue ? '<div class="note">Value estimate ' + money(i.businessValue, S.view.meta.currency) +
      " — " + esc(i.valueBasis || "no basis recorded") + "</div>" : "") + "</div>";
}
function openDrill(title, sub, items) {
  // Remember what opened this so focus can go back there on close. Dumping the
  // user at the top of the document is disorienting for anyone navigating by
  // keyboard or screen reader — WCAG 2.4.3.
  S.drillOpener = document.activeElement;
  S.lastDrill = items || [];
  $("#p-title").textContent = title;
  $("#p-sub").innerHTML = esc(sub || "") + (items && items.length ? " · <b>" + items.length + " issue" + (items.length > 1 ? "s" : "") +
    ", " + n1(sum(items, i => i.storyPoints)) + " points</b>" : "");
  $("#p-body").innerHTML = (items && items.length) ? items.map(issueRow).join("")
    : '<div class="note" style="padding:18px 0">Nothing matches — which is usually good news.</div>';
  $("#panel").classList.add("on"); $("#scrim").classList.add("on");
  $("#p-close").focus();
}
function closeDrill() {
  $("#panel").classList.remove("on");
  $("#scrim").classList.remove("on");
  const back = S.drillOpener;
  S.drillOpener = null;
  if (back && document.contains(back) && back.focus) back.focus();
  else { const k = $("#kpis button"); if (k) k.focus(); }
}
$("#p-close").onclick = closeDrill; $("#p-done").onclick = closeDrill; $("#scrim").onclick = closeDrill;
document.addEventListener("keydown", e => { if (e.key === "Escape") { closeDrill(); $("#modal").classList.remove("on"); } });

/* =====================================================================
   export
   ================================================================== */
function toCSV(rows) {
  return rows.map(r => r.map(v => {
    const s = v == null ? "" : String(v);
    return /[",\n]/.test(s) ? '"' + s.replace(/"/g, '""') + '"' : s;
  }).join(",")).join("\n");
}
function download(name, text, mime) {
  const b = new Blob([text], { type: mime || "text/plain;charset=utf-8" });
  const a = document.createElement("a");
  a.href = URL.createObjectURL(b); a.download = name; a.click();
  setTimeout(() => URL.revokeObjectURL(a.href), 2000);
}
const ISSUE_COLS = ["key", "summary", "type", "status", "statusCategory", "assignee", "storyPoints", "priority",
  "epic", "created", "started", "resolved", "dueDate", "flagged", "addedMidSprint", "businessValue", "valueBasis", "labels", "url"];
function issuesCSV(items) {
  return toCSV([ISSUE_COLS].concat(items.map(i => ISSUE_COLS.map(c =>
    c === "labels" ? (i.labels || []).join(";") : i[c]))));
}
$("#btn-export").onclick = () => download((S.view.meta.sprintName || "sprint").replace(/\W+/g, "-").toLowerCase() + "-issues.csv", issuesCSV(filtered()), "text/csv");
$("#p-csv").onclick = () => download("drill-down.csv", issuesCSV(S.lastDrill), "text/csv");
$("#btn-print").onclick = () => print();

/* =====================================================================
   theme
   ================================================================== */
function setTheme(t) {
  document.documentElement.dataset.theme = t;
  $("#btn-theme").textContent = t === "dark" ? "Light" : "Dark";
  render();
}
$("#btn-theme").onclick = () => setTheme(document.documentElement.dataset.theme === "dark" ? "light" : "dark");
if (matchMedia("(prefers-color-scheme: dark)").matches) document.documentElement.dataset.theme = "dark";

/* =====================================================================
   tile visibility — one page, two audiences
   ---------------------------------------------------------------------
   An executive and the team that did the work do not need the same tiles,
   but they must not be given different numbers. Hiding a tile changes what
   is shown and nothing that is computed: every figure still comes from the
   same derive() over the same filtered issues, so a tile that reappears
   agrees with the one next to it.

   Both presets keep "What this sprint means". A view without the narrative
   is a wall of charts, which is the thing this page exists to replace.

   State travels in the URL (?view= / ?tiles=) and, for a saved copy, in a
   data-tiles attribute on <html>. Deliberately not in browser storage: the
   intended distribution method is emailing the file, and stored state does
   not survive that. This file uses no browser storage of any kind — the
   security suite bans those APIs by name from the whole source, comments
   included, which is why they are not written out here either.
   ================================================================== */
const TILES = [
  { id: "c-exec",  label: "What this sprint means" },
  { id: "c-kpis",  label: "Headline numbers" },
  { id: "c-burn",  label: "Burndown, with scope changes" },
  { id: "c-dist",  label: "Where each person's work sits" },
  { id: "c-flow",  label: "How long work takes, and what waits" },
  { id: "c-age",   label: "How long open work has been sitting" },
  { id: "c-pred",  label: "Can we trust the forecast?" },
  { id: "c-dora",  label: "Release quality & speed" },
  { id: "c-load",  label: "Team load" },
  { id: "c-value", label: "Business value delivered" },
  { id: "c-rel",   label: "Releases & milestones" },
  { id: "c-risk",  label: "Risks and what to do about them" }
];
const TILE_IDS = TILES.map(t => t.id);

/** Which tiles each audience gets. Taken from the agent's own two report
 *  templates rather than invented here — agent/templates/exec-brief.md asks
 *  will we make it / what changed / what it is worth / what we need from you;
 *  team-report.md asks where we are / unblock / ageing / flow / what to
 *  commit next. A printed view and the agent's brief for the same audience
 *  disagreeing about what matters is a worse failure than either being
 *  slightly wrong on its own. */
const PRESETS = {
  all:  TILE_IDS.slice(),
  exec: ["c-exec", "c-kpis", "c-pred", "c-dora", "c-value", "c-rel", "c-risk"],
  team: ["c-exec", "c-kpis", "c-burn", "c-dist", "c-flow", "c-age", "c-pred", "c-load", "c-risk"]
};
const PRESET_LABEL = { all: "Everything", exec: "Executive", team: "Team" };

/** The preset whose set matches exactly, or "custom". Compared as sets so
 *  ticking a box back to a preset's shape re-selects that preset. */
function presetOf(shown) {
  for (const k of Object.keys(PRESETS)) {
    const p = PRESETS[k];
    if (p.length === shown.size && p.every(id => shown.has(id))) return k;
  }
  return "custom";
}

function setShown(ids) {
  S.shown = new Set(ids.filter(id => TILE_IDS.indexOf(id) >= 0));
  applyTiles();
  syncTileUrl();
}

/** Show or hide each tile. Nothing here recomputes — render() has already
 *  produced every tile's content whether it is on screen or not. */
function applyTiles() {
  TILE_IDS.forEach(id => {
    const el = $("#" + id);
    if (el) el.classList.toggle("hidden", !S.shown.has(id));
  });
  const name = presetOf(S.shown), hidden = TILE_IDS.length - S.shown.size;
  const btn = $("#btn-view");
  btn.textContent = hidden ? "Tiles · " + (name === "custom" ? S.shown.size + " of " + TILE_IDS.length
                                                             : PRESET_LABEL[name]) : "Tiles";
  btn.title = hidden ? hidden + " of " + TILE_IDS.length + " tiles hidden in this view"
                     : "Choose which tiles this view shows";
  paintPicker();
}

/** Reflect state into the URL so a hosted view can be linked. replaceState
 *  throws on some file:// origins; a saved copy carries the view in its
 *  data-tiles attribute instead, so failing here costs nothing. */
function syncTileUrl() {
  try {
    const u = new URL(location.href), name = presetOf(S.shown);
    u.searchParams.delete("view"); u.searchParams.delete("tiles");
    if (name !== "all") {
      if (name === "custom") u.searchParams.set("tiles", [...S.shown].join(","));
      else u.searchParams.set("view", name);
    }
    history.replaceState(null, "", u);
  } catch (e) { /* file:// — the attribute on a saved copy covers this */ }
}

function buildPicker() {
  const pop = $("#view-pop");
  pop.innerHTML =
    '<h4 id="vp-h">Tiles in this view</h4>' +
    '<div class="note">Hiding a tile changes what is shown, never what is counted. ' +
    'Both presets keep the narrative.</div>' +
    '<div class="vp-presets" role="group" aria-label="Preset views">' +
      Object.keys(PRESETS).map(k =>
        '<button type="button" data-preset="' + esc(k) + '" aria-pressed="false">' +
        esc(PRESET_LABEL[k]) + "</button>").join("") +
    "</div>" +
    '<div class="vp-list">' +
      TILES.map(t => '<label><input type="checkbox" data-tile="' + esc(t.id) + '">' +
        "<span>" + esc(t.label) + "</span></label>").join("") +
    "</div>" +
    '<div class="vp-count" id="vp-count"></div>' +
    '<div class="vp-actions">' +
      '<button type="button" class="btn" id="vp-save">Save this view as a file</button>' +
    "</div>";

  pop.querySelectorAll("[data-preset]").forEach(b =>
    b.onclick = () => setShown(PRESETS[b.dataset.preset]));
  pop.querySelectorAll("[data-tile]").forEach(c =>
    c.onchange = () => {
      const next = new Set(S.shown);
      c.checked ? next.add(c.dataset.tile) : next.delete(c.dataset.tile);
      setShown([...next]);
    });
  $("#vp-save").onclick = saveView;
}

/** Push state into the picker's controls. Split from applyTiles so the
 *  checkboxes cannot drift from the tiles they describe. */
function paintPicker() {
  const pop = $("#view-pop");
  if (!pop.firstChild) return;
  const name = presetOf(S.shown);
  pop.querySelectorAll("[data-preset]").forEach(b =>
    b.setAttribute("aria-pressed", String(b.dataset.preset === name)));
  pop.querySelectorAll("[data-tile]").forEach(c => { c.checked = S.shown.has(c.dataset.tile); });
  const hidden = TILE_IDS.filter(id => !S.shown.has(id));
  // Name what is hidden rather than only counting it. A view that quietly
  // drops a tile reads as a complete page to whoever receives it.
  $("#vp-count").innerHTML = hidden.length
    ? "<b>" + hidden.length + " hidden:</b> " +
      esc(hidden.map(id => TILES.find(t => t.id === id).label).join(", "))
    : "All " + TILE_IDS.length + " tiles shown.";
}

function openPicker(on) {
  $("#view-pop").classList.toggle("hidden", !on);
  $("#btn-view").setAttribute("aria-expanded", String(on));
  if (on) { paintPicker(); $("#view-pop").querySelector("[data-preset]").focus(); }
  else $("#btn-view").focus();
}
$("#btn-view").onclick = () => openPicker($("#view-pop").classList.contains("hidden"));
addEventListener("keydown", e => {
  if (e.key === "Escape" && !$("#view-pop").classList.contains("hidden")) openPicker(false);
});
addEventListener("mousedown", e => {
  if (!$("#view-pop").classList.contains("hidden") && !e.target.closest(".viewpick")) openPicker(false);
});

/** Write a standalone copy of this page with the current view and the
 *  current data baked in.
 *
 *  The data matters as much as the view: after an upload the dataset lives
 *  in memory, not in the seed script, so serialising the document alone
 *  would hand someone a file that silently reverted to the demo sprint —
 *  a copy that looks right and is about the wrong company.
 */
function saveView() {
  const root = document.documentElement.cloneNode(true);
  root.setAttribute("data-tiles", [...S.shown].join(","));
  root.setAttribute("data-theme", document.documentElement.dataset.theme || "light");

  const seed = root.querySelector("#seed-data");
  seed.textContent = JSON.stringify(S.data);

  // Drop rendered output. Every one of these is rewritten unconditionally by
  // render() on load, so clearing them costs nothing and keeps the copy from
  // carrying a second, stale set of charts.
  ["#exec-verdict", "#exec-basis", "#exec-list", "#kpis", "#ctxbar", "#f-chips", "#foot",
   "#burn-chart", "#burn-table", "#dist-chart", "#dist-table", "#flowtime-chart", "#flowtime-table",
   "#age-chart", "#age-table", "#pred-chart", "#pred-table",
   "#dora-body", "#load-body", "#value-body", "#rel-body", "#risk-body", "#p-body", "#view-pop"
  ].forEach(sel => { const el = root.querySelector(sel); if (el) el.innerHTML = ""; });

  const name = presetOf(S.shown);
  const stem = (S.view && S.view.meta && S.view.meta.sprintName || "sprint").replace(/\W+/g, "-").toLowerCase();
  download(stem + "-" + (name === "custom" ? "custom" : name) + "-view.html",
    "<!DOCTYPE html>\n" + root.outerHTML, "text/html;charset=utf-8");
  openPicker(false);
}

/* =====================================================================
   master render
   ================================================================== */
let rafT;
function render() {
  S.view = buildView();
  renderContextBar();
  const items = filtered(), m = derive(items);
  renderHeader(m); renderFilters(); renderExec(m); renderKpis(m);
  renderBurn(m); renderDist(m, items); renderFlowTime(m, items); renderAge(m);
  renderPred(m); renderDora(m); renderLoad(); renderValue(m); renderRel(m); renderRisk(m, items);
  applyTiles();
  const empty = !S.view.issues.length && S.view.ctx && !S.view.ctx.isRollup;
  $("#grid").style.opacity = empty ? "0.45" : "";
  const nctx = (S.data.contexts || []).length;
  $("#foot").innerHTML = "Generated from " + esc(S.data.meta.sourceLabel || "loaded data") + " · " +
    S.data.issues.length + " issues across " + nctx + " sprint" + (nctx === 1 ? "" : "s") +
    " · showing " + S.view.issues.length + " · measured in " + U().label +
    " · rendered " + new Date().toLocaleString() +
    "<br>Every figure on this page traces back to an issue. Click anything that looks wrong.";
}
addEventListener("resize", () => { clearTimeout(rafT); rafT = setTimeout(render, 180); });

/* =====================================================================
   live mode — optional, and absent by default
   ---------------------------------------------------------------------
   The page never talks to Jira or Asana. It talks to a small server on the
   same origin, which someone has deliberately started (scripts/serve_live.py).
   If nothing answers, everything below silently does not exist and the file
   keeps working offline from whatever contexts were bundled into it.
   ================================================================== */
async function probeLive() {
  // Only meaningful over http(s). On file:// the fetch is rejected at the
  // scheme level and the browser logs it regardless of any catch, so don't
  // ask — an emailed copy of this file should produce a silent console.
  if (!/^https?:$/.test(location.protocol)) return;
  try {
    const r = await fetch("api/contexts", { cache: "no-store" });
    if (!r.ok) return;
    const j = await r.json();
    if (!j || !Array.isArray(j.contexts)) return;
    S.live = { source: j.source || "server", label: j.label || "live server" };

    // Merge in sprints the bundle does not contain, as stubs. Their issues are
    // fetched only when someone selects them — pulling six months of every
    // board up front is how a "live" dashboard becomes a slow one.
    const known = new Set(S.data.contexts.map(c => c.id));
    let added = 0;
    j.contexts.forEach(c => {
      if (known.has(c.id)) return;
      S.data.contexts.push(Object.assign({ stub: true, issueCount: c.issueCount || 0 }, c));
      S.data.byContext[c.id] = { burndown: [], history: [], releases: [], dora: null };
      added++;
    });
    if (added) render();
    else renderContextBar();
  } catch (e) { /* no server; this is the normal case */ }
}

async function loadContext(id) {
  const bar = $("#ctxbar");
  bar.classList.add("loading");
  try {
    const r = await fetch("api/context?id=" + encodeURIComponent(id), { cache: "no-store" });
    if (!r.ok) throw new Error("server returned " + r.status);
    const j = await r.json();
    const ctx = S.data.contexts.find(c => c.id === id);
    if (ctx) { Object.assign(ctx, j.context || {}); delete ctx.stub; }
    const fresh = (j.issues || []).map(i => {
      const o = normaliseIssue(i, S.data.meta);
      o.contextId = id;                       // never let normalise() re-tag these
      return o;
    });
    S.data.issues = S.data.issues.filter(i => i.contextId !== id).concat(fresh);
    const c2 = S.data.contexts.find(c => c.id === id);
    if (c2) c2.issueCount = fresh.length;
    S.data.byContext[id] = {
      burndown: j.burndown || [], history: j.history || [],
      releases: j.releases || [], dora: j.dora || null
    };
    S.ctx = id;
    render();
  } catch (e) {
    alert("Could not load that sprint from the live server:\n\n" + e.message +
          "\n\nThe bundled sprints still work.");
  } finally { bar.classList.remove("loading"); }
}

/** The only way the context changes. Fetches first if the target is a stub. */
function selectContext(id) {
  const c = (S.view ? S.view.contexts : S.data.contexts).find(x => x.id === id);
  const needsFetch = c && !c.isRollup && S.live &&
    (c.stub || !S.data.issues.some(i => i.contextId === id));
  if (needsFetch) { loadContext(id); return; }
  S.ctx = id;
  render();
}

async function refreshLive() {
  const id = S.ctx;
  if (id && id.indexOf(ROLL) !== 0) await loadContext(id);
}

/* =====================================================================
   public API — consumed by import.js
   ================================================================== */
window.DVD = {
  get data() { return S.data; },
  normalise: normalise,
  render: render,
  esc: esc, D: D, days: days, fmtD: fmtD, sum: sum, uniq: uniq, n1: n1,
  toCSV: toCSV, download: download, issuesCSV: issuesCSV, ISSUE_COLS: ISSUE_COLS,
  workingDays: workingDays,
  /** Hooks for tests/perf.py. Not used by the page itself. */
  debug: {
    contexts: () => selectableContexts(),
    view: () => S.view,
    tiles: () => [...S.shown],
    tileIds: () => TILE_IDS.slice(),
    presets: () => PRESETS,
    setTiles: ids => setShown(ids),
    selectContext: id => { S.ctx = id; render(); },
    setFilter: (k, v) => { S.filters[k] = v; render(); },
    setUnit: u => { S.unit = u; render(); },
    render: () => render()
  },
  /** Replace the working dataset and repaint everything. */
  applyDataset: function (d) {
    S.data = normalise(d);
    S.ctx = S.data.defaultContextId;
    S.filters = { assignee: "", epic: "", type: "", status: "", q: "" };
    $$("select[data-built]").forEach(el => el.dataset.built = "0");
    const q = $("#f-q"); if (q) q.value = "";
    render();
  }
};

/* boot */
S.data = normalise(JSON.parse(document.getElementById("seed-data").textContent));
const qs = new URLSearchParams(location.search).get("data");
S.ctx = S.data.defaultContextId;

/* Which tiles to show. An explicit ?tiles= or ?view= wins, then a saved
 * copy's data-tiles attribute, then everything. An unrecognised or empty
 * selection falls back to everything on purpose: a blank page reads as a
 * broken file, not as a deliberate view. */
(function initTiles() {
  const sp = new URLSearchParams(location.search);
  const t = sp.get("tiles"), v = sp.get("view");
  const attr = document.documentElement.getAttribute("data-tiles");
  let ids;
  if (t) ids = t.split(",");
  else if (v && PRESETS[v]) ids = PRESETS[v];
  else if (attr !== null) ids = attr.split(",");
  else ids = PRESETS.all;
  S.shown = new Set(ids.map(s => s.trim()).filter(id => TILE_IDS.indexOf(id) >= 0));
  if (!S.shown.size) S.shown = new Set(PRESETS.all);
  buildPicker();
})();
if (qs) {
  fetch(qs).then(r => r.json()).then(d => { S.data = normalise(d); S.ctx = d.defaultContextId; render(); })
    .catch(() => render())
    .then(probeLive);
} else { render(); probeLive(); }

})();
