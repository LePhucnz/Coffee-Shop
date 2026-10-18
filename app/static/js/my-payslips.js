// Sprint 6 - Phiếu lương của tôi (FR-13): chỉ phiếu đã chốt của chính mình
document.addEventListener("DOMContentLoaded", async () => {
    if (!API.getUser()) return;
    let items = [];
    try {
        items = await API.request("/api/payroll/payslips/me");
    } catch (err) {
        showToast(err.message, "error");
    }
    const body = document.getElementById("rows");
    if (!items.length) {
        body.innerHTML = `<tr><td colspan="9" class="py-8 text-center text-[#71717a]">Chưa có phiếu lương nào được chốt</td></tr>`;
        return;
    }
    const last = items[0];
    document.getElementById("latest").classList.remove("hidden");
    document.getElementById("latest-period").textContent = `Kỳ gần nhất · ${last.ten_ky} · ${periodRange(last)}`;
    document.getElementById("latest-net").textContent = vnd(last.thuc_lanh);
    document.getElementById("latest-meta").textContent = `${last.so_ca} ca · ${hoursLabel(last.tong_gio)} · Đơn giá ${rateLabel(last)}`;
    document.getElementById("latest-view").href = `/payslip?id=${last.id}`;
    document.getElementById("latest-pdf").addEventListener("click", () => downloadSlip(last.id));

    body.innerHTML = items.map(s => `
        <tr>
            <td class="py-2 px-2"><div class="font-bold">${escapeHtml(s.ten_ky)}</div><div class="text-[11px] text-[#71717a]">${periodRange(s)}</div></td>
            <td class="py-2 px-2 text-center">${s.so_ca}</td>
            <td class="py-2 px-2 text-right">${hoursText(s.tong_gio)}</td>
            <td class="py-2 px-2 text-center">${s.so_lan_tre} / ${s.so_lan_som}</td>
            <td class="py-2 px-2 text-right whitespace-nowrap">${vnd(s.luong_co_ban)}</td>
            <td class="py-2 px-2 text-right whitespace-nowrap text-emerald-700">${s.tien_thuong ? "+" + vnd(s.tien_thuong) : "-"}</td>
            <td class="py-2 px-2 text-right whitespace-nowrap text-[#dc2626]">${s.tien_phat ? "-" + vnd(s.tien_phat) : "-"}</td>
            <td class="py-2 px-2 text-right whitespace-nowrap font-extrabold">${vnd(s.thuc_lanh)}</td>
            <td class="py-2 px-2 whitespace-nowrap text-right">
                <a href="/payslip?id=${s.id}" class="text-xs font-bold text-[#cf6800] hover:underline mr-3">Xem</a>
                <button type="button" onclick="downloadSlip(${s.id})" class="text-xs font-bold text-[#cf6800] hover:underline">PDF</button>
            </td>
        </tr>`).join("");
});

async function downloadSlip(id) {
    try {
        await downloadWithAuth(`/api/payroll/payslips/${id}/export?dinh_dang=pdf`, "phieu-luong.pdf");
    } catch (err) {
        showToast(err.message, "error");
    }
}
