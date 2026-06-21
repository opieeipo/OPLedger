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

async function renderDashboard(me) {
  const canWrite = me.role === "owner" || me.role === "bookkeeper";
  const isOwner = me.role === "owner";

  const [ledger, accounts, transactions, cats] = await Promise.all([
    api("/ledger").catch(() => ({ name: t("app.title") })),
    api("/accounts").catch(() => []),
    api("/transactions").catch(() => []),
    api("/categories").catch(() => null),
  ]);
  if (cats && Array.isArray(cats.categories) && cats.categories.length) {
    SCHEDULE_C = cats.categories;
  }

  const header = el("div", { class: "dash-head" },
    el("div", {}, el("h2", {}, ledger.name), el("p", { class: "muted small" }, `${me.username} · ${me.role}`)),
    el("button", { class: "ghost", onclick: () => { token.clear(); route(); } }, t("common.logout")),
  );

  const sections = [header];
  sections.push(renderAccounts(accounts, canWrite));
  if (canWrite) sections.push(renderImport(accounts));
  sections.push(await renderReports());
  sections.push(renderTransactions(transactions, canWrite, accounts));
  if (isOwner) sections.push(await renderUsers());

  mount(el("div", { class: "dashboard" }, ...sections));
}

function renderAccounts(accounts, canWrite) {
  const list = accounts.length
    ? el("ul", { class: "list" }, ...accounts.map((a) =>
        el("li", {}, `${a.nickname}${a.institution ? " — " + a.institution : ""}`)))
    : el("p", { class: "muted" }, t("accounts.none"));

  const section = el("section", { class: "card" }, el("h3", {}, t("accounts.heading")), list);

  if (canWrite) {
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
        route();
      } catch (err) { showError(section, err.data?.detail || t("errors.generic")); }
    });
    section.append(form);
  }
  return section;
}

function renderImport(accounts) {
  const section = el("section", { class: "card" }, el("h3", {}, t("import.heading")));
  if (!accounts.length) {
    section.append(el("p", { class: "muted" }, t("import.needAccount")));
    return section;
  }
  const select = el("select", { required: "true" },
    ...accounts.map((a) => el("option", { value: a.id }, a.nickname)));
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
      section.append(el("p", { class: "notice" }, msg));
      setTimeout(route, 1200);
    } catch (err) { showError(section, err.data?.detail || t("errors.generic")); }
  });
  section.append(form);
  return section;
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

async function renderReports() {
  const year = new Date().getFullYear();
  const r = await api(`/reports/schedule-c?year=${year}`).catch(() => null);
  const section = el("section", { class: "card" },
    el("h3", {}, `${t("reports.heading")} — ${year}`));

  const exports = el("div", { class: "inline" },
    el("button", { class: "ghost", onclick: () => downloadExport("/export/csv", "opledger.csv") }, t("reports.exportCsv")),
    el("button", { class: "ghost", onclick: () => downloadExport(`/export/txf?year=${year}`, `opledger-${year}.txf`) }, t("reports.exportTxf")),
    el("button", { class: "ghost", onclick: () => downloadExport(`/export/pdf?year=${year}`, `opledger-schedule-c-${year}.pdf`) }, t("reports.exportPdf")));
  section.append(exports);

  if (!r || (!Number(r.gross_receipts) && !Number(r.total_expenses))) {
    section.append(el("p", { class: "muted" }, t("reports.none")));
    return section;
  }
  const money = (v) => Number(v).toFixed(2);
  section.append(el("ul", { class: "list" },
    el("li", {}, `${t("reports.grossReceipts")}: ${money(r.gross_receipts)}`),
    el("li", {}, `${t("reports.totalExpenses")}: ${money(r.total_expenses)}`),
    el("li", {}, `${t("reports.netProfit")}: ${money(r.net_profit)}`)));
  if (r.by_category.length) {
    section.append(el("table", { class: "txns" },
      el("thead", {}, el("tr", {},
        el("th", {}, t("reports.category")), el("th", { class: "num" }, t("reports.amount")))),
      el("tbody", {}, ...r.by_category.map((c) =>
        el("tr", {}, el("td", {}, c.category), el("td", { class: "num" }, money(c.amount)))))));
  }
  return section;
}

function renderTransactions(transactions, canWrite, accounts = []) {
  const section = el("section", { class: "card" }, el("h3", {}, t("transactions.heading")));
  if (!transactions.length) {
    section.append(el("p", { class: "muted" }, t("transactions.none")));
    return section;
  }
  const acctName = new Map(accounts.map((a) => [a.id, a.nickname]));

  // Account filter for the multi-account ledger view (client-side).
  const filter = el("select", {},
    el("option", { value: "" }, t("transactions.allAccounts")),
    ...accounts.map((a) => el("option", { value: a.id }, a.nickname)));
  const tbody = el("tbody", {});

  function row(txn) {
    const typeCell = canWrite ? typeSelect(txn) : el("span", {}, txn.txn_type || t("transactions.untagged"));
    const catCell = canWrite ? categorySelect(txn) : el("span", {}, txn.schedule_c_category || "—");
    return el("tr", {},
      el("td", {}, txn.posted),
      el("td", {}, acctName.get(txn.account_id) || "—"),
      el("td", {}, txn.payee || "—"),
      el("td", { class: "num" }, Number(txn.amount).toFixed(2)),
      el("td", {}, typeCell),
      el("td", {}, catCell),
    );
  }
  function repaint() {
    const sel = filter.value ? Number(filter.value) : null;
    const shown = sel ? transactions.filter((t) => t.account_id === sel) : transactions;
    tbody.replaceChildren(...shown.map(row));
  }
  filter.addEventListener("change", repaint);

  if (accounts.length > 1) {
    section.append(el("label", { class: "field" }, t("transactions.account"), filter));
  }
  section.append(el("table", { class: "txns" },
    el("thead", {}, el("tr", {},
      el("th", {}, t("transactions.date")), el("th", {}, t("transactions.account")),
      el("th", {}, t("transactions.payee")),
      el("th", { class: "num" }, t("transactions.amount")), el("th", {}, t("transactions.type")),
      el("th", {}, t("transactions.category")))),
    tbody));
  repaint();
  return section;
}

function typeSelect(txn) {
  const sel = el("select", {},
    el("option", { value: "" }, t("transactions.untagged")),
    el("option", { value: "personal" }, t("transactions.personal")),
    el("option", { value: "business" }, t("transactions.business")));
  sel.value = txn.txn_type || "";
  sel.addEventListener("change", () => saveTag(txn, sel.value, txn.schedule_c_category));
  return sel;
}

function categorySelect(txn) {
  const sel = el("select", {},
    el("option", { value: "" }, t("transactions.selectCategory")),
    ...SCHEDULE_C.map((c) => el("option", { value: c }, c)));
  sel.value = txn.schedule_c_category || "";
  sel.addEventListener("change", () => saveTag(txn, txn.txn_type || "business", sel.value));
  return sel;
}

async function saveTag(txn, type, category) {
  if (!type) return;
  try {
    await api(`/transactions/${txn.id}/tag`, { method: "POST", body: {
      txn_type: type, schedule_c_category: type === "business" ? category || null : null,
    } });
    txn.txn_type = type;
    txn.schedule_c_category = category;
  } catch { /* leave the control as-is on failure */ }
}

async function renderUsers() {
  const users = await api("/users").catch(() => []);
  const section = el("section", { class: "card" }, el("h3", {}, t("users.heading")));
  section.append(el("ul", { class: "list" }, ...users.map((u) =>
    el("li", {}, `${u.username} · ${u.role}`))));

  const name = el("input", { type: "text", required: "true", placeholder: t("users.username") });
  const pw = el("input", { type: "password", required: "true", minlength: "8", placeholder: t("users.password") });
  const role = el("select", {},
    el("option", { value: "viewer" }, t("users.roleViewer")),
    el("option", { value: "bookkeeper" }, t("users.roleBookkeeper")),
    el("option", { value: "owner" }, t("users.roleOwner")));
  const form = el("form", { class: "inline" }, name, pw, role,
    el("button", { type: "submit" }, t("users.add")));
  form.addEventListener("submit", async (e) => {
    e.preventDefault();
    try {
      await api("/users", { method: "POST", body: { username: name.value, password: pw.value, role: role.value } });
      route();
    } catch (err) { showError(section, err.data?.detail || t("errors.generic")); }
  });
  section.append(form);
  return section;
}

// --- Router ---------------------------------------------------------------

function mount(node) {
  const root = app();
  root.replaceChildren(node);
}

async function route() {
  const status = await api("/setup/status").catch(() => ({ initialized: false, unlocked: false }));
  if (!status.initialized) return renderSetup();
  if (!status.unlocked) return renderUnlock();
  if (!token.get()) return renderLogin();
  try {
    const me = await api("/me");
    return renderDashboard(me);
  } catch (err) {
    token.clear();
    return renderLogin();
  }
}

async function main() {
  await initI18n();
  await route();
}

main();
