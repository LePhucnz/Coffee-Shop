// Trang Hồ sơ của tôi: nhân viên chỉ xem được hồ sơ và hợp đồng của chính mình
document.addEventListener("DOMContentLoaded", async () => {
    const user = API.getUser();
    if (!user) return;
    if (!user.ma_nv) {
        document.getElementById("profile-empty").classList.remove("hidden");
        return;
    }

    try {
        const [emp, contracts] = await Promise.all([
            API.request(`/api/employees/${user.ma_nv}`),
            API.request("/api/contracts")
        ]);
        renderProfile(emp);
        renderContracts(contracts.filter(c => c.ma_nhan_vien === user.ma_nv));
        document.getElementById("profile-content").classList.remove("hidden");
    } catch (err) {
        showToast(err.message, "error");
    }
});

function renderProfile(emp) {
    const avatar = document.getElementById("pf-avatar");
    if (emp.anh_dai_dien) {
        avatar.innerHTML = `<img src="${escapeHtml(emp.anh_dai_dien)}" alt="" class="w-full h-full object-cover">`;
    } else {
        avatar.textContent = (emp.ho_ten || "?").trim().split(" ").pop().charAt(0).toUpperCase();
    }
    document.getElementById("pf-name").textContent = emp.ho_ten;
    document.getElementById("pf-code").textContent = `${emp.ma_nhan_vien || ""} · ${emp.ten_vi_tri || "Chưa có vị trí"}`;
    document.getElementById("pf-status").innerHTML = statusBadge(EMPLOYEE_STATUS, emp.trang_thai);

    const rows = [
        ["Ngày sinh", formatDate(emp.ngay_sinh)],
        ["Giới tính", emp.gioi_tinh || "-"],
        ["Số điện thoại", emp.so_dien_thoai || "-"],
        ["Email", emp.email || "-"],
        ["CMND / CCCD", emp.cccd || "-"],
        ["Ngày vào làm", formatDate(emp.ngay_vao_lam)],
        ["Cửa hàng", emp.ten_cua_hang || "-"],
        ["Địa chỉ", emp.dia_chi || "-"]
    ];
    document.getElementById("pf-details").innerHTML = rows.map(([label, value]) => `
        <div>
            <dt class="text-xs font-bold text-[#71717a] uppercase tracking-wider">${label}</dt>
            <dd class="mt-0.5 font-medium text-[#18181b]">${escapeHtml(value)}</dd>
        </div>`).join("");
}

function renderContracts(items) {
    const tbody = document.getElementById("pf-contracts");
    if (!items.length) {
        tbody.innerHTML = `<tr><td colspan="5" class="py-6 text-center text-[#71717a]">Chưa có hợp đồng</td></tr>`;
        return;
    }
    tbody.innerHTML = items.map(c => `
        <tr>
            <td class="py-3 px-5">${escapeHtml(c.loai_hop_dong || "-")}</td>
            <td class="py-3 px-5">${formatDate(c.ngay_bat_dau)} → ${formatDate(c.ngay_ket_thuc)}</td>
            <td class="py-3 px-5 text-right whitespace-nowrap">${formatMoney(c.muc_luong)}</td>
            <td class="py-3 px-5">${c.file_dinh_kem ? `<a href="${escapeHtml(c.file_dinh_kem)}" target="_blank" rel="noopener" class="text-[#cf6800] font-semibold hover:underline">Xem file</a>` : "-"}</td>
            <td class="py-3 px-5">${statusBadge(CONTRACT_STATUS, c.trang_thai)}</td>
        </tr>`).join("");
}
