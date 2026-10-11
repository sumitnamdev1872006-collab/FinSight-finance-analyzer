// FinSight — script.js

const fmt = n => "₹" + Number(n).toLocaleString("en-IN", {minimumFractionDigits:2});
const charts = {};

// ── Session ID — unique per browser tab, cleared on tab close ─────────────────
const SESSION_ID = (() => {
  let id = sessionStorage.getItem("finsight_session");
  if (!id) {
    id = crypto.randomUUID ? crypto.randomUUID() : Math.random().toString(36).slice(2) + Date.now();
    sessionStorage.setItem("finsight_session", id);
  }
  return id;
})();

function renderChart(id, cfg) {
  if (charts[id]) charts[id].destroy();
  const c = document.getElementById(id);
  if (c) charts[id] = new Chart(c, cfg);
}

// ── Navigation ────────────────────────────────────────────────────────────────
const TITLES = {dashboard:"Dashboard",transactions:"Transactions",upload:"Upload Data",analysis:"Analysis",insights:"Insights"};

function go(page) {
  document.querySelectorAll(".page").forEach(p => p.classList.remove("active"));
  document.querySelectorAll(".nav-link").forEach(l => l.classList.remove("active"));
  document.getElementById("page-" + page)?.classList.add("active");
  document.querySelector(`.nav-link[data-page="${page}"]`)?.classList.add("active");
  document.getElementById("page-title").textContent = TITLES[page] || page;
  if (page === "dashboard")    loadDashboard();
  if (page === "transactions") loadTransactions();
  if (page === "analysis")     loadAnalysis();
  if (page === "insights")     loadInsights();
}

document.querySelectorAll("[data-page]").forEach(el =>
  el.addEventListener("click", e => { e.preventDefault(); go(el.getAttribute("data-page")); })
);

// ── API ───────────────────────────────────────────────────────────────────────
async function api(path, opts = {}) {
  const headers = { "Content-Type": "application/json", "x-session-id": SESSION_ID, ...(opts.headers || {}) };
  const res = await fetch(path, { ...opts, headers });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(data.detail || res.statusText);
  return data;
}

// ── Dashboard ─────────────────────────────────────────────────────────────────
async function loadDashboard() {
  try {
    const d = await api("/api/dashboard");
    document.getElementById("s-income").textContent   = fmt(d.total_income);
    document.getElementById("s-expenses").textContent = fmt(d.total_expenses);
    document.getElementById("s-savings").textContent  = fmt(d.savings);
    document.getElementById("s-pct").textContent      = d.savings_pct.toFixed(1) + "%";

    // Bar chart — income vs expenses
    renderChart("ch-bar", {
      type: "bar",
      data: { labels: ["Income","Expenses"],
              datasets: [{ data: [d.total_income, d.total_expenses], backgroundColor: ["#22c55e","#ef4444"], borderRadius: 6 }] },
      options: { plugins:{legend:{display:false}}, scales:{y:{beginAtZero:true}} }
    });

    // Pie/doughnut — category
    const cats = Object.keys(d.category_totals || {});
    if (cats.length) {
      renderChart("ch-pie", {
        type: "doughnut",
        data: { labels: cats, datasets: [{ data: Object.values(d.category_totals),
          backgroundColor: ["#3b82f6","#f97316","#a855f7","#22c55e","#ef4444","#06b6d4","#f59e0b","#ec4899","#8b5cf6","#10b981","#6b7280"] }] },
        options: { plugins:{legend:{position:"right"}} }
      });
    }

    // Line — monthly expenses
    const mt = d.monthly_trend || {};
    if ((mt.months||[]).length) {
      renderChart("ch-line", {
        type: "line",
        data: { labels: mt.months, datasets: [{ label:"Expenses", data: mt.expenses, borderColor:"#ef4444", backgroundColor:"rgba(239,68,68,.08)", fill:true, tension:.3 }] },
        options: { scales:{y:{beginAtZero:true}} }
      });
      renderChart("ch-savings", {
        type: "line",
        data: { labels: mt.months, datasets: [{ label:"Savings", data: mt.savings, borderColor:"#22c55e", backgroundColor:"rgba(34,197,94,.08)", fill:true, tension:.3 }] },
        options: { scales:{y:{beginAtZero:true}} }
      });
    }

    // Recent table
    const wrap = document.getElementById("recent-wrap");
    wrap.innerHTML = (d.recent||[]).length ? buildTable(d.recent, false) : '<p class="empty">No transactions yet.</p>';
  } catch(e) { console.warn("Dashboard:", e.message); }
}

// ── Transactions ──────────────────────────────────────────────────────────────
let allTxns = [];

async function loadTransactions() {
  const search = document.getElementById("f-search")?.value || "";
  const type   = document.getElementById("f-filter-type")?.value || "";
  const cat    = document.getElementById("f-filter-cat")?.value || "";
  const qs     = new URLSearchParams({ search, type, category: cat }).toString();
  try {
    allTxns = await api("/api/transactions?" + qs);
    document.getElementById("txn-table-wrap").innerHTML =
      allTxns.length ? buildTable(allTxns, true) : '<p class="empty">No transactions found.</p>';
  } catch(e) { console.warn("Transactions:", e.message); }
}

function buildTable(rows, showDel) {
  let h = `<table class="tbl"><thead><tr><th>Date</th><th>Description</th><th>Amount</th><th>Type</th><th>Category</th>${showDel?"<th></th>":""}</tr></thead><tbody>`;
  rows.forEach(t => {
    const badge = t.type === "income" ? `<span class="b-in">Income</span>` : `<span class="b-ex">Expense</span>`;
    const hi    = t.is_high_expense ? `<span class="b-hi">High</span> ` : "";
    h += `<tr><td>${t.date}</td><td>${hi}${t.description}</td><td>${fmt(t.amount)}</td><td>${badge}</td><td>${t.category}</td>${showDel?`<td><button class="btn-del" onclick="delTxn(${t.id})">Delete</button></td>`:""}</tr>`;
  });
  return h + "</tbody></table>";
}

// Filters live-update
["f-search","f-filter-type","f-filter-cat"].forEach(id =>
  document.getElementById(id)?.addEventListener("change", loadTransactions)
);
document.getElementById("f-search")?.addEventListener("input", loadTransactions);

// Add transaction
document.getElementById("txn-form")?.addEventListener("submit", async e => {
  e.preventDefault();
  const msgEl = document.getElementById("txn-msg");
  const payload = {
    date:        document.getElementById("f-date").value,
    description: document.getElementById("f-desc").value.trim(),
    amount:      parseFloat(document.getElementById("f-amt").value),
    type:        document.getElementById("f-type").value,
    category:    document.getElementById("f-cat").value,
  };
  if (!payload.date || !payload.description || !payload.type || !payload.category) {
    msgEl.textContent = "All fields are required."; msgEl.className = "msg err"; return;
  }
  if (payload.amount <= 0 || isNaN(payload.amount)) {
    msgEl.textContent = "Amount must be greater than zero."; msgEl.className = "msg err"; return;
  }
  try {
    await api("/api/transactions", { method:"POST", body:JSON.stringify(payload) });
    msgEl.textContent = "Transaction added!"; msgEl.className = "msg ok";
    e.target.reset();
    document.getElementById("f-date").valueAsDate = new Date();
    loadTransactions();
    setTimeout(() => { msgEl.textContent = ""; }, 3000);
  } catch(err) { msgEl.textContent = "Error: " + err.message; msgEl.className = "msg err"; }
});

async function delTxn(id) {
  if (!confirm("Delete this transaction?")) return;
  try { await api("/api/transactions/" + id, { method:"DELETE" }); loadTransactions(); }
  catch(e) { alert("Error: " + e.message); }
}

function downloadExport(format) {
  const search   = document.getElementById("f-search")?.value || "";
  const type     = document.getElementById("f-filter-type")?.value || "";
  const category = document.getElementById("f-filter-cat")?.value || "";
  const qs = new URLSearchParams({ search, type, category }).toString();
  // Use fetch+blob so session header is sent (window.location.href can't send headers)
  fetch(`/api/export/${format}?${qs}`, { headers: { "x-session-id": SESSION_ID } })
    .then(res => {
      if (!res.ok) { res.json().then(d => alert(d.detail || "No data to export.")); return; }
      return res.blob();
    })
    .then(blob => {
      if (!blob) return;
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `finsight_transactions.${format}`;
      a.click();
      URL.revokeObjectURL(url);
    });
}

// ── Upload ────────────────────────────────────────────────────────────────────
const dropZone   = document.getElementById("drop-zone");
const csvInput   = document.getElementById("csv-input");
const uploadRes  = document.getElementById("upload-result");

dropZone?.addEventListener("click", e => { if (e.target !== csvInput) csvInput?.click(); });
dropZone?.addEventListener("dragover",  e => { e.preventDefault(); dropZone.style.background="#dbeafe"; });
dropZone?.addEventListener("dragleave", () => { dropZone.style.background=""; });
dropZone?.addEventListener("drop", e => { e.preventDefault(); dropZone.style.background=""; doUpload(e.dataTransfer.files[0]); });
csvInput?.addEventListener("change", () => doUpload(csvInput.files[0]));

async function doUpload(file) {
  if (!file) return;
  if (!file.name.endsWith(".csv")) { showUpload("Only CSV files are supported.", true); return; }
  const fd = new FormData(); fd.append("file", file);
  try {
    const res = await fetch("/api/upload", { method:"POST", body:fd, headers:{"x-session-id": SESSION_ID} });
    const d = await res.json();
    if (!res.ok) throw new Error(d.detail || "Upload failed");
    showUpload(`✅ <strong>Import complete!</strong><br>
      Total rows: <strong>${d.total_rows}</strong><br>
      Imported: <strong>${d.imported}</strong><br>
      Invalid/skipped: <strong>${d.invalid}</strong><br>
      Duplicates removed: <strong>${d.duplicates}</strong>
      ${d.errors.length ? "<br>Issues: " + d.errors.join("; ") : ""}`, false);
  } catch(e) { showUpload("❌ " + e.message, true); }
}

function showUpload(html, isErr) {
  uploadRes.style.display = "block";
  uploadRes.innerHTML = html;
  uploadRes.className = "upload-result" + (isErr ? " err" : "");
}

// ── Analysis ──────────────────────────────────────────────────────────────────
async function loadAnalysis() {
  const wrap  = document.getElementById("analysis-wrap");
  const month = document.getElementById("a-month")?.value || "";
  const type  = document.getElementById("a-type")?.value || "";
  const qs    = new URLSearchParams({ month, type }).toString();
  try {
    const d = await api("/api/analysis?" + qs);
    let h = `<div class="stats-grid">
      <div class="si"><div class="si-lbl">Avg Expense</div><div class="si-val">${fmt(d.avg_expense)}</div></div>
      <div class="si"><div class="si-lbl">Max Expense</div><div class="si-val">${fmt(d.max_expense)}</div></div>
      <div class="si"><div class="si-lbl">Min Expense</div><div class="si-val">${fmt(d.min_expense)}</div></div>
      <div class="si"><div class="si-lbl">Transactions</div><div class="si-val">${d.total_transactions}</div></div>
      <div class="si"><div class="si-lbl">Avg Monthly Expense</div><div class="si-val">${fmt(d.avg_monthly_expense)}</div></div>
      <div class="si"><div class="si-lbl">Highest Month</div><div class="si-val">${d.highest_spending_month||"N/A"}</div></div>
    </div>
    <h3 style="margin-bottom:10px">Category Breakdown</h3>
    <table class="tbl"><thead><tr><th>Category</th><th>Total Spent</th><th>% of Expenses</th></tr></thead><tbody>`;
    (d.category_breakdown||[]).forEach(c => {
      h += `<tr><td>${c.category}</td><td>${fmt(c.total)}</td><td>${c.percentage}%</td></tr>`;
    });
    h += `</tbody></table>
    <h3 style="margin:14px 0 10px">Monthly Summary</h3>
    <table class="tbl"><thead><tr><th>Month</th><th>Income</th><th>Expenses</th><th>Savings</th></tr></thead><tbody>`;
    (d.monthly_summary||[]).forEach(m => {
      h += `<tr><td>${m.month}</td><td>${fmt(m.income)}</td><td>${fmt(m.expenses)}</td><td>${fmt(m.savings)}</td></tr>`;
    });
    h += "</tbody></table>";
    wrap.innerHTML = h;
  } catch(e) { wrap.innerHTML = `<p class="empty">${e.message}</p>`; }
}

// ── Insights ──────────────────────────────────────────────────────────────────
async function loadInsights() {
  const wrap = document.getElementById("insights-wrap");
  try {
    const d = await api("/api/insights");
    const icons = ["💡","📌","📊","⚠️","✅","📈","💰","🔍"];
    wrap.innerHTML = (d.insights||[]).map((ins, i) =>
      `<div class="ins-item"><span class="ins-ico">${icons[i%icons.length]}</span><span class="ins-txt">${ins}</span></div>`
    ).join("") || '<p class="empty">No insights yet.</p>';
  } catch(e) { wrap.innerHTML = '<p class="empty">Could not load insights.</p>'; }
}

// ── Init ──────────────────────────────────────────────────────────────────────
const di = document.getElementById("f-date");
if (di) di.valueAsDate = new Date();
go("dashboard");
