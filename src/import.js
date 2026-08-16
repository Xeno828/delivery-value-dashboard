/* ============================================================================
   import.js — turn an arbitrary export file into a dashboard dataset
   ----------------------------------------------------------------------------
   Handles .csv / .tsv / .xlsx / .json, including raw exports straight out of
   Jira and Asana. Nothing here touches the network. Everything runs in the
   page: the file is read with FileReader, parsed in memory, and discarded when
   the tab closes.

   Three steps, deliberately: choose -> map -> preview. Silent auto-mapping is
   how a dashboard ends up confidently wrong, so every guess is shown and can
   be overridden before anything is applied.
   ========================================================================= */
(function () {
"use strict";

const API = window.DVD;
const $  = (s, r) => (r || document).querySelector(s);
const $$ = (s, r) => Array.from((r || document).querySelectorAll(s));
const esc = API.esc;

/* ------------------------------------------------------------------ fields */
const FIELDS = [
  { k: "key",            req: true,  lab: "Issue key",        hint: "Unique identifier, e.g. ABC-123" },
  { k: "summary",        req: true,  lab: "Summary",          hint: "One-line title" },
  { k: "status",         req: true,  lab: "Status",           hint: "Your own workflow status name" },
  { k: "statusCategory", req: false, lab: "Status category",  hint: "To Do / In Progress / Done — inferred from status if absent" },
  { k: "assignee",       req: false, lab: "Assignee",         hint: "Display name" },
  { k: "storyPoints",    req: false, lab: "Story points",     hint: "Number; blank counts as 0" },
  { k: "type",           req: false, lab: "Issue type",       hint: "Story / Bug / Task" },
  { k: "priority",       req: false, lab: "Priority",         hint: "Highest / High / Medium / Low" },
  { k: "epic",           req: false, lab: "Epic or parent",   hint: "Groups work for the epic filter" },
  { k: "created",        req: true,  lab: "Created date",     hint: "Drives ageing and lead time" },
  { k: "started",        req: false, lab: "Started date",     hint: "Drives cycle time and the waiting-vs-working split" },
  { k: "resolved",       req: false, lab: "Resolved date",    hint: "Drives the burndown and completion" },
  { k: "dueDate",        req: false, lab: "Due date",         hint: "Drives the overdue count" },
  { k: "flagged",        req: false, lab: "Flagged/blocked",  hint: "Anything non-empty counts as blocked" },
  { k: "addedMidSprint", req: false, lab: "Added mid-sprint", hint: "Drives the scope line on the burndown" },
  { k: "businessValue",  req: false, lab: "Business value",   hint: "Number, one currency throughout" },
  { k: "valueBasis",     req: false, lab: "Value basis",      hint: "One line on how the number was reached" },
  { k: "labels",         req: false, lab: "Labels / tags",    hint: "Separated by ; , or |" },
  { k: "url",            req: false, lab: "Link",             hint: "Deep link back to the tracker" }
];
const DATE_FIELDS = ["created", "started", "resolved", "dueDate"];
const BOOL_FIELDS = ["flagged", "addedMidSprint"];
const NUM_FIELDS  = ["storyPoints", "businessValue"];

/* Header synonyms, lower-cased and stripped of punctuation. Ordered: the first
   match wins, so put the precise names before the loose ones. */
const SYN = {
  key:            ["issue key", "key", "issue id", "issueid", "id", "task id", "gid", "ticket", "issue"],
  summary:        ["summary", "title", "name", "task name", "issue summary", "description"],
  type:           ["issue type", "issuetype", "type", "work type", "task type", "item type"],
  status:         ["status", "state", "issue status", "workflow status", "section", "column"],
  statusCategory: ["status category", "statuscategory", "category", "status category name"],
  assignee:       ["assignee", "assigned to", "owner", "assignee name", "assignee display name", "responsible"],
  storyPoints:    ["story points", "story point estimate", "storypoints", "points", "estimate", "effort",
                   "custom field story points", "custom field story point estimate", "sp"],
  priority:       ["priority", "severity", "urgency"],
  epic:           ["epic", "epic link", "epic name", "parent", "parent summary", "parent key", "project",
                   "feature", "initiative", "section"],
  created:        ["created", "created date", "created at", "createdat", "date created", "raised", "opened", "reported"],
  started:        ["started", "start date", "started date", "in progress date", "actual start", "start on",
                   "start_on", "development started", "date started"],
  resolved:       ["resolved", "resolution date", "resolved date", "completed at", "completed date", "closed",
                   "closed date", "done date", "completed on", "date completed"],
  dueDate:        ["due date", "due", "duedate", "due on", "due_on", "target date", "target end", "deadline"],
  flagged:        ["flagged", "blocked", "is blocked", "impediment", "blocker", "on hold"],
  addedMidSprint: ["added mid sprint", "added midsprint", "added mid-sprint", "sprint added", "added to sprint",
                   "mid sprint", "unplanned", "unplanned work", "added after start", "scope added", "injected"],
  businessValue:  ["business value", "value", "estimated value", "benefit", "expected value", "revenue impact",
                   "custom field business value"],
  valueBasis:     ["value basis", "basis", "value rationale", "value justification", "value assumption"],
  labels:         ["labels", "label", "tags", "tag", "components", "component"],
  url:            ["url", "link", "permalink", "permalink url", "issue url", "web url", "browse"]
};

const norm = s => String(s == null ? "" : s)
  .replace(/﻿/g, "").toLowerCase().replace(/[_\-.]+/g, " ")
  .replace(/[()\[\]]/g, " ").replace(/\s+/g, " ").trim();

/* =====================================================================
   CSV / TSV
   ================================================================== */
function sniffDelimiter(text) {
  const line = text.split(/\r?\n/).find(l => l.trim()) || "";
  const counts = { ",": 0, ";": 0, "\t": 0, "|": 0 };
  let q = false;
  for (const ch of line) {
    if (ch === '"') q = !q;
    else if (!q && counts[ch] !== undefined) counts[ch]++;
  }
  return Object.keys(counts).reduce((a, b) => (counts[b] > counts[a] ? b : a), ",");
}

function parseDelimited(text, delim) {
  text = text.replace(/^﻿/, "");
  delim = delim || sniffDelimiter(text);
  const rows = [];
  let row = [], cur = "", q = false;
  for (let i = 0; i < text.length; i++) {
    const c = text[i];
    if (q) {
      if (c === '"' && text[i + 1] === '"') { cur += '"'; i++; }
      else if (c === '"') q = false;
      else cur += c;
    } else if (c === '"') q = true;
    else if (c === delim) { row.push(cur); cur = ""; }
    else if (c === "\n") { row.push(cur); rows.push(row); row = []; cur = ""; }
    else if (c !== "\r") cur += c;
  }
  if (cur !== "" || row.length) { row.push(cur); rows.push(row); }
  // Jira sometimes prefixes a comment line; the header is the first row that
  // has more than one populated cell.
  while (rows.length && rows[0].filter(v => String(v).trim()).length < 2) rows.shift();
  if (!rows.length) throw new Error("no rows found");
  const header = rows.shift().map(h => String(h).trim());
  const body = rows.filter(r => r.some(v => String(v).trim() !== ""));
  return { header, rows: body.map(r => header.map((_, i) => r[i] == null ? "" : String(r[i]).trim())) };
}

/* =====================================================================
   XLSX — zip + shared strings + first worksheet, no dependencies
   ================================================================== */
async function inflateRaw(bytes) {
  if (typeof DecompressionStream === "undefined")
    throw new Error("this browser cannot unzip .xlsx — save the sheet as CSV and upload that instead");
  const ds = new DecompressionStream("deflate-raw");
  const stream = new Blob([bytes]).stream().pipeThrough(ds);
  return new Uint8Array(await new Response(stream).arrayBuffer());
}

async function unzip(buffer) {
  const b = new Uint8Array(buffer), dv = new DataView(buffer);
  // locate the end-of-central-directory record
  let eocd = -1;
  for (let i = b.length - 22; i >= Math.max(0, b.length - 66000); i--) {
    if (dv.getUint32(i, true) === 0x06054b50) { eocd = i; break; }
  }
  if (eocd < 0) throw new Error("not a readable .xlsx file");
  const count = dv.getUint16(eocd + 10, true);
  let p = dv.getUint32(eocd + 16, true);
  const files = {};
  for (let n = 0; n < count; n++) {
    if (dv.getUint32(p, true) !== 0x02014b50) break;
    const method = dv.getUint16(p + 10, true);
    const csize  = dv.getUint32(p + 20, true);
    const nlen   = dv.getUint16(p + 28, true);
    const elen   = dv.getUint16(p + 30, true);
    const clen   = dv.getUint16(p + 32, true);
    const lho    = dv.getUint32(p + 42, true);
    const name   = new TextDecoder().decode(b.subarray(p + 46, p + 46 + nlen));
    const lnlen  = dv.getUint16(lho + 26, true);
    const lelen  = dv.getUint16(lho + 28, true);
    const start  = lho + 30 + lnlen + lelen;
    files[name] = { method, data: b.subarray(start, start + csize) };
    p += 46 + nlen + elen + clen;
  }
  const out = {};
  for (const [name, f] of Object.entries(files)) {
    if (!/\.(xml|rels)$/i.test(name)) continue;
    const raw = f.method === 0 ? f.data : await inflateRaw(f.data);
    out[name] = new TextDecoder().decode(raw);
  }
  return out;
}

const colIndex = ref => {
  let n = 0;
  for (const ch of ref.replace(/\d+/g, "")) n = n * 26 + (ch.charCodeAt(0) - 64);
  return n - 1;
};

async function parseXLSX(buffer) {
  const files = await unzip(buffer);
  const X = new DOMParser();
  const shared = [];
  if (files["xl/sharedStrings.xml"]) {
    const doc = X.parseFromString(files["xl/sharedStrings.xml"], "application/xml");
    Array.from(doc.getElementsByTagName("si")).forEach(si =>
      shared.push(Array.from(si.getElementsByTagName("t")).map(t => t.textContent).join("")));
  }
  const sheetName = Object.keys(files)
    .filter(n => /^xl\/worksheets\/sheet\d+\.xml$/.test(n)).sort()[0];
  if (!sheetName) throw new Error("no worksheet found inside the .xlsx");
  const doc = X.parseFromString(files[sheetName], "application/xml");
  const rows = [];
  Array.from(doc.getElementsByTagName("row")).forEach(r => {
    const arr = [];
    Array.from(r.getElementsByTagName("c")).forEach(c => {
      const ix = colIndex(c.getAttribute("r") || "A1");
      const t = c.getAttribute("t");
      let v = "";
      if (t === "inlineStr") {
        v = Array.from(c.getElementsByTagName("t")).map(x => x.textContent).join("");
      } else {
        const vn = c.getElementsByTagName("v")[0];
        v = vn ? vn.textContent : "";
        if (t === "s") v = shared[Number(v)] != null ? shared[Number(v)] : "";
      }
      arr[ix] = String(v).trim();
    });
    rows.push(arr);
  });
  while (rows.length && rows[0].filter(v => v && String(v).trim()).length < 2) rows.shift();
  if (!rows.length) throw new Error("the first worksheet is empty");
  const header = rows.shift().map(h => String(h == null ? "" : h).trim());
  const body = rows.filter(r => r.some(v => v && String(v).trim() !== ""));
  return { header, rows: body.map(r => header.map((_, i) => r[i] == null ? "" : String(r[i]))) };
}

/* =====================================================================
   value coercion
   ================================================================== */
const MONTHS = { jan: 1, feb: 2, mar: 3, apr: 4, may: 5, jun: 6, jul: 7, aug: 8, sep: 9, oct: 10, nov: 11, dec: 12 };
const pad = n => String(n).padStart(2, "0");

/** Excel serial date -> ISO. Excel's 1900 epoch is offset by 2 days
 *  (day 0 is 1899-12-30) and includes a fictional 29 Feb 1900. */
function serialToISO(n) {
  const ms = (n - 25569) * 86400000;
  return new Date(Math.round(ms)).toISOString().slice(0, 10);
}

/** Parse one date value. `order` is "dmy" or "mdy" for ambiguous numeric dates. */
function parseDate(v, order) {
  if (v == null || v === "") return null;
  const s = String(v).trim();
  if (!s) return null;

  // Excel serial number
  if (/^\d+(\.\d+)?$/.test(s)) {
    const n = Number(s);
    if (n > 20000 && n < 80000) return serialToISO(n);
    return null;
  }
  // ISO, with or without a time part
  let m = s.match(/^(\d{4})-(\d{2})-(\d{2})/);
  if (m) return m[1] + "-" + m[2] + "-" + m[3];
  // 22/Jul/26 3:41 PM  ·  22-Jul-2026  ·  Jul 22, 2026
  m = s.match(/^(\d{1,2})[\/\-\s]([A-Za-z]{3,})[\/\-\s](\d{2,4})/);
  if (m) {
    const mo = MONTHS[m[2].slice(0, 3).toLowerCase()];
    if (mo) return fullYear(m[3]) + "-" + pad(mo) + "-" + pad(m[1]);
  }
  m = s.match(/^([A-Za-z]{3,})\s+(\d{1,2}),?\s+(\d{4})/);
  if (m) {
    const mo = MONTHS[m[1].slice(0, 3).toLowerCase()];
    if (mo) return m[3] + "-" + pad(mo) + "-" + pad(m[2]);
  }
  // all-numeric, ambiguous
  m = s.match(/^(\d{1,2})[\/\-.](\d{1,2})[\/\-.](\d{2,4})/);
  if (m) {
    let a = +m[1], b = +m[2];
    let day, mon;
    if (a > 12) { day = a; mon = b; }
    else if (b > 12) { mon = a; day = b; }
    else if (order === "mdy") { mon = a; day = b; }
    else { day = a; mon = b; }
    return fullYear(m[3]) + "-" + pad(mon) + "-" + pad(day);
  }
  const t = Date.parse(s);
  return isNaN(t) ? null : new Date(t).toISOString().slice(0, 10);
}
function fullYear(y) {
  const n = +y;
  return String(y).length === 4 ? String(n) : String(n < 70 ? 2000 + n : 1900 + n);
}

/** Decide dd/mm vs mm/dd for a column by looking at every value in it. */
function detectOrder(values) {
  let numeric = 0, dmy = 0, mdy = 0;
  values.forEach(v => {
    const m = String(v || "").match(/^(\d{1,2})[\/\-.](\d{1,2})[\/\-.](\d{2,4})/);
    if (!m) return;
    numeric++;
    if (+m[1] > 12) dmy++;
    else if (+m[2] > 12) mdy++;
  });
  // No all-numeric dates in this column (ISO, or "22/Jul/26") — nothing to guess.
  if (!numeric) return { order: "dmy", certain: true, numeric: 0 };
  if (dmy && !mdy) return { order: "dmy", certain: true, numeric };
  if (mdy && !dmy) return { order: "mdy", certain: true, numeric };
  // Either the column contradicts itself, or no value has a day above 12 and
  // the order is genuinely undecidable. Both must be surfaced, not guessed at.
  return { order: dmy >= mdy ? "dmy" : "mdy", certain: false, numeric,
           reason: (dmy && mdy) ? "contradicts" : "undecidable" };
}

function toBool(v) {
  const s = String(v == null ? "" : v).trim().toLowerCase();
  if (!s) return false;
  if (["false", "no", "n", "0", "none", "-", "null", "not blocked"].includes(s)) return false;
  return true;   // Jira puts the word "Impediment" in its Flagged column
}
function toNum(v) {
  if (v == null || v === "") return 0;
  const n = parseFloat(String(v).replace(/[^0-9.\-]/g, ""));
  return isNaN(n) ? 0 : n;
}
function toLabels(v) {
  if (Array.isArray(v)) return v.filter(Boolean);
  return String(v == null ? "" : v).split(/[;,|]/).map(s => s.trim()).filter(Boolean);
}

/* =====================================================================
   wizard state
   ================================================================== */
const W = {
  filename: "",
  header: [],
  rows: [],
  map: {},          // field -> column index, or -1
  extraCols: {},    // field -> [indices] for repeated headers (labels)
  window: {},
  built: null,
  mode: "replace",
  jsonDataset: null // set when the upload was already a full dataset
};

function autoMap(header) {
  const used = new Set(), map = {}, extra = {};
  const normed = header.map(norm);
  FIELDS.forEach(f => {
    const syns = SYN[f.k] || [];
    let hit = -1;
    for (const syn of syns) {                       // exact first
      const ix = normed.findIndex((h, i) => !used.has(i) && h === syn);
      if (ix >= 0) { hit = ix; break; }
    }
    if (hit < 0) for (const syn of syns) {           // then contains
      const ix = normed.findIndex((h, i) => !used.has(i) && h.includes(syn));
      if (ix >= 0) { hit = ix; break; }
    }
    map[f.k] = hit;
    if (hit >= 0) used.add(hit);
  });
  // repeated headers (Jira emits Labels, Labels, Labels…) all feed one field
  if (map.labels >= 0) {
    const want = normed[map.labels];
    extra.labels = normed.map((h, i) => (h === want ? i : -1)).filter(i => i >= 0);
  }
  return { map, extra };
}

/* =====================================================================
   build issues from the mapping
   ================================================================== */
function buildIssues() {
  const orders = {}, warnings = [];
  DATE_FIELDS.forEach(f => {
    const ix = W.map[f];
    if (ix >= 0) orders[f] = detectOrder(W.rows.map(r => r[ix]));
  });

  const badDates = {};
  const issues = W.rows.map(r => {
    const g = f => { const ix = W.map[f]; return ix >= 0 ? r[ix] : ""; };
    const o = { };
    FIELDS.forEach(f => {
      const k = f.k, raw = g(k);
      if (DATE_FIELDS.includes(k)) {
        const v = parseDate(raw, (orders[k] || {}).order);
        if (raw && !v) badDates[k] = (badDates[k] || 0) + 1;
        o[k] = v;
      } else if (BOOL_FIELDS.includes(k)) o[k] = W.map[k] === -2 ? false : toBool(raw);
      else if (NUM_FIELDS.includes(k)) o[k] = toNum(raw);
      else if (k === "labels") {
        const cols = (W.extraCols.labels && W.extraCols.labels.length) ? W.extraCols.labels : (W.map.labels >= 0 ? [W.map.labels] : []);
        o.labels = cols.flatMap(ix => toLabels(r[ix]));
      } else o[k] = raw === "" ? null : raw;
    });
    if (W.map.addedMidSprint === -2 && W.window.startDate && o.created)
      o.addedMidSprint = o.created > W.window.startDate;
    if (!o.key) o.key = "ROW-" + (W.rows.indexOf(r) + 1);
    o.summary = o.summary || "(no summary)";
    o.status = o.status || "To Do";
    return o;
  });

  Object.entries(badDates).forEach(([f, n]) =>
    warnings.push(["wrn", "Unreadable dates", n + " value" + (n > 1 ? "s" : "") +
      " in the <b>" + f + "</b> column could not be read as a date and were dropped."]));
  Object.entries(orders).forEach(([f, o]) => {
    if (o.certain !== false) return;
    const read = o.order === "dmy" ? "day/month/year" : "month/day/year";
    warnings.push(["err", "Ambiguous date format",
      o.reason === "contradicts"
        ? "The <b>" + f + "</b> column contains both day-first and month-first values. Read as <b>" + read +
          "</b>, which means some of them are wrong. Re-export with ISO dates (YYYY-MM-DD)."
        : "Every date in <b>" + f + "</b> has a day of 12 or lower, so day-first and month-first cannot be told " +
          "apart. Read as <b>" + read + "</b>. If that is wrong, every elapsed-time figure on the page is wrong " +
          "— re-export with ISO dates (YYYY-MM-DD)."]);
  });
  return { issues, warnings };
}

/* =====================================================================
   derived series — never inherit the previous file's charts
   ================================================================== */
function inferWindow(issues) {
  const all = f => issues.map(i => i[f]).filter(Boolean).sort();
  const starts = all("started").concat(all("created"));
  const ends = all("resolved").concat(all("dueDate"));
  const prev = API.data.meta || {};
  const start = all("started")[0] || starts[0] || prev.startDate || null;
  const end = ends[ends.length - 1] || prev.endDate || null;
  const today = new Date().toISOString().slice(0, 10);
  return {
    sprintName: prev.sprintName && W.mode === "merge" ? prev.sprintName : "Imported " + (start || today),
    startDate: start, endDate: end,
    asOfDate: end && end < today ? end : today
  };
}

function buildBurndown(issues, meta) {
  /* Emits BOTH units. The dashboard's toggle needs an item series to switch to,
     and the forecasting agent works in items — a burndown that only exists in
     story points is the two-tools-disagree problem baked into the data.
     Mirrors scripts/rebuild_burndown.py and the fetcher's build_burndown(). */
  const days = API.workingDays(meta.startDate, meta.endDate);
  if (!days.length) return [];
  const planned = issues.filter(i => !i.addedMidSprint);
  const baseP = planned.reduce((t, i) => t + (i.storyPoints || 0), 0);
  const baseI = planned.length;

  const addedOn = {}, doneOn = {};
  const bump = (bag, key, pts) => {
    const b = bag[key] || (bag[key] = [0, 0]);
    b[0] += pts; b[1] += 1;
  };
  issues.forEach(i => {
    if (i.addedMidSprint && i.created) bump(addedOn, i.created, i.storyPoints || 0);
    if (i.resolved) bump(doneOn, i.resolved, i.storyPoints || 0);
  });

  const asOf = meta.asOfDate, n = days.length;
  let scopeP = baseP, remP = baseP, scopeI = baseI, remI = baseI;
  return days.map((day, k) => {
    const prevDay = k ? days[k - 1] : null;
    const inWindow = d => d <= day && (!prevDay || d > prevDay);
    Object.keys(addedOn).forEach(d => {
      if (!inWindow(d)) return;
      scopeP += addedOn[d][0]; remP += addedOn[d][0];
      scopeI += addedOn[d][1]; remI += addedOn[d][1];
    });
    Object.keys(doneOn).forEach(d => {
      if (!inWindow(d)) return;
      remP -= doneOn[d][0];
      remI -= doneOn[d][1];
    });
    const future = day > asOf;
    const frac = n > 1 ? 1 - k / (n - 1) : 0;
    return {
      date: day,
      remainingSP: future ? null : Math.round(remP * 10) / 10,
      scopeSP: future ? null : Math.round(scopeP * 10) / 10,
      idealSP: Math.round(baseP * frac * 10) / 10,
      remainingItems: future ? null : remI,
      scopeItems: future ? null : scopeI,
      idealItems: Math.round(baseI * frac * 10) / 10
    };
  });
}

function buildHistoryRow(issues, meta, prevHistory) {
  const done = issues.filter(i => (i.statusCategory || "") === "Done" || /done|closed|resolved|complete/i.test(i.status || ""));
  const d = (a, b) => (a && b) ? (API.D(b) - API.D(a)) / 864e5 : null;
  const lead = done.map(i => d(i.created, i.resolved)).filter(v => v != null && v >= 0);
  const cyc = done.map(i => d(i.started, i.resolved)).filter(v => v != null && v >= 0);
  const totL = lead.reduce((a, b) => a + b, 0), totC = cyc.reduce((a, b) => a + b, 0);
  const completed = done.reduce((t, i) => t + (i.storyPoints || 0), 0);
  return {
    sprint: meta.sprintName,
    committedSP: Math.round(issues.filter(i => !i.addedMidSprint).reduce((t, i) => t + (i.storyPoints || 0), 0) * 10) / 10,
    completedSP: Math.round(completed * 10) / 10,
    committedItems: issues.filter(i => !i.addedMidSprint).length,
    completedItems: done.length,
    throughput: done.length,
    // Work in progress and interruption, both from issue status. Hours are
    // deliberately absent: the organisation does not operate overtime, and a
    // field for them would imply a time-tracking regime that does not exist.
    wipItems: issues.filter(i => i.statusCategory === "In Progress").length,
    unplannedItems: issues.filter(i => i.addedMidSprint).length,
    flowEfficiency: totL > 0 ? Math.round(totC / totL * 100) / 100 : null,
    valueDelivered: Math.round(done.reduce((t, i) => t + (i.businessValue || 0), 0))
  };
}

/* =====================================================================
   assemble the candidate dataset
   ================================================================== */
function assemble() {
  const { issues, warnings } = buildIssues();
  const prev = API.data;
  let merged = issues;

  if (W.mode === "merge") {
    const byKey = new Map(prev.issues.map(i => [i.key, Object.assign({}, i)]));
    issues.forEach(i => {
      const ex = byKey.get(i.key);
      if (ex) {
        // only overwrite with values the upload actually supplied
        Object.keys(i).forEach(k => {
          const v = i[k];
          const supplied = W.map[k] >= 0 &&
            !(v === null || v === "" || (Array.isArray(v) && !v.length) ||
              ((k === "storyPoints" || k === "businessValue") && v === 0) ||
              (BOOL_FIELDS.includes(k) && v === false));
          if (supplied) ex[k] = v;
        });
        byKey.set(i.key, ex);
      } else byKey.set(i.key, i);
    });
    merged = Array.from(byKey.values());
  }

  const meta = Object.assign({}, prev.meta, {
    sprintName: W.window.sprintName,
    startDate: W.window.startDate,
    endDate: W.window.endDate,
    asOfDate: W.window.asOfDate,
    source: "upload",
    sourceLabel: "Uploaded: " + W.filename,
    generatedAt: new Date().toISOString()
  });
  meta.workingDays = API.workingDays(meta.startDate, meta.endDate);

  const history = (prev.history || []).filter(h => h.sprint !== meta.sprintName)
    .concat([buildHistoryRow(merged, meta, prev.history)]).slice(-6);

  return {
    dataset: {
      schemaVersion: "1.0",
      meta,
      issues: merged,
      burndown: buildBurndown(merged, meta),
      history,
      releases: prev.releases || [],
      dora: prev.dora || null
    },
    warnings
  };
}

/* =====================================================================
   UI — modal plumbing
   ================================================================== */
const modal = $("#modal");
const show = id => ["step-choose", "step-map", "step-preview"]
  .forEach(s => $("#" + s).classList.toggle("hidden", s !== id));

function openModal() { modal.classList.add("on"); show("step-choose"); }
function closeModal() { modal.classList.remove("on"); }
$("#btn-import").onclick = openModal;
$("#m-close").onclick = closeModal;
modal.addEventListener("click", e => { if (e.target === modal) closeModal(); });
document.addEventListener("keydown", e => { if (e.key === "Escape") closeModal(); });

$$(".tabs button").forEach(b => b.onclick = () => {
  $$(".tabs button").forEach(x => x.setAttribute("aria-selected", String(x === b)));
  ["file", "jira", "schema"].forEach(t => $("#tab-" + t).classList.toggle("hidden", t !== b.dataset.tab));
});

let toastT;
function toast(msg) {
  let el = $(".toast");
  if (!el) { el = document.createElement("div"); el.className = "toast"; document.body.appendChild(el); }
  el.textContent = msg;
  el.classList.add("on");
  clearTimeout(toastT);
  toastT = setTimeout(() => el.classList.remove("on"), 3200);
}

/* ------------------------------------------------------------- step 1 */
async function ingest(file) {
  W.filename = file.name || "pasted text";
  const ext = (file.name || "").toLowerCase().split(".").pop();
  try {
    if (ext === "xlsx") {
      const buf = await file.arrayBuffer();
      const t = await parseXLSX(buf);
      W.header = t.header; W.rows = t.rows; W.jsonDataset = null;
    } else {
      const text = await file.text();
      handleText(text);
    }
    toStep2();
  } catch (err) { alert("Could not read " + W.filename + ":\n\n" + err.message); }
}

function handleText(text) {
  const t = text.trim();
  if (t.startsWith("{") || t.startsWith("[")) {
    const parsed = JSON.parse(t);
    const ds = Array.isArray(parsed) ? { issues: parsed } : parsed;
    if (!ds.issues || !ds.issues.length) throw new Error("the JSON contains no issues[] array");
    // A full dataset needs no mapping — flatten it into the same table shape so
    // the preview still shows what will be applied.
    W.jsonDataset = ds;
    const keys = Array.from(new Set(ds.issues.flatMap(o => Object.keys(o))));
    W.header = keys;
    W.rows = ds.issues.map(o => keys.map(k => Array.isArray(o[k]) ? o[k].join(";") : (o[k] == null ? "" : String(o[k]))));
  } else {
    const p = parseDelimited(text);
    W.header = p.header; W.rows = p.rows; W.jsonDataset = null;
  }
}

const drop = $("#drop"), fileInput = $("#file");
["dragenter", "dragover"].forEach(ev => drop.addEventListener(ev, e => { e.preventDefault(); drop.classList.add("over"); }));
["dragleave", "drop"].forEach(ev => drop.addEventListener(ev, e => { e.preventDefault(); drop.classList.remove("over"); }));
drop.addEventListener("drop", e => { const f = e.dataTransfer.files[0]; if (f) ingest(f); });
fileInput.onchange = e => { const f = e.target.files[0]; if (f) ingest(f); e.target.value = ""; };
$("#m-paste").onclick = () => {
  const t = $("#paste").value;
  if (!t.trim()) return alert("Nothing pasted.");
  W.filename = "pasted text";
  try { handleText(t); toStep2(); }
  catch (err) { alert("Could not read that text:\n\n" + err.message); }
};

/* ------------------------------------------------------------- step 2 */
function toStep2() {
  const a = autoMap(W.header);
  W.map = a.map; W.extraCols = a.extra;
  Object.keys(INFERABLE).forEach(k => { if (W.map[k] < 0) W.map[k] = -2; });
  if (W.jsonDataset) FIELDS.forEach(f => {
    const ix = W.header.indexOf(f.k);
    if (ix >= 0) W.map[f.k] = ix;
  });

  $("#map-src").innerHTML = "Read <b>" + esc(W.filename) + "</b> — " + W.rows.length +
    " row" + (W.rows.length === 1 ? "" : "s") + ", " + W.header.length + " columns." +
    (W.jsonDataset ? " This looks like a dashboard dataset, so the mapping is already exact." : "");

  drawMapTable();
  const win = inferWindow(buildIssues().issues);
  W.window = win;
  $("#w-name").value = win.sprintName || "";
  $("#w-start").value = win.startDate || "";
  $("#w-end").value = win.endDate || "";
  $("#w-asof").value = win.asOfDate || "";
  show("step-map");
}

const INFERABLE = { addedMidSprint: "— infer: created after the sprint starts —" };

function drawMapTable() {
  const opts = (ix, k) => '<option value="-1">— not in my file —</option>' +
    (INFERABLE[k] ? '<option value="-2"' + (ix === -2 ? " selected" : "") + ">" + esc(INFERABLE[k]) + "</option>" : "") +
    W.header.map((h, i) => '<option value="' + i + '"' + (i === ix ? " selected" : "") + ">" +
      esc(h || "(column " + (i + 1) + ")") + "</option>").join("");
  $("#map-body").innerHTML = FIELDS.map(f => {
    const ix = W.map[f.k];
    const sample = ix >= 0 ? (W.rows.find(r => r[ix] !== "") || [])[ix]
      : (ix === -2 ? "computed from the sprint start date below" : "");
    let status, cls;
    if (ix === -2) { status = '<span class="chip c-warn"><span aria-hidden="true">&#9650;</span>inferred</span>'; cls = ""; }
    else if (ix >= 0) { status = '<span class="chip c-good"><span aria-hidden="true">&#10003;</span>matched</span>'; cls = ""; }
    else if (f.req) { status = '<span class="chip c-crit"><span aria-hidden="true">&#9632;</span>required</span>'; cls = "req"; }
    else { status = '<span class="chip c-info"><span aria-hidden="true">i</span>will be blank</span>'; cls = ""; }
    return '<tr class="' + cls + '"><td><b>' + esc(f.lab) + '</b><div class="ex">' + esc(f.hint) + "</div></td>" +
      '<td><select data-field="' + f.k + '" title="' +
        esc(ix >= 0 ? W.header[ix] : "") + '">' + opts(ix, f.k) + "</select></td>" +
      '<td class="ex">' + esc(sample == null ? "" : String(sample).slice(0, 60)) + "</td>" +
      "<td>" + status + "</td></tr>";
  }).join("");
  $("#map-body").onchange = e => {
    const sel = e.target.closest("select[data-field]"); if (!sel) return;
    W.map[sel.dataset.field] = Number(sel.value);
    if (sel.dataset.field === "labels") W.extraCols.labels = [];
    drawMapTable();
  };
}

$("#m-back").onclick = () => show("step-choose");
$("#m-back2").onclick = () => show("step-map");

/* ------------------------------------------------------------- step 3 */
$("#m-preview").onclick = () => {
  const missing = FIELDS.filter(f => f.req && W.map[f.k] < 0);
  if (missing.length)
    return alert("Pick a column for: " + missing.map(f => f.lab).join(", "));
  W.mode = ($('input[name="mergemode"]:checked') || {}).value || "replace";
  W.window = {
    sprintName: $("#w-name").value.trim() || "Imported sprint",
    startDate: $("#w-start").value || null,
    endDate: $("#w-end").value || null,
    asOfDate: $("#w-asof").value || new Date().toISOString().slice(0, 10)
  };
  const { dataset, warnings } = assemble();
  W.built = dataset;

  const iss = dataset.issues;
  const done = iss.filter(i => /done|closed|resolved|complete/i.test(i.statusCategory || i.status || ""));
  const stats = [
    [iss.length, "issues"],
    [done.length, "done"],
    [Math.round(iss.reduce((t, i) => t + (i.storyPoints || 0), 0) * 10) / 10, "story points"],
    [new Set(iss.map(i => i.assignee).filter(Boolean)).size, "people"],
    [dataset.burndown.length, "burndown days"]
  ];
  $("#prev-stats").innerHTML = stats.map(s => "<div><b>" + s[0] + "</b><span>" + s[1] + "</span></div>").join("");

  const warn = warnings.slice();
  const dup = {};
  iss.forEach(i => dup[i.key] = (dup[i.key] || 0) + 1);
  const dups = Object.keys(dup).filter(k => dup[k] > 1);
  if (dups.length) warn.push(["err", "Duplicate keys",
    dups.length + " key" + (dups.length > 1 ? "s appear" : " appears") + " more than once (" +
    esc(dups.slice(0, 4).join(", ")) + (dups.length > 4 ? "…" : "") +
    "). Counts will be inflated until you de-duplicate the export."]);
  if (W.map.storyPoints < 0) warn.push(["wrn", "No story points",
    "Every issue counts as 0 points, so the burndown, pace and distribution charts will be flat. Item counts still work."]);
  if (W.map.started < 0) warn.push(["wrn", "No started date",
    "Cycle time cannot be calculated, so the waiting-vs-working chart will be empty. In Jira this is derivable from the changelog — the fetcher script does it for you."]);
  if (W.map.addedMidSprint === -2) warn.push(["wrn", "Mid-sprint additions are inferred",
    "Your file has no such column, so anything created after <b>" + esc(W.window.startDate || "the sprint start") +
    "</b> is treated as added mid-sprint. That is a proxy: a backlog item created mid-sprint and planned into the " +
    "next one would be miscounted. Map a real column if you have one."]);
  if (W.map.addedMidSprint === -1) warn.push(["wrn", "No mid-sprint flag",
    "The scope line on the burndown will be flat, so scope growth stays invisible — the single most useful thing this dashboard adds."]);
  if (W.map.businessValue < 0) warn.push(["wrn", "No business value",
    "The value card will read zero. Upload a second file with key and businessValue columns using <b>Merge</b> to layer estimates on top."]);
  if (!dataset.dora) warn.push(["wrn", "No release metrics",
    "DORA figures come from your CI/CD tool, not a tracker. That card will say it has no data."]);
  if (!dataset.burndown.length) warn.push(["err", "No sprint window",
    "Without a start and end date there is no burndown and no pace-vs-clock figure. Set them on the previous step."]);
  if (!warn.length) warn.push(["ok", "Nothing looks wrong", "Every field the dashboard needs was found and read cleanly."]);

  const ic = { err: "&#9632;", wrn: "&#9650;", ok: "&#10003;" };
  $("#prev-warn").innerHTML = warn.map(w =>
    '<div class="warn ' + w[0] + '"><span aria-hidden="true">' + ic[w[0]] + "</span><span><b>" +
    w[1] + ".</b> " + w[2] + "</span></div>").join("");

  const cols = ["key", "summary", "assignee", "status", "storyPoints", "created", "started", "resolved", "flagged"];
  $("#prev-table").innerHTML = "<table class='tv'><thead><tr>" +
    cols.map(c => "<th>" + c + "</th>").join("") + "</tr></thead><tbody>" +
    iss.slice(0, 8).map(i => "<tr>" + cols.map(c =>
      "<td>" + esc(c === "summary" ? String(i[c] || "").slice(0, 44) : (i[c] == null ? "—" : String(i[c]))) + "</td>").join("") +
      "</tr>").join("") + "</tbody></table>" +
    (iss.length > 8 ? '<div class="note" style="padding:6px 2px">…and ' + (iss.length - 8) + " more.</div>" : "");

  show("step-preview");
};

$("#m-apply").onclick = () => {
  if (!W.built) return;
  API.applyDataset(W.built);
  closeModal();
  toast("Loaded " + W.built.issues.length + " issues from " + W.filename);
};

/* ------------------------------------------------------- templates etc. */
const TEMPLATE = {
  schemaVersion: "1.0",
  meta: { organisation: "", team: "", sprintName: "", sprintGoal: "", startDate: "YYYY-MM-DD",
    endDate: "YYYY-MM-DD", asOfDate: "YYYY-MM-DD", source: "manual", sourceLabel: "",
    baseUrl: "https://your-domain.atlassian.net", currency: "USD", workingDays: [] },
  issues: [{ key: "ABC-1", summary: "", type: "Story", status: "In Progress", statusCategory: "In Progress",
    assignee: "", storyPoints: 0, priority: "Medium", epic: "", created: "YYYY-MM-DD", started: null,
    resolved: null, dueDate: null, flagged: false, addedMidSprint: false, businessValue: 0,
    valueBasis: "", labels: [] }],
  burndown: [{ date: "YYYY-MM-DD", remainingSP: 0, scopeSP: 0, idealSP: 0,
    remainingItems: 0, scopeItems: 0, idealItems: 0 }],
  history: [{ sprint: "", committedSP: 0, completedSP: 0, committedItems: 0, completedItems: 0,
    throughput: 0, wipItems: 0, unplannedItems: 0, flowEfficiency: 0, valueDelivered: 0 }],
  releases: [{ name: "", targetDate: "YYYY-MM-DD", scopeIssues: 0, doneIssues: 0, status: "On Track", note: "" }],
  dora: { deploymentFrequencyPerWeek: 0, deploymentFrequencyTrend: [], changeFailureRatePct: 0,
    changeFailureRateTrend: [], leadTimeForChangesDays: 0, leadTimeForChangesTrend: [],
    mttrMinutes: 0, mttrTrend: [] }
};
$("#m-template").onclick = () => API.download("dashboard-data-template.json", JSON.stringify(TEMPLATE, null, 2), "application/json");
$("#m-template-csv").onclick = () => API.download("issues-template.csv",
  API.toCSV([API.ISSUE_COLS, ["ABC-1", "Example issue", "Story", "In Progress", "In Progress", "Sam Okafor",
    5, "High", "Checkout", "2026-08-03", "2026-08-05", "", "2026-08-14", "false", "false", 0, "", "", ""]]), "text/csv");
$("#m-current").onclick = () => API.download("dashboard-data.json", JSON.stringify(API.data, null, 2), "application/json");
$("#m-sample").onclick = () => {
  API.applyDataset(JSON.parse(document.getElementById("seed-data").textContent));
  closeModal(); toast("Demo data restored");
};

/* --------------------------------------------------------- static tabs */
$("#tab-jira").innerHTML =
  "<h4>Why the page cannot call Jira directly</h4>" +
  "<p style='font-size:12.5px;margin:4px 0 8px'>Jira and Asana both reject cross-origin requests from a browser page, " +
  "and any token pasted into this file would be readable by anyone you forward it to. The fetcher script keeps the " +
  "token on your machine and writes a plain JSON file you then upload here.</p>" +
  "<h4>Step 1 &mdash; run the fetcher</h4>" +
  "<pre>pip install -r scripts/requirements.txt\n\nexport JIRA_URL=https://your-domain.atlassian.net\nexport JIRA_EMAIL=you@company.com\nexport JIRA_TOKEN=&lt;Atlassian API token&gt;\n\npython3 scripts/fetch_delivery_data.py --jira-board 42 --out data/dashboard-data.json</pre>" +
  "<p style='font-size:12.5px;margin:4px 0 8px'>Asana:</p>" +
  "<pre>export ASANA_TOKEN=&lt;personal access token&gt;\npython3 scripts/fetch_delivery_data.py --asana-project 1201234567890</pre>" +
  "<h4>Step 2 &mdash; load it</h4>" +
  "<p style='font-size:12.5px;margin:4px 0 8px'>Drag the JSON onto the upload tab, or serve the folder and open " +
  "<code>index.html?data=data/dashboard-data.json</code> to load it on page open.</p>" +
  "<h4>Step 3 &mdash; schedule it</h4>" +
  "<pre># weekdays at 08:00\n0 8 * * 1-5  cd /path/to/repo &amp;&amp; ./scripts/refresh.sh</pre>" +
  "<h4>Later &mdash; regenerate through Claude</h4>" +
  "<p style='font-size:12.5px;margin:4px 0'>Once the format has proved itself, connect the Atlassian and Asana " +
  "connectors and ask in plain language: &ldquo;pull Sprint 25 and rebuild the dashboard&rdquo;. Same JSON contract, " +
  "no script to run. Keep the fetcher for scheduled and offline refreshes.</p>";

$("#tab-schema").innerHTML =
  "<p style='font-size:12.5px;margin:4px 0 10px'>One row per issue drives every chart. You do not need these exact " +
  "column names &mdash; the upload step matches your headings and lets you correct any it gets wrong. These are the " +
  "names used internally and in the templates.</p>" +
  "<pre>" + esc(API.ISSUE_COLS.join(",")) + "</pre>" +
  "<table class='tv'><thead><tr><th>Field</th><th style='text-align:left'>Meaning</th></tr></thead><tbody>" +
  FIELDS.map(f => "<tr><td><code>" + f.k + "</code></td><td style='white-space:normal'>" +
    esc(f.lab) + " &mdash; " + esc(f.hint) + (f.req ? " <b>(required)</b>" : "") + "</td></tr>").join("") +
  "</tbody></table>" +
  "<p class='note' style='margin-top:10px'>Optional blocks in a full JSON dataset: <code>burndown[]</code>, " +
  "<code>history[]</code> (last six sprints; drives every trend), <code>releases[]</code> and <code>dora{}</code>. " +
  "When you upload a flat CSV, the burndown and the current history row are recalculated from your issues rather " +
  "than inherited &mdash; stale charts sitting under fresh numbers is worse than no charts.</p>";

/* expose for tests */
window.DVDImport = { parseDelimited, parseDate, detectOrder, autoMap, toBool, toNum, parseXLSX, FIELDS, W };

})();
