let allCards = [];
let allRecs = [];
let activeCalcCard = null;

document.addEventListener("DOMContentLoaded", async () => {
  if (window.lucide) lucide.createIcons();

  const userId = localStorage.getItem("finadvisor_user_id") || "00000000-0000-0000-0000-000000000001";

  try {
    const [cardsRes, txnRes, summaryRes] = await Promise.all([
      fetch(`/api/v1/cards/?user_id=${userId}`),
      fetch(`/api/v1/transactions/?user_id=${userId}&limit=100`),
      fetch(`/api/v1/dashboard/summary?user_id=${userId}`),
    ]);

    const cards = await cardsRes.json();
    allCards = cards;
    const txnData = await txnRes.json();
    const summary = await summaryRes.json();

    const transactions = Array.isArray(txnData) ? txnData : txnData.items || txnData.transactions || [];
    const recs = generateAllRecommendations(cards, transactions, summary);
    allRecs = recs;

    renderRecommendations(recs);
    renderScoreCard(summary, cards);
    initFilters(recs);
    setupCalcModalListeners();
  } catch (err) {
    console.error("Error loading recommendations:", err);
    const recsList = document.getElementById("recsList");
    if (recsList) {
      recsList.innerHTML = `
        <div class="glass-card rec-fallback">
          <i data-lucide="alert-circle" class="rec-fallback-icon"></i>
          <div class="rec-fallback-text">Unable to load recommendations</div>
        </div>`;
    }
    if (window.lucide) lucide.createIcons();
  }
});

function generateAllRecommendations(cards, transactions, summary) {
  const recs = [];
  const creditCards = cards.filter((c) => c.card_type === "credit" && c.is_active);

  creditCards.forEach((card) => {
    const util = card.credit_limit > 0 ? (card.current_balance / card.credit_limit) * 100 : 0;
    if (util > 80) {
      recs.push({
        id: `high-util-${card.id}`,
        category: "credit",
        impact: "high",
        icon: "alert-triangle",
        iconColor: "#EF4444",
        iconBg: "#FEF2F2",
        title: `Pay Down ${card.bank_name} Card (${util.toFixed(0)}% Utilization)`,
        subtitle: "High Impact · Credit Score",
        description: `Your ${card.bank_name} card ending ${card.card_last4} has ${util.toFixed(1)}% utilization which severely damages your CIBIL score. Cards above 80% utilization can drop your score by 50-100 points.`,
        action: "See Payment Plan",
        detail: `Target payment: Rs${formatNum((card.current_balance - card.credit_limit * 0.3).toFixed(0))} to reach 30% utilization. This could improve your CIBIL score by 30-50 points.`,
        cardId: card.id,
      });
    } else if (util > 30) {
      recs.push({
        id: `med-util-${card.id}`,
        category: "credit",
        impact: "medium",
        icon: "trending-down",
        iconColor: "#F59E0B",
        iconBg: "#FFF7ED",
        title: `Reduce ${card.bank_name} Utilization`,
        subtitle: "Medium Impact · Credit Score",
        description: `${card.bank_name} card at ${util.toFixed(1)}% utilization. Experts recommend keeping utilization below 30% for optimal credit score.`,
        action: "Calculate Target",
        detail: `Pay Rs${formatNum((card.current_balance - card.credit_limit * 0.3).toFixed(0))} to reach the ideal 30% threshold.`,
        cardId: card.id,
      });
    }
  });

  creditCards.forEach((card) => {
    if (!card.payment_due_date) return;
    const today = new Date();
    const due = new Date(today.getFullYear(), today.getMonth(), card.payment_due_date);
    if (due < today) due.setMonth(due.getMonth() + 1);
    const days = Math.ceil((due - today) / 86400000);

    if (days <= 7) {
      const minPay = Math.max(500, card.current_balance * 0.05);
      recs.push({
        id: `due-${card.id}`,
        category: "payment",
        impact: "high",
        icon: "clock",
        iconColor: "#EF4444",
        iconBg: "#FEF2F2",
        title: `${card.bank_name} Payment Due in ${days} Days`,
        subtitle: "High Impact · Avoid Late Fees",
        description: `Payment of minimum Rs${formatNum(minPay.toFixed(0))} or full balance Rs${formatNum(card.current_balance)} due on the ${card.payment_due_date}${getOrdinal(card.payment_due_date)}.`,
        action: "Set Reminder",
        detail: `Paying the full balance saves Rs${formatNum((card.current_balance * 0.03 * 30).toFixed(0))} in monthly interest charges.`,
      });
    }
  });



  const highInterestCards = creditCards.filter((c) => c.pending_emi_amount > 0 && c.emi_interest_rate > 14);
  if (highInterestCards.length > 0) {
    const totalEmi = highInterestCards.reduce((sum, c) => sum + Number(c.pending_emi_amount || 0), 0);
    const avgRate = highInterestCards.reduce((sum, c) => sum + Number(c.emi_interest_rate || 0), 0) / highInterestCards.length;

    recs.push({
      id: "balance-transfer",
      category: "savings",
      impact: "medium",
      icon: "refresh-cw",
      iconColor: "#7C3AED",
      iconBg: "#F5F3FF",
      title: "Consider Balance Transfer",
      subtitle: "Medium Impact · Save on Interest",
      description: `You have Rs${formatNum(totalEmi.toFixed(0))} in EMIs at ${avgRate.toFixed(1)}% average interest. Balance transfer to a 0% introductory offer could save significant money.`,
      action: "Compare Options",
      detail: `Estimated savings: Rs${formatNum((totalEmi * (avgRate - 4) / 100 / 12 * 6).toFixed(0))} over 6 months if you can secure a lower rate.`,
    });
  }

  const lowUtilCards = creditCards.filter((c) => {
    const util = c.credit_limit > 0 ? (c.current_balance / c.credit_limit) * 100 : 0;
    return util < 20 && c.credit_limit > 0;
  });
  if (lowUtilCards.length > 0) {
    recs.push({
      id: "limit-increase",
      category: "credit",
      impact: "low",
      icon: "arrow-up-circle",
      iconColor: "#10B981",
      iconBg: "#ECFDF5",
      title: "Request Credit Limit Increase",
      subtitle: "Low Impact · Improve Credit Profile",
      description: `${lowUtilCards.length} of your cards have under 20% utilization showing responsible usage. Requesting a limit increase can further improve your credit utilization ratio.`,
      action: "Learn More",
      detail: "A credit limit increase without increased spending lowers your utilization ratio and can improve your credit score.",
    });
  }

  const thisMonthSpend = summary.total_spent_this_month || 0;
  const lastMonthSpend = summary.total_spent_last_month || 0;
  if (thisMonthSpend > lastMonthSpend * 1.3 && lastMonthSpend > 0) {
    const increase = ((thisMonthSpend - lastMonthSpend) / lastMonthSpend * 100).toFixed(0);
    recs.push({
      id: "spending-alert",
      category: "spending",
      impact: "medium",
      icon: "trending-up",
      iconColor: "#F59E0B",
      iconBg: "#FFF7ED",
      title: `Spending Up ${increase}% This Month`,
      subtitle: "Medium Impact · Budget Control",
      description: `You've spent Rs${formatNum(thisMonthSpend)} this month vs Rs${formatNum(lastMonthSpend)} last month. Monitor spending to avoid overextending your credit.`,
      action: "View Breakdown",
      detail: "Click to see which categories increased and set spending limits.",
    });
  }



  return recs;
}

function renderRecommendations(recs) {
  const container = document.getElementById("recsList");
  if (!container) return;

  if (recs.length === 0) {
    container.innerHTML = `
      <div class="glass-card rec-fallback">
        <i data-lucide="check-circle" class="rec-fallback-icon rec-ok"></i>
        <div class="rec-fallback-title">Excellent Financial Health!</div>
        <div class="rec-fallback-text">No critical recommendations at this time.</div>
      </div>`;
    if (window.lucide) lucide.createIcons();
    return;
  }

  const impactOrder = { high: 0, medium: 1, low: 2 };
  recs.sort((a, b) => impactOrder[a.impact] - impactOrder[b.impact]);

  const impactColors = {
    high: { color: "#EF4444", bg: "#FEF2F2", label: "High Impact" },
    medium: { color: "#F59E0B", bg: "#FFF7ED", label: "Medium Impact" },
    low: { color: "#10B981", bg: "#ECFDF5", label: "Low Impact" },
  };

  container.innerHTML = recs
    .map((rec) => {
      const imp = impactColors[rec.impact];
      return `
      <div class="rec-item glass-card" data-impact="${rec.impact}">
        <div class="rec-item-icon" style="background:${rec.iconBg};">
          <i data-lucide="${rec.icon}" style="color:${rec.iconColor};"></i>
        </div>
        <div class="rec-item-content">
          <div class="rec-item-title-row">
            <span class="rec-item-title">${rec.title}</span>
            <span class="rec-item-pill" style="background:${imp.bg};color:${imp.color};border:1px solid ${imp.color}30;">${imp.label}</span>
          </div>
          <div class="rec-item-subtitle">${rec.subtitle}</div>
          <p class="rec-item-description">${rec.description}</p>
          <div class="rec-item-detail">💡 ${rec.detail}</div>
          <button class="rec-item-action" type="button" onclick="handleRecAction('${rec.id}')" style="background:${rec.iconColor};">
            ${rec.action}
            <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><path d="M5 12h14M12 5l7 7-7 7"/></svg>
          </button>
        </div>
      </div>`;
    })
    .join("");

  if (window.lucide) lucide.createIcons();
}

function renderScoreCard(summary, cards) {
  const score = summary.financial_health_score || 80;
  const scoreNum = document.getElementById("recScoreNum");
  const scoreLabel = document.getElementById("recScoreLabel");
  const scoreCircle = document.getElementById("scoreCircleFill");

  if (scoreNum) scoreNum.textContent = score;

  const labels = { 90: "Excellent", 70: "Good", 50: "Fair", 0: "Needs Work" };
  const label = Object.entries(labels).reverse().find(([threshold]) => score >= Number(threshold));
  if (scoreLabel && label) scoreLabel.textContent = label[1];

  if (scoreCircle) {
    const circumference = 251.2;
    const offset = circumference - (score / 100 * circumference);
    scoreCircle.style.strokeDashoffset = offset;
    scoreCircle.style.stroke = score >= 80 ? "#10B981" : score >= 60 ? "#F59E0B" : "#EF4444";
  }

  const factors = document.getElementById("recScoreFactors");
  if (factors) {
    const creditCards = cards.filter((c) => c.card_type === "credit" && c.is_active);
    const avgUtil = creditCards.length > 0
      ? creditCards.reduce((sum, c) => {
          const u = c.credit_limit > 0 ? (c.current_balance / c.credit_limit) * 100 : 0;
          return sum + u;
        }, 0) / creditCards.length
      : 0;

    const factorList = [
      { label: "Credit Utilization", score: avgUtil < 30 ? 30 : avgUtil < 60 ? 20 : 10, max: 30, color: avgUtil < 30 ? "#10B981" : "#F59E0B" },
      { label: "Payment History", score: 25, max: 25, color: "#10B981" },
      { label: "EMI Management", score: 25, max: 25, color: "#3B82F6" },
      { label: "Spending Pattern", score: 20, max: 20, color: "#7C3AED" },
    ];

    factors.innerHTML = factorList
      .map((f) => `
      <div class="rec-factor-item">
        <div class="rec-factor-row">
          <span class="rec-factor-label">${f.label}</span>
          <span class="rec-factor-score" style="color:${f.color};">${f.score}/${f.max}</span>
        </div>
        <div class="rec-factor-track"><div class="rec-factor-fill" style="background:${f.color};width:${(f.score / f.max) * 100}%;"></div></div>
      </div>
    `)
      .join("");
  }
}

function initFilters(recs) {
  document.getElementById("count-all").textContent = recs.length;
  document.getElementById("count-high").textContent = recs.filter((r) => r.impact === "high").length;
  document.getElementById("count-medium").textContent = recs.filter((r) => r.impact === "medium").length;
  document.getElementById("count-low").textContent = recs.filter((r) => r.impact === "low").length;

  document.querySelectorAll(".rec-filter-btn").forEach((btn) => {
    btn.addEventListener("click", () => {
      document.querySelectorAll(".rec-filter-btn").forEach((b) => b.classList.remove("active"));
      btn.classList.add("active");

      const filter = btn.dataset.filter;
      document.querySelectorAll(".rec-item").forEach((item) => {
        item.style.display = filter === "all" || item.dataset.impact === filter ? "flex" : "none";
      });
    });
  });
}

function handleRecAction(recId) {
  const rec = allRecs.find((r) => r.id === recId);
  if (!rec) return;

  if (rec.id.startsWith("med-util-") || rec.id.startsWith("high-util-")) {
    const card = allCards.find((c) => String(c.id).toLowerCase() === String(rec.cardId).toLowerCase());
    if (card) {
      openTargetCalcModal(card);
    }
  } else {
    if (window.showToast) {
      showToast(rec.action || "Opening...", "info");
    }
  }
}

function openTargetCalcModal(card) {
  activeCalcCard = card;
  const modal = document.getElementById("targetCalcModal");
  if (!modal) return;

  // Set card info
  document.getElementById("calcCardName").textContent = `${card.bank_name || "Card"} ••••${card.card_last4 || "0000"}`;
  
  const balance = Number(card.current_balance || 0);
  const limit = Number(card.credit_limit || 0);
  const util = limit > 0 ? (balance / limit) * 100 : 0;

  document.getElementById("calcCurrentBalance").textContent = `Rs${formatNum(balance.toFixed(0))}`;
  document.getElementById("calcCreditLimit").textContent = `Rs${formatNum(limit.toFixed(0))}`;
  
  const utilText = document.getElementById("calcCurrentUtil");
  utilText.textContent = `${util.toFixed(1)}%`;
  if (util < 30) {
    utilText.style.color = "#10b981";
  } else if (util < 60) {
    utilText.style.color = "#f59e0b";
  } else {
    utilText.style.color = "#ef4444";
  }

  // Reset inputs to default target 30%
  const slider = document.getElementById("calcTargetUtilSlider");
  const utilInput = document.getElementById("calcTargetUtilInput");
  const paymentInput = document.getElementById("calcPaymentInput");

  if (slider) slider.value = 30;
  if (utilInput) utilInput.value = 30;
  if (paymentInput) paymentInput.value = "";
  document.getElementById("calcTargetUtilVal").textContent = "30%";

  modal.classList.remove("hidden");
  modal.style.display = "block";
  if (window.lucide) lucide.createIcons();

  recalculateTarget("util", 30);
}

function recalculateTarget(source, value) {
  if (!activeCalcCard) return;

  const balance = Number(activeCalcCard.current_balance || 0);
  const limit = Number(activeCalcCard.credit_limit || 0);
  
  let paymentRequired = 0;
  let newUtil = 0;

  if (source === "util") {
    const targetUtil = value; // in %
    const targetBalance = limit * (targetUtil / 100);
    paymentRequired = Math.max(0, balance - targetBalance);
    newUtil = targetUtil;
  } else if (source === "payment") {
    const payment = value;
    paymentRequired = payment;
    const newBalance = Math.max(0, balance - payment);
    newUtil = limit > 0 ? (newBalance / limit) * 100 : 0;
  }

  // Update DOM results
  document.getElementById("calcPaymentRequired").textContent = `Rs${formatNum(paymentRequired.toFixed(0))}`;
  document.getElementById("calcNewUtil").textContent = `${newUtil.toFixed(1)}%`;

  const newUtilBar = document.getElementById("calcNewUtilBar");
  const newUtilText = document.getElementById("calcNewUtil");

  if (newUtilBar) {
    newUtilBar.style.width = `${Math.min(newUtil, 100)}%`;
    let color = "#10b981";
    if (newUtil >= 60) {
      color = "#ef4444";
    } else if (newUtil >= 30) {
      color = "#f59e0b";
    }
    newUtilBar.style.background = color;
    if (newUtilText) newUtilText.style.color = color;
  }

  // Generate dynamic insight
  let insightText = "";
  if (newUtil <= 30) {
    insightText = `Paying Rs ${formatNum(paymentRequired.toFixed(0))} to reach ${newUtil.toFixed(1)}% utilization keeps your credit ratio in the optimal zone (below 30%) and helps boost your credit score.`;
  } else if (newUtil <= 50) {
    insightText = `Paying Rs ${formatNum(paymentRequired.toFixed(0))} will bring your utilization down to ${newUtil.toFixed(1)}%. While better, try aiming for below 30% for a stronger boost to your credit score.`;
  } else if (newUtil < 80) {
    insightText = `Paying Rs ${formatNum(paymentRequired.toFixed(0))} reduces utilization to ${newUtil.toFixed(1)}%, but it remains elevated. Keeping utilization above 50% can trigger warning flags on your credit report.`;
  } else {
    insightText = `Your utilization remains critically high at ${newUtil.toFixed(1)}%. Utilization above 80% severely damages your credit score. Consider a larger payment to get below 50% or 30%.`;
  }

  const calcInsightText = document.getElementById("calcInsightText");
  if (calcInsightText) calcInsightText.textContent = insightText;
}

function setupCalcModalListeners() {
  const modal = document.getElementById("targetCalcModal");
  const closeBtn1 = document.getElementById("closeCalcModal");
  const closeBtn2 = document.getElementById("closeCalcModalBtn");
  const slider = document.getElementById("calcTargetUtilSlider");
  const paymentInput = document.getElementById("calcPaymentInput");
  const utilInput = document.getElementById("calcTargetUtilInput");

  if (!modal) return;

  const closeCalc = () => {
    modal.classList.add("hidden");
    modal.style.display = "none";
    activeCalcCard = null;
  };

  closeBtn1?.addEventListener("click", closeCalc);
  closeBtn2?.addEventListener("click", closeCalc);
  modal.querySelector(".modal-overlay")?.addEventListener("click", (e) => {
    if (e.target === e.currentTarget) closeCalc();
  });

  slider?.addEventListener("input", () => {
    if (!activeCalcCard) return;
    const val = parseInt(slider.value);
    document.getElementById("calcTargetUtilVal").textContent = `${val}%`;
    if (utilInput) utilInput.value = val;
    if (paymentInput) paymentInput.value = "";
    recalculateTarget("util", val);
  });

  utilInput?.addEventListener("input", () => {
    if (!activeCalcCard) return;
    let val = parseInt(utilInput.value);
    if (isNaN(val)) return;
    if (val < 5) val = 5;
    if (val > 100) val = 100;
    
    if (slider) slider.value = val;
    document.getElementById("calcTargetUtilVal").textContent = `${val}%`;
    if (paymentInput) paymentInput.value = "";
    recalculateTarget("util", val);
  });

  paymentInput?.addEventListener("input", () => {
    if (!activeCalcCard) return;
    let payVal = parseFloat(paymentInput.value);
    if (isNaN(payVal)) {
      const sliderVal = parseInt(slider?.value || "30");
      recalculateTarget("util", sliderVal);
      return;
    }
    if (payVal < 0) payVal = 0;
    
    if (utilInput) utilInput.value = "";
    recalculateTarget("payment", payVal);
  });
}

function formatNum(num) {
  return Number(num).toLocaleString("en-IN");
}

function getOrdinal(n) {
  const s = ["th", "st", "nd", "rd"];
  const v = n % 100;
  return s[(v - 20) % 10] || s[v] || s[0];
}
