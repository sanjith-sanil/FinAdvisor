const tabs = {
	personal: document.getElementById("personalTab"),
	security: document.getElementById("securityTab"),
	"auto-collection": document.getElementById("autoCollectionTab"),
	badges: document.getElementById("badgesTab"),
};

// ── Initialise visible tab on every page load ─────────────────────────────
// Determine which tab is marked active in the HTML (default: "personal")
const activeTabEl = document.querySelector(".profile-tab.active");
const initialTab  = activeTabEl ? activeTabEl.dataset.tab : "personal";

// Explicitly show/hide each panel — overrides any CSS caching issues
Object.entries(tabs).forEach(([key, el]) => {
	if (el) el.style.display = key === initialTab ? "block" : "none";
});

if (initialTab === "badges") {
	loadUserBadges();
}

document.querySelectorAll(".profile-tab").forEach((tab) => {
	tab.addEventListener("click", () => {
		const target = tab.dataset.tab;
		document.querySelectorAll(".profile-tab").forEach((item) => item.classList.remove("active"));
		tab.classList.add("active");
		Object.entries(tabs).forEach(([key, el]) => {
			if (el) el.style.display = key === target ? "block" : "none";
		});
		if (target === "badges") {
			loadUserBadges();
		}
		if (window.lucide) lucide.createIcons();
	});
});

const hashTab = window.location.hash.replace("#", "");
if (hashTab && tabs[hashTab]) {
  document.querySelectorAll(".profile-tab").forEach((item) => item.classList.remove("active"));
  document.querySelector(`.profile-tab[data-tab="${hashTab}"]`)?.classList.add("active");
  Object.entries(tabs).forEach(([key, el]) => {
    if (el) el.style.display = key === hashTab ? "block" : "none";
  });
  if (hashTab === "badges") {
    loadUserBadges();
  }
}

document.querySelectorAll(".toggle").forEach((toggle) => {
	toggle.addEventListener("click", () => {
		toggle.classList.toggle("on");
	});
});


document.querySelectorAll(".toggle-password").forEach((btn) => {
	btn.addEventListener("click", () => {
		const targetId = btn.dataset.target;
		const input = targetId ? document.getElementById(targetId) : null;
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

const viewInsightsBtn = document.getElementById("viewInsightsBtn");
const editAvatarBtn = document.getElementById("editAvatarBtn");
const logoutBtn = document.getElementById("logoutBtn");
const profileName = document.getElementById("profileName");
const profileCustomer = document.getElementById("profileCustomer");
const profileAvatar = document.querySelector(".profile-avatar");

viewInsightsBtn?.addEventListener("click", () => {
	window.location.href = "/dashboard";
});

editAvatarBtn?.addEventListener("click", () => {
	showToast("Avatar editing coming soon", "info");
});

logoutBtn?.addEventListener("click", () => {
	localStorage.removeItem("finadvisor_user_id");
	localStorage.removeItem("finadvisor_token");
	window.location.href = "/signin";
});

const storedName = localStorage.getItem("finadvisor_name") || "";
const storedCustomer = localStorage.getItem("finadvisor_customer_id") || "";
const storedEmail = localStorage.getItem("finadvisor_email") || "";
if (profileName && storedName) profileName.textContent = storedName;
if (profileCustomer && storedCustomer) profileCustomer.textContent = storedCustomer;
if (profileAvatar) {
	const parts = storedName.trim().split(/\s+/).filter(Boolean);
	const first = parts[0]?.[0] || "F";
	const last = parts.length > 1 ? parts[parts.length - 1]?.[0] || "" : "";
	profileAvatar.textContent = (first + last).toUpperCase();
}

if (window.lucide) lucide.createIcons();

const profileConnectGmail = document.getElementById("profileConnectGmail");
const profileTestImap = document.getElementById("profileTestImap");
const profileSaveImap = document.getElementById("profileSaveImap");
const emailStatusPill = document.getElementById("emailStatusPill");
const emailSetupOptions = document.getElementById("emailSetupOptions");
const emailStatusPanel = document.getElementById("emailStatusPanel");
const emailMasked = document.getElementById("emailMasked");
const emailAuthType = document.getElementById("emailAuthType");
const emailLastChecked = document.getElementById("emailLastChecked");
const emailProcessed = document.getElementById("emailProcessed");
const emailTransactions = document.getElementById("emailTransactions");
const emailLastError = document.getElementById("emailLastError");
const emailCheckNow = document.getElementById("emailCheckNow");
const emailToggle = document.getElementById("emailToggle");
const emailDisconnect = document.getElementById("emailDisconnect");
const emailLog = document.getElementById("emailLog");
const profileEmail = document.getElementById("profileEmail");
const profileAppPassword = document.getElementById("profileAppPassword");
const emailSyncProgress = document.getElementById("emailSyncProgress");
const syncStatusText = document.getElementById("syncStatusText");
const syncStats = document.getElementById("syncStats");
const syncEmailsFound = document.getElementById("syncEmailsFound");
const syncTxnFound = document.getElementById("syncTxnFound");

const pdfCardSelect = document.getElementById("pdfCardSelect");
const pdfDropzone = document.getElementById("pdfDropzone");
const pdfDropzoneText = document.getElementById("pdfDropzoneText");
const pdfFile = document.getElementById("pdfFile");
const pdfUploadBtn = document.getElementById("pdfUploadBtn");
const pdfUploadsList = document.getElementById("pdfUploadsList");
const pdfUploadForm = document.getElementById("pdfUploadForm");
const bankDomainSearch = document.getElementById("bankDomainSearch");
const bankDomainGroups = document.getElementById("bankDomainGroups");
const bankDomainStats = document.getElementById("bankDomainStats");
const profileTestEmailSender = document.getElementById("profileTestEmailSender");
const profileTestEmailSubject = document.getElementById("profileTestEmailSubject");
const profileTestEmailBody = document.getElementById("profileTestEmailBody");
const profileParseEmail = document.getElementById("profileParseEmail");
const profileEmailPreview = document.getElementById("profileEmailPreview");


const BANK_GROUPS = {
	"Private Banks": ["HDFC", "ICICI", "AXIS", "KOTAK", "YES", "INDUSIND", "IDFC", "RBL", "FEDERAL", "SIB", "KVB", "BANDHAN", "AU"],
	"Public Banks": ["SBI", "PNB", "BOI", "BOB", "CANARA", "UNION", "IOB"],
	"Foreign Banks": ["CITI", "HSBC", "SCB", "DBS"],
	"Payments Banks": ["PAYTM", "AIRTEL", "NPCI", "AMAZON", "PHONEPE", "GPAY", "RAZORPAY"],
};

let bankDomainCache = [];
let syncPollInterval = null;

if (profileEmail && storedEmail) profileEmail.value = storedEmail;

const minutesAgo = (value) => {
	if (!value) return "-";
	const diff = Date.now() - new Date(value).getTime();
	return Math.max(1, Math.round(diff / 60000));
};

function stopSyncPolling() {
	if (syncPollInterval) {
		clearInterval(syncPollInterval);
		syncPollInterval = null;
	}
}

function showSyncProgressPanel() {
	if (emailSetupOptions) emailSetupOptions.style.display = "none";
	if (emailStatusPanel) emailStatusPanel.style.display = "none";
	if (emailSyncProgress) emailSyncProgress.style.display = "block";
	if (syncStats) syncStats.style.display = "none";
	if (syncStatusText) syncStatusText.textContent = "Connecting to your inbox...";
}

function showSyncError(errorMessage) {
	if (!emailSyncProgress) return;
	const message = errorMessage || "Unable to complete email sync. Please try again.";
	emailSyncProgress.innerHTML = `
		<div style="text-align:center;padding:16px">
			<div style="width:52px;height:52px;background:#FEF2F2;border-radius:50%;display:flex;align-items:center;justify-content:center;margin:0 auto 14px">
				<i data-lucide="alert-triangle" style="width:26px;height:26px;color:#EF4444"></i>
			</div>
			<div style="font-size:15px;font-weight:700;color:#991B1B;margin-bottom:6px">Sync Failed</div>
			<div style="font-size:12px;color:#64748B;margin-bottom:16px">${message}</div>
			<button class="btn btn-primary" id="retryEmailSyncBtn" type="button" style="font-size:12px;padding:8px 16px">Retry Sync</button>
		</div>
	`;
	const retryBtn = document.getElementById("retryEmailSyncBtn");
	retryBtn?.addEventListener("click", async () => {
		const userId = getUserId();
		await apiFetch(`/api/v1/email-config/check-now?user_id=${userId}`, { method: "POST" });
		showSyncProgressPanel();
		pollSyncStatus(userId);
	});
	if (window.lucide) lucide.createIcons();
}

function showSyncComplete(data) {
	if (!emailSyncProgress) return;
	emailSyncProgress.innerHTML = `
		<div style="text-align:center;padding:16px">
			<div style="width:52px;height:52px;background:#ECFDF5;border-radius:50%;display:flex;align-items:center;justify-content:center;margin:0 auto 14px">
				<i data-lucide="check" style="width:26px;height:26px;color:#10B981"></i>
			</div>
			<div style="font-size:15px;font-weight:700;color:#065F46;margin-bottom:6px">Sync Complete!</div>
			<div style="font-size:12px;color:#64748B;margin-bottom:16px">
				Found <strong>${data.bank_emails_found || 0}</strong> bank emails ->
				<strong>${data.transactions_found || 0}</strong> transactions saved
			</div>
			<div style="display:flex;gap:10px;justify-content:center">
				<a href="/history" class="btn btn-primary" style="font-size:12px;padding:8px 16px">View History</a>
				<a href="/dashboard" class="btn btn-outline" style="font-size:12px;padding:8px 16px">Dashboard</a>
			</div>
		</div>
	`;
	if (window.lucide) lucide.createIcons();
}

function pollSyncStatus(userId) {
	stopSyncPolling();
	syncPollInterval = setInterval(async () => {
		try {
			const data = await apiFetch(`/api/v1/email-config/sync-status?user_id=${userId}`);
			if (syncEmailsFound) syncEmailsFound.textContent = data.bank_emails_found || 0;
			if (syncTxnFound) syncTxnFound.textContent = data.transactions_found || 0;
			if (syncStats) syncStats.style.display = "grid";

			if (data.sync_status === "completed") {
				stopSyncPolling();
				showSyncComplete(data);
				return;
			}

			if (data.sync_status === "error") {
				stopSyncPolling();
				showSyncError(data.last_error);
				return;
			}

			const texts = [
				"Scanning INBOX...",
				"Scanning Promotions folder...",
				"Parsing bank emails...",
				`Found ${data.bank_emails_found || 0} bank emails...`,
				"Extracting transaction details...",
				`Saved ${data.transactions_found || 0} transactions...`,
			];
			const index = Math.floor(Date.now() / 3000) % texts.length;
			if (syncStatusText) syncStatusText.textContent = texts[index];
		} catch (error) {
			console.error("Poll error:", error);
		}
	}, 3000);
}

async function loadEmailStatus() {
	const userId = getUserId();
	const data = await apiFetch(`/api/v1/email-config/status?user_id=${userId}`);
	const syncData = await apiFetch(`/api/v1/email-config/sync-status?user_id=${userId}`);
	if (!data.configured) {
		emailStatusPill.textContent = "Not Connected";
		emailSetupOptions.style.display = "grid";
		emailStatusPanel.style.display = "none";
		if (emailSyncProgress) emailSyncProgress.style.display = "none";
		stopSyncPolling();
		return;
	}

	if (syncData.sync_status === "syncing") {
		showSyncProgressPanel();
		pollSyncStatus(userId);
		return;
	}

	stopSyncPolling();
	if (emailSyncProgress) emailSyncProgress.style.display = "none";
	emailSetupOptions.style.display = "none";
	emailStatusPanel.style.display = "block";
	emailStatusPill.textContent = data.auth_type === "oauth" ? "OAuth Active" : "IMAP Active";
	emailMasked.textContent = data.email_masked || "-";
	emailAuthType.textContent = data.auth_type || "-";
	emailLastChecked.textContent = data.last_checked ? `${minutesAgo(data.last_checked)} min ago` : "-";
	emailProcessed.textContent = data.total_processed;
	emailTransactions.textContent = data.total_transactions;
	if (bankDomainStats && data.whitelisted_domains_count) {
		const scan = data.last_scan_stats || {};
		bankDomainStats.textContent = `${data.whitelisted_domains_count} verified domains | Last scan: ${scan.total_scanned || 0} scanned, ${scan.bank_emails_found || 0} bank emails, ${scan.non_bank_skipped || 0} rejected | Protecting against spam`;
	}
	if (data.last_error) {
		emailLastError.style.display = "block";
		emailLastError.textContent = data.last_error;
	} else {
		emailLastError.style.display = "none";
	}
	emailToggle.textContent = data.is_active ? "Disable" : "Enable";
	emailLog.innerHTML = data.recent_logs
		.map((log) => {
			const label = log.error_message
				? `Error: ${log.error_message}`
				: `Found ${log.transactions_found} transactions`;
			return `<div class="auto-log-item">${new Date(log.time).toLocaleTimeString()} - ${label}</div>`;
		})
		.join("");
}

function groupNameForCode(bankCode) {
	const upper = (bankCode || "").toUpperCase();
	for (const [groupName, codes] of Object.entries(BANK_GROUPS)) {
		if (codes.includes(upper)) return groupName;
	}
	return "Payments Banks";
}

function codeColor(code) {
	const palette = {
		HDFC: "#004C8F",
		SBI: "#2D6DB5",
		ICICI: "#F58220",
		AXIS: "#97144D",
		KOTAK: "#ED1C24",
		YES: "#00539B",
		INDUSIND: "#E31837",
		IDFC: "#9B1F61",
		PNB: "#FF6600",
		BOI: "#003087",
		BOB: "#F7941D",
	};
	return palette[(code || "").toUpperCase()] || "#475569";
}

function renderBankDomains(filterText = "") {
	if (!bankDomainGroups) return;
	const q = (filterText || "").trim().toLowerCase();
	const filtered = bankDomainCache.filter(
		(item) =>
			item.domain.toLowerCase().includes(q) ||
			item.bank_name.toLowerCase().includes(q) ||
			item.bank_code.toLowerCase().includes(q)
	);

	const grouped = {
		"Private Banks": [],
		"Public Banks": [],
		"Foreign Banks": [],
		"Payments Banks": [],
	};

	filtered.forEach((item) => {
		grouped[groupNameForCode(item.bank_code)].push(item);
	});

	const sections = Object.entries(grouped)
		.map(([title, rows]) => {
			if (!rows.length) return "";
			return `
				<div class="bank-domain-group-title">${title}</div>
				${rows
					.map(
						(row) => `
							<div class="bank-domain-row">
								<div class="bank-domain-name">${row.bank_name}</div>
								<div class="bank-domain-pill">${row.domain}</div>
								<span class="bank-code-pill" style="background: ${codeColor(row.bank_code)};">${row.bank_code}</span>
							</div>
						`
					)
					.join("")}
			`;
		})
		.join("");

	bankDomainGroups.innerHTML = sections || '<div class="bank-domain-row"><div class="bank-domain-name">No matching domains</div><div class="bank-domain-pill">-</div><span class="bank-code-pill" style="background:#64748b;">N/A</span></div>';
}

async function loadBankDomains() {
	if (!bankDomainGroups) return;
	const response = await apiFetch("/api/v1/email-config/bank-domains");
	bankDomainCache = response.domains || [];
	const today = new Date().toLocaleDateString("en-IN");
	if (bankDomainStats) {
		bankDomainStats.textContent = `${response.total || 0} verified domains | Last updated: ${today} | Protecting against spam`;
	}
	renderBankDomains(bankDomainSearch?.value || "");
}

async function loadUserCards() {
	if (!pdfCardSelect) return;
	try {
		const userId = getUserId();
		const cards = await apiFetch(`/api/v1/cards/?user_id=${userId}`);
		pdfCardSelect.innerHTML = '<option value="">-- Select Card (Optional) --</option>';
		cards.forEach(card => {
			const option = document.createElement("option");
			option.value = card.id;
			option.dataset.bank = card.bank_name;
			option.textContent = `${card.bank_name} - **** ${card.card_last4} (${card.card_holder_name})`;
			pdfCardSelect.appendChild(option);
		});
	} catch (error) {
		console.error("Failed to load cards:", error);
		pdfCardSelect.innerHTML = '<option value="">Failed to load cards</option>';
	}
}

async function loadPdfUploads() {
	if (!pdfUploadsList) return;
	try {
		const userId = getUserId();
		const uploads = await apiFetch(`/api/v1/pdf/uploads?user_id=${userId}`);
		if (!uploads || uploads.length === 0) {
			pdfUploadsList.innerHTML = '<div style="text-align: center; color: var(--neutral-500); padding: 24px 0; font-size: 13px;">No statement uploads yet.</div>';
			return;
		}
		
		uploads.sort((a, b) => new Date(b.upload_date) - new Date(a.upload_date));
		
		pdfUploadsList.innerHTML = uploads.map(upload => {
			const dateStr = new Date(upload.upload_date).toLocaleDateString("en-IN", {
				day: "numeric", month: "short", hour: "2-digit", minute: "2-digit"
			});
			const bankName = upload.bank_name || "Unknown Bank";
			const count = upload.total_transactions_parsed || 0;
			const status = (upload.status || "processing").toLowerCase();
			const statusLabel = status === "completed" ? `${count} txns` : status;
			
			return `
				<div class="pdf-upload-item">
					<div>
						<div class="filename" title="${upload.filename}">${upload.filename}</div>
						<div class="bank">${bankName}</div>
					</div>
					<div class="meta">
						<span class="status-badge ${status}">${statusLabel}</span>
						<div style="font-size: 10px; color: var(--neutral-500); margin-top: 2px;">${dateStr}</div>
					</div>
				</div>
			`;
		}).join("");
	} catch (error) {
		console.error("Failed to load pdf uploads:", error);
		pdfUploadsList.innerHTML = '<div style="text-align: center; color: var(--danger); padding: 24px 0; font-size: 13px;">Failed to load upload history</div>';
	}
}


profileConnectGmail?.addEventListener("click", () => {
	const userId = getUserId();
	window.location.href = `/api/v1/auth/google/authorize?user_id=${userId}`;
});

profileTestImap?.addEventListener("click", async () => {
	const email = profileEmail.value;
	const password = profileAppPassword.value;
	const result = await apiFetch("/api/v1/email-config/test-connection", {
		method: "POST",
		body: JSON.stringify({ email_address: email, password }),
	});
	showToast(result.message || "Connected", result.success ? "success" : "error");
});

profileSaveImap?.addEventListener("click", async () => {
	const userId = getUserId();
	const email = profileEmail.value;
	const password = profileAppPassword.value;
	const result = await apiFetch("/api/v1/email-config/setup-imap", {
		method: "POST",
		body: JSON.stringify({ user_id: userId, email_address: email, password }),
	});
	showToast(result.message || "Email connected. Fetching all transactions...", "success");
	showSyncProgressPanel();
	pollSyncStatus(userId);
});

emailCheckNow?.addEventListener("click", async () => {
	const userId = getUserId();
	await apiFetch(`/api/v1/email-config/check-now?user_id=${userId}`, { method: "POST" });
	showToast("Email sync started", "info");
	showSyncProgressPanel();
	pollSyncStatus(userId);
});

emailToggle?.addEventListener("click", async () => {
	const userId = getUserId();
	const result = await apiFetch(`/api/v1/email-config/toggle?user_id=${userId}`, { method: "PUT" });
	showToast(result.is_active ? "Email collection enabled" : "Email collection disabled", "info");
	loadEmailStatus();
});

emailDisconnect?.addEventListener("click", async () => {
	const userId = getUserId();
	await apiFetch(`/api/v1/email-config/disconnect?user_id=${userId}`, { method: "DELETE" });
	showToast("Email disconnected", "success");
	loadEmailStatus();
});

const copyValue = async (value) => {
	try {
		await navigator.clipboard.writeText(value);
		showToast("Copied", "success");
	} catch {
		showToast("Copy failed", "error");
	}
};



pdfDropzone?.addEventListener("dragover", (e) => {
	e.preventDefault();
	pdfDropzone.classList.add("dragover");
});

pdfDropzone?.addEventListener("dragleave", () => {
	pdfDropzone.classList.remove("dragover");
});

pdfDropzone?.addEventListener("drop", (e) => {
	e.preventDefault();
	pdfDropzone.classList.remove("dragover");
	const files = e.dataTransfer.files;
	if (files.length > 0) {
		handleSelectedPdf(files[0]);
	}
});

pdfDropzone?.addEventListener("click", () => {
	pdfFile?.click();
});

pdfFile?.addEventListener("change", () => {
	if (pdfFile.files && pdfFile.files.length > 0) {
		handleSelectedPdf(pdfFile.files[0]);
	}
});

function handleSelectedPdf(file) {
	if (!file.name.toLowerCase().endsWith(".pdf")) {
		showToast("Only PDF statement files are allowed", "error");
		if (pdfUploadBtn) pdfUploadBtn.disabled = true;
		if (pdfDropzoneText) pdfDropzoneText.textContent = "Drag & drop PDF or click to browse";
		return;
	}

	const maxBytes = 10 * 1024 * 1024; // 10MB
	if (file.size > maxBytes) {
		showToast("PDF file exceeds maximum limit of 10MB", "error");
		if (pdfUploadBtn) pdfUploadBtn.disabled = true;
		if (pdfDropzoneText) pdfDropzoneText.textContent = "Drag & drop PDF or click to browse";
		return;
	}

	if (pdfDropzoneText) {
		pdfDropzoneText.textContent = `Selected: ${file.name} (${(file.size / (1024 * 1024)).toFixed(2)} MB)`;
	}
	if (pdfUploadBtn) {
		pdfUploadBtn.disabled = false;
	}
}

pdfUploadForm?.addEventListener("submit", async (e) => {
	e.preventDefault();
	
	const file = pdfFile.files && pdfFile.files[0] ? pdfFile.files[0] : null;
	if (!file) {
		showToast("Please select a PDF file first", "error");
		return;
	}

	const userId = getUserId();
	const cardId = pdfCardSelect ? pdfCardSelect.value : "";

	const formData = new FormData();
	formData.append("file", file);

	let uploadUrl = `/api/v1/pdf/upload?user_id=${userId}`;
	if (cardId) uploadUrl += `&card_id=${cardId}`;

	const originalBtnText = pdfUploadBtn.textContent;
	try {
		pdfUploadBtn.disabled = true;
		pdfUploadBtn.textContent = "Uploading & Parsing...";
		
		const result = await apiFetch(uploadUrl, {
			method: "POST",
			body: formData,
			headers: {}
		});

		showToast(`PDF Statement processed successfully! Parsed ${result.total_transactions_parsed || 0} transactions.`, "success");
		
		pdfUploadForm.reset();
		if (pdfDropzoneText) pdfDropzoneText.textContent = "Drag & drop PDF or click to browse";
		pdfUploadBtn.disabled = true;
		
		await loadPdfUploads();
	} catch (error) {
		console.error("PDF upload error:", error);
		showToast(error.message || "Failed to upload and parse PDF", "error");
	} finally {
		pdfUploadBtn.textContent = originalBtnText;
		if (pdfFile.files && pdfFile.files.length > 0) {
			pdfUploadBtn.disabled = false;
		}
	}
});


profileParseEmail?.addEventListener("click", async () => {
	const userId = getUserId();
	const sender = profileTestEmailSender.value;
	const subject = profileTestEmailSubject.value;
	const body = profileTestEmailBody.value;

	if (!body.trim()) {
		showToast("Please enter an email body first", "error");
		return;
	}

	try {
		profileEmailPreview.style.display = "block";
		profileEmailPreview.textContent = "Processing and parsing...";
		
		const result = await apiFetch(`/api/v1/email-config/ingest-test`, {
			method: "POST",
			body: JSON.stringify({
				user_id: userId,
				sender_email: sender,
				subject: subject,
				email_body: body
			})
		});
		
		profileEmailPreview.textContent = JSON.stringify(result, null, 2);
		if (result.success) {
			showToast(result.message || "Email parsed successfully!", "success");
		} else {
			showToast(result.message || "Failed to parse email", "error");
		}
	} catch (error) {
		profileEmailPreview.textContent = `Error: ${error.message}`;
		showToast("Failed to parse test email", "error");
	}
});


async function loadPersonalDetails() {
	const userId = getUserId();
	try {
		const user = await apiFetch(`/api/v1/users/${userId}`);
		const form = document.getElementById("profileForm");
		if (form) {
			form.elements["full_name"].value = user.full_name || "";
			form.elements["email"].value = user.email || "";
			form.elements["phone_number"].value = user.phone_number || "";
			form.elements["date_of_birth"].value = user.date_of_birth || "";
			form.elements["address"].value = user.address || "";
		}
		if (user.created_at) {
			const date = new Date(user.created_at);
			const formattedDate = date.toLocaleDateString("en-US", {
				year: "numeric",
				month: "long",
				day: "numeric",
			});
			const memberSinceEl = document.getElementById("memberSince");
			if (memberSinceEl) {
				memberSinceEl.textContent = `Member since: ${formattedDate}`;
			}
		}
	} catch (err) {
		console.error("Failed to load personal details:", err);
	}
}

document.getElementById("profileForm")?.addEventListener("submit", async (e) => {
	e.preventDefault();
	const userId = getUserId();
	const form = e.target;
	const submitBtn = form.querySelector('button[type="submit"]');

	const payload = {
		full_name: form.elements["full_name"].value.trim(),
		email: form.elements["email"].value.trim(),
		phone_number: form.elements["phone_number"].value.trim() || null,
		date_of_birth: form.elements["date_of_birth"].value || null,
		address: form.elements["address"].value.trim() || null,
	};

	try {
		if (submitBtn) submitBtn.disabled = true;
		const updatedUser = await apiFetch(`/api/v1/users/${userId}`, {
			method: "PUT",
			body: JSON.stringify(payload),
		});

		localStorage.setItem("finadvisor_name", updatedUser.full_name);
		localStorage.setItem("finadvisor_email", updatedUser.email);

		if (profileName) profileName.textContent = updatedUser.full_name;
		if (profileAvatar) {
			const parts = updatedUser.full_name.trim().split(/\s+/).filter(Boolean);
			const first = parts[0]?.[0] || "F";
			const last = parts.length > 1 ? parts[parts.length - 1]?.[0] || "" : "";
			profileAvatar.textContent = (first + last).toUpperCase();
		}

		showToast("Profile updated successfully", "success");
	} catch (err) {
		showToast(err.message || "Failed to update profile", "error");
	} finally {
		if (submitBtn) submitBtn.disabled = false;
	}
});


function initSecurityHandlers() {
	const userId = getUserId();

	// Change Password
	document.getElementById("securityUpdatePasswordBtn")?.addEventListener("click", async () => {
		const currentPassword = document.getElementById("securityCurrentPassword")?.value;
		const newPassword = document.getElementById("securityNewPassword")?.value;
		const confirmPassword = document.getElementById("securityConfirmPassword")?.value;

		if (!currentPassword || !newPassword || !confirmPassword) {
			showToast("All password fields are required", "error");
			return;
		}
		if (newPassword !== confirmPassword) {
			showToast("New passwords do not match", "error");
			return;
		}
		if (newPassword.length < 6) {
			showToast("Password must be at least 6 characters", "error");
			return;
		}

		try {
			const result = await apiFetch(`/api/v1/users/${userId}/change-password`, {
				method: "POST",
				body: JSON.stringify({
					current_password: currentPassword,
					new_password: newPassword,
					confirm_password: confirmPassword,
				}),
			});
			showToast(result.message || "Password updated successfully", "success");

			document.getElementById("securityCurrentPassword").value = "";
			document.getElementById("securityNewPassword").value = "";
			document.getElementById("securityConfirmPassword").value = "";
		} catch (err) {
			showToast(err.message || "Failed to change password", "error");
		}
	});

	// Export CSV
	document.getElementById("profileExportDataBtn")?.addEventListener("click", () => {
		window.location.href = `/api/v1/users/${userId}/export-data`;
	});

	// Delete Account
	document.getElementById("profileDeleteAccountBtn")?.addEventListener("click", async () => {
		if (confirm("WARNING: Are you sure you want to permanently delete your account? All transactions, credit cards, and bank account links will be lost. This action cannot be undone.")) {
			try {
				await apiFetch(`/api/v1/users/${userId}`, { method: "DELETE" });
				showToast("Account deleted successfully", "success");

				localStorage.removeItem("finadvisor_user_id");
				localStorage.removeItem("finadvisor_name");
				localStorage.removeItem("finadvisor_customer_id");
				localStorage.removeItem("finadvisor_email");
				localStorage.removeItem("finadvisor_token");
				window.location.href = "/signin";
			} catch (err) {
				showToast(err.message || "Failed to delete account", "error");
			}
		}
	});
}


async function loadProfileStats() {
	const userId = getUserId();
	try {
		const stats = await apiFetch(`/api/v1/users/${userId}/stats`);
		const cardCountEl = document.getElementById("cardCount");
		const transactionCountEl = document.getElementById("transactionCount");
		if (cardCountEl) {
			cardCountEl.textContent = stats.cards_count;
		}
		if (transactionCountEl) {
			transactionCountEl.textContent = stats.transactions_count;
		}
	} catch (err) {
		console.error("Failed to load profile stats:", err);
	}
}


if (document.getElementById("autoCollectionTab")) {
	loadEmailStatus();
	loadUserCards();
	loadPdfUploads();
	loadBankDomains();
	loadPersonalDetails();
	loadProfileStats();
	initSecurityHandlers();
}

bankDomainSearch?.addEventListener("input", () => {
	renderBankDomains(bankDomainSearch.value);
});


async function loadUserBadges() {
  const userId = getUserId();
  const token = localStorage.getItem("finadvisor_token");
  const grid = document.getElementById("badgesGrid");
  if (!grid || !userId || !token) return;

  grid.innerHTML = `
    <div style="grid-column:1/-1;text-align:center;padding:30px;color:var(--neutral-500);">
      <i data-lucide="loader-2" class="spin" style="width:24px;height:24px;margin-bottom:8px;display:inline-block;"></i>
      <div>Loading achievements...</div>
    </div>
  `;
  if (window.lucide) lucide.createIcons();

  try {
    const response = await fetch(`/api/v1/users/${userId}/badges`, {
      headers: {
        "Authorization": `Bearer ${token}`
      }
    });
    if (!response.ok) {
      grid.innerHTML = `<div style="grid-column:1/-1;text-align:center;color:var(--danger);">Failed to load achievements</div>`;
      return;
    }
    const badges = await response.json();

    // Detect newly unlocked badges
    const prevState = JSON.parse(localStorage.getItem('finadvisor_badges_state') || '{}');
    const newlyUnlocked = [];
    badges.forEach(b => {
      if (b.unlocked && !prevState[b.id]) {
        newlyUnlocked.push(b);
      }
    });
    
    grid.innerHTML = badges.map(b => {
      const icon = b.icon || "award";
      const borderStyle = b.unlocked ? "border:2px solid var(--primary);" : "opacity:0.6;filter:grayscale(80%);border:1px solid var(--neutral-200);";
      const bg = b.unlocked ? "background:var(--primary-light);" : "background:var(--neutral-100);";
      const iconColor = b.unlocked ? "color:var(--primary);" : "color:var(--neutral-400);";
      const isNew = newlyUnlocked.some(nu => nu.id === b.id);
      
      return `
        <div class="glass-card badge-card ${isNew ? 'badge-unlock-anim' : ''}" style="display:flex;flex-direction:column;align-items:center;text-align:center;padding:16px;border-radius:12px;${borderStyle}transition:all 0.2s ease;">
          <div class="badge-icon-wrap" style="width:48px;height:48px;border-radius:50%;display:flex;align-items:center;justify-content:center;margin-bottom:12px;${bg}${iconColor}">
            <i data-lucide="${icon}" style="width:22px;height:22px;"></i>
          </div>
          <div class="badge-title" style="font-size:13px;font-weight:700;color:var(--neutral-900);margin-bottom:4px;">${b.title}</div>
          <div class="badge-desc" style="font-size:10px;color:var(--neutral-500);line-height:1.2;margin-bottom:8px;height:24px;overflow:hidden;">${b.description}</div>
          <div class="badge-status-pill" style="font-size:9px;font-weight:700;padding:2px 8px;border-radius:10px;background:${b.unlocked ? '#D1FAE5' : '#F3F4F6'};color:${b.unlocked ? '#065F46' : '#6B7280'};">
            ${b.unlocked ? "Unlocked" : b.progress}
          </div>
        </div>
      `;
    }).join("");
    
    if (window.lucide) lucide.createIcons();

    // Store current badge state
    const currentState = {};
    badges.forEach(b => { currentState[b.id] = b.unlocked; });
    localStorage.setItem('finadvisor_badges_state', JSON.stringify(currentState));

    // Show toasts for newly unlocked badges
    newlyUnlocked.forEach(b => {
      if (typeof showToast === 'function') {
        showToast(`🏆 Badge unlocked: ${b.title}!`, 'success');
      }
    });
  } catch (error) {
    console.error("Error fetching badges", error);
    grid.innerHTML = `<div style="grid-column:1/-1;text-align:center;color:var(--danger);">Error loading achievements</div>`;
  }
}
