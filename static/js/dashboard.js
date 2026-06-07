let categoryChart;
let trendChart;
let dashboardSyncPoll = null;
let dashboardDataRefreshPoll = null;

if (window.Chart) {
  Chart.defaults.font.family = "'Inter', 'Space Grotesk', system-ui";
  Chart.defaults.font.size = 11;
  Chart.defaults.color = "#94A3B8";
}

function formatMoney(value) {
  return Number(value || 0).toLocaleString("en-IN", { maximumFractionDigits: 2 });
}

function clearDashboardSyncTimers() {
  if (dashboardSyncPoll) {
    clearInterval(dashboardSyncPoll);
    dashboardSyncPoll = null;
  }
  if (dashboardDataRefreshPoll) {
    clearInterval(dashboardDataRefreshPoll);
    dashboardDataRefreshPoll = null;
  }
}

function upsertDashboardSyncBanner(kind, text) {
  const target = document.querySelector(".dashboard-top-row");
  if (!target) return;

  let banner = document.getElementById("dashboardSyncBanner");
  if (!banner) {
    banner = document.createElement("div");
    banner.id = "dashboardSyncBanner";
    banner.className = "sync-banner";
    target.insertAdjacentElement("afterend", banner);
  }

  banner.className = `sync-banner ${kind}`;
  banner.textContent = text;
}

function removeDashboardSyncBanner() {
  const banner = document.getElementById("dashboardSyncBanner");
  if (banner) banner.remove();
}

async function monitorDashboardEmailSync() {
  clearDashboardSyncTimers();
  const userId = getUserId();
  const status = await apiFetch(`/api/v1/email-config/sync-status?user_id=${userId}`);

  if (status.sync_status === "syncing") {
    upsertDashboardSyncBanner("info", "Importing transactions from email...");

    dashboardDataRefreshPoll = setInterval(() => {
      loadDashboardData();
    }, 10000);

    dashboardSyncPoll = setInterval(async () => {
      try {
        const latest = await apiFetch(`/api/v1/email-config/sync-status?user_id=${userId}`);
        if (latest.sync_status === "completed") {
          clearDashboardSyncTimers();
          removeDashboardSyncBanner();
          await loadDashboardData();
          showToast("Email import completed. Dashboard refreshed.", "success");
        } else if (latest.sync_status === "error") {
          clearDashboardSyncTimers();
          upsertDashboardSyncBanner("error", `Email import failed: ${latest.last_error || "Unknown error"}`);
        }
      } catch (error) {
        console.error("Dashboard sync polling failed", error);
      }
    }, 5000);
    return;
  }

  if (status.sync_status === "completed") {
    const marker = `dashboard-sync-refresh-${userId}`;
    if (sessionStorage.getItem(marker) !== "done") {
      sessionStorage.setItem(marker, "done");
      await loadDashboardData();
    }
  }
}

function renderHealthScore(score, label, color) {
  const radius = 40;
  const circumference = 2 * Math.PI * radius;
  const rawScore = Number(score || 0);
  const has900Scale = rawScore > 100;
  const normalizedPercent = Math.max(0, Math.min(100, has900Scale ? rawScore / 9 : rawScore));
  const displayScore = Math.round(Math.max(0, Math.min(900, has900Scale ? rawScore : rawScore * 9)));
  const offset = circumference - (normalizedPercent / 100) * circumference;

  const container = document.getElementById("healthScoreWidget");
  if (!container) return;

  container.innerHTML = `
    <div class="health-score-wrap">
      <div class="health-score-svg-wrap">
        <svg width="100" height="100" viewBox="0 0 100 100">
          <circle cx="50" cy="50" r="${radius}" fill="none" stroke="#E2E8F0" stroke-width="8" />
          <circle
            cx="50"
            cy="50"
            r="${radius}"
            fill="none"
            stroke="${color}"
            stroke-width="8"
            stroke-linecap="round"
            stroke-dasharray="${circumference}"
            stroke-dashoffset="${offset}"
            transform="rotate(-90 50 50)"
            style="transition: stroke-dashoffset 1s ease"
          />
        </svg>
        <div class="health-score-center">
          <span class="health-score-num" style="color:${color};">${displayScore}</span>
          <span class="health-score-den">/900</span>
        </div>
      </div>
      <div class="health-score-pill" style="background:${color}18;color:${color};">${label}</div>
    </div>
  `;
}

function renderSummaryCards(summary) {
  const totalOutstanding = document.getElementById("totalOutstanding");
  const availableCredit = document.getElementById("availableCredit");
  const thisMonthSpending = document.getElementById("thisMonthSpending");
  const momChange = document.getElementById("momChange");
  const emiOutflow = document.getElementById("emiOutflow");
  const totalMinimumDue = document.getElementById("totalMinimumDue");

  if (totalOutstanding) totalOutstanding.textContent = `Rs${formatMoney(summary.total_outstanding)}`;
  if (availableCredit) availableCredit.textContent = `Rs${formatMoney(summary.available_credit)}`;
  if (thisMonthSpending) thisMonthSpending.textContent = `Rs${formatMoney(summary.this_month_spending)}`;
  if (momChange) momChange.textContent = `${Number(summary.month_change_percentage || 0).toFixed(1)}%`;
  if (emiOutflow) emiOutflow.textContent = `Rs${formatMoney(summary.total_monthly_emi)}`;

  const minDue = Number(summary.credit_metrics?.total_minimum_due_all_cards || 0);
  if (totalMinimumDue) totalMinimumDue.textContent = `Rs${formatMoney(minDue)}`;
}

function renderCategoryChart(categoryData) {
  const labels = Object.keys(categoryData || {});
  const values = Object.values(categoryData || {});

  const chartCanvas = document.getElementById("categoryChart");
  const legend = document.getElementById("categoryLegend");
  const placeholder = document.getElementById("categoryPlaceholder");

  const hasData = labels.length > 0 && values.some((v) => Number(v) > 0);

  if (!window.Chart) {
    if (chartCanvas) chartCanvas.style.display = "none";
    if (legend) legend.innerHTML = "";
    if (placeholder) placeholder.style.display = "flex";
    return;
  }

  if (!hasData) {
    if (categoryChart) categoryChart.destroy();
    if (chartCanvas) chartCanvas.style.display = "none";
    if (legend) legend.innerHTML = "";
    if (placeholder) placeholder.style.display = "flex";
    return;
  }

  if (placeholder) placeholder.style.display = "none";
  if (chartCanvas) chartCanvas.style.display = "block";

  if (categoryChart) categoryChart.destroy();

  const palette = ["#2563eb", "#7c3aed", "#10b981", "#f59e0b", "#ef4444", "#0ea5e9", "#14b8a6", "#64748b"];
  categoryChart = new Chart(chartCanvas, {
    type: "doughnut",
    data: {
      labels,
      datasets: [
        {
          data: values,
          backgroundColor: labels.map((_, idx) => palette[idx % palette.length]),
          borderWidth: 2,
          borderColor: "#fff",
        },
      ],
    },
    options: {
      cutout: "72%",
      responsive: true,
      maintainAspectRatio: false,
      plugins: {
        legend: { display: false },
        tooltip: {
          backgroundColor: "rgba(15,23,42,0.9)",
          padding: 12,
          cornerRadius: 10,
          titleFont: { size: 12, weight: "600" },
          bodyFont: { size: 11 },
          callbacks: {
            label: (ctx) => ` Rs${ctx.raw.toLocaleString("en-IN")}`,
          },
        },
      },
      animation: {
        animateRotate: true,
        duration: 800,
      },
    },
  });

  if (legend) {
    legend.innerHTML = labels
      .map(
        (label, index) => `
      <div class="legend-item">
        <span class="legend-dot" style="background:${palette[index % palette.length]};"></span>
        <span>${label}</span>
        <span style="margin-left:auto;">Rs${formatMoney(values[index])}</span>
      </div>`
      )
      .join("");
  }
}

function loadMonthlyTrendChart(summary) {
  const canvas = document.getElementById("trendChart");
  if (!canvas || !window.Chart) return;

  if (trendChart) trendChart.destroy();

  const thisMonth = Number(summary.this_month_spending || 0);
  const lastMonth = Number(summary.last_month_spending || 0);
  const avg = (thisMonth + lastMonth) / 2;

  const ctx = canvas.getContext("2d");
  const gradient = ctx.createLinearGradient(0, 0, 0, 300);
  gradient.addColorStop(0, "#4F46E5");
  gradient.addColorStop(1, "#7C3AED");

  trendChart = new Chart(canvas, {
    type: "bar",
    data: {
      labels: ["Last Month", "This Month", "Average"],
      datasets: [
        {
          label: "Spending",
          data: [lastMonth, thisMonth, avg],
          backgroundColor: gradient,
          borderRadius: 8,
          borderSkipped: "bottom",
        },
      ],
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: {
        legend: { display: false },
        tooltip: {
          backgroundColor: "rgba(15,23,42,0.9)",
          padding: 12,
          cornerRadius: 10,
          callbacks: {
            label: (ctx) => ` Rs${ctx.raw.toLocaleString("en-IN")}`,
          },
        },
      },
      scales: {
        x: {
          grid: { display: false },
          ticks: { font: { size: 10 }, color: "#94A3B8" },
          border: { display: false },
        },
        y: {
          grid: { color: "rgba(0,0,0,0.04)", drawBorder: false },
          ticks: {
            font: { size: 10 },
            color: "#94A3B8",
            callback: (v) => `Rs${(v / 1000).toFixed(0)}k`,
          },
          border: { display: false },
        },
      },
      elements: {
        bar: {
          borderRadius: 8,
          borderSkipped: "bottom",
        },
      },
      animation: { duration: 800 },
    },
  });
}

function loadCardUtilization(summary) {
  const utilizationList = document.getElementById("utilizationList");
  if (!utilizationList) return;

  const cards = summary.credit_metrics?.per_card || [];
  if (!cards.length) {
    utilizationList.innerHTML = '<div class="empty-state p-12">No active credit cards</div>';
    return;
  }

  utilizationList.innerHTML = cards
    .map((card) => {
      const ratio = Number(card.credit_utilization_ratio || 0);
      const color = ratio < 30 ? "#10b981" : ratio < 60 ? "#f59e0b" : "#ef4444";
      return `
        <div class="util-row">
          <div>${card.bank_name}</div>
          <div class="util-bar"><span style="width:${Math.min(100, ratio)}%;background:${color};"></span></div>
          <div>Rs${formatMoney(card.current_balance)} / Rs${formatMoney(card.credit_limit)}</div>
          <div class="badge" style="background:${color}22;color:${color};">${ratio.toFixed(1)}%</div>
        </div>
      `;
    })
    .join("");
}

async function loadRecentTransactions(userId) {
  const recentTable = document.getElementById("recentTransactions");
  if (!recentTable) return;

  const res = await fetch(`/api/v1/transactions/?user_id=${userId}&limit=10`);
  const payload = await res.json();
  if (!res.ok) {
    throw new Error(payload.detail || "Failed to load recent transactions");
  }

  recentTable.innerHTML = `
    <tr><th>Date</th><th>Merchant</th><th>Category</th><th>Amount</th><th>Card</th><th>Balance</th></tr>
    ${payload
      .map(
        (txn) => `
      <tr>
        <td>${new Date(txn.transaction_date).toLocaleDateString()}</td>
        <td>${txn.description || txn.merchant_name || "-"}</td>
        <td>${txn.merchant_category || "Other"}</td>
        <td class="${txn.transaction_type === "debit" ? "amount-debit" : "amount-credit"}">
          ${txn.transaction_type === "debit" ? "-" : "+"}Rs${formatMoney(txn.amount)}
        </td>
        <td>${txn.card_id || "-"}</td>
        <td>${txn.balance_after ? `Rs${formatMoney(txn.balance_after)}` : "-"}</td>
      </tr>`
      )
      .join("")}
  `;
}

function loadEmiAnalysis(summary) {
  const emiList = document.getElementById("emiList");
  if (!emiList) return;

  const cards = summary.credit_metrics?.per_card || [];
  emiList.innerHTML = cards
    .map(
      (card) => `
      <div class="flex-between p-12 border-top-muted">
        <span>${card.bank_name}</span>
        <span>Rs${formatMoney(card.minimum_payment_due || 0)} min due</span>
      </div>`
    )
    .join("");
}

function renderAlerts(alerts) {
  const alertsEl = document.getElementById("alerts");
  if (!alertsEl) return;

  if (!alerts || !alerts.length) {
    alertsEl.innerHTML = '<div class="alert-item"><i data-lucide="check-circle" style="color:#10b981"></i><span>No active alerts</span></div>';
  } else {
    alertsEl.innerHTML = alerts
      .map((item) => {
        const color = item.severity === "danger" ? "#ef4444" : item.severity === "warning" ? "#f59e0b" : "#2563eb";
        const icon = item.type === "payment_due" ? "clock" : "alert-triangle";
        return `<div class="alert-item"><i data-lucide="${icon}" style="color:${color}"></i><span>${item.message}</span></div>`;
      })
      .join("");
  }

  if (window.lucide) lucide.createIcons();
}

async function loadDashboardData() {
  const userId = localStorage.getItem("finadvisor_user_id") || "00000000-0000-0000-0000-000000000001";

  try {
    const summaryRes = await fetch(`/api/v1/dashboard/summary?user_id=${userId}`);
    if (!summaryRes.ok) {
      const err = await summaryRes.json().catch(() => ({}));
      throw new Error(err.detail || "Failed to load dashboard");
    }

    const summary = await summaryRes.json();

    renderSummaryCards(summary);
    renderHealthScore(summary.financial_health_score || 50, summary.score_label || "Fair", summary.score_color || "#F59E0B");
    renderCategoryChart(summary.spending?.category_breakdown || {});
    loadMonthlyTrendChart(summary);
    loadCardUtilization(summary);
    await loadRecentTransactions(userId);
    loadEmiAnalysis(summary);
    renderAlerts(summary.alerts || []);
  } catch (err) {
    console.error("Dashboard load error:", err);
    showToast("Failed to load dashboard data", "error");
  }
}

function calculateManual() {
  const income = (Number(document.getElementById("m-income")?.value) || 0) + (Number(document.getElementById("m-other-income")?.value) || 0);
  const outstanding = Number(document.getElementById("m-total-outstanding")?.value) || 0;
  const totalEmi = Number(document.getElementById("m-total-emi")?.value) || 0;
  const pendingEmi = Number(document.getElementById("m-pending-emi")?.value) || 0;

  const rent = Number(document.getElementById("m-rent")?.value) || 0;
  const groceries = Number(document.getElementById("m-groceries")?.value) || 0;
  const utilities = Number(document.getElementById("m-utilities")?.value) || 0;
  const transport = Number(document.getElementById("m-transport")?.value) || 0;
  const entertainment = Number(document.getElementById("m-entertainment")?.value) || 0;
  const otherExp = Number(document.getElementById("m-other-expenses")?.value) || 0;

  const totalExpenses = rent + groceries + utilities + transport + entertainment + otherExp + totalEmi;
  const disposable = income - totalExpenses;
  const savingsRate = income > 0 ? (disposable / income * 100).toFixed(1) : 0;
  const emiRatio = income > 0 ? (totalEmi / income * 100).toFixed(1) : 0;

  const placeholder = document.getElementById("manual-results-placeholder");
  const content = document.getElementById("manual-results-content");

  if (placeholder) placeholder.style.display = "none";
  if (content) {
    content.style.display = "block";
    content.classList.remove("hidden");
    content.innerHTML = `
      <div class="p-12">
        <div class="font-600 mb-12">Financial Analysis Results</div>
        ${[
          { label: "Monthly Income", value: `Rs${income.toLocaleString("en-IN")}`, color: "#10B981" },
          { label: "Total Expenses", value: `Rs${totalExpenses.toLocaleString("en-IN")}`, color: "#EF4444" },
          { label: "Disposable Income", value: `Rs${disposable.toLocaleString("en-IN")}`, color: disposable >= 0 ? "#10B981" : "#EF4444" },
          { label: "Savings Rate", value: `${savingsRate}%`, color: savingsRate >= 20 ? "#10B981" : "#F59E0B" },
          { label: "EMI-to-Income Ratio", value: `${emiRatio}%`, color: emiRatio <= 40 ? "#10B981" : "#EF4444" },
          { label: "Total Outstanding", value: `Rs${outstanding.toLocaleString("en-IN")}`, color: "#475569" },
          { label: "Pending EMI", value: `Rs${pendingEmi.toLocaleString("en-IN")}`, color: "#64748B" },
        ]
          .map(
            (r) => `
          <div class="flex-between p-12 border-top-muted">
            <span class="text-sm">${r.label}</span>
            <span class="font-600" style="color:${r.color}">${r.value}</span>
          </div>
        `
          )
          .join("")}

        <div class="mt-12 p-12" style="border-radius:10px;background:${savingsRate >= 20 ? "#ECFDF5" : "#FFF7ED"};border:1px solid ${savingsRate >= 20 ? "#A7F3D0" : "#FDE68A"};">
          <div class="font-600" style="font-size:11px;color:${savingsRate >= 20 ? "#065F46" : "#92400E"}">
            ${savingsRate >= 20 ? "Good financial health!" : "Consider reducing expenses"}
          </div>
          <div style="font-size:10px;margin-top:4px;color:${savingsRate >= 20 ? "#065F46" : "#92400E"}">
            ${emiRatio > 40 ? "EMI ratio above 40% is high. Consider prepaying loans." : "EMI ratio is within healthy range."}
          </div>
        </div>
      </div>
    `;
  }

  if (window.showToast) showToast("Calculations complete!", "success");
}

window.refreshDashboard = loadDashboardData;
window.calculateManual = calculateManual;

function setDashboardTab(target) {
  const auto = document.getElementById("autoTab");
  const manual = document.getElementById("manualTab");

  if (auto) {
    auto.style.display = target === "auto" ? "block" : "none";
    auto.classList.toggle("hidden", target !== "auto");
  }
  if (manual) {
    manual.style.display = target === "manual" ? "block" : "none";
    manual.classList.toggle("hidden", target !== "manual");
  }

  document.querySelectorAll(".dashboard-tab").forEach((btn) => {
    btn.classList.toggle("active", btn.getAttribute("data-tab") === target);
  });

  if (window.lucide) lucide.createIcons();
}

document.addEventListener("DOMContentLoaded", () => {
  if (window.lucide) lucide.createIcons();
  setDashboardTab("auto");
  loadDashboardData();
  monitorDashboardEmailSync();

  document.querySelectorAll(".dashboard-tab").forEach((tab) => {
    tab.addEventListener("click", function () {
      const target = this.getAttribute("data-tab");
      setDashboardTab(target === "manual" ? "manual" : "auto");
    });
  });
});
