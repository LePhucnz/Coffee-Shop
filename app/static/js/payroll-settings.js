// Sprint 6 - Cài đặt lương: đơn giá giờ, phạt trễ/sớm, thưởng chuyên cần, hệ số ca, ngày lễ (FR-12)
let settings = null;
const NUMBER_FIELDS = ["gio_chuan_thang", "nguong_luong_thang", "phat_moi_phut", "phat_moi_lan", "phat_vang_moi_lan",
    "thuong_chuyen_can", "chuyen_can_so_ca_toi_thieu"];

document.addEventListener("DOMContentLoaded", () => {
    if (!API.isAdmin()) return;
    document.getElementById("settings-form").addEventListener("submit", save);
    document.getElementById("settings-form").addEventListener("input", updateExample);
    document.getElementById("holiday-form").addEventListener("submit", addHoliday);
    load();
});

async function load() {
    try {
        fill(await API.request("/api/payroll/settings"));
    } catch (err) {
        showToast(err.message, "error");
    }
}

function fill(data) {
    settings = data;
    const form = document.getElementById("settings-form");
    NUMBER_FIELDS.forEach(name => { form.elements[name].value = data[name]; });
    form.querySelectorAll('input[name="cach_phat"]').forEach(r => { r.checked = r.value === data.cach_phat; });
    form.elements.chuyen_can_ky_tuan.checked = !!data.chuyen_can_ky_tuan;
    document.getElementById("shift-coefs").innerHTML = data.he_so_ca.map(h => `
        <div class="flex items-center justify-between gap-3 py-2">
            <div><div class="font-bold">${escapeHtml(h.ten_ca || "")}</div><div class="text-[11px] text-[#71717a]">${escapeHtml(h.khung_gio || "")}</div></div>
            <label class="flex items-center gap-1 text-xs font-bold text-[#52525b]">×
                <input type="number" min="0.5" max="5" step="0.1" data-shift="${h.id}" value="${h.he_so_luong}" class="form-input !py-1.5 w-24">
            </label>
        </div>`).join("");
    document.getElementById("h-coef").value = data.he_so_ngay_le_mac_dinh;
    document.getElementById("updated").textContent = data.ngay_cap_nhat ? `Cập nhật lần cuối ${formatDateTime(data.ngay_cap_nhat)}` : "Đang dùng giá trị mặc định";
    renderHolidays();
    updateExample();
}

function renderHolidays() {
    const body = document.getElementById("holidays");
    body.innerHTML = settings.ngay_le.length ? settings.ngay_le.map(h => `
        <tr>
            <td class="py-2 px-2 whitespace-nowrap">${formatDate(h.ngay)}</td>
            <td class="py-2 px-2">${escapeHtml(h.ten)}</td>
            <td class="py-2 px-2 text-center font-bold">× ${h.he_so}</td>
            <td class="py-2 px-2 text-right"><button type="button" onclick="removeHoliday(${h.id})" class="text-xs font-bold text-[#dc2626] hover:underline">Xóa</button></td>
        </tr>`).join("") : `<tr><td colspan="4" class="py-6 text-center text-[#71717a]">Chưa có ngày lễ nào</td></tr>`;
}

function updateExample() {
    const form = document.getElementById("settings-form");
    const hours = Number(form.elements.gio_chuan_thang.value) || 208;
    document.getElementById("rate-example").textContent =
        `VD hợp đồng 9.000.000 đ/tháng → ${vnd(9000000 / hours)}/giờ. Hợp đồng 25.000 đ được hiểu là 25.000 đ/giờ.`;
}

async function save(e) {
    e.preventDefault();
    const form = document.getElementById("settings-form");
    const body = { ...settings };
    NUMBER_FIELDS.forEach(name => { body[name] = Number(form.elements[name].value); });
    body.cach_phat = form.querySelector('input[name="cach_phat"]:checked').value;
    body.chuyen_can_ky_tuan = form.elements.chuyen_can_ky_tuan.checked;
    body.he_so_ca = settings.he_so_ca.map(h => ({
        ...h, he_so_luong: Number(document.querySelector(`[data-shift="${h.id}"]`).value)
    }));
    try {
        fill(await API.request("/api/payroll/settings", { method: "PUT", body }));
        showToast("Đã lưu cài đặt lương. Bấm \"Tính lại\" ở kỳ nháp để áp dụng.");
    } catch (err) {
        showToast(err.message, "error");
    }
}

async function addHoliday(e) {
    e.preventDefault();
    try {
        fill(await API.request("/api/payroll/holidays", {
            method: "POST",
            body: {
                ngay: document.getElementById("h-date").value,
                ten: document.getElementById("h-name").value.trim(),
                he_so: Number(document.getElementById("h-coef").value) || 2
            }
        }));
        document.getElementById("h-date").value = "";
        document.getElementById("h-name").value = "";
        showToast("Đã thêm ngày lễ");
    } catch (err) {
        showToast(err.message, "error");
    }
}

async function removeHoliday(id) {
    if (!confirm("Xóa ngày lễ này?")) return;
    try {
        fill(await API.request(`/api/payroll/holidays/${id}`, { method: "DELETE" }));
    } catch (err) {
        showToast(err.message, "error");
    }
}
