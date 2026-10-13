// Sprint 5 - Màn 13: cài đặt chấm công (chỉ Admin được lưu)
let settings = null;

document.addEventListener("DOMContentLoaded", () => {
    if (!API.isAdmin()) return;
    document.getElementById("settings-form").addEventListener("submit", save);
    document.getElementById("btn-here").addEventListener("click", useMyLocation);
    load();
});

async function load() {
    try {
        settings = await API.request("/api/attendance/settings");
        const form = document.getElementById("settings-form");
        Object.entries(settings).forEach(([k, v]) => {
            if (form.elements[k]) form.elements[k].value = v === null || v === undefined ? "" : v;
        });
        document.getElementById("store-name").textContent = settings.ten_cua_hang || "";
        document.getElementById("updated").textContent = settings.ngay_cap_nhat ? `Cập nhật lần cuối: ${formatDateTime(settings.ngay_cap_nhat)}` : "";
        const readonly = !settings.co_the_sua;
        document.getElementById("readonly-note").classList.toggle("hidden", !readonly);
        form.querySelectorAll("input, button").forEach(el => { el.disabled = readonly; });
    } catch (err) {
        showToast(err.message, "error");
    }
}

function useMyLocation() {
    if (!navigator.geolocation) return showToast("Trình duyệt không hỗ trợ GPS", "error");
    navigator.geolocation.getCurrentPosition(pos => {
        const form = document.getElementById("settings-form");
        form.elements.vi_do_quan.value = pos.coords.latitude.toFixed(6);
        form.elements.kinh_do_quan.value = pos.coords.longitude.toFixed(6);
        showToast("Đã điền vị trí hiện tại, bấm Lưu để áp dụng", "info");
    }, () => showToast("Không lấy được vị trí", "error"), { enableHighAccuracy: true, timeout: 15000 });
}

async function save(e) {
    e.preventDefault();
    const form = document.getElementById("settings-form");
    const body = { ...settings };
    Array.from(form.elements).forEach(el => {
        if (!el.name) return;
        if (el.type === "number") body[el.name] = el.value === "" ? null : Number(el.value);
        else body[el.name] = el.value.trim();
    });
    if (!confirm("Lưu cài đặt? Thay đổi áp dụng cho các ca bắt đầu sau thời điểm lưu.")) return;
    try {
        settings = await API.request("/api/attendance/settings", { method: "PUT", body });
        showToast("Đã lưu cài đặt chấm công");
        load();
    } catch (err) {
        showToast(err.message, "error");
    }
}
