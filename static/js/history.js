const BANK_META = {
  HDFC: { name: "HDFC Bank", color: "#004C8F" },
  SBI: { name: "State Bank of India", color: "#2D6DB5" },
  ICICI: { name: "ICICI Bank", color: "#F58220" },
  AXIS: { name: "Axis Bank", color: "#97144D" },
  KOTAK: { name: "Kotak Mahindra Bank", color: "#ED1C24" },
  YES: { name: "Yes Bank", color: "#00539B" },
  INDUSIND: { name: "IndusInd Bank", color: "#E31837" },
  IDFC: { name: "IDFC First Bank", color: "#9B1F61" },
  PNB: { name: "Punjab National Bank", color: "#FF6600" },
  BOI: { name: "Bank of India", color: "#003087" },
  BOB: { name: "Bank of Baroda", color: "#F7941D" },
  UNKNOWN: { name: "Unknown Bank", color: "#64748B" },
};

let historySyncPoll = null;
let historyRefreshPoll = null;

function clearHistorySyncTimers() {
  if (historySyncPoll) {
    clearInterval(historySyncPoll);
    historySyncPoll = null;
  }
  if (historyRefreshPoll) {
    clearInterval(historyRefreshPoll);
    historyRefreshPoll = null;
  }
}

function upsertHistorySyncBanner(kind, text) {
  const anchor = document.querySelector(".collection-status-bar");
  if (!anchor) return;

  let banner = document.getElementById("historySyncBanner");
  if (!banner) {
    banner = document.createElement("div");
    banner.id = "historySyncBanner";
    banner.className = "sync-banner";
    anchor.insertAdjacentElement("afterend", banner);
  }
  banner.className = `sync-banner ${kind}`;
  banner.textContent = text;
}

function removeHistorySyncBanner() {
  const banner = document.getElementById("historySyncBanner");
  if (banner) banner.remove();
}

async function monitorHistoryEmailSync() {
  clearHistorySyncTimers();
  const userId = getUserId();
  const status = await apiFetch(`/api/v1/email-config/sync-status?user_id=${userId}`);

  if (status.sync_status === "syncing") {
    upsertHistorySyncBanner("info", "Email sync in progress... Transactions are being imported.");

    historyRefreshPoll = setInterval(() => {
      loadTransactions();
      updateCollectionStatus();
    }, 5000);

    historySyncPoll = setInterval(async () => {
      try {
        const latest = await apiFetch(`/api/v1/email-config/sync-status?user_id=${userId}`);
        if (latest.sync_status === "completed") {
          clearHistorySyncTimers();
          removeHistorySyncBanner();
          await loadTransactions();
          await updateCollectionStatus();
          showToast("Email sync completed. History refreshed.", "success");
        } else if (latest.sync_status === "error") {
          clearHistorySyncTimers();
          upsertHistorySyncBanner("error", `Email sync failed: ${latest.last_error || "Unknown error"}`);
        }
      } catch (error) {
        console.error("History sync polling failed", error);
      }
    }, 5000);
    return;
  }

  if (status.sync_status === "completed" && status.last_checked) {
    const ageMs = Date.now() - new Date(status.last_checked).getTime();
    if (ageMs < 60 * 60 * 1000) {
      upsertHistorySyncBanner("success", `\u2713 ${status.transactions_found || 0} transactions imported from your bank emails`);
      setTimeout(() => removeHistorySyncBanner(), 5000);
    }
  }
}

function hexToRgb(hex) {
  const value = hex.replace("#", "");
  const parsed = Number.parseInt(value.length === 3 ? value.split("").map((c) => c + c).join("") : value, 16);
  return {
    r: (parsed >> 16) & 255,
    g: (parsed >> 8) & 255,
    b: parsed & 255,
  };
}

function bankBadgeHtml(txn) {
  const bankCode = (txn.bank_code || "").toUpperCase();
  const bankName = txn.bank_name || "";
  if (!bankCode && !bankName) {
    return "<span class=\"muted-dash\">—</span>";
  }

  const meta = BANK_META[bankCode] || { name: bankName || bankCode, color: "#64748B" };
  const rgb = hexToRgb(meta.color);
  const label = bankCode || bankName;

  return `<span class="bank-pill" style="background: rgba(${rgb.r}, ${rgb.g}, ${rgb.b}, 0.15); color: ${meta.color}; border: 1px solid rgba(${rgb.r}, ${rgb.g}, ${rgb.b}, 0.30);">${label}</span>`;
}

function sourceIcon(source) {
  if (source === "sms") return "message-square";
  if (source === "email") return "mail";
  if (source === "pdf_upload") return "file-text";
  return "pen-line";
}

function sourceLabel(source) {
  const value = String(source || "").toLowerCase();
  if (value === "sms") return "SMS";
  if (value === "email") return "Email";
  if (value === "pdf_upload") return "PDF Upload";
  if (value === "manual") return "Manual";
  return source || "-";
}

function formatAmount(txn) {
  const prefix = txn.transaction_type === "debit" ? "-" : "+";
  return `${prefix}₹${Number(txn.amount || 0).toLocaleString("en-IN")}`;
}

function formatBalance(balance) {
  if (balance === null || balance === undefined) {
    return '<span class="muted-dash" title="This bank email did not include an available balance">Not provided</span>';
  }
  return `₹${Number(balance).toLocaleString("en-IN")}`;
}

function escapeHtml(value) {
  return String(value ?? "")
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/\"/g, "&quot;")
    .replace(/'/g, "&#39;");
}

function senderValue(txn) {
  const source = String(txn.source || "").toLowerCase();
  if (source === "email") return txn.sender_email || txn.sender_phone || "—";
  if (source === "sms") return txn.sender_phone || txn.sender_email || "—";
  if (txn.sender_email) return txn.sender_email;
  if (txn.sender_phone) return txn.sender_phone;
  return "—";
}

function descriptionCellHtml(txn) {
  const value = (txn.description || txn.merchant_name || "").trim();
  const safeValue = escapeHtml(value || "—");
  const isLong = value.length > 90;
  return `
    <div class="txn-desc ${isLong ? "" : "no-toggle"}">
      <span class="txn-desc-text" title="${safeValue}">${safeValue}</span>
      ${
        isLong
          ? '<button type="button" class="desc-toggle-btn" aria-label="Expand description">Show more</button>'
          : ""
      }
    </div>
  `;
}

function monthKey(dateValue) {
  const date = new Date(dateValue);
  return `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, "0")}`;
}

function monthLabel(key) {
  const [year, month] = key.split("-").map((value) => Number(value));
  return new Date(year, month - 1, 1).toLocaleDateString("en-IN", { month: "long", year: "numeric" });
}

function buildMonthlyRows(data) {
  const grouped = new Map();
  data.forEach((txn) => {
    const key = monthKey(txn.transaction_date);
    if (!grouped.has(key)) grouped.set(key, []);
    grouped.get(key).push(txn);
  });

  const orderedKeys = [...grouped.keys()].sort((a, b) => (a < b ? 1 : -1));
  const rows = [];

  orderedKeys.forEach((key) => {
    const items = grouped.get(key);
    let spent = 0;
    let received = 0;
    const bankTotals = {};

    items.forEach((txn) => {
      const amount = Number(txn.amount || 0);
      if (txn.transaction_type === "debit") {
        spent += amount;
      } else if (txn.transaction_type === "credit") {
        received += amount;
      }

      const code = (txn.bank_code || "UNKNOWN").toUpperCase();
      const name = txn.bank_name || (BANK_META[code] ? BANK_META[code].name : "Unknown Bank");
      if (!bankTotals[code]) {
        bankTotals[code] = { code, name, value: 0 };
      }
      bankTotals[code].value += amount;
    });

    const topBank = Object.values(bankTotals).sort((a, b) => b.value - a.value)[0];
    const topBankLabel = topBank ? `${topBank.code} (₹${topBank.value.toLocaleString("en-IN")})` : "—";

    rows.push(`
      <tr class="month-summary-row">
        <td colspan="8">
          ${monthLabel(key)} — Spent: ₹${spent.toLocaleString("en-IN")} | Received: ₹${received.toLocaleString("en-IN")} | Top Bank: ${topBankLabel}
        </td>
      </tr>
    `);

    items.forEach((txn) => {
      const sender = senderValue(txn);
      const senderSafe = sender || "—";
      rows.push(`
        <tr>
          <td>${new Date(txn.transaction_date).toLocaleDateString("en-IN")}</td>
          <td>${descriptionCellHtml(txn)}</td>
          <td><span class="badge">${txn.transaction_type || "-"}</span></td>
          <td class="${txn.transaction_type === "debit" ? "amount-debit" : "amount-credit"}">${formatAmount(txn)}</td>
          <td>${sourceLabel(txn.source)}</td>
          <td>${bankBadgeHtml(txn)}</td>
          <td>
            <span
              class="sender-token ${senderSafe === "—" ? "disabled" : ""}"
              data-copy="${senderSafe}"
              title="${senderSafe}"
            >${senderSafe}<span class="copy-hint">Copied!</span></span>
          </td>
          <td>${formatBalance(txn.balance_after)}</td>
        </tr>
      `);
    });
  });

  return rows.join("");
}

async function loadTransactions() {
  const userId = getUserId();
  const params = new URLSearchParams({ user_id: userId });
  const dateFrom = document.getElementById("dateFrom").value;
  const dateTo = document.getElementById("dateTo").value;
  const cardId = document.getElementById("cardFilter").value;
  const type = document.getElementById("typeFilter").value;
  const category = document.getElementById("categoryFilter").value;
  const source = document.getElementById("sourceFilter").value;
  const bankCode = document.getElementById("bankFilter").value;
  const search = document.getElementById("searchBox").value;

  if (dateFrom) params.set("date_from", dateFrom);
  if (dateTo) params.set("date_to", dateTo);
  if (cardId) params.set("card_id", cardId);
  if (type) params.set("type", type);
  if (category) params.set("category", category);
  if (source) params.set("source", source);
  if (bankCode) params.set("bank_code", bankCode);
  if (search) params.set("search", search);

  const data = await apiFetch(`/api/v1/transactions/?${params.toString()}`);
  const table = document.getElementById("transactionsTable");
  const empty = document.getElementById("transactionsEmpty");

  data.sort((a, b) => new Date(b.transaction_date) - new Date(a.transaction_date));

  if (empty) empty.style.display = data.length ? "none" : "block";

  table.innerHTML = `
    <tr>
      <th>Date</th>
      <th>Description</th>
      <th>Type</th>
      <th>Amount</th>
      <th>Source</th>
      <th>Bank</th>
      <th>Sender Email / SMS ID</th>
      <th>Balance</th>
    </tr>
    ${buildMonthlyRows(data)}
  `;

  if (window.lucide) lucide.createIcons();
}

window.loadTransactions = loadTransactions;

document.addEventListener("click", async (event) => {
  const toggleBtn = event.target.closest(".desc-toggle-btn");
  if (toggleBtn) {
    const wrapper = toggleBtn.closest(".txn-desc");
    const expanded = wrapper?.classList.toggle("expanded");
    toggleBtn.textContent = expanded ? "Show less" : "Show more";
    toggleBtn.setAttribute("aria-label", expanded ? "Collapse description" : "Expand description");
    return;
  }

  const senderNode = event.target.closest(".sender-token");
  if (!senderNode || senderNode.classList.contains("disabled")) return;
  const value = senderNode.getAttribute("data-copy") || "";
  if (!value || value === "—") return;

  try {
    await navigator.clipboard.writeText(value);
    senderNode.classList.add("copied");
    setTimeout(() => senderNode.classList.remove("copied"), 900);
  } catch {
    showToast("Copy failed", "error");
  }
});

async function parseSms() {
  const userId = getUserId();
  const payload = {
    raw_sms: document.getElementById("smsRaw").value,
    sender: document.getElementById("smsSender").value,
    received_at: document.getElementById("smsReceived").value,
  };
  const result = await apiFetch(`/api/v1/sms/ingest?user_id=${userId}`, {
    method: "POST",
    body: JSON.stringify(payload),
  });
  const preview = document.getElementById("smsPreview");
  preview.style.display = "block";
  preview.innerHTML = `
    <div class="grid grid-5" style="gap: 8px; font-size: 12px;">
      <div><strong>Type</strong><br/>${result.transaction.transaction_type || "-"}</div>
      <div><strong>Amount</strong><br/>₹${result.transaction.amount || 0}</div>
      <div><strong>Merchant</strong><br/>${result.transaction.merchant_name || "-"}</div>
      <div><strong>Bank</strong><br/>${result.transaction.bank_code || "UNKNOWN"}</div>
      <div><strong>Date</strong><br/>${payload.received_at || "-"}</div>
    </div>
    <div style="display: flex; gap: 8px; margin-top: 8px;">
      <button class="btn btn-primary">Confirm & Save</button>
      <button class="btn btn-secondary">Discard</button>
    </div>
  `;
  loadTransactions();
}

async function loadCardOptions() {
  const userId = getUserId();
  if (!userId) return;
  const cards = await apiFetch(`/api/v1/cards/?user_id=${userId}`);
  const selector = document.getElementById("cardFilter");
  selector.innerHTML =
    `<option value="">All Cards</option>` +
    cards.map((card) => `<option value="${card.id}">${card.bank_name} •••• ${card.card_last4}</option>`).join("");
}

async function updateCollectionStatus() {
  const userId = getUserId();
  const data = await apiFetch(`/api/v1/email-config/status?user_id=${userId}`);
  const emailDot = document.getElementById("emailDot");
  const emailStatus = document.getElementById("emailStatus");
  const lastChecked = document.getElementById("lastChecked");
  if (data.configured && data.is_active) {
    emailDot?.classList.remove("inactive");
    const minutes = data.last_checked
      ? Math.max(1, Math.round((Date.now() - new Date(data.last_checked).getTime()) / 60000))
      : 0;
    emailStatus.textContent = `Email: checked ${minutes} min ago`;
    if (data.last_checked) lastChecked.textContent = `Last checked: ${minutes} min ago`;
  } else {
    emailDot?.classList.add("inactive");
    emailStatus.textContent = "Email: not connected";
  }

  const smsDot = document.getElementById("smsDot");
  const smsStatus = document.getElementById("smsStatus");
  if (smsDot && smsStatus) {
    const user = await apiFetch(`/api/v1/users/${userId}`);
    if (user.sms_configured) {
      smsDot.classList.remove("inactive");
      smsStatus.textContent = "SMS: active";
    } else {
      smsDot.classList.add("inactive");
      smsStatus.textContent = "SMS: waiting...";
    }
  }
}

async function checkEmailNow() {
  const userId = getUserId();
  const btn = document.getElementById("checkEmailNow");
  if (btn) {
    btn.textContent = "Checking...";
    btn.disabled = true;
  }
  await apiFetch(`/api/v1/email-config/check-now?user_id=${userId}`, { method: "POST" });
  showToast("Email sync started", "info");
  await monitorHistoryEmailSync();
  if (btn) {
    btn.textContent = "Check Now";
    btn.disabled = false;
  }
  updateCollectionStatus();
}

window.addEventListener("DOMContentLoaded", () => {
  if (window.lucide) lucide.createIcons();
  loadCardOptions();
  loadTransactions();
  document.getElementById("parseSms").addEventListener("click", parseSms);
  document.getElementById("exportCsv").addEventListener("click", () => {
    const userId = getUserId();
    window.location.href = `/api/v1/transactions/export/csv?user_id=${userId}`;
  });
  document.getElementById("applyFilters").addEventListener("click", loadTransactions);
  document.getElementById("checkEmailNow")?.addEventListener("click", checkEmailNow);
  updateCollectionStatus();
  monitorHistoryEmailSync();
  document.querySelectorAll(".collapsible-header").forEach((header) => {
    header.addEventListener("click", () => {
      const body = header.nextElementSibling;
      const chevron = header.querySelector(".chevron");
      const isOpen = body.style.maxHeight;
      body.style.maxHeight = isOpen ? null : `${body.scrollHeight}px`;
      body.style.overflow = "hidden";
      body.style.transition = "max-height 0.3s ease";
      if (chevron) chevron.style.transform = isOpen ? "rotate(0deg)" : "rotate(180deg)";
    });
  });
});
