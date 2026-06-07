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

  const menuButton = document.getElementById("mobileMenuButton");
  const navLinks = document.getElementById("navLinks");
  if (menuButton && navLinks) {
    menuButton.addEventListener("click", () => {
      navLinks.classList.toggle("mobile-open");
    });
  }
});

