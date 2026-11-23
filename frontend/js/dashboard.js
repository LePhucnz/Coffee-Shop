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
