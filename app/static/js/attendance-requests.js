// Sprint 5 - Màn 09: hàng đợi & duyệt yêu cầu bù/sửa công (FR-11A)
let requests = [];
let current = null;

document.addEventListener("DOMContentLoaded", () => {
    if (!API.isAdmin()) return;
    document.getElementById("f-type").innerHTML += Object.entries(REQUEST_TYPES)
        .map(([k, v]) => `<option value="${k}">${v}</option>`).join("");
    document.getElementById("f-status").value = queryParam("trang_thai") || "dang_mo";
    document.getElementById("f-type").value = queryParam("loai") || "";
    loadEmployees();
    ["f-status", "f-employee", "f-type"].forEach(id => document.getElementById(id).addEventListener("change", loadRequests));
    document.getElementById("btn-approve").addEventListener("click", approve);
    document.getElementById("btn-reject").addEventListener("click", reject);
    document.getElementById("btn-ask").addEventListener("click", ask);
    loadRequests().then(() => {
        const id = Number(queryParam("id"));
        if (id) showRequest(id);
    });
});

async function loadEmployees() {
    try {
        const items = await API.request("/api/shifts/schedulable-employees");
        const sel = document.getElementById("f-employee");
        sel.innerHTML += items.map(e => `<option value="${e.ma_nv}">${escapeHtml(e.ho_ten)} · ${escapeHtml(e.ma_nhan_vien || "")}</option>`).join("");
        sel.value = queryParam("ma_nv") || "";
    } catch (e) { /* bộ lọc không bắt buộc */ }
}

async function loadRequests() {
    const params = {
        trang_thai: document.getElementById("f-status").value,
        ma_nv: document.getElementById("f-employee").value,
        loai: document.getElementById("f-type").value
    };
    setQueryParams(params);
    try {
        requests = await API.request(`/api/attendance/requests?${buildQuery(params)}`);
        renderRequests();
    } catch (err) {
        showToast(err.message, "error");
    }
}

function renderRequests() {
    const body = document.getElementById("request-rows");
    if (!requests.length) {
        body.innerHTML = `<tr><td colspan="6" class="py-6 text-center text-[#71717a]">Không có yêu cầu nào</td></tr>`;
        return;
    }
    body.innerHTML = requests.map(y => `
        <tr class="${current && current.id === y.id ? "bg-[#fffaf3]" : ""}">
            <td class="py-2 px-2 whitespace-nowrap font-semibold">${shortDateTime(y.ngay_tao)}</td>
            <td class="py-2 px-2 text-xs"><span class="font-bold">${escapeHtml(y.ma_nhan_vien || "")} · ${escapeHtml(y.ho_ten || "")}</span><br>${formatDate(y.ngay_lam)} · ${escapeHtml(y.ten_ca || "")}</td>
            <td class="py-2 px-2 text-xs">${escapeHtml(y.ten_loai)}
                ${y.vuot_han_muc ? `<div class="text-[11px] font-bold text-amber-700">Vượt hạn mức tháng</div>` : ""}
                ${y.lech_nhieu ? `<div class="text-[11px] font-bold text-amber-700">Lệch &gt; 2 giờ</div>` : ""}</td>
            <td class="py-2 px-2">${statusBadge(REQUEST_STATUS, y.trang_thai)}</td>
            <td class="py-2 px-2 text-xs whitespace-nowrap">${y.han_xu_ly ? formatDateTime(y.han_xu_ly) : "-"}</td>
            <td class="py-2 px-2"><button type="button" onclick="showRequest(${y.id})" class="text-xs font-bold text-[#cf6800] hover:underline">${current && current.id === y.id ? "Đang xem" : "Xem yêu cầu"}</button></td>
        </tr>`).join("");
}

async function showRequest(id) {
    try {
        current = await API.request(`/api/attendance/requests/${id}`);
        const detail = await API.request(`/api/attendance/assignments/${current.ma_phan_cong}`);
        renderDetail(current, detail);
        renderRequests();
        setQueryParams({ id });
        document.getElementById("detail-wrap").classList.remove("hidden");
        document.getElementById("detail-wrap").scrollIntoView({ behavior: "smooth", block: "start" });
    } catch (err) {
        showToast(err.message, "error");
    }
}

function renderDetail(y, d) {
    const r = d.ca;
    document.getElementById("d-title").textContent = `${y.ten_loai} · ${formatDate(y.ngay_lam)}`;
    document.getElementById("d-employee").textContent = `${y.ho_ten || ""} · ${y.ma_nhan_vien || ""} · ${y.ten_vi_tri || ""}`;
    document.getElementById("d-shift").textContent = `Ca được phân: ${y.ten_ca || ""} ${formatTime(y.gio_bat_dau)}-${formatTime(y.gio_ket_thuc)}`;
    document.getElementById("d-flags").innerHTML = [
        y.vuot_han_muc ? `<span class="px-2 py-0.5 rounded-full text-[11px] font-bold bg-amber-100 text-amber-800">Vượt hạn mức tháng</span>` : "",
        y.lech_nhieu ? `<span class="px-2 py-0.5 rounded-full text-[11px] font-bold bg-amber-100 text-amber-800">Lệch &gt; 2 giờ · Cần lý do chi tiết</span>` : "",
        flagBadges(r.co)
    ].join(" ");
    document.getElementById("d-original").innerHTML = `
        <div>Vào: ${hhmm(r.gio_vao_goc || r.gio_vao)}</div>
        <div>Ra: ${r.gio_ra_goc || r.gio_ra ? hhmm(r.gio_ra_goc || r.gio_ra) : "chưa ghi nhận"}</div>
        <div>Tổng: ${r.so_gio_lam ? hoursText(r.so_gio_lam) : "chưa xác định"}</div>
        <div>Trạng thái: ${escapeHtml(r.ten_trang_thai)}</div>`;
    const proposal = [];
    if (y.gio_vao_de_xuat) proposal.push(`<div>Vào: ${shortDateTime(y.gio_vao_de_xuat)}</div>`);
    if (y.gio_ra_de_xuat) proposal.push(`<div>Ra: ${shortDateTime(y.gio_ra_de_xuat)}</div>`);
    if (y.ten_ca_dung) proposal.push(`<div>Chuyển sang: ${escapeHtml(y.ten_ca_dung)}</div>`);
    if (y.loai === "giai_trinh") proposal.push(`<div>Giải trình cờ, không đổi giờ</div>`);
    document.getElementById("d-proposal").innerHTML = proposal.join("") || "-";
    document.getElementById("d-reason").textContent = y.ly_do;
    const q = document.getElementById("d-question");
    q.classList.toggle("hidden", !y.cau_hoi_bo_sung);
    q.textContent = y.cau_hoi_bo_sung ? `Đã hỏi bổ sung: ${y.cau_hoi_bo_sung}` : "";
    document.getElementById("d-files").innerHTML = y.tep.length ? y.tep.map(f =>
        `<a href="${escapeHtml(f.duong_dan)}" target="_blank" class="px-3 py-1.5 rounded-lg border border-[#e6dfd5] text-xs font-bold hover:bg-[#faf6f0]">${escapeHtml(f.ten_tep)}${f.kich_thuoc ? ` · ${(f.kich_thuoc / 1048576).toFixed(1)} MB` : ""}</a>`
    ).join("") : `<span class="text-xs text-[#71717a]">Không có minh chứng</span>`;

    document.getElementById("d-location").innerHTML = `
        <div>Check-in: ${LOCATION_NAMES[r.vi_tri] || "-"}${r.khoang_cach_vao !== null ? ` · cách quán ${r.khoang_cach_vao} m` : ""}</div>
        <div>Tọa độ vào: ${d.vi_do_vao !== null ? `${d.vi_do_vao}, ${d.kinh_do_vao}` : "không có"}</div>
        <div>Check-out: ${r.gio_ra ? (r.khoang_cach_ra !== null ? `cách quán ${r.khoang_cach_ra} m` : "không định vị") : "không có dữ liệu"}</div>
        <div>IP: ${escapeHtml(r.ip_vao || "-")}${r.ip_ra && r.ip_ra !== r.ip_vao ? ` / ${escapeHtml(r.ip_ra)}` : ""}</div>
        <div>Thiết bị: ${escapeHtml((r.thiet_bi_vao || "-").substring(0, 12))}</div>`;
    document.getElementById("d-recent").innerHTML = d.yeu_cau_gan_day.length ? d.yeu_cau_gan_day.map(x =>
        `<li>${formatDate(x.ngay_lam)}: ${escapeHtml(x.ten_loai)} · ${escapeHtml(x.ten_trang_thai)}</li>`).join("")
        : `<li>Không có yêu cầu nào trong 30 ngày qua.</li>`;
    document.getElementById("d-detail-link").href = `/attendance-detail?pc=${y.ma_phan_cong}`;

    const open = ["cho_duyet", "can_bo_sung"].includes(y.trang_thai);
    document.querySelectorAll("#decision-card input, #decision-card button").forEach(el => { el.disabled = !open; });
    document.getElementById("decision-note").textContent = open
        ? (y.trang_thai === "can_bo_sung" ? "Đang chờ nhân viên bổ sung. Bạn vẫn có thể ra quyết định nếu đủ thông tin." : "")
        : `Yêu cầu đã ${y.ten_trang_thai.toLowerCase()}${y.nguoi_xu_ly ? ` bởi ${y.nguoi_xu_ly}` : ""}${y.ngay_xu_ly ? ` lúc ${formatDateTime(y.ngay_xu_ly)}` : ""}.`;
    ["a-note", "a-reject", "a-ask"].forEach(id => { document.getElementById(id).value = ""; });
    document.getElementById("a-waive").checked = false;
}

async function decide(path, body, message) {
    try {
        current = await API.request(`/api/attendance/requests/${current.id}/${path}`, { method: "POST", body });
        showToast(message);
        await loadRequests();
        showRequest(current.id);
    } catch (err) {
        showToast(err.message, "error");
    }
}

function approve() {
    const note = document.getElementById("a-note").value.trim();
    const waive = document.getElementById("a-waive").checked;
    if (waive && note.length < 5) return showToast("Miễn phạt cần ghi chú lý do", "error");
    decide("approve", { ghi_chu: note || null, mien_phat: waive, ly_do_mien_phat: waive ? note : null }, "Đã duyệt yêu cầu và cập nhật bản ghi công");
}

function reject() {
    const reason = document.getElementById("a-reject").value.trim();
    if (reason.length < 5) return showToast("Bắt buộc nhập lý do khi từ chối", "error");
    decide("reject", { ly_do: reason }, "Đã từ chối yêu cầu");
}

function ask() {
    const question = document.getElementById("a-ask").value.trim();
    if (question.length < 5) return showToast("Hãy nhập câu hỏi cụ thể cho nhân viên", "error");
    decide("ask", { cau_hoi: question }, "Đã gửi yêu cầu bổ sung cho nhân viên");
}
