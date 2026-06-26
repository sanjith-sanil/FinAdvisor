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

  const theme = localStorage.getItem("finadvisor_theme") || "default";
  let colors = ["#4F46E5", "#10B981", "#F59E0B", "#EF4444", "#7C3AED", "#3B82F6", "#EC4899", "#14B8A6", "#F97316", "#64748B"];
  if (theme === "graphite") {
    colors = ["#3b82f6", "#6366f1", "#4f46e5", "#818cf8", "#a5b4fc", "#cbd5e1", "#94a3b8", "#64748b", "#3f3f46", "#18181b"];
  } else if (theme === "warmcharcoal") {
    colors = ["#f59e0b", "#fbbf24", "#d97706", "#b45309", "#f97316", "#ea580c", "#c2410c", "#7c2d12", "#3d3530", "#1c1917"];
  } else if (theme === "emeraldmint") {
    colors = ["#059669", "#10b981", "#34d399", "#6ee7b7", "#2563eb", "#d97706", "#dc2626", "#7c3aed", "#0891b2", "#64748b"];
  }
  const isCustomDark = ["graphite", "warmcharcoal"].includes(theme);
  const chartBorderColor = isCustomDark ? (theme === "graphite" ? "#27272a" : "#292524") : "#fff";

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
            borderColor: chartBorderColor,
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

  const theme = localStorage.getItem("finadvisor_theme") || "default";
  const isCustomDark = ["graphite", "warmcharcoal"].includes(theme);

  let barColor = "rgba(79, 70, 229, 0.8)";
  if (theme === "graphite") {
    barColor = "#3b82f6";
  } else if (theme === "warmcharcoal") {
    barColor = "#f59e0b";
  } else if (theme === "emeraldmint") {
    barColor = "rgba(5, 150, 105, 0.8)";
  }

  const tickColor = isCustomDark ? "#a1a1aa" : "#64748b";
  const gridColor = isCustomDark ? "rgba(255, 255, 255, 0.06)" : "rgba(0,0,0,0.04)";

  dayChartInstance = new Chart(ctx, {
    type: "bar",
    data: {
      labels: ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"],
      datasets: [
        {
          data: dayTotals,
          backgroundColor: barColor,
          borderRadius: 8,
        },
      ],
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: { legend: { display: false } },
      scales: {
        x: {
          grid: { display: false },
          ticks: { color: tickColor },
        },
        y: {
          grid: { color: gridColor },
          ticks: {
            color: tickColor,
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
    const theme = localStorage.getItem("finadvisor_theme") || "default";
    const isCustomDark = ["graphite", "warmcharcoal"].includes(theme);

    let lineColor = "#4F46E5";
    let lineBg = "rgba(79,70,229,0.08)";
    if (theme === "graphite") {
      lineColor = "#3b82f6";
      lineBg = "rgba(59, 130, 246, 0.08)";
    } else if (theme === "warmcharcoal") {
      lineColor = "#f59e0b";
      lineBg = "rgba(245, 158, 11, 0.08)";
    } else if (theme === "emeraldmint") {
      lineColor = "#059669";
      lineBg = "rgba(5, 150, 105, 0.08)";
    }

    const tickColor = isCustomDark ? "#a1a1aa" : "#64748b";
    const gridColor = isCustomDark ? "rgba(255, 255, 255, 0.06)" : "rgba(0,0,0,0.04)";

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
            borderColor: lineColor,
            backgroundColor: lineBg,
            tension: 0.4,
            fill: true,
            pointBackgroundColor: lineColor,
            pointRadius: 4,
            pointHoverRadius: 6,
          },
        ],
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: { legend: { display: false } },
        scales: {
          x: {
            grid: { display: false },
            ticks: { color: tickColor },
          },
          y: {
            grid: { color: gridColor },
            ticks: { color: tickColor },
          },
        },
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

  const theme = localStorage.getItem("finadvisor_theme") || "default";
  const isCustomDark = ["graphite", "warmcharcoal"].includes(theme);

  let lineColor = "#10B981";
  let lineBg = "rgba(16,185,129,0.08)";
  if (theme === "graphite" || theme === "warmcharcoal") {
    lineColor = "#4ade80";
    lineBg = "rgba(74, 222, 128, 0.08)";
  } else if (theme === "emeraldmint") {
    lineColor = "#10b981";
    lineBg = "rgba(16, 185, 129, 0.08)";
  }

  const tickColor = isCustomDark ? "#a1a1aa" : "#64748b";
  const gridColor = isCustomDark ? "rgba(255, 255, 255, 0.06)" : "rgba(0,0,0,0.04)";

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
          borderColor: lineColor,
          backgroundColor: lineBg,
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
      scales: {
        x: {
          grid: { display: false },
          ticks: { color: tickColor },
        },
        y: {
          grid: { color: gridColor },
          ticks: { color: tickColor },
        },
      },
    },
  });
}

window.addEventListener("themeChanged", () => {
  if (typeof applyPeriod === "function" && allTransactions.length > 0) {
    setTimeout(() => applyPeriod(activePeriod), 50);
  }
});
