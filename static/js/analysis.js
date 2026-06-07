let allTransactions = [];
let activePeriod = "this_month";

let donutChartInstance;
let dayChartInstance;
let monthlyTrendChartInstance;
let dailyTrendChartInstance;

document.addEventListener("DOMContentLoaded", async () => {
  if (window.lucide) lucide.createIcons();

  const userId = localStorage.getItem("finadvisor_user_id") || "00000000-0000-0000-0000-000000000001";

  bindAnalysisTabs();
  bindPeriodFilters();

  try {
    const txnRes = await fetch(`/api/v1/transactions/?user_id=${userId}&limit=500`);
    const txnData = await txnRes.json();
    allTransactions = Array.isArray(txnData) ? txnData : txnData.items || txnData.transactions || [];

    applyPeriod(activePeriod);
  } catch (err) {
    console.error("Analysis error:", err);
  }
});

function bindAnalysisTabs() {
  document.querySelectorAll(".analysis-tab").forEach((tab) => {
    tab.addEventListener("click", () => {
      document.querySelectorAll(".analysis-tab").forEach((t) => t.classList.remove("active"));
      document.querySelectorAll(".analysis-tab-panel").forEach((p) => p.classList.remove("active"));
      tab.classList.add("active");
      document.getElementById(`tab-${tab.dataset.tab}`)?.classList.add("active");
    });
  });
}

function bindPeriodFilters() {
  document.querySelectorAll("[data-period]").forEach((btn) => {
    btn.addEventListener("click", () => {
      document.querySelectorAll("[data-period]").forEach((b) => b.classList.remove("active"));
      btn.classList.add("active");
      applyPeriod(btn.dataset.period || "this_month");
    });
  });
}

function applyPeriod(period) {
  activePeriod = period;
  const filtered = filterTransactionsByPeriod(allTransactions, period);

  renderSpendingBreakdown(filtered, period);
  renderTrends(filtered);

  if (window.lucide) lucide.createIcons();
}

function getRangeForPeriod(period, now = new Date()) {
  const startOfToday = new Date(now.getFullYear(), now.getMonth(), now.getDate());
  let start;
  let end;

  if (period === "this_month") {
    start = new Date(now.getFullYear(), now.getMonth(), 1);
    end = new Date(now.getFullYear(), now.getMonth() + 1, 1);
  } else if (period === "last_month") {
    start = new Date(now.getFullYear(), now.getMonth() - 1, 1);
    end = new Date(now.getFullYear(), now.getMonth(), 1);
  } else if (period === "3_months") {
    start = new Date(now.getFullYear(), now.getMonth() - 2, 1);
    end = new Date(now.getFullYear(), now.getMonth() + 1, 1);
  } else if (period === "6_months") {
    start = new Date(now.getFullYear(), now.getMonth() - 5, 1);
    end = new Date(now.getFullYear(), now.getMonth() + 1, 1);
  } else {
    start = new Date(now.getFullYear(), now.getMonth(), 1);
    end = new Date(now.getFullYear(), now.getMonth() + 1, 1);
  }

  if (period === "this_month") {
    end = new Date(startOfToday.getFullYear(), startOfToday.getMonth(), startOfToday.getDate() + 1);
  }

  return { start, end };
}

function getPreviousRange(period, now = new Date()) {
  if (period === "this_month") return getRangeForPeriod("last_month", now);
  if (period === "last_month") {
    const start = new Date(now.getFullYear(), now.getMonth() - 2, 1);
    const end = new Date(now.getFullYear(), now.getMonth() - 1, 1);
    return { start, end };
  }
  if (period === "3_months") {
    const start = new Date(now.getFullYear(), now.getMonth() - 5, 1);
    const end = new Date(now.getFullYear(), now.getMonth() - 2, 1);
    return { start, end };
  }
  const start = new Date(now.getFullYear(), now.getMonth() - 11, 1);
  const end = new Date(now.getFullYear(), now.getMonth() - 5, 1);
  return { start, end };
}

function filterTransactionsByRange(transactions, range) {
  return transactions.filter((t) => {
    const txDate = new Date(t.transaction_date);
    return txDate >= range.start && txDate < range.end;
  });
}

function filterTransactionsByPeriod(transactions, period) {
  return filterTransactionsByRange(transactions, getRangeForPeriod(period));
}

function renderSpendingBreakdown(transactions, period) {
  const debits = transactions.filter((t) => t.transaction_type === "debit");
  const total = debits.reduce((sum, t) => sum + Number(t.amount || 0), 0);

  const range = getRangeForPeriod(period);
  const days = Math.max(1, Math.round((range.end - range.start) / (1000 * 60 * 60 * 24)));

  const prevRange = getPreviousRange(period);
  const prevDebits = filterTransactionsByRange(allTransactions, prevRange).filter((t) => t.transaction_type === "debit");
  const prevTotal = prevDebits.reduce((sum, t) => sum + Number(t.amount || 0), 0);
  const changePct = prevTotal > 0 ? ((total - prevTotal) / prevTotal) * 100 : 0;

  const spendTotal = document.getElementById("spend-total");
  const spendDailyAvg = document.getElementById("spend-daily-avg");
  const spendVsLast = document.getElementById("spend-vs-last");

  if (spendTotal) spendTotal.textContent = `Rs${total.toLocaleString("en-IN")}`;
  if (spendDailyAvg) spendDailyAvg.textContent = `Rs${Math.round(total / days).toLocaleString("en-IN")}`;
  if (spendVsLast) spendVsLast.textContent = `${changePct >= 0 ? "+" : ""}${changePct.toFixed(1)}%`;

  const categoryMap = {};
  debits.forEach((t) => {
    const category = t.merchant_category || "Other";
    categoryMap[category] = (categoryMap[category] || 0) + Number(t.amount || 0);
  });

  const categories = Object.entries(categoryMap).sort((a, b) => b[1] - a[1]);
  const topCategory = document.getElementById("spend-top-category");
  if (topCategory) topCategory.textContent = categories.length > 0 ? categories[0][0] : "-";

  const colors = ["#4F46E5", "#10B981", "#F59E0B", "#EF4444", "#7C3AED", "#3B82F6", "#EC4899", "#14B8A6", "#F97316", "#64748B"];

  const legend = document.getElementById("analysisDonutLegend");
  if (legend) {
    legend.innerHTML = categories.length
      ? categories
          .map(
            (c, i) => `
        <div class="legend-item">
          <div class="legend-dot" style="background:${colors[i % colors.length]}"></div>
          <span>${c[0]}</span>
          <span class="analysis-legend-value">Rs${c[1].toLocaleString("en-IN")}</span>
        </div>
      `
          )
          .join("")
      : '<div class="analysis-placeholder-cell">No category data</div>';
  }

  const donutCtx = document.getElementById("analysisDonutChart")?.getContext("2d");
  if (donutChartInstance) donutChartInstance.destroy();
  if (window.Chart && donutCtx && categories.length) {
    donutChartInstance = new Chart(donutCtx, {
      type: "doughnut",
      data: {
        labels: categories.map((c) => c[0]),
        datasets: [
          {
            data: categories.map((c) => c[1]),
            backgroundColor: categories.map((_, i) => colors[i % colors.length]),
            borderWidth: 2,
            borderColor: "#fff",
            hoverOffset: 6,
          },
        ],
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        cutout: "65%",
        plugins: {
          legend: { display: false },
          tooltip: {
            callbacks: {
              label: (ctx) => ` Rs${ctx.raw.toLocaleString("en-IN")}`,
            },
          },
        },
      },
    });
  }

  renderDayOfWeekChart(debits);

  const tbody = document.getElementById("categoryDetailBody");
  if (tbody) {
    tbody.innerHTML = categories.length
      ? categories
          .map(
            (c, i) => `
        <tr>
          <td>
            <span class="analysis-category-cell">
              <span class="analysis-category-dot" style="background:${colors[i % colors.length]}"></span>
              ${c[0]}
            </span>
          </td>
          <td>${debits.filter((t) => (t.merchant_category || "Other") === c[0]).length}</td>
          <td class="analysis-cell-strong">Rs${c[1].toLocaleString("en-IN")}</td>
          <td>
            <div class="analysis-percent-cell">
              <div class="analysis-percent-track">
                <div class="analysis-percent-fill" style="background:${colors[i % colors.length]};width:${total > 0 ? ((c[1] / total) * 100).toFixed(0) : 0}%"></div>
              </div>
              ${total > 0 ? ((c[1] / total) * 100).toFixed(1) : 0}%
            </div>
          </td>
          <td><span class="analysis-trend-muted">-</span></td>
        </tr>
      `
          )
          .join("")
      : '<tr><td colspan="5" class="analysis-placeholder-cell">No transactions found</td></tr>';
  }
}

function renderDayOfWeekChart(debits) {
  const dayTotals = [0, 0, 0, 0, 0, 0, 0];
  debits.forEach((t) => {
    const day = new Date(t.transaction_date).getDay();
    dayTotals[day] += Number(t.amount || 0);
  });

  const ctx = document.getElementById("analysisDayChart")?.getContext("2d");
  if (dayChartInstance) dayChartInstance.destroy();
  if (!window.Chart || !ctx) return;

  dayChartInstance = new Chart(ctx, {
    type: "bar",
    data: {
      labels: ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"],
      datasets: [
        {
          data: dayTotals,
          backgroundColor: "rgba(79, 70, 229, 0.8)",
          borderRadius: 8,
        },
      ],
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: { legend: { display: false } },
      scales: {
        x: { grid: { display: false } },
        y: {
          grid: { color: "rgba(0,0,0,0.04)" },
          ticks: {
            callback: (v) => `Rs${Number(v).toLocaleString("en-IN")}`,
          },
        },
      },
    },
  });
}


function renderTrends(transactions) {
  const debitTxns = transactions.filter((t) => t.transaction_type === "debit");

  const monthlyMap = {};
  debitTxns.forEach((t) => {
    const d = new Date(t.transaction_date);
    const key = `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}`;
    monthlyMap[key] = (monthlyMap[key] || 0) + Number(t.amount || 0);
  });

  const months = Object.entries(monthlyMap).sort((a, b) => a[0].localeCompare(b[0])).slice(-6);

  const trendCtx = document.getElementById("monthlyTrendChart")?.getContext("2d");
  if (monthlyTrendChartInstance) monthlyTrendChartInstance.destroy();
  if (window.Chart && trendCtx && months.length) {
    monthlyTrendChartInstance = new Chart(trendCtx, {
      type: "line",
      data: {
        labels: months.map((m) => {
          const [y, mo] = m[0].split("-");
          return new Date(y, mo - 1).toLocaleString("default", { month: "short" });
        }),
        datasets: [
          {
            label: "Spending",
            data: months.map((m) => m[1]),
            borderColor: "#4F46E5",
            backgroundColor: "rgba(79,70,229,0.08)",
            tension: 0.4,
            fill: true,
            pointBackgroundColor: "#4F46E5",
            pointRadius: 4,
            pointHoverRadius: 6,
          },
        ],
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: { legend: { display: false } },
      },
    });
  }

  renderDailyTrendChart(debitTxns);
}

function renderDailyTrendChart(debitTxns) {
  const byDay = {};
  debitTxns.forEach((t) => {
    const d = new Date(t.transaction_date);
    const key = `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
    byDay[key] = (byDay[key] || 0) + Number(t.amount || 0);
  });

  const entries = Object.entries(byDay).sort((a, b) => a[0].localeCompare(b[0])).slice(-30);
  const ctx = document.getElementById("dailyTrendChart")?.getContext("2d");

  if (dailyTrendChartInstance) dailyTrendChartInstance.destroy();
  if (!window.Chart || !ctx || !entries.length) return;

  dailyTrendChartInstance = new Chart(ctx, {
    type: "line",
    data: {
      labels: entries.map((e) => {
        const d = new Date(e[0]);
        return `${d.getDate()}/${d.getMonth() + 1}`;
      }),
      datasets: [
        {
          data: entries.map((e) => e[1]),
          borderColor: "#10B981",
          backgroundColor: "rgba(16,185,129,0.08)",
          tension: 0.35,
          fill: true,
          pointRadius: 2,
        },
      ],
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: { legend: { display: false } },
    },
  });
}
