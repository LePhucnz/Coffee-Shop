// Sprint 5 - Quản lý chấm công: màn 07 Theo ngày, màn 08 Theo kỳ (FR-11B)
let mode = "ngay";
let page = 1;
let flag = "";

document.addEventListener("DOMContentLoaded", () => {
    if (!API.isAdmin()) return;
    const today = toISODate(new Date());
    mode = queryParam("che_do") === "ky" ? "ky" : "ngay";
    flag = queryParam("co") || "";
    document.getElementById("f-day").value = queryParam("ngay") || today;
    document.getElementById("f-from").value = queryParam("tu_ngay") || today.substring(0, 8) + "01";
    document.getElementById("f-to").value = queryParam("den_ngay") || today;
    document.getElementById("f-keyword").value = queryParam("tu_khoa") || "";
    document.getElementById("f-status").value = queryParam("trang_thai") || "";

    Promise.all([loadPositionsInto("f-position"), loadShiftTypesInto("f-shift")]).then(() => {
        document.getElementById("f-position").value = queryParam("ma_vi_tri") || "";
        document.getElementById("f-shift").value = queryParam("ma_ca") || "";
    });

    document.querySelectorAll(".mode-btn").forEach(b => b.addEventListener("click", () => setMode(b.dataset.mode)));
    document.querySelectorAll(".flag-chip").forEach(b => b.addEventListener("click", () => {
        flag = flag === b.dataset.flag ? "" : b.dataset.flag;
        page = 1;
        reload();
    }));
    ["f-position", "f-shift", "f-day", "f-from", "f-to", "f-status"].forEach(id =>
        document.getElementById(id).addEventListener("change", () => { page = 1; reload(); }));
    let typing;
    document.getElementById("f-keyword").addEventListener("input", () => {
        clearTimeout(typing);
        typing = setTimeout(() => { page = 1; reload(); }, 350);
    });
    document.getElementById("btn-refresh").addEventListener("click", reload);
    document.getElementById("btn-export").addEventListener("click", exportExcel);

    setMode(mode);
    loadPending();
    // Tự cập nhật tối đa 60 giây/lần
    setInterval(() => { if (mode === "ngay") reload(); loadPending(); }, 60000);
});

function setMode(m) {
    mode = m;
    document.querySelectorAll(".mode-btn").forEach(b => {
        const active = b.dataset.mode === m;
        b.classList.toggle("border-[#cf6800]", active);
        b.classList.toggle("text-[#cf6800]", active);
        b.classList.toggle("border-transparent", !active);
        b.classList.toggle("text-[#71717a]", !active);
    });
    const day = m === "ngay";
    document.getElementById("cards-day").classList.toggle("hidden", !day);
    document.getElementById("cards-period").classList.toggle("hidden", day);
    document.getElementById("view-day").classList.toggle("hidden", !day);
    document.getElementById("view-period").classList.toggle("hidden", day);
    document.getElementById("f-day-wrap").classList.toggle("hidden", !day);
    document.getElementById("f-shift-wrap").classList.toggle("hidden", !day);
    document.getElementById("f-from-wrap").classList.toggle("hidden", day);
    document.getElementById("f-to-wrap").classList.toggle("hidden", day);
    document.getElementById("page-sub").textContent = day
        ? "Toàn bộ ca được phân trong ngày, bất thường hiển thị trước"
        : "Bảng công theo kỳ, khớp tổng giờ dùng để tính lương";
    page = 1;
    reload();
}

function filters() {
    const base = {
        tu_khoa: document.getElementById("f-keyword").value.trim(),
        ma_vi_tri: document.getElementById("f-position").value,
        trang_thai: document.getElementById("f-status").value,
        co: flag
    };
    if (mode === "ngay") {
        return { ...base, ngay: document.getElementById("f-day").value, ma_ca: document.getElementById("f-shift").value };
    }
    return { ...base, tu_ngay: document.getElementById("f-from").value, den_ngay: document.getElementById("f-to").value };
}

function reload() {
    document.querySelectorAll(".flag-chip").forEach(b => {
        const active = b.dataset.flag === flag;
        b.classList.toggle("bg-[#cf6800]", active);
        b.classList.toggle("text-white", active);
        b.classList.toggle("border-[#cf6800]", active);
        b.classList.toggle("bg-white", !active);
    });
    setQueryParams({ che_do: mode === "ky" ? "ky" : null, ...filters() });
    return mode === "ngay" ? loadDay() : loadPeriod();
}

async function loadPending() {
    try {
        const data = await API.request("/api/attendance/requests/pending-count");
        document.getElementById("pending-count").textContent = data.so_cho_duyet;
    } catch (e) { /* không chặn trang */ }
}

// ---------- Màn 07: theo ngày ----------

async function loadDay() {
    try {
        const data = await API.request(`/api/attendance?${buildQuery({ ...filters(), trang: page })}`);
        const t = data.thong_ke;
        document.getElementById("c-total").textContent = t.tong_ca;
        document.getElementById("c-full").textContent = t.so_du_vao_ra;
        document.getElementById("c-late").textContent = t.di_tre;
        document.getElementById("c-absent").textContent = t.vang_mat;
        document.getElementById("c-missing").textContent = t.chua_check_out;
        document.getElementById("updated-at").textContent =
            `Cập nhật ${formatDateTime(data.cap_nhat_luc)} · Tự cập nhật tối đa 60 giây`;
        document.getElementById("btn-bulk").href = `/attendance-adjust?mode=bulk&ngay=${data.tu_ngay}`;
        renderDay(data);
    } catch (err) {
        showToast(err.message, "error");
    }
}

function renderDay(data) {
    const body = document.getElementById("day-rows");
    if (!data.items.length) {
        body.innerHTML = `<tr><td colspan="8" class="py-6 text-center text-[#71717a]">Không có ca nào khớp bộ lọc</td></tr>`;
    } else {
        body.innerHTML = data.items.map(r => {
            const abnormal = ["vang_mat", "chua_check_out"].includes(r.trang_thai) || r.phut_di_tre || (r.co || []).length;
            const flagText = (r.co || []).length ? flagBadges(r.co) : `<span class="text-xs text-[#52525b]">${LOCATION_NAMES[r.vi_tri] || "-"}</span>`;
            return `
            <tr class="${abnormal ? "bg-[#fffaf3]" : ""}">
                <td class="py-2 px-2"><div class="text-[11px] text-[#71717a]">${escapeHtml(r.ma_nhan_vien || "")}</div><div class="font-bold">${escapeHtml(r.ho_ten || "")}</div></td>
                <td class="py-2 px-2 text-xs">${escapeHtml(r.ten_vi_tri || "-")}</td>
                <td class="py-2 px-2 text-xs">${escapeHtml(r.ten_ca || "")}<br>${formatTime(r.gio_bat_dau)}-${formatTime(r.gio_ket_thuc)}</td>
                <td class="py-2 px-2 whitespace-nowrap">${hhmm(r.gio_vao)} / ${hhmm(r.gio_ra)}</td>
                <td class="py-2 px-2">${r.phut_di_tre || (r.gio_vao ? 0 : "-")}</td>
                <td class="py-2 px-2"><div class="flex flex-col items-start gap-1">${attendanceLabels(r.nhan) || statusBadge(ATTENDANCE_STATUS, r.trang_thai)}</div></td>
                <td class="py-2 px-2"><div class="flex flex-col items-start gap-1">${flagText}</div></td>
                <td class="py-2 px-2 whitespace-nowrap"><a href="/attendance-detail?pc=${r.ma_phan_cong}" class="text-xs font-bold text-[#cf6800] hover:underline">Xem chi tiết</a></td>
            </tr>`;
        }).join("");
    }
    const from = data.tong_so ? (data.trang - 1) * 20 + 1 : 0;
    const to = Math.min(data.trang * 20, data.tong_so);
    document.getElementById("page-info").textContent = `${from}-${to} / ${data.tong_so} bản ghi · 20 bản ghi / trang · Trang ${data.trang}/${data.so_trang}`;
    const pager = document.getElementById("pager");
    const btn = (label, p, active, disabled) =>
        `<button type="button" ${disabled ? "disabled" : ""} onclick="gotoPage(${p})" class="px-3 py-1.5 rounded-lg text-xs font-bold border ${active ? "bg-[#cf6800] border-[#cf6800] text-white" : "bg-white border-[#e6dfd5]"} disabled:opacity-40">${label}</button>`;
    let html = btn("Trước", data.trang - 1, false, data.trang <= 1);
    for (let p = Math.max(1, data.trang - 2); p <= Math.min(data.so_trang, data.trang + 2); p++) html += btn(p, p, p === data.trang, false);
    html += btn("Sau", data.trang + 1, false, data.trang >= data.so_trang);
    pager.innerHTML = html;
}

function gotoPage(p) {
    page = p;
    loadDay();
}

// ---------- Màn 08: theo kỳ ----------

async function loadPeriod() {
    const f = filters();
    try {
        const data = await API.request(`/api/attendance/period?${buildQuery(f)}`);
        document.getElementById("p-hours").textContent = hoursText(data.tong_gio_xac_nhan);
        document.getElementById("p-ot").textContent = `${data.phut_vuot_ca_cho_duyet} phút`;
        document.getElementById("p-missing").textContent = data.so_ca_thieu_ra;
        document.getElementById("updated-at").textContent = `Kỳ ${formatDate(data.tu_ngay)} - ${formatDate(data.den_ngay)}`;
        renderPeriod(data);
    } catch (err) {
        showToast(err.message, "error");
    }
}

function renderPeriod(data) {
    document.getElementById("period-head").innerHTML = `
        <tr class="bg-[#eee7db]/80 font-bold text-[#52525b] text-left">
            <th class="py-2 px-2 sticky left-0 bg-[#eee7db] min-w-[160px]">Nhân viên</th>
            ${data.ngay.map(d => `<th class="py-2 px-2 text-center whitespace-nowrap">${dayLabel(d)}</th>`).join("")}
            <th class="py-2 px-2 whitespace-nowrap">Số ca</th>
            <th class="py-2 px-2 whitespace-nowrap">Tổng giờ</th>
            <th class="py-2 px-2 whitespace-nowrap">Trễ / Sớm</th>
            <th class="py-2 px-2 whitespace-nowrap">Vắng</th>
        </tr>`;
    const body = document.getElementById("period-rows");
    if (!data.nhan_vien.length) {
        body.innerHTML = `<tr><td colspan="${data.ngay.length + 5}" class="py-6 text-center text-[#71717a]">Không có dữ liệu trong kỳ</td></tr>`;
        return;
    }
    body.innerHTML = data.nhan_vien.map(nv => `
        <tr class="${nv.trang_thai_nv === "da_nghi" ? "opacity-60" : ""}">
            <td class="py-2 px-2 sticky left-0 bg-white">
                <div class="font-bold">${escapeHtml(nv.ho_ten || "")}</div>
                <div class="text-[11px] text-[#71717a]">${escapeHtml(nv.ma_nhan_vien || "")} · ${escapeHtml(nv.ten_vi_tri || "")}${nv.trang_thai_nv === "da_nghi" ? " · Đã nghỉ" : ""}</div>
            </td>
            ${data.ngay.map(d => {
                const cells = nv.o[d] || [];
                if (!cells.length) return `<td class="py-2 px-1 text-center text-stone-300">·</td>`;
                return `<td class="py-1 px-1 text-center">${cells.map(c =>
                    `<a href="/attendance-detail?pc=${c.ma_phan_cong}" title="${escapeHtml(c.nhan)}" class="block rounded px-1.5 py-1 mb-0.5 font-bold whitespace-nowrap ${CELL_COLORS[c.ma] || ""}">${escapeHtml(c.nhan)}</a>`
                ).join("")}</td>`;
            }).join("")}
            <td class="py-2 px-2 text-center">${nv.so_ca}</td>
            <td class="py-2 px-2 font-bold whitespace-nowrap">${hoursText(nv.tong_gio)}</td>
            <td class="py-2 px-2 whitespace-nowrap">${nv.phut_tre} / ${nv.phut_som} phút</td>
            <td class="py-2 px-2 text-center">${nv.so_vang}</td>
        </tr>`).join("");
}

async function exportExcel() {
    const q = buildQuery({ che_do: mode, ...filters() });
    try {
        await downloadWithAuth(`/api/attendance/export?${q}`, `cham-cong-${mode}.xlsx`);
    } catch (err) {
        showToast(err.message, "error");
    }
}
