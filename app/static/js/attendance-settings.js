// Sprint 5 - Màn 13: cài đặt chấm công (Admin / Manager được lưu)
let settings = null;

document.addEventListener("DOMContentLoaded", () => {
    if (!API.isAdmin()) return;
    document.getElementById("settings-form").addEventListener("submit", save);
    document.getElementById("btn-here").addEventListener("click", useMyLocation);
    const btnDefault = document.getElementById("btn-default-store");
    if (btnDefault) {
        btnDefault.addEventListener("click", () => {
            const form = document.getElementById("settings-form");
            form.elements.vi_do_quan.value = (10.8505).toFixed(6);
            form.elements.kinh_do_quan.value = (106.7719).toFixed(6);
            showToast("Đã điền tọa độ cơ sở Thủ Đức (10.850500, 106.771900)", "info");
        });
    }
    load();
});

async function load() {
    try {
        settings = await API.request("/api/attendance/settings");
        const form = document.getElementById("settings-form");
        Object.entries(settings).forEach(([k, v]) => {
            if (form.elements[k]) form.elements[k].value = v === null || v === undefined ? "" : v;
        });
        const storeNameEl = document.getElementById("store-name");
        if (storeNameEl) {
            storeNameEl.textContent = settings.ten_cua_hang ? `Cơ sở: ${settings.ten_cua_hang}` : "";
        }
        document.getElementById("updated").textContent = settings.ngay_cap_nhat ? `Cập nhật lần cuối: ${formatDateTime(settings.ngay_cap_nhat)}` : "";
        const readonly = !settings.co_the_sua;
        document.getElementById("readonly-note").classList.toggle("hidden", !readonly);
        form.querySelectorAll("input, button").forEach(el => { el.disabled = readonly; });
    } catch (err) {
        showToast(err.message, "error");
    }
}

function useMyLocation() {
    const btn = document.getElementById("btn-here");
    const label = document.getElementById("btn-here-text") || btn;
    const originalText = label.textContent;

    if (!navigator.geolocation) {
        return showToast("Trình duyệt không hỗ trợ Geolocation hoặc trang web cần chạy trên HTTPS / localhost", "error");
    }

    btn.disabled = true;
    label.textContent = "Đang lấy vị trí GPS...";

    const form = document.getElementById("settings-form");

    function onSuccess(pos) {
        btn.disabled = false;
        label.textContent = originalText;
        const lat = pos.coords.latitude.toFixed(6);
        const lon = pos.coords.longitude.toFixed(6);
        form.elements.vi_do_quan.value = lat;
        form.elements.kinh_do_quan.value = lon;
        showToast(`Đã lấy vị trí GPS thành công: ${lat}, ${lon}`, "info");
    }

    function onError(err) {
        // Nếu thử high accuracy thất bại hoặc timeout, thử lại low accuracy (Wi-Fi / IP)
        if (err && (err.code === 2 || err.code === 3)) {
            navigator.geolocation.getCurrentPosition(
                onSuccess,
                (fallbackErr) => {
                    btn.disabled = false;
                    label.textContent = originalText;
                    let msg = "Không lấy được vị trí GPS.";
                    if (fallbackErr.code === 1) msg = "Trình duyệt chưa được cấp quyền truy cập vị trí.";
                    else if (fallbackErr.code === 2) msg = "Thiết bị không xác định được vị trí GPS.";
                    else if (fallbackErr.code === 3) msg = "Quá thời gian chờ lấy vị trí GPS.";
                    showToast(msg, "error");
                },
                { enableHighAccuracy: false, timeout: 10000, maximumAge: 60000 }
            );
            return;
        }

        btn.disabled = false;
        label.textContent = originalText;
        let msg = "Không lấy được vị trí GPS.";
        if (err && err.code === 1) msg = "Trình duyệt chưa được cấp quyền truy cập vị trí. Vui lòng cho phép quyền vị trí trên thanh địa chỉ.";
        showToast(msg, "error");
    }

    navigator.geolocation.getCurrentPosition(
        onSuccess,
        onError,
        { enableHighAccuracy: true, timeout: 8000, maximumAge: 0 }
    );
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
        showToast("Đã lưu cài đặt chấm công thành công");
        load();
    } catch (err) {
        showToast(err.message, "error");
    }
}
