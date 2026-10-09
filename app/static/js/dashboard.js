// Dashboard UI Logic & Interactive Elements
document.addEventListener("DOMContentLoaded", () => {
    // Current date display in Vietnamese
    const dateSubtitle = document.getElementById("current-date-label");
    if (dateSubtitle) {
        const days = ["Chủ Nhật", "Thứ Hai", "Thứ Ba", "Thứ Tư", "Thứ Năm", "Thứ Sáu", "Thứ Bảy"];
        const now = new Date();
        const dayName = days[now.getDay()];
        const day = String(now.getDate()).padStart(2, "0");
        const month = String(now.getMonth() + 1).padStart(2, "0");
        const year = now.getFullYear();
        dateSubtitle.innerText = `Hôm nay, ${dayName} ${day} tháng ${month}, ${year}`;
    }

    // Chart bar tooltip display
    const chartBars = document.querySelectorAll(".chart-bar");
    const chartTooltip = document.getElementById("chart-tooltip");

    chartBars.forEach(bar => {
        bar.addEventListener("mouseenter", (e) => {
            const label = bar.getAttribute("data-label");
            const hours = bar.getAttribute("data-hours");
            if (chartTooltip) {
                chartTooltip.innerHTML = `<strong>Tháng ${label}:</strong> ${hours} giờ làm`;
                chartTooltip.classList.remove("opacity-0");
            }
        });

        bar.addEventListener("mouseleave", () => {
            if (chartTooltip) {
                chartTooltip.classList.add("opacity-0");
            }
        });
    });

    // Số liệu thật từ API (Sprint 3)
    loadDashboardStats();

    // Quick shortcut button actions
    document.querySelectorAll(".shortcut-btn").forEach(btn => {
        btn.addEventListener("click", (e) => {
            e.preventDefault();
            const action = btn.innerText.trim();
            if (window.showToast) {
                window.showToast(`Đang mở: ${action}`, "info");
            } else {
                alert(`Chức năng: ${action}`);
            }
        });
    });
});

async function loadDashboardStats() {
    if (typeof API === "undefined" || !API.getUser()) return;
    try {
        const stats = await API.request("/api/system/stats");
        const empEl = document.getElementById("stat-employees");
        if (empEl) empEl.textContent = stats.active_employees;

        // FR-05: Cảnh báo Admin/Manager khi có hợp đồng sắp hết hạn
        const banner = document.getElementById("expiring-banner");
        if (banner && API.isAdmin() && stats.expiring_contracts > 0) {
            document.getElementById("expiring-banner-count").textContent = stats.expiring_contracts;
            banner.classList.remove("hidden");
        }
    } catch (e) {
        // Giữ nguyên giao diện nếu không lấy được thống kê
    }

    // Sprint 4: số ca hôm nay và số ô ca thiếu người trong tuần (chỉ Admin/Manager)
    if (!API.isAdmin()) return;
    try {
        const shifts = await API.request("/api/shifts/today");
        document.getElementById("stat-shifts-today").textContent = shifts.so_ca_hom_nay;
        document.getElementById("stat-understaffed").textContent =
            shifts.so_o_thieu_tuan_nay === null ? "Chưa xếp" : shifts.so_o_thieu_tuan_nay;
    } catch (e) {
        // Bỏ qua nếu chưa có dữ liệu ca
    }
}
