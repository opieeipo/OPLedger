# OPLedger Roadmap

Tracks planned work beyond the initial "ledger paper" redesign. Checked items
are done; order reflects the agreed build sequence.

## Batch 1 — UI restructure ✅

- [x] **Settings (gear) screen** — a second screen behind a gear icon in the
      title bar. Move Users management, add-user, and account administration here.
- [x] **Account tabs** — a tab bar at the top to switch the ledger between
      accounts (plus an "All" tab).
- [x] **Business / Personal filter** — filter the ledger by `txn_type`
      (segmented All / Business / Personal / Untagged control).
- [x] **Sortable + filterable headers** — click a transactions header to sort;
      per-column filter inputs on every column.
- [x] **Exports as icons** — CSV / TXF / PDF as muted icons in a vertical rail
      beside the ledger (stacks below on mobile).
- [x] **Accounts full CRUD** — `PATCH`/`DELETE` endpoints; editable rows in
      Settings. Delete refuses (409) if the account still has transactions.
- [x] **Users full CRUD + RBAC** — `PATCH` (role/password) added; editable rows.
      Users API is owner-only; last Owner can't be deleted or demoted; can't
      delete your own account (enforced backend + disabled in UI).
- [x] **Tooltips** — custom CSS tooltips on icon buttons (native `title` was
      unreliable).

## Batch 2 — Reporting

- [x] **View-aware panels** — Schedule C shows only on the Business view (it's a
      business-only tax form); recurring detection runs per-view (client-side),
      so it works for personal and business and filters with the segment/tab.
- [x] **Category-breakdown pie** per view — hand-drawn SVG donut (no chart
      library), with a **Money out / Money in** toggle so each view shows both
      directions: Business → expenses by category / revenue by source;
      Personal/Untagged → spending / income by payee; All → out/in by type.
- [x] **Editable company name** — Settings → General (was previously fixed at
      setup); round-trips through `/ledger`.
- [x] **Desktop polish** — default right-click context menu suppressed in the
      app window.
- [x] **Generalized categories** — `personal_category` column (+ self-healing
      `ADD COLUMN` migration), configurable `personal_categories.yaml`, the
      category dropdown adapts per row (Business → Schedule C, Personal →
      personal cats, Untagged → disabled), and the pie breaks personal down by
      personal category (All = a mix). Tagging updates dependent panels live.
- [x] **Date-range picker** — a Reports view (chart icon in the title bar) with
      Week / Month / Quarter / Year / Custom presets, prev/next stepping, and a
      "Compare to previous" toggle that yields WoW / MoM / QoQ / YoY. Fiscal-year
      aware (uses the fiscal_year_start setting for quarter/year boundaries).
- [x] **A report per range** — each range drives a P&L (income / expenses / net
      + by-category) with prior-period and Δ columns when comparing. Backend
      `/reports/pnl?start=&end=&account_id=` already existed.
- [x] **Contextual quarterly estimate** — the estimate card reflects the quarter
      tied to the view: Year → current quarter; Quarter → the shown quarter;
      Month/Week/Custom → the quarter containing the period (annualized basis).
- [x] **Charts + print/PDF** — horizontal bar charts for the P&L and by-category
      elements (current-vs-prior when comparing), and a "Print / Save as PDF"
      button with a print stylesheet that hides app chrome.
- [x] **Fiscal vs calendar year** — setting in Settings → General (month
      dropdown, default calendar year). Reports honoring it land with the
      date-range work below.
- [x] **EIN field** — captured in Settings → General, shown in the ledger
      header; will surface on IRS-bound reports.
- [x] **Quarterly method selector** — Settings → General captures the method +
      its params (set-aside % / filing status / prior-year tax). The actual
      calculation report lands in increment 3.
- [x] **Quarterly estimates** — all three methods (set-aside %, SE+income tax,
      prior-year safe harbor), selectable in Settings, shown as a card in the
      Reports view (per-quarter + annual + method breakdown). Year-specific tax
      constants live in editable `config/tax_constants.yaml` (recent-year
      defaults). Estimate-only, with a disclaimer.
- [x] **IRS-format reports** — the PDF export now mirrors the official Schedule
      C: Part I income (lines 1–7), Part II expenses by official line number
      (8–27a, categories mapped, unknowns roll into 27a), line 28 total, and
      29–31 net profit, with proprietor name + EIN from settings. Generated
      summary, not the fillable gov form. TXF still targets tax software.

## Batch 3 — Troubleshooting

- [ ] **Import audit log** — the importer records each run (file, account,
      parsed/imported/duplicate/error detail) instead of only returning counts.
- [ ] **Stats screen** — surface the log + import health to diagnose bad imports.

## Browser-constrained — building the realistic alternative

- [ ] **Bank access (no iframe).** Banks block framing via `X-Frame-Options` /
      CSP `frame-ancestors`, so embedding their sites is not possible. Instead:
      a configurable list of bank links that open in a normal window.
- [ ] **Download auto-detect (launcher-spawned watcher).** The browser page is
      sandboxed and can't watch the filesystem — but the launcher is a native
      host process, so it spawns a small **Python watcher sidecar** (uses the
      existing `.venv`; portable across macOS/Linux/Windows with no extra system
      deps, unlike native fswatch/inotify/FileSystemWatcher). The watcher
      monitors a configurable Downloads path (default to the OS Downloads dir,
      overridable in Settings), debounces, parses `<BANKACCTFROM>` to match an
      account, and POSTs new `.qfx`/`.ofx` files to a new localhost-bound ingest
      endpoint that reuses the existing import/dedup pipeline. Lifecycle is tied
      to the launcher (spawned with the backend, torn down on window close).
      Open design point: auth — the watcher is a host process, not the browser
      holding a JWT, so it uses a launch-generated shared secret handed to both
      backend and watcher.
