// Trang Lịch làm của tôi: ca đã công bố trong tuần và thông báo xếp ca
let myWeek = null;

document.addEventListener("DOMContentLoaded", () => {
    const user = API.getUser();
    if (!user) return;
    if (!user.ma_nv) {
        document.getElementById("no-profile").classList.remove("hidden");
        return;
    }
    myWeek = getWeekFromUrl(0);
    document.getElementById("week-prev").addEventListener("click", () => changeWeek(-7));
    document.getElementById("week-next").addEventListener("click", () => changeWeek(7));
    document.getElementById("read-all").addEventListener("click", readAll);
    loadMySchedule();
    loadNotifications();
});

function changeWeek(days) {
    myWeek = addDays(myWeek, days);
    setWeekInUrl(myWeek);
    loadMySchedule();
}

async function loadMySchedule() {
    document.getElementById("week-label").textContent = weekRangeLabel(myWeek);
    try {
        const data = await API.request(`/api/shifts/my-schedule?week=${myWeek}`);
        document.getElementById("not-published").classList.toggle("hidden", data.da_cong_bo);
        document.getElementById("total-hours").textContent = data.tong_gio;
        const today = toISODate(new Date());
        document.getElementById("week-days").innerHTML = Array.from({ length: 7 }, (_, i) => {
            const d = addDays(data.tuan_bat_dau, i);
            const shifts = data.ca.filter(c => c.ngay_lam === d);
            const isToday = d === today;
            return `<div class="dash-card p-3 ${isToday ? "ring-2 ring-[#cf6800]" : ""}">
                <div class="text-xs font-bold ${isToday ? "text-[#cf6800]" : "text-[#52525b]"}">${dayLabel(d)}${isToday ? " · Hôm nay" : ""}</div>
                <div class="mt-2 space-y-1.5">
                    ${shifts.length ? shifts.map(c => `
                        <div class="rounded-lg bg-[#fef3c7] px-2 py-1.5">
                            <div class="text-xs font-bold text-[#b45309]">${escapeHtml(c.ten_ca)}</div>
                            <div class="text-[11px] text-[#52525b]">${formatTime(c.gio_bat_dau)} - ${formatTime(c.gio_ket_thuc)}</div>
                        </div>`).join("")
                        : `<div class="text-xs text-[#9ca3af]">${data.da_cong_bo ? "Nghỉ" : "-"}</div>`}
                </div>
            </div>`;
        }).join("");
    } catch (err) {
        showToast(err.message, "error");
    }
}

async function loadNotifications() {
    try {
        const data = await API.request("/api/notifications/me");
        const list = document.getElementById("notif-list");
        if (!data.items.length) {
            list.innerHTML = `<li class="text-[#71717a]">Chưa có thông báo nào</li>`;
            return;
        }
        list.innerHTML = data.items.map(n => `
            <li class="rounded-xl border p-3 ${n.da_doc ? "border-[#f0e9df] bg-white" : "border-amber-300 bg-amber-50"}">
                <a href="${escapeHtml(n.lien_ket || "#")}" onclick="markRead(${n.id})" class="block">
                    <div class="font-semibold text-[#18181b]">${escapeHtml(n.tieu_de)}</div>
                    ${n.noi_dung ? `<div class="text-xs text-[#52525b] mt-1 whitespace-pre-line">${escapeHtml(n.noi_dung)}</div>` : ""}
                    <div class="text-[11px] text-[#9ca3af] mt-1">${formatDateTime(n.ngay_tao + "Z")}</div>
                </a>
            </li>`).join("");
    } catch (err) {
        showToast(err.message, "error");
    }
}

function markRead(id) {
    API.request(`/api/notifications/${id}/read`, { method: "POST" }).catch(() => {});
}

async function readAll() {
    try {
        await API.request("/api/notifications/read-all", { method: "POST" });
        await loadNotifications();
        API.loadNotificationBadge();
    } catch (err) {
        showToast(err.message, "error");
    }
}
