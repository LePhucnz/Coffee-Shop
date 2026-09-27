// Centralized API Client & Auth Handling
const API = {
    getToken() {
        return localStorage.getItem("access_token");
    },
    getRefreshToken() {
        return localStorage.getItem("refresh_token");
    },
    getUser() {
        const u = localStorage.getItem("current_user");
        return u ? JSON.parse(u) : null;
    },
    setSession(tokenResponse) {
        localStorage.setItem("access_token", tokenResponse.access_token);
        localStorage.setItem("refresh_token", tokenResponse.refresh_token);
        if (tokenResponse.user) {
            localStorage.setItem("current_user", JSON.stringify(tokenResponse.user));
        }
        // Save to cookie as well for server-side fallback
        document.cookie = `access_token=${tokenResponse.access_token}; path=/; max-age=86400`;
    },
    clearSession() {
        localStorage.removeItem("access_token");
        localStorage.removeItem("refresh_token");
        localStorage.removeItem("current_user");
        document.cookie = "access_token=; path=/; max-age=0";
    },
    async request(url, options = {}) {
        options.headers = options.headers || {};
        if (!(options.body instanceof FormData)) {
            options.headers["Content-Type"] = "application/json";
        }
        const token = this.getToken();
        if (token) {
            options.headers["Authorization"] = `Bearer ${token}`;
        }

        try {
            let res = await fetch(url, options);

            // Handle 401 Unauthorized -> Try refresh token
            if (res.status === 401 && this.getRefreshToken()) {
                const refreshed = await this.refreshToken();
                if (refreshed) {
                    options.headers["Authorization"] = `Bearer ${this.getToken()}`;
                    res = await fetch(url, options);
                } else {
                    this.clearSession();
                    if (!window.location.pathname.includes("/login")) {
                        window.location.href = "/login";
                    }
                    return null;
                }
            }

            const data = await res.json().catch(() => ({}));
            if (!res.ok) {
                const msg = data.detail || "Đã xảy ra lỗi, vui lòng thử lại!";
                throw new Error(msg);
            }
            return data;
        } catch (err) {
            throw err;
        }
    },
    async refreshToken() {
        const refresh = this.getRefreshToken();
        if (!refresh) return false;
        try {
            const res = await fetch("/api/auth/refresh", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ refresh_token: refresh })
            });
            if (res.ok) {
                const data = await res.json();
                localStorage.setItem("access_token", data.access_token);
                document.cookie = `access_token=${data.access_token}; path=/; max-age=86400`;
                return true;
            }
        } catch (e) {
            console.error("Lỗi khi refresh token:", e);
        }
        return false;
    }
};

// UI Toast Notification Utility
function showToast(message, type = "success") {
    let container = document.getElementById("toast-container");
    if (!container) {
        container = document.createElement("div");
        container.id = "toast-container";
        document.body.appendChild(container);
    }

    const toast = document.createElement("div");
    const colors = {
        success: "bg-emerald-600 text-white",
        error: "bg-red-600 text-white",
        warning: "bg-amber-600 text-white",
        info: "bg-blue-600 text-white"
    };

    toast.className = `px-4 py-3 rounded-lg shadow-lg text-sm font-medium flex items-center gap-3 fade-in ${colors[type] || colors.info}`;
    toast.innerHTML = `
        <span>${message}</span>
        <button onclick="this.parentElement.remove()" class="ml-2 hover:opacity-80">✕</button>
    `;

    container.appendChild(toast);
    setTimeout(() => {
        if (toast.parentElement) toast.remove();
    }, 4500);
}

function checkAuthRedirect() {
    const user = API.getUser();
    if (!user && !window.location.pathname.includes("/login")) {
        window.location.href = "/login";
    }
}
