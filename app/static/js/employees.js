// Employee Management (FR-04, FR-06)
let currentEmployees = [];
let stores = [];
let positions = [];

document.addEventListener("DOMContentLoaded", async () => {
    checkAuthRedirect();
    await loadInitialData();
    await loadEmployees();
    setupEventListeners();
});

async function loadInitialData() {
    try {
        const [storesData, positionsData] = await Promise.all([
            API.request("/api/system/stores"),
            API.request("/api/system/positions")
        ]);
        stores = storesData || [];
        positions = positionsData || [];

        populateDropdowns();
    } catch (err) {
        console.error("Lỗi nạp dữ liệu ban đầu:", err);
    }
}

function populateDropdowns() {
    const filterPos = document.getElementById("filter-position");
    const modalPos = document.getElementById("emp-position");
    const modalStore = document.getElementById("emp-store");

    if (filterPos) {
        filterPos.innerHTML = '<option value="">Tất cả vị trí</option>' +
            positions.map(p => `<option value="${p.id}">${p.ten_vi_tri}</option>`).join("");
    }
    if (modalPos) {
        modalPos.innerHTML = '<option value="">-- Chọn vị trí --</option>' +
            positions.map(p => `<option value="${p.id}">${p.ten_vi_tri}</option>`).join("");
    }
    if (modalStore) {
        modalStore.innerHTML = '<option value="">-- Chọn chi nhánh --</option>' +
            stores.map(s => `<option value="${s.id}">${s.ten_cua_hang}</option>`).join("");
    }
}

async function loadEmployees() {
    const keyword = document.getElementById("search-keyword")?.value || "";
    const pos = document.getElementById("filter-position")?.value || "";
    const status = document.getElementById("filter-status")?.value || "";

    const params = new URLSearchParams();
    if (keyword) params.append("keyword", keyword);
    if (pos) params.append("ma_vi_tri", pos);
    if (status) params.append("trang_thai", status);

    const tbody = document.getElementById("employees-tbody");
    if (!tbody) return;

    tbody.innerHTML = `<tr><td colspan="7" class="text-center py-8 text-gray-500">Đang tải dữ liệu...</td></tr>`;

    try {
        const data = await API.request(`/api/employees?${params.toString()}`);
        currentEmployees = data.items || [];
        renderEmployeesTable(currentEmployees);
    } catch (err) {
        tbody.innerHTML = `<tr><td colspan="7" class="text-center py-8 text-red-500">${err.message}</td></tr>`;
    }
}

function renderEmployeesTable(list) {
    const tbody = document.getElementById("employees-tbody");
    if (!tbody) return;

    if (list.length === 0) {
        tbody.innerHTML = `<tr><td colspan="7" class="text-center py-8 text-gray-500">Không tìm thấy hồ sơ nhân sự nào phù hợp</td></tr>`;
        return;
    }

    const statusBadge = (st) => {
        if (st === "dang_lam") return `<span class="px-2.5 py-1 text-xs font-semibold rounded-full badge-active">Đang làm việc</span>`;
        if (st === "nghi_phep") return `<span class="px-2.5 py-1 text-xs font-semibold rounded-full badge-leave">Đang nghỉ phép</span>`;
        if (st === "da_nghi") return `<span class="px-2.5 py-1 text-xs font-semibold rounded-full badge-resigned">Đã nghỉ việc</span>`;
        return `<span class="px-2.5 py-1 text-xs font-semibold rounded-full bg-gray-100 text-gray-700">${st}</span>`;
    };

    tbody.innerHTML = list.map(emp => `
        <tr class="border-b border-gray-100 hover:bg-amber-50/30 transition-colors">
            <td class="py-3 px-4 font-mono text-sm font-semibold text-amber-900">${emp.ma_nhan_vien || "NV" + emp.id}</td>
            <td class="py-3 px-4">
                <div class="font-medium text-gray-900">${emp.ho_ten}</div>
                <div class="text-xs text-gray-500">${emp.email || "Chưa có email"}</div>
            </td>
            <td class="py-3 px-4 text-sm text-gray-600">${emp.so_dien_thoai || "---"}</td>
            <td class="py-3 px-4 text-sm font-medium text-gray-700">${emp.ten_vi_tri || "---"}</td>
            <td class="py-3 px-4 text-sm text-gray-600">${emp.ten_cua_hang || "---"}</td>
            <td class="py-3 px-4">${statusBadge(emp.trang_thai)}</td>
            <td class="py-3 px-4 text-right space-x-1 whitespace-nowrap">
                <button onclick="viewEmployeeDetail(${emp.id})" class="p-1.5 text-blue-600 hover:bg-blue-50 rounded" title="Xem chi tiết">
                    <svg class="w-4 h-4 inline" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 12a3 3 0 11-6 0 3 3 0 016 0z"/><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M2.458 12C3.732 7.943 7.523 5 12 5c4.478 0 8.268 2.943 9.542 7-1.274 4.057-5.064 7-9.542 7-4.477 0-8.268-2.943-9.542-7z"/></svg>
                </button>
                <button onclick="editEmployee(${emp.id})" class="p-1.5 text-amber-700 hover:bg-amber-50 rounded" title="Sửa hồ sơ">
                    <svg class="w-4 h-4 inline" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M11 5H6a2 2 0 00-2 2v11a2 2 0 002 2h11a2 2 0 002-2v-5m-1.414-9.414a2 2 0 112.828 2.828L11.828 15H9v-2.828l8.586-8.586z"/></svg>
                </button>
                <button onclick="deleteEmployee(${emp.id}, '${emp.ho_ten}')" class="p-1.5 text-red-600 hover:bg-red-50 rounded" title="Xóa mềm">
                    <svg class="w-4 h-4 inline" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16"/></svg>
                </button>
            </td>
        </tr>
    `).join("");
}

function setupEventListeners() {
    const searchBtn = document.getElementById("btn-search");
    const searchInput = document.getElementById("search-keyword");
    const filterPos = document.getElementById("filter-position");
    const filterStatus = document.getElementById("filter-status");

    if (searchBtn) searchBtn.addEventListener("click", loadEmployees);
    if (searchInput) searchInput.addEventListener("keyup", (e) => { if (e.key === "Enter") loadEmployees(); });
    if (filterPos) filterPos.addEventListener("change", loadEmployees);
    if (filterStatus) filterStatus.addEventListener("change", loadEmployees);

    // Form submit
    const empForm = document.getElementById("employee-form");
    if (empForm) {
        empForm.addEventListener("submit", saveEmployee);
    }
}

function openAddEmployeeModal() {
    document.getElementById("modal-title").innerText = "Thêm mới Hồ sơ Nhân sự";
    document.getElementById("employee-id").value = "";
    document.getElementById("employee-form").reset();
    document.getElementById("account-creation-section").classList.remove("hidden");
    document.getElementById("employee-modal").classList.remove("hidden");
}

function closeEmployeeModal() {
    document.getElementById("employee-modal").classList.add("hidden");
}

function editEmployee(id) {
    const emp = currentEmployees.find(e => e.id === id);
    if (!emp) return;

    document.getElementById("modal-title").innerText = `Cập nhật Hồ sơ: ${emp.ho_ten}`;
    document.getElementById("employee-id").value = emp.id;
    document.getElementById("emp-code").value = emp.ma_nhan_vien || "";
    document.getElementById("emp-fullname").value = emp.ho_ten || "";
    document.getElementById("emp-phone").value = emp.so_dien_thoai || "";
    document.getElementById("emp-email").value = emp.email || "";
    document.getElementById("emp-cccd").value = emp.cccd || "";
    document.getElementById("emp-address").value = emp.dia_chi || "";
    document.getElementById("emp-position").value = emp.ma_vi_tri || "";
    document.getElementById("emp-store").value = emp.ma_cua_hang || "";
    document.getElementById("emp-status").value = emp.trang_thai || "dang_lam";
    document.getElementById("emp-dob").value = emp.ngay_sinh || "";
    document.getElementById("emp-start-date").value = emp.ngay_vao_lam || "";

    // Ẩn tạo tài khoản khi đang sửa hồ sơ
    document.getElementById("account-creation-section").classList.add("hidden");
    document.getElementById("employee-modal").classList.remove("hidden");
}

async function saveEmployee(e) {
    e.preventDefault();
    const id = document.getElementById("employee-id").value;
    const isEdit = Boolean(id);

    const payload = {
        ma_nhan_vien: document.getElementById("emp-code").value.trim() || null,
        ho_ten: document.getElementById("emp-fullname").value.trim(),
        so_dien_thoai: document.getElementById("emp-phone").value.trim() || null,
        email: document.getElementById("emp-email").value.trim() || null,
        cccd: document.getElementById("emp-cccd").value.trim() || null,
        dia_chi: document.getElementById("emp-address").value.trim() || null,
        ma_vi_tri: parseInt(document.getElementById("emp-position").value) || null,
        ma_cua_hang: parseInt(document.getElementById("emp-store").value) || null,
        trang_thai: document.getElementById("emp-status").value,
        ngay_sinh: document.getElementById("emp-dob").value || null,
        ngay_vao_lam: document.getElementById("emp-start-date").value || null
    };

    if (!isEdit) {
        const createAcc = document.getElementById("create-account-checkbox")?.checked;
        if (createAcc) {
            payload.tao_tai_khoan = true;
            payload.ten_dang_nhap = document.getElementById("new-username").value.trim();
            payload.mat_khau = document.getElementById("new-password").value;
        }
    }

    try {
        if (isEdit) {
            await API.request(`/api/employees/${id}`, {
                method: "PUT",
                body: JSON.stringify(payload)
            });
            showToast("Cập nhật hồ sơ nhân sự thành công!", "success");
        } else {
            await API.request("/api/employees", {
                method: "POST",
                body: JSON.stringify(payload)
            });
            showToast("Thêm mới hồ sơ nhân sự thành công!", "success");
        }
        closeEmployeeModal();
        await loadEmployees();
    } catch (err) {
        showToast(err.message, "error");
    }
}

async function deleteEmployee(id, name) {
    if (!confirm(`Bạn có chắc chắn muốn xóa mềm nhân viên "${name}"?\nDữ liệu lịch sử chấm công & bảng lương vẫn được lưu trữ an toàn.`)) {
        return;
    }
    try {
        await API.request(`/api/employees/${id}`, { method: "DELETE" });
        showToast("Đã xóa mềm hồ sơ nhân sự!", "success");
        await loadEmployees();
    } catch (err) {
        showToast(err.message, "error");
    }
}

function viewEmployeeDetail(id) {
    const emp = currentEmployees.find(e => e.id === id);
    if (!emp) return;

    alert(`THÔNG TIN CHI TIẾT NHÂN SỰ:
Mã NV: ${emp.ma_nhan_vien || "Chưa có"}
Họ tên: ${emp.ho_ten}
Vị trí: ${emp.ten_vi_tri || "---"}
Chi nhánh: ${emp.ten_cua_hang || "---"}
Email: ${emp.email || "---"}
Số điện thoại: ${emp.so_dien_thoai || "---"}
Số CCCD: ${emp.cccd || "---"}
Ngày sinh: ${emp.ngay_sinh || "---"}
Ngày vào làm: ${emp.ngay_vao_lam || "---"}
Trạng thái: ${emp.trang_thai}
Tài khoản đăng nhập: ${emp.ten_dang_nhap || "Chưa tạo tài khoản"}`);
}
