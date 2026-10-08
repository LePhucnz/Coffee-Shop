// Trang Hồ sơ nhân sự (FR-04, FR-06)
let employees = [];
let positions = [];
let stores = [];

document.addEventListener("DOMContentLoaded", async () => {
    if (!API.getUser()) return;
    await loadLookups();
    await loadEmployees();
    bindEvents();
});

async function loadLookups() {
    try {
        [positions, stores] = await Promise.all([
            API.request("/api/system/positions"),
            API.request("/api/system/stores")
        ]);
    } catch (err) {
        showToast("Không tải được danh mục vị trí / cửa hàng: " + err.message, "error");
        return;
    }
    const posOptions = positions.map(p => `<option value="${p.id}">${escapeHtml(p.ten_vi_tri)}</option>`).join("");
    const storeOptions = stores.map(s => `<option value="${s.id}">${escapeHtml(s.ten_cua_hang)}</option>`).join("");
    document.getElementById("filter-position").innerHTML = `<option value="">Tất cả vị trí</option>${posOptions}`;
    document.getElementById("emp-position").innerHTML = `<option value="">-- Chọn vị trí --</option>${posOptions}`;
    document.getElementById("emp-store").innerHTML = `<option value="">-- Chọn cửa hàng --</option>${storeOptions}`;
}

async function loadEmployees() {
    const params = new URLSearchParams();
    const keyword = document.getElementById("search-keyword").value.trim();
    const position = document.getElementById("filter-position").value;
    const status = document.getElementById("filter-status").value;
    if (keyword) params.set("keyword", keyword);
    if (position) params.set("ma_vi_tri", position);
    if (status) params.set("trang_thai", status);
    if (document.getElementById("filter-deleted").checked) params.set("include_deleted", "true");

    const tbody = document.getElementById("employees-tbody");
    try {
        const data = await API.request(`/api/employees?${params}`);
        employees = data.items;
        renderTable();
        await loadStatusCounts();
    } catch (err) {
        tbody.innerHTML = `<tr><td colspan="6" class="py-10 text-center text-red-600">${escapeHtml(err.message)}</td></tr>`;
    }
}

async function loadStatusCounts() {
    try {
        const stats = await API.request("/api/system/stats");
        document.getElementById("count-dang_lam").textContent = stats.active_employees;
        document.getElementById("count-nghi_phep").textContent = stats.on_leave_employees;
        document.getElementById("count-da_nghi").textContent = stats.resigned_employees;
    } catch (e) {
        // Thống kê chỉ để tham khảo, bỏ qua lỗi
    }
}

function avatarHtml(emp) {
    if (emp.anh_dai_dien) {
        return `<img src="${escapeHtml(emp.anh_dai_dien)}" alt="" class="w-9 h-9 rounded-full object-cover shrink-0">`;
    }
    const initial = (emp.ho_ten || "?").trim().split(" ").pop().charAt(0).toUpperCase();
    return `<div class="w-9 h-9 rounded-full bg-[#cf6800] text-white flex items-center justify-center font-bold text-sm shrink-0">${escapeHtml(initial)}</div>`;
}

function renderTable() {
    const tbody = document.getElementById("employees-tbody");
    document.getElementById("employees-total").textContent = `Tổng cộng: ${employees.length} hồ sơ`;

    if (!employees.length) {
        tbody.innerHTML = `<tr><td colspan="6" class="py-10 text-center text-[#71717a]">Không tìm thấy nhân viên phù hợp</td></tr>`;
        return;
    }

    tbody.innerHTML = employees.map(emp => {
        const deleted = emp.is_deleted;
        const actions = deleted
            ? `<button class="text-emerald-700 font-semibold hover:underline" onclick="restoreEmployee(${emp.id})">Khôi phục</button>`
            : `<button class="text-[#cf6800] font-semibold hover:underline" onclick="openEmployeeModal(${emp.id})">Sửa</button>
               <select class="ml-2 text-xs border border-[#e5e0d8] rounded-lg px-2 py-1" onchange="changeStatus(${emp.id}, this.value)" title="Đổi trạng thái">
                   <option value="">Đổi trạng thái</option>
                   <option value="dang_lam">Đang làm việc</option>
                   <option value="nghi_phep">Đang nghỉ phép</option>
                   <option value="da_nghi">Đã nghỉ việc</option>
               </select>
               <button class="ml-2 text-red-600 font-semibold hover:underline" onclick="deleteEmployee(${emp.id})">Xóa</button>`;
        return `
        <tr class="hover:bg-[#faf7f2] transition-colors ${deleted ? "opacity-50" : ""}">
            <td class="py-3.5 px-5">
                <div class="flex items-center gap-3">
                    ${avatarHtml(emp)}
                    <div class="min-w-0">
                        <div class="font-semibold text-[#18181b] truncate">${escapeHtml(emp.ho_ten)}</div>
                        <div class="text-xs text-[#71717a]">${escapeHtml(emp.ma_nhan_vien || "")}${deleted ? " · Đã xóa" : ""}</div>
                    </div>
                </div>
            </td>
            <td class="py-3.5 px-5 text-[#52525b]">${escapeHtml(emp.ten_vi_tri || "-")}</td>
            <td class="py-3.5 px-5 text-[#52525b]">
                <div>${escapeHtml(emp.so_dien_thoai || "-")}</div>
                <div class="text-xs text-[#71717a]">${escapeHtml(emp.email || "")}</div>
            </td>
            <td class="py-3.5 px-5 text-[#52525b]">${formatDate(emp.ngay_vao_lam)}</td>
            <td class="py-3.5 px-5">${statusBadge(EMPLOYEE_STATUS, emp.trang_thai)}</td>
            <td class="py-3.5 px-5 text-right whitespace-nowrap">${actions}</td>
        </tr>`;
    }).join("");
}

function getMaxBirthDate() {
    const d = new Date();
    d.setDate(d.getDate() - 1);
    const yyyy = d.getFullYear();
    const mm = String(d.getMonth() + 1).padStart(2, "0");
    const dd = String(d.getDate()).padStart(2, "0");
    return `${yyyy}-${mm}-${dd}`;
}

function bindEvents() {
    let timer;
    document.getElementById("search-keyword").addEventListener("input", () => {
        clearTimeout(timer);
        timer = setTimeout(loadEmployees, 300);
    });
    ["filter-position", "filter-status", "filter-deleted"].forEach(id =>
        document.getElementById(id).addEventListener("change", loadEmployees)
    );

    document.getElementById("emp-create-account").addEventListener("change", e => {
        document.getElementById("account-fields").classList.toggle("hidden", !e.target.checked);
    });

    document.getElementById("emp-avatar").addEventListener("change", e => {
        const file = e.target.files[0];
        if (file) setAvatarPreview(URL.createObjectURL(file));
    });

    // 1. Chặn nhập chữ cho số điện thoại (chỉ cho phép số và dấu + ở đầu)
    const phoneInput = document.getElementById("emp-phone");
    if (phoneInput) {
        phoneInput.addEventListener("keydown", e => {
            if (["Backspace", "Delete", "Tab", "Escape", "Enter", "ArrowLeft", "ArrowRight", "ArrowUp", "ArrowDown", "Home", "End"].includes(e.key) ||
                (e.ctrlKey || e.metaKey)) {
                return;
            }
            if (e.key === "+" && e.target.selectionStart === 0 && !e.target.value.includes("+")) {
                return;
            }
            if (!/^\d$/.test(e.key)) {
                e.preventDefault();
            }
        });
        phoneInput.addEventListener("input", e => {
            let val = e.target.value;
            if (val.startsWith("+")) {
                val = "+" + val.slice(1).replace(/\D/g, "");
            } else {
                val = val.replace(/\D/g, "");
            }
            if (val.length > 11) val = val.slice(0, 11);
            e.target.value = val;
        });
    }

    // 2. Chặn nhập chữ cho CCCD (chỉ cho phép chữ số, tối đa 12 số)
    const cccdInput = document.getElementById("emp-cccd");
    if (cccdInput) {
        cccdInput.addEventListener("keydown", e => {
            if (["Backspace", "Delete", "Tab", "Escape", "Enter", "ArrowLeft", "ArrowRight", "ArrowUp", "ArrowDown", "Home", "End"].includes(e.key) ||
                (e.ctrlKey || e.metaKey)) {
                return;
            }
            if (!/^\d$/.test(e.key)) {
                e.preventDefault();
            }
        });
        cccdInput.addEventListener("input", e => {
            e.target.value = e.target.value.replace(/\D/g, "").slice(0, 12);
        });
    }

    // 3. Chặn chọn/nhập ngày sinh là hôm nay hoặc tương lai
    const dobInput = document.getElementById("emp-dob");
    if (dobInput) {
        const maxDob = getMaxBirthDate();
        dobInput.setAttribute("max", maxDob);

        const validateDob = () => {
            const limit = getMaxBirthDate();
            if (dobInput.value && dobInput.value > limit) {
                showToast("Ngày sinh không hợp lệ: phải trước ngày hôm nay (không được là hôm nay hoặc tương lai)", "warning");
                dobInput.value = "";
            }
        };
        dobInput.addEventListener("change", validateDob);
        dobInput.addEventListener("input", validateDob);
        dobInput.addEventListener("blur", validateDob);
    }

    document.getElementById("employee-form").addEventListener("submit", saveEmployee);
}

function setAvatarPreview(src) {
    const img = document.getElementById("emp-avatar-preview");
    const placeholder = document.getElementById("emp-avatar-placeholder");
    img.src = src || "";
    img.classList.toggle("hidden", !src);
    placeholder.classList.toggle("hidden", !!src);
}

const FIELD_MAP = {
    "emp-name": "ho_ten",
    "emp-code": "ma_nhan_vien",
    "emp-dob": "ngay_sinh",
    "emp-gender": "gioi_tinh",
    "emp-phone": "so_dien_thoai",
    "emp-email": "email",
    "emp-cccd": "cccd",
    "emp-start": "ngay_vao_lam",
    "emp-position": "ma_vi_tri",
    "emp-store": "ma_cua_hang",
    "emp-address": "dia_chi",
    "emp-status": "trang_thai"
};

function openEmployeeModal(id = null) {
    const form = document.getElementById("employee-form");
    form.reset();
    document.getElementById("account-fields").classList.add("hidden");
    document.getElementById("emp-id").value = id || "";

    const emp = id ? employees.find(e => e.id === id) : null;
    document.getElementById("employee-modal-title").textContent = emp ? `Sửa hồ sơ: ${emp.ho_ten}` : "Thêm nhân viên";
    // Chỉ tạo tài khoản khi thêm mới
    document.getElementById("account-section").classList.toggle("hidden", !!emp);

    if (emp) {
        Object.entries(FIELD_MAP).forEach(([inputId, field]) => {
            document.getElementById(inputId).value = emp[field] ?? "";
        });
    }
    // Giới hạn ngày sinh tối đa là hôm qua (không được chọn hôm nay hoặc tương lai)
    const maxDob = getMaxBirthDate();
    const dobInput = document.getElementById("emp-dob");
    if (dobInput) dobInput.setAttribute("max", maxDob);

    setAvatarPreview(emp ? emp.anh_dai_dien : null);
    document.getElementById("employee-modal").classList.remove("hidden");
}

function closeEmployeeModal() {
    document.getElementById("employee-modal").classList.add("hidden");
}

function collectForm() {
    const payload = {};
    Object.entries(FIELD_MAP).forEach(([inputId, field]) => {
        const value = document.getElementById(inputId).value.trim();
        if (["ma_vi_tri", "ma_cua_hang"].includes(field)) {
            payload[field] = value ? Number(value) : null;
        } else {
            payload[field] = value || null;
        }
    });
    return payload;
}

async function saveEmployee(e) {
    e.preventDefault();
    const id = document.getElementById("emp-id").value;
    const payload = collectForm();
    const btn = document.getElementById("emp-submit");
    btn.disabled = true;

    // Kiểm tra hợp lệ dữ liệu phía client
    if (payload.ngay_sinh) {
        const todayStr = new Date().toISOString().split("T")[0];
        if (payload.ngay_sinh >= todayStr) {
            showToast("Ngày sinh không hợp lệ: phải trước ngày hôm nay", "error");
            btn.disabled = false;
            return;
        }
    }

    if (payload.so_dien_thoai) {
        const cleanedPhone = payload.so_dien_thoai.replace(/[\s.-]/g, "");
        if (!/^(?:0|\+84)\d{9}$/.test(cleanedPhone)) {
            showToast("Số điện thoại không hợp lệ: phải gồm 10 chữ số bắt đầu bằng số 0 và không chứa chữ cái", "error");
            btn.disabled = false;
            return;
        }
        payload.so_dien_thoai = cleanedPhone;
    }

    if (payload.cccd) {
        if (!/^(\d{9}|\d{12})$/.test(payload.cccd)) {
            showToast("CMND/CCCD không hợp lệ: chỉ được chứa chữ số và phải gồm 9 hoặc 12 chữ số", "error");
            btn.disabled = false;
            return;
        }
    }

    try {
        let saved;
        if (id) {
            // Không ghi đè mã NV bằng giá trị rỗng khi sửa
            if (!payload.ma_nhan_vien) delete payload.ma_nhan_vien;
            saved = await API.request(`/api/employees/${id}`, { method: "PUT", body: payload });
        } else {
            if (document.getElementById("emp-create-account").checked) {
                payload.tao_tai_khoan = true;
                payload.ten_dang_nhap = document.getElementById("acc-username").value.trim();
                payload.mat_khau = document.getElementById("acc-password").value;
                payload.ma_vai_tro = Number(document.getElementById("acc-role").value);
                if (!payload.ten_dang_nhap || !payload.mat_khau) {
                    throw new Error("Vui lòng nhập tên đăng nhập và mật khẩu");
                }
            }
            saved = await API.request("/api/employees", { method: "POST", body: payload });
        }

        const avatarFile = document.getElementById("emp-avatar").files[0];
        if (avatarFile) {
            await API.upload(`/api/employees/${saved.id}/avatar`, avatarFile);
        }

        showToast(id ? "Đã cập nhật hồ sơ" : `Đã thêm nhân viên ${saved.ho_ten} (${saved.ma_nhan_vien})`);
        closeEmployeeModal();
        await loadEmployees();
    } catch (err) {
        showToast(err.message, "error");
    } finally {
        btn.disabled = false;
    }
}

async function changeStatus(id, status) {
    if (!status) return;
    const emp = employees.find(e => e.id === id);
    if (status === "da_nghi" && !confirm(`Chuyển ${emp.ho_ten} sang "Đã nghỉ việc"? Nhân viên sẽ không thể đăng nhập và không được xếp ca.`)) {
        renderTable();
        return;
    }
    try {
        await API.request(`/api/employees/${id}/status`, { method: "PATCH", body: { trang_thai: status } });
        showToast(`Đã cập nhật trạng thái: ${EMPLOYEE_STATUS[status].text}`);
        await loadEmployees();
    } catch (err) {
        showToast(err.message, "error");
        renderTable();
    }
}

async function deleteEmployee(id) {
    const emp = employees.find(e => e.id === id);
    if (!confirm(`Xóa hồ sơ ${emp.ho_ten}? Dữ liệu lịch sử vẫn được giữ lại và có thể khôi phục.`)) return;
    try {
        const res = await API.request(`/api/employees/${id}`, { method: "DELETE" });
        showToast(res.message);
        await loadEmployees();
    } catch (err) {
        showToast(err.message, "error");
    }
}

async function restoreEmployee(id) {
    try {
        const emp = await API.request(`/api/employees/${id}/restore`, { method: "POST" });
        showToast(`Đã khôi phục hồ sơ ${emp.ho_ten}`);
        await loadEmployees();
    } catch (err) {
        showToast(err.message, "error");
    }
}
