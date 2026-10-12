// Sprint 5 - Màn 11: điều chỉnh trực tiếp / hàng loạt, chốt kỳ, hủy ca
const adjustPc = Number(queryParam("pc"));
let adjustDetail = null;
let bulkRows = [];

document.addEventListener("DOMContentLoaded", () => {
    if (!API.isAdmin()) return;
    document.querySelectorAll(".tab-btn").forEach(b => b.addEventListener("click", () => switchTab(b.dataset.tab)));
    const initial = queryParam("mode") || (adjustPc ? "direct" : "bulk");
    switchTab(["direct", "bulk", "lock"].includes(initial) ? initial : "direct");

    // Trực tiếp
    ["d-in", "d-out", "d-clear-out"].forEach(id => document.getElementById(id).addEventListener("input", renderPreview));
    document.getElementById("direct-form").addEventListener("submit", saveDirect);
    document.getElementById("cancel-form").addEventListener("submit", cancelShift);
    if (adjustPc) loadDirect();

    // Hàng loạt
    const today = toISODate(new Date());
    document.getElementById("b-day").value = queryParam("ngay") || today;
    document.getElementById("b-day").addEventListener("change", loadBulk);
    document.getElementById("b-preview-btn").addEventListener("click", () => submitBulk(true));
    document.getElementById("b-apply-btn").addEventListener("click", () => submitBulk(false));
    loadBulk();

    // Chốt kỳ
    document.getElementById("l-from").value = today.substring(0, 8) + "01";
    document.getElementById("l-to").value = today;
    document.getElementById("lock-form").addEventListener("submit", e => { e.preventDefault(); lockPeriod(false); });
    document.getElementById("l-carry").addEventListener("click", () => lockPeriod(true));
    loadPeriods();
});

function switchTab(tab) {
    document.querySelectorAll(".tab-btn").forEach(b => {
        const active = b.dataset.tab === tab;
        b.classList.toggle("border-[#cf6800]", active);
        b.classList.toggle("text-[#cf6800]", active);
        b.classList.toggle("border-transparent", !active);
        b.classList.toggle("text-[#71717a]", !active);
    });
    ["direct", "bulk", "lock"].forEach(t => document.getElementById(`tab-${t}`).classList.toggle("hidden", t !== tab));
    setQueryParams({ mode: tab });
}

// ---------- Điều chỉnh trực tiếp ----------

async function loadDirect() {
    try {
        adjustDetail = await API.request(`/api/attendance/assignments/${adjustPc}`);
        const r = adjustDetail.ca;
        document.getElementById("direct-empty").classList.add("hidden");
        document.getElementById("direct-body").classList.remove("hidden");
        document.getElementById("d-employee").textContent = `${r.ho_ten || ""} · ${r.ma_nhan_vien || ""} · ${r.ten_vi_tri || ""}`;
        document.getElementById("d-shift").textContent = `${formatDate(r.ngay_lam)} · ${r.ten_ca} ${formatTime(r.gio_bat_dau)}-${formatTime(r.gio_ket_thuc)}`;
        document.getElementById("d-cancel").href = `/attendance-detail?pc=${adjustPc}`;
        let endDefault = combineDateTime(r.ngay_lam, r.gio_ket_thuc);
        if (r.gio_ket_thuc < r.gio_bat_dau) endDefault = combineDateTime(addDays(r.ngay_lam, 1), r.gio_ket_thuc);
        document.getElementById("d-in").value = toLocalInput(r.gio_vao) || combineDateTime(r.ngay_lam, r.gio_bat_dau);
        document.getElementById("d-out").value = toLocalInput(r.gio_ra) || endDefault;
        document.getElementById("d-target").innerHTML = `<option value="">Giữ ${escapeHtml(r.ten_ca)} (đúng ca)</option>` +
            adjustDetail.ca_cung_ngay.filter(c => !c.da_co_cham_cong)
                .map(c => `<option value="${c.ma_phan_cong}">Chuyển sang ${escapeHtml(c.ten_ca)}</option>`).join("");
        document.getElementById("d-locked").classList.toggle("hidden", !r.ky_da_chot);
        const open = document.getElementById("d-open-request");
        open.classList.toggle("hidden", !r.ma_yeu_cau_dang_mo);
        open.innerHTML = r.ma_yeu_cau_dang_mo
            ? `<strong>Ca này đang có yêu cầu chờ duyệt.</strong> Nên <a class="underline font-bold" href="/attendance-requests?id=${r.ma_yeu_cau_dang_mo}">xử lý yêu cầu ở màn 09</a> trước để không có hai quyết định mâu thuẫn.`
            : "";
        document.getElementById("cancel-form").classList.toggle("hidden", r.da_huy);
        renderPreview();
    } catch (err) {
        showToast(err.message, "error");
    }
}

function renderPreview() {
    if (!adjustDetail) return;
    const r = adjustDetail.ca;
    const vin = document.getElementById("d-in").value;
    const clear = document.getElementById("d-clear-out").checked;
    document.getElementById("d-out").disabled = clear;
    const vout = clear ? "" : document.getElementById("d-out").value;
    let hours = "Chưa xác định";
    if (vin && vout) {
        const mins = Math.round((new Date(vout) - new Date(vin)) / 60000);
        hours = mins > 0 ? `${Math.floor(mins / 60)}h${String(mins % 60).padStart(2, "0")} (thực tế, trước khi trừ phần ngoài ca)` : "Giờ ra phải sau giờ vào";
    }
    const rows = [
        ["Vào", hhmm(r.gio_vao), vin ? vin.substring(11, 16) : "--:--"],
        ["Ra", r.gio_ra ? hhmm(r.gio_ra) : "Chưa có", vout ? vout.substring(11, 16) : "Chưa có"],
        ["Tổng giờ", r.so_gio_lam ? hoursText(r.so_gio_lam) : "Chưa xác định", hours],
        ["Trễ / sớm", `${r.phut_di_tre} / ${r.phut_ve_som} phút`, "Tính lại khi lưu"],
        ["Trạng thái", escapeHtml(r.ten_trang_thai), "Đã điều chỉnh"]
    ];
    document.getElementById("d-preview").innerHTML = rows.map(([a, b, c]) =>
        `<tr><td class="py-2 px-2 font-semibold">${a}</td><td class="py-2 px-2">${b}</td><td class="py-2 px-2 text-[#cf6800] font-semibold">${c}</td></tr>`).join("");
}

async function saveDirect(e) {
    e.preventDefault();
    const reason = document.getElementById("d-reason").value.trim();
    if (reason.length < 10) return showToast("Lý do điều chỉnh bắt buộc, tối thiểu 10 ký tự", "error");
    const clear = document.getElementById("d-clear-out").checked;
    const vin = document.getElementById("d-in").value;
    const vout = document.getElementById("d-out").value;
    const body = {
        gio_vao: vin ? vin + ":00" : null,
        gio_ra: !clear && vout ? vout + ":00" : null,
        xoa_gio_ra: clear,
        ma_phan_cong_dung: Number(document.getElementById("d-target").value) || null,
        ly_do: reason
    };
    try {
        const row = await API.request(`/api/attendance/assignments/${adjustPc}`, { method: "PUT", body });
        showToast(adjustDetail.ca.ky_da_chot ? "Đã ghi điều chỉnh sang kỳ sau" : "Đã lưu điều chỉnh và báo cho nhân viên");
        window.location.href = `/attendance-detail?pc=${row.ma_phan_cong}`;
    } catch (err) {
        showToast(err.message, "error");
    }
}

async function cancelShift(e) {
    e.preventDefault();
    const reason = document.getElementById("c-reason").value.trim();
    if (reason.length < 5) return showToast("Bắt buộc nêu lý do hủy ca", "error");
    const pay = document.querySelector("input[name=c-pay]:checked").value === "1";
    if (!confirm("Hủy ca này? Lịch sử chấm công vẫn được giữ lại.")) return;
    try {
        await API.request(`/api/attendance/assignments/${adjustPc}/cancel`, { method: "POST", body: { ly_do: reason, tinh_cong: pay } });
        showToast("Đã hủy ca và ghi nhật ký");
        window.location.href = `/attendance-detail?pc=${adjustPc}`;
    } catch (err) {
        showToast(err.message, "error");
    }
}

// ---------- Hàng loạt ----------

async function loadBulk() {
    const day = document.getElementById("b-day").value;
    setQueryParams({ ngay: day });
    document.getElementById("b-apply-btn").disabled = true;
    document.getElementById("b-result").innerHTML = "";
    try {
        const data = await API.request(`/api/attendance?ngay=${day}&so_dong=200`);
        bulkRows = data.items.filter(r => r.trang_thai !== "da_huy");
        const body = document.getElementById("b-rows");
        if (!bulkRows.length) {
            body.innerHTML = `<tr><td colspan="5" class="py-6 text-center text-[#71717a]">Không có ca nào trong ngày</td></tr>`;
            return;
        }
        body.innerHTML = bulkRows.map(r => {
            let end = combineDateTime(r.ngay_lam, r.gio_ket_thuc);
            if (r.gio_ket_thuc < r.gio_bat_dau) end = combineDateTime(addDays(r.ngay_lam, 1), r.gio_ket_thuc);
            return `
            <tr>
                <td class="py-2 px-2"><label class="flex items-center gap-2"><input type="checkbox" class="b-check" value="${r.ma_phan_cong}">
                    <span><span class="font-bold">${escapeHtml(r.ho_ten || "")}</span> <span class="text-[11px] text-[#71717a]">${escapeHtml(r.ma_nhan_vien || "")}</span></span></label></td>
                <td class="py-2 px-2 text-xs">${shiftText(r)}</td>
                <td class="py-2 px-2 text-xs">${hhmm(r.gio_vao)} / ${hhmm(r.gio_ra)}<div>${attendanceLabels(r.nhan)}</div></td>
                <td class="py-2 px-2"><input type="datetime-local" class="form-input !py-1.5 text-xs" id="b-in-${r.ma_phan_cong}" value="${toLocalInput(r.gio_vao) || combineDateTime(r.ngay_lam, r.gio_bat_dau)}"></td>
                <td class="py-2 px-2"><input type="datetime-local" class="form-input !py-1.5 text-xs" id="b-out-${r.ma_phan_cong}" value="${toLocalInput(r.gio_ra)}" placeholder="Chưa xác nhận"></td>
            </tr>`;
        }).join("");
        document.querySelectorAll(".b-check").forEach(c => c.addEventListener("change", () => { document.getElementById("b-apply-btn").disabled = true; }));
    } catch (err) {
        showToast(err.message, "error");
    }
}

async function submitBulk(preview) {
    const ids = Array.from(document.querySelectorAll(".b-check:checked")).map(c => Number(c.value));
    if (!ids.length) return showToast("Chọn ít nhất một ca bị ảnh hưởng", "error");
    const reason = document.getElementById("b-reason").value.trim();
    if (reason.length < 10) return showToast("Lý do áp dụng chung bắt buộc, tối thiểu 10 ký tự", "error");
    const items = ids.map(id => {
        const vin = document.getElementById(`b-in-${id}`).value;
        const vout = document.getElementById(`b-out-${id}`).value;
        return { ma_phan_cong: id, gio_vao: vin ? vin + ":00" : null, gio_ra: vout ? vout + ":00" : null };
    });
    if (!preview && !confirm(`Áp dụng điều chỉnh cho ${ids.length} bản ghi?`)) return;
    try {
        const res = await API.request("/api/attendance/bulk-adjust", {
            method: "POST", body: { items, ly_do: reason, mien_phat: document.getElementById("b-waive").checked, xem_truoc: preview }
        });
        const errors = res.loi.map(e => `<li class="text-red-700">Ca #${e.ma_phan_cong}: ${escapeHtml(e.loi)}</li>`).join("");
        const lines = res.items.map(i => `<li>${escapeHtml(i.ho_ten || "")} · ${escapeHtml(i.ca || "")} ${formatDate(i.ngay_lam)}:
            ${hhmm((i.truoc.vao || "").replace(" ", "T"))}/${hhmm((i.truoc.ra || "").replace(" ", "T"))} → <strong>${i.sau.vao.substring(11)}/${i.sau.ra ? i.sau.ra.substring(11) : "--:--"}</strong>
            (${hoursText(i.sau.gio)}) ${attendanceLabels(i.nhan_sau)}${i.ky_da_chot ? ` <span class="text-amber-700 text-[11px]">Kỳ đã chốt, ghi sang kỳ sau</span>` : ""}</li>`).join("");
        document.getElementById("b-result").innerHTML = `
            <div class="rounded-xl bg-[#faf6f0] p-4">
                <div class="font-bold mb-2">${res.xem_truoc ? `Xem trước ${res.items.length} bản ghi` : `Đã áp dụng ${res.da_ap_dung} bản ghi`}</div>
                <ul class="space-y-1 text-xs">${errors}${lines}</ul>
            </div>`;
        document.getElementById("b-apply-btn").disabled = !(res.xem_truoc && !res.loi.length && res.items.length);
        if (!res.xem_truoc) {
            showToast(`Đã điều chỉnh ${res.da_ap_dung} bản ghi`);
            loadBulk();
        }
    } catch (err) {
        showToast(err.message, "error");
    }
}

// ---------- Chốt kỳ ----------

async function loadPeriods() {
    try {
        const items = await API.request("/api/attendance/periods");
        const isOwner = (API.getUser() || {}).ten_vai_tro === "Admin";
        document.getElementById("l-list").innerHTML = items.length ? items.map(k => `
            <li class="rounded-xl border border-[#f0e9df] p-3 flex flex-wrap items-center justify-between gap-2">
                <div><span class="font-bold">${formatDate(k.tu_ngay)} - ${formatDate(k.den_ngay)}</span>
                    <div class="text-xs text-[#71717a]">Chốt ${formatDateTime(k.ngay_chot)}${k.nguoi_chot ? ` bởi ${escapeHtml(k.nguoi_chot)}` : ""}${k.ghi_chu ? ` · ${escapeHtml(k.ghi_chu)}` : ""}</div></div>
                ${isOwner ? `<button type="button" onclick="unlockPeriod(${k.id})" class="text-xs font-bold text-red-600 hover:underline">Mở khóa</button>` : ""}
            </li>`).join("") : `<li class="text-[#71717a]">Chưa có kỳ nào được chốt.</li>`;
    } catch (err) {
        showToast(err.message, "error");
    }
}

async function lockPeriod(carry) {
    const body = {
        tu_ngay: document.getElementById("l-from").value,
        den_ngay: document.getElementById("l-to").value,
        ghi_chu: document.getElementById("l-note").value.trim() || null,
        chuyen_yeu_cau_sang_ky_sau: carry
    };
    if (!body.tu_ngay || !body.den_ngay) return showToast("Chọn khoảng ngày cần chốt", "error");
    if (!carry && !confirm(`Chốt kỳ ${formatDate(body.tu_ngay)} - ${formatDate(body.den_ngay)}?`)) return;
    try {
        const res = await API.request("/api/attendance/periods/lock", { method: "POST", body });
        document.getElementById("l-pending").classList.add("hidden");
        showToast(res.so_yeu_cau_chuyen_ky_sau
            ? `Đã chốt kỳ, ${res.so_yeu_cau_chuyen_ky_sau} yêu cầu sẽ ghi nhận sang kỳ sau khi được duyệt`
            : "Đã chốt kỳ công");
        loadPeriods();
    } catch (err) {
        if (err.message.includes("yêu cầu")) {
            document.getElementById("l-pending").classList.remove("hidden");
            document.getElementById("l-pending-text").textContent = err.message;
        } else {
            showToast(err.message, "error");
        }
    }
}

async function unlockPeriod(id) {
    if (!confirm("Mở khóa kỳ này? Các điều chỉnh sau đó sẽ sửa trực tiếp vào kỳ.")) return;
    try {
        await API.request(`/api/attendance/periods/${id}`, { method: "DELETE" });
        showToast("Đã mở khóa kỳ công");
        loadPeriods();
    } catch (err) {
        showToast(err.message, "error");
    }
}
