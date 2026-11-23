// Sprint 5 - Tiện ích dùng chung cho các trang chấm công (FR-10, FR-11, FR-11A, FR-11B, FR-11D)

// Màu nhãn kết quả chấm công
const ATTENDANCE_LABELS = {
    dung_gio: "bg-emerald-100 text-emerald-700",
    di_tre: "bg-amber-100 text-amber-700",
    ve_som: "bg-amber-100 text-amber-700",
    vang_mat: "bg-red-100 text-red-700",
    chua_check_in: "bg-red-100 text-red-700",
    chua_check_out: "bg-orange-100 text-orange-700",
    vuot_ca: "bg-sky-100 text-sky-700",
    ngoai_vi_tri: "bg-purple-100 text-purple-700",
    khong_dinh_vi: "bg-purple-100 text-purple-700",
    thiet_bi_trung: "bg-purple-100 text-purple-700",
    da_dieu_chinh: "bg-stone-200 text-stone-700",
    mien_phat: "bg-emerald-50 text-emerald-700",
    cho_duyet: "bg-amber-50 text-amber-800",
    da_huy: "bg-stone-200 text-stone-600"
};

const ATTENDANCE_STATUS = {
    chua_den_ca: { text: "Chưa đến giờ", cls: "bg-stone-100 text-stone-600" },
    cho_check_in: { text: "Chờ check-in", cls: "bg-amber-100 text-amber-700" },
    dang_lam: { text: "Đang làm", cls: "bg-emerald-100 text-emerald-700" },
    chua_check_out: { text: "Chưa check-out", cls: "bg-orange-100 text-orange-700" },
    hoan_thanh: { text: "Đã hoàn thành", cls: "bg-stone-200 text-stone-700" },
    vang_mat: { text: "Vắng không phép", cls: "bg-red-100 text-red-700" },
    da_huy: { text: "Ca đã hủy", cls: "bg-stone-200 text-stone-600" }
};

const FLAG_NAMES = {
    ngoai_vi_tri: "Ngoài phạm vi",
    khong_dinh_vi: "Thiếu GPS",
    thiet_bi_trung: "Cùng thiết bị",
    vuot_han_muc: "Vượt hạn mức"
};

const LOCATION_NAMES = {
    trong_pham_vi: "Trong phạm vi",
    ngoai_pham_vi: "Ngoài phạm vi",
    khong_dinh_vi: "Không định vị",
    khong_ro: "-"
};

const REQUEST_TYPES = {
    bu_check_in: "Bù check-in",
    bu_check_out: "Bù check-out",
    bu_ca_hai: "Bù cả vào và ra",
    sua_gio: "Sửa giờ chấm công",
    sua_ca: "Sửa ca chấm công",
    giai_trinh: "Giải trình cờ chấm công"
};

const REQUEST_STATUS = {
    cho_duyet: { text: "Chờ duyệt", cls: "bg-amber-100 text-amber-700" },
    can_bo_sung: { text: "Cần bổ sung", cls: "bg-sky-100 text-sky-700" },
    da_duyet: { text: "Đã duyệt", cls: "bg-emerald-100 text-emerald-700" },
    tu_choi: { text: "Từ chối", cls: "bg-red-100 text-red-700" },
    da_huy: { text: "Đã hủy", cls: "bg-stone-200 text-stone-600" },
    het_han: { text: "Hết hạn", cls: "bg-stone-200 text-stone-600" }
};

// Ký hiệu ô trong bảng công theo kỳ (màn 08)
const CELL_COLORS = {
    D: "bg-emerald-50 text-emerald-700",
    T: "bg-amber-50 text-amber-700",
    S: "bg-amber-50 text-amber-700",
    TS: "bg-amber-100 text-amber-800",
    V: "bg-red-50 text-red-700",
    DC: "bg-stone-100 text-stone-700",
    "?": "bg-orange-50 text-orange-700",
    H: "bg-stone-100 text-stone-500",
    "-": "bg-white text-stone-400"
};

function attendanceLabels(items) {
    return (items || []).map(n =>
        `<span class="inline-flex px-2 py-0.5 rounded-full text-[11px] font-bold whitespace-nowrap ${ATTENDANCE_LABELS[n.ma] || "bg-stone-100 text-stone-600"}">${escapeHtml(n.ten)}</span>`
    ).join(" ");
}

function flagBadges(flags) {
    return (flags || []).map(f =>
        `<span class="inline-flex px-2 py-0.5 rounded-full text-[11px] font-bold whitespace-nowrap bg-purple-100 text-purple-700">${escapeHtml(FLAG_NAMES[f] || f)}</span>`
    ).join(" ");
}

// "2026-10-12T14:05:00" -> "14:05"
function hhmm(value) {
    if (!value) return "--:--";
    return String(value).substring(11, 16);
}

// "2026-10-12T14:05:00" -> "12/10 14:05"
function shortDateTime(value) {
    if (!value) return "-";
    const s = String(value);
    return `${s.substring(8, 10)}/${s.substring(5, 7)} ${s.substring(11, 16)}`;
}

// Giá trị cho ô <input type="datetime-local"> (giữ nguyên giờ máy chủ, không đổi múi giờ)
function toLocalInput(value) {
    return value ? String(value).substring(0, 16) : "";
}

// Ghép ngày làm + giờ "HH:MM" thành giá trị datetime-local
function combineDateTime(day, time) {
    return `${String(day).substring(0, 10)}T${String(time || "00:00").substring(0, 5)}`;
}

function shiftText(r) {
    return `${escapeHtml(r.ten_ca || "")} ${formatTime(r.gio_bat_dau)}-${formatTime(r.gio_ket_thuc)}`;
}

function minutesText(value) {
    return value ? `${value} phút` : "0";
}

function hoursText(value) {
    const h = Math.floor(value || 0);
    const m = Math.round(((value || 0) - h) * 60);
    return m ? `${h}h${String(m).padStart(2, "0")}` : `${h}h`;
}

// Mã thiết bị ẩn danh, lưu trên trình duyệt để phát hiện nhiều tài khoản dùng chung 1 máy (FR-10 mục 4)
function deviceId() {
    try {
        let id = localStorage.getItem("device_id");
        if (!id) {
            id = (crypto.randomUUID ? crypto.randomUUID() : String(Date.now()) + Math.random().toString(16).slice(2));
            localStorage.setItem("device_id", id);
        }
        return id;
    } catch (e) {
        return "khong-ro";
    }
}

function queryParam(name) {
    return new URLSearchParams(window.location.search).get(name);
}

function setQueryParams(params) {
    const url = new URL(window.location.href);
    Object.entries(params).forEach(([k, v]) => {
        if (v === null || v === undefined || v === "") url.searchParams.delete(k);
        else url.searchParams.set(k, v);
    });
    window.history.replaceState(null, "", url);
}

function buildQuery(params) {
    const q = new URLSearchParams();
    Object.entries(params).forEach(([k, v]) => {
        if (v !== null && v !== undefined && v !== "") q.set(k, v);
    });
    return q.toString();
}

// Tải file (Excel) có kèm token đăng nhập
async function downloadWithAuth(url, fallbackName) {
    const res = await fetch(url, { headers: { Authorization: `Bearer ${API.getToken()}` } });
    if (!res.ok) {
        let msg = `Lỗi ${res.status}`;
        try { msg = (await res.json()).detail || msg; } catch (e) { /* bỏ qua */ }
        throw new Error(msg);
    }
    const blob = await res.blob();
    const disposition = res.headers.get("Content-Disposition") || "";
    const match = disposition.match(/filename="?([^";]+)"?/);
    const a = document.createElement("a");
    a.href = URL.createObjectURL(blob);
    a.download = match ? decodeURIComponent(match[1]) : fallbackName;
    document.body.appendChild(a);
    a.click();
    a.remove();
    setTimeout(() => URL.revokeObjectURL(a.href), 1000);
}

function openModal(id) {
    document.getElementById(id).classList.remove("hidden");
}

function closeModal(id) {
    document.getElementById(id).classList.add("hidden");
}

async function loadPositionsInto(selectId) {
    try {
        const items = await API.request("/api/system/positions");
        const sel = document.getElementById(selectId);
        sel.innerHTML += items.map(p => `<option value="${p.id}">${escapeHtml(p.ten_vi_tri)}</option>`).join("");
    } catch (e) { /* bộ lọc không bắt buộc */ }
}

async function loadShiftTypesInto(selectId) {
    try {
        const items = await API.request("/api/shifts/types");
        const sel = document.getElementById(selectId);
        sel.innerHTML += items.map(t => `<option value="${t.id}">${escapeHtml(t.ten_ca)}</option>`).join("");
    } catch (e) { /* bộ lọc không bắt buộc */ }
}
