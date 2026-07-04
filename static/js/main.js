(function() {
  const publicPages = ["/", "/login", "/register", "/signin", "/signup"];
  const currentPath = window.location.pathname;
  const token = localStorage.getItem("finadvisor_token");
  
  if (!publicPages.includes(currentPath) && !token) {
    window.location.href = "/login";
    return;
  }

  const originalFetch = window.fetch;
  window.fetch = async function (url, options = {}) {
    const activeToken = localStorage.getItem("finadvisor_token");
    if (activeToken) {
      options.headers = options.headers || {};
      if (!options.headers["Authorization"]) {
        options.headers["Authorization"] = `Bearer ${activeToken}`;
      }
    }
    const response = await originalFetch(url, options);
    if (response.status === 401 && url.includes("/api/v1/") && !url.includes("/api/v1/auth/")) {
      localStorage.removeItem("finadvisor_token");
      localStorage.removeItem("finadvisor_user_id");
      window.location.href = "/login";
    }
    return response;
  };
})();

function applySavedTheme() {
  const theme = localStorage.getItem("finadvisor_theme") || "default";
  document.body.className = "";
  if (theme !== "default") {
    document.body.classList.add(`theme-${theme}`);
  }
  window.dispatchEvent(new Event("themeChanged"));
}

function openThemeSelector() {
  const existing = document.getElementById("themeSelectorModal");
  if (existing) existing.remove();

  const theme = localStorage.getItem("finadvisor_theme") || "default";

  const modalHtml = `
    <div class="modal-overlay" id="themeSelectorModal" style="position:fixed;inset:0;background:rgba(15,23,42,0.65);display:flex;justify-content:center;align-items:center;z-index:9999;backdrop-filter:blur(6px);animation:fadeIn 0.2s ease;">
      <style>
        @keyframes fadeIn { from { opacity: 0; } to { opacity: 1; } }
        @keyframes scaleUp { from { transform: scale(0.95); opacity: 0; } to { transform: scale(1); opacity: 1; } }
        
        .theme-modal-card {
          background: var(--neutral-50, white);
          border-radius: 20px;
          border: 1px solid var(--neutral-100, #e2e8f0);
          width: min(360px, 92vw);
          padding: 24px;
          box-shadow: 0 20px 50px rgba(0,0,0,0.2);
          animation: scaleUp 0.25s cubic-bezier(0.34, 1.56, 0.64, 1);
          position: relative;
        }
        
        .theme-option-card {
          display: flex;
          align-items: center;
          justify-content: space-between;
          padding: 16px;
          border-radius: 12px;
          border: 2px solid var(--neutral-100, #cbd5e1);
          cursor: pointer;
          transition: all 0.2s ease;
          background: rgba(255, 255, 255, 0.03);
          margin-top: 12px;
        }
        
        .theme-option-card:hover {
          border-color: var(--primary) !important;
          background: var(--primary-light) !important;
          transform: translateY(-2px);
        }
        
        .theme-option-card.active {
          border-color: var(--primary) !important;
          background: var(--primary-light) !important;
        }

        .theme-color-dot {
          width: 14px;
          height: 14px;
          border-radius: 50%;
          display: inline-block;
          border: 1px solid rgba(0,0,0,0.1);
        }
      </style>
      <div class="theme-modal-card">
        <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:8px;">
          <h3 style="margin:0;font-size:18px;font-weight:700;color:var(--neutral-900);">Select Theme</h3>
          <button id="closeThemeModal" style="background:none;border:none;cursor:pointer;font-size:24px;color:var(--neutral-500);display:flex;align-items:center;justify-content:center;padding:0;width:30px;height:30px;line-height:30px;">&times;</button>
        </div>
        <div style="display:flex;flex-direction:column;gap:4px;">
          <!-- Default -->
          <div class="theme-option-card ${theme === 'default' ? 'active' : ''}" data-theme="default">
            <div style="display:flex;align-items:center;gap:12px;">
              <div style="display:flex;gap:4px;">
                <span class="theme-color-dot" style="background:#f4f7ff;"></span>
                <span class="theme-color-dot" style="background:#4f46e5;"></span>
              </div>
              <span style="font-weight:600;font-size:14px;color:var(--neutral-900);">Default Light</span>
            </div>
            <div class="theme-check-icon" style="font-size:16px;color:var(--primary);font-weight:700;">${theme === 'default' ? '✓' : ''}</div>
          </div>
          <!-- Graphite -->
          <div class="theme-option-card ${theme === 'graphite' ? 'active' : ''}" data-theme="graphite">
            <div style="display:flex;align-items:center;gap:12px;">
              <div style="display:flex;gap:4px;">
                <span class="theme-color-dot" style="background:#18181b;border-color:#3f3f46;"></span>
                <span class="theme-color-dot" style="background:#3b82f6;"></span>
              </div>
              <span style="font-weight:600;font-size:14px;color:var(--neutral-900);">Graphite Dark</span>
            </div>
            <div class="theme-check-icon" style="font-size:16px;color:var(--primary);font-weight:700;">${theme === 'graphite' ? '✓' : ''}</div>
          </div>
          <!-- Warm Charcoal -->
          <div class="theme-option-card ${theme === 'warmcharcoal' ? 'active' : ''}" data-theme="warmcharcoal">
            <div style="display:flex;align-items:center;gap:12px;">
              <div style="display:flex;gap:4px;">
                <span class="theme-color-dot" style="background:#1c1917;border-color:#3d3530;"></span>
                <span class="theme-color-dot" style="background:#f59e0b;"></span>
              </div>
              <span style="font-weight:600;font-size:14px;color:var(--neutral-900);">Warm Charcoal</span>
            </div>
            <div class="theme-check-icon" style="font-size:16px;color:var(--primary);font-weight:700;">${theme === 'warmcharcoal' ? '✓' : ''}</div>
          </div>
          <!-- Emerald Mint -->
          <div class="theme-option-card ${theme === 'emeraldmint' ? 'active' : ''}" data-theme="emeraldmint">
            <div style="display:flex;align-items:center;gap:12px;">
              <div style="display:flex;gap:4px;">
                <span class="theme-color-dot" style="background:#f0fdf4;"></span>
                <span class="theme-color-dot" style="background:#059669;"></span>
              </div>
              <span style="font-weight:600;font-size:14px;color:var(--neutral-900);">Emerald Mint</span>
            </div>
            <div class="theme-check-icon" style="font-size:16px;color:var(--primary);font-weight:700;">${theme === 'emeraldmint' ? '✓' : ''}</div>
          </div>
        </div>
      </div>
    </div>
  `;

  document.body.insertAdjacentHTML("beforeend", modalHtml);

  const modal = document.getElementById("themeSelectorModal");
  
  const closeModal = () => {
    modal.style.opacity = "0";
    modal.style.transition = "opacity 0.15s ease";
    setTimeout(() => modal.remove(), 150);
  };

  modal.querySelector("#closeThemeModal").addEventListener("click", closeModal);
  modal.addEventListener("click", (e) => {
    if (e.target === modal) closeModal();
  });

  modal.querySelectorAll(".theme-option-card").forEach((card) => {
    card.addEventListener("click", () => {
      const selectedTheme = card.dataset.theme;
      localStorage.setItem("finadvisor_theme", selectedTheme);
      applySavedTheme();
      
      modal.querySelectorAll(".theme-option-card").forEach((c) => {
        c.classList.toggle("active", c.dataset.theme === selectedTheme);
        c.querySelector(".theme-check-icon").textContent = c.dataset.theme === selectedTheme ? "✓" : "";
      });

      const readableNames = {
        default: 'Default Light',
        graphite: 'Graphite Dark',
        warmcharcoal: 'Warm Charcoal',
        emeraldmint: 'Emerald Mint'
      };
      showToast(`Theme changed to ${readableNames[selectedTheme] || selectedTheme}`, "success");
      setTimeout(closeModal, 200);
    });
  });
}

applySavedTheme();

function showToast(message, type = "info") {
  const colors = {
    success: "#10B981",
    error: "#EF4444",
    warning: "#F59E0B",
    info: "#2563EB",
  };
  const toast = document.createElement("div");
  toast.style.cssText = `
    position: fixed; bottom: 24px; right: 24px; z-index: 9999;
    background: white; color: #0F172A;
    border-left: 4px solid ${colors[type]};
    border-radius: 8px; padding: 12px 16px;
    box-shadow: 0 4px 24px rgba(0,0,0,0.12);
    font-size: 13px; max-width: 320px;
    animation: slideIn 0.3s ease;
  `;
  toast.textContent = message;
  document.body.appendChild(toast);
  setTimeout(() => toast.remove(), 3500);
}

function getUserId() {
  return localStorage.getItem("finadvisor_user_id") || "00000000-0000-0000-0000-000000000001";
}


function normalizeErrorMessage(detail) {
  if (detail == null) return "Request failed";
  if (typeof detail === "string") return detail;
  if (Array.isArray(detail)) {
    return detail
      .map((item) => item?.msg || item?.message || JSON.stringify(item))
      .join(", ");
  }
  if (typeof detail === "object") {
    return detail.msg || detail.message || JSON.stringify(detail);
  }
  return String(detail);
}

async function apiFetch(url, options = {}) {
  try {
    const response = await fetch(url, {
      headers: { "Content-Type": "application/json" },
      ...options,
    });
    if (!response.ok) {
      const data = await response.json().catch(() => ({}));
      const message = normalizeErrorMessage(data.detail || data.message || data);
      throw new Error(message);
    }
    return await response.json();
  } catch (error) {
    const message = normalizeErrorMessage(error?.message || error);
    showToast(message, "error");
    throw error;
  }
}

function setActiveNav() {
  const currentPath = window.location.pathname.replace(/\/+$/, "") || "/";
  document.querySelectorAll(".nav-link").forEach((link) => {
    const linkPath = new URL(link.href).pathname.replace(/\/+$/, "") || "/";
    if (linkPath === currentPath) {
      link.classList.add("active");
    } else {
      link.classList.remove("active");
    }
  });
}

function getInitials(name) {
  const parts = (name || "").trim().split(/\s+/).filter(Boolean);
  if (parts.length === 0) return "FN";
  const first = parts[0][0] || "";
  const last = parts.length > 1 ? parts[parts.length - 1][0] || "" : "";
  return (first + last).toUpperCase() || "FN";
}

function hydrateUserBadges() {
  const name = localStorage.getItem("finadvisor_name") || "";
  const customerId = localStorage.getItem("finadvisor_customer_id") || "";
  const avatar = document.getElementById("avatar");
  const customerPill = document.getElementById("customerId");
  if (avatar) avatar.textContent = getInitials(name);
  if (customerPill && customerId) customerPill.textContent = customerId;
}

function formatTimeAgo(dateStr) {
  if (!dateStr) return "-";
  const diffMs = Date.now() - new Date(dateStr).getTime();
  const diffMins = Math.floor(diffMs / 60000);
  if (diffMins < 1) return "Just now";
  if (diffMins < 60) return `${diffMins}m ago`;
  const diffHours = Math.floor(diffMins / 60);
  if (diffHours < 24) return `${diffHours}h ago`;
  const diffDays = Math.floor(diffHours / 24);
  return `${diffDays}d ago`;
}


document.addEventListener("DOMContentLoaded", () => {
  if (window.lucide) lucide.createIcons();
  setActiveNav();
  hydrateUserBadges();

  if (window.location.pathname.includes("/profile")) {
    const customerPill = document.getElementById("customerId");
    if (customerPill) {
      customerPill.innerHTML = `
        <svg viewBox="0 0 512 512" width="18" height="18" fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" stroke-width="38" style="display:inline-block;vertical-align:middle;">
          <path d="M452.37 59.63h0a40.49 40.49 0 00-57.26 0L184 294.74c23.08 4.7 46.12 27.29 49.26 49.26l219.11-227.11a40.49 40.49 0 000-57.26zM138 336c-29.88 0-54 24.5-54 54.86 0 23.95-20.88 36.57-36 36.57C64.56 449.74 92.82 464 120 464c39.78 0 72-32.73 72-73.14 0-30.36-24.12-54.86-54-54.86z" />
          <circle cx="420" cy="92" r="14" fill="currentColor" stroke="none" />
        </svg>
      `;
      customerPill.style.cursor = "pointer";
      customerPill.title = "Select Theme";
      customerPill.classList.add("theme-switcher");
      customerPill.addEventListener("click", openThemeSelector);
    }
  }

  const menuButton = document.getElementById("mobileMenuButton");
  const navLinks = document.getElementById("navLinks");
  if (menuButton && navLinks) {
    menuButton.addEventListener("click", () => {
      navLinks.classList.toggle("mobile-open");
    });
  }

  // --- Notification Event Listeners Setup ---
  loadNotifications();
  connectNotificationStream();

  const notifBellBtn = document.getElementById("notifBellBtn");
  const notifDropdown = document.getElementById("notifDropdown");
  const clearNotifBtn = document.getElementById("clearNotifBtn");

  if (notifBellBtn && notifDropdown) {
    notifBellBtn.addEventListener("click", (e) => {
      e.stopPropagation();
      notifDropdown.classList.toggle("hidden");
      loadNotifications();
    });

    document.addEventListener("click", (e) => {
      if (!notifDropdown.contains(e.target) && e.target !== notifBellBtn) {
        notifDropdown.classList.add("hidden");
      }
    });
  }

  if (clearNotifBtn) {
    clearNotifBtn.addEventListener("click", () => {
      const list = document.getElementById("notifDropdownList");
      if (!list) return;
      const items = list.querySelectorAll(".notif-item");
      const clickedIds = JSON.parse(localStorage.getItem("finadvisor_read_notifs") || "[]");
      items.forEach(item => {
        const id = item.dataset.id;
        if (!clickedIds.includes(id)) {
          clickedIds.push(id);
        }
      });
      localStorage.setItem("finadvisor_read_notifs", JSON.stringify(clickedIds));
      loadNotifications();
    });
  }
});

// --- Live Notification UI and EventStream (SSE) integration ---
let notifEventSource = null;

async function loadNotifications() {
  const userId = getUserId();
  const token = localStorage.getItem("finadvisor_token");
  if (!userId || !token) return;

  try {
    const response = await fetch(`/api/v1/notifications/${userId}`, {
      headers: {
        "Authorization": `Bearer ${token}`
      }
    });
    if (!response.ok) return;
    const notifications = await response.json();
    renderNotifications(notifications);
  } catch (error) {
    console.error("Error loading notifications", error);
  }
}

function renderNotifications(notifications) {
  const list = document.getElementById("notifDropdownList");
  const badge = document.getElementById("notifBadge");
  if (!list) return;

  const clickedIds = JSON.parse(localStorage.getItem("finadvisor_read_notifs") || "[]");
  const unreadList = notifications.filter(n => n.unread && !clickedIds.includes(n.id));
  const unreadCount = unreadList.length;

  if (badge) {
    if (unreadCount > 0) {
      badge.textContent = unreadCount;
      badge.classList.remove("hidden");
    } else {
      badge.classList.add("hidden");
    }
  }

  if (notifications.length === 0) {
    list.innerHTML = `<div class="notif-empty-state">No new notifications</div>`;
    return;
  }

  const icons = {
    reminder: "calendar",
    statement: "file-text",
    transaction: "credit-card"
  };

  list.innerHTML = notifications.map(n => {
    const isUnread = n.unread && !clickedIds.includes(n.id);
    const icon = icons[n.type] || "bell";
    const timeStr = formatTimeAgo(n.timestamp);
    return `
      <div class="notif-item ${isUnread ? 'unread' : ''}" data-id="${n.id}">
        <div class="notif-item-icon">
          <i data-lucide="${icon}"></i>
        </div>
        <div class="notif-item-content">
          <div class="notif-item-title">${n.title}</div>
          <div class="notif-item-meta">${n.meta}</div>
          <div class="notif-item-time">${timeStr}</div>
        </div>
      </div>
    `;
  }).join("");

  if (window.lucide) lucide.createIcons();

  list.querySelectorAll(".notif-item").forEach(item => {
    item.addEventListener("click", () => {
      const id = item.dataset.id;
      if (!clickedIds.includes(id)) {
        clickedIds.push(id);
        localStorage.setItem("finadvisor_read_notifs", JSON.stringify(clickedIds));
      }
      item.classList.remove("unread");
      const newUnreadCount = notifications.filter(n => n.unread && !clickedIds.includes(n.id)).length;
      if (badge) {
        if (newUnreadCount > 0) {
          badge.textContent = newUnreadCount;
        } else {
          badge.classList.add("hidden");
        }
      }
    });
  });
}

function connectNotificationStream() {
  const userId = getUserId();
  const token = localStorage.getItem("finadvisor_token");
  if (!userId || !token) return;

  if (notifEventSource) {
    notifEventSource.close();
  }

  notifEventSource = new EventSource(`/api/v1/notifications/stream/${userId}?token=${encodeURIComponent(token)}`);

  notifEventSource.onmessage = (event) => {
    try {
      const data = JSON.parse(event.data);
      playNotificationSound();
      showToast(`${data.title}: ${data.meta}`, "info");
      loadNotifications();
      window.dispatchEvent(new CustomEvent("realtimeNotification", { detail: data }));
    } catch (e) {
      console.error("Error parsing live notification event", e);
    }
  };

  notifEventSource.onerror = (err) => {
    console.error("SSE stream error", err);
  };
}

function playNotificationSound() {
  try {
    const context = new (window.AudioContext || window.webkitAudioContext)();
    const osc = context.createOscillator();
    const gain = context.createGain();
    
    osc.type = "sine";
    osc.frequency.setValueAtTime(587.33, context.currentTime); // D5
    osc.frequency.setValueAtTime(880, context.currentTime + 0.1); // A5
    
    gain.gain.setValueAtTime(0.08, context.currentTime);
    gain.gain.exponentialRampToValueAtTime(0.01, context.currentTime + 0.35);
    
    osc.connect(gain);
    gain.connect(context.destination);
    
    osc.start();
    osc.stop(context.currentTime + 0.35);
  } catch (e) {
    // Audio Context blocked by user gesture
  }
}

