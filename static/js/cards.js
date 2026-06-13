const cardsGrid = document.getElementById("cardsGrid");
const cardsEmpty = document.getElementById("cardsEmpty");
const cardModal = document.getElementById("cardModal");
const cardForm = document.getElementById("cardForm");
const modalTitle = document.getElementById("modalTitle");
const cardSubmitBtn = document.getElementById("cardSubmitBtn");
const modalCardPreview = document.getElementById("modalCardPreview");
const askCardBtn = document.getElementById("askCardBtn");
const cardChatbotModal = document.getElementById("cardChatbotModal");
const cardChatbotTitle = document.getElementById("cardChatbotTitle");
const cardChatMessages = document.getElementById("cardChatMessages");
const cardChatInput = document.getElementById("cardChatInput");
const cardChatSend = document.getElementById("cardChatSend");
const cardChatbotClose = document.getElementById("cardChatbotClose");
const cardChatSuggestions = document.getElementById("cardChatSuggestions");
const cardChatClear = document.getElementById("cardChatClear");

let allCards = [];
let activeFilter = "all";
let openCardId = null;
let cardChatSessionId = null;
let cardChatSessions = {};
let cardChatLoading = false;
let cardChatActiveCardId = null;
let cardChatActiveLabel = "";
let cardChatEntityLabel = "";
let cardChatActiveCard = null;
const cardChatHistory = {};
let activeCalcCard = null;

function formatMoney(value) {
  return Number(value || 0).toLocaleString("en-IN", { maximumFractionDigits: 2 });
}

function getThemeClass(card) {
  const explicit = String(card.color_theme || "").toLowerCase();
  if (explicit) {
    if (["hdfc", "icici", "axis", "sbi", "kotak", "yes", "indusind", "idfc", "default"].includes(explicit)) {
      return `card-theme-${explicit}`;
    }
  }

  const bank = String(card.bank_name || "").toLowerCase();
  if (bank.includes("hdfc")) return "card-theme-hdfc";
  if (bank.includes("icici")) return "card-theme-icici";
  if (bank.includes("axis")) return "card-theme-axis";
  if (bank.includes("sbi")) return "card-theme-sbi";
  if (bank.includes("kotak")) return "card-theme-kotak";
  if (bank.includes("yes")) return "card-theme-yes";
  if (bank.includes("indus")) return "card-theme-indusind";
  if (bank.includes("idfc")) return "card-theme-idfc";
  return "card-theme-default";
}

function renderNetworkLogo(network) {
  const value = String(network || "other").toLowerCase();
  if (value === "visa") {
    return '<span class="logo-visa">VISA</span>';
  }
  if (value === "mastercard") {
    return `
      <div class="logo-mastercard">
        <span class="mc-left"></span>
        <span class="mc-right"></span>
      </div>
    `;
  }
  if (value === "rupay") {
    return '<span class="logo-rupay">RuPay</span>';
  }
  if (value === "amex") {
    return '<span class="logo-amex">AMEX</span>';
  }
  return '<span class="logo-generic">CARD</span>';
}

function nfcIcon() {
  return `
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round">
      <path d="M4 9c2.5 0 4.5 2 4.5 4.5"/>
      <path d="M4 5c4.7 0 8.5 3.8 8.5 8.5"/>
      <path d="M4 1c6.9 0 12.5 5.6 12.5 12.5"/>
    </svg>
  `;
}

function flipIcon() {
  return `
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round">
      <path d="M3 12a9 9 0 0 1 15.5-6.4"/>
      <path d="M21 12a9 9 0 0 1-15.5 6.4"/>
      <path d="M18 2v4h-4"/>
      <path d="M6 22v-4h4"/>
    </svg>
  `;
}

function buildCardHtml(card) {
  const utilPctRaw = card.credit_limit > 0 ? ((card.current_balance || 0) / card.credit_limit) * 100 : 0;
  const utilPct = Math.max(0, Math.min(100, Number(utilPctRaw.toFixed(1))));
  const utilColor = utilPct < 30 ? "#10B981" : utilPct < 60 ? "#F59E0B" : "#EF4444";
  const available = (Number(card.credit_limit) || 0) - (Number(card.current_balance) || 0);
  const pendingToLimit = Math.max(0, (Number(card.credit_limit) || 0) - ((Number(card.current_balance) || 0) + (Number(card.pending_emi_amount) || 0)));

  return `
    <div class="card-item-wrapper ${card.is_active === false ? 'deactivated-card' : ''}" id="card-wrapper-${card.id}">
      <div class="card-flip-container" id="card-${card.id}">
        <div class="card-flipper" id="flipper-${card.id}">
          <div class="card-face bank-card card-front ${getThemeClass(card)}">
            <div class="card-holographic"></div>
            <span class="card-bank-name">${card.bank_name || "BANK"}</span>
            <div class="card-network-logo">${renderNetworkLogo(card.card_network)}</div>
            <div class="card-chip">
              <span></span><span></span><span></span><span></span><span></span>
            </div>
            <div class="card-nfc">${nfcIcon()}</div>
            <div class="card-number">•••• •••• •••• ${card.card_last4 || "0000"}</div>
            <div class="card-bottom">
              <div class="card-holder-info">
                <span class="card-label">CARD HOLDER</span>
                <span class="card-name">${(card.card_holder_name || "CARD HOLDER").toUpperCase()}</span>
              </div>
              <div class="card-expiry-info">
                <span class="card-label">VALID THRU</span>
                <span class="card-expiry">${String(card.expiry_month || 0).padStart(2, "0")}/${String(card.expiry_year || "").slice(-2) || "--"}</span>
              </div>
              <div class="card-type-badge">${card.card_type || "credit"}</div>
            </div>
            <div class="flip-hint" title="Click to flip">${flipIcon()}</div>
          </div>

          <div class="card-face bank-card card-back ${getThemeClass(card)}">
            <div class="card-magnetic-stripe"></div>
            <div class="card-back-content">
              <div class="back-metric"><span class="back-label">CREDIT LIMIT</span><span class="back-value">Rs${formatMoney(card.credit_limit)}</span></div>
              <div class="back-metric"><span class="back-label">CURRENT BALANCE</span><span class="back-value">Rs${formatMoney(card.current_balance)}</span></div>
              <div class="back-metric"><span class="back-label">AVAILABLE</span><span class="back-value available">Rs${formatMoney(available)}</span></div>
              <div class="back-utilization">
                <div class="util-bar-container"><div class="util-bar-fill" style="width:${utilPct}%;background:${utilColor}"></div></div>
                <span class="util-label">${utilPct}% used</span>
              </div>
              <div class="back-metric"><span class="back-label">PENDING TO LIMIT</span><span class="back-value">Rs${formatMoney(pendingToLimit)}</span></div>
              <div class="card-signature-strip">
                <div class="signature-lines"></div>
                <div class="cvv-box"><span class="cvv-label">CVV</span><span class="cvv-value">•••</span></div>
              </div>
            </div>
            <div class="flip-hint" title="Click to flip back">${flipIcon()}</div>
          </div>
        </div>
      </div>

      <div class="card-controls card-actions-overlay">
        <button class="btn-view-details view-details-btn" data-card-id="${card.id}" type="button" onclick="viewCardDetails('${card.id}')">View Details ▾</button>
        <button class="btn-card-action edit" type="button" onclick="openEditCard('${card.id}')" title="Edit">
          <i data-lucide="edit-2"></i>
        </button>
        ${card.is_active !== false ? `
          <button class="btn-card-action deactivate" type="button" onclick="deactivateCard('${card.id}')" title="Deactivate">
            <i data-lucide="pause-circle"></i>
          </button>
        ` : `
          <button class="btn-card-action reactivate" type="button" onclick="reactivateCard('${card.id}')" title="Reactivate">
            <i data-lucide="play-circle"></i>
          </button>
        `}
        <button class="btn-card-action delete" type="button" onclick="confirmDeleteCard('${card.id}')" title="Delete">
          <i data-lucide="trash-2"></i>
        </button>
      </div>
    </div>
  `;
}

function updateCardsEmptyState() {
  const wrappers = cardsGrid ? cardsGrid.querySelectorAll(".card-item-wrapper") : [];
  if (cardsEmpty) {
    cardsEmpty.style.display = wrappers.length === 0 ? "block" : "none";
  }
}

function filteredCards() {
  if (activeFilter === "all") return allCards;
  if (activeFilter === "active") return allCards.filter((c) => Boolean(c.is_active));
  if (activeFilter === "inactive") return allCards.filter((c) => !Boolean(c.is_active));
  return allCards.filter((c) => String(c.card_type).toLowerCase() === activeFilter);
}

function renderCards() {
  if (!cardsGrid) return;

  const cards = filteredCards();
  cardsGrid.innerHTML = cards.map((card) => buildCardHtml(card)).join("");

  initCardFlip();
  updateCardsEmptyState();

  if (window.lucide) {
    lucide.createIcons();
  }
}

async function fetchCards() {
  const userId = localStorage.getItem("finadvisor_user_id") || "00000000-0000-0000-0000-000000000001";
  const res = await fetch(`/api/v1/cards/?user_id=${userId}`);
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || "Failed to fetch cards");
  }
  allCards = await res.json();
  renderCards();
}

function initCardFlip() {
  document.querySelectorAll(".card-flip-container").forEach((container) => {
    container.addEventListener("click", function (e) {
      if (e.target.closest(".card-actions-overlay")) return;
      const flipper = this.querySelector(".card-flipper");
      if (flipper) flipper.classList.toggle("flipped");
    });
  });
}

function formatNumber(num) {
  return Number.parseFloat(num || 0).toLocaleString("en-IN");
}

function formatCardEntityLabel(card) {
  const type = String(card.card_type || "credit").toLowerCase() === "debit" ? "Debit" : "Credit";
  return `${card.bank_name || "Card"} ${type}`;
}

function formatCardUiLabel(card) {
  return `${card.bank_name || "Card"} ••••${card.card_last4 || "0000"}`;
}

function cardChatHistoryKey(cardId) {
  return `finadvisor_card_chat_history_${cardId}`;
}

function loadCardChatHistory(cardId) {
  try {
    const raw = localStorage.getItem(cardChatHistoryKey(cardId));
    const parsed = raw ? JSON.parse(raw) : [];
    return Array.isArray(parsed) ? parsed : [];
  } catch {
    return [];
  }
}

function persistCardChatHistory(cardId) {
  try {
    localStorage.setItem(cardChatHistoryKey(cardId), JSON.stringify(cardChatHistory[cardId] || []));
  } catch {
    return;
  }
}

function openCardChatbot(card) {
  if (!cardChatbotModal) return;
  cardChatActiveCardId = card.id;
  cardChatActiveCard = card;
  cardChatActiveLabel = formatCardUiLabel(card);
  cardChatEntityLabel = formatCardEntityLabel(card);
  cardChatSessionId = cardChatSessions[card.id] || null;
  cardChatHistory[card.id] = loadCardChatHistory(card.id);

  cardChatbotTitle.textContent = `AI Assistant - ${cardChatActiveLabel}`;
  cardChatbotModal.classList.add("open");
  cardChatbotModal.setAttribute("aria-hidden", "false");

  renderCardChatMessages();
  renderCardChatSuggestions();
  initCardChatSession();

  if (cardChatInput) cardChatInput.focus();
  if (window.lucide) lucide.createIcons();
}

function closeCardChatbot() {
  if (!cardChatbotModal) return;
  cardChatbotModal.classList.remove("open");
  cardChatbotModal.setAttribute("aria-hidden", "true");
}

function clearCardChatHistory(cardId) {
  if (!cardId) return;
  try {
    localStorage.removeItem(cardChatHistoryKey(cardId));
    cardChatHistory[cardId] = [];
  } catch {
    return;
  }
}

function getCardChatHistory(cardId) {
  if (!cardChatHistory[cardId]) {
    cardChatHistory[cardId] = loadCardChatHistory(cardId);
  }
  return cardChatHistory[cardId];
}

function renderCardChatMessages() {
  if (!cardChatMessages || !cardChatActiveCardId) return;
  const history = getCardChatHistory(cardChatActiveCardId);
  cardChatMessages.innerHTML = "";

  if (!history.length) {
    appendCardChatMessage("bot", `Ask me anything about ${cardChatActiveLabel}.`);
    return;
  }

  history.forEach((item) => appendCardChatMessage(item.role, item.text, false));
  scrollCardChatToBottom();
}

function buildCardInsightBlock(titleText, items) {
  const block = document.createElement("div");
  block.className = "chatbot-insight-block";

  const title = document.createElement("div");
  title.className = "chatbot-insight-title";
  title.textContent = titleText;
  block.appendChild(title);

  const grid = document.createElement("div");
  grid.className = "chatbot-insight-grid";

  items.forEach((item) => {
    const card = document.createElement("div");
    card.className = `chatbot-insight-card tone-${item.tone || "neutral"}`;

    const label = document.createElement("div");
    label.className = "chatbot-insight-label";
    label.textContent = item.title || "Insight";

    card.appendChild(label);

    if (item.value) {
      const value = document.createElement("div");
      value.className = "chatbot-insight-value";
      value.textContent = item.value;
      card.appendChild(value);
    }

    if (item.detail) {
      const detail = document.createElement("div");
      detail.className = "chatbot-insight-detail";
      detail.textContent = item.detail;
      card.appendChild(detail);
    }

    grid.appendChild(card);
  });

  block.appendChild(grid);
  return block;
}

function appendCardChatMessage(role, text, store = true, meta = null) {
  if (!cardChatMessages) return;

  const row = document.createElement("div");
  row.className = `chatbot-row ${role === "user" ? "user" : "bot"}`;

  if (role !== "user") {
    const avatar = document.createElement("div");
    avatar.className = "chatbot-mini-avatar";
    avatar.innerHTML = '<i data-lucide="bot"></i>';
    row.appendChild(avatar);
  }

  const bubble = document.createElement("div");
  bubble.className = `chatbot-bubble ${role === "user" ? "user" : "bot"}`;
  bubble.innerHTML = String(text || "").replace(/\n/g, "<br>");

  if (role === "user") {
    row.appendChild(bubble);
  } else {
    const wrap = document.createElement("div");
    wrap.className = "chatbot-bubble-wrap";
    wrap.appendChild(bubble);

    if (meta && Array.isArray(meta.insights) && meta.insights.length) {
      wrap.appendChild(buildCardInsightBlock("Card insights", meta.insights));
    }

    if (meta && Array.isArray(meta.recommendations) && meta.recommendations.length) {
      wrap.appendChild(buildCardInsightBlock("Recommendations", meta.recommendations));
    }
    row.appendChild(wrap);
  }

  cardChatMessages.appendChild(row);

  if (store && cardChatActiveCardId) {
    getCardChatHistory(cardChatActiveCardId).push({ role, text });
    persistCardChatHistory(cardChatActiveCardId);
  }

  if (window.lucide) lucide.createIcons();
  scrollCardChatToBottom();
}

function showCardChatTyping() {
  if (!cardChatMessages || document.getElementById("cardChatTyping")) return;
  const row = document.createElement("div");
  row.className = "chatbot-row bot";
  row.id = "cardChatTyping";

  const avatar = document.createElement("div");
  avatar.className = "chatbot-mini-avatar";
  avatar.innerHTML = '<i data-lucide="bot"></i>';

  const bubble = document.createElement("div");
  bubble.className = "chatbot-bubble bot typing";
  bubble.innerHTML = '<span class="typing-dot"></span><span class="typing-dot"></span><span class="typing-dot"></span>';

  row.appendChild(avatar);
  row.appendChild(bubble);
  cardChatMessages.appendChild(row);
  if (window.lucide) lucide.createIcons();
  scrollCardChatToBottom();
}

function hideCardChatTyping() {
  const node = document.getElementById("cardChatTyping");
  if (node) node.remove();
}

function scrollCardChatToBottom() {
  if (!cardChatMessages) return;
  cardChatMessages.scrollTop = cardChatMessages.scrollHeight;
}

function renderCardChatSuggestions() {
  if (!cardChatSuggestions) return;
  const suggestions = [
    "Can I spend Rs 5000 on this card?",
    "How much can I spend from this card?",
    "What is the outstanding balance on this card?",
    "When is the payment due for this card?",
    "What is my credit utilization on this card?",
    "How much have I spent using this card this month?",
    "How much EMI is remaining on this card?",
  ];
  cardChatSuggestions.innerHTML = suggestions
    .map((label) => `<button type="button" data-suggest="${label}">${label}</button>`)
    .join("");

  cardChatSuggestions.querySelectorAll("button").forEach((btn) => {
    btn.addEventListener("click", () => {
      btn.classList.add("active");
      setTimeout(() => btn.classList.remove("active"), 200);
      sendCardChatQuestion(btn.dataset.suggest || "");
    });
  });
}

function normalizeCardQuestion(text) {
  const value = String(text || "").trim();
  const lower = value.toLowerCase();

  if (/can i spend|should i spend|is it safe to spend|is it okay to spend|can i buy|should i buy/.test(lower)) {
    return value;
  }

  if (/due amount|minimum payment|min pay|minimum due/.test(lower)) {
    return `What is the minimum payment due on my ${cardChatEntityLabel} card?`;
  }
  if (/payment due|when is|due date|bill due|due on/.test(lower)) {
    return `When is the payment due for my ${cardChatEntityLabel} card?`;
  }
  if (/credit left|available credit|spend from this card|how much can i spend|limit left/.test(lower)) {
    return `How much can I spend from my ${cardChatEntityLabel} card?`;
  }
  if (/outstanding balance|owed balance|balance due|how much do i owe/.test(lower)) {
    return `What is the outstanding balance on my ${cardChatEntityLabel} card?`;
  }
  if (/utilization/.test(lower)) {
    return `What is my credit utilization on my ${cardChatEntityLabel} card?`;
  }
  if (/spent this month|monthly spend|this month/.test(lower)) {
    return `How much have I spent using my ${cardChatEntityLabel} card this month?`;
  }
  if (/emi pending|pending emi|emi remaining|emi left|installment left/.test(lower)) {
    return `How much EMI is remaining on my ${cardChatEntityLabel} card?`;
  }

  return `${value} for ${cardChatEntityLabel}`;
}

async function initCardChatSession() {
  if (cardChatSessionId) return cardChatSessionId;
  const userId = localStorage.getItem("finadvisor_user_id") || "00000000-0000-0000-0000-000000000001";
  try {
    const res = await fetch(`/api/v1/chatbot/welcome/${userId}`, {
      headers: { "X-User-Id": userId },
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || "Unable to initialize chatbot");
    cardChatSessionId = data.session_id;
    if (cardChatActiveCardId) {
      cardChatSessions[cardChatActiveCardId] = cardChatSessionId;
    }
    return cardChatSessionId;
  } catch (error) {
    appendCardChatMessage("bot", "I could not load the AI assistant right now.");
    return null;
  }
}

async function sendCardChatQuestion(text) {
  if (!text || cardChatLoading) return;
  if (!cardChatSessionId) {
    const session = await initCardChatSession();
    if (!session) return;
  }
  if (!cardChatActiveCardId) {
    showToast("Open card details first", "info");
    return;
  }
  cardChatLoading = true;

  const userId = localStorage.getItem("finadvisor_user_id") || "00000000-0000-0000-0000-000000000001";
  const enriched = normalizeCardQuestion(text);

  appendCardChatMessage("user", text);
  showCardChatTyping();

  try {
    const res = await fetch("/api/v1/chatbot/ask-card", {
      method: "POST",
      headers: { "Content-Type": "application/json", "X-User-Id": userId },
      body: JSON.stringify({
        session_id: cardChatSessionId,
        user_id: userId,
        card_id: cardChatActiveCardId,
        typed_text: enriched,
      }),
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || "Unable to fetch answer");

    hideCardChatTyping();
    if (data.no_match) {
      appendCardChatMessage("bot", data.message || "I did not understand that question.");
    } else if (data.needs_clarification) {
      appendCardChatMessage("bot", data.message || "Please clarify your question.");
    } else {
      appendCardChatMessage("bot", data.answer || "I could not find an answer for that.", true, data.data || null);
    }
  } catch (error) {
    hideCardChatTyping();
    appendCardChatMessage("bot", "Something went wrong while getting that answer.");
  } finally {
    cardChatLoading = false;
  }
}

async function renderCardTransactions(card) {
  const tbody = document.getElementById("detail-transactions-body");
  if (!tbody) return;
  tbody.innerHTML = '<tr><td colspan="5" class="emi-placeholder">Loading transactions...</td></tr>';

  const userId = localStorage.getItem("finadvisor_user_id") || "00000000-0000-0000-0000-000000000001";
  try {
    const res = await fetch(`/api/v1/transactions/?user_id=${userId}&card_id=${card.id}&limit=6`);
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || "Failed to load transactions");

    if (!data.length) {
      tbody.innerHTML = '<tr><td colspan="5" class="emi-placeholder">No transactions for this card yet</td></tr>';
      return;
    }

    tbody.innerHTML = data
      .map((txn) => {
        const amount = Number(txn.amount || 0);
        const signed = txn.transaction_type === "debit" ? `-Rs${formatNumber(amount)}` : `+Rs${formatNumber(amount)}`;
        const amountClass = txn.transaction_type === "debit" ? "amount-debit" : "amount-credit";
        return `
          <tr>
            <td>${new Date(txn.transaction_date).toLocaleDateString("en-IN")}</td>
            <td>${txn.description || txn.merchant_name || "-"}</td>
            <td><span class="badge">${txn.transaction_type || "-"}</span></td>
            <td class="${amountClass}">${signed}</td>
            <td>${txn.balance_after ? `Rs${formatNumber(txn.balance_after)}` : "-"}</td>
          </tr>
        `;
      })
      .join("");
  } catch (error) {
    tbody.innerHTML = '<tr><td colspan="5" class="emi-placeholder">Unable to load transactions</td></tr>';
  }
}

function viewCardDetails(cardId, cardData = null) {
  const panel = document.getElementById("cardDetailsPanel");
  if (!panel) return;

  if (openCardId === cardId && panel.classList.contains("visible")) {
    closeCardDetails();
    return;
  }

  openCardId = cardId;

  document.querySelectorAll(".view-details-btn").forEach((btn) => btn.classList.remove("active"));
  document.querySelector(`.view-details-btn[data-card-id="${cardId}"]`)?.classList.add("active");

  const sourceCard = cardData || allCards.find((item) => String(item.id).toLowerCase() === String(cardId).toLowerCase());
  if (!sourceCard) {
    console.error(`Card details not found for cardId: ${cardId}. Available cards:`, allCards.map(c => c.id));
    showToast("Card details not found", "error");
    return;
  }

  populateCardDetailsPanel(sourceCard);

  panel.style.display = "block";
  panel.classList.add("visible");

  if (window.lucide) {
    lucide.createIcons();
  }

  setTimeout(() => {
    const wrapper = document.querySelector(
      '.card-details-panel-wrapper'
    );
    if (wrapper) {
      wrapper.scrollIntoView({ 
        behavior: 'smooth', 
        block: 'start' 
      });
    }
  }, 50);
}

function closeCardDetails() {
  const panel = document.getElementById("cardDetailsPanel");
  if (!panel) return;

  panel.classList.remove("visible");
  panel.style.display = "none";
  openCardId = null;

  document.querySelectorAll(".view-details-btn").forEach((btn) => btn.classList.remove("active"));
}

function populateCardDetailsPanel(card) {
  const creditLimit = Number(card.credit_limit || 0);
  const outstanding = Number(card.current_balance || 0);
  const available = card.available_balance !== null && card.available_balance !== undefined
    ? Number(card.available_balance || 0)
    : Math.max(0, creditLimit - outstanding);

  document.getElementById("detail-credit-limit").textContent = `Rs${formatNumber(creditLimit)}`;
  document.getElementById("detail-outstanding").textContent = `Rs${formatNumber(outstanding)}`;
  document.getElementById("detail-available").textContent = `Rs${formatNumber(available)}`;

  const utilization = creditLimit > 0 ? Number(((outstanding / creditLimit) * 100).toFixed(1)) : 0;
  document.getElementById("detail-utilization").textContent = `${utilization}%`;

  const utilEl = document.getElementById("detail-utilization");
  const barFill = document.getElementById("detail-util-bar");
  if (utilization < 30) {
    utilEl.style.color = "#10B981";
    barFill.style.background = "#10B981";
  } else if (utilization < 60) {
    utilEl.style.color = "#F59E0B";
    barFill.style.background = "#F59E0B";
  } else {
    utilEl.style.color = "#EF4444";
    barFill.style.background = "#EF4444";
  }
  barFill.style.width = `${Math.min(utilization, 100)}%`;

  const minPayment = Math.max(500, outstanding * 0.05);
  document.getElementById("detail-min-payment").textContent = `Rs${formatNumber(minPayment)}`;

  document.getElementById("detail-due-date").textContent = card.payment_due_date ? `${card.payment_due_date} of month` : "N/A";

  const daysEl = document.getElementById("detail-days-due");
  if (card.payment_due_date) {
    const today = new Date();
    const dueDate = new Date(today.getFullYear(), today.getMonth(), Number(card.payment_due_date));
    if (dueDate < today) dueDate.setMonth(dueDate.getMonth() + 1);

    const days = Math.ceil((dueDate - today) / (1000 * 60 * 60 * 24));
    daysEl.textContent = `${days} days`;
    daysEl.style.color = days < 7 ? "#EF4444" : days < 15 ? "#F59E0B" : "#10B981";
  } else {
    daysEl.textContent = "N/A";
    daysEl.style.color = "#64748B";
  }

  document.getElementById("detail-monthly-emi").textContent = card.monthly_emi_amount ? `Rs${formatNumber(card.monthly_emi_amount)}` : "Rs0";
  document.getElementById("detail-pending-emi").textContent = card.pending_emi_amount ? `Rs${formatNumber(card.pending_emi_amount)}` : "Rs0";
  document.getElementById("detail-tenure").textContent = card.emi_tenure_months ? `${card.emi_tenure_months} months` : "N/A";
  document.getElementById("detail-annual-rate").textContent = card.emi_interest_rate ? `${card.emi_interest_rate}%` : "N/A";

  const monthlyRate = card.emi_interest_rate ? (Number(card.emi_interest_rate) / 12).toFixed(2) : "0.00";
  document.getElementById("detail-monthly-rate").textContent = `${monthlyRate}%`;

  const totalInterest = card.monthly_emi_amount && card.emi_tenure_months
    ? (Number(card.monthly_emi_amount) * Number(card.emi_tenure_months)) - Number(card.pending_emi_amount || 0)
    : 0;
  document.getElementById("detail-total-interest").textContent = `Rs${formatNumber(Math.abs(totalInterest))}`;

  renderEmiSchedule(card.pending_emi_amount, card.emi_interest_rate, card.emi_tenure_months);
  document.getElementById("detail-card-name").textContent = `${card.bank_name || "Card"} ••••${card.card_last4 || "0000"}`;
  if (askCardBtn) {
    askCardBtn.dataset.cardId = card.id;
  }
  generateCardRecommendations(card);
  renderCardTransactions(card);
}

function getDaysUntilDue(dueDateDay) {
  if (!dueDateDay) return null;
  const today = new Date();
  const dueDate = new Date(today.getFullYear(), today.getMonth(), Number(dueDateDay));
  if (dueDate < today) {
    dueDate.setMonth(dueDate.getMonth() + 1);
  }
  return Math.ceil((dueDate - today) / (1000 * 60 * 60 * 24));
}

function handleRecAction(actionType) {
  console.log(`handleRecAction: type=${actionType}, openCardId=${openCardId}`);
  if (actionType === "utilization_target" || actionType === "payment_plan") {
    const card = allCards.find((c) => String(c.id).toLowerCase() === String(openCardId).toLowerCase());
    if (card) {
      openTargetCalcModal(card);
      return;
    } else {
      console.warn(`Card not found for openCardId: ${openCardId} in handleRecAction`);
    }
  }

  const messages = {
    payment_plan: "Opening payment plan calculator...",
    utilization_target: "Calculating utilization target...",
    reminder: "Payment reminder set!",
    balance_transfer: "Opening balance transfer comparison...",
    autopay: "Auto-pay setup guide loading...",
    limit_increase: "Opening credit limit increase guide...",
    rewards: "Opening rewards optimization guide...",
  };
  showToast(messages[actionType] || "Opening...", "info");
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

  document.getElementById("calcCurrentBalance").textContent = `Rs${formatNumber(balance.toFixed(0))}`;
  document.getElementById("calcCreditLimit").textContent = `Rs${formatNumber(limit.toFixed(0))}`;
  
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
  document.getElementById("calcPaymentRequired").textContent = `Rs${formatNumber(paymentRequired.toFixed(0))}`;
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
    insightText = `Paying Rs ${formatNumber(paymentRequired.toFixed(0))} to reach ${newUtil.toFixed(1)}% utilization keeps your credit ratio in the optimal zone (below 30%) and helps boost your credit score.`;
  } else if (newUtil <= 50) {
    insightText = `Paying Rs ${formatNumber(paymentRequired.toFixed(0))} will bring your utilization down to ${newUtil.toFixed(1)}%. While better, try aiming for below 30% for a stronger boost to your credit score.`;
  } else if (newUtil < 80) {
    insightText = `Paying Rs ${formatNumber(paymentRequired.toFixed(0))} reduces utilization to ${newUtil.toFixed(1)}%, but it remains elevated. Keeping utilization above 50% can trigger warning flags on your credit report.`;
  } else {
    insightText = `Your utilization remains critically high at ${newUtil.toFixed(1)}%. Utilization above 80% damages your credit score. Consider a larger payment to get below 50% or 30%.`;
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

function generateCardRecommendations(card) {
  const container = document.getElementById("card-recommendations-list");
  if (!container) return;

  const recs = [];
  const utilization = card.credit_limit > 0 ? (card.current_balance / card.credit_limit) * 100 : 0;
  const daysUntilDue = getDaysUntilDue(card.payment_due_date);
  const minPayment = Math.max(500, Number(card.current_balance || 0) * 0.05);

  if (utilization > 80) {
    recs.push({
      icon: "alert-triangle",
      impact: "high",
      impactColor: "#EF4444",
      impactBg: "#FEF2F2",
      title: "Critical: Pay Down Balance Now",
      description: `Your utilization is ${utilization.toFixed(1)}% which severely impacts your CIBIL score. Pay at least Rs${formatNumber((card.current_balance * 0.3).toFixed(0))} to bring it below 50%.`,
      action: "See Payment Plan",
      actionType: "payment_plan",
    });
  } else if (utilization > 30) {
    recs.push({
      icon: "trending-down",
      impact: "medium",
      impactColor: "#F59E0B",
      impactBg: "#FFF7ED",
      title: "Reduce Credit Utilization",
      description: `Utilization at ${utilization.toFixed(1)}%. Keeping it below 30% improves your credit score significantly. Target: Rs${formatNumber((card.credit_limit * 0.3).toFixed(0))} or less.`,
      action: "Calculate Target",
      actionType: "utilization_target",
    });
  }

  if (daysUntilDue !== null && daysUntilDue <= 7) {
    recs.push({
      icon: "clock",
      impact: "high",
      impactColor: "#EF4444",
      impactBg: "#FEF2F2",
      title: `Payment Due in ${daysUntilDue} Days`,
      description: `Minimum payment of Rs${formatNumber(minPayment.toFixed(0))} is due. Pay full balance Rs${formatNumber(card.current_balance)} to avoid interest charges of Rs${formatNumber((card.current_balance * 0.02).toFixed(0))}/month.`,
      action: "Set Reminder",
      actionType: "reminder",
    });
  }

  if (Number(card.pending_emi_amount || 0) > 0 && Number(card.emi_interest_rate || 0) > 12) {
    recs.push({
      icon: "refresh-cw",
      impact: "medium",
      impactColor: "#F59E0B",
      impactBg: "#FFF7ED",
      title: "Consider Balance Transfer",
      description: `You're paying ${card.emi_interest_rate}% interest on Rs${formatNumber(card.pending_emi_amount)}. A balance transfer to a 0% introductory offer could save you Rs${formatNumber((card.pending_emi_amount * card.emi_interest_rate / 100 / 12 * card.emi_tenure_months * 0.4).toFixed(0))}.`,
      action: "Compare Options",
      actionType: "balance_transfer",
    });
  }



  if (recs.length === 0) {
    container.innerHTML = `
      <div class="rec-empty-state">
        <i data-lucide="check-circle" class="rec-empty-icon"></i>
        <div class="rec-empty-title">Great job! No issues found.</div>
        <div class="rec-empty-subtitle">This card is being managed well.</div>
      </div>`;
    if (window.lucide) lucide.createIcons();
    return;
  }

  container.innerHTML = recs.map((rec) => `
    <div class="rec-card" style="background:${rec.impactBg};border:1px solid ${rec.impactColor}22;">
      <div class="rec-icon-wrap" style="background:${rec.impactColor}18;">
        <i data-lucide="${rec.icon}" style="color:${rec.impactColor};"></i>
      </div>
      <div class="rec-content">
        <div class="rec-title-row">
          <span class="rec-title">${rec.title}</span>
          <span class="rec-impact" style="background:${rec.impactColor}20;color:${rec.impactColor};">${rec.impact} impact</span>
        </div>
        <p class="rec-description">${rec.description}</p>
        ${rec.action ? `<button class="rec-action-btn" type="button" onclick="handleRecAction('${rec.actionType}')" style="background:${rec.impactColor};">${rec.action} →</button>` : ''}
      </div>
    </div>
  `).join("");

  if (window.lucide) lucide.createIcons();
}

function renderEmiSchedule(principal, annualRate, tenure) {
  const tbody = document.getElementById("emi-schedule-body");
  if (!tbody) return;
  tbody.innerHTML = "";

  const p = Number(principal || 0);
  const r = Number(annualRate || 0);
  const t = Number(tenure || 0);

  if (!p || !r || !t) {
    tbody.innerHTML = '<tr><td colspan="5" class="emi-placeholder">No EMI data</td></tr>';
    return;
  }

  const monthlyRate = r / 12 / 100;
  const emi = p * monthlyRate * Math.pow(1 + monthlyRate, t) / (Math.pow(1 + monthlyRate, t) - 1);

  let balance = p;
  const months = Math.min(t, 3);

  for (let i = 1; i <= months; i += 1) {
    const interest = balance * monthlyRate;
    const principalPaid = emi - interest;
    balance -= principalPaid;

    const row = document.createElement("tr");
    row.innerHTML =
      `<td>Month ${i}</td>` +
      `<td>Rs${formatNumber(emi.toFixed(2))}</td>` +
      `<td>Rs${formatNumber(principalPaid.toFixed(2))}</td>` +
      `<td>Rs${formatNumber(interest.toFixed(2))}</td>` +
      `<td>Rs${formatNumber(Math.max(0, balance).toFixed(2))}</td>`;
    tbody.appendChild(row);
  }
}

async function deactivateCard(cardId) {
  const confirmed = await showConfirmDialog(
    "Deactivate Card",
    "This card will be marked as inactive. You can reactivate it later. Continue?",
    "Deactivate",
    "warning"
  );

  if (!confirmed) return;

  const userId = localStorage.getItem("finadvisor_user_id") || "00000000-0000-0000-0000-000000000001";

  try {
    const res = await fetch(`/api/v1/cards/${cardId}?user_id=${userId}`, {
      method: "DELETE",
      headers: { "Content-Type": "application/json" },
    });

    if (!res.ok) {
      const err = await res.json();
      throw new Error(err.detail || "Failed to deactivate card");
    }

    const idx = allCards.findIndex((c) => c.id === cardId);
    if (idx !== -1) {
      allCards[idx].is_active = false;
    }
    renderCards();

    showToast("Card deactivated successfully", "success");
    if (openCardId === cardId) {
      closeCardDetails();
    }
  } catch (err) {
    showToast(err.message, "error");
  }
}

async function reactivateCard(cardId) {
  const confirmed = await showConfirmDialog(
    "Reactivate Card",
    "Do you want to reactivate this card?",
    "Reactivate",
    "success"
  );

  if (!confirmed) return;

  const userId = localStorage.getItem("finadvisor_user_id") || "00000000-0000-0000-0000-000000000001";

  try {
    const res = await fetch(`/api/v1/cards/${cardId}?user_id=${userId}`, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ is_active: true }),
    });

    if (!res.ok) {
      const err = await res.json();
      throw new Error(err.detail || "Failed to reactivate card");
    }

    const idx = allCards.findIndex((c) => c.id === cardId);
    if (idx !== -1) {
      allCards[idx].is_active = true;
    }
    renderCards();

    showToast("Card reactivated successfully", "success");
  } catch (err) {
    showToast(err.message, "error");
  }
}

async function confirmDeleteCard(cardId) {
  const card = allCards.find((c) => c.id === cardId);
  if (card && card.is_active !== false) {
    await showConfirmDialog(
      "Deactivate Card First",
      "Please deactivate the card first and then delete it later.",
      "Okay",
      "warning",
      true
    );
    return;
  }

  const confirmed = await showConfirmDialog(
    "Delete Card Permanently",
    "This will permanently delete the card and ALL its linked benefits. This cannot be undone. Are you sure?",
    "Delete Permanently",
    "danger"
  );

  if (!confirmed) return;

  const userId = localStorage.getItem("finadvisor_user_id") || "00000000-0000-0000-0000-000000000001";

  try {
    const res = await fetch(`/api/v1/cards/${cardId}/permanent?user_id=${userId}`, { method: "DELETE" });

    if (!res.ok) {
      const err = await res.json();
      throw new Error(err.detail || "Delete failed");
    }

    const cardWrapper = document.getElementById("card-wrapper-" + cardId);
    if (cardWrapper) {
      cardWrapper.style.opacity = "0";
      cardWrapper.style.transition = "all 0.3s ease";
      setTimeout(() => {
        cardWrapper.remove();
        updateCardsEmptyState();
      }, 300);
    }

    if (openCardId === cardId) {
      closeCardDetails();
    }

    showToast("Card deleted permanently", "warning");
  } catch (err) {
    showToast(err.message, "error");
  }
}

function showConfirmDialog(title, message, confirmText, type = "warning", singleButton = false) {
  return new Promise((resolve) => {
    const colors = { warning: "#F59E0B", danger: "#EF4444", info: "#2563EB", success: "#10B981" };

    const existing = document.getElementById("confirm-dialog");
    if (existing) existing.remove();

    const dialog = document.createElement("div");
    dialog.id = "confirm-dialog";
    dialog.style.cssText = "position:fixed;inset:0;z-index:10000;background:rgba(0,0,0,0.5);display:flex;align-items:center;justify-content:center;padding:20px;";

    dialog.innerHTML = `
      <div style="background:white;border-radius:16px;padding:24px;max-width:400px;width:100%;box-shadow:0 20px 60px rgba(0,0,0,0.2);">
        <div style="display:flex;align-items:center;gap:10px;margin-bottom:12px">
          <div style="width:36px;height:36px;border-radius:10px;background:${colors[type]}20;display:flex;align-items:center;justify-content:center;flex-shrink:0">
            <svg width="18" height="18" fill="${colors[type]}" viewBox="0 0 24 24"><path d="M12 9v4m0 4h.01M10.29 3.86L1.82 18a2 2 0 001.71 3h16.94a2 2 0 001.71-3L13.71 3.86a2 2 0 00-3.42 0z"/></svg>
          </div>
          <h3 style="font-size:14px;font-weight:700;color:#0f172a;margin:0">${title}</h3>
        </div>
        <p style="font-size:13px;color:#475569;margin:0 0 20px;line-height:1.5">${message}</p>
        <div style="display:flex;gap:8px;justify-content:flex-end">
          ${singleButton ? "" : '<button id="dialog-cancel" style="background:#f1f5f9;border:none;border-radius:8px;padding:8px 16px;font-size:13px;cursor:pointer;color:#475569;font-weight:500">Cancel</button>'}
          <button id="dialog-confirm" style="background:${colors[type]};border:none;border-radius:8px;padding:8px 16px;font-size:13px;cursor:pointer;color:white;font-weight:600">${confirmText}</button>
        </div>
      </div>`;

    document.body.appendChild(dialog);

    if (!singleButton) {
      document.getElementById("dialog-cancel").onclick = () => {
        dialog.remove();
        resolve(false);
      };
    }
    document.getElementById("dialog-confirm").onclick = () => {
      dialog.remove();
      resolve(true);
    };
    dialog.onclick = (e) => {
      if (e.target === dialog) {
        dialog.remove();
        resolve(false);
      }
    };
  });
}

async function openEditCard(cardId) {
  try {
    const userId = localStorage.getItem("finadvisor_user_id") || "00000000-0000-0000-0000-000000000001";
    const res = await fetch(`/api/v1/cards/${cardId}?user_id=${userId}`);
    const card = await res.json();
    if (!res.ok) {
      throw new Error(card.detail || "Failed to load card");
    }
    openCardModal(card);
  } catch (err) {
    showToast(err.message || "Failed to open edit", "error");
  }
}

async function saveCardEdit(cardId, formData) {
  const userId = localStorage.getItem("finadvisor_user_id") || "00000000-0000-0000-0000-000000000001";

  try {
    const res = await fetch(`/api/v1/cards/${cardId}?user_id=${userId}`, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(formData),
    });

    if (!res.ok) {
      const err = await res.json();
      throw new Error(err.detail || "Update failed");
    }

    const updatedCard = await res.json();
    updateCardInDOM(updatedCard);

    closeModal();
    showToast("Card updated successfully", "success");

    return updatedCard;
  } catch (err) {
    showToast(err.message, "error");
    throw err;
  }
}

function collectFormData() {
  const raw = Object.fromEntries(new FormData(cardForm));
  const numericFields = [
    "expiry_month",
    "expiry_year",
    "credit_limit",
    "current_balance",
    "available_balance",
    "pending_emi_amount",
    "emi_tenure_months",
    "emi_interest_rate",
    "monthly_emi_amount",
    "billing_cycle_date",
    "payment_due_date",
    "annual_fee",
    "joining_fee",
    "reward_points_balance",
    "lounge_visits_per_quarter",
  ];

  numericFields.forEach((field) => {
    if (raw[field] === "" || raw[field] === undefined) {
      raw[field] = null;
      return;
    }
    const value = Number(raw[field]);
    raw[field] = Number.isNaN(value) ? null : value;
  });

  // Keep backend-required numeric fields as numbers (not null) to avoid 422 validation failures.
  ["annual_fee", "joining_fee", "reward_points_balance", "lounge_visits_per_quarter"].forEach((field) => {
    if (raw[field] === null || raw[field] === undefined) {
      raw[field] = 0;
    }
  });

  raw.lounge_access = String(raw.lounge_access) === "true";
  raw.fuel_surcharge_waiver = String(raw.fuel_surcharge_waiver) === "true";

  raw.card_last4 = String(raw.card_last4 || "").replace(/\D/g, "").slice(-4);

  return raw;
}

function validateCardForm(formData) {
  if (!formData.card_holder_name) {
    showToast("Card holder name is required", "error");
    return false;
  }
  if (!formData.card_last4 || formData.card_last4.length !== 4) {
    showToast("Card last 4 digits must be exactly 4 numbers", "error");
    return false;
  }
  if (!formData.bank_name) {
    showToast("Bank name is required", "error");
    return false;
  }
  return true;
}

async function createNewCard(formData) {
  const userId = localStorage.getItem("finadvisor_user_id") || "00000000-0000-0000-0000-000000000001";
  formData.user_id = userId;

  console.log("Creating card with data:", formData);

  const res = await fetch(`/api/v1/cards/?user_id=${userId}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(formData),
  });

  console.log("Response status:", res.status);

  const payload = await res.json();
  if (!res.ok) {
    const message = Array.isArray(payload.detail)
      ? payload.detail.map((d) => d.msg).join(", ")
      : payload.detail;
    throw new Error(message || "Failed to create card");
  }

  showToast("Card created successfully", "success");
  await fetchCards();
  closeModal();
}

function updateCardInDOM() {
  fetchCards();
}

function closeModal() {
  if (cardModal) {
    cardModal.classList.add("hidden");
    cardModal.style.display = "";
  }
  cardForm.removeAttribute("data-editing-card-id");
  cardForm.reset();
  handleCardTypeChange();
  renderModalPreview();
}

function openCardModal(existingCard = null) {
  const form = cardForm;
  const submitBtn = cardSubmitBtn;

  if (existingCard) {
    modalTitle.textContent = "Edit Card";
    submitBtn.textContent = "Update Card";
    form.setAttribute("data-editing-card-id", existingCard.id);
    prefillCardForm(existingCard);
  } else {
    modalTitle.textContent = "Add New Card";
    submitBtn.textContent = "Add Card";
    form.removeAttribute("data-editing-card-id");
    form.reset();
    handleCardTypeChange();
  }

  renderModalPreview();
  cardModal.classList.remove("hidden");
  cardModal.style.display = "";
}

function prefillCardForm(card) {
  const fields = {
    cardType: card.card_type,
    bankName: card.bank_name,
    cardHolderName: card.card_holder_name,
    cardLast4: card.card_last4,
    cardNetwork: card.card_network,
    expiryMonth: card.expiry_month,
    expiryYear: card.expiry_year,
    creditLimit: card.credit_limit,
    currentBalance: card.current_balance,
    availableBalance: card.available_balance,
    billingCycleDate: card.billing_cycle_date,
    paymentDueDate: card.payment_due_date,
    pendingEmi: card.pending_emi_amount,
    emiTenure: card.emi_tenure_months,
    interestRate: card.emi_interest_rate,
    monthlyEmi: card.monthly_emi_amount,
    annualFee: card.annual_fee,
    rewardPoints: card.reward_points_balance,
  };

  Object.entries(fields).forEach(([id, value]) => {
    const el = document.getElementById(id);
    if (el && value !== null && value !== undefined) {
      el.value = value;
    }
  });

  const statementPassword = document.getElementById("statementPassword");
  if (statementPassword) statementPassword.value = "";

  handleCardTypeChange();
}

function handleCardTypeChange() {
  const cardType = document.getElementById("cardType")?.value || "credit";
  document.querySelectorAll("[data-credit]").forEach((el) => {
    el.style.display = cardType === "credit" ? "block" : "none";
  });
  document.querySelectorAll("[data-debit]").forEach((el) => {
    el.style.display = cardType === "debit" ? "block" : "none";
  });
}

function inferThemeFromBank(bankName) {
  const bank = String(bankName || "").toLowerCase();
  if (bank.includes("hdfc")) return "hdfc";
  if (bank.includes("icici")) return "icici";
  if (bank.includes("axis")) return "axis";
  if (bank.includes("sbi")) return "sbi";
  if (bank.includes("kotak")) return "kotak";
  if (bank.includes("yes")) return "yes";
  if (bank.includes("indus")) return "indusind";
  if (bank.includes("idfc")) return "idfc";
  return "default";
}

function renderModalPreview() {
  if (!modalCardPreview) return;
  const cardType = document.getElementById("cardType")?.value || "credit";
  const bank = document.getElementById("bankName")?.value || "BANK";
  const holder = document.getElementById("cardHolderName")?.value || "CARD HOLDER";
  const last4 = document.getElementById("cardLast4")?.value || "0000";
  const month = String(document.getElementById("expiryMonth")?.value || "01").padStart(2, "0");
  const year = String(document.getElementById("expiryYear")?.value || "2030").slice(-2);

  modalCardPreview.className = `modal-card-preview bank-card ${getThemeClass({ bank_name: bank })}`;
  modalCardPreview.innerHTML = `
    <div class="card-holographic"></div>
    <span class="card-bank-name">${bank}</span>
    <div class="card-number">•••• •••• •••• ${last4}</div>
    <div class="card-bottom">
      <div class="card-holder-info"><span class="card-label">CARD HOLDER</span><span class="card-name">${holder.toUpperCase()}</span></div>
      <div class="card-expiry-info"><span class="card-label">VALID THRU</span><span class="card-expiry">${month}/${year}</span></div>
      <div class="card-type-badge">${cardType}</div>
    </div>
  `;
}

function bindCardChatModalEvents() {
  askCardBtn?.addEventListener("click", () => {
    const cardId = askCardBtn.dataset.cardId;
    const card = allCards.find((item) => String(item.id).toLowerCase() === String(cardId).toLowerCase());
    if (card) {
      openCardChatbot(card);
    } else {
      showToast("Open card details first", "info");
    }
  });

  cardChatbotClose?.addEventListener("click", closeCardChatbot);
  cardChatClear?.addEventListener("click", () => {
    if (!cardChatActiveCardId) {
      showToast("Open card details first", "info");
      return;
    }
    clearCardChatHistory(cardChatActiveCardId);
    renderCardChatMessages();
    showToast("Chat history cleared", "success");
  });
  cardChatbotModal?.addEventListener("click", (event) => {
    if (event.target?.dataset?.close === "true") {
      closeCardChatbot();
    }
  });

  cardChatSend?.addEventListener("click", () => {
    const value = cardChatInput?.value.trim() || "";
    if (!value) return;
    if (cardChatInput) cardChatInput.value = "";
    sendCardChatQuestion(value);
  });

  cardChatInput?.addEventListener("keypress", (event) => {
    if (event.key === "Enter") {
      event.preventDefault();
      const value = cardChatInput.value.trim();
      if (!value) return;
      cardChatInput.value = "";
      sendCardChatQuestion(value);
    }
  });
}

async function openAddBenefit(cardId) {
  const category = prompt("Benefit category (cashback/rewards/lounge/insurance/fuel/dining/shopping/travel/emi/other):", "cashback");
  if (!category) return;

  const title = prompt("Benefit title:");
  if (!title) return;

  const value = prompt("Value (optional):", "");
  const description = prompt("Description (optional):", "");
  const conditions = prompt("Conditions (optional):", "");

  const userId = localStorage.getItem("finadvisor_user_id") || "00000000-0000-0000-0000-000000000001";

  const res = await fetch(`/api/v1/cards/${cardId}/benefits?user_id=${userId}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      benefit_category: category,
      title,
      value: value || null,
      description: description || null,
      conditions: conditions || null,
    }),
  });

  const data = await res.json();
  if (!res.ok) {
    showToast(data.detail || "Failed to add benefit", "error");
    return;
  }

  showToast("Benefit added", "success");
}

cardForm?.addEventListener("submit", async (e) => {
  e.preventDefault();

  const submitBtn = e.target.querySelector('button[type="submit"]');
  try {
    const editingCardId = cardForm.getAttribute("data-editing-card-id");
    const formData = collectFormData();

    if (!validateCardForm(formData)) return;

    submitBtn.disabled = true;
    submitBtn.innerHTML = '<i data-lucide="loader-2" class="spin"></i> Saving...';
    if (window.lucide) {
      lucide.createIcons();
    }

    if (editingCardId) {
      await saveCardEdit(editingCardId, formData);
    } else {
      await createNewCard(formData);
    }
  } catch (err) {
    showToast(err.message || "Operation failed", "error");
  } finally {
    submitBtn.disabled = false;
    const editingCardId = cardForm.getAttribute("data-editing-card-id");
    submitBtn.textContent = editingCardId ? "Update Card" : "Add Card";
  }
});

function initFilters() {
  document.querySelectorAll("[data-filter]").forEach((button) => {
    button.addEventListener("click", () => {
      document.querySelectorAll("[data-filter]").forEach((b) => b.classList.remove("active"));
      button.classList.add("active");
      activeFilter = button.getAttribute("data-filter") || "all";
      renderCards();
    });
  });
}

function initModalEvents() {
  document.getElementById("openCardModal")?.addEventListener("click", () => openCardModal(null));
  document.getElementById("addFirstCard")?.addEventListener("click", () => openCardModal(null));
  document.getElementById("closeCardModal")?.addEventListener("click", closeModal);
  cardModal?.addEventListener("click", (e) => {
    if (e.target === cardModal || e.target.classList.contains("modal-overlay")) {
      closeModal();
    }
  });

  [
    "cardType",
    "bankName",
    "cardHolderName",
    "cardLast4",
    "expiryMonth",
    "expiryYear",
  ].forEach((id) => {
    document.getElementById(id)?.addEventListener("input", renderModalPreview);
    document.getElementById(id)?.addEventListener("change", renderModalPreview);
  });

  document.getElementById("cardType")?.addEventListener("change", handleCardTypeChange);
}

document.addEventListener("DOMContentLoaded", async () => {
  if (window.lucide) {
    lucide.createIcons();
  }
 
  initFilters();
  initModalEvents();
  bindCardChatModalEvents();
  handleCardTypeChange();
  renderModalPreview();
  setupCalcModalListeners();
 
  try {
    await fetchCards();
  } catch (err) {
    showToast(err.message || "Failed to load cards", "error");
  }
});

window.viewCardDetails = viewCardDetails;
window.closeCardDetails = closeCardDetails;
window.openEditCard = openEditCard;
window.deactivateCard = deactivateCard;
window.reactivateCard = reactivateCard;
window.confirmDeleteCard = confirmDeleteCard;
window.openAddBenefit = openAddBenefit;
window.handleRecAction = handleRecAction;
