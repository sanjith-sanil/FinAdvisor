async function readJsonResponse(response) {
  const text = await response.text();
  if (!text) return {};
  try {
    return JSON.parse(text);
  } catch {
    return { detail: text };
  }
}

function getResponseMessage(payload, fallback) {
  const detail = payload?.detail || payload?.message || payload;
  if (Array.isArray(detail)) return detail.map((item) => item.msg || item.message || String(item)).join(" | ");
  if (detail && typeof detail === "object") return detail.msg || detail.message || JSON.stringify(detail);
  return detail || fallback;
}

async function cacheEmailDataOnLogin(userId) {
  if (!userId) return;
  try {
    const [statusRes, txnRes] = await Promise.all([
      fetch(`/api/v1/email-config/status?user_id=${userId}`),
      fetch(`/api/v1/transactions/?user_id=${userId}&source=email&limit=10000`),
    ]);
    const status = await readJsonResponse(statusRes);
    const txns = await readJsonResponse(txnRes);
    const statusList = Array.isArray(status) ? status : [status];
    const txnsList = Array.isArray(txns) ? txns : [];
    const payload = [[statusList, txnsList]];
    localStorage.setItem("finadvisor_email_data", JSON.stringify(payload));
  } catch {
    return;
  }
}

document.addEventListener("DOMContentLoaded", async () => {
  if (window.lucide) lucide.createIcons();

  const params = new URLSearchParams(window.location.search);
  const googleError = params.get("google_error");
  if (googleError) {
    showFormError(googleError);
  }
  if (params.get("google_login") === "1" && params.get("user_id")) {
    localStorage.setItem("finadvisor_user_id", params.get("user_id"));
    localStorage.setItem("finadvisor_customer_id", params.get("customer_id") || "");
    localStorage.setItem("finadvisor_name", params.get("full_name") || "");
    localStorage.setItem("finadvisor_email", params.get("email") || "");
    await cacheEmailDataOnLogin(params.get("user_id"));
    window.location.href = "/home";
    return;
  }

  const googleLoginUrl = "/api/v1/auth/google/login/authorize";
  const googleLoginBtn = document.getElementById("googleLoginBtn");
  if (googleLoginBtn) {
    googleLoginBtn.addEventListener("click", () => {
      window.location.href = googleLoginUrl;
    });
  }
  document.querySelectorAll(".social-btn, .auth-social-btn").forEach((btn) => {
    if (btn.textContent?.toLowerCase().includes("google")) {
      btn.addEventListener("click", () => {
        window.location.href = googleLoginUrl;
      });
    }
  });

  document.querySelectorAll(".toggle-password").forEach((btn) => {
    btn.addEventListener("click", () => {
      const targetId = btn.dataset.target;
      const input = targetId
        ? document.getElementById(targetId)
        : btn.closest(".auth-input-wrapper")?.querySelector("input");
      if (!input) return;
      if (input.type === "password") {
        input.type = "text";
        btn.innerHTML = '<i data-lucide="eye-off"></i>';
      } else {
        input.type = "password";
        btn.innerHTML = '<i data-lucide="eye"></i>';
      }
      if (window.lucide) lucide.createIcons();
    });
  });

  const confirmInput = document.getElementById("confirm_password");
  if (confirmInput) {
    confirmInput.addEventListener("input", validatePasswordMatch);
  }

  const loginForm = document.getElementById("loginForm");
  if (loginForm) {
    loginForm.addEventListener("submit", async (event) => {
      event.preventDefault();
      const btn = loginForm.querySelector("button[type=submit]");
      if (!btn) return;
      btn.disabled = true;
      btn.innerHTML = '<i data-lucide="loader-2" class="spin"></i> Signing in...';
      if (window.lucide) lucide.createIcons();

      try {
        const response = await fetch("/api/v1/auth/login", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            email: document.getElementById("email").value,
            password: document.getElementById("password").value,
          }),
        });
        const data = await readJsonResponse(response);
        if (!response.ok) throw new Error(getResponseMessage(data, "Login failed"));

        localStorage.setItem("finadvisor_user_id", data.user_id);
        localStorage.setItem("finadvisor_customer_id", data.customer_id);
        localStorage.setItem("finadvisor_name", data.full_name);
        localStorage.setItem("finadvisor_email", data.email);
        await cacheEmailDataOnLogin(data.user_id);
        window.location.href = "/home";
      } catch (error) {
        showFormError(error.message || "Login failed");
        btn.disabled = false;
        btn.textContent = "Sign In";
      }
    });
  }

  const registerForm = document.getElementById("registerForm");
  if (registerForm) {
    const steps = Array.from(document.querySelectorAll(".auth-step"));
    const badges = Array.from(document.querySelectorAll("[data-step-badge]"));
    const selectedEmail = document.getElementById("selectedEmail");
    const continueToEmail = document.getElementById("continueToEmail");
    const backToStep1 = document.getElementById("backToStep1");
    const skipEmailBtn = document.getElementById("skipEmailBtn");
    const connectGmailBtn = document.getElementById("connectGmailBtn");
    const testImapBtn = document.getElementById("testImapBtn");
    const imapHelpBtn = document.getElementById("imapHelpBtn");
    const completeSetupBtn = document.getElementById("completeSetupBtn");
    const skipSmsBtn = document.getElementById("skipSmsBtn");
    const markSmsConfigured = document.getElementById("markSmsConfigured");
    const smsAppLink = document.getElementById("smsAppLink");
    const smsWebhookUrl = document.getElementById("smsWebhookUrl");
    const smsApiKey = document.getElementById("smsApiKey");
    const smsUserId = document.getElementById("smsUserId");
    const smsFilterTags = document.getElementById("smsFilterTags");
    const copyWebhookBtn = document.getElementById("copyWebhookBtn");
    const copyApiKeyBtn = document.getElementById("copyApiKeyBtn");
    const copyUserIdBtn = document.getElementById("copyUserIdBtn");
    const goDashboardBtn = document.getElementById("goDashboardBtn");
    const copyCustomerBtn = document.getElementById("copyCustomerBtn");
    const emailStatusCard = document.getElementById("emailStatusCard");
    const smsStatusCard = document.getElementById("smsStatusCard");
    const customerIdLabel = document.getElementById("customerIdLabel");
    const firstName = document.getElementById("firstName");

    let emailConnected = false;
    let smsConfigured = false;

    const getActiveUserId = () => {
      const params = new URLSearchParams(window.location.search);
      const paramUserId = params.get("user_id");
      if (paramUserId) {
        localStorage.setItem("finadvisor_user_id", paramUserId);
        return paramUserId;
      }
      return localStorage.getItem("finadvisor_user_id");
    };

    const syncCustomerId = async () => {
      const storedCustomerId = localStorage.getItem("finadvisor_customer_id");
      if (storedCustomerId && customerIdLabel) {
        customerIdLabel.textContent = storedCustomerId;
        return;
      }
      const userId = getActiveUserId();
      if (!userId) return;
      try {
        const response = await fetch(`/api/v1/users/${userId}`);
        if (!response.ok) return;
        const data = await readJsonResponse(response);
        if (data?.customer_id) {
          localStorage.setItem("finadvisor_customer_id", data.customer_id);
          if (customerIdLabel) customerIdLabel.textContent = data.customer_id;
        }
      } catch {
        return;
      }
    };

    const setStep = (step) => {
      steps.forEach((el) => el.classList.toggle("active", el.dataset.step === String(step)));
      badges.forEach((badge) => {
        badge.classList.toggle("active", Number(badge.dataset.stepBadge) <= Number(step));
      });
      if (window.lucide) lucide.createIcons();
    };

    const showHelp = () => {
      showFormNotice(
        "Gmail: myaccount.google.com → Security → App Passwords. Outlook: account.microsoft.com → Security → App Password. Yahoo: login.yahoo.com → Security → App Password."
      );
    };

    const loadSmsSetup = async () => {
      const userId = getActiveUserId();
      if (!userId) return;
      const fallbackAppUrl = "https://play.google.com/store/apps/details?id=com.frzinapps.smsforward";
      smsAppLink.setAttribute("href", fallbackAppUrl);
      const response = await fetch(`/api/v1/sms/setup-info/${userId}`);
      if (!response.ok) {
        if (response.status === 404) {
          localStorage.removeItem("finadvisor_user_id");
          localStorage.removeItem("finadvisor_customer_id");
          showFormError("User not found. Please complete Step 1 again.");
          setStep(1);
        }
        smsWebhookUrl.value = "";
        smsApiKey.value = "";
        smsUserId.value = "";
        smsFilterTags.innerHTML = "";
        return;
      }
      const data = await response.json();
      const cleanValue = (value) => {
        if (value === undefined || value === null) return "";
        const text = String(value);
        return ["undefined", "null"].includes(text.toLowerCase()) ? "" : text;
      };
      smsWebhookUrl.value = cleanValue(data.webhook_url);
      smsApiKey.value = cleanValue(data.api_key);
      smsUserId.value = cleanValue(data.user_id);
      smsAppLink.setAttribute("href", cleanValue(data.app_download_url) || fallbackAppUrl);
      const keywords = (data.filter_keywords || "")
        .split(",")
        .map((item) => item.trim())
        .filter(Boolean);
      smsFilterTags.innerHTML = keywords
        .map((item) => `<span class="filter-tag">${item}</span>`)
        .join("");
    };

    const ensureAppLink = () => {
      const fallbackAppUrl = "https://play.google.com/store/apps/details?id=com.frzinapps.smsforward";
      const href = smsAppLink?.getAttribute("href") || "";
      const normalized = href.toLowerCase();
      if (!href || href === "#" || normalized === "undefined" || normalized === "null") {
        smsAppLink?.setAttribute("href", fallbackAppUrl);
      }
    };

    smsAppLink?.addEventListener("click", () => {
      ensureAppLink();
    });

    const copyText = async (value) => {
      try {
        await navigator.clipboard.writeText(value);
        showFormNotice("Copied to clipboard");
      } catch {
        showFormError("Unable to copy. Please copy manually.");
      }
    };

    continueToEmail?.addEventListener("click", async () => {
      const terms = document.getElementById("terms");
      if (terms && !terms.checked) {
        showFormError("Please agree to Terms and Privacy Policy");
        return;
      }
      const phone = document.getElementById("phone_number").value.replace(/\D/g, "");
      if (phone.length !== 10) {
        showFormError("Phone number must be 10 digits");
        return;
      }
      const password = document.getElementById("password").value;
      const confirm = document.getElementById("confirm_password").value;
      if (password !== confirm) {
        showFormError("Passwords do not match");
        return;
      }

      try {
        const response = await fetch("/api/v1/auth/register", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            full_name: document.getElementById("full_name").value,
            email: document.getElementById("email").value,
            phone_number: "+91" + phone,
            password,
            confirm_password: confirm,
          }),
        });
        const data = await readJsonResponse(response);
        if (!response.ok) {
          throw new Error(getResponseMessage(data, "Registration failed"));
        }
        localStorage.setItem("finadvisor_user_id", data.user_id);
        localStorage.setItem("finadvisor_customer_id", data.customer_id);
        localStorage.setItem("finadvisor_name", data.full_name);
        selectedEmail.textContent = data.email;
        customerIdLabel.textContent = data.customer_id;
        const nameParts = (data.full_name || "").split(" ");
        firstName.textContent = nameParts[0] || "there";
        setStep(2);
      } catch (error) {
        showFormError(error.message || "Registration failed");
      }
    });

    backToStep1?.addEventListener("click", () => setStep(1));

    connectGmailBtn?.addEventListener("click", () => {
      const userId = getActiveUserId();
      if (!userId) return;
      window.location.href = `/api/v1/auth/google/authorize?user_id=${userId}`;
    });

    testImapBtn?.addEventListener("click", async () => {
      const userId = getActiveUserId();
      const email = document.getElementById("email").value;
      const password = document.getElementById("imapPassword").value;
      if (!password) {
        showFormError("Enter your app password first");
        return;
      }
      const response = await fetch("/api/v1/email-config/test-connection", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email_address: email, password }),
      });
      const result = await readJsonResponse(response);
      if (!response.ok || !result.success) {
        showFormError(result.message || "Connection failed");
        return;
      }
      await fetch("/api/v1/email-config/setup-imap", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ user_id: userId, email_address: email, password }),
      });
      emailConnected = true;
      setStep(3);
      loadSmsSetup();
    });

    imapHelpBtn?.addEventListener("click", showHelp);
    skipEmailBtn?.addEventListener("click", () => {
      emailConnected = false;
      setStep(3);
      loadSmsSetup();
    });

    markSmsConfigured?.addEventListener("click", async () => {
      const userId = getActiveUserId();
      if (!userId) return;
      await fetch(`/api/v1/sms/mark-configured/${userId}`, { method: "POST" });
      smsConfigured = true;
      showFormNotice("SMS setup marked as complete");
    });

    completeSetupBtn?.addEventListener("click", () => {
      emailStatusCard.textContent = emailConnected ? "Email: Connected (OK)" : "Email: Pending setup";
      smsStatusCard.textContent = smsConfigured ? "SMS: Auto-forward active (OK)" : "SMS: Manual only";
      syncCustomerId();
      setStep(4);
    });

    skipSmsBtn?.addEventListener("click", () => {
      smsConfigured = false;
      syncCustomerId();
      setStep(4);
    });

    copyWebhookBtn?.addEventListener("click", () => copyText(smsWebhookUrl.value));
    copyApiKeyBtn?.addEventListener("click", () => copyText(smsApiKey.value));
    copyUserIdBtn?.addEventListener("click", () => copyText(smsUserId.value));
    copyCustomerBtn?.addEventListener("click", () => copyText(customerIdLabel.textContent));
    goDashboardBtn?.addEventListener("click", () => {
      window.location.href = "/dashboard";
    });

    const urlStep = new URLSearchParams(window.location.search).get("step");
    if (urlStep === "3") {
      const storedUserId = getActiveUserId();
      if (!storedUserId) {
        showFormError("Please complete Step 1 first.");
        setStep(1);
        return;
      }
      setStep(3);
      loadSmsSetup();
      emailConnected = true;
      if (selectedEmail) selectedEmail.textContent = document.getElementById("email").value || "";
    }

    syncCustomerId();
  }
});

function validatePasswordMatch() {
  const password = document.getElementById("password")?.value || "";
  const confirm = document.getElementById("confirm_password")?.value || "";
  const indicator = document.getElementById("match-indicator");
  const confirmInput = document.getElementById("confirm_password");
  if (!indicator) return;
  if (!confirm) {
    indicator.innerHTML = "";
    confirmInput?.classList.remove("error");
    return;
  }
  if (password === confirm) {
    indicator.innerHTML = '<i data-lucide="check-circle" style="color:#10B981;width:14px"></i>';
    confirmInput?.classList.remove("error");
  } else {
    indicator.innerHTML = '<i data-lucide="x-circle" style="color:#EF4444;width:14px"></i>';
    confirmInput?.classList.add("error");
  }
  if (window.lucide) lucide.createIcons();
}


function showFormError(message) {
  let errorDiv = document.getElementById("form-error");
  if (!errorDiv) {
    errorDiv = document.createElement("div");
    errorDiv.id = "form-error";
    errorDiv.style.cssText =
      "background: #FEF2F2; border: 1px solid #FECACA;" +
      "color: #DC2626; border-radius: 8px;" +
      "padding: 10px 14px; font-size: 12px;" +
      "margin-bottom: 14px; display: flex;" +
      "align-items: center; gap: 8px;";
    const form = document.querySelector("form");
    if (form) form.insertBefore(errorDiv, form.firstChild);
  }
  errorDiv.innerHTML =
    '<i data-lucide="alert-circle" style="width:14px;flex-shrink:0"></i>' + message;
  if (window.lucide) lucide.createIcons();
  setTimeout(() => errorDiv?.remove(), 4000);
}

function showFormNotice(message) {
  let noticeDiv = document.getElementById("form-notice");
  if (!noticeDiv) {
    noticeDiv = document.createElement("div");
    noticeDiv.id = "form-notice";
    noticeDiv.style.cssText =
      "background: #EFF6FF; border: 1px solid #BFDBFE;" +
      "color: #1D4ED8; border-radius: 8px;" +
      "padding: 10px 14px; font-size: 12px;" +
      "margin-bottom: 14px; display: flex;" +
      "align-items: center; gap: 8px;";
    const form = document.querySelector("form");
    if (form) form.insertBefore(noticeDiv, form.firstChild);
  }
  noticeDiv.innerHTML =
    '<i data-lucide="info" style="width:14px;flex-shrink:0"></i>' + message;
  if (window.lucide) lucide.createIcons();
  setTimeout(() => noticeDiv?.remove(), 4500);
}
