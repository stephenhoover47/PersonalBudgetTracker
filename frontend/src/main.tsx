import React, { useEffect, useRef, useState } from "react";
import { createRoot } from "react-dom/client";
import { cents, dollars as money } from "./money";
import "./style.css";
import { displayMonth, displayDate, shiftMonth } from "./dates";

type Category = { archived?: boolean; id: number; name: string; mode: string };
type Account = { archived?: boolean; id: number; name: string; kind: string };
type Allocation = { category_id: number; cents: number };
type Tx = {
  id: number;
  account_id: number;
  date: string;
  merchant: string;
  cents: number;
  kind: string;
  version: number;
  splits: Allocation[];
};
type BudgetCategory = Category & {
  budget_cents: number;
  rollover_cents: number;
  rollover: boolean;
  configured: boolean;
  inherited_from: string | null;
  spent_cents: number;
  remaining_cents: number;
};
type Saving = { id: number; name: string; cents: number; inherited_from: string | null };
type Dashboard = {
  spent_cents: number;
  budget_cents: number;
  remaining_cents: number;
  review_count: number;
  income_cents: number;
  contribution_cents: number;
  planned_savings_cents: number;
  categories: BudgetCategory[];
  savings: Saving[];
};
type Me = { name: string; household: string; members: string[]; csrf: string };
type Preview = {
  id: number;
  rows: { date: string; merchant: string; cents: number; duplicate: boolean }[];
  duplicates: number;
  net_cents: number;
  new_net_cents: number;
};
type History = {
  id: number;
  account_id: number;
  status: string;
  created: number;
  imported: number;
  duplicates: number;
};
const kinds = [
  "review",
  "expense",
  "refund",
  "reimbursement",
  "income",
  "contribution",
  "transfer",
  "card_payment",
  "savings",
  "loan_payment",
];
const labels: Record<string, string> = {
  review: "Needs review",
  expense: "Purchase / expense",
  refund: "Refund",
  reimbursement: "Reimbursement",
  income: "Income",
  contribution: "Household contribution",
  transfer: "Owned-account transfer",
  card_payment: "Credit card payment",
  savings: "Savings transfer",
  loan_payment: "Loan payment",
};
const spending = (kind: string) =>
  ["expense", "refund", "reimbursement", "loan_payment"].includes(kind);
const currentMonth = () =>
  new Intl.DateTimeFormat("sv-SE", {
    timeZone: "America/New_York",
    year: "numeric",
    month: "2-digit",
  }).format(new Date());
let csrf = "";
async function api<T>(
  path: string,
  method = "GET",
  body?: unknown,
): Promise<T> {
  const response = await fetch("/api" + path, {
    method,
    credentials: "same-origin",
    headers: {
      "Content-Type": "application/json",
      "X-Requested-With": "household",
      ...(csrf ? { "X-CSRF-Token": csrf } : {}),
    },
    body: body === undefined ? undefined : JSON.stringify(body),
  });
  const data = await response.json();
  if (!response.ok)
    throw new Error(
      typeof data.detail === "string"
        ? data.detail
        : `Request failed (${response.status}). Check your entries.`,
    );
  return data;
}
function KindSelect({
  value,
  onChange,
}: {
  value: string;
  onChange: (v: string) => void;
}) {
  return (
    <select
      aria-label="Transaction type"
      value={value}
      onChange={(e) => onChange(e.target.value)}
    >
      {kinds.map((k) => (
        <option key={k} value={k}>
          {labels[k]}
        </option>
      ))}
    </select>
  );
}
function App() {
  const [planEditing, setPlanEditing] = useState(false);
  const [planSaving, setPlanSaving] = useState(false);
  function leavePlan() {
    if (planSaving) return false;
    if (planEditing && !window.confirm("Discard unsaved plan changes?")) return false;
    setPlanEditing(false); return true;
  }
  function changeMonth(value: string) {
    if (value === month) return true;
    if (!leavePlan()) return false;
    setNotice(""); setMonth(value); setOffset(0); return true;
  }
  const [me, setMe] = useState<Me | null>(null),
    [boot, setBoot] = useState(true),
    [error, setError] = useState(""),
    [notice, setNotice] = useState(""),
    [busy, setBusy] = useState(false);
  const [tab, setTab] = useState(new URLSearchParams(location.search).has("bank_link") ? "Settings" : "Overview"),
    [month, setMonth] = useState(currentMonth()),
    [dashboard, setDashboard] = useState<Dashboard | null>(null),
    [accounts, setAccounts] = useState<Account[]>([]),
    [categories, setCategories] = useState<Category[]>([]);
  const [txs, setTxs] = useState<Tx[]>([]),
    [total, setTotal] = useState(0),
    [offset, setOffset] = useState(0),
    [search, setSearch] = useState(""),
    [kind, setKind] = useState(""),
    [account, setAccount] = useState(""),
    [category, setCategory] = useState(""),
    [sort, setSort] = useState("newest"),
    [creditsFirst, setCreditsFirst] = useState(false),
    [selected, setSelected] = useState<number[]>([]),
    [editing, setEditing] = useState<Tx | null>(null);
  const [bulkKind, setBulkKind] = useState("expense"),
    [bulkCategory, setBulkCategory] = useState(""),
    [history, setHistory] = useState<History[]>([]);
  const [preview, setPreview] = useState<Preview | null>(null),
    [format, setFormat] = useState("canonical"),
    [positive, setPositive] = useState(true),
    [csv, setCsv] = useState(""),
    [reconcile, setReconcile] = useState(""),
    [importAccount, setImportAccount] = useState("");
  const scope = JSON.stringify([me?.household, month]);
  const txScope = JSON.stringify([
    scope,
    search,
    kind,
    account,
    category,
    sort,
    creditsFirst,
    offset,
  ]);
  const activeScope = useRef(scope);
  const activeTxScope = useRef(txScope);
  const pending = useRef(0);
  const loadGeneration = useRef(0);
  const txGeneration = useRef(0);
  activeScope.current = scope;
  activeTxScope.current = txScope;
  async function load() {
    const generation = ++loadGeneration.current;
    const [d, a, c, h] = await Promise.all([
      api<Dashboard>(`/dashboard?month=${month}`),
      api<Account[]>("/accounts"),
      api<Category[]>("/categories"),
      api<History[]>("/imports"),
    ]);
    if (scope !== activeScope.current || generation !== loadGeneration.current)
      return;
    setDashboard(d);
    setAccounts(a);
    setCategories(c);
    setHistory(h);
  }
  async function loadTx() {
    const generation = ++txGeneration.current;
    const p = new URLSearchParams({
      month,
      search,
      offset: String(offset),
      limit: "50",
      sort,
      credits_first: String(creditsFirst),
    });
    if (kind) p.set("kind", kind);
    if (account) p.set("account_id", account);
    if (category) p.set("category_id", category);
    const result = await api<{ items: Tx[]; total: number }>(
      "/transactions?" + p,
    );
    if (
      txScope !== activeTxScope.current ||
      generation !== txGeneration.current
    )
      return;
    setTxs(result.items);
    setTotal(result.total);
    setSelected([]);
  }
  async function run(action: () => Promise<void>, clearFeedback = true) {
    pending.current += 1;
    setBusy(true);
    if (clearFeedback) {
      setError("");
      setNotice("");
    }
    try {
      await action();
    } catch (e) {
      setError((e as Error).message);
    } finally {
      pending.current -= 1;
      setBusy(pending.current > 0);
    }
  }
  useEffect(() => {
    api<Me>("/me")
      .then((m) => {
        csrf = m.csrf;
        setMe(m);
      })
      .catch(() => {})
      .finally(() => setBoot(false));
  }, []);
  useEffect(() => {
    if (me) void run(load, false);
  }, [me, month]);
  useEffect(() => {
    if (!me) return;
    let active = true;
    const timer = setTimeout(() => {
      if (active) void run(loadTx, false);
    }, 200);
    return () => {
      active = false;
      clearTimeout(timer);
    };
  }, [me, month, search, kind, account, category, sort, creditsFirst, offset]);
  async function refresh() {
    await load();
    await loadTx();
  }
  if (boot)
    return (
      <main className="login">
        <p>Opening your household…</p>
      </main>
    );
  if (!me)
    return (
      <main className="login">
        <img className="login-logo" src="/brand/pocketwatcher-logo.png" alt="PocketWatcher" width="900" height="461" />
        <div className="login-card">
          <span className="eyebrow">A LITTLE CLARITY, TOGETHER</span>
          <h1>
            Your household.
            <br />
            One clear picture.
          </h1>
          <p>Shared spending, thoughtful plans, room for what matters.</p>
          <form
            onSubmit={(e) => {
              e.preventDefault();
              const f = new FormData(e.currentTarget);
              void run(async () => {
                const r = await api<{ csrf: string }>("/auth/login", "POST", {
                  email: f.get("email"),
                  password: f.get("password"),
                });
                csrf = r.csrf;
                setMe(await api<Me>("/me"));
              });
            }}
          >
            <label>
              Email
              <input
                name="email"
                type="email"
                autoComplete="username"
                required
              />
            </label>
            <label>
              Password
              <input
                name="password"
                type="password"
                autoComplete="current-password"
                required
              />
            </label>
            <button disabled={busy}>Sign in</button>
          </form>
          {error && (
            <p className="error" role="alert">
              {error}
            </p>
          )}
          <small>Two individual logins. One shared household budget.</small>
        </div>
      </main>
    );
  return (
    <div className="shell">
      <aside>
        <a className="wordmark brand" href="/" aria-label="PocketWatcher home">
          <img className="brand-mark" src="/brand/pocketwatcher-mark.png" alt="" width="52" height="52" />
          <span>PocketWatcher</span>
        </a>
        <span className="household">{me.household}</span>
        <nav>
          {["Overview", "Transactions", "Import", "Plan", "Settings"].map(
            (t) => (
              <button
                key={t}
                className={tab === t ? "active" : ""}
                onClick={() => {
                  if (t !== tab && !leavePlan()) return;
                  setTab(t);
                  setNotice("");
                }}
              >
                {t}
              </button>
            ),
          )}
        </nav>
        <div className="aside-bottom">
          <span>{me.members.join(" + ")}</span>
          <small>Built for your life together.</small>
          <button
            className="quiet"
            onClick={() =>
              void run(async () => {
                await api("/auth/logout", "POST");
                csrf = "";
                setMe(null);
              })
            }
          >
            Sign out
          </button>
        </div>
      </aside>
      <main>
        <header>
          <div>
            <span className="eyebrow">YOUR SHARED FINANCES</span>
            <h1>{tab === "Overview" ? `A clear view, ${me.name}.` : tab}</h1>
          </div>
          <div className="month-control">
            <button type="button" className="secondary" aria-label="Previous month" disabled={busy || planSaving || month === "2000-01"} onClick={() => changeMonth(shiftMonth(month, -1))}>‹</button>
            <label className="month">Budget month<span className="month-field"><span className="month-display" aria-hidden="true">{displayMonth(month)}</span><input aria-label="Budget month" type="month" min="2000-01" max="2100-12" value={month} disabled={busy || planSaving} onChange={e => {if (/^\d{4}-\d{2}$/.test(e.target.value) && !changeMonth(e.target.value)) e.currentTarget.value = month;}} onBlur={e => {e.currentTarget.value = month;}} onClick={e => {try {e.currentTarget.showPicker?.();} catch { /* Native interaction remains available. */ }}} /></span></label>
            <button type="button" className="secondary" aria-label="Next month" disabled={busy || planSaving || month === "2100-12"} onClick={() => changeMonth(shiftMonth(month, 1))}>›</button>
          </div>
          <button
            className="mobile-logout quiet"
            onClick={() =>
              void run(async () => {
                await api("/auth/logout", "POST");
                csrf = "";
                setMe(null);
              })
            }
          >
            Sign out
          </button>
        </header>
        {error && (
          <div className="error" role="alert">
            {error}
          </div>
        )}
        {notice && (
          <div className="success save-confirmation" role="status" aria-live="polite">
            <span>✓ {notice}</span>
            <button type="button" className="quiet" aria-label="Dismiss confirmation" onClick={() => setNotice("")}>✕</button>
          </div>
        )}
        {busy && (
          <div className="loading" role="status">
            Updating…
          </div>
        )}
        {tab === "Overview" && dashboard && (
          <>
            <div className="hero">
              <div>
                <span className="eyebrow">LEFT IN YOUR SPENDING BUDGET</span>
                <h2>{money(dashboard.remaining_cents)}</h2>
                <p>Your spending limit minus spending so far · {displayMonth(month)}</p>
                <p className="hero-explanation">This is a budget estimate, not your bank balance. Savings plans are separate.</p>
              </div>
              <div className="hero-note">
                A plan for the everyday.
                <br />
                Space for the someday.
              </div>
            </div>
            <div className="stats">
              <Stat
                label="Spent this month"
                description="Categorized purchases and loan payments, minus refunds and reimbursements. Unreviewed transactions are excluded."
                value={money(dashboard.spent_cents)}
              />
              <Stat
                label="Spending limit this month"
                description="Your category budgets, plus unused money or overspending carried forward."
                value={money(dashboard.budget_cents)}
              />
              <Stat
                label="Monthly savings target"
                description="What you intend to save. This does not confirm that money was transferred."
                value={money(dashboard.planned_savings_cents)}
              />
            </div>
            {dashboard.review_count > 0 && (
              <button
                className="review-banner"
                onClick={() => {
                  setSearch("");
                  setCategory("");
                  setAccount("");
                  setOffset(0);
                  setKind("review");
                  setTab("Transactions");
                }}
              >
                {dashboard.review_count} transactions need review. Totals are
                incomplete until classified. <span>Review →</span>
              </button>
            )}
            <section className="panel attention" aria-label="Budget check-in">
              <h2>Your quick check-in</h2>
              <p>{dashboard.review_count > 0
                ? `${dashboard.review_count} transactions need review before these totals are complete.`
                : "All imported transactions are reviewed."}</p>
              <p>{dashboard.categories.filter(c => c.configured && c.remaining_cents < 0).length
                ? `${dashboard.categories.filter(c => c.configured && c.remaining_cents < 0).length} categories over budget. Tap a category below to see why.`
                : "No configured categories are over budget."}</p>
              {dashboard.categories.some(c => !c.configured && c.spent_cents !== 0) &&
                <p>Some spending has no category budget. Set a plan to include it in your comparison.</p>}
              <small>Remaining budget is a spending-plan comparison, not your bank balance or cash available.</small>
            </section>
            <div className="columns">
              <section className="panel">
                <div className="section-title">
                  <h2>Where it’s going</h2>
                  <button className="quiet" onClick={() => setTab("Plan")}>
                    Edit plan →
                  </button>
                </div>
                {dashboard.categories.length === 0 && (
                  <p>Add categories in Settings to begin.</p>
                )}
                {dashboard.categories.map((c) => (
                  <button className="category-row category-link" key={c.id}
                    aria-label={`View ${c.name} transactions`}
                    onClick={() => {
                      setCategory(String(c.id)); setSearch(""); setKind("");
                      setAccount(""); setOffset(0); setSort("newest");
                      setCreditsFirst(false); setTab("Transactions");
                    }}>
                    <div>
                      <strong>{c.name}</strong>
                      <small>
                        {c.mode}
                        {!c.configured ? " · No budget set" : ""}
                      </small>
                    </div>
                    <div>
                      <strong>{money(c.spent_cents)}</strong>
                      <small>
                        of {money(c.budget_cents + c.rollover_cents)}
                      </small>
                    </div>
                    <div className="track">
                      <i
                        className={c.remaining_cents < 0 ? "over" : ""}
                        style={{
                          width: `${Math.min(100, Math.max(0, (c.spent_cents / Math.max(1, c.budget_cents + c.rollover_cents)) * 100))}%`,
                        }}
                      />
                    </div>
                  </button>
                ))}
              </section>
              <section className="panel">
                <span className="eyebrow">LOOKING AHEAD</span>
                <h2>Make room for your goals</h2>
                <p>Monthly earmarks for the things you’re building together.</p>
                {dashboard.savings.map((s) => (
                  <div className="goal" key={s.name}>
                    <span>{s.name}</span>
                    <strong>{money(s.cents)}</strong>
                  </div>
                ))}
                {!dashboard.savings.length && (
                  <p className="empty">
                    Emergency fund, travel, a future home. Add your first
                    allocation in Plan.
                  </p>
                )}
                <button className="secondary" onClick={() => setTab("Plan")}>
                  Plan savings
                </button>
                <hr />
                <small>Allocations are plans only. No money is moved.</small>
                <div className="goal">
                  <span>Income</span>
                  <strong>{money(dashboard.income_cents)}</strong>
                </div>
                <div className="goal">
                  <span>Household contributions</span>
                  <strong>{money(dashboard.contribution_cents)}</strong>
                </div>
              </section>
            </div>
          </>
        )}
        {tab === "Transactions" && (
          <section className="panel activity-panel">
            <div className="section-title">
              <h2>Your shared activity</h2>
              <span className="muted">{total} transactions</span>
            </div>
            <div className="filters">
              <input
                aria-label="Search merchants"
                placeholder="Search merchants…"
                value={search}
                onChange={(e) => {
                  setSearch(e.target.value);
                  setOffset(0);
                }}
              />
              <select
                aria-label="Filter by type"
                value={kind}
                onChange={(e) => {
                  setKind(e.target.value);
                  setOffset(0);
                }}
              >
                <option value="">All types</option>
                {kinds.map((k) => (
                  <option key={k} value={k}>
                    {labels[k]}
                  </option>
                ))}
              </select>
              <select
                aria-label="Filter by account"
                value={account}
                onChange={(e) => {
                  setAccount(e.target.value);
                  setOffset(0);
                }}
              >
                <option value="">All accounts</option>
                {accounts.map((a) => (
                  <option key={a.id} value={a.id} disabled={a.archived}>
                    {a.name}
                  </option>
                ))}
              </select>
              <select
                aria-label="Filter by category"
                value={category}
                onChange={(e) => {
                  setCategory(e.target.value);
                  setOffset(0);
                }}
              >
                <option value="">All categories</option>
                {categories.map((c) => (
                  <option key={c.id} value={c.id} disabled={c.archived}>
                    {c.name}
                  </option>
                ))}
              </select>
            </div>
            <div className="transaction-tools">
              <label>Sort transactions
                <select aria-label="Sort transactions" value={sort} onChange={e => { setSort(e.target.value); setOffset(0); }}>
                  <option value="newest">Date: newest first</option>
                  <option value="oldest">Date: oldest first</option>
                  <option value="largest">Amount: highest first</option>
                  <option value="smallest">Amount: lowest first</option>
                </select>
              </label>
              <label className="check"><input type="checkbox" checked={creditsFirst}
                onChange={e => { setCreditsFirst(e.target.checked); setOffset(0); }} />Refunds & reimbursements first</label>
              <button className="quiet" onClick={() => { setSearch(""); setKind(""); setAccount(""); setCategory(""); setSort("newest"); setCreditsFirst(false); setOffset(0); }}>Clear filters</button>
            </div>
            {category && <p className="filter-summary">Showing transactions containing {categories.find(c => String(c.id) === category)?.name}. Amounts show the full transaction; category splits appear beneath the merchant.</p>}
            {selected.length > 0 && (
              <div className="bulk">
                <strong>{selected.length} selected</strong>
                <KindSelect value={bulkKind} onChange={setBulkKind} />
                {spending(bulkKind) && (
                  <select
                    aria-label="Bulk category"
                    value={bulkCategory}
                    onChange={(e) => setBulkCategory(e.target.value)}
                  >
                    <option value="">Choose category</option>
                    {categories.map((c) => (
                      <option key={c.id} value={c.id} disabled={c.archived}>
                        {c.name}
                      </option>
                    ))}
                  </select>
                )}
                <button
                  disabled={busy || (spending(bulkKind) && !bulkCategory)}
                  onClick={() =>
                    void run(async () => {
                      await api("/transactions/bulk", "POST", {
                        transactions: Object.fromEntries(
                          txs
                            .filter((t) => selected.includes(t.id))
                            .map((t) => [t.id, t.version]),
                        ),
                        kind: bulkKind,
                        category_id: spending(bulkKind)
                          ? Number(bulkCategory)
                          : null,
                      });
                      await refresh();
                      setNotice("Selected transactions updated.");
                    })
                  }
                >
                  Apply to selected
                </button>
              </div>
            )}
            <div className="table-scroll transaction-table">
              <table>
                <thead>
                  <tr>
                    <th>
                      <input
                        aria-label="Select all on page"
                        type="checkbox"
                        checked={
                          txs.length > 0 && selected.length === txs.length
                        }
                        onChange={(e) =>
                          setSelected(
                            e.target.checked ? txs.map((t) => t.id) : [],
                          )
                        }
                      />
                    </th>
                    <th>Date / account</th>
                    <th>Merchant</th>
                    <th>Classification</th>
                    <th>Amount</th>
                    <th />
                  </tr>
                </thead>
                <tbody>
                  {txs.map((t) => (
                    <tr key={t.id}>
                      <td>
                        <input
                          aria-label={`Select ${t.merchant}`}
                          type="checkbox"
                          checked={selected.includes(t.id)}
                          onChange={(e) =>
                            setSelected(
                              e.target.checked
                                ? [...selected, t.id]
                                : selected.filter((i) => i !== t.id),
                            )
                          }
                        />
                      </td>
                      <td>
                        {displayDate(t.date)}
                        <small>
                          {accounts.find((a) => a.id === t.account_id)?.name}
                        </small>
                      </td>
                      <td>
                        <strong>{t.merchant}</strong>
                        <small>
                          {t.splits
                            .map(
                              (s) =>
                                categories.find((c) => c.id === s.category_id)
                                  ?.name,
                            )
                            .join(" + ")}
                        </small>
                      </td>
                      <td>
                        <span
                          className={
                            "badge " + (t.kind === "review" ? "warning" : "")
                          }
                        >
                          {labels[t.kind]}
                        </span>
                      </td>
                      <td className="amount">
                        {money(t.cents)}
                        <small>{t.cents < 0 ? "Money in" : "Money out"}</small>
                      </td>
                      <td>
                        <button className="quiet" onClick={() => setEditing(t)}>
                          Edit
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <div className="transaction-cards">
              {txs.length > 0 && <label className="check select-page"><input type="checkbox" aria-label="Select all mobile transactions" checked={selected.length === txs.length} onChange={e => setSelected(e.target.checked ? txs.map(t => t.id) : [])} />Select all on page</label>}
              {txs.map(t => <article className="transaction-card" key={t.id} aria-label={`${t.merchant}, ${displayDate(t.date)}`}>
                <div className="transaction-card-top">
                  <input type="checkbox" aria-label={`Select ${t.merchant}`} checked={selected.includes(t.id)} onChange={e => setSelected(ids => e.target.checked ? [...ids, t.id] : ids.filter(id => id !== t.id))} />
                  <div className="transaction-merchant"><strong>{t.merchant}</strong><small>{displayDate(t.date)}</small></div>
                  <div className="transaction-amount"><strong>{money(t.cents)}</strong><small>{t.cents < 0 ? "Money in" : "Money out"}</small></div>
                </div>
                <small className="transaction-account">{accounts.find(a => a.id === t.account_id)?.name}</small>
                {t.splits.length > 0 && <p className="transaction-splits">{t.splits.map(s => `${categories.find(c => c.id === s.category_id)?.name}: ${money(s.cents)}`).join(" · ")}</p>}
                <div className="transaction-card-bottom"><span className={`badge ${t.kind === "review" ? "warning" : ""}`}>{labels[t.kind]}</span><button type="button" className="secondary" onClick={() => setEditing(t)}>Edit</button></div>
              </article>)}
            </div>
            {!txs.length && (
              <div className="empty">
                No transactions match. Import a CSV or adjust your filters.
              </div>
            )}
            <div className="pagination">
              <button
                className="secondary"
                disabled={offset === 0 || busy}
                onClick={() => setOffset(Math.max(0, offset - 50))}
              >
                Previous
              </button>
              <span>
                {total ? offset + 1 : 0}–{Math.min(offset + 50, total)} of{" "}
                {total}
              </span>
              <button
                className="secondary"
                disabled={offset + 50 >= total || busy}
                onClick={() => setOffset(offset + 50)}
              >
                Next
              </button>
            </div>
            <small>
              Positive amounts are outflows; negative amounts are inflows.
              Transfers and card payments do not count as spending.
            </small>
          </section>
        )}
        {tab === "Import" && (
          <>
            <section className="panel">
              <h2>Bring in your shared activity</h2>
              <p>
                Upload posted transactions from a joint account or shared credit
                card. Preview, reconcile, then import. All new transactions need
                classification.
              </p>
              <div className="form-grid">
                <label>
                  Shared account
                  <select
                    value={importAccount}
                    onChange={(e) => {
                      setImportAccount(e.target.value);
                      setPreview(null);
                    }}
                  >
                    <option value="">Choose account</option>
                    {accounts.map((a) => (
                      <option key={a.id} value={a.id} disabled={a.archived}>
                        {a.name}
                      </option>
                    ))}
                  </select>
                </label>
                <label>
                  CSV format
                  <select
                    value={format}
                    onChange={(e) => {
                      setFormat(e.target.value);
                      setPreview(null);
                    }}
                  >
                    <option value="canonical">Standard CSV</option>
                    <option value="chase">Chase (negative purchases)</option>
                    <option value="capital_one">
                      Capital One (Debit / Credit)
                    </option>
                  </select>
                </label>
                {format === "canonical" && (
                  <label className="check">
                    <input
                      type="checkbox"
                      checked={positive}
                      onChange={(e) => {
                        setPositive(e.target.checked);
                        setPreview(null);
                      }}
                    />
                    My CSV uses positive amounts for money out
                  </label>
                )}
                <label>
                  CSV file
                  <input
                    type="file"
                    accept=".csv,text/csv"
                    onChange={(e) => {
                      const f = e.target.files?.[0];
                      if (!f) return;
                      if (f.size > 2000000) {
                        setError("CSV limit is 2 MB.");
                        return;
                      }
                      void f.text().then((t) => {
                        setCsv(t);
                        setPreview(null);
                      });
                    }}
                  />
                </label>
              </div>
              <p className="hint">
                Standard headers: <code>date,merchant,amount,external_id</code>{" "}
                (external_id optional). Dates: YYYY-MM-DD or MM/DD/YYYY. USD
                only, up to 5,000 rows. Use stable IDs when available; use
                overlapping full-day exports when IDs are unavailable.
              </p>
              <button
                disabled={busy || !csv || !importAccount}
                onClick={() =>
                  void run(async () => {
                    setPreview(
                      await api<Preview>("/imports/preview", "POST", {
                        account_id: Number(importAccount),
                        csv,
                        format,
                        outflows_positive: positive,
                      }),
                    );
                    setReconcile("");
                  })
                }
              >
                Preview import
              </button>
            </section>
            {preview && (
              <section className="panel">
                <h2>Review before importing</h2>
                <div className="stats">
                  <Stat
                    label="Rows in file"
                    value={String(preview.rows.length)}
                  />
                  <Stat
                    label="Duplicates skipped"
                    value={String(preview.duplicates)}
                  />
                  <Stat
                    label="New net outflow"
                    value={money(preview.new_net_cents)}
                  />
                </div>
                <div className="table-scroll preview-table">
                  <table>
                    <thead>
                      <tr>
                        <th>Date</th>
                        <th>Merchant</th>
                        <th>Amount</th>
                        <th>Status</th>
                      </tr>
                    </thead>
                    <tbody>
                      {preview.rows.slice(0, 100).map((r, i) => (
                        <tr key={i}>
                          <td>{displayDate(r.date)}</td>
                          <td>{r.merchant}</td>
                          <td>{money(r.cents)}</td>
                          <td>
                            {r.duplicate
                              ? "Already imported"
                              : "New · needs review"}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
                <p>
                  Showing the first {Math.min(100, preview.rows.length)} rows.
                  Verify the file’s signed net total:{" "}
                  <strong>{money(preview.net_cents)}</strong>. Negative means
                  net money in.
                </p>
                <label>
                  Enter the net total from your export ($)
                  <input
                    inputMode="decimal"
                    value={reconcile}
                    onChange={(e) => setReconcile(e.target.value)}
                    placeholder="0.00"
                  />
                </label>
                <button
                  disabled={busy || !reconcile}
                  onClick={() =>
                    void run(async () => {
                      const r = await api<{
                        imported: number;
                        duplicates: number;
                      }>(`/imports/${preview.id}/commit`, "POST", {
                        expected_net_cents: cents(reconcile),
                      });
                      setPreview(null);
                      setCsv("");
                      await refresh();
                      setNotice(
                        `Imported ${r.imported} transactions; skipped ${r.duplicates} duplicates. Classify them in Transactions.`,
                      );
                    })
                  }
                >
                  Confirm import
                </button>
              </section>
            )}
            <section className="panel">
              <h2>Recent imports</h2>
              {history.map((h) => (
                <div className="goal" key={h.id}>
                  <span>
                    #{h.id} ·{" "}
                    {accounts.find((a) => a.id === h.account_id)?.name}
                    <small>
                      {new Date(h.created * 1000).toLocaleString("en-US", {timeZone: "America/New_York", month: "short", day: "numeric", year: "numeric", hour: "numeric", minute: "2-digit"})} · {h.status}
                    </small>
                  </span>
                  <span>
                    {h.imported} added · {h.duplicates} skipped
                  </span>
                </div>
              ))}
              {!history.length && <p>No imports yet.</p>}
            </section>
          </>
        )}
        {tab === "Plan" && dashboard && (
          <Plan key={month} onEditingChange={setPlanEditing} month={month} dashboard={dashboard} busy={busy}
            onSave={async (payload) => {
              setPlanSaving(true);
              try {
                await api(`/plan/${month}`, "PUT", payload);
                await load();
                setNotice("Plan saved. Changes repeat in following months.");
              } finally {setPlanSaving(false);}
            }} />
        )}
        {tab === "Settings" && (
          <>
            <BankConnections onRefresh={refresh} />
            <section className="panel">
              <h2>Shared accounts</h2>
              <p>
                Add only accounts whose transactions belong in your household
                budget. Personal spending stays outside this app.
              </p>
              {accounts.map(a => <SettingRow key={`${a.id}-${a.name}-${a.kind}-${a.archived}`} name={a.name} value={a.kind} archived={!!a.archived} kind="accounts" busy={busy}
                onSave={(name, value) => void run(async () => {await api(`/accounts/${a.id}`, "PUT", {name, kind: value}); await refresh(); setNotice("Account updated.");})}
                onArchive={action => void run(async () => {await api(`/settings/accounts/${a.id}/${action}`, "POST"); await refresh(); setNotice(action === "archive" ? "Account archived. Transaction history kept." : "Account restored.");})} />)}
              <form
                className="inline-form"
                onSubmit={(e) => {
                  e.preventDefault();
                  const form = e.currentTarget,
                    f = new FormData(form);
                  void run(async () => {
                    await api("/accounts", "POST", {
                      name: f.get("name"),
                      kind: f.get("kind"),
                    });
                    form.reset();
                    await load();
                    setNotice("Shared account added.");
                  });
                }}
              >
                <label>
                  Account name
                  <input
                    name="name"
                    required
                    maxLength={100}
                    placeholder="Joint checking"
                  />
                </label>
                <label>
                  Type
                  <select name="kind">
                    <option value="checking">Checking</option>
                    <option value="credit">Credit card</option>
                    <option value="savings">Savings</option>
                  </select>
                </label>
                <button disabled={busy}>Add account</button>
              </form>
            </section>
            <section className="panel">
              <h2>Your categories</h2>
              {categories.map(c => <SettingRow key={`${c.id}-${c.name}-${c.mode}-${c.archived}`} name={c.name} value={c.mode} archived={!!c.archived} kind="categories" busy={busy}
                onSave={(name, value) => void run(async () => {await api(`/categories/${c.id}`, "PUT", {name, mode: value}); await refresh(); setNotice("Category updated.");})}
                onArchive={action => void run(async () => {await api(`/settings/categories/${c.id}/${action}`, "POST"); await refresh(); setNotice(action === "archive" ? "Category archived. History kept; budget stopped from this month." : "Category restored. Set its budget in Plan.");})} />)}
              <form
                className="inline-form"
                onSubmit={(e) => {
                  e.preventDefault();
                  const form = e.currentTarget,
                    f = new FormData(form);
                  void run(async () => {
                    await api("/categories", "POST", {
                      name: f.get("name"),
                      mode: f.get("mode"),
                    });
                    form.reset();
                    await load();
                    setNotice("Category added.");
                  });
                }}
              >
                <label>
                  Category name
                  <input name="name" required maxLength={100} />
                </label>
                <label>
                  Spending style
                  <select name="mode">
                    <option value="flexible">Flexible</option>
                    <option value="fixed">Fixed</option>
                  </select>
                </label>
                <button disabled={busy}>Add category</button>
              </form>
            </section>
            <section className="panel">
              <h2>Household access</h2>
              <p>
                {me.members.join(" and ")} share this budget with separate
                logins. Password recovery is handled through the administrative
                reset command; there is no public signup.
              </p>
            </section>
          </>
        )}
        <footer>
          PocketWatcher · Shared spending, considered together.{" "}
          <button
            className="quiet"
            disabled={busy}
            onClick={() => void run(refresh)}
          >
            Refresh data
          </button>
        </footer>
      </main>
      {editing && (
        <EditDialog
          tx={editing}
          categories={categories}
          busy={busy}
          serverError={error}
          onClose={() => setEditing(null)}
          onSave={(kind, splits) =>
            void run(async () => {
              await api(`/transactions/${editing.id}`, "PUT", {
                version: editing.version,
                kind,
                splits,
              });
              setEditing(null);
              await refresh();
              setNotice("Transaction updated.");
            })
          }
        />
      )}
    </div>
  );
}
function Stat({ label, value, description }: { label: string; value: string; description?: string }) {
  return (
    <div className="stat">
      <span>{label}</span>
      <strong>{value}</strong>
      {description && <small>{description}</small>}
    </div>
  );
}
type PlanPayload = {
  budgets: {category_id: number; cents: number; rollover: boolean}[];
  savings: {id?: number; name: string; cents: number}[];
  removed_savings: number[];
};
function Plan({month, dashboard, busy, onSave, onEditingChange}: {
  onEditingChange: (editing: boolean) => void;
  month: string; dashboard: Dashboard; busy: boolean;
  onSave: (payload: PlanPayload) => Promise<void>;
}) {
  const [editing, updateEditing] = useState(false), [saving, setSaving] = useState(false),
    [error, setError] = useState("");
  const [budgets, setBudgets] = useState<{id: number; amount: string; rollover: boolean}[]>([]);
  const [goals, setGoals] = useState<{id?: number; name: string; amount: string}[]>([]);
  function start() {
    setBudgets(dashboard.categories.map(c => ({id: c.id, amount: (c.budget_cents / 100).toFixed(2), rollover: c.rollover})));
    setGoals(dashboard.savings.map(s => ({id: s.id, name: s.name, amount: (s.cents / 100).toFixed(2)})));
    setError(""); setEditing(true);
  }
  function setEditing(value: boolean) {updateEditing(value); onEditingChange(value);}
  // Protect a draft if the user changes month, tab, or refreshes the page.
  useEffect(() => {
    if (!editing) return;
    const handler = (e: BeforeUnloadEvent) => {e.preventDefault(); e.returnValue = "";};
    window.addEventListener("beforeunload", handler);
    return () => window.removeEventListener("beforeunload", handler);
  }, [editing]);
  return <form className="plan" onSubmit={async e => {
    e.preventDefault(); if (saving) return; setError("");
    try {
      const parsedBudgets = budgets.map(b => ({category_id: b.id, cents: cents(b.amount), rollover: b.rollover}));
      const parsedGoals = goals.map(g => ({...(g.id ? {id: g.id} : {}), name: g.name.trim(), cents: cents(g.amount)}));
      if (parsedBudgets.some(b => b.cents < 0) || parsedGoals.some(g => !g.name || g.cents <= 0))
        throw Error("Use nonnegative budgets and a name and positive amount for each savings plan.");
      const names = parsedGoals.map(g => g.name);
      if (new Set(names).size !== names.length) throw Error("Give each savings plan a different name.");
      setSaving(true);
      await onSave({
        budgets: parsedBudgets.filter(b => {const c = dashboard.categories.find(c => c.id === b.category_id)!; return b.cents !== c.budget_cents || b.rollover !== c.rollover;}),
        savings: parsedGoals.filter(g => {const old = dashboard.savings.find(s => s.id === g.id); return !old || old.name !== g.name || old.cents !== g.cents;}),
        removed_savings: dashboard.savings.filter(s => !goals.some(g => g.id === s.id)).map(s => s.id),
      });
      setEditing(false);
    } catch (err) { setError((err as Error).message); }
    finally {setSaving(false);}
  }}>
    <section className="panel">
      <div className="section-title">
        <div><h2>Your monthly plan</h2><p>Amounts repeat each month until you change them. Changes start in {displayMonth(month)}.</p></div>
        {!editing && <button type="button" disabled={busy} onClick={start}>Edit plan</button>}
      </div>
      <fieldset disabled={saving || busy}>
        {dashboard.categories.filter(c => !c.archived).map(c => {
          const draft = budgets.find(b => b.id === c.id);
          return <div className="budget-row" key={c.id}>
            <div><strong>{c.name}</strong><small>{money(c.spent_cents)} spent · {money(c.rollover_cents)} carried{c.inherited_from ? ` · Repeating from ${displayMonth(c.inherited_from)}` : ""}</small></div>
            {editing && draft ? <>
              <label>Budget ($)<input aria-label={`${c.name} budget`} inputMode="decimal" required value={draft.amount} onChange={e => setBudgets(bs => bs.map(b => b.id === c.id ? {...b, amount: e.target.value} : b))} /></label>
              <label className="check"><input aria-label={`${c.name} rollover`} type="checkbox" checked={draft.rollover} onChange={e => setBudgets(bs => bs.map(b => b.id === c.id ? {...b, rollover: e.target.checked} : b))} />Rollover</label>
            </> : <div className="plan-amount"><strong>{money(c.budget_cents)}</strong><small>{c.rollover ? "Rollover on" : "Rollover off"}</small></div>}
          </div>;
        })}
      </fieldset>
    </section>
    <section className="panel">
      <h2>Monthly savings plans</h2>
      <p>Your monthly savings targets. These do not move money or track bank bucket balances.</p>
      <fieldset disabled={saving || busy}>
        {editing ? <>
          {goals.map((g, i) => <div className="inline-form" role="group" aria-label={`Savings goal ${i + 1}`} key={g.id ?? `new-${i}`}>
            <label>Goal name<input aria-label={`Goal ${i + 1} name`} required maxLength={100} value={g.name} onChange={e => setGoals(gs => gs.map((v,j) => j === i ? {...v, name: e.target.value} : v))} /></label>
            <label>Monthly allocation ($)<input aria-label={`Goal ${i + 1} allocation`} required inputMode="decimal" value={g.amount} onChange={e => setGoals(gs => gs.map((v,j) => j === i ? {...v, amount: e.target.value} : v))} /></label>
            <button type="button" className="quiet" onClick={() => setGoals(gs => gs.filter((_,j) => j !== i))}>Remove goal {i + 1}</button>
          </div>)}
          <button type="button" className="secondary" onClick={() => setGoals(gs => [...gs, {name: "", amount: ""}])}>Add savings goal</button>
        </> : <>
          {dashboard.savings.map(s => <div className="goal" key={s.id}><span><strong>{s.name}</strong>{s.inherited_from && <small>Repeating from {displayMonth(s.inherited_from)}</small>}</span><strong>{money(s.cents)} / month</strong></div>)}
          {!dashboard.savings.length && <p>No savings goals yet. Edit your plan to add one.</p>}
        </>}
      </fieldset>
    </section>
    {editing && <div className="plan-actions">
      {error && <p role="alert">{error}</p>}
      <p>Saving applies to this month onward. Removing a goal stops it from this month.</p>
      <div><button disabled={saving || busy}>{saving ? "Saving…" : "Save changes"}</button><button type="button" className="secondary" disabled={saving} onClick={() => {setEditing(false); setError("");}}>Cancel</button></div>
    </div>}
  </form>;
}
function SettingRow({name, value, archived, kind, busy, onSave, onArchive}: {
 name: string; value: string; archived: boolean; kind: "accounts" | "categories"; busy: boolean;
 onSave: (name: string, value: string) => void; onArchive: (action: "archive" | "restore") => void;
}) {
 const [editing, setEditing] = useState(false), [draft, setDraft] = useState(name), [choice, setChoice] = useState(value);
 if (archived) return <details className="setting-row"><summary>Archived: {name}</summary><button type="button" className="secondary" disabled={busy} onClick={() => onArchive("restore")}>Restore {name}</button></details>;
 return <div className="setting-row" role="group" aria-label={`${kind === "accounts" ? "Account" : "Category"}: ${name}`}>
 {editing ? <form className="inline-form" onSubmit={e => {e.preventDefault(); onSave(draft, choice);}}>
 <label>Name<input aria-label={`Edit ${name} name`} required maxLength={100} value={draft} onChange={e => setDraft(e.target.value)} /></label>
 <label>{kind === "accounts" ? "Type" : "Spending style"}<select aria-label={`Edit ${name} type`} value={choice} onChange={e => setChoice(e.target.value)}>
 {(kind === "accounts" ? ["checking", "credit", "savings"] : ["fixed", "flexible"]).map(v => <option value={v} key={v}>{v === "credit" ? "Credit card" : v}</option>)}
 </select></label><button disabled={busy}>Save changes</button><button type="button" className="secondary" disabled={busy} onClick={() => {setDraft(name); setChoice(value); setEditing(false);}}>Cancel</button>
 </form> : <><div><strong>{name}</strong><small>{value}</small></div><div className="setting-actions"><button type="button" className="secondary" disabled={busy} onClick={() => setEditing(true)}>Edit</button><button type="button" className="quiet" disabled={busy} onClick={() => {if(window.confirm(`Archive ${name}? Transaction history stays. ${kind === "categories" ? "Its budget stops from this month onward." : "New imports should use active accounts."}`)) onArchive("archive");}}>Archive</button></div></>}
 </div>;
}
function EditDialog({
  tx,
  categories,
  busy,
  serverError,
  onClose,
  onSave,
}: {
  tx: Tx;
  categories: Category[];
  busy: boolean;
  serverError: string;
  onClose: () => void;
  onSave: (kind: string, splits: Allocation[]) => void;
}) {
  const [kind, setKind] = useState(tx.kind),
    [error, setError] = useState(""),
    [rows, setRows] = useState(
      tx.splits.length
        ? tx.splits.map((s) => ({
            category: String(s.category_id),
            amount: (s.cents / 100).toFixed(2),
          }))
        : [
            {
              category: String(categories[0]?.id || ""),
              amount: (tx.cents / 100).toFixed(2),
            },
          ],
    );
  useEffect(() => {
    const prior = document.activeElement as HTMLElement;
    const dialog = document.querySelector("dialog");
    dialog?.showModal();
    return () => {
      dialog?.close();
      prior?.focus();
    };
  }, []);
  return (
    <dialog
      onCancel={(e) => {
        e.preventDefault();
        if (!busy) onClose();
      }}
    >
      <form
        onSubmit={(e) => {
          e.preventDefault();
          try {
            const splits = spending(kind)
              ? rows.map((r) => ({
                  category_id: Number(r.category),
                  cents: cents(r.amount),
                }))
              : [];
            if (
              spending(kind) &&
              splits.reduce((n, s) => n + s.cents, 0) !== tx.cents
            )
              throw Error("Splits must total " + money(tx.cents));
            setError("");
            onSave(kind, splits);
          } catch (e) {
            setError((e as Error).message);
          }
        }}
      >
        <div className="section-title">
          <h2>Edit transaction</h2>
          <button
            type="button"
            className="quiet"
            onClick={onClose}
            disabled={busy}
            aria-label="Close editor"
          >
            ✕
          </button>
        </div>
        <strong>
          {tx.merchant} · {money(tx.cents)}
        </strong>
        <p>{displayDate(tx.date)} · Positive is money out; negative is money in.</p>
        <label>
          Classification
          <KindSelect value={kind} onChange={setKind} />
        </label>
        {spending(kind) && (
          <>
            <h3>Category allocations</h3>
            {rows.map((r, i) => (
              <div className="split-row" key={i}>
                <select
                  aria-label={`Split ${i + 1} category`}
                  required
                  value={r.category}
                  onChange={(e) =>
                    setRows(
                      rows.map((v, j) =>
                        j === i ? { ...v, category: e.target.value } : v,
                      ),
                    )
                  }
                >
                  <option value="">Category</option>
                  {categories.map((c) => (
                    <option key={c.id} value={c.id} disabled={c.archived}>
                      {c.name}
                    </option>
                  ))}
                </select>
                <input
                  aria-label={`Split ${i + 1} dollars`}
                  inputMode="decimal"
                  value={r.amount}
                  onChange={(e) =>
                    setRows(
                      rows.map((v, j) =>
                        j === i ? { ...v, amount: e.target.value } : v,
                      ),
                    )
                  }
                />
                <button
                  className="quiet"
                  type="button"
                  aria-label={`Remove split ${i + 1}`}
                  onClick={() => setRows(rows.filter((_, j) => j !== i))}
                >
                  ✕
                </button>
              </div>
            ))}
            <button
              type="button"
              className="secondary"
              disabled={rows.length >= 30}
              onClick={() =>
                setRows([...rows, { category: "", amount: "0.00" }])
              }
            >
              Add split
            </button>
          </>
        )}
        {(error || serverError) && (
          <p className="error" role="alert">
            {error || serverError}
          </p>
        )}
        <div className="dialog-actions">
          <button
            type="button"
            className="secondary"
            disabled={busy}
            onClick={onClose}
          >
            Cancel
          </button>
          <button disabled={busy}>Save transaction</button>
        </div>
      </form>
    </dialog>
  );
}

createRoot(document.getElementById("root")!).render(<App />);

if (import.meta.env.PROD && "serviceWorker" in navigator) {
  window.addEventListener("load", () => {
    void navigator.serviceWorker
      .register("/sw.js", { scope: "/", updateViaCache: "none" })
      .catch(() => {
        // Home-screen support is optional; network-only budgeting still works.
      });
  });
}

type BankConnection = {id: number; accounts: {id: string; name: string; mask: string | null; kind: string}[]; selected: string[]; start_date: string | null; last_sync: number | null};
function BankConnections({onRefresh}: {onRefresh: () => Promise<void>}) {
  const [state, setState] = useState<{configured: boolean; pending_link: number | null; pending_links?: number[]; items: BankConnection[]} | null>(null);
  const [busy, setBusy] = useState(false), [message, setMessage] = useState(""), [error, setError] = useState("");
  const [start, setStart] = useState("2026-11-01");
  const reload = async () => setState(await api("/banks"));
  useEffect(() => {
    let active = true;
    async function initialize() {
      const current = await api<{configured: boolean; pending_link: number | null; pending_links: number[]; items: BankConnection[]}>("/banks");
      if (!active) return;
      setState(current);
      if (current.pending_links?.length) {
        setBusy(true);
        try {
          const result = await api<{completed: number; pending: number; expired: number}>("/banks/recover", "POST");
          if (active) setMessage(result.completed ? "Bank connection recovered. Choose accounts below." : result.expired ? "An earlier bank authorization expired or was already used and has been closed. Saved connections remain below. If your bank is not listed, use Connect a bank once and return here immediately after authorizing." : "Your bank authorization has not been confirmed yet. Use Check pending connections; you do not need to start linking again.");
          if (active) {await reload(); await onRefresh();}
        } finally {if (active) setBusy(false);}
      }
    }
    initialize().catch(e => {if (active) setError(e.message);});
    return () => {active = false;};
  }, []);
  async function action(fn: () => Promise<void>) {
    setBusy(true); setError(""); setMessage("");
    try {await fn(); await reload(); await onRefresh();}
    catch (e) {setError((e as Error).message); await reload().catch(() => {});}
    finally {setBusy(false);}
  }
  return <section className="panel">
    <h2>Connect your banks</h2>
    <p>Live connection pilot · Only select accounts used for shared spending. You authorize access on Plaid’s secure site.</p>
    <p className="hint">Sync is manual during this first test to conserve your Plaid allowance. Only posted USD transactions on or after your start date are imported. They appear in Needs review; payments and transfers must be classified before using spending totals.</p>
    {error && <p className="error" role="alert">{error}</p>}
    {message && <p className="success" role="status">{message}</p>}
    {state && !state.configured && <p>Bank connection setup is incomplete.</p>}
    <label>Import transactions starting<input aria-label="Bank import start date" type="date" value={start} onChange={e => setStart(e.target.value)} disabled={busy} /></label>
    <p className="hint">Step 1: Authorize your bank. Step 2: Choose shared accounts. Step 3: Sync transactions. Existing connections are listed below.</p>
    <button type="button" disabled={busy || !state?.configured} onClick={() => void action(async () => {
      const result = await api<{url: string}>("/banks/link", "POST", {start_date: start});
      window.location.assign(result.url);
    })}>Connect a bank</button>
    {state?.pending_link && <button type="button" className="secondary" disabled={busy} onClick={() => void action(async () => {
      const result = await api<{completed: number; pending: number; expired: number}>("/banks/recover", "POST"); setMessage(result.completed ? "Connections saved. Choose shared accounts below." : result.expired ? "Old authorizations could not be reused and were closed. Saved connections remain below. If your bank is not listed, connect it once and return immediately after authorization." : "Plaid has not reported a completed authorization. Finish the bank authorization in Plaid and check again shortly.");
    })}>Check pending connections</button>}
    {state?.items.map(item => <div key={item.id} className="bank-connection">
      <h3>Bank connection {item.id}</h3>
      <button type="button" className="quiet" disabled={busy} onClick={() => {
        if (window.confirm("Disconnect this bank? Imported transactions stay in PocketWatcher. Reconnecting can require duplicate reconciliation.")) void action(async () => {await api(`/banks/${item.id}/disconnect`, "POST"); setMessage("Bank disconnected. Imported transactions were kept.");});
      }}>Disconnect bank</button>
      {!item.accounts.length && <button type="button" disabled={busy} onClick={() => void action(async () => {await api(`/banks/${item.id}/discover`, "POST");})}>Load available accounts</button>}
      {!item.selected.length ? <form onSubmit={e => {
        e.preventDefault(); const data = new FormData(e.currentTarget);
        void action(async () => {
          await api(`/banks/${item.id}/accounts`, "PUT", {account_ids: data.getAll("account"), start_date: data.get("start")});
          setMessage("Accounts selected. Tap Sync transactions to import them.");
        });
      }}><fieldset disabled={busy}>
        {item.accounts.map(a => <label className="check" key={a.id}><input type="checkbox" name="account" value={a.id} />{a.name} {a.mask ? `••${a.mask}` : ""} · {a.kind}</label>)}
        <label>Import from<input aria-label={`Import start date for connection ${item.id}`} type="date" name="start" defaultValue={item.start_date || "2026-11-01"} required /></label>
        <p className="hint">Choose a date in the past 90 days. This first selection is fixed for this connection. Previously imported CSVs for the same account need reconciliation to avoid duplicates.</p>
        <button disabled={!item.accounts.length}>Save selected accounts</button>
      </fieldset></form> : <>
        {item.accounts.filter(a => item.selected.includes(a.id)).map(a => <p key={a.id}>{a.name} {a.mask ? `••${a.mask}` : ""}</p>)}
        <p className="hint">Importing from {displayDate(item.start_date!)}. {item.last_sync ? `Last synced ${new Date(item.last_sync * 1000).toLocaleString("en-US")}` : "Not synced yet."}</p>
        <button disabled={busy} type="button" onClick={() => void action(async () => {
          const result = await api<{changed: number}>(`/banks/${item.id}/sync`, "POST");
          setMessage(result.changed ? `${result.changed} transaction changes synced. Review them in Transactions.` : "No new posted transactions yet. Initial bank data may still be loading; try again later.");
        })}>Sync transactions</button>
      </>}
    </div>)}
  </section>;
}
