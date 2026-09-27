// Contract Management (FR-05)
let currentContracts = [];
let employeesList = [];

document.addEventListener("DOMContentLoaded", async () => {
    checkAuthRedirect();
    await loadEmployeesDropdown();
    await loadExpiringAlerts();
    await loadContracts();
    setupEventListeners();
});

async function loadEmployeesDropdown() {
    try {
        const data = await API.request("/api/employees");
        employeesList = data.items || [];
        const select = document.getElementById("contract-employee");
        if (select) {
            select.innerHTML = '<option value="">-- Chọn nhân viên --</option>' +
                employeesList.map(e => `<option value="${e.id}">${e.ma_nhan_vien || "NV" + e.id} - ${e.ho_ten}</option>`).join("");
        }
    } catch (err) {
        console.error("Lỗi nạp danh sách nhân viên cho hợp đồng:", err);
    }
}

async function loadExpiringAlerts() {
    const alertBox = document.getElementById("expiring-contracts-alert");
    if (!alertBox) return;

    try {
        const expiring = await API.request("/api/contracts/expiring?days=30");
        if (expiring && expiring.length > 0) {
            alertBox.classList.remove("hidden");
            const listHtml = expiring.map(c => `
                <div class="flex items-center justify-between py-2 border-b border-amber-200 last:border-0 text-sm">
                    <div>
                        <span class="font-bold text-amber-950">${c.ho_ten}</span> (${c.ma_nhan_vien_code || "NV" + c.ma_nhan_vien}) - 
                        Loại HĐ: <span class="font-medium">${c.loai_hop_dong || "---"}</span>
                    </div>
                    <div class="flex items-center gap-3">
                        <span class="text-xs text-gray-600">Hết hạn: ${c.ngay_ket_thuc}</span>
                        <span class="px-2 py-0.5 rounded text-xs font-bold bg-amber-200 text-amber-900">
                            Còn ${c.so_ngay_con_lai} ngày
                        </span>
                    </div>
                </div>
            `).join("");
            document.getElementById("expiring-contracts-list").innerHTML = listHtml;
        } else {
            alertBox.classList.add("hidden");
        }
    } catch (err) {
        console.error("Lỗi tải cảnh báo hợp đồng:", err);
    }
}

async function loadContracts() {
    const tbody = document.getElementById("contracts-tbody");
    if (!tbody) return;

    tbody.innerHTML = `<tr><td colspan="7" class="text-center py-8 text-gray-500">Đang tải danh sách hợp đồng...</td></tr>`;

    try {
        const contracts = await API.request("/api/contracts");
        currentContracts = contracts || [];
        renderContractsTable(currentContracts);
    } catch (err) {
        tbody.innerHTML = `<tr><td colspan="7" class="text-center py-8 text-red-500">${err.message}</td></tr>`;
    }
}

function renderContractsTable(list) {
    const tbody = document.getElementById("contracts-tbody");
    if (!tbody) return;

    if (list.length === 0) {
        tbody.innerHTML = `<tr><td colspan="7" class="text-center py-8 text-gray-500">Chưa có hợp đồng lao động nào</td></tr>`;
        return;
    }

    const formatCurrency = (amount) => {
        if (!amount) return "---";
        return new Intl.NumberFormat('vi-VN', { style: 'currency', currency: 'VND' }).format(amount);
    };

    tbody.innerHTML = list.map(c => `
        <tr class="border-b border-gray-100 hover:bg-amber-50/30 transition-colors">
            <td class="py-3 px-4 font-mono text-sm font-semibold text-gray-800">HD-${c.id}</td>
            <td class="py-3 px-4">
                <div class="font-medium text-gray-900">${c.ho_ten_nhan_vien || "---"}</div>
                <div class="text-xs text-gray-500">${c.ma_nhan_vien_code || ""}</div>
            </td>
            <td class="py-3 px-4 text-sm font-medium text-amber-950">${c.loai_hop_dong || "---"}</td>
            <td class="py-3 px-4 text-sm font-semibold text-emerald-800">${formatCurrency(c.muc_luong)}</td>
            <td class="py-3 px-4 text-sm text-gray-600">
                ${c.ngay_bat_dau || "---"} &rarr; ${c.ngay_ket_thuc || "Vô thời hạn"}
            </td>
            <td class="py-3 px-4">
                ${c.canh_bao_het_han ? `
                    <span class="px-2.5 py-1 text-xs font-bold rounded-full bg-amber-100 text-amber-800 border border-amber-300 animate-pulse">
                        Sắp hết hạn (${c.so_ngay_con_lai} ngày)
                    </span>
                ` : `
                    <span class="px-2.5 py-1 text-xs font-semibold rounded-full ${c.trang_thai === 'hieu_luc' ? 'badge-active' : 'badge-resigned'}">
                        ${c.trang_thai === 'hieu_luc' ? 'Hiệu lực' : 'Hết hạn'}
                    </span>
                `}
            </td>
            <td class="py-3 px-4 text-right space-x-1 whitespace-nowrap">
                <button onclick="editContract(${c.id})" class="p-1.5 text-amber-700 hover:bg-amber-50 rounded" title="Sửa hợp đồng">
                    <svg class="w-4 h-4 inline" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M11 5H6a2 2 0 00-2 2v11a2 2 0 002 2h11a2 2 0 002-2v-5m-1.414-9.414a2 2 0 112.828 2.828L11.828 15H9v-2.828l8.586-8.586z"/></svg>
                </button>
                <button onclick="deleteContract(${c.id})" class="p-1.5 text-red-600 hover:bg-red-50 rounded" title="Xóa hợp đồng">
                    <svg class="w-4 h-4 inline" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16"/></svg>
                </button>
            </td>
        </tr>
    `).join("");
}

function setupEventListeners() {
    const form = document.getElementById("contract-form");
    if (form) form.addEventListener("submit", saveContract);
}

function openAddContractModal() {
    document.getElementById("contract-modal-title").innerText = "Thêm mới Hợp đồng Lao động";
    document.getElementById("contract-id").value = "";
    document.getElementById("contract-form").reset();
    document.getElementById("contract-employee").disabled = false;
    document.getElementById("contract-modal").classList.remove("hidden");
}

function closeContractModal() {
    document.getElementById("contract-modal").classList.add("hidden");
}

function editContract(id) {
    const c = currentContracts.find(item => item.id === id);
    if (!c) return;

    document.getElementById("contract-modal-title").innerText = `Cập nhật Hợp đồng: HD-${c.id}`;
    document.getElementById("contract-id").value = c.id;
    document.getElementById("contract-employee").value = c.ma_nhan_vien;
    document.getElementById("contract-employee").disabled = true;
    document.getElementById("contract-type").value = c.loai_hop_dong || "Toàn thời gian";
    document.getElementById("contract-salary").value = c.muc_luong || "";
    document.getElementById("contract-start-date").value = c.ngay_bat_dau || "";
    document.getElementById("contract-end-date").value = c.ngay_ket_thuc || "";
    document.getElementById("contract-status").value = c.trang_thai || "hieu_luc";

    document.getElementById("contract-modal").classList.remove("hidden");
}

async function saveContract(e) {
    e.preventDefault();
    const id = document.getElementById("contract-id").value;
    const isEdit = Boolean(id);

    const payload = {
        ma_nhan_vien: parseInt(document.getElementById("contract-employee").value),
        loai_hop_dong: document.getElementById("contract-type").value,
        muc_luong: parseFloat(document.getElementById("contract-salary").value) || null,
        ngay_bat_dau: document.getElementById("contract-start-date").value || null,
        ngay_ket_thuc: document.getElementById("contract-end-date").value || null,
        trang_thai: document.getElementById("contract-status").value
    };

    if (!payload.ma_nhan_vien) {
        showToast("Vui lòng chọn nhân viên cho hợp đồng!", "warning");
        return;
    }

    try {
        if (isEdit) {
            await API.request(`/api/contracts/${id}`, {
                method: "PUT",
                body: JSON.stringify(payload)
            });
            showToast("Cập nhật hợp đồng thành công!", "success");
        } else {
            await API.request("/api/contracts", {
                method: "POST",
                body: JSON.stringify(payload)
            });
            showToast("Thêm hợp đồng mới thành công!", "success");
        }
        closeContractModal();
        await loadExpiringAlerts();
        await loadContracts();
    } catch (err) {
        showToast(err.message, "error");
    }
}

async function deleteContract(id) {
    if (!confirm("Bạn có chắc chắn muốn xóa hợp đồng này?")) return;
    try {
        await API.request(`/api/contracts/${id}`, { method: "DELETE" });
        showToast("Đã xóa hợp đồng thành công!", "success");
        await loadExpiringAlerts();
        await loadContracts();
    } catch (err) {
        showToast(err.message, "error");
    }
}
