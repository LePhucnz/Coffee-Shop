// Sprint 5 - Trang Chấm công của nhân viên (FR-10 check-in/check-out, FR-11 lịch sử đi trễ/về sớm)
let todayData = null;
let selectedShiftId = null;
let serverOffsetMs = 0;          // Lệch giữa giờ máy chủ và giờ trình duyệt
let position = null;             // { vi_do, kinh_do, accuracy }
let gpsError = null;

document.addEventListener("DOMContentLoaded", () => {
    const user = API.getUser();
    if (!user) return;
    if (!user.ma_nv) {
        document.getElementById("no-profile").classList.remove("hidden");
        document.getElementById("attendance-body").classList.add("hidden");
        return;
    }
    document.getElementById("btn-check").addEventListener("click", submitCheck);
    startTourIfFirstTime();
    document.getElementById("history-range").addEventListener("change", loadHistory);
    setInterval(tickClock, 1000);
    watchPosition();
    loadToday();
    loadHistory();
    // Tự cập nhật trạng thái nút khi tới giờ mở check-in / hết ca
    setInterval(loadToday, 60000);
});

// ---------- Đồng hồ theo giờ máy chủ ----------

function serverNow() {
    return new Date(Date.now() + serverOffsetMs);
}

function tickClock() {
    const now = serverNow();
    const pad = n => String(n).padStart(2, "0");
    document.getElementById("clock").textContent = `${pad(now.getHours())}:${pad(now.getMinutes())}`;
    const weekday = ["Chủ Nhật", "Thứ Hai", "Thứ Ba", "Thứ Tư", "Thứ Năm", "Thứ Sáu", "Thứ Bảy"][now.getDay()];
    document.getElementById("clock-date").textContent = `${weekday}, ngày ${now.getDate()} tháng ${pad(now.getMonth() + 1)}`;
}

// ---------- GPS trình duyệt ----------

function watchPosition() {
    if (!navigator.geolocation) {
        gpsError = "Trình duyệt không hỗ trợ GPS";
        renderGps();
        return;
    }
    navigator.geolocation.watchPosition(
        pos => {
            position = { vi_do: pos.coords.latitude, kinh_do: pos.coords.longitude, accuracy: pos.coords.accuracy };
            gpsError = null;
            renderGps();
        },
        err => {
            gpsError = err.code === 1 ? "Bạn chưa cho phép truy cập vị trí" : "Không lấy được vị trí GPS";
            renderGps();
        },
        { enableHighAccuracy: true, maximumAge: 30000, timeout: 20000 }
    );
}

function distanceMeters(lat1, lon1, lat2, lon2) {
    const r = 6371000, rad = x => x * Math.PI / 180;
    const dp = rad(lat2 - lat1), dl = rad(lon2 - lon1);
    const a = Math.sin(dp / 2) ** 2 + Math.cos(rad(lat1)) * Math.cos(rad(lat2)) * Math.sin(dl / 2) ** 2;
    return 2 * r * Math.asin(Math.sqrt(a));
}

function renderGps() {
    const badge = document.getElementById("gps-badge");
    const text = document.getElementById("gps-text");
    let cls = "bg-stone-100 text-stone-600";
    if (gpsError) {
        cls = "bg-amber-100 text-amber-700";
        text.textContent = `${gpsError} (vẫn chấm công được, sẽ bị gắn cờ)`;
    } else if (!position) {
        text.textContent = "Đang lấy vị trí GPS...";
    } else if (todayData && todayData.vi_do_quan !== null) {
        const d = Math.round(distanceMeters(position.vi_do, position.kinh_do, todayData.vi_do_quan, todayData.kinh_do_quan));
        if (d <= todayData.ban_kinh_cho_phep) {
            cls = "bg-emerald-100 text-emerald-700";
            text.textContent = `Trong phạm vi quán (GPS OK, cách ${d} m)`;
        } else {
            cls = "bg-red-100 text-red-700";
            text.textContent = `Ngoài phạm vi quán (cách ${d} m) - sẽ bị gắn cờ`;
        }
    } else {
        cls = "bg-emerald-100 text-emerald-700";
        text.textContent = "Đã lấy được vị trí GPS";
    }
    badge.className = `inline-flex items-center gap-2 mt-4 px-3 py-1.5 rounded-full text-xs font-bold ${cls}`;
}

// ---------- Ca hôm nay ----------

async function loadToday() {
    try {
        todayData = await API.request("/api/attendance/today");
        serverOffsetMs = new Date(todayData.gio_hien_tai).getTime() - Date.now();
        tickClock();
        document.getElementById("rule-open").textContent = todayData.mo_truoc_phut;
        document.getElementById("rule-grace").textContent = todayData.an_han_phut;
        document.getElementById("rule-radius").textContent = todayData.ban_kinh_cho_phep;
        if (!todayData.ca.some(c => c.ma_phan_cong === selectedShiftId)) {
            // Ưu tiên ca đang mở nút, sau đó tới ca chưa xong
            const open = todayData.ca.find(c => c.co_the_check_in || c.co_the_check_out)
                || todayData.ca.find(c => c.trang_thai !== "hoan_thanh") || todayData.ca[0];
            selectedShiftId = open ? open.ma_phan_cong : null;
        }
        renderToday();
        renderGps();
    } catch (err) {
        showToast(err.message, "error");
    }
}

function selectShift(id) {
    selectedShiftId = id;
    renderToday();
}

function renderToday() {
    const notice = document.getElementById("today-notice");
    notice.classList.toggle("hidden", !todayData.thong_bao);
    notice.textContent = todayData.thong_bao || "";
    const tabs = document.getElementById("shift-tabs");
    tabs.classList.toggle("hidden", todayData.ca.length < 2);
    tabs.innerHTML = todayData.ca.map(c => `
        <button type="button" onclick="selectShift(${c.ma_phan_cong})"
            class="px-3 py-1.5 rounded-full text-xs font-bold border ${c.ma_phan_cong === selectedShiftId ? "bg-[#cf6800] border-[#cf6800] text-white" : "bg-white border-[#e6dfd5] text-[#52525b]"}">
            ${escapeHtml(c.ten_ca)} ${formatTime(c.gio_bat_dau)}
        </button>`).join("");

    const ca = todayData.ca.find(c => c.ma_phan_cong === selectedShiftId);
    const btn = document.getElementById("btn-check");
    const hint = document.getElementById("check-hint");
    const result = document.getElementById("check-result");

    if (!ca) {
        document.getElementById("shift-title").textContent = "Hôm nay bạn không có ca nào";
        document.getElementById("shift-status").innerHTML = `<a href="/my-schedule" class="text-xs font-semibold text-[#cf6800] hover:underline">Xem lịch làm của tôi</a>`;
        btn.disabled = true;
        btn.textContent = "Không có ca để check-in";
        hint.textContent = "Chỉ chấm công được cho ca đã được phân công trong lịch đã công bố.";
        result.classList.add("hidden");
        return;
    }

    document.getElementById("shift-title").textContent = `${ca.ten_ca} • ${formatTime(ca.gio_bat_dau)} - ${formatTime(ca.gio_ket_thuc)}`;
    document.getElementById("shift-status").innerHTML = statusBadge(ATTENDANCE_STATUS, ca.trang_thai);

    if (ca.gio_vao) {
        btn.textContent = "Check-out kết thúc ca";
        btn.disabled = !ca.co_the_check_out;
        hint.textContent = ca.co_the_check_out
            ? `Ca kết thúc lúc ${formatTime(ca.gio_ket_thuc)}. Check-out trước giờ này sẽ bị tính về sớm.`
            : (ca.trang_thai === "chua_check_out"
                ? "Đã quá hạn check-out. Hãy gửi yêu cầu bù check-out ở trang Lịch sử công."
                : "Bạn đã hoàn thành ca này.");
    } else {
        btn.textContent = "Bắt đầu Check-in vào ca";
        btn.disabled = !ca.co_the_check_in;
        const start = formatTime(ca.gio_bat_dau);
        const [h, m] = start.split(":").map(Number);
        const graceEnd = new Date(2000, 0, 1, h, m + todayData.an_han_phut);
        const graceText = `${String(graceEnd.getHours()).padStart(2, "0")}:${String(graceEnd.getMinutes()).padStart(2, "0")}`;
        if (ca.trang_thai === "chua_den_ca") {
            hint.textContent = `Nút Check-in sẽ mở lúc ${hhmm(ca.mo_check_in_luc)}.`;
        } else if (ca.trang_thai === "vang_mat") {
            hint.textContent = "Ca đã kết thúc mà chưa check-in, hệ thống ghi nhận Vắng. Nếu bạn có đi làm, hãy gửi yêu cầu bù công.";
        } else {
            hint.textContent = `Vui lòng check-in trước ${graceText} để không bị tính đi trễ.`;
        }
    }

    result.classList.toggle("hidden", !ca.gio_vao);
    document.getElementById("res-in").textContent = hhmm(ca.gio_vao);
    document.getElementById("res-out").textContent = hhmm(ca.gio_ra);
    document.getElementById("res-labels").innerHTML = attendanceLabels(ca.nhan);
    const link = document.getElementById("request-link");
    link.classList.toggle("hidden", !ca.co_the_gui_yeu_cau);
    link.href = `/attendance-history?pc=${ca.ma_phan_cong}`;
}

async function submitCheck() {
    const ca = todayData && todayData.ca.find(c => c.ma_phan_cong === selectedShiftId);
    if (!ca) return;
    const isOut = !!ca.gio_vao;
    if (isOut) {
        // FR-10 mục 3: cảnh báo trước khi check-out sớm
        const end = new Date(combineDateTime(ca.ngay_lam, ca.gio_ket_thuc));
        if (ca.gio_ket_thuc < ca.gio_bat_dau) end.setDate(end.getDate() + 1);  // ca qua đêm
        const early = Math.floor((end - serverNow()) / 60000);
        const msg = early > 0
            ? `Bạn đang về sớm ${early} phút so với giờ kết thúc ca. Vẫn check-out?`
            : `Xác nhận Check-out ${ca.ten_ca}?`;
        if (!confirm(msg)) return;
    }

    const btn = document.getElementById("btn-check");
    btn.disabled = true;
    try {
        const row = await API.request(`/api/attendance/${isOut ? "check-out" : "check-in"}`, {
            method: "POST",
            headers: { "X-Device-Id": deviceId() },
            body: {
                ma_phan_cong: ca.ma_phan_cong,
                vi_do: position ? position.vi_do : null,
                kinh_do: position ? position.kinh_do : null
            }
        });
        const flagged = (row.co || []).length ? ` (gắn cờ: ${row.co.map(f => FLAG_NAMES[f] || f).join(", ")})` : "";
        showToast(`${isOut ? "Check-out" : "Check-in"} thành công lúc ${hhmm(isOut ? row.gio_ra : row.gio_vao)}${flagged}`,
            flagged ? "warning" : "success");
        await loadToday();
        loadHistory();
    } catch (err) {
        showToast(err.message, "error");
        loadToday();
    }
}

// ---------- Lịch sử cá nhân ----------

async function loadHistory() {
    const range = document.getElementById("history-range").value;
    const today = toISODate(serverNow());
    let from = addDays(today, -6);
    if (range === "30") from = addDays(today, -29);
    if (range === "month") from = today.substring(0, 8) + "01";
    try {
        const data = await API.request(`/api/attendance/me?tu_ngay=${from}&den_ngay=${today}`);
        document.getElementById("stat-hours").textContent = `${data.thong_ke.tong_gio_lam}h`;
        document.getElementById("stat-late").textContent = data.thong_ke.di_tre;
        document.getElementById("stat-absent").textContent = data.thong_ke.vang_mat;
        const rows = data.items.filter(r => r.trang_thai !== "chua_den_ca");
        document.getElementById("history-body").innerHTML = rows.length ? rows.map(r => `
            <tr>
                <td class="py-2 px-2 font-semibold whitespace-nowrap"><a class="hover:underline" href="/attendance-history?pc=${r.ma_phan_cong}">${dayLabel(r.ngay_lam)}</a></td>
                <td class="py-2 px-2 text-xs text-[#52525b]">${escapeHtml(r.ten_ca)}<br>${formatTime(r.gio_bat_dau)}-${formatTime(r.gio_ket_thuc)}</td>
                <td class="py-2 px-2">${hhmm(r.gio_vao)}</td>
                <td class="py-2 px-2">${hhmm(r.gio_ra)}</td>
                <td class="py-2 px-2">${attendanceLabels(r.nhan) || statusBadge(ATTENDANCE_STATUS, r.trang_thai)}</td>
            </tr>`).join("")
            : `<tr><td colspan="5" class="py-6 text-center text-[#71717a]">Chưa có dữ liệu chấm công</td></tr>`;
    } catch (err) {
        showToast(err.message, "error");
    }
}

// ---------- FR-11C: hướng dẫn nhanh lần đầu sử dụng ----------

const TOUR_STEPS = [
    { title: "1. Xem ca hôm nay", text: "Thẻ trên cùng cho biết ca bạn được phân công và trạng thái hiện tại." },
    { title: "2. Bật định vị", text: "Cho phép trình duyệt lấy vị trí. Không có GPS bạn vẫn chấm công được, nhưng bản ghi sẽ bị gắn cờ để Quản lý xem xét." },
    { title: "3. Bấm Check-in / Check-out", text: "Nút mở trước giờ vào ca 15 phút. Giờ ghi nhận là giờ máy chủ, không theo đồng hồ điện thoại." },
    { title: "4. Quên chấm công?", text: "Vào Lịch sử công, chọn ca và gửi yêu cầu bù/sửa công trong 48 giờ sau khi hết ca, kèm lý do và minh chứng nếu có." }
];
let tourIndex = 0;

function startTourIfFirstTime(force) {
    let seen = false;
    try { seen = localStorage.getItem("attendance_tour_done") === "1"; } catch (e) { /* bỏ qua */ }
    if (seen && !force) return;
    tourIndex = 0;
    renderTour();
    openModal("tour-modal");
}

function renderTour() {
    const step = TOUR_STEPS[tourIndex];
    document.getElementById("tour-title").textContent = step.title;
    document.getElementById("tour-text").textContent = step.text;
    document.getElementById("tour-progress").textContent = `${tourIndex + 1}/${TOUR_STEPS.length}`;
    document.getElementById("tour-next").textContent = tourIndex === TOUR_STEPS.length - 1 ? "Bắt đầu chấm công" : "Tiếp";
}

function nextTourStep() {
    if (tourIndex < TOUR_STEPS.length - 1) {
        tourIndex += 1;
        renderTour();
        return;
    }
    finishTour();
}

function finishTour() {
    try { localStorage.setItem("attendance_tour_done", "1"); } catch (e) { /* bỏ qua */ }
    closeModal("tour-modal");
}
