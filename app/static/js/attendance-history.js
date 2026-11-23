// Sprint 5 - Lịch sử công của nhân viên (FR-11) và yêu cầu bù/sửa công (FR-11A)
let historyRows = [];
let myRequests = [];
let formContext = null;   // { mode: "create" | "update", row, request, detail }

document.addEventListener("DOMContentLoaded", () => {
    const user = API.getUser();
    if (!user) return;
    if (!user.ma_nv) {
        document.getElementById("no-profile").classList.remove("hidden");
        document.getElementById("history-body-wrap").classList.add("hidden");
        return;
    }
    const today = toISODate(new Date());
    document.getElementById("f-from").value = queryParam("tu_ngay") || today.substring(0, 8) + "01";
    document.getElementById("f-to").value = queryParam("den_ngay") || today;
    document.getElementById("f-status").value = queryParam("trang_thai") || "";
    document.getElementById("btn-filter").addEventListener("click", loadHistory);
    document.querySelectorAll(".tab-btn").forEach(btn => btn.addEventListener("click", () => switchTab(btn.dataset.tab)));
    document.getElementById("r-type").addEventListener("change", renderTypeFields);
    document.getElementById("request-form").addEventListener("submit", submitRequest);

    if (queryParam("tab") === "requests") switchTab("requests");
    loadHistory();
    loadMyRequests();
    // Mở thẳng form yêu cầu khi đi từ trang Chấm công / thông báo (?pc=)
    const pc = Number(queryParam("pc"));
    if (pc) openRequestForm(pc);
});

function switchTab(tab) {
    document.querySelectorAll(".tab-btn").forEach(btn => {
        const active = btn.dataset.tab === tab;
        btn.classList.toggle("border-[#cf6800]", active);
        btn.classList.toggle("text-[#cf6800]", active);
        btn.classList.toggle("border-transparent", !active);
        btn.classList.toggle("text-[#71717a]", !active);
    });
    document.getElementById("tab-history").classList.toggle("hidden", tab !== "history");
    document.getElementById("tab-requests").classList.toggle("hidden", tab !== "requests");
    setQueryParams({ tab: tab === "requests" ? "requests" : null });
}

// ---------- Lịch sử công ----------

async function loadHistory() {
    const params = {
        tu_ngay: document.getElementById("f-from").value,
        den_ngay: document.getElementById("f-to").value,
        trang_thai: document.getElementById("f-status").value
    };
    setQueryParams(params);
    try {
        const data = await API.request(`/api/attendance/me?${buildQuery(params)}`);
        historyRows = data.items;
        const t = data.thong_ke;
        document.getElementById("s-done").textContent = `${t.so_ca_da_lam}/${t.tong_ca}`;
        document.getElementById("s-hours").textContent = hoursText(t.tong_gio_lam);
        document.getElementById("s-late").textContent = `${t.di_tre} / ${t.ve_som}`;
        document.getElementById("s-absent").textContent = t.vang_mat;
        document.getElementById("s-missing").textContent = t.chua_check_out;
        renderHistory();
    } catch (err) {
        showToast(err.message, "error");
    }
}

function renderHistory() {
    const body = document.getElementById("history-rows");
    if (!historyRows.length) {
        body.innerHTML = `<tr><td colspan="6" class="py-6 text-center text-[#71717a]">Không có ca nào trong khoảng này</td></tr>`;
        return;
    }
    body.innerHTML = historyRows.map(r => {
        let action = `<button type="button" onclick="showDetail(${r.ma_phan_cong})" class="text-xs font-bold text-[#cf6800] hover:underline">Chi tiết</button>`;
        if (r.ma_yeu_cau_dang_mo) {
            action += ` <span class="text-[11px] text-amber-700 font-semibold">· Đang có yêu cầu</span>`;
        } else if (r.co_the_gui_yeu_cau) {
            action += ` · <button type="button" onclick="openRequestForm(${r.ma_phan_cong})" class="text-xs font-bold text-[#cf6800] hover:underline">Gửi yêu cầu</button>`;
        }
        return `
        <tr>
            <td class="py-2 px-2 font-semibold whitespace-nowrap">${dayLabel(r.ngay_lam)}</td>
            <td class="py-2 px-2 text-xs text-[#52525b]">${shiftText(r)}</td>
            <td class="py-2 px-2 whitespace-nowrap">${hhmm(r.gio_vao)} / ${hhmm(r.gio_ra)}</td>
            <td class="py-2 px-2">${r.so_gio_lam ? hoursText(r.so_gio_lam) : "-"}</td>
            <td class="py-2 px-2">${attendanceLabels(r.nhan) || statusBadge(ATTENDANCE_STATUS, r.trang_thai)}</td>
            <td class="py-2 px-2 whitespace-nowrap">${action}</td>
        </tr>`;
    }).join("");
}

async function showDetail(pcId) {
    try {
        const d = await API.request(`/api/attendance/assignments/${pcId}`);
        const r = d.ca;
        document.getElementById("detail-title").textContent = `${r.ten_ca} · ${formatDate(r.ngay_lam)}`;
        const logs = d.nhat_ky.length ? d.nhat_ky.map(l => `
            <li class="border-l-2 border-[#e6dfd5] pl-3">
                <div class="font-semibold">${escapeHtml(l.ten_hanh_dong)} <span class="text-[11px] text-[#71717a]">${formatDateTime(l.thoi_gian)}</span></div>
                ${l.ly_do ? `<div class="text-xs text-[#52525b]">Lý do: ${escapeHtml(l.ly_do)}</div>` : ""}
                ${l.nguoi_thuc_hien ? `<div class="text-xs text-[#71717a]">Người thực hiện: ${escapeHtml(l.nguoi_thuc_hien)}</div>` : ""}
            </li>`).join("") : `<li class="text-[#71717a]">Chưa có thay đổi nào.</li>`;
        const reqs = d.yeu_cau.length ? d.yeu_cau.map(requestLine).join("") : `<li class="text-[#71717a]">Chưa có yêu cầu.</li>`;
        document.getElementById("detail-content").innerHTML = `
            <div class="grid grid-cols-2 gap-3">
                <div class="rounded-xl bg-[#faf6f0] p-3"><div class="text-[11px] font-bold uppercase text-[#71717a]">Giờ vào</div><div class="font-extrabold">${hhmm(r.gio_vao)}</div>
                    ${r.gio_vao_goc && r.gio_vao_goc !== r.gio_vao ? `<div class="text-[11px] text-[#71717a]">Gốc: ${hhmm(r.gio_vao_goc)}</div>` : ""}</div>
                <div class="rounded-xl bg-[#faf6f0] p-3"><div class="text-[11px] font-bold uppercase text-[#71717a]">Giờ ra</div><div class="font-extrabold">${hhmm(r.gio_ra)}</div>
                    ${r.gio_ra_goc && r.gio_ra_goc !== r.gio_ra ? `<div class="text-[11px] text-[#71717a]">Gốc: ${hhmm(r.gio_ra_goc)}</div>` : ""}</div>
            </div>
            <div class="flex flex-wrap gap-2">${attendanceLabels(r.nhan) || statusBadge(ATTENDANCE_STATUS, r.trang_thai)}</div>
            <div class="text-xs text-[#52525b]">Giờ được tính: <strong>${hoursText(r.so_gio_lam)}</strong> · Trễ ${r.phut_di_tre} phút · Sớm ${r.phut_ve_som} phút
                ${r.phut_vuot_ca ? ` · Vượt ca ${r.phut_vuot_ca} phút (duyệt ${r.phut_vuot_ca_duyet})` : ""}</div>
            ${r.ly_do_huy ? `<div class="text-xs text-[#52525b]">Lý do hủy ca: ${escapeHtml(r.ly_do_huy)}</div>` : ""}
            ${r.ly_do_mien_phat ? `<div class="text-xs text-emerald-700">Miễn phạt: ${escapeHtml(r.ly_do_mien_phat)}</div>` : ""}
            <div><h4 class="text-xs font-bold uppercase text-[#52525b] mb-2">Yêu cầu bù/sửa công</h4><ul class="space-y-2">${reqs}</ul></div>
            <div><h4 class="text-xs font-bold uppercase text-[#52525b] mb-2">Nhật ký thay đổi</h4><ul class="space-y-2">${logs}</ul></div>
            ${r.co_the_gui_yeu_cau && !r.ma_yeu_cau_dang_mo ? `<button type="button" onclick="closeModal('detail-modal'); openRequestForm(${r.ma_phan_cong})" class="btn-primary w-full">Gửi yêu cầu bù/sửa công cho ca này</button>` : ""}
            ${r.han_gui_yeu_cau ? `<p class="text-[11px] text-[#71717a]">Hạn gửi yêu cầu: ${formatDateTime(r.han_gui_yeu_cau)}</p>` : ""}`;
        openModal("detail-modal");
    } catch (err) {
        showToast(err.message, "error");
    }
}

function requestLine(y) {
    return `<li class="rounded-xl border border-[#f0e9df] p-3">
        <div class="flex items-center justify-between gap-2"><span class="font-semibold">${escapeHtml(y.ten_loai)}</span>${statusBadge(REQUEST_STATUS, y.trang_thai)}</div>
        <div class="text-xs text-[#52525b] mt-1">${escapeHtml(y.ly_do)}</div>
        ${y.cau_hoi_bo_sung && y.trang_thai === "can_bo_sung" ? `<div class="text-xs text-sky-700 mt-1">Quản lý hỏi: ${escapeHtml(y.cau_hoi_bo_sung)}</div>` : ""}
        ${y.ly_do_tu_choi ? `<div class="text-xs text-red-700 mt-1">Lý do từ chối: ${escapeHtml(y.ly_do_tu_choi)}</div>` : ""}
    </li>`;
}

// ---------- Yêu cầu của tôi ----------

async function loadMyRequests() {
    try {
        myRequests = await API.request("/api/attendance/requests/me");
        const open = myRequests.filter(y => ["cho_duyet", "can_bo_sung"].includes(y.trang_thai)).length;
        const badge = document.getElementById("open-count");
        badge.textContent = open;
        badge.classList.toggle("hidden", !open);
        renderRequests();
    } catch (err) {
        showToast(err.message, "error");
    }
}

function renderRequests() {
    const body = document.getElementById("request-rows");
    if (!myRequests.length) {
        body.innerHTML = `<tr><td colspan="6" class="py-6 text-center text-[#71717a]">Bạn chưa gửi yêu cầu nào</td></tr>`;
        return;
    }
    body.innerHTML = myRequests.map(y => {
        const proposal = [y.gio_vao_de_xuat ? `Vào ${shortDateTime(y.gio_vao_de_xuat)}` : "", y.gio_ra_de_xuat ? `Ra ${shortDateTime(y.gio_ra_de_xuat)}` : "",
            y.ten_ca_dung ? `→ ${escapeHtml(y.ten_ca_dung)}` : ""].filter(Boolean).join("<br>") || "-";
        let actions = "";
        if (y.trang_thai === "can_bo_sung") {
            actions += `<button type="button" onclick="openUpdateForm(${y.id})" class="text-xs font-bold text-[#cf6800] hover:underline">Bổ sung</button> · `;
        }
        if (["cho_duyet", "can_bo_sung"].includes(y.trang_thai)) {
            actions += `<button type="button" onclick="cancelRequest(${y.id})" class="text-xs font-bold text-red-600 hover:underline">Hủy</button>`;
        }
        const note = y.trang_thai === "can_bo_sung" && y.cau_hoi_bo_sung
            ? `<div class="text-[11px] text-sky-700 mt-1">Quản lý hỏi: ${escapeHtml(y.cau_hoi_bo_sung)}</div>`
            : (y.ly_do_tu_choi ? `<div class="text-[11px] text-red-700 mt-1">${escapeHtml(y.ly_do_tu_choi)}</div>` : "");
        return `
        <tr>
            <td class="py-2 px-2 whitespace-nowrap">${formatDateTime(y.ngay_tao)}</td>
            <td class="py-2 px-2 text-xs">${formatDate(y.ngay_lam)}<br>${escapeHtml(y.ten_ca || "")}</td>
            <td class="py-2 px-2 text-xs font-semibold">${escapeHtml(y.ten_loai)}
                ${y.vuot_han_muc ? `<div class="text-[11px] text-amber-700">Vượt hạn mức tháng</div>` : ""}</td>
            <td class="py-2 px-2 text-xs">${proposal}</td>
            <td class="py-2 px-2">${statusBadge(REQUEST_STATUS, y.trang_thai)}${note}</td>
            <td class="py-2 px-2 whitespace-nowrap">${actions || "-"}</td>
        </tr>`;
    }).join("");
}

async function cancelRequest(id) {
    if (!confirm("Hủy yêu cầu này?")) return;
    try {
        await API.request(`/api/attendance/requests/${id}/cancel`, { method: "POST" });
        showToast("Đã hủy yêu cầu");
        loadMyRequests();
        loadHistory();
    } catch (err) {
        showToast(err.message, "error");
    }
}

// ---------- Form gửi / bổ sung yêu cầu ----------

function allowedTypes(r) {
    const hasIn = !!r.gio_vao, hasOut = !!r.gio_ra;
    const types = [];
    if (!hasIn) types.push("bu_ca_hai", "bu_check_in");
    if (hasIn && !hasOut) types.push("bu_check_out");
    if (hasIn) types.push("sua_gio");
    if (hasIn) types.push("sua_ca");
    if ((r.co || []).some(c => c !== "vuot_han_muc")) types.push("giai_trinh");
    return types;
}

async function openRequestForm(pcId) {
    try {
        const detail = await API.request(`/api/attendance/assignments/${pcId}`);
        const r = detail.ca;
        if (!r.co_the_gui_yeu_cau) {
            showToast(r.ma_yeu_cau_dang_mo ? "Ca này đang có yêu cầu chưa xử lý" : "Ca này không còn trong hạn gửi yêu cầu", "warning");
            return;
        }
        formContext = { mode: "create", row: r, detail };
        fillForm(r, null, detail);
    } catch (err) {
        showToast(err.message, "error");
    }
}

async function openUpdateForm(id) {
    const y = myRequests.find(x => x.id === id);
    if (!y) return;
    try {
        const detail = await API.request(`/api/attendance/assignments/${y.ma_phan_cong}`);
        formContext = { mode: "update", row: detail.ca, request: y, detail };
        fillForm(detail.ca, y, detail);
    } catch (err) {
        showToast(err.message, "error");
    }
}

function fillForm(r, y, detail) {
    document.getElementById("request-title").textContent = y ? "Bổ sung thông tin yêu cầu" : "Gửi yêu cầu bù/sửa công";
    document.getElementById("request-shift").innerHTML = `
        <div class="font-bold">${escapeHtml(r.ten_ca)} · ${formatDate(r.ngay_lam)} (${formatTime(r.gio_bat_dau)}-${formatTime(r.gio_ket_thuc)})</div>
        <div class="text-xs text-[#52525b] mt-1">Đã ghi nhận: vào ${hhmm(r.gio_vao)}, ra ${hhmm(r.gio_ra)}</div>`;
    const q = document.getElementById("request-question");
    q.classList.toggle("hidden", !(y && y.cau_hoi_bo_sung));
    q.textContent = y && y.cau_hoi_bo_sung ? `Quản lý cần bổ sung: ${y.cau_hoi_bo_sung}` : "";

    const typeSel = document.getElementById("r-type");
    const types = y ? [y.loai] : allowedTypes(r);
    typeSel.innerHTML = types.map(t => `<option value="${t}">${REQUEST_TYPES[t]}</option>`).join("");
    typeSel.disabled = !!y;

    const startDefault = combineDateTime(r.ngay_lam, r.gio_bat_dau);
    let endDefault = combineDateTime(r.ngay_lam, r.gio_ket_thuc);
    if (r.gio_ket_thuc && r.gio_bat_dau && r.gio_ket_thuc < r.gio_bat_dau) endDefault = combineDateTime(addDays(r.ngay_lam, 1), r.gio_ket_thuc);
    document.getElementById("r-in").value = y ? toLocalInput(y.gio_vao_de_xuat) : (toLocalInput(r.gio_vao) || startDefault);
    document.getElementById("r-out").value = y ? toLocalInput(y.gio_ra_de_xuat) : (toLocalInput(r.gio_ra) || endDefault);
    document.getElementById("r-shift").innerHTML = (detail.ca_cung_ngay || [])
        .filter(c => !c.da_co_cham_cong)
        .map(c => `<option value="${c.ma_phan_cong}" ${y && y.ma_phan_cong_dung === c.ma_phan_cong ? "selected" : ""}>${escapeHtml(c.ten_ca)}</option>`).join("")
        || `<option value="">Không có ca khác trong ngày</option>`;
    document.getElementById("r-reason").value = y ? y.ly_do : "";
    document.getElementById("r-files").value = "";
    renderExistingFiles(y);
    document.getElementById("r-deadline").textContent = r.han_gui_yeu_cau ? `Hạn gửi: ${formatDateTime(r.han_gui_yeu_cau)}` : "";
    document.getElementById("r-submit").textContent = y ? "Gửi lại cho Quản lý" : "Gửi yêu cầu";
    renderTypeFields();
    openModal("request-modal");
}

function renderExistingFiles(y) {
    const box = document.getElementById("r-existing-files");
    box.innerHTML = y && y.tep.length ? y.tep.map(f => `
        <div class="flex items-center justify-between text-xs rounded-lg bg-[#faf6f0] px-3 py-1.5">
            <a href="${escapeHtml(f.duong_dan)}" target="_blank" class="font-semibold hover:underline">${escapeHtml(f.ten_tep)}</a>
            <button type="button" onclick="removeFile(${y.id}, ${f.id})" class="text-red-600 font-bold">Xóa</button>
        </div>`).join("") : "";
}

async function removeFile(requestId, fileId) {
    try {
        const updated = await API.request(`/api/attendance/requests/${requestId}/files/${fileId}`, { method: "DELETE" });
        formContext.request = updated;
        renderExistingFiles(updated);
        loadMyRequests();
    } catch (err) {
        showToast(err.message, "error");
    }
}

function renderTypeFields() {
    const t = document.getElementById("r-type").value;
    document.getElementById("r-in-wrap").classList.toggle("hidden", !["bu_check_in", "bu_ca_hai", "sua_gio"].includes(t));
    document.getElementById("r-out-wrap").classList.toggle("hidden", !["bu_check_out", "bu_ca_hai", "sua_gio"].includes(t));
    document.getElementById("r-shift-wrap").classList.toggle("hidden", t !== "sua_ca");
}

async function submitRequest(e) {
    e.preventDefault();
    if (!formContext) return;
    const t = document.getElementById("r-type").value;
    const files = Array.from(document.getElementById("r-files").files);
    if (files.length > 3) return showToast("Tối đa 3 tệp minh chứng", "error");
    const tooBig = files.find(f => f.size > 5 * 1024 * 1024);
    if (tooBig) return showToast(`Tệp ${tooBig.name} vượt quá 5 MB`, "error");

    const useIn = ["bu_check_in", "bu_ca_hai", "sua_gio"].includes(t);
    const useOut = ["bu_check_out", "bu_ca_hai", "sua_gio"].includes(t);
    const payload = {
        gio_vao_de_xuat: useIn && document.getElementById("r-in").value ? document.getElementById("r-in").value + ":00" : null,
        gio_ra_de_xuat: useOut && document.getElementById("r-out").value ? document.getElementById("r-out").value + ":00" : null,
        ma_phan_cong_dung: t === "sua_ca" ? Number(document.getElementById("r-shift").value) || null : null,
        ly_do: document.getElementById("r-reason").value.trim()
    };
    if (payload.ly_do.length < 10) return showToast("Lý do bắt buộc, tối thiểu 10 ký tự", "error");

    const btn = document.getElementById("r-submit");
    btn.disabled = true;
    try {
        let saved;
        if (formContext.mode === "update") {
            saved = await API.request(`/api/attendance/requests/${formContext.request.id}`, { method: "PUT", body: payload });
        } else {
            saved = await API.request("/api/attendance/requests", {
                method: "POST", body: { ...payload, ma_phan_cong: formContext.row.ma_phan_cong, loai: t }
            });
        }
        for (const f of files) {
            await API.upload(`/api/attendance/requests/${saved.id}/files`, f);
        }
        closeModal("request-modal");
        showToast(saved.vuot_han_muc
            ? "Đã gửi yêu cầu. Lưu ý: bạn đã vượt hạn mức yêu cầu trong tháng, Quản lý sẽ xem xét kỹ hơn."
            : "Đã gửi yêu cầu, Quản lý sẽ xử lý trong 3 ngày", saved.vuot_han_muc ? "warning" : "success");
        setQueryParams({ pc: null });
        loadHistory();
        loadMyRequests();
    } catch (err) {
        showToast(err.message, "error");
    } finally {
        btn.disabled = false;
    }
}
