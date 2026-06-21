// OPLedger frontend controller.
//
// Talks to the backend exclusively through the REST API under /api — the same
// surface a hosted deployment exposes. State machine:
//   not initialized -> setup wizard
//   locked          -> unlock screen
//   no/expired token -> login
//   authenticated    -> dashboard
import { initI18n, t } from "./i18n.js";

const API = "/api";
const TOKEN_KEY = "opledger.token";

// Schedule C line items. Loaded from /api/categories (config-driven) at
// dashboard render; this is the fallback if that request fails.
let SCHEDULE_C = [
  "Advertising", "Car and truck expenses", "Commissions and fees",
  "Contract labor", "Depreciation", "Insurance",
  "Legal and professional services", "Office expenses",
  "Rent or lease (equipment)", "Repairs and maintenance", "Supplies",
  "Taxes and licenses", "Travel", "Utilities", "Wages", "Other expenses",
];

// Personal-spending categories (config-driven, like SCHEDULE_C). Fallback list.
let PERSONAL_CATS = [
  "Housing", "Groceries", "Dining", "Transportation", "Utilities", "Health",
  "Insurance", "Entertainment", "Shopping", "Travel", "Education",
  "Savings/Investment", "Gifts/Donations", "Income", "Other",
];

const token = {
  get: () => localStorage.getItem(TOKEN_KEY),
  set: (v) => localStorage.setItem(TOKEN_KEY, v),
  clear: () => localStorage.removeItem(TOKEN_KEY),
};

async function api(path, { method = "GET", body, form } = {}) {
  const headers = {};
  const tok = token.get();
  if (tok) headers["Authorization"] = `Bearer ${tok}`;
  let payload;
  if (form) {
    payload = form; // FormData; let the browser set the boundary
  } else if (body !== undefined) {
    headers["Content-Type"] = "application/json";
    payload = JSON.stringify(body);
  }
  const res = await fetch(`${API}${path}`, { method, headers, body: payload });
  if (res.status === 204) return null;
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw Object.assign(new Error(data.detail || "error"), { status: res.status, data });
  return data;
}

const app = () => document.getElementById("app");

function el(tag, attrs = {}, ...children) {
  const node = document.createElement(tag);
  for (const [k, v] of Object.entries(attrs)) {
    if (k === "class") node.className = v;
    else if (k === "html") node.innerHTML = v;
    else if (k.startsWith("on") && typeof v === "function") node.addEventListener(k.slice(2), v);
    else if (v !== null && v !== undefined) node.setAttribute(k, v);
  }
  for (const c of children.flat()) {
    if (c == null) continue;
    node.append(c.nodeType ? c : document.createTextNode(c));
  }
  return node;
}

function field(labelKey, input) {
  return el("label", { class: "field" }, t(labelKey), input);
}

function showError(container, message) {
  const existing = container.querySelector(".error");
  if (existing) existing.remove();
  container.prepend(el("p", { class: "error" }, message));
}

// --- Screens --------------------------------------------------------------

function renderSetup() {
  const u = el("input", { type: "text", required: "true", autocomplete: "username" });
  const p = el("input", { type: "password", required: "true", minlength: "8", autocomplete: "new-password" });
  const pass = el("input", { type: "password", required: "true", minlength: "8" });
  const name = el("input", { type: "text", required: "true", placeholder: t("setup.ledgerNamePlaceholder") });
  const acctNick = el("input", { type: "text" });
  const acctInst = el("input", { type: "text" });

  const form = el("form", { class: "card" },
    el("h2", {}, t("setup.heading")),
    el("p", { class: "muted" }, t("setup.intro")),
    field("setup.ownerUsername", u),
    field("setup.ownerPassword", p),
    field("setup.passphrase", pass),
    el("p", { class: "muted small" }, t("setup.passphraseHelp")),
    field("setup.ledgerName", name),
    el("fieldset", {},
      el("legend", {}, `${t("setup.firstAccount")} (${t("common.optional")})`),
      field("setup.accountNickname", acctNick),
      field("setup.accountInstitution", acctInst),
    ),
    el("button", { type: "submit" }, t("setup.submit")),
  );

  form.addEventListener("submit", async (e) => {
    e.preventDefault();
    try {
      const payload = {
        owner_username: u.value, owner_password: p.value,
        passphrase: pass.value, ledger_name: name.value,
      };
      if (acctNick.value.trim()) {
        payload.first_account = { nickname: acctNick.value.trim(), institution: acctInst.value.trim() || null };
      }
      const res = await api("/setup", { method: "POST", body: payload });
      token.set(res.access_token);
      route();
    } catch (err) {
      showError(form, err.data?.detail || t("errors.generic"));
    }
  });

  mount(form);
}

function renderUnlock() {
  const pass = el("input", { type: "password", required: "true", autofocus: "true" });
  const form = el("form", { class: "card" },
    el("h2", {}, t("unlock.heading")),
    el("p", { class: "muted" }, t("unlock.intro")),
    field("unlock.passphrase", pass),
    el("button", { type: "submit" }, t("unlock.submit")),
  );
  form.addEventListener("submit", async (e) => {
    e.preventDefault();
    try {
      await api("/unlock", { method: "POST", body: { passphrase: pass.value } });
      route();
    } catch (err) {
      showError(form, err.status === 401 ? t("errors.badPassphrase") : t("errors.generic"));
    }
  });
  mount(form);
}

function renderLogin() {
  const u = el("input", { type: "text", required: "true", autocomplete: "username" });
  const p = el("input", { type: "password", required: "true", autocomplete: "current-password" });
  const form = el("form", { class: "card" },
    el("h2", {}, t("login.heading")),
    field("login.username", u),
    field("login.password", p),
    el("button", { type: "submit" }, t("login.submit")),
  );
  form.addEventListener("submit", async (e) => {
    e.preventDefault();
    try {
      const res = await api("/auth/login", { method: "POST", body: { username: u.value, password: p.value } });
      token.set(res.access_token);
      route();
    } catch (err) {
      showError(form, err.status === 401 ? t("errors.badLogin") : t("errors.generic"));
    }
  });
  mount(form);
}

// Inline SVG icons (no external assets — the app ships with no runtime deps).
const ICONS = {
  gear: '<svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="3"/><path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 1 1-2.83 2.83l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-4 0v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 1 1-2.83-2.83l.06-.06a1.65 1.65 0 0 0 .33-1.82 1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1 0-4h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 1 1 2.83-2.83l.06.06a1.65 1.65 0 0 0 1.82.33H9a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 4 0v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 1 1 2.83 2.83l-.06.06a1.65 1.65 0 0 0-.33 1.82V9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 0 4h-.09a1.65 1.65 0 0 0-1.51 1z"/></svg>',
  chart: '<svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round"><path d="M3 3v18h18"/><rect x="7" y="11" width="3" height="6"/><rect x="12" y="7" width="3" height="10"/><rect x="17" y="13" width="3" height="4"/></svg>',
  // Distinct glyphs per export format (no labels — tooltip names each).
  csv: '<svg viewBox="0 0 24 24" width="19" height="19" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="4" width="18" height="16" rx="2"/><path d="M3 9.5h18M3 14.5h18M9 4.5v15M15 4.5v15"/></svg>',
  txf: '<svg viewBox="0 0 24 24" width="19" height="19" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"><path d="M6 2.5h12v19l-2.4-1.6-2.4 1.6-2.4-1.6L8.4 21 6 21.5z"/><path d="M9.5 8h5M9.5 12h5"/></svg>',
  pdf: '<svg viewBox="0 0 24 24" width="19" height="19" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"><path d="M7 2.5h7l4 4V20a1.5 1.5 0 0 1-1.5 1.5h-9.5A1.5 1.5 0 0 1 5.5 20V4A1.5 1.5 0 0 1 7 2.5z"/><path d="M14 2.5V7h4"/><path d="M9 13.5h6M9 17h4"/></svg>',
  trash: '<svg viewBox="0 0 24 24" width="15" height="15" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"><path d="M3 6h18M8 6V4a1 1 0 0 1 1-1h6a1 1 0 0 1 1 1v2M19 6l-1 14a2 2 0 0 1-2 2H8a2 2 0 0 1-2-2L5 6M10 11v6M14 11v6"/></svg>',
};

// Client-side view state for the authenticated app. Held in memory and
// re-rendered without refetching; mutations call loadApp() to refresh.
const state = {
  me: null,
  ledger: { name: "" },
  accounts: [],
  transactions: [],
  report: null,
  users: [],
  settings: {},
  pieDir: "out",           // "out" (expenses/spending) | "in" (income/revenue)
  rpt: { period: "year", offset: 0, compare: false, customStart: "", customEnd: "" },
  rptData: null,           // fetched P&L for the current (and prior) range
  view: "ledger",          // "ledger" | "settings" | "reports"
  accountTab: "all",       // "all" | account id
  typeFilter: "all",       // "all" | "business" | "personal" | "untagged"
  sort: { key: "posted", dir: "desc" },
  colFilters: {},          // { <column key>: substring }
};

const canWrite = () => state.me?.role === "owner" || state.me?.role === "bookkeeper";
const isOwner = () => state.me?.role === "owner";

function setTopbarControls(node) {
  const right = document.getElementById("topbar-right");
  if (right) right.replaceChildren(...(node ? [node] : []));
}

async function loadApp() {
  const year = new Date().getFullYear();
  const [ledger, accounts, transactions, cats, report, settings] = await Promise.all([
    api("/ledger").catch(() => ({ name: t("app.title") })),
    api("/accounts").catch(() => []),
    api("/transactions").catch(() => []),
    api("/categories").catch(() => null),
    api(`/reports/schedule-c?year=${year}`).catch(() => null),
    api("/settings").catch(() => ({})),
  ]);
  state.ledger = ledger;
  state.accounts = accounts;
  state.transactions = transactions;
  state.report = report;
  state.settings = settings || {};
  if (cats && Array.isArray(cats.categories) && cats.categories.length) SCHEDULE_C = cats.categories;
  if (cats && Array.isArray(cats.personal_categories) && cats.personal_categories.length) PERSONAL_CATS = cats.personal_categories;
  state.users = isOwner() ? await api("/users").catch(() => []) : [];
  renderApp();
}

function renderApp() {
  setTopbarControls(topbarControls());
  if (state.view === "settings") return mount(renderSettings());
  if (state.view === "reports") return mount(renderReportsView());
  return mount(renderLedger());
}

function topbarControls() {
  const reports = el("button", {
    class: "icon-btn has-tip" + (state.view === "reports" ? " active" : ""),
    "data-tip": t("reports.viewTitle"), "aria-label": t("reports.viewTitle"),
    html: ICONS.chart,
    onclick: () => {
      if (state.view === "reports") { state.view = "ledger"; renderApp(); }
      else { state.view = "reports"; loadReports(); }
    },
  });
  const gear = el("button", {
    class: "icon-btn has-tip" + (state.view === "settings" ? " active" : ""),
    "data-tip": t("app.settings"), "aria-label": t("app.settings"),
    html: ICONS.gear,
    onclick: () => { state.view = state.view === "settings" ? "ledger" : "settings"; renderApp(); },
  });
  const logout = el("button", { class: "ghost small-btn",
    onclick: () => { token.clear(); setTopbarControls(null); route(); } }, t("common.logout"));
  return el("div", { class: "chrome-actions" }, reports, gear, logout);
}

// --- Ledger view ----------------------------------------------------------

function renderLedger() {
  const head = el("div", { class: "ledger-head" },
    el("h2", {}, state.ledger.name || t("app.title")),
    el("div", { class: "head-meta muted small" },
      state.settings.ein ? el("span", {}, `${t("settings.ein")} ${state.settings.ein}`) : null,
      el("span", {}, `${state.me.username} · ${state.me.role}`)));

  const col = el("div", { class: "ledger-col" }, toolbar());
  if (canWrite()) col.append(importCard());
  col.append(transactionsCard(), pieCard());
  // Schedule C is a business-only tax form — only show it on the Business view.
  if (state.typeFilter === "business") col.append(reportsCard());
  col.append(recurringCard());

  const main = el("div", { class: "ledger-main" }, col, exportRail());
  return el("div", {}, head, accountTabs(), main);
}

function accountTabs() {
  const tabs = el("div", { class: "tabs" });
  const mk = (label, val) => el("button", {
    class: "tab" + (state.accountTab === val ? " active" : ""),
    onclick: () => { state.accountTab = val; renderApp(); },
  }, label);
  tabs.append(mk(t("tabs.all"), "all"));
  for (const a of state.accounts) tabs.append(mk(a.nickname, a.id));
  return tabs;
}

function toolbar() {
  const seg = el("div", { class: "segment" });
  const opt = (label, val) => el("button", {
    class: "seg-btn" + (state.typeFilter === val ? " active" : ""),
    onclick: () => { state.typeFilter = val; renderApp(); },
  }, label);
  seg.append(
    opt(t("filter.all"), "all"),
    opt(t("transactions.business"), "business"),
    opt(t("transactions.personal"), "personal"),
    opt(t("transactions.untagged"), "untagged"));
  return el("div", { class: "toolbar" }, el("span", { class: "muted small" }, t("filter.view")), seg);
}

function exportRail() {
  const year = new Date().getFullYear();
  const item = (icon, title, onclick) => el("button",
    { class: "export-btn has-tip tip-left", "data-tip": title, "aria-label": title, html: icon, onclick });
  return el("aside", { class: "export-rail" },
    item(ICONS.csv, t("reports.exportCsv"), () => downloadExport("/export/csv", "opledger.csv")),
    item(ICONS.txf, t("reports.exportTxf"), () => downloadExport(`/export/txf?year=${year}`, `opledger-${year}.txf`)),
    item(ICONS.pdf, t("reports.exportPdf"), () => downloadExport(`/export/pdf?year=${year}`, `opledger-schedule-c-${year}.pdf`)));
}

// Transactions in the current "view" — scoped by the account tab and the
// type segment, but not the table's per-column filters. Shared by the table,
// the pie, and recurring so they all track the active view.
function viewTxns() {
  let rows = state.transactions.slice();
  if (state.accountTab !== "all") rows = rows.filter((r) => r.account_id === state.accountTab);
  if (state.typeFilter === "untagged") rows = rows.filter((r) => !r.txn_type);
  else if (state.typeFilter !== "all") rows = rows.filter((r) => r.txn_type === state.typeFilter);
  return rows;
}

// --- Recurring detection (client-side, mirrors backend services/recurring) -
const _CADENCES = [["weekly", 6, 8], ["biweekly", 12, 16], ["monthly", 27, 32],
  ["quarterly", 85, 95], ["annual", 358, 372]];

function detectRecurring(txns) {
  const norm = (p) => (p || "").trim().toUpperCase().replace(/\s+/g, " ");
  const groups = new Map();
  for (const txn of txns) {
    const key = norm(txn.payee) + "|" + Math.round(Math.abs(Number(txn.amount) || 0));
    if (!groups.has(key)) groups.set(key, []);
    groups.get(key).push(txn);
  }
  const out = [];
  for (const rows of groups.values()) {
    if (rows.length < 3) continue;
    const payee = norm(rows[0].payee);
    if (!payee) continue;
    const dates = rows.map((r) => new Date(r.posted + "T00:00:00")).sort((a, b) => a - b);
    const gaps = [];
    for (let i = 1; i < dates.length; i++) {
      const d = Math.round((dates[i] - dates[i - 1]) / 86400000);
      if (d > 0) gaps.push(d);
    }
    if (gaps.length < 2) continue;
    const avg = gaps.reduce((a, b) => a + b, 0) / gaps.length;
    const cadence = (_CADENCES.find(([, lo, hi]) => avg >= lo && avg <= hi) || [])[0];
    if (!cadence) continue;
    const amount = rows.reduce((a, r) => a + Math.abs(Number(r.amount) || 0), 0) / rows.length;
    out.push({ payee: rows[rows.length - 1].payee || payee, amount, occurrences: rows.length, cadence, last: dates[dates.length - 1] });
  }
  out.sort((a, b) => b.last - a.last);
  return out;
}

// --- Category breakdown pie (per view) ------------------------------------
const PIE_COLORS = ["#2e6b52", "#a23a2c", "#3c7e9a", "#c08a3e", "#6a5b8f",
  "#5a8f6a", "#b5683f", "#7a8a4a", "#9a5a7a", "#4a6b8a"];

function breakdown(rows) {
  const out = state.pieDir !== "in";
  const match = (a) => (out ? a < 0 : a > 0);
  const uncat = t("reports.uncategorized");
  const agg = new Map();
  const add = (k, v) => agg.set(k, (agg.get(k) || 0) + v);
  const view = state.typeFilter;
  // A transaction's category depends on its type (the generalized model).
  const rowCat = (r) => r.txn_type === "business" ? (r.schedule_c_category || uncat)
    : r.txn_type === "personal" ? (r.personal_category || uncat) : uncat;

  let title, keyOf;
  if (view === "business") {
    title = out ? t("pie.expensesByCategory") : t("pie.revenueBySource");
    keyOf = (r) => (out ? (r.schedule_c_category || uncat) : (r.payee || "—"));
  } else if (view === "personal") {
    title = out ? t("pie.spendingByCategory") : t("pie.incomeBySource");
    keyOf = (r) => (out ? (r.personal_category || uncat) : (r.payee || "—"));
  } else if (view === "untagged") {
    title = out ? t("pie.spendingByPayee") : t("pie.incomeByPayee");
    keyOf = (r) => r.payee || "—";
  } else { // all — a mix of both category sets
    title = out ? t("pie.spendingByCategory") : t("pie.incomeBySource");
    keyOf = (r) => (out ? rowCat(r) : (r.payee || "—"));
  }
  for (const r of rows) {
    const a = Number(r.amount) || 0;
    if (match(a)) add(keyOf(r), Math.abs(a));
  }
  let slices = [...agg.entries()].map(([label, value]) => ({ label, value }))
    .filter((s) => s.value > 0).sort((a, b) => b.value - a.value);
  if (slices.length > 9) {
    const other = slices.slice(8).reduce((a, s) => a + s.value, 0);
    slices = slices.slice(0, 8).concat({ label: t("pie.other"), value: other });
  }
  return { title, slices };
}

function donutSvg(slices, size = 176, thickness = 34) {
  const total = slices.reduce((a, s) => a + s.value, 0);
  if (!total) return "";
  const r = size / 2, ir = r - thickness, cx = r, cy = r;
  if (slices.length === 1) {
    return `<svg viewBox="0 0 ${size} ${size}" width="${size}" height="${size}"><circle cx="${cx}" cy="${cy}" r="${(r + ir) / 2}" fill="none" stroke="${slices[0].color}" stroke-width="${thickness}"/></svg>`;
  }
  let angle = -Math.PI / 2;
  const arcs = slices.map((s) => {
    const frac = s.value / total;
    const a2 = angle + frac * 2 * Math.PI;
    const large = frac > 0.5 ? 1 : 0;
    const p = (rad, ang) => `${(cx + rad * Math.cos(ang)).toFixed(2)} ${(cy + rad * Math.sin(ang)).toFixed(2)}`;
    const d = `M${p(r, angle)} A${r} ${r} 0 ${large} 1 ${p(r, a2)} L${p(ir, a2)} A${ir} ${ir} 0 ${large} 0 ${p(ir, angle)} Z`;
    angle = a2;
    return `<path d="${d}" fill="${s.color}"/>`;
  });
  return `<svg viewBox="0 0 ${size} ${size}" width="${size}" height="${size}" role="img">${arcs.join("")}</svg>`;
}

function pieDirToggle() {
  const seg = el("div", { class: "segment" });
  const opt = (label, val) => el("button", {
    class: "seg-btn" + (state.pieDir === val ? " active" : ""),
    onclick: () => { state.pieDir = val; renderApp(); },
  }, label);
  seg.append(opt(t("pie.moneyOut"), "out"), opt(t("pie.moneyIn"), "in"));
  return seg;
}

function pieCard() {
  const { title, slices } = breakdown(viewTxns());
  const card = el("section", { class: "card" });
  card.append(el("div", { class: "pie-head" }, el("h3", {}, title), pieDirToggle()));
  if (!slices.length) {
    card.append(el("p", { class: "muted" }, t("pie.none")));
    return card;
  }
  slices.forEach((s, i) => { s.color = PIE_COLORS[i % PIE_COLORS.length]; });
  const total = slices.reduce((a, s) => a + s.value, 0);
  const money = (v) => Number(v).toFixed(2);
  const legend = el("ul", { class: "pie-legend" }, ...slices.map((s) =>
    el("li", {},
      el("span", { class: "swatch", style: `background:${s.color}` }),
      el("span", { class: "pie-label" }, s.label),
      el("span", { class: "pie-pct num" }, `${(100 * s.value / total).toFixed(0)}%`),
      el("span", { class: "pie-amt num muted" }, money(s.value)))));
  card.append(el("div", { class: "pie-wrap" },
    el("div", { class: "pie-svg", html: donutSvg(slices) }), legend));
  return card;
}

function transactionsCard() {
  const card = el("section", { class: "card" }, el("h3", {}, t("transactions.heading")));
  if (!state.transactions.length) {
    card.append(el("p", { class: "muted" }, t("transactions.none")));
    return card;
  }

  const cols = [
    { key: "posted", label: t("transactions.date") },
    { key: "account", label: t("transactions.account") },
    { key: "payee", label: t("transactions.payee") },
    { key: "amount", label: t("transactions.amount"), num: true },
    { key: "txn_type", label: t("transactions.type") },
    { key: "schedule_c_category", label: t("transactions.category") },
  ];
  const acctName = (id) => (state.accounts.find((a) => a.id === id) || {}).nickname || "—";
  const cellVal = (txn, key) =>
    key === "account" ? acctName(txn.account_id)
    : key === "amount" ? Number(txn.amount)
    : txn[key];

  function visible() {
    let rows = viewTxns();
    for (const [key, val] of Object.entries(state.colFilters)) {
      if (!val) continue;
      const needle = String(val).toLowerCase();
      rows = rows.filter((r) => String(cellVal(r, key) ?? "").toLowerCase().includes(needle));
    }
    const { key, dir } = state.sort;
    rows.sort((a, b) => {
      let av = cellVal(a, key), bv = cellVal(b, key);
      if (key === "amount") { av = Number(av) || 0; bv = Number(bv) || 0; }
      else { av = String(av ?? "").toLowerCase(); bv = String(bv ?? "").toLowerCase(); }
      return av < bv ? (dir === "asc" ? -1 : 1) : av > bv ? (dir === "asc" ? 1 : -1) : 0;
    });
    return rows;
  }

  function row(txn) {
    const shownCat = txn.txn_type === "personal" ? txn.personal_category : txn.schedule_c_category;
    const typeCell = canWrite() ? typeSelect(txn) : el("span", {}, txn.txn_type || t("transactions.untagged"));
    const catCell = canWrite() ? categorySelect(txn) : el("span", {}, shownCat || "—");
    return el("tr", {},
      el("td", {}, txn.posted),
      el("td", {}, acctName(txn.account_id)),
      el("td", {}, txn.payee || "—"),
      el("td", { class: Number(txn.amount) < 0 ? "num neg" : "num" }, Number(txn.amount).toFixed(2)),
      el("td", {}, typeCell),
      el("td", {}, catCell));
  }

  const tbody = el("tbody", {});
  const count = el("p", { class: "muted small txn-count" });
  function repaint() {
    const rows = visible();
    tbody.replaceChildren(...rows.map(row));
    count.textContent = t("transactions.count").replace("{n}", rows.length);
  }

  // Sortable headers + a per-column filter row.
  const headRow = el("tr", {});
  const filterRow = el("tr", { class: "filters" });
  for (const c of cols) {
    const active = state.sort.key === c.key;
    const arrow = active ? (state.sort.dir === "asc" ? " ▲" : " ▼") : "";
    headRow.append(el("th", {
      class: (c.num ? "num " : "") + "sortable" + (active ? " sorted" : ""),
      onclick: () => {
        if (state.sort.key === c.key) state.sort.dir = state.sort.dir === "asc" ? "desc" : "asc";
        else state.sort = { key: c.key, dir: c.num || c.key === "posted" ? "desc" : "asc" };
        renderApp();
      },
    }, c.label + arrow));
    const input = el("input", {
      type: "text", class: "col-filter", placeholder: t("filter.search"),
      value: state.colFilters[c.key] || "",
      oninput: (e) => { state.colFilters[c.key] = e.target.value; repaint(); },
    });
    filterRow.append(el("th", { class: c.num ? "num" : "" }, input));
  }

  card.append(count, el("div", { class: "table-wrap" },
    el("table", { class: "txns" }, el("thead", {}, headRow, filterRow), tbody)));
  repaint();
  return card;
}

function reportsCard() {
  const year = new Date().getFullYear();
  const r = state.report;
  const card = el("section", { class: "card" }, el("h3", {}, `${t("reports.heading")} — ${year}`));
  if (!r || (!Number(r.gross_receipts) && !Number(r.total_expenses))) {
    card.append(el("p", { class: "muted" }, t("reports.none")));
    return card;
  }
  const money = (v) => Number(v).toFixed(2);
  card.append(el("ul", { class: "list" },
    el("li", {}, `${t("reports.grossReceipts")}: ${money(r.gross_receipts)}`),
    el("li", {}, `${t("reports.totalExpenses")}: ${money(r.total_expenses)}`),
    el("li", {}, `${t("reports.netProfit")}: ${money(r.net_profit)}`)));
  if (r.by_category && r.by_category.length) {
    card.append(el("table", { class: "txns" },
      el("thead", {}, el("tr", {},
        el("th", {}, t("reports.category")), el("th", { class: "num" }, t("reports.amount")))),
      el("tbody", {}, ...r.by_category.map((c) =>
        el("tr", {}, el("td", {}, c.category), el("td", { class: "num" }, money(c.amount)))))));
  }
  return card;
}

function recurringCard() {
  const series = detectRecurring(viewTxns());
  const card = el("section", { class: "card" }, el("h3", {}, t("recurring.heading")));
  if (!series.length) {
    card.append(el("p", { class: "muted" }, t("recurring.none")));
    return card;
  }
  card.append(el("table", { class: "txns" },
    el("thead", {}, el("tr", {},
      el("th", {}, t("recurring.payee")), el("th", { class: "num" }, t("recurring.amount")),
      el("th", {}, t("recurring.cadence")), el("th", { class: "num" }, t("recurring.occurrences")))),
    el("tbody", {}, ...series.map((s) =>
      el("tr", {},
        el("td", {}, s.payee),
        el("td", { class: "num" }, Number(s.amount).toFixed(2)),
        el("td", {}, s.cadence),
        el("td", { class: "num" }, s.occurrences))))));
  return card;
}

function importCard() {
  const card = el("section", { class: "card" }, el("h3", {}, t("import.heading")));
  if (!state.accounts.length) {
    card.append(el("p", { class: "muted" }, t("import.needAccount")));
    return card;
  }
  const select = el("select", { required: "true" },
    ...state.accounts.map((a) => el("option", { value: a.id }, a.nickname)));
  if (state.accountTab !== "all") select.value = state.accountTab;
  const file = el("input", { type: "file", accept: ".qfx,.ofx", required: "true" });
  const form = el("form", { class: "inline" },
    field("import.account", select), field("import.file", file),
    el("button", { type: "submit" }, t("import.submit")));
  form.addEventListener("submit", async (e) => {
    e.preventDefault();
    const fd = new FormData();
    fd.append("account_id", select.value);
    fd.append("file", file.files[0]);
    try {
      const res = await api("/transactions/import", { method: "POST", form: fd });
      const msg = t("import.result")
        .replace("{imported}", res.imported)
        .replace("{duplicates}", res.duplicates)
        .replace("{parsed}", res.parsed);
      card.append(el("p", { class: "notice" }, msg));
      setTimeout(loadApp, 1000);
    } catch (err) { showError(card, err.data?.detail || t("errors.generic")); }
  });
  card.append(form);
  return card;
}

// --- Reports view ---------------------------------------------------------

const _LOC = navigator.language || "en";
const _iso = (d) => `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
const _mdy = (d) => d.toLocaleDateString(_LOC, { month: "short", day: "numeric" });

// Most recent fiscal-year start (month `fs`, 1-based) on or before `d`.
function fyStart(d, fs) {
  const m = fs - 1;
  const y = d.getMonth() < m ? d.getFullYear() - 1 : d.getFullYear();
  return new Date(y, m, 1);
}

// Resolve a period + offset (in units) into {start, end, label}, fiscal-aware.
function computeRange(period, offset, fs, custom) {
  const today = new Date();
  if (period === "custom") {
    const s = custom.customStart || _iso(today);
    const e = custom.customEnd || _iso(today);
    return { start: s, end: e, label: `${s} → ${e}` };
  }
  if (period === "week") {
    const base = new Date(today.getFullYear(), today.getMonth(), today.getDate());
    const start = new Date(base);
    start.setDate(base.getDate() - base.getDay() + offset * 7); // Sunday-start week
    const end = new Date(start); end.setDate(start.getDate() + 6);
    return { start: _iso(start), end: _iso(end), label: `${_mdy(start)} – ${_mdy(end)}` };
  }
  if (period === "month") {
    const start = new Date(today.getFullYear(), today.getMonth() + offset, 1);
    const end = new Date(start.getFullYear(), start.getMonth() + 1, 0);
    return { start: _iso(start), end: _iso(end), label: start.toLocaleDateString(_LOC, { month: "long", year: "numeric" }) };
  }
  if (period === "quarter") {
    const fy = fyStart(today, fs);
    const since = (today.getFullYear() - fy.getFullYear()) * 12 + (today.getMonth() - fy.getMonth());
    const qi = Math.floor(since / 3) + offset;
    const start = new Date(fy.getFullYear(), fy.getMonth() + qi * 3, 1);
    const end = new Date(start.getFullYear(), start.getMonth() + 3, 0);
    const fromFS = (((start.getMonth() - (fs - 1)) % 12) + 12) % 12;
    const qNum = Math.floor(fromFS / 3) + 1;
    const fyYear = fyStart(start, fs).getFullYear();
    return { start: _iso(start), end: _iso(end), label: fs === 1 ? `Q${qNum} ${fyYear}` : `Q${qNum} FY${fyYear}` };
  }
  // year (fiscal)
  const fy = fyStart(today, fs);
  const start = new Date(fy.getFullYear() + offset, fy.getMonth(), 1);
  const end = new Date(start.getFullYear() + 1, start.getMonth(), 0);
  return { start: _iso(start), end: _iso(end), label: fs === 1 ? String(start.getFullYear()) : `FY${start.getFullYear()}` };
}

// The fiscal quarter containing `date` → {start, end, label}.
function quarterRangeFor(date, fs) {
  const fy = fyStart(date, fs);
  const since = (date.getFullYear() - fy.getFullYear()) * 12 + (date.getMonth() - fy.getMonth());
  const qi = Math.floor(since / 3);
  const start = new Date(fy.getFullYear(), fy.getMonth() + qi * 3, 1);
  const end = new Date(start.getFullYear(), start.getMonth() + 3, 0);
  const fromFS = (((start.getMonth() - (fs - 1)) % 12) + 12) % 12;
  const qNum = Math.floor(fromFS / 3) + 1;
  const fyYear = fyStart(start, fs).getFullYear();
  return { start: _iso(start), end: _iso(end), label: fs === 1 ? `Q${qNum} ${fyYear}` : `Q${qNum} FY${fyYear}` };
}

// Which quarter the estimate reflects, and the annualization basis:
//  - year view → current quarter, but annualize over the whole displayed year (×1)
//  - quarter view → the displayed quarter (×4)
//  - month/week/custom → the quarter containing the displayed period (×4)
function estimateContext(r, fs, cur) {
  if (r.period === "year") {
    return { start: cur.start, end: cur.end, ppy: 1, label: quarterRangeFor(new Date(), fs).label };
  }
  if (r.period === "quarter") {
    return { start: cur.start, end: cur.end, ppy: 4, label: cur.label };
  }
  const q = quarterRangeFor(new Date(cur.start + "T00:00:00"), fs);
  return { start: q.start, end: q.end, ppy: 4, label: q.label };
}

async function loadReports() {
  const r = state.rpt;
  const fs = Number(state.settings.fiscal_year_start) || 1;
  const acct = state.accountTab !== "all" ? `&account_id=${state.accountTab}` : "";
  const cur = computeRange(r.period, r.offset, fs, r);
  const curData = await api(`/reports/pnl?start=${cur.start}&end=${cur.end}${acct}`).catch(() => null);
  let prior = null, priorData = null;
  if (r.compare && r.period !== "custom") {
    prior = computeRange(r.period, r.offset - 1, fs, r);
    priorData = await api(`/reports/pnl?start=${prior.start}&end=${prior.end}${acct}`).catch(() => null);
  }
  const ec = estimateContext(r, fs, cur);
  const qe = await api(`/reports/quarterly-estimate?start=${ec.start}&end=${ec.end}&periods_per_year=${ec.ppy}`).catch(() => null);
  state.rptData = { cur, curData, prior, priorData, qe, qeLabel: ec.label };
  renderApp();
}

function renderReportsView() {
  const head = el("div", { class: "ledger-head" },
    el("h2", {}, t("reports.viewTitle")),
    el("div", { class: "rpt-headright" },
      el("span", { class: "muted small" }, state.ledger.name || t("app.title")),
      el("button", { class: "ghost small-btn print-btn", onclick: () => window.print() }, t("reports.print"))));

  const seg = el("div", { class: "segment" });
  const pOpt = (label, val) => el("button", {
    class: "seg-btn" + (state.rpt.period === val ? " active" : ""),
    onclick: () => { state.rpt.period = val; state.rpt.offset = 0; loadReports(); },
  }, label);
  seg.append(pOpt(t("reports.week"), "week"), pOpt(t("reports.month"), "month"),
    pOpt(t("reports.quarter"), "quarter"), pOpt(t("reports.year"), "year"), pOpt(t("reports.custom"), "custom"));

  const controls = el("section", { class: "card rpt-controls" }, seg);

  if (state.rpt.period === "custom") {
    const s = el("input", { type: "date", value: state.rpt.customStart });
    const e = el("input", { type: "date", value: state.rpt.customEnd });
    const apply = el("button", { onclick: () => { state.rpt.customStart = s.value; state.rpt.customEnd = e.value; loadReports(); } }, t("reports.apply"));
    controls.append(el("div", { class: "inline" }, field("reports.from", s), field("reports.to", e), apply));
  } else {
    const prev = el("button", { class: "ghost small-btn", onclick: () => { state.rpt.offset -= 1; loadReports(); } }, "◀");
    const next = el("button", { class: "ghost small-btn", onclick: () => { state.rpt.offset += 1; loadReports(); } }, "▶");
    const lbl = el("span", { class: "rpt-period" }, state.rptData?.cur?.label || "…");
    const cmp = el("input", { type: "checkbox", onchange: (ev) => { state.rpt.compare = ev.target.checked; loadReports(); } });
    if (state.rpt.compare) cmp.checked = true;
    controls.append(el("div", { class: "rpt-row" },
      el("div", { class: "rpt-stepper" }, prev, lbl, next),
      el("label", { class: "rpt-compare" }, cmp, t("reports.compare"))));
  }

  if (state.accounts.length > 1) {
    const acc = el("select", {}, el("option", { value: "all" }, t("tabs.all")),
      ...state.accounts.map((a) => el("option", { value: a.id }, a.nickname)));
    acc.value = state.accountTab;
    acc.addEventListener("change", () => { state.accountTab = acc.value === "all" ? "all" : Number(acc.value); loadReports(); });
    controls.append(el("label", { class: "field" }, t("transactions.account"), acc));
  }

  return el("div", {}, head, controls, reportResults(), quarterlyCard());
}

function quarterlyCard() {
  const qe = state.rptData?.qe;
  if (!qe) return null;
  const money = (v) => Number(v || 0).toFixed(2);
  const methodLabel = {
    set_aside: t("settings.methodSetAside"),
    se_income: t("settings.methodSeIncome"),
    safe_harbor: t("settings.methodSafeHarbor"),
  }[qe.method] || qe.method;

  const card = el("section", { class: "card" },
    el("h3", {}, `${t("reports.quarterly")} — ${state.rptData?.qeLabel || ""}`),
    el("p", { class: "muted small" }, methodLabel));
  card.append(el("div", { class: "q-grid" },
    el("div", { class: "q-cell" }, el("span", { class: "q-amt num" }, money(qe.per_quarter)),
      el("span", { class: "q-lbl muted small" }, t("reports.perQuarter"))),
    el("div", { class: "q-cell" }, el("span", { class: "q-amt num" }, money(qe.annual)),
      el("span", { class: "q-lbl muted small" }, t("reports.annualEst")))));

  let rows;
  if (qe.method === "se_income") {
    rows = [[t("reports.seTax"), money(qe.detail.self_employment_tax)],
      [t("reports.incomeTax"), money(qe.detail.income_tax)],
      [t("reports.taxableIncome"), money(qe.detail.taxable_income)]];
  } else if (qe.method === "safe_harbor") {
    rows = [[t("settings.priorYearTax"), money(qe.detail.prior_year_tax)]];
  } else {
    rows = [[t("settings.setAsideRate"), `${Math.round((qe.detail.set_aside_rate || 0) * 100)}%`],
      [t("reports.net"), money(qe.net_profit)]];
  }
  card.append(el("table", { class: "txns" }, el("tbody", {},
    ...rows.map(([k, v]) => el("tr", {}, el("td", {}, k), el("td", { class: "num" }, v))))));
  card.append(el("p", { class: "muted small" }, t("reports.estDisclaimer")));
  return card;
}

// Horizontal bar chart (CSS widths — prints cleanly, no chart-library dep).
// items: [{label, value, prior?}]; `compare` shows a second (prior) bar.
function barChart(items, compare) {
  const max = Math.max(1, ...items.flatMap((i) => [Math.abs(Number(i.value) || 0), compare ? Math.abs(Number(i.prior) || 0) : 0]));
  const pct = (v) => `${(Math.abs(Number(v) || 0) / max) * 100}%`;
  const wrap = el("div", { class: "bars" });
  for (const it of items) {
    const track = el("div", { class: "bar-track" });
    track.append(el("div", { class: "bar-fill cur", style: `width:${pct(it.value)}` }));
    if (compare) track.append(el("div", { class: "bar-fill prior", style: `width:${pct(it.prior)}` }));
    wrap.append(el("div", { class: "bar-row" },
      el("span", { class: "bar-label" }, it.label), track,
      el("span", { class: "bar-val num" }, Number(it.value || 0).toFixed(2))));
  }
  return wrap;
}

function reportResults() {
  const d = state.rptData;
  if (!d || !d.curData) return el("section", { class: "card" }, el("p", { class: "muted" }, t("app.loading")));
  const cur = d.curData, prior = d.priorData;
  const money = (v) => Number(v || 0).toFixed(2);
  const delta = (c, p) => {
    const dv = Number(c) - Number(p);
    const pct = Number(p) ? ` (${dv >= 0 ? "+" : ""}${(100 * dv / Math.abs(p)).toFixed(0)}%)` : "";
    return `${dv >= 0 ? "+" : ""}${money(dv)}${pct}`;
  };
  const card = el("section", { class: "card" }, el("h3", {}, `${t("reports.pnlTitle")} — ${d.cur.label}`));

  const head = el("tr", {}, el("th", {}, ""), el("th", { class: "num" }, d.cur.label));
  if (prior) head.append(el("th", { class: "num" }, d.prior.label), el("th", { class: "num" }, "Δ"));
  const body = el("tbody", {});
  for (const [key, f] of [["reports.income", "income"], ["reports.expenses", "expenses"], ["reports.net", "net"]]) {
    const tr = el("tr", {}, el("td", {}, t(key)), el("td", { class: "num" }, money(cur[f])));
    if (prior) tr.append(el("td", { class: "num" }, money(prior[f])), el("td", { class: "num" }, delta(cur[f], prior[f])));
    body.append(tr);
  }
  card.append(el("table", { class: "txns" }, el("thead", {}, head), body));
  card.append(barChart([
    { label: t("reports.income"), value: cur.income, prior: prior?.income },
    { label: t("reports.expenses"), value: cur.expenses, prior: prior?.expenses },
    { label: t("reports.net"), value: cur.net, prior: prior?.net },
  ], !!prior));

  if (cur.by_category && cur.by_category.length) {
    const priorMap = new Map((prior?.by_category || []).map((c) => [c.category, c.amount]));
    const cth = el("tr", {}, el("th", {}, t("reports.category")), el("th", { class: "num" }, t("reports.amount")));
    if (prior) cth.append(el("th", { class: "num" }, "Δ"));
    card.append(el("h3", { class: "rpt-subhead" }, t("reports.byCategory")),
      el("table", { class: "txns" }, el("thead", {}, cth),
        el("tbody", {}, ...cur.by_category.map((c) => {
          const tr = el("tr", {}, el("td", {}, c.category), el("td", { class: "num" }, money(c.amount)));
          if (prior) tr.append(el("td", { class: "num" }, delta(c.amount, priorMap.get(c.category) || 0)));
          return tr;
        }))));
    card.append(barChart(cur.by_category.map((c) =>
      ({ label: c.category, value: c.amount, prior: priorMap.get(c.category) })), !!prior));
  } else {
    card.append(el("p", { class: "muted" }, t("reports.none")));
  }
  return card;
}

// --- Settings view --------------------------------------------------------

function renderSettings() {
  const head = el("div", { class: "ledger-head" },
    el("h2", {}, t("settings.heading")),
    el("button", { class: "ghost", onclick: () => { state.view = "ledger"; renderApp(); } },
      `← ${t("app.backToLedger")}`));

  const sections = [head, generalSettingsCard()];
  if (canWrite()) sections.push(accountsAdminCard());
  if (isOwner()) sections.push(usersCard());
  return el("div", {}, ...sections);
}

function monthName(m) {
  return new Date(2000, m - 1, 1).toLocaleDateString(navigator.language || "en", { month: "long" });
}

function generalSettingsCard() {
  const s = state.settings || {};
  const card = el("section", { class: "card" }, el("h3", {}, t("settings.general")));

  if (!isOwner()) {
    const fy = s.fiscal_year_start || 1;
    card.append(el("ul", { class: "list" },
      el("li", {}, `${t("settings.ledgerName")}: ${s.name || state.ledger.name || "—"}`),
      el("li", {}, `${t("settings.ein")}: ${s.ein || "—"}`),
      el("li", {}, `${t("settings.fiscalYearStart")}: ${fy === 1 ? t("settings.calendarYear") : monthName(fy)}`)));
    return card;
  }

  const name = el("input", { type: "text", required: "true", value: s.name || state.ledger.name || "" });
  const ein = el("input", { type: "text", value: s.ein || "", placeholder: t("settings.einPlaceholder") });
  const fiscal = el("select", {}, ...Array.from({ length: 12 }, (_, i) =>
    el("option", { value: i + 1 }, i === 0 ? `${monthName(1)} (${t("settings.calendarYear")})` : monthName(i + 1))));
  fiscal.value = s.fiscal_year_start || 1;

  const method = el("select", {},
    el("option", { value: "set_aside" }, t("settings.methodSetAside")),
    el("option", { value: "se_income" }, t("settings.methodSeIncome")),
    el("option", { value: "safe_harbor" }, t("settings.methodSafeHarbor")));
  method.value = s.quarterly_method || "set_aside";

  const rate = el("input", { type: "number", min: "0", max: "100", step: "1",
    value: Math.round((s.quarterly_set_aside_rate ?? 0.27) * 100) });
  const filing = el("select", {},
    el("option", { value: "single" }, t("settings.filingSingle")),
    el("option", { value: "married_joint" }, t("settings.filingMarriedJoint")),
    el("option", { value: "married_separate" }, t("settings.filingMarriedSeparate")),
    el("option", { value: "head_of_household" }, t("settings.filingHoH")));
  filing.value = s.quarterly_filing_status || "single";
  const priorTax = el("input", { type: "number", min: "0", step: "0.01", value: s.quarterly_prior_year_tax ?? 0 });

  const pSetAside = el("label", { class: "field" }, t("settings.setAsideRate"), rate);
  const pFiling = el("label", { class: "field" }, t("settings.filingStatus"), filing);
  const pPrior = el("label", { class: "field" }, t("settings.priorYearTax"), priorTax);
  const params = el("div", {}, pSetAside, pFiling, pPrior);
  const syncParams = () => {
    pSetAside.style.display = method.value === "set_aside" ? "" : "none";
    pFiling.style.display = method.value === "se_income" ? "" : "none";
    pPrior.style.display = method.value === "safe_harbor" ? "" : "none";
  };
  method.addEventListener("change", syncParams);

  const form = el("form", {},
    el("label", { class: "field" }, t("settings.ledgerName"), name),
    el("label", { class: "field" }, t("settings.ein"), ein),
    el("label", { class: "field" }, t("settings.fiscalYearStart"), fiscal),
    el("label", { class: "field" }, t("settings.quarterlyMethod"), method),
    params,
    el("button", { type: "submit" }, t("common.save")));
  syncParams();
  form.addEventListener("submit", async (e) => {
    e.preventDefault();
    try {
      await api("/settings", { method: "PATCH", body: {
        name: name.value,
        ein: ein.value || null,
        fiscal_year_start: Number(fiscal.value),
        quarterly_method: method.value,
        quarterly_set_aside_rate: Number(rate.value) / 100,
        quarterly_filing_status: filing.value,
        quarterly_prior_year_tax: Number(priorTax.value),
      } });
      card.append(el("p", { class: "notice" }, t("settings.saved")));
      setTimeout(loadApp, 800);
    } catch (err) { showError(card, err.data?.detail || t("errors.generic")); }
  });
  card.append(form);
  return card;
}

function accountsAdminCard() {
  const card = el("section", { class: "card" }, el("h3", {}, t("accounts.heading")));
  if (!state.accounts.length) card.append(el("p", { class: "muted" }, t("accounts.none")));
  for (const a of state.accounts) card.append(accountRow(card, a));

  card.append(el("p", { class: "field-label muted small" }, t("accounts.add")));
  const nick = el("input", { type: "text", required: "true", placeholder: t("accounts.nickname") });
  const inst = el("input", { type: "text", placeholder: t("accounts.institution") });
  const num = el("input", { type: "text", placeholder: t("accounts.accountNumber") });
  const form = el("form", { class: "inline" }, nick, inst, num,
    el("button", { type: "submit" }, t("accounts.add")));
  form.addEventListener("submit", async (e) => {
    e.preventDefault();
    try {
      await api("/accounts", { method: "POST", body: {
        nickname: nick.value, institution: inst.value || null, account_number: num.value || null,
      } });
      loadApp();
    } catch (err) { showError(card, err.data?.detail || t("errors.generic")); }
  });
  card.append(form);
  return card;
}

function accountRow(card, a) {
  const nick = el("input", { type: "text", required: "true", value: a.nickname });
  const inst = el("input", { type: "text", placeholder: t("accounts.institution"), value: a.institution || "" });
  const num = el("input", { type: "text", placeholder: t("accounts.accountNumber"), value: a.account_number || "" });
  const del = el("button", {
    type: "button", class: "icon-btn danger has-tip", "data-tip": t("common.delete"), "aria-label": t("common.delete"),
    html: ICONS.trash,
    onclick: async () => {
      try { await api(`/accounts/${a.id}`, { method: "DELETE" }); loadApp(); }
      catch (err) { showError(card, err.data?.detail || t("errors.generic")); }
    },
  });
  const row = el("form", { class: "inline acct-row" }, nick, inst, num,
    el("button", { type: "submit" }, t("common.save")), del);
  row.addEventListener("submit", async (e) => {
    e.preventDefault();
    try {
      await api(`/accounts/${a.id}`, { method: "PATCH", body: {
        nickname: nick.value, institution: inst.value || null, account_number: num.value || null,
      } });
      loadApp();
    } catch (err) { showError(card, err.data?.detail || t("errors.generic")); }
  });
  return row;
}

function roleSelect(selected) {
  const sel = el("select", {},
    el("option", { value: "viewer" }, t("users.roleViewer")),
    el("option", { value: "bookkeeper" }, t("users.roleBookkeeper")),
    el("option", { value: "owner" }, t("users.roleOwner")));
  if (selected) sel.value = selected;
  return sel;
}

function usersCard() {
  const card = el("section", { class: "card" }, el("h3", {}, t("users.heading")));
  const ownerCount = state.users.filter((u) => u.role === "owner").length;
  for (const u of state.users) card.append(userRow(card, u, ownerCount));

  card.append(el("p", { class: "field-label muted small" }, t("users.add")));
  const name = el("input", { type: "text", required: "true", placeholder: t("users.username") });
  const pw = el("input", { type: "password", required: "true", minlength: "8", placeholder: t("users.password") });
  const role = roleSelect("viewer");
  const form = el("form", { class: "inline" }, name, pw, role,
    el("button", { type: "submit" }, t("users.add")));
  form.addEventListener("submit", async (e) => {
    e.preventDefault();
    try {
      await api("/users", { method: "POST", body: { username: name.value, password: pw.value, role: role.value } });
      loadApp();
    } catch (err) { showError(card, err.data?.detail || t("errors.generic")); }
  });
  card.append(form);
  return card;
}

function userRow(card, u, ownerCount) {
  const role = roleSelect(u.role);
  const pw = el("input", { type: "password", minlength: "8", placeholder: t("users.newPassword") });
  // The last Owner can't be deleted or demoted; you can't delete yourself.
  const isSelf = u.id === state.me.id;
  const lastOwner = u.role === "owner" && ownerCount <= 1;
  const del = el("button", {
    type: "button", class: "icon-btn danger has-tip", "data-tip": t("common.delete"), "aria-label": t("common.delete"),
    html: ICONS.trash,
    onclick: async () => {
      try { await api(`/users/${u.id}`, { method: "DELETE" }); loadApp(); }
      catch (err) { showError(card, err.data?.detail || t("errors.generic")); }
    },
  });
  if (isSelf || lastOwner) del.disabled = true;
  if (lastOwner) role.disabled = true;  // can't demote the last Owner

  const row = el("form", { class: "inline acct-row" },
    el("span", { class: "row-name" }, u.username), role, pw,
    el("button", { type: "submit" }, t("common.save")), del);
  row.addEventListener("submit", async (e) => {
    e.preventDefault();
    const body = { role: role.value };
    if (pw.value) body.password = pw.value;
    try {
      await api(`/users/${u.id}`, { method: "PATCH", body });
      loadApp();
    } catch (err) { showError(card, err.data?.detail || t("errors.generic")); }
  });
  return row;
}

async function downloadExport(path, filename) {
  const tok = token.get();
  const res = await fetch(`${API}${path}`, { headers: tok ? { Authorization: `Bearer ${tok}` } : {} });
  if (!res.ok) return;
  const blob = await res.blob();
  const url = URL.createObjectURL(blob);
  const a = el("a", { href: url, download: filename });
  document.body.append(a);
  a.click();
  a.remove();
  URL.revokeObjectURL(url);
}

function typeSelect(txn) {
  const sel = el("select", {},
    el("option", { value: "" }, t("transactions.untagged")),
    el("option", { value: "personal" }, t("transactions.personal")),
    el("option", { value: "business" }, t("transactions.business")));
  sel.value = txn.txn_type || "";
  // Switching type changes which category set applies — clear it and re-render
  // so the row's category dropdown rebuilds with the right options.
  sel.addEventListener("change", () => saveTag(txn, sel.value, ""));
  return sel;
}

function categorySelect(txn) {
  const personal = txn.txn_type === "personal";
  const list = personal ? PERSONAL_CATS : SCHEDULE_C;
  const current = personal ? txn.personal_category : txn.schedule_c_category;
  const sel = el("select", {},
    el("option", { value: "" }, t("transactions.selectCategory")),
    ...list.map((c) => el("option", { value: c }, c)));
  sel.value = current || "";
  if (!txn.txn_type) sel.disabled = true;  // tag a type first
  sel.addEventListener("change", () => saveTag(txn, txn.txn_type, sel.value));
  return sel;
}

async function saveTag(txn, type, category) {
  if (!type) return;
  const body = { txn_type: type };
  if (type === "business") body.schedule_c_category = category || null;
  else body.personal_category = category || null;
  try {
    await api(`/transactions/${txn.id}/tag`, { method: "POST", body });
    txn.txn_type = type;
    if (type === "business") { txn.schedule_c_category = category || null; txn.personal_category = null; }
    else { txn.personal_category = category || null; txn.schedule_c_category = null; }
    renderApp();  // dependent panels (pie, Schedule C, recurring) update live
  } catch { /* leave the control as-is on failure */ }
}

// --- Router ---------------------------------------------------------------

function mount(node) {
  const root = app();
  root.replaceChildren(node);
}

async function route() {
  const status = await api("/setup/status").catch(() => ({ initialized: false, unlocked: false }));
  setTopbarControls(null);
  if (!status.initialized) return renderSetup();
  if (!status.unlocked) return renderUnlock();
  if (!token.get()) return renderLogin();
  try {
    state.me = await api("/me");
    return loadApp();
  } catch (err) {
    token.clear();
    return renderLogin();
  }
}

async function main() {
  // This runs as a chromeless desktop app — suppress the browser's default
  // right-click context menu so it feels native rather than web-page-like.
  document.addEventListener("contextmenu", (e) => e.preventDefault());
  await initI18n();
  await route();
}

main();
