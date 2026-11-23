// Trang Hợp đồng lao động (FR-05)
const CONTRACT_TYPES = ["Chính thức", "Thử việc", "Thời vụ", "Toàn thời gian", "Bán thời gian"];
let contracts = [];
let employeeOptions = [];

document.addEventListener("DOMContentLoaded", async () => {
    if (!API.getUser()) return;
    fillContractTypes();
    await loadEmployeeOptions();
    await Promise.all([loadContracts(), loadExpiring()]);
    bindEvents();
});

function fillContractTypes() {
    const options = CONTRACT_TYPES.map(t => `<option value="${t}">${t}</option>`).join("");
    document.getElementById("filter-type").innerHTML = `<option value="">Tất cả loại hợp đồng</option>${options}`;
    document.getElementById("ct-type").innerHTML = options;
}

async function loadEmployeeOptions() {
    try {
        const data = await API.request("/api/employees");
        employeeOptions = data.items;
    } catch (err) {
        showToast("Không tải được danh sách nhân viên: " + err.message, "error");
    }
    const options = employeeOptions
        .map(e => `<option value="${e.id}">${escapeHtml(e.ma_nhan_vien || "")} - ${escapeHtml(e.ho_ten)}</option>`)
        .join("");
    document.getElementById("filter-employee").innerHTML = `<option value="">Tất cả nhân viên</option>${options}`;
    document.getElementById("ct-employee").innerHTML = `<option value="">-- Chọn nhân viên --</option>${options}`;
}

async function loadContracts() {
    const params = new URLSearchParams();
    const emp = document.getElementById("filter-employee").value;
    const type = document.getElementById("filter-type").value;
    const status = document.getElementById("filter-status").value;
    if (emp) params.set("ma_nhan_vien", emp);
    if (type) params.set("loai_hop_dong", type);
    if (status) params.set("trang_thai", status);

    try {
        contracts = await API.request(`/api/contracts?${params}`);
        renderTable();
    } catch (err) {
        document.getElementById("contracts-tbody").innerHTML =
            `<tr><td colspan="7" class="py-10 text-center text-red-600">${escapeHtml(err.message)}</td></tr>`;
    }
}

async function loadExpiring() {
    try {
        const items = await API.request("/api/contracts/expiring?days=30");
        const box = document.getElementById("expiring-box");
        box.classList.toggle("hidden", items.length === 0);
        document.getElementById("expiring-count").textContent = `${items.length} hợp đồng`;
        document.getElementById("expiring-list").innerHTML = items.map(c => `
            <li class="flex justify-between gap-4">
                <span><strong>${escapeHtml(c.ho_ten)}</strong> (${escapeHtml(c.ma_nhan_vien_code || "")}) · ${escapeHtml(c.loai_hop_dong || "")}</span>
                <span class="font-semibold text-[#dc2626] whitespace-nowrap">Hết hạn ${formatDate(c.ngay_ket_thuc)} · còn ${c.so_ngay_con_lai} ngày</span>
            </li>`).join("");
    } catch (e) {
        // Không chặn trang nếu lỗi cảnh báo
    }
}

function renderTable() {
    const tbody = document.getElementById("contracts-tbody");
    if (!contracts.length) {
        tbody.innerHTML = `<tr><td colspan="7" class="py-10 text-center text-[#71717a]">Chưa có hợp đồng nào</td></tr>`;
        return;
    }
    tbody.innerHTML = contracts.map(c => `
        <tr class="transition-colors ${c.canh_bao_het_han ? "bg-amber-50 hover:bg-amber-100" : "hover:bg-[#faf7f2]"}">
            <td class="py-3.5 px-5">
                <div class="font-semibold text-[#18181b]">${escapeHtml(c.ho_ten_nhan_vien || "-")}</div>
                <div class="text-xs text-[#71717a]">${escapeHtml(c.ma_nhan_vien_code || "")}</div>
            </td>
            <td class="py-3.5 px-5 text-[#52525b]">${escapeHtml(c.loai_hop_dong || "-")}</td>
            <td class="py-3.5 px-5 text-[#52525b]">
                <div>${formatDate(c.ngay_bat_dau)} → ${formatDate(c.ngay_ket_thuc)}</div>
                ${c.canh_bao_het_han ? `<div class="text-xs font-semibold text-amber-700">Còn ${c.so_ngay_con_lai} ngày</div>` : ""}
            </td>
            <td class="py-3.5 px-5 text-right text-[#52525b] whitespace-nowrap">${formatMoney(c.muc_luong)}</td>
            <td class="py-3.5 px-5">
                ${c.file_dinh_kem ? `<a href="${escapeHtml(c.file_dinh_kem)}" target="_blank" rel="noopener" class="text-[#cf6800] font-semibold hover:underline">Xem file</a>` : `<span class="text-[#a1a1aa]">-</span>`}
            </td>
            <td class="py-3.5 px-5">${statusBadge(CONTRACT_STATUS, c.trang_thai)}</td>
            <td class="py-3.5 px-5 text-right whitespace-nowrap">
                <button class="text-[#cf6800] font-semibold hover:underline" onclick="openContractModal(${c.id})">Sửa</button>
                <button class="ml-2 text-red-600 font-semibold hover:underline" onclick="deleteContract(${c.id})">Xóa</button>
            </td>
        </tr>`).join("");
}

function bindEvents() {
    ["filter-employee", "filter-type", "filter-status"].forEach(id =>
        document.getElementById(id).addEventListener("change", loadContracts)
    );
    document.getElementById("contract-form").addEventListener("submit", saveContract);
}

function openContractModal(id = null) {
    document.getElementById("contract-form").reset();
    document.getElementById("ct-id").value = id || "";
    const c = id ? contracts.find(x => x.id === id) : null;
    document.getElementById("contract-modal-title").textContent = c ? "Sửa hợp đồng" : "Thêm hợp đồng";

    const empSelect = document.getElementById("ct-employee");
    empSelect.disabled = !!c;  // Không đổi nhân viên của hợp đồng đã tạo
    if (c) {
        empSelect.value = c.ma_nhan_vien;
        document.getElementById("ct-type").value = c.loai_hop_dong || CONTRACT_TYPES[0];
        document.getElementById("ct-status").value = c.trang_thai || "hieu_luc";
        document.getElementById("ct-start").value = c.ngay_bat_dau || "";
        document.getElementById("ct-end").value = c.ngay_ket_thuc || "";
        document.getElementById("ct-salary").value = c.muc_luong ?? "";
        document.getElementById("ct-salary-code").value = c.ma_bang_luong || "";
    }
    document.getElementById("ct-current-file").innerHTML = c && c.file_dinh_kem
        ? `File hiện tại: <a href="${escapeHtml(c.file_dinh_kem)}" target="_blank" rel="noopener" class="text-[#cf6800] underline">xem</a> (chọn file mới để thay)`
        : "";
    document.getElementById("contract-modal").classList.remove("hidden");
}

function closeContractModal() {
    document.getElementById("contract-modal").classList.add("hidden");
}

async function saveContract(e) {
    e.preventDefault();
    const id = document.getElementById("ct-id").value;
    const start = document.getElementById("ct-start").value;
    const end = document.getElementById("ct-end").value;
    if (start && end && start > end) {
        showToast("Ngày bắt đầu không được lớn hơn ngày kết thúc", "error");
        return;
    }
    const salary = document.getElementById("ct-salary").value;
    const payload = {
        loai_hop_dong: document.getElementById("ct-type").value,
        trang_thai: document.getElementById("ct-status").value,
        ngay_bat_dau: start || null,
        ngay_ket_thuc: end || null,
        muc_luong: salary === "" ? null : Number(salary),
        ma_bang_luong: document.getElementById("ct-salary-code").value.trim() || null
    };

    const btn = document.getElementById("ct-submit");
    btn.disabled = true;
    try {
        let saved;
        if (id) {
            saved = await API.request(`/api/contracts/${id}`, { method: "PUT", body: payload });
        } else {
            payload.ma_nhan_vien = Number(document.getElementById("ct-employee").value);
            if (!payload.ma_nhan_vien) throw new Error("Vui lòng chọn nhân viên");
            saved = await API.request("/api/contracts", { method: "POST", body: payload });
        }
        const file = document.getElementById("ct-file").files[0];
        if (file) {
            await API.upload(`/api/contracts/${saved.id}/file`, file);
        }
        showToast(id ? "Đã cập nhật hợp đồng" : "Đã thêm hợp đồng");
        closeContractModal();
        await Promise.all([loadContracts(), loadExpiring()]);
    } catch (err) {
        showToast(err.message, "error");
    } finally {
        btn.disabled = false;
    }
}

async function deleteContract(id) {
    const c = contracts.find(x => x.id === id);
    if (!confirm(`Xóa hợp đồng ${c.loai_hop_dong} của ${c.ho_ten_nhan_vien}?`)) return;
    try {
        await API.request(`/api/contracts/${id}`, { method: "DELETE" });
        showToast("Đã xóa hợp đồng");
        await Promise.all([loadContracts(), loadExpiring()]);
    } catch (err) {
        showToast(err.message, "error");
    }
}
