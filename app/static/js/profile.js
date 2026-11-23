// Trang Hồ sơ của tôi: nhân viên chỉ xem được hồ sơ và hợp đồng của chính mình
let currentEmp = null;

document.addEventListener("DOMContentLoaded", async () => {
    const user = API.getUser();
    if (!user) return;
    if (!user.ma_nv) {
        document.getElementById("profile-empty").classList.remove("hidden");
        return;
    }

    await loadMyProfile();
});

async function loadMyProfile() {
    const user = API.getUser();
    try {
        const [emp, contracts] = await Promise.all([
            API.request(`/api/employees/${user.ma_nv}`),
            API.request("/api/contracts")
        ]);
        currentEmp = emp;
        renderProfile(emp);
        renderContracts(contracts.filter(c => c.ma_nhan_vien === user.ma_nv));
        document.getElementById("profile-content").classList.remove("hidden");
    } catch (err) {
        showToast(err.message, "error");
    }
}

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

// Modal Đổi mật khẩu
function openPasswordModal() {
    const form = document.getElementById("form-change-password");
    if (form) form.reset();
    document.getElementById("password-modal").classList.remove("hidden");
}

function closePasswordModal() {
    document.getElementById("password-modal").classList.add("hidden");
}

async function submitChangePassword(e) {
    e.preventDefault();
    const oldPass = document.getElementById("pw-old").value;
    const newPass = document.getElementById("pw-new").value;
    const confirmPass = document.getElementById("pw-confirm").value;

    if (newPass !== confirmPass) {
        showToast("Mật khẩu xác nhận không khớp", "error");
        return;
    }

    const btn = document.getElementById("btn-save-pw");
    btn.disabled = true;
    try {
        const res = await API.request("/api/auth/change-password", {
            method: "POST",
            body: { mat_khau_cu: oldPass, mat_khau_moi: newPass }
        });
        showToast(res.message || "Đổi mật khẩu thành công!");
        closePasswordModal();
    } catch (err) {
        showToast(err.message, "error");
    } finally {
        btn.disabled = false;
    }
}

// Modal Cập nhật thông tin liên hệ
function openContactModal() {
    if (!currentEmp) return;
    document.getElementById("ct-phone").value = currentEmp.so_dien_thoai || "";
    document.getElementById("ct-email").value = currentEmp.email || "";
    document.getElementById("ct-address").value = currentEmp.dia_chi || "";
    document.getElementById("ct-marital").value = currentEmp.tinh_trang_hon_nhan || "Độc thân";
    document.getElementById("ct-dependents").value = currentEmp.so_nguoi_phu_thuoc ?? 0;
    document.getElementById("contact-modal").classList.remove("hidden");
}

function closeContactModal() {
    document.getElementById("contact-modal").classList.add("hidden");
}

async function submitContactUpdate(e) {
    e.preventDefault();
    const payload = {
        so_dien_thoai: document.getElementById("ct-phone").value.trim() || null,
        email: document.getElementById("ct-email").value.trim() || null,
        dia_chi: document.getElementById("ct-address").value.trim() || null,
        tinh_trang_hon_nhan: document.getElementById("ct-marital").value || null,
        so_nguoi_phu_thuoc: parseInt(document.getElementById("ct-dependents").value, 10) || 0
    };

    const btn = document.getElementById("btn-save-contact");
    btn.disabled = true;
    try {
        const updated = await API.request("/api/employees/me", {
            method: "PUT",
            body: payload
        });
        showToast("Cập nhật thông tin liên hệ thành công!");
        closeContactModal();
        currentEmp = { ...currentEmp, ...updated };
        renderProfile(currentEmp);
    } catch (err) {
        showToast(err.message, "error");
    } finally {
        btn.disabled = false;
    }
}

// Upload Avatar
async function uploadMyAvatar(e) {
    const file = e.target.files && e.target.files[0];
    if (!file) return;
    if (!currentEmp || !currentEmp.id) return;

    try {
        const res = await API.upload(`/api/employees/${currentEmp.id}/avatar`, file);
        showToast("Cập nhật ảnh đại diện thành công!");
        if (res.avatar_url) {
            currentEmp.anh_dai_dien = res.avatar_url;
            const avatarEl = document.getElementById("pf-avatar");
            avatarEl.innerHTML = `<img src="${escapeHtml(res.avatar_url)}" alt="" class="w-full h-full object-cover">`;
        }
    } catch (err) {
        showToast(err.message, "error");
    } finally {
        e.target.value = "";
    }
}

