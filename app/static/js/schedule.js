// Trang Xếp ca (FR-08, FR-09): lưới ca theo tuần, xếp tự động, chỉnh tay, công bố
let schWeek = null;
let schedule = null;
let schedulable = [];
let shiftTypes = [];
let assignSlot = null;

document.addEventListener("DOMContentLoaded", async () => {
    if (!API.getUser() || !API.isAdmin()) return;
    schWeek = getWeekFromUrl(1);
    document.getElementById("week-prev").addEventListener("click", () => changeWeek(-7));
    document.getElementById("week-next").addEventListener("click", () => changeWeek(7));
    document.getElementById("btn-auto").addEventListener("click", runAutoSchedule);
    document.getElementById("btn-publish").addEventListener("click", publishWeek);
    document.getElementById("btn-unpublish").addEventListener("click", unpublishWeek);
    document.getElementById("btn-add-type").addEventListener("click", addTypeRow);
    document.getElementById("assign-form").addEventListener("submit", submitAssign);
    try {
        schedulable = await API.request("/api/employees/schedulable");
    } catch (err) {
        showToast("Không tải được danh sách nhân viên: " + err.message, "error");
    }
    await Promise.all([loadSchedule(), loadShiftTypes()]);
});

function changeWeek(days) {
    schWeek = addDays(schWeek, days);
    setWeekInUrl(schWeek);
    loadSchedule();
}

async function loadSchedule() {
    document.getElementById("week-label").textContent = weekRangeLabel(schWeek);
    try {
        render(await API.request(`/api/shifts/schedule?week=${schWeek}`));
    } catch (err) {
        document.getElementById("grid-body").innerHTML =
            `<tr><td class="py-10 text-center text-red-600">${escapeHtml(err.message)}</td></tr>`;
    }
}

const WEEK_STATUS = {
    chua_tao: { text: "Chưa xếp ca", cls: "bg-stone-100 text-stone-600" },
    nhap: { text: "Bản nháp (nhân viên chưa thấy)", cls: "bg-amber-100 text-amber-700" },
    da_cong_bo: { text: "Đã công bố", cls: "bg-emerald-100 text-emerald-700" }
};

function isLocked() {
    return schedule && schedule.trang_thai === "da_cong_bo";
}

function render(data) {
    schedule = data;
    const st = WEEK_STATUS[data.trang_thai] || WEEK_STATUS.nhap;
    const statusEl = document.getElementById("week-status");
    statusEl.className = `inline-flex px-3 py-1.5 rounded-full font-bold ${st.cls}`;
    statusEl.textContent = data.trang_thai === "da_cong_bo" && data.ngay_cong_bo
        ? `${st.text} lúc ${formatDateTime(data.ngay_cong_bo)}` : st.text;
    document.getElementById("deadline-label").textContent = `Hạn chót đăng ký nguyện vọng: ${formatDateTime(data.han_chot_dang_ky)}`;

    document.getElementById("stat-total").textContent = data.phan_cong.length;
    document.getElementById("stat-errors").textContent = data.so_loi;
    document.getElementById("stat-warnings").textContent = data.so_canh_bao;

    const locked = isLocked();
    // Dùng style.display vì class nút trong style.css đè lên class "hidden" của Tailwind
    document.getElementById("btn-auto").style.display = locked ? "none" : "";
    document.getElementById("btn-publish").style.display = locked ? "none" : "";
    document.getElementById("btn-unpublish").style.display = locked ? "" : "none";
    const publishBtn = document.getElementById("btn-publish");
    publishBtn.disabled = !data.co_the_cong_bo;
    publishBtn.classList.toggle("opacity-50", !data.co_the_cong_bo);
    publishBtn.title = data.so_loi ? "Còn lỗi xung đột, hãy sửa các ô màu đỏ trước" : "";

    renderGrid();
    renderConflicts();
    renderHours();
}

function renderGrid() {
    const days = schedule.ngay;
    const today = toISODate(new Date());
    document.getElementById("grid-head").innerHTML = `<th class="py-3 px-4 w-44">Ca làm</th>` + days.map(d => `
        <th class="py-3 px-2 text-center ${d === today ? "text-[#cf6800]" : ""}">${dayLabel(d)}</th>`).join("");

    if (!schedule.loai_ca.length) {
        document.getElementById("grid-body").innerHTML =
            `<tr><td colspan="8" class="py-10 text-center text-[#71717a]">Chưa có loại ca nào đang dùng. Thêm ở phần cấu hình bên dưới.</td></tr>`;
        return;
    }

    const slotMap = {};
    schedule.o_ca.forEach(o => { slotMap[`${o.ngay}|${o.ma_ca}`] = o; });
    const people = {};
    schedule.phan_cong.forEach(p => {
        const key = `${p.ngay_lam}|${p.ma_ca}`;
        (people[key] = people[key] || []).push(p);
    });

    document.getElementById("grid-body").innerHTML = schedule.loai_ca.map(lc => `
        <tr class="align-top">
            <td class="py-3 px-4">
                <div class="font-semibold text-[#18181b]">${escapeHtml(lc.ten_ca)}</div>
                <div class="text-xs text-[#71717a]">${formatTime(lc.gio_bat_dau)} - ${formatTime(lc.gio_ket_thuc)}</div>
                <div class="text-xs text-[#71717a]">Cần ${lc.so_nv_toi_thieu}-${lc.so_nv_toi_da} người</div>
            </td>
            ${days.map(d => renderCell(slotMap[`${d}|${lc.id}`], people[`${d}|${lc.id}`] || [])).join("")}
        </tr>`).join("");
}

function renderCell(slot, list) {
    if (!slot) return `<td></td>`;
    const warn = slot.canh_bao.length > 0;
    const bg = warn ? "bg-amber-50" : (slot.so_nguoi > 0 ? "bg-emerald-50/60" : "");
    const countCls = warn ? "bg-amber-200 text-amber-800" : "bg-emerald-100 text-emerald-700";
    const chips = list.map(p => {
        const errors = p.xung_dot.filter(c => c.muc_do === "loi");
        const warns = p.xung_dot.filter(c => c.muc_do === "canh_bao");
        const cls = errors.length
            ? "bg-red-100 border-red-400 text-red-800"
            : warns.length ? "bg-amber-100 border-amber-300 text-amber-900" : "bg-white border-[#e6dfd5] text-[#18181b]";
        const tip = p.xung_dot.map(c => c.thong_bao).join("\n");
        const icon = errors.length ? "⛔ " : warns.length ? "⚠ " : "";
        return `<div class="flex items-center justify-between gap-1 px-2 py-1 rounded-lg border text-xs font-semibold ${cls}" title="${escapeHtml(tip)}">
            <span class="truncate">${icon}${p.theo_nguyen_vong ? "★ " : ""}${escapeHtml(shortName(p.ho_ten))}</span>
            ${isLocked() ? "" : `<button type="button" class="text-[#9ca3af] hover:text-red-600 leading-none" title="Gỡ khỏi ca" onclick="removeAssignment(${p.id})">&times;</button>`}
        </div>`;
    }).join("");
    const wishCount = slot.nguyen_vong.length;
    return `<td class="py-2 px-1.5 ${bg}">
        <div class="flex items-center justify-between mb-1.5">
            <span class="px-1.5 py-0.5 rounded text-[11px] font-bold ${countCls}" title="${escapeHtml(slot.canh_bao.map(c => c.thong_bao).join("\n"))}">${slot.so_nguoi}/${slot.toi_thieu}-${slot.toi_da}</span>
            <span class="text-[10px] text-[#9ca3af]" title="${escapeHtml(slot.nguyen_vong.map(n => n.ho_ten).join(", "))}">${wishCount ? `${wishCount} NV` : ""}</span>
        </div>
        <div class="space-y-1">${chips}</div>
        ${isLocked() ? "" : `<button type="button" onclick="openAssignModal('${slot.ngay}', ${slot.ma_ca})" class="mt-1.5 w-full text-[11px] font-semibold text-[#cf6800] hover:underline">+ Thêm</button>`}
    </td>`;
}

function shortName(name) {
    const parts = String(name || "").trim().split(/\s+/);
    return parts.length > 2 ? `${parts[0]} ${parts[parts.length - 1]}` : name;
}

function renderConflicts() {
    const typeName = Object.fromEntries(schedule.loai_ca.map(lc => [lc.id, lc.ten_ca]));
    const rows = [];
    schedule.phan_cong.forEach(p => p.xung_dot.forEach(c => rows.push({
        level: c.muc_do,
        text: `<strong>${escapeHtml(p.ho_ten)}</strong> · ${dayLabel(p.ngay_lam)} · ${escapeHtml(typeName[p.ma_ca] || "")}: ${escapeHtml(c.thong_bao)}`
    })));
    // Ô ca thiếu/thừa người gộp thành một dòng, chi tiết xem ở ô màu vàng trong lưới
    const thieu = schedule.o_ca.filter(o => o.canh_bao.some(c => c.loai === "thieu_nguoi")).length;
    const thua = schedule.o_ca.filter(o => o.canh_bao.some(c => c.loai === "du_nguoi")).length;
    if (thieu) rows.push({ level: "canh_bao", text: `<strong>${thieu} ô ca thiếu người</strong> (ô màu vàng trong lưới)` });
    if (thua) rows.push({ level: "canh_bao", text: `<strong>${thua} ô ca vượt số người tối đa</strong>` });
    rows.sort((a, b) => (a.level === "loi" ? 0 : 1) - (b.level === "loi" ? 0 : 1));
    document.getElementById("conflict-list").innerHTML = rows.length
        ? rows.map(r => `<li class="flex gap-2 ${r.level === "loi" ? "text-red-700" : "text-amber-800"}">
                <span>${r.level === "loi" ? "⛔" : "⚠"}</span><span>${r.text}</span></li>`).join("")
        : `<li class="text-emerald-700">Không có xung đột nào 👍</li>`;
}

function renderHours() {
    document.getElementById("hours-body").innerHTML = schedule.tong_gio.length
        ? schedule.tong_gio.map(t => `<tr class="border-t border-[#f5efe6]">
                <td class="py-1.5">${escapeHtml(t.ho_ten)}</td>
                <td class="py-1.5 text-right">${t.so_ca}</td>
                <td class="py-1.5 text-right font-semibold ${t.so_gio > 48 ? "text-red-600" : ""}">${t.so_gio}</td></tr>`).join("")
        : `<tr><td colspan="3" class="py-3 text-[#71717a]">Chưa có ai được xếp ca</td></tr>`;
}

// ---------- Thao tác ----------

async function runAutoSchedule() {
    if (schedule && schedule.phan_cong.length &&
        !confirm("Xếp ca tự động sẽ xóa bản nháp hiện tại của tuần này và xếp lại từ nguyện vọng. Tiếp tục?")) return;
    try {
        render(await API.request("/api/shifts/schedule/auto", { method: "POST", body: { tuan_bat_dau: schWeek } }));
        const thieu = schedule.o_ca.filter(o => o.canh_bao.some(c => c.loai === "thieu_nguoi")).length;
        showToast(`Đã xếp ${schedule.phan_cong.length} lượt ca` + (thieu ? `, còn ${thieu} ô thiếu người` : ""), thieu ? "warning" : "success");
    } catch (err) {
        showToast(err.message, "error");
    }
}

async function publishWeek() {
    const warn = schedule.so_canh_bao ? `\nCòn ${schedule.so_canh_bao} cảnh báo (thiếu người / vượt giờ).` : "";
    if (!confirm(`Công bố lịch tuần ${weekRangeLabel(schWeek)}? Nhân viên sẽ nhận thông báo.${warn}`)) return;
    try {
        render(await API.request("/api/shifts/schedule/publish", { method: "POST", body: { tuan_bat_dau: schWeek } }));
        showToast("Đã công bố lịch và gửi thông báo cho nhân viên");
    } catch (err) {
        showToast(err.message, "error");
    }
}

async function unpublishWeek() {
    if (!confirm("Chuyển lịch về nháp? Nhân viên sẽ tạm không thấy lịch tuần này cho tới khi công bố lại.")) return;
    try {
        render(await API.request("/api/shifts/schedule/unpublish", { method: "POST", body: { tuan_bat_dau: schWeek } }));
        showToast("Lịch đã chuyển về nháp", "info");
    } catch (err) {
        showToast(err.message, "error");
    }
}

async function removeAssignment(id) {
    try {
        render(await API.request(`/api/shifts/assignments/${id}`, { method: "DELETE" }));
    } catch (err) {
        showToast(err.message, "error");
    }
}

function openAssignModal(ngay, maCa) {
    assignSlot = { ngay, maCa };
    const lc = schedule.loai_ca.find(t => t.id === maCa);
    const slot = schedule.o_ca.find(o => o.ngay === ngay && o.ma_ca === maCa);
    document.getElementById("assign-slot-label").innerHTML =
        `<strong>${dayLabel(ngay)}</strong> · ${escapeHtml(lc.ten_ca)} (${formatTime(lc.gio_bat_dau)} - ${formatTime(lc.gio_ket_thuc)})`;

    const inSlot = new Set(schedule.phan_cong.filter(p => p.ngay_lam === ngay && p.ma_ca === maCa).map(p => p.ma_nv));
    const wished = new Set(slot.nguyen_vong.map(n => n.ma_nv));
    const available = schedulable.filter(e => !inSlot.has(e.id));
    const option = e => `<option value="${e.id}">${escapeHtml(e.ma_nhan_vien || "")} - ${escapeHtml(e.ho_ten)}</option>`;
    const first = available.filter(e => wished.has(e.id));
    const rest = available.filter(e => !wished.has(e.id));
    document.getElementById("assign-employee").innerHTML = `<option value="">-- Chọn nhân viên --</option>`
        + (first.length ? `<optgroup label="★ Đã đăng ký ca này">${first.map(option).join("")}</optgroup>` : "")
        + (rest.length ? `<optgroup label="Nhân viên khác">${rest.map(option).join("")}</optgroup>` : "");
    document.getElementById("assign-modal").classList.remove("hidden");
}

function closeAssignModal() {
    document.getElementById("assign-modal").classList.add("hidden");
}

async function submitAssign(e) {
    e.preventDefault();
    const maNv = Number(document.getElementById("assign-employee").value);
    if (!maNv) return;
    try {
        render(await API.request("/api/shifts/assignments", {
            method: "POST",
            body: { ma_nv: maNv, ma_ca: assignSlot.maCa, ngay_lam: assignSlot.ngay }
        }));
        closeAssignModal();
        const added = schedule.phan_cong.find(p => p.ma_nv === maNv && p.ngay_lam === assignSlot.ngay && p.ma_ca === assignSlot.maCa);
        if (added && added.xung_dot.length) {
            showToast(added.xung_dot.map(c => c.thong_bao).join(". "), added.xung_dot.some(c => c.muc_do === "loi") ? "error" : "warning");
        }
    } catch (err) {
        showToast(err.message, "error");
    }
}

// ---------- Cấu hình loại ca ----------

async function loadShiftTypes() {
    try {
        shiftTypes = await API.request("/api/shifts/types?include_inactive=true");
        renderTypes();
    } catch (err) {
        showToast(err.message, "error");
    }
}

function typeRow(t) {
    const id = t.id || "new";
    return `<tr data-id="${id}" class="border-t border-[#f5efe6]">
        <td class="py-2 pr-2">${t.id ? `<span class="text-xs font-mono">${escapeHtml(t.ma_loai_ca)}</span>`
            : `<input class="form-input text-sm" data-f="ma_loai_ca" placeholder="CA_TOI" value="">`}</td>
        <td class="py-2 pr-2"><input class="form-input text-sm" data-f="ten_ca" value="${escapeHtml(t.ten_ca || "")}"></td>
        <td class="py-2 pr-2"><input type="time" class="form-input text-sm" data-f="gio_bat_dau" value="${formatTime(t.gio_bat_dau).replace("--:--", "")}"></td>
        <td class="py-2 pr-2"><input type="time" class="form-input text-sm" data-f="gio_ket_thuc" value="${formatTime(t.gio_ket_thuc).replace("--:--", "")}"></td>
        <td class="py-2 pr-2"><input type="number" min="0" class="form-input text-sm w-20" data-f="so_nv_toi_thieu" value="${t.so_nv_toi_thieu ?? 1}"></td>
        <td class="py-2 pr-2"><input type="number" min="1" class="form-input text-sm w-20" data-f="so_nv_toi_da" value="${t.so_nv_toi_da ?? 3}"></td>
        <td class="py-2 pr-2"><input type="checkbox" data-f="trang_thai" ${t.trang_thai !== false ? "checked" : ""}></td>
        <td class="py-2 text-right"><button type="button" class="btn-primary text-xs px-3 py-1.5" onclick="saveType('${id}')">Lưu</button></td>
    </tr>`;
}

function renderTypes() {
    document.getElementById("types-body").innerHTML = shiftTypes.map(typeRow).join("");
}

function addTypeRow() {
    if (document.querySelector('#types-body tr[data-id="new"]')) return;
    document.getElementById("types-body").insertAdjacentHTML("beforeend", typeRow({ trang_thai: true }));
}

async function saveType(id) {
    const row = document.querySelector(`#types-body tr[data-id="${id}"]`);
    const val = f => row.querySelector(`[data-f="${f}"]`);
    const body = {
        ten_ca: val("ten_ca").value.trim(),
        gio_bat_dau: val("gio_bat_dau").value,
        gio_ket_thuc: val("gio_ket_thuc").value,
        so_nv_toi_thieu: Number(val("so_nv_toi_thieu").value),
        so_nv_toi_da: Number(val("so_nv_toi_da").value),
        trang_thai: val("trang_thai").checked
    };
    try {
        if (id === "new") {
            body.ma_loai_ca = val("ma_loai_ca").value.trim();
            await API.request("/api/shifts/types", { method: "POST", body });
        } else {
            await API.request(`/api/shifts/types/${id}`, { method: "PUT", body });
        }
        showToast("Đã lưu cấu hình ca");
        await Promise.all([loadShiftTypes(), loadSchedule()]);
    } catch (err) {
        showToast(err.message, "error");
    }
}
