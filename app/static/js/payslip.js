// Sprint 6 - Phiếu lương: chi tiết ca, các khoản, tải PDF/Excel; Quản lý thêm/xóa khoản thủ công khi kỳ còn nháp
let slip = null;
const slipId = queryParam("id");

document.addEventListener("DOMContentLoaded", () => {
    if (!API.getUser()) return;
    if (API.isAdmin()) document.getElementById("btn-back").href = "/payroll";
    document.getElementById("btn-pdf").addEventListener("click", () => download("pdf"));
    document.getElementById("btn-xlsx").addEventListener("click", () => download("xlsx"));
    document.getElementById("btn-add").addEventListener("click", () => {
        document.getElementById("item-form").reset();
        openModal("item-modal");
    });
    document.getElementById("item-form").addEventListener("submit", addItem);
    if (!slipId) {
        window.location.href = "/my-payslips";
        return;
    }
    load();
});

async function load() {
    try {
        slip = await API.request(`/api/payroll/payslips/${slipId}`);
        render();
    } catch (err) {
        document.getElementById("ps-name").textContent = "Không xem được phiếu lương";
        document.getElementById("ps-sub").textContent = err.message;
    }
}

function render() {
    const s = slip;
    if (API.isAdmin()) document.getElementById("btn-back").href = `/payroll?ky=${s.ma_ky_luong}`;
    document.getElementById("ps-period").textContent = `${s.ten_ky} · ${periodRange(s)}`;
    document.getElementById("ps-name").textContent = s.ho_ten || "";
    document.getElementById("ps-sub").textContent = `${s.ma_nhan_vien || ""} · ${s.ten_vi_tri || ""}${s.da_nghi_viec ? " · Đã nghỉ việc" : ""}`;
    document.getElementById("ps-net").textContent = vnd(s.thuc_lanh);
    document.getElementById("ps-status").innerHTML = statusBadge(PAYROLL_STATUS, s.trang_thai) +
        (s.ngay_tinh ? `<span class="text-[11px] text-[#a19991] ml-2">Tính lúc ${formatDateTime(s.ngay_tinh)}</span>` : "");
    document.getElementById("ps-warnings").innerHTML = warningBox(s.canh_bao);

    const row = (k, v, cls = "") => `<div class="flex justify-between gap-3 py-2"><dt class="text-[#71717a]">${k}</dt><dd class="font-bold text-right ${cls}">${v}</dd></div>`;
    document.getElementById("ps-summary").innerHTML = [
        row("Đơn giá", escapeHtml(rateLabel(s))),
        row("Số ca đã làm", s.so_ca),
        row("Tổng giờ làm", hoursLabel(s.tong_gio)),
        s.gio_dieu_chinh ? row("Giờ điều chỉnh kỳ trước", `${s.gio_dieu_chinh > 0 ? "+" : ""}${s.gio_dieu_chinh} giờ`) : "",
        row("Giờ quy đổi (× hệ số)", hoursLabel(s.gio_quy_doi)),
        row("Đi trễ", `${s.so_lan_tre} lần · ${s.phut_tre} phút`),
        row("Về sớm", `${s.so_lan_som} lần · ${s.phut_som} phút`),
        row("Vắng không phép", `${s.so_vang} ca`),
        row("Lương cơ bản", vnd(s.luong_co_ban)),
        row("Thưởng + phụ cấp", "+ " + vnd(s.tien_thuong), "text-emerald-700"),
        row("Phạt + khấu trừ", "- " + vnd(s.tien_phat), "text-[#dc2626]"),
        row("Thực lãnh", vnd(s.thuc_lanh), "text-lg")
    ].join("");

    const isOwn = API.isAdmin() && API.getUser().ma_nv === s.ma_nv && s.trang_thai === "nhap" && !s.co_the_sua;
    document.getElementById("btn-add").classList.toggle("hidden", !s.co_the_sua);
    document.getElementById("ps-own-note").classList.toggle("hidden", !isOwn);
    document.getElementById("ps-items").innerHTML = s.khoan.length ? s.khoan.map(k => `
        <div class="flex items-start justify-between gap-3 py-2.5">
            <div class="min-w-0">
                <div class="flex flex-wrap items-center gap-1.5">${itemBadge(k)}
                    <span class="text-[11px] font-semibold text-[#71717a]">${k.nguon === "thu_cong" ? `Thủ công${k.nguoi_tao ? " · " + escapeHtml(k.nguoi_tao) : ""}` : "Tự động"}</span></div>
                <div class="mt-1">${escapeHtml(k.ly_do || "")}</div>
            </div>
            <div class="text-right shrink-0">
                <div class="font-extrabold ${k.dau < 0 ? "text-[#dc2626]" : "text-emerald-700"}">${signedVnd(k.so_tien, k.dau)}</div>
                ${s.co_the_sua && k.nguon === "thu_cong" ? `<button type="button" onclick="removeItem(${k.id})" class="text-[11px] font-bold text-[#dc2626] hover:underline">Xóa</button>` : ""}
            </div>
        </div>`).join("") : `<div class="py-4 text-center text-[#71717a]">Không có khoản thưởng, phụ cấp hay phạt nào</div>`;

    document.getElementById("ps-shifts").innerHTML = s.ca.length ? s.ca.map(c => `
        <tr>
            <td class="py-2 px-2 whitespace-nowrap">${dayLabel(c.ngay)}</td>
            <td class="py-2 px-2 text-xs">${escapeHtml(c.ca)}</td>
            <td class="py-2 px-2 whitespace-nowrap">${c.vao || "--:--"} / ${c.ra || "--:--"}</td>
            <td class="py-2 px-2">${statusBadge(ATTENDANCE_STATUS, c.trang_thai)}${c.da_dieu_chinh ? ` <span class="text-[11px] text-stone-500">ĐC</span>` : ""}</td>
            <td class="py-2 px-2 text-right">${hoursText(c.so_gio)}${c.phut_vuot_ca_duyet ? `<div class="text-[11px] text-sky-700">+${c.phut_vuot_ca_duyet}p vượt ca</div>` : ""}</td>
            <td class="py-2 px-2 text-center whitespace-nowrap">× ${c.he_so}${c.ngay_le ? `<div class="text-[11px] text-[#cf6800] font-bold">${escapeHtml(c.ngay_le)}</div>` : ""}</td>
            <td class="py-2 px-2 text-right whitespace-nowrap font-bold">${vnd(c.thanh_tien)}</td>
            <td class="py-2 px-2 text-xs whitespace-nowrap">${c.phut_tre || c.phut_som ? `${c.phut_tre} / ${c.phut_som} phút` : "-"}
                ${c.mien_phat ? `<div class="text-emerald-700 font-bold">Miễn phạt</div>` : c.tien_phat ? `<div class="text-[#dc2626]">-${vnd(c.tien_phat)}</div>` : ""}</td>
        </tr>`).join("") : `<tr><td colspan="8" class="py-6 text-center text-[#71717a]">Không có ca nào trong kỳ</td></tr>`;
}

async function addItem(e) {
    e.preventDefault();
    try {
        slip = await API.request(`/api/payroll/payslips/${slip.id}/items`, {
            method: "POST",
            body: {
                loai: document.getElementById("i-type").value,
                so_tien: Number(document.getElementById("i-amount").value),
                ly_do: document.getElementById("i-reason").value.trim()
            }
        });
        closeModal("item-modal");
        render();
        showToast("Đã thêm khoản vào phiếu lương");
    } catch (err) {
        showToast(err.message, "error");
    }
}

async function removeItem(id) {
    if (!confirm("Xóa khoản thủ công này?")) return;
    try {
        slip = await API.request(`/api/payroll/payslips/${slip.id}/items/${id}`, { method: "DELETE" });
        render();
        showToast("Đã xóa khoản");
    } catch (err) {
        showToast(err.message, "error");
    }
}

async function download(fmt) {
    try {
        await downloadWithAuth(`/api/payroll/payslips/${slipId}/export?dinh_dang=${fmt}`, `phieu-luong.${fmt}`);
    } catch (err) {
        showToast(err.message, "error");
    }
}
