// Sprint 6 - Tiện ích dùng chung cho các trang lương (FR-12, FR-13)

const PAYROLL_STATUS = {
    nhap: { text: "Bản nháp", cls: "bg-amber-100 text-amber-700" },
    da_chot: { text: "Đã chốt", cls: "bg-emerald-100 text-emerald-700" }
};

const PERIOD_TYPES = { thang: "Tháng", tuan: "Tuần", tuy_chon: "Tùy chọn" };

const ITEM_COLORS = {
    thuong: "bg-emerald-100 text-emerald-700",
    phu_cap: "bg-sky-100 text-sky-700",
    phat: "bg-red-100 text-red-700",
    khau_tru: "bg-orange-100 text-orange-700",
    dieu_chinh_cong: "bg-stone-200 text-stone-700"
};

// 1234567 -> "1.234.567 đ"
function vnd(value) {
    return Math.round(Number(value || 0)).toLocaleString("vi-VN") + " đ";
}

function signedVnd(value, sign) {
    return (sign < 0 ? "- " : "+ ") + vnd(value);
}

function hoursLabel(value) {
    return `${Number(value || 0).toLocaleString("vi-VN", { maximumFractionDigits: 2 })} giờ`;
}

function itemBadge(item) {
    return `<span class="inline-flex px-2 py-0.5 rounded-full text-[11px] font-bold whitespace-nowrap ${ITEM_COLORS[item.loai] || "bg-stone-100 text-stone-600"}">${escapeHtml(item.ten_loai)}</span>`;
}

function rateLabel(slip) {
    if (!slip.loai_luong) return "Chưa có mức lương";
    const rate = `${vnd(slip.don_gia_gio)}/giờ`;
    return slip.loai_luong === "thang" ? `${rate} (lương tháng ${vnd(slip.muc_luong_hop_dong)})` : rate;
}

function warningBox(items) {
    if (!items || !items.length) return "";
    return `<div class="rounded-xl bg-amber-50 border border-amber-200 px-4 py-3 text-sm text-amber-800 space-y-1">
        ${items.map(w => `<div>⚠ ${escapeHtml(w)}</div>`).join("")}
    </div>`;
}

function periodRange(p) {
    return `${formatDate(p.tu_ngay)} - ${formatDate(p.den_ngay)}`;
}
