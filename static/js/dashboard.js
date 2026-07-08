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
  const radius = 42;
  const circumference = 2 * Math.PI * radius;
  const rawScore = Number(score || 0);
  const has900Scale = rawScore > 100;
  const normalizedPercent = Math.max(0, Math.min(100, has900Scale ? rawScore / 9 : rawScore));
  const displayScore = Math.round(Math.max(0, Math.min(900, has900Scale ? rawScore : rawScore * 9)));
  const offset = circumference - (normalizedPercent / 100) * circumference;

  const theme = localStorage.getItem("finadvisor_theme") || "default";
  let displayColor = color;
  if (theme === "graphite") {
    if (color === "#10B981" || color === "#3B82F6") {
      displayColor = "#4ade80";
    } else if (color === "#EF4444" || color === "#DC2626") {
      displayColor = "#f87171";
    } else if (color === "#64748b" || color === "#64748B") {
      displayColor = "#a1a1aa";
    } else {
      displayColor = "#f59e0b";
    }
  }

  const container = document.getElementById("healthScoreWidget");
  if (!container) return;

  container.innerHTML = `
    <div class="health-score-wrap">
      <div class="health-score-svg-wrap">
        <svg width="100" height="100" viewBox="0 0 100 100">
          <circle cx="50" cy="50" r="${radius}" fill="none" stroke="${theme === 'graphite' ? '#3f3f46' : '#E2E8F0'}" stroke-width="8" />
          <circle
            cx="50"
            cy="50"
            r="${radius}"
            fill="none"
            stroke="${displayColor}"
            stroke-width="8"
            stroke-linecap="round"
            stroke-dasharray="${circumference}"
            stroke-dashoffset="${offset}"
            transform="rotate(-90 50 50)"
            style="transition: stroke-dashoffset 1s ease"
          />
        </svg>
        <div class="health-score-center">
          <span class="health-score-num" style="color:${displayColor};">${displayScore}</span>
          <span class="health-score-den">/900</span>
        </div>
      </div>
      <div class="health-score-pill" style="background:${theme === 'graphite' ? '#3f3f46' : displayColor + '18'};color:${displayColor};">${label}</div>
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

  const theme = localStorage.getItem("finadvisor_theme") || "default";
  let palette = ["#2563eb", "#7c3aed", "#10b981", "#f59e0b", "#ef4444", "#0ea5e9", "#14b8a6", "#64748b"];
  if (theme === "graphite") {
    palette = ["#3b82f6", "#6366f1", "#4f46e5", "#818cf8", "#a5b4fc", "#cbd5e1", "#94a3b8", "#64748b"];
  } else if (theme === "warmcharcoal") {
    palette = ["#f59e0b", "#fbbf24", "#d97706", "#b45309", "#f97316", "#ea580c", "#c2410c", "#7c2d12"];
  } else if (theme === "emeraldmint") {
    palette = ["#059669", "#10b981", "#34d399", "#6ee7b7", "#2563eb", "#d97706", "#dc2626", "#0891b2"];
  }
  const isCustomDark = ["graphite", "warmcharcoal"].includes(theme);
  const chartBorderColor = isCustomDark ? (theme === "graphite" ? "#27272a" : "#292524") : "#fff";

  categoryChart = new Chart(chartCanvas, {
    type: "doughnut",
    data: {
      labels,
      datasets: [
        {
          data: values,
          backgroundColor: labels.map((_, idx) => palette[idx % palette.length]),
          borderWidth: 2,
          borderColor: chartBorderColor,
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
  const theme = localStorage.getItem("finadvisor_theme") || "default";
  const isCustomDark = ["graphite", "warmcharcoal"].includes(theme);

  let barColors;
  if (isCustomDark) {
    const chartPrimary = getComputedStyle(document.body).getPropertyValue("--chart-primary").trim() || (theme === "graphite" ? "#3b82f6" : "#f59e0b");
    const chartSecondary = getComputedStyle(document.body).getPropertyValue("--chart-secondary").trim() || (theme === "graphite" ? "#6366f1" : "#fbbf24");
    barColors = [chartSecondary, chartPrimary, chartPrimary];
  } else if (theme === "emeraldmint") {
    const gradient = ctx.createLinearGradient(0, 0, 0, 300);
    gradient.addColorStop(0, "#059669");
    gradient.addColorStop(1, "#10b981");
    barColors = gradient;
  } else {
    const gradient = ctx.createLinearGradient(0, 0, 0, 300);
    gradient.addColorStop(0, "#4F46E5");
    gradient.addColorStop(1, "#7C3AED");
    barColors = gradient;
  }

  const tickColor = isCustomDark ? "#a1a1aa" : "#94A3B8";
  const gridColor = isCustomDark ? "rgba(255,255,255,0.06)" : "rgba(0,0,0,0.04)";

  trendChart = new Chart(canvas, {
    type: "bar",
    data: {
      labels: ["Last Month", "This Month", "Average"],
      datasets: [
        {
          label: "Spending",
          data: [lastMonth, thisMonth, avg],
          backgroundColor: barColors,
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
          ticks: { font: { size: 10 }, color: tickColor },
          border: { display: false },
        },
        y: {
          grid: { color: gridColor, drawBorder: false },
          ticks: {
            font: { size: 10 },
            color: tickColor,
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

  const theme = localStorage.getItem("finadvisor_theme") || "default";

  utilizationList.innerHTML = cards
    .map((card) => {
      const ratio = Number(card.credit_utilization_ratio || 0);
      const color = ratio < 30 
        ? (getComputedStyle(document.body).getPropertyValue("--success").trim() || "#10b981") 
        : ratio < 60 
        ? (getComputedStyle(document.body).getPropertyValue("--warning").trim() || "#f59e0b") 
        : (getComputedStyle(document.body).getPropertyValue("--danger").trim() || "#ef4444");
      
      const badgeBg = theme === "graphite" ? "var(--badge-bg)" : `${color}22`;
      return `
        <div class="util-row">
          <div>${card.bank_name}</div>
          <div class="util-bar"><span style="width:${Math.min(100, ratio)}%;background:${color};"></span></div>
          <div>Rs${formatMoney(card.current_balance)} / Rs${formatMoney(card.credit_limit)}</div>
          <div class="badge" style="background:${badgeBg};color:${color};">${ratio.toFixed(1)}%</div>
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

    // Fetch user profile for login streak
    try {
      const userRes = await fetch(`/api/v1/users/${userId}`);
      if (userRes.ok) {
        const user = await userRes.json();
        const streakBadge = document.getElementById("dashboardStreakBadge");
        const streakCount = document.getElementById("streakCount");
        if (streakBadge && streakCount && user.current_streak > 0) {
          streakCount.textContent = user.current_streak;
          streakBadge.style.display = "inline-flex";
        }
      }
    } catch (e) {
      console.error("Error loading user streak", e);
    }

    // Populate the dropdown first as it is critical and fast
    try {
      populateManualCardDropdown(summary);
    } catch (e) {
      console.error("Error populating manual card dropdown:", e);
    }

    try {
      renderSummaryCards(summary);
    } catch (e) {
      console.error("Error rendering summary cards:", e);
    }

    try {
      renderHealthScore(summary.financial_health_score || 50, summary.score_label || "Fair", summary.score_color || "#F59E0B");
    } catch (e) {
      console.error("Error rendering health score:", e);
    }

    // Eval Onboarding Checklist
    try {
      await checkOnboardingStatus(summary);
      await setupOnboardingListeners(summary);
    } catch (e) {
      console.error("Error loading onboarding widget:", e);
    }

    try {
      renderCategoryChart(summary.spending?.category_breakdown || {});
    } catch (e) {
      console.error("Error rendering category chart:", e);
    }

    try {
      loadMonthlyTrendChart(summary);
    } catch (e) {
      console.error("Error loading monthly trend chart:", e);
    }

    try {
      loadCardUtilization(summary);
    } catch (e) {
      console.error("Error loading card utilization:", e);
    }

    try {
      await loadRecentTransactions(userId);
    } catch (e) {
      console.error("Error loading recent transactions:", e);
    }

    try {
      loadEmiAnalysis(summary);
    } catch (e) {
      console.error("Error loading EMI analysis:", e);
    }

    try {
      renderAlerts(summary.alerts || []);
    } catch (e) {
      console.error("Error rendering alerts:", e);
    }

    // --- Budget Progress Bar ---
    try {
      await loadBudgetProgress(userId);
    } catch (e) {
      console.error("Error loading budget progress:", e);
    }
  } catch (err) {
    console.error("Dashboard load error:", err);
    showToast("Failed to load dashboard data", "error");
  }
}

function populateManualCardDropdown(summary) {
  const dropdown = document.getElementById("m-total-outstanding");
  if (!dropdown) return;

  dropdown.innerHTML = "";

  const totalOutstanding = summary.total_outstanding || 0;
  
  // 1. Add option for Total Outstanding Balance of all cards
  const totalOpt = document.createElement("option");
  totalOpt.value = totalOutstanding;
  totalOpt.textContent = "Total Outstanding Balance";
  dropdown.appendChild(totalOpt);

  // 2. Add options for individual cards
  const cards = summary.credit_metrics?.per_card || [];
  cards.forEach((card) => {
    const opt = document.createElement("option");
    opt.value = card.current_balance || 0;
    const last4Str = card.card_last4 ? ` ••••${card.card_last4}` : "";
    opt.textContent = `Outstanding of ${card.bank_name}${last4Str} (Rs${(card.current_balance || 0).toLocaleString("en-IN")})`;
    dropdown.appendChild(opt);
  });
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

window.addEventListener("themeChanged", () => {
  if (typeof loadDashboardData === "function") {
    setTimeout(() => loadDashboardData(), 50);
  }
});


// --- Onboarding Checklist Flow Helpers ---
async function checkOnboardingStatus(summary) {
  const userId = localStorage.getItem("finadvisor_user_id") || "00000000-0000-0000-0000-000000000001";
  const token = localStorage.getItem("finadvisor_token");
  const widget = document.getElementById("onboardingWidget");
  if (!widget || !userId || !token) return;

  try {
    const userRes = await fetch(`/api/v1/users/${userId}`);
    if (!userRes.ok) return;
    const user = await userRes.json();

    const budgetRes = await fetch(`/api/v1/users/${userId}/budget`);
    let budgetLimit = 0;
    if (budgetRes.ok) {
      const budgetData = await budgetRes.json();
      budgetLimit = budgetData.monthly_limit || 0;
      const budgetInput = document.getElementById("obBudgetInput");
      if (budgetInput && budgetLimit > 0 && !budgetInput.value) {
        budgetInput.value = budgetLimit;
      }
    }

    const step1Done = summary.cards_count > 0;
    const step2Done = user.email_collection_configured === true;
    const step3Done = budgetLimit > 0;

    let completedSteps = 0;
    if (step1Done) completedSteps++;
    if (step2Done) completedSteps++;
    if (step3Done) completedSteps++;

    updateStepCardStyle("obStep1", step1Done, "credit-card");
    updateStepCardStyle("obStep2", step2Done, "mail");
    updateStepCardStyle("obStep3", step3Done, "calculator");

    const percent = Math.round((completedSteps / 3) * 100);
    const ring = document.getElementById("onboardingProgressRing");
    const percentText = document.getElementById("onboardingProgressPercent");
    
    if (percentText) percentText.textContent = `${percent}%`;
    if (ring) {
      const circumference = 2 * Math.PI * 15.915; // ~100
      const offset = circumference - (completedSteps / 3) * circumference;
      ring.style.strokeDashoffset = offset;
    }

    if (completedSteps === 3) {
      widget.classList.add("hidden");
    } else {
      widget.classList.remove("hidden");
    }

    if (window.lucide) lucide.createIcons();
  } catch (e) {
    console.error("Error evaluating onboarding checklist", e);
  }
}

function updateStepCardStyle(cardId, isDone, originalIcon) {
  const card = document.getElementById(cardId);
  if (!card) return;

  const iconWrap = card.querySelector(".ob-step-icon");
  
  if (isDone) {
    card.style.borderColor = "var(--primary)";
    card.style.background = "var(--primary-light)";
    if (iconWrap) {
      iconWrap.style.background = "var(--primary)";
      iconWrap.style.color = "white";
      iconWrap.innerHTML = `<i data-lucide="check" style="width:14px;height:14px;"></i>`;
    }
    const link = card.querySelector("a");
    if (link) {
      link.style.pointerEvents = "none";
      link.style.opacity = "0.5";
      link.textContent = "Done ✓";
    }
  } else {
    card.style.borderColor = "var(--neutral-100)";
    card.style.background = "transparent";
    if (iconWrap) {
      iconWrap.style.background = "var(--neutral-100)";
      iconWrap.style.color = "var(--neutral-500)";
      iconWrap.innerHTML = `<i data-lucide="${originalIcon}" style="width:14px;height:14px;"></i>`;
    }
  }
}

let onboardingListenerBound = false;
async function setupOnboardingListeners(summary) {
  if (onboardingListenerBound) return;
  const btn = document.getElementById("obSetBudgetBtn");
  if (!btn) return;

  onboardingListenerBound = true;
  btn.addEventListener("click", async () => {
    const userId = localStorage.getItem("finadvisor_user_id") || "00000000-0000-0000-0000-000000000001";
    const token = localStorage.getItem("finadvisor_token");
    const limit = Number(document.getElementById("obBudgetInput").value) || 0;

    if (limit <= 0) {
      showToast("Please enter a valid budget limit", "warning");
      return;
    }

    try {
      const res = await fetch(`/api/v1/users/${userId}/budget`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "Authorization": `Bearer ${token}`
        },
        body: JSON.stringify({ monthly_limit: limit })
      });
      if (res.ok) {
        showToast("Budget set successfully", "success");
        await checkOnboardingStatus(summary);
      }
    } catch (e) {
      console.error(e);
      showToast("Failed to save budget", "error");
    }
  });
}

// --- Budget Progress Bar ---
async function loadBudgetProgress(userId) {
  const token = localStorage.getItem("finadvisor_token");
  if (!userId || !token) return;

  const widget = document.getElementById("budgetProgressWidget");
  if (!widget) return;

  try {
    const res = await fetch(`/api/v1/users/${userId}/budget`, {
      headers: { "Authorization": `Bearer ${token}` }
    });
    if (!res.ok) return;
    const data = await res.json();

    const limit = data.monthly_limit || 0;
    const spent = data.current_spent || 0;

    if (limit <= 0) {
      widget.classList.add("hidden");
      return;
    }

    // Show widget
    widget.classList.remove("hidden");

    const pct = Math.min((spent / limit) * 100, 100);

    // Format amounts
    const fmtSpent = `₹${Number(spent).toLocaleString("en-IN", { maximumFractionDigits: 0 })}`;
    const fmtLimit = `₹${Number(limit).toLocaleString("en-IN", { maximumFractionDigits: 0 })}`;

    document.getElementById("budgetSpent").textContent = fmtSpent;
    document.getElementById("budgetLimit").textContent = fmtLimit;
    document.getElementById("budgetPercentLabel").textContent = `${Math.round(pct)}% used`;

    // Color the fill bar
    const fill = document.getElementById("budgetFill");
    if (fill) {
      fill.style.width = `${pct}%`;
      if (pct < 60) {
        fill.style.background = "linear-gradient(90deg, #22c55e, #4ade80)";
      } else if (pct < 80) {
        fill.style.background = "linear-gradient(90deg, #f59e0b, #fbbf24)";
      } else {
        fill.style.background = "linear-gradient(90deg, #ef4444, #f87171)";
      }
    }

    // Overspend warning toast (once per session)
    if (pct >= 80 && !sessionStorage.getItem("finadvisor_budget_warned")) {
      sessionStorage.setItem("finadvisor_budget_warned", "1");
      const msg = pct >= 100
        ? `🚨 You've exceeded your monthly budget! (${Math.round(pct)}% used)`
        : `⚠️ You've used ${Math.round(pct)}% of your monthly budget!`;
      showToast(msg, pct >= 100 ? "error" : "warning");
    }

    if (window.lucide) lucide.createIcons();
  } catch (e) {
    console.error("Budget progress error:", e);
  }
}
