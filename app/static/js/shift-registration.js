// Trang Đăng ký ca (FR-07): nhân viên chọn ca rảnh theo tuần, khóa sau hạn chót
let regWeek = null;
let regData = null;
let selected = new Set(); // phần tử dạng "YYYY-MM-DD|ma_ca"

document.addEventListener("DOMContentLoaded", () => {
    const user = API.getUser();
    if (!user) return;
    if (API.isAdmin()) {
        // Theo phân quyền BRD, Admin/Manager không đăng ký lịch rảnh
        window.location.href = "/schedule";
        return;
    }
    // Không có ?week= trên URL thì để máy chủ chọn tuần gần nhất còn hạn đăng ký
    regWeek = new URLSearchParams(window.location.search).get("week") ? getWeekFromUrl(1) : null;
    document.getElementById("week-prev").addEventListener("click", () => changeWeek(-7));
    document.getElementById("week-next").addEventListener("click", () => changeWeek(7));
    document.getElementById("reg-clear").addEventListener("click", () => {
        if (!regData || !regData.con_mo) return;
        selected.clear();
        renderGrid();
    });
    document.getElementById("reg-save").addEventListener("click", saveRegistration);
    loadRegistration();
});

function changeWeek(days) {
    if (!regWeek) return;
    regWeek = addDays(regWeek, days);
    setWeekInUrl(regWeek);
    loadRegistration();
}

async function loadRegistration() {
    if (regWeek) document.getElementById("week-label").textContent = weekRangeLabel(regWeek);
    try {
        regData = await API.request(`/api/shifts/registrations/me${regWeek ? `?week=${regWeek}` : ""}`);
        regWeek = regData.tuan_bat_dau;
        document.getElementById("week-label").textContent = weekRangeLabel(regWeek);
        selected = new Set(regData.dang_ky.map(d => `${d.ngay}|${d.ma_ca}`));
        renderDeadline();
        renderGrid();
    } catch (err) {
        document.getElementById("reg-body").innerHTML =
            `<tr><td class="py-10 text-center text-red-600">${escapeHtml(err.message)}</td></tr>`;
    }
}

function renderDeadline() {
    const box = document.getElementById("deadline-box");
    const status = document.getElementById("reg-status");
    const deadline = formatDateTime(regData.han_chot);
    if (regData.con_mo) {
        box.className = "mt-4 rounded-2xl border p-4 text-sm font-medium bg-emerald-50 border-emerald-200 text-emerald-800";
        box.innerHTML = `Hạn chót đăng ký: <strong>${deadline}</strong>. Bạn có thể sửa nguyện vọng bất cứ lúc nào trước hạn chót.`;
        status.className = "inline-flex px-3 py-1.5 rounded-full text-xs font-bold bg-emerald-100 text-emerald-700";
        status.textContent = "Đang mở đăng ký";
    } else {
        box.className = "mt-4 rounded-2xl border p-4 text-sm font-medium bg-stone-100 border-stone-200 text-stone-700";
        box.innerHTML = `Đã khóa đăng ký từ <strong>${deadline}</strong>. Nguyện vọng tuần này chỉ được xem, không sửa được nữa.`;
        status.className = "inline-flex px-3 py-1.5 rounded-full text-xs font-bold bg-stone-200 text-stone-600";
        status.textContent = "Đã khóa";
    }
    document.getElementById("reg-save").disabled = !regData.con_mo;
    document.getElementById("reg-clear").disabled = !regData.con_mo;
    document.getElementById("reg-save").classList.toggle("opacity-50", !regData.con_mo);
}

function renderGrid() {
    const days = Array.from({ length: 7 }, (_, i) => addDays(regData.tuan_bat_dau, i));
    const today = toISODate(new Date());
    document.getElementById("reg-head").innerHTML = `<th class="py-3 px-4 w-48">Ca làm</th>` + days.map(d => `
        <th class="py-3 px-2 text-center ${d === today ? "text-[#cf6800]" : ""}">${dayLabel(d)}</th>`).join("");

    if (!regData.loai_ca.length) {
        document.getElementById("reg-body").innerHTML =
            `<tr><td colspan="8" class="py-10 text-center text-[#71717a]">Quản lý chưa cấu hình loại ca nào</td></tr>`;
        return;
    }

    document.getElementById("reg-body").innerHTML = regData.loai_ca.map(lc => `
        <tr>
            <td class="py-3 px-4">
                <button type="button" class="text-left" onclick="toggleRow(${lc.id})" ${regData.con_mo ? "" : "disabled"}>
                    <div class="font-semibold text-[#18181b]">${escapeHtml(lc.ten_ca)}</div>
                    <div class="text-xs text-[#71717a]">${formatTime(lc.gio_bat_dau)} - ${formatTime(lc.gio_ket_thuc)} · ${lc.so_gio} giờ</div>
                </button>
            </td>
            ${days.map(d => {
                const key = `${d}|${lc.id}`;
                const on = selected.has(key);
                const cls = on
                    ? "bg-[#cf6800] border-[#cf6800] text-white"
                    : "bg-white border-[#e6dfd5] text-[#9ca3af] hover:border-[#cf6800]";
                return `<td class="py-2 px-2 text-center">
                    <button type="button" data-key="${key}" onclick="toggleCell('${key}')"
                        class="w-full h-11 rounded-xl border-2 text-sm font-bold transition-colors ${cls} ${regData.con_mo ? "" : "cursor-not-allowed opacity-70"}"
                        ${regData.con_mo ? "" : "disabled"} aria-pressed="${on}">${on ? "✓ Rảnh" : "—"}</button>
                </td>`;
            }).join("")}
        </tr>`).join("");
    updateSummary();
}

function toggleCell(key) {
    if (!regData.con_mo) return;
    selected.has(key) ? selected.delete(key) : selected.add(key);
    renderGrid();
}

function toggleRow(maCa) {
    if (!regData.con_mo) return;
    const keys = Array.from({ length: 7 }, (_, i) => `${addDays(regData.tuan_bat_dau, i)}|${maCa}`);
    const allOn = keys.every(k => selected.has(k));
    keys.forEach(k => allOn ? selected.delete(k) : selected.add(k));
    renderGrid();
}

function updateSummary() {
    const hoursByType = Object.fromEntries(regData.loai_ca.map(lc => [lc.id, lc.so_gio]));
    let hours = 0;
    selected.forEach(k => { hours += hoursByType[k.split("|")[1]] || 0; });
    document.getElementById("reg-count").textContent = selected.size;
    document.getElementById("reg-hours").textContent = hours;
}

async function saveRegistration() {
    const btn = document.getElementById("reg-save");
    btn.disabled = true;
    try {
        const dang_ky = Array.from(selected).map(k => {
            const [ngay, maCa] = k.split("|");
            return { ngay, ma_ca: Number(maCa) };
        });
        regData = await API.request("/api/shifts/registrations/me", {
            method: "PUT",
            body: { tuan_bat_dau: regData.tuan_bat_dau, dang_ky }
        });
        selected = new Set(regData.dang_ky.map(d => `${d.ngay}|${d.ma_ca}`));
        renderDeadline();
        renderGrid();
        showToast(`Đã lưu ${regData.dang_ky.length} nguyện vọng cho tuần ${weekRangeLabel(regData.tuan_bat_dau)}`);
    } catch (err) {
        showToast(err.message, "error");
    } finally {
        btn.disabled = !(regData && regData.con_mo);
    }
}
