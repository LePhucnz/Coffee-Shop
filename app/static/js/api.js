// API client dùng chung cho các trang sau đăng nhập (Sprint 3+)
// Token và thông tin người dùng được auth.js lưu vào localStorage khi đăng nhập.
const API = {
    getToken() {
        return localStorage.getItem("access_token");
    },

    getUser() {
        try {
            return JSON.parse(localStorage.getItem("user") || "null");
        } catch (e) {
            return null;
        }
    },

    isAdmin() {
        const user = this.getUser();
        return !!user && ["Admin", "Manager"].includes(user.ten_vai_tro);
    },

    requireLogin() {
        const user = this.getUser();
        if (!user || !this.getToken()) {
            window.location.href = "/login";
            return null;
        }
        return user;
    },

    logout() {
        localStorage.removeItem("access_token");
        localStorage.removeItem("refresh_token");
        localStorage.removeItem("user");
        window.location.href = "/login";
    },

    async refreshToken() {
        const refresh = localStorage.getItem("refresh_token");
        if (!refresh) return false;
        try {
            const res = await fetch("/api/auth/refresh", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ refresh_token: refresh })
            });
            if (!res.ok) return false;
            const data = await res.json();
            localStorage.setItem("access_token", data.access_token);
            return true;
        } catch (e) {
            return false;
        }
    },

    async request(url, options = {}, retried = false) {
        const headers = { ...(options.headers || {}) };
        const isForm = options.body instanceof FormData;
        if (options.body && !isForm) headers["Content-Type"] = "application/json";
        const token = this.getToken();
        if (token) headers["Authorization"] = `Bearer ${token}`;

        const res = await fetch(url, {
            ...options,
            headers,
            body: options.body && !isForm && typeof options.body !== "string"
                ? JSON.stringify(options.body)
                : options.body
        });

        // Access token hết hạn: thử refresh một lần rồi gọi lại
        if (res.status === 401 && !retried) {
            if (await this.refreshToken()) {
                return this.request(url, options, true);
            }
            this.logout();
            throw new Error("Phiên đăng nhập đã hết hạn");
        }

        const data = await res.json().catch(() => ({}));
        if (!res.ok) {
            let msg = data.detail || "Đã xảy ra lỗi, vui lòng thử lại";
            if (Array.isArray(msg)) msg = msg.map(d => d.msg).join("; ");
            throw new Error(msg);
        }
        return data;
    },

    upload(url, file) {
        const fd = new FormData();
        fd.append("file", file);
        return this.request(url, { method: "POST", body: fd });
    },

    renderUserCard(user) {
        const nameEl = document.getElementById("nav-user-name");
        const roleEl = document.getElementById("nav-user-role");
        const avatarEl = document.getElementById("nav-avatar");
        const name = user.ho_ten || user.ten_dang_nhap || "?";
        if (nameEl) nameEl.textContent = name;
        if (roleEl) roleEl.textContent = ROLE_LABELS[user.ten_vai_tro] || user.ten_vai_tro || "Nhân viên";
        if (avatarEl) avatarEl.textContent = name.trim().split(" ").pop().charAt(0).toUpperCase();
        // Ẩn menu quản trị với Staff
        if (!this.isAdmin()) {
            document.querySelectorAll(".admin-only").forEach(el => { el.style.display = "none"; });
        }
    }
};

const ROLE_LABELS = {
    Admin: "Quản trị viên",
    Manager: "Quản lý cửa hàng",
    Staff: "Nhân viên"
};

// FR-06: Nhãn trạng thái làm việc
const EMPLOYEE_STATUS = {
    dang_lam: { text: "Đang làm việc", cls: "bg-emerald-100 text-emerald-700" },
    nghi_phep: { text: "Đang nghỉ phép", cls: "bg-amber-100 text-amber-700" },
    da_nghi: { text: "Đã nghỉ việc", cls: "bg-stone-200 text-stone-600" }
};

const CONTRACT_STATUS = {
    hieu_luc: { text: "Hiệu lực", cls: "bg-emerald-100 text-emerald-700" },
    het_han: { text: "Hết hạn", cls: "bg-stone-200 text-stone-600" },
    da_huy: { text: "Đã hủy", cls: "bg-red-100 text-red-700" }
};

function escapeHtml(value) {
    if (value === null || value === undefined) return "";
    return String(value)
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;")
        .replace(/"/g, "&quot;")
        .replace(/'/g, "&#39;");
}

function statusBadge(map, key) {
    const s = map[key] || { text: key || "-", cls: "bg-stone-100 text-stone-600" };
    return `<span class="inline-flex px-2.5 py-1 rounded-full text-xs font-semibold whitespace-nowrap ${s.cls}">${escapeHtml(s.text)}</span>`;
}

function formatDate(value) {
    if (!value) return "-";
    const [y, m, d] = String(value).substring(0, 10).split("-");
    return `${d}/${m}/${y}`;
}

function formatMoney(value) {
    if (value === null || value === undefined || value === "") return "-";
    return Number(value).toLocaleString("vi-VN") + " đ";
}

function showToast(message, type = "success") {
    const container = document.getElementById("toast-container");
    if (!container) {
        alert(message);
        return;
    }
    const colors = {
        success: "bg-emerald-600",
        error: "bg-red-600",
        warning: "bg-amber-600",
        info: "bg-stone-800"
    };
    const toast = document.createElement("div");
    toast.className = `px-4 py-3 rounded-xl shadow-lg text-sm font-medium text-white fade-in ${colors[type] || colors.info}`;
    toast.textContent = message;
    container.appendChild(toast);
    setTimeout(() => toast.remove(), 4000);
}
window.showToast = showToast;
