// Sprint 6 - Tính lương: tạo kỳ, xem trước bảng lương, tính lại, xuất báo cáo, chốt kỳ (FR-12, FR-13)
let periods = [];
let current = null;
let createType = "thang";

document.addEventListener("DOMContentLoaded", () => {
    if (!API.isAdmin()) return;
    document.getElementById("btn-new").addEventListener("click", openCreate);
    document.getElementById("period-select").addEventListener("change", e => loadPeriod(e.target.value));
    document.getElementById("btn-recalc").addEventListener("click", recalc);
    document.getElementById("btn-xlsx").addEventListener("click", () => exportFile("xlsx"));
    document.getElementById("btn-pdf").addEventListener("click", () => exportFile("pdf"));
    document.getElementById("btn-finalize").addEventListener("click", openFinalize);
    document.getElementById("btn-delete").addEventListener("click", deletePeriod);
    document.getElementById("fz-confirm").addEventListener("click", finalize);
    document.getElementById("f-keyword").addEventListener("input", () => renderRows());
    document.querySelectorAll(".type-tab").forEach(b => b.addEventListener("click", () => setCreateType(b.dataset.type)));
    ["c-month", "c-week", "c-from", "c-to"].forEach(id => document.getElementById(id).addEventListener("change", previewRange));
    document.getElementById("create-form").addEventListener("submit", createPeriod);
    loadPeriods(queryParam("ky"));
});

async function loadPeriods(selectId) {
    try {
        periods = await API.request("/api/payroll/periods");
    } catch (err) {
        showToast(err.message, "error");
        return;
    }
    const empty = !periods.length;
    document.getElementById("empty").classList.toggle("hidden", !empty);
    document.getElementById("content").classList.toggle("hidden", empty);
    if (empty) return;
    const sel = document.getElementById("period-select");
    sel.innerHTML = periods.map(p =>
        `<option value="${p.id}">${escapeHtml(p.ten_ky)} · ${periodRange(p)} · ${PAYROLL_STATUS[p.trang_thai].text}</option>`
    ).join("");
    const id = periods.some(p => String(p.id) === String(selectId)) ? selectId : periods[0].id;
    sel.value = id;
    loadPeriod(id);
}

async function loadPeriod(id) {
    try {
        current = await API.request(`/api/payroll/periods/${id}`);
        setQueryParams({ ky: id });
        render();
    } catch (err) {
        showToast(err.message, "error");
    }
}

function render() {
    const p = current;
    const draft = p.trang_thai === "nhap";
    document.getElementById("period-meta").innerHTML = `
        <div>${statusBadge(PAYROLL_STATUS, p.trang_thai)} <span class="ml-1 font-bold text-[#18181b]">${PERIOD_TYPES[p.loai_ky] || ""} · ${periodRange(p)}</span></div>
        ${p.ngay_tinh ? `<div>Tính lúc ${formatDateTime(p.ngay_tinh)}${p.nguoi_tinh ? ` bởi ${escapeHtml(p.nguoi_tinh)}` : ""}</div>` : ""}
        ${p.ngay_chot ? `<div class="text-emerald-700 font-bold">Chốt lúc ${formatDateTime(p.ngay_chot)}${p.nguoi_chot ? ` bởi ${escapeHtml(p.nguoi_chot)}` : ""}</div>` : ""}
        ${p.ghi_chu ? `<div>${escapeHtml(p.ghi_chu)}</div>` : ""}`;
    const t = p.tong;
    document.getElementById("t-staff").textContent = t.so_nhan_vien;
    document.getElementById("t-hours").textContent = hoursLabel(t.tong_gio);
    document.getElementById("t-base").textContent = vnd(t.luong_co_ban);
    document.getElementById("t-bonus").textContent = "+ " + vnd(t.tien_thuong);
    document.getElementById("t-penalty").textContent = "- " + vnd(t.tien_phat);
    document.getElementById("t-net").textContent = vnd(t.thuc_lanh);
    document.getElementById("warnings").innerHTML = warningBox(p.canh_bao);
    ["btn-recalc", "btn-finalize", "btn-delete"].forEach(id => document.getElementById(id).classList.toggle("hidden", !draft));
    document.getElementById("btn-grid").href = `/attendance-manage?che_do=ky&tu_ngay=${p.tu_ngay}&den_ngay=${p.den_ngay}`;
    renderRows();
}

function renderRows() {
    const key = document.getElementById("f-keyword").value.trim().toLowerCase();
    const rows = current.phieu.filter(s => !key || (s.ho_ten || "").toLowerCase().includes(key) || (s.ma_nhan_vien || "").toLowerCase().includes(key));
    const body = document.getElementById("rows");
    if (!rows.length) {
        body.innerHTML = `<tr><td colspan="11" class="py-6 text-center text-[#71717a]">${current.phieu.length ? "Không có nhân viên khớp" : "Kỳ này chưa có ca nào đã công bố"}</td></tr>`;
    } else {
        body.innerHTML = rows.map(s => `
            <tr class="${s.canh_bao.length ? "bg-[#fffaf3]" : ""} ${s.da_nghi_viec ? "opacity-70" : ""}">
                <td class="py-2 px-2"><div class="text-[11px] text-[#71717a]">${escapeHtml(s.ma_nhan_vien || "")} · ${escapeHtml(s.ten_vi_tri || "")}</div>
                    <div class="font-bold">${escapeHtml(s.ho_ten || "")}${s.da_nghi_viec ? ` <span class="text-[11px] font-semibold text-stone-500">(đã nghỉ)</span>` : ""}</div></td>
                <td class="py-2 px-2 text-xs whitespace-nowrap">${s.loai_luong ? `${vnd(s.don_gia_gio)}/giờ<div class="text-[11px] text-[#71717a]">${s.loai_luong === "thang" ? "Lương tháng quy đổi" : "Lương giờ"}</div>` : `<span class="text-[#dc2626] font-bold">Chưa có HĐ</span>`}</td>
                <td class="py-2 px-2 text-center">${s.so_ca}</td>
                <td class="py-2 px-2 text-right whitespace-nowrap">${hoursText(s.tong_gio)}${s.gio_dieu_chinh ? `<div class="text-[11px] text-stone-500">ĐC ${s.gio_dieu_chinh > 0 ? "+" : ""}${s.gio_dieu_chinh}h</div>` : ""}</td>
                <td class="py-2 px-2 text-center whitespace-nowrap">${s.so_lan_tre} / ${s.so_lan_som}</td>
                <td class="py-2 px-2 text-center">${s.so_vang}</td>
                <td class="py-2 px-2 text-right whitespace-nowrap">${vnd(s.luong_co_ban)}</td>
                <td class="py-2 px-2 text-right whitespace-nowrap text-emerald-700">${s.tien_thuong ? "+" + vnd(s.tien_thuong) : "-"}</td>
                <td class="py-2 px-2 text-right whitespace-nowrap text-[#dc2626]">${s.tien_phat ? "-" + vnd(s.tien_phat) : "-"}</td>
                <td class="py-2 px-2 text-right whitespace-nowrap font-extrabold">${vnd(s.thuc_lanh)}</td>
                <td class="py-2 px-2 whitespace-nowrap text-right">
                    ${s.canh_bao.length ? `<span title="${escapeHtml(s.canh_bao.join("\n"))}" class="cursor-help text-amber-600 mr-2">⚠ ${s.canh_bao.length}</span>` : ""}
                    <a href="/payslip?id=${s.id}" class="text-xs font-bold text-[#cf6800] hover:underline">${current.trang_thai === "nhap" ? "Chi tiết / điều chỉnh" : "Xem phiếu"}</a>
                </td>
            </tr>`).join("");
    }
    const t = current.tong;
    document.getElementById("foot").innerHTML = current.phieu.length ? `
        <tr class="bg-[#fff4e6] font-extrabold">
            <td class="py-2 px-2 rounded-l-lg" colspan="3">Tổng ${t.so_nhan_vien} nhân viên</td>
            <td class="py-2 px-2 text-right">${hoursText(t.tong_gio)}</td>
            <td colspan="2"></td>
            <td class="py-2 px-2 text-right whitespace-nowrap">${vnd(t.luong_co_ban)}</td>
            <td class="py-2 px-2 text-right whitespace-nowrap text-emerald-700">+${vnd(t.tien_thuong)}</td>
            <td class="py-2 px-2 text-right whitespace-nowrap text-[#dc2626]">-${vnd(t.tien_phat)}</td>
            <td class="py-2 px-2 text-right whitespace-nowrap">${vnd(t.thuc_lanh)}</td>
            <td class="rounded-r-lg"></td>
        </tr>` : "";
}

// ---------- Tạo kỳ ----------

function openCreate() {
    const today = new Date();
    const prevMonth = new Date(today.getFullYear(), today.getMonth() - 1, 1);
    document.getElementById("c-month").value = toISODate(prevMonth).substring(0, 7);
    document.getElementById("c-week").value = addDays(mondayOf(today), -7);
    document.getElementById("c-from").value = toISODate(prevMonth);
    document.getElementById("c-to").value = addDays(toISODate(new Date(today.getFullYear(), today.getMonth(), 1)), -1);
    document.getElementById("c-name").value = "";
    document.getElementById("c-note").value = "";
    setCreateType("thang");
    openModal("create-modal");
}

function setCreateType(type) {
    createType = type;
    document.querySelectorAll(".type-tab").forEach(b => {
        const active = b.dataset.type === type;
        b.classList.toggle("bg-[#cf6800]", active);
        b.classList.toggle("text-white", active);
        b.classList.toggle("border-[#cf6800]", active);
        b.classList.toggle("border-[#e6dfd5]", !active);
    });
    document.getElementById("c-month-wrap").classList.toggle("hidden", type !== "thang");
    document.getElementById("c-week-wrap").classList.toggle("hidden", type !== "tuan");
    document.getElementById("c-range-wrap").classList.toggle("hidden", type !== "tuy_chon");
    previewRange();
}

function createRange() {
    if (createType === "thang") {
        const v = document.getElementById("c-month").value;
        if (!v) return null;
        const [y, m] = v.split("-").map(Number);
        return { tu_ngay: `${v}-01`, den_ngay: toISODate(new Date(y, m, 0)) };
    }
    if (createType === "tuan") {
        const v = document.getElementById("c-week").value;
        if (!v) return null;
        const start = mondayOf(v);
        return { tu_ngay: start, den_ngay: addDays(start, 6) };
    }
    const from = document.getElementById("c-from").value;
    const to = document.getElementById("c-to").value;
    return from && to ? { tu_ngay: from, den_ngay: to } : null;
}

function previewRange() {
    const r = createRange();
    const box = document.getElementById("c-preview");
    if (!r) {
        box.textContent = "Chọn khoảng ngày của kỳ lương";
        return;
    }
    const days = Math.round((parseISODate(r.den_ngay) - parseISODate(r.tu_ngay)) / 86400000) + 1;
    const overlap = periods.find(p => p.tu_ngay <= r.den_ngay && p.den_ngay >= r.tu_ngay);
    box.innerHTML = `Kỳ lương <b>${formatDate(r.tu_ngay)} - ${formatDate(r.den_ngay)}</b> (${days} ngày).
        ${createType === "thang" ? "Có xét thưởng chuyên cần." : ""}
        ${overlap ? `<div class="text-[#dc2626] font-bold mt-1">Trùng với kỳ "${escapeHtml(overlap.ten_ky)}"</div>` : ""}`;
}

async function createPeriod(e) {
    e.preventDefault();
    const r = createRange();
    if (!r) return showToast("Vui lòng chọn khoảng ngày", "warning");
    const btn = document.getElementById("c-submit");
    btn.disabled = true;
    try {
        const data = await API.request("/api/payroll/periods", {
            method: "POST",
            body: { loai_ky: createType, ...r, ten_ky: document.getElementById("c-name").value.trim() || null,
                    ghi_chu: document.getElementById("c-note").value.trim() || null }
        });
        closeModal("create-modal");
        showToast(`Đã tạo "${data.ten_ky}" và tính lương cho ${data.tong.so_nhan_vien} nhân viên`);
        loadPeriods(data.id);
    } catch (err) {
        showToast(err.message, "error");
    } finally {
        btn.disabled = false;
    }
}

// ---------- Thao tác kỳ ----------

async function recalc() {
    try {
        current = await API.request(`/api/payroll/periods/${current.id}/calculate`, { method: "POST" });
        render();
        showToast("Đã tính lại theo chấm công và cài đặt mới nhất");
    } catch (err) {
        showToast(err.message, "error");
    }
}

async function exportFile(fmt) {
    try {
        await downloadWithAuth(`/api/payroll/periods/${current.id}/export?dinh_dang=${fmt}`, `bang-luong.${fmt}`);
    } catch (err) {
        showToast(err.message, "error");
    }
}

async function deletePeriod() {
    if (!confirm(`Xóa kỳ nháp "${current.ten_ky}"? Các khoản thủ công đã thêm cũng bị xóa.`)) return;
    try {
        await API.request(`/api/payroll/periods/${current.id}`, { method: "DELETE" });
        showToast("Đã xóa kỳ lương nháp");
        setQueryParams({ ky: null });
        loadPeriods();
    } catch (err) {
        showToast(err.message, "error");
    }
}

function openFinalize() {
    const t = current.tong;
    document.getElementById("fz-summary").innerHTML = `
        <div class="font-bold">${escapeHtml(current.ten_ky)} · ${periodRange(current)}</div>
        <div>${t.so_nhan_vien} nhân viên · ${hoursLabel(t.tong_gio)}</div>
        <div>Tổng thực lãnh: <b>${vnd(t.thuc_lanh)}</b></div>`;
    document.getElementById("fz-warnings").innerHTML = warningBox(current.canh_bao);
    const pending = current.so_yeu_cau_cho_duyet;
    document.getElementById("fz-carry-wrap").classList.toggle("hidden", !pending);
    document.getElementById("fz-pending").textContent = pending;
    document.getElementById("fz-carry").checked = false;
    openModal("finalize-modal");
}

async function finalize() {
    const pending = current.so_yeu_cau_cho_duyet;
    const carry = document.getElementById("fz-carry").checked;
    if (pending && !carry) return showToast("Hãy xử lý yêu cầu chờ duyệt hoặc chọn chuyển sang kỳ sau", "warning");
    try {
        current = await API.request(`/api/payroll/periods/${current.id}/finalize`, {
            method: "POST", body: { chuyen_yeu_cau_sang_ky_sau: carry }
        });
        closeModal("finalize-modal");
        showToast("Đã chốt kỳ lương và gửi phiếu lương cho nhân viên");
        loadPeriods(current.id);
    } catch (err) {
        showToast(err.message, "error");
    }
}
