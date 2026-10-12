// Sprint 5 - Màn 10: chi tiết công & nhật ký điều chỉnh
const pcId = Number(queryParam("pc"));
let detail = null;

const SNAPSHOT_NAMES = {
    vao: "Vào", ra: "Ra", gio: "Giờ", trang_thai: "Trạng thái", ca: "Mã ca",
    vuot_ca_duyet: "Vượt ca duyệt (phút)", mien_phat: "Miễn phạt", tinh_cong: "Tính công", xac_nhan: "Gỡ cờ"
};

document.addEventListener("DOMContentLoaded", () => {
    if (!API.isAdmin()) return;
    if (!pcId) {
        document.getElementById("sub").textContent = "Chưa chọn ca. Hãy mở từ bảng Quản lý chấm công.";
        return;
    }
    document.getElementById("btn-adjust").href = `/attendance-adjust?pc=${pcId}`;
    document.getElementById("btn-ot").addEventListener("click", () => approveOvertime(false));
    document.getElementById("btn-ot-no").addEventListener("click", () => approveOvertime(true));
    document.getElementById("btn-waive").addEventListener("click", () => waive(true));
    document.getElementById("btn-unwaive").addEventListener("click", () => waive(false));
    document.getElementById("btn-flag-ok").addEventListener("click", () => verifyFlags(true));
    document.getElementById("btn-flag-keep").addEventListener("click", () => verifyFlags(false));
    load();
});

async function load() {
    try {
        detail = await API.request(`/api/attendance/assignments/${pcId}`);
        render();
    } catch (err) {
        document.getElementById("sub").textContent = err.message;
        showToast(err.message, "error");
    }
}

function render() {
    const r = detail.ca;
    document.getElementById("sub").textContent =
        `${r.ho_ten || ""} · ${r.ma_nhan_vien || ""} · ${r.ten_vi_tri || ""} · ${dayLabel(r.ngay_lam)}/${String(r.ngay_lam).substring(0, 4)}`;
    document.getElementById("labels").innerHTML = attendanceLabels(r.nhan) + " " + flagBadges(r.co);
    document.getElementById("locked-note").classList.toggle("hidden", !r.ky_da_chot);

    const changed = (a, b) => a && b && a !== b;
    const day = String(r.ngay_lam).substring(8, 10) + "/" + String(r.ngay_lam).substring(5, 7);
    const rows = [
        ["Giờ vào", `${day} · ${formatTime(r.gio_bat_dau)}`, hhmm(r.gio_vao) + (changed(r.gio_vao_goc, r.gio_vao) ? ` <span class="text-[11px] text-[#71717a]">(gốc ${hhmm(r.gio_vao_goc)})</span>` : "")],
        ["Giờ ra", `${day} · ${formatTime(r.gio_ket_thuc)}`, hhmm(r.gio_ra) + (changed(r.gio_ra_goc, r.gio_ra) ? ` <span class="text-[11px] text-[#71717a]">(gốc ${hhmm(r.gio_ra_goc)})</span>` : "")],
        ["Tổng giờ được tính", hoursText(r.so_gio_ca), r.so_gio_lam ? hoursText(r.so_gio_lam) : "Chưa xác định"],
        ["Đi trễ / Về sớm", "-", `${r.phut_di_tre} / ${r.phut_ve_som} phút`],
        ["Vượt ca", "-", r.phut_vuot_ca ? `${r.phut_vuot_ca} phút · đã duyệt ${r.phut_vuot_ca_duyet}` : "0"],
        ["Trạng thái", "-", escapeHtml(r.ten_trang_thai)]
    ];
    document.getElementById("plan-rows").innerHTML = rows.map(([a, b, c]) =>
        `<tr><td class="py-2 px-2 font-semibold">${a}</td><td class="py-2 px-2">${b}</td><td class="py-2 px-2 text-[#cf6800] font-semibold">${c}</td></tr>`).join("");

    document.getElementById("location").innerHTML = `
        <div>Vào: ${LOCATION_NAMES[r.vi_tri] || "-"}${r.khoang_cach_vao !== null ? ` · ${r.khoang_cach_vao} m` : ""}</div>
        <div>Ra: ${r.gio_ra ? (r.khoang_cach_ra !== null ? `${r.khoang_cach_ra} m` : "không định vị") : "chưa có"}</div>
        <div>Tọa độ vào: ${detail.vi_do_vao !== null ? `${detail.vi_do_vao}, ${detail.kinh_do_vao}` : "không có"}</div>
        <div>Tọa độ ra: ${detail.vi_do_ra !== null ? `${detail.vi_do_ra}, ${detail.kinh_do_ra}` : "không có"}</div>
        <div>IP: ${escapeHtml(r.ip_vao || "-")}${r.ip_ra ? ` / ${escapeHtml(r.ip_ra)}` : ""}</div>
        <div>Thiết bị: ${escapeHtml((r.thiet_bi_vao || "-").substring(0, 12))}${r.thiet_bi_ra && r.thiet_bi_ra !== r.thiet_bi_vao ? ` / ${escapeHtml(r.thiet_bi_ra.substring(0, 12))}` : ""}</div>`;

    const pendingOt = r.phut_vuot_ca - r.phut_vuot_ca_duyet;
    document.getElementById("ot-info").textContent = r.phut_vuot_ca
        ? `Ghi nhận vượt ca ${r.phut_vuot_ca} phút, đã duyệt ${r.phut_vuot_ca_duyet} phút${pendingOt > 0 ? `, còn ${pendingOt} phút chờ duyệt` : ""}.`
        : "Ca này không có giờ vượt ca.";
    document.getElementById("ot-minutes").value = r.phut_vuot_ca || 0;
    ["ot-minutes", "ot-reason", "btn-ot", "btn-ot-no"].forEach(id => { document.getElementById(id).disabled = !r.phut_vuot_ca; });

    const violated = r.phut_di_tre || r.phut_ve_som || r.trang_thai === "vang_mat";
    document.getElementById("waive-info").textContent = r.mien_phat
        ? `Đã miễn phạt: ${r.ly_do_mien_phat || ""}`
        : (violated ? `Vi phạm: trễ ${r.phut_di_tre} phút, sớm ${r.phut_ve_som} phút${r.trang_thai === "vang_mat" ? ", vắng" : ""}.` : "Ca này không có vi phạm.");
    document.getElementById("btn-waive").disabled = !violated || r.mien_phat;
    document.getElementById("btn-unwaive").classList.toggle("hidden", !r.mien_phat);

    const flags = (r.co || []).filter(f => f !== "vuot_han_muc");
    document.getElementById("flag-list").innerHTML = flags.length ? flagBadges(flags) : `<span class="text-xs text-[#71717a]">Không có cờ cần xác minh</span>`;
    document.getElementById("btn-flag-ok").disabled = !flags.length;
    document.getElementById("btn-flag-keep").disabled = !flags.length;
    document.getElementById("flag-result").textContent = r.ghi_chu_xac_minh ? `Ghi chú gần nhất: ${r.ghi_chu_xac_minh}` : "";

    document.getElementById("requests").innerHTML = detail.yeu_cau.length ? detail.yeu_cau.map(y => `
        <li class="rounded-xl border border-[#f0e9df] p-3 flex flex-wrap items-center justify-between gap-2">
            <div><span class="font-semibold">${escapeHtml(y.ten_loai)}</span> <span class="text-xs text-[#71717a]">gửi ${formatDateTime(y.ngay_tao)}</span>
                <div class="text-xs text-[#52525b]">${escapeHtml(y.ly_do)}</div></div>
            <div class="flex items-center gap-2">${statusBadge(REQUEST_STATUS, y.trang_thai)}
                <a href="/attendance-requests?trang_thai=tat_ca&id=${y.id}" class="text-xs font-bold text-[#cf6800] hover:underline">Mở</a></div>
        </li>`).join("") : `<li class="text-[#71717a]">Không có yêu cầu nào.</li>`;

    document.getElementById("logs").innerHTML = detail.nhat_ky.length ? detail.nhat_ky.map(l => `
        <tr>
            <td class="py-2 px-2 whitespace-nowrap">${formatDateTime(l.thoi_gian)}</td>
            <td class="py-2 px-2 font-semibold">${escapeHtml(l.ten_hanh_dong)}${l.tu_duyet ? ` <span class="text-[11px] text-amber-700">(Tự duyệt)</span>` : ""}</td>
            <td class="py-2 px-2 text-xs">${snapshotText(l.truoc)}<div class="text-[#cf6800]">→ ${snapshotText(l.sau)}</div></td>
            <td class="py-2 px-2 text-xs">${l.nguoi_yeu_cau ? `Yêu cầu: ${escapeHtml(l.nguoi_yeu_cau)}<br>` : ""}${escapeHtml(l.nguoi_thuc_hien || "Hệ thống")}</td>
            <td class="py-2 px-2 text-xs">${escapeHtml(l.ly_do || "-")}</td>
        </tr>`).join("") : `<tr><td colspan="5" class="py-6 text-center text-[#71717a]">Chưa có thay đổi</td></tr>`;

    document.getElementById("adjustments").innerHTML = detail.dieu_chinh_ky_sau.length
        ? `<h3 class="text-xs font-bold uppercase text-[#52525b] mb-2">Điều chỉnh ghi sang kỳ sau</h3>` + detail.dieu_chinh_ky_sau.map(a =>
            `<div class="text-xs rounded-lg bg-[#faf6f0] px-3 py-2 mb-1">Áp dụng từ ${formatDate(a.ap_dung_tu_ngay)} · chênh ${a.so_gio_chenh > 0 ? "+" : ""}${a.so_gio_chenh}h · ${escapeHtml(a.ly_do || "")}</div>`).join("")
        : "";
}

function snapshotText(s) {
    if (!s) return "-";
    return Object.entries(s).filter(([, v]) => v !== null && v !== undefined && v !== "")
        .map(([k, v]) => `${SNAPSHOT_NAMES[k] || k}: ${typeof v === "boolean" ? (v ? "Có" : "Không") : escapeHtml(typeof v === "string" && v.length >= 16 && v[4] === "-" ? v.substring(11, 16) : (ATTENDANCE_STATUS[v] ? ATTENDANCE_STATUS[v].text : v))}`)
        .join(" · ") || "-";
}

async function post(path, body, message) {
    try {
        await API.request(`/api/attendance/assignments/${pcId}/${path}`, { method: "POST", body });
        showToast(message);
        load();
    } catch (err) {
        showToast(err.message, "error");
    }
}

function approveOvertime(reject) {
    const reason = document.getElementById("ot-reason").value.trim();
    if (reason.length < 5) return showToast("Nhập lý do duyệt / không duyệt", "error");
    const minutes = reject ? 0 : Number(document.getElementById("ot-minutes").value || 0);
    post("overtime", { so_phut: minutes, ly_do: reason }, reject ? "Đã ghi nhận không duyệt vượt ca" : `Đã duyệt ${minutes} phút vượt ca`);
}

function waive(on) {
    const reason = document.getElementById("waive-reason").value.trim();
    if (reason.length < 5) return showToast("Không được để trống lý do miễn phạt", "error");
    post("waive", { mien_phat: on, ly_do: reason }, on ? "Đã miễn phạt" : "Đã bỏ miễn phạt");
}

function verifyFlags(accept) {
    const note = document.getElementById("flag-note").value.trim();
    if (note.length < 5) return showToast("Nhập ghi chú xác minh", "error");
    post("verify-flags", { xac_nhan: accept, ghi_chu: note }, accept ? "Đã xác nhận giải trình, gỡ cờ" : "Đã giữ cờ để theo dõi");
}
