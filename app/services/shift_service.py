"""
Sprint 4: Đăng ký lịch rảnh và xếp ca làm việc (FR-07, FR-08, FR-09)
Các hàm xử lý nghiệp vụ dùng chung cho API ca làm.
"""
from collections import defaultdict
from datetime import date, datetime, time, timedelta
from typing import Dict, List, Optional, Tuple

from sqlalchemy.orm import Session

from app.config import settings
from app.models.employee import NhanVien
from app.models.shift import LoaiCa, DangKyCa, PhanCongCa, LichCaTuan, ThongBao

WEEKDAY_LABELS = ["T2", "T3", "T4", "T5", "T6", "T7", "CN"]


# ---------- Tuần và hạn chót đăng ký (FR-07) ----------

def week_start(d: date) -> date:
    """Trả về ngày Thứ Hai của tuần chứa ngày d"""
    return d - timedelta(days=d.weekday())


def week_days(start: date) -> List[date]:
    return [start + timedelta(days=i) for i in range(7)]


def registration_deadline(start: date) -> datetime:
    """
    Hạn chót đăng ký nguyện vọng cho tuần bắt đầu từ 'start'.
    Mặc định: Thứ Năm của tuần trước, lúc 23:59.
    """
    days_before = 7 - settings.REGISTRATION_DEADLINE_WEEKDAY
    deadline_day = start - timedelta(days=days_before)
    return datetime.combine(
        deadline_day,
        time(settings.REGISTRATION_DEADLINE_HOUR, settings.REGISTRATION_DEADLINE_MINUTE, 59)
    )


def is_registration_open(start: date, now: Optional[datetime] = None) -> bool:
    return (now or datetime.now()) <= registration_deadline(start)


def format_day(d: date) -> str:
    return f"{WEEKDAY_LABELS[d.weekday()]} {d.strftime('%d/%m')}"


# ---------- Khung giờ ca ----------

def shift_interval(loai_ca: LoaiCa, ngay: date) -> Optional[Tuple[datetime, datetime]]:
    """Khoảng thời gian thực của ca trong ngày; ca qua đêm thì giờ kết thúc sang ngày hôm sau"""
    if not loai_ca or loai_ca.gio_bat_dau is None or loai_ca.gio_ket_thuc is None:
        return None
    start = datetime.combine(ngay, loai_ca.gio_bat_dau)
    end = datetime.combine(ngay, loai_ca.gio_ket_thuc)
    if end <= start:
        end += timedelta(days=1)
    return start, end


def shift_hours(loai_ca: LoaiCa) -> float:
    interval = shift_interval(loai_ca, date(2000, 1, 3))
    if not interval:
        return 0.0
    return round((interval[1] - interval[0]).total_seconds() / 3600, 2)


def shift_label(loai_ca: LoaiCa) -> str:
    name = loai_ca.ten_ca or loai_ca.ma_loai_ca
    if loai_ca.gio_bat_dau and loai_ca.gio_ket_thuc:
        return f"{name} ({loai_ca.gio_bat_dau.strftime('%H:%M')}-{loai_ca.gio_ket_thuc.strftime('%H:%M')})"
    return name


def active_shift_types(db: Session) -> List[LoaiCa]:
    items = db.query(LoaiCa).filter(LoaiCa.trang_thai == True).all()
    return sorted(items, key=lambda lc: (lc.gio_bat_dau or time(0, 0), lc.id))


# ---------- Nhân viên được xếp ca (FR-06, BR-05) ----------

def schedulable_employees(db: Session) -> List[NhanVien]:
    return db.query(NhanVien).filter(
        NhanVien.is_deleted == False,
        NhanVien.trang_thai == "dang_lam"
    ).order_by(NhanVien.ho_ten).all()


def employee_block_reason(nv: Optional[NhanVien]) -> Optional[str]:
    """Lý do nhân viên không được xếp ca (None nếu xếp được)"""
    if nv is None:
        return "Không tìm thấy hồ sơ nhân viên"
    if nv.is_deleted:
        return "Hồ sơ nhân viên đã bị xóa"
    if nv.trang_thai == "da_nghi":
        return "Nhân viên đã nghỉ việc"
    if nv.trang_thai == "nghi_phep":
        return "Nhân viên đang nghỉ phép"
    return None


# ---------- Lịch tuần ----------

def get_week(db: Session, start: date) -> Optional[LichCaTuan]:
    return db.query(LichCaTuan).filter(LichCaTuan.tuan_bat_dau == start).first()


def get_or_create_week(db: Session, start: date) -> LichCaTuan:
    week = get_week(db, start)
    if not week:
        week = LichCaTuan(tuan_bat_dau=start, trang_thai="nhap")
        db.add(week)
        db.flush()
    return week


def week_assignments(db: Session, start: date) -> List[PhanCongCa]:
    end = start + timedelta(days=6)
    return db.query(PhanCongCa).filter(
        PhanCongCa.ngay_lam >= start,
        PhanCongCa.ngay_lam <= end
    ).order_by(PhanCongCa.ngay_lam, PhanCongCa.ma_ca, PhanCongCa.id).all()


def week_registrations(db: Session, start: date) -> List[DangKyCa]:
    end = start + timedelta(days=6)
    return db.query(DangKyCa).filter(
        DangKyCa.ngay_dang_ky >= start,
        DangKyCa.ngay_dang_ky <= end
    ).all()


def is_preferred(db: Session, ma_nv: int, ma_ca: int, ngay: date) -> bool:
    return db.query(DangKyCa).filter(
        DangKyCa.ma_nv == ma_nv,
        DangKyCa.ma_ca == ma_ca,
        DangKyCa.ngay_dang_ky == ngay
    ).first() is not None


# ---------- Phát hiện xung đột (FR-09) ----------

def detect_conflicts(assignments: List[PhanCongCa]) -> Dict[int, List[dict]]:
    """
    Trả về {id phân công: [xung đột]}. Mỗi xung đột gồm loai, muc_do ('loi' | 'canh_bao') và thong_bao.
    - 'loi' chặn việc công bố lịch: trùng giờ (BR-01), nhân viên nghỉ phép/đã nghỉ việc.
    - 'canh_bao' vẫn cho công bố: vượt số giờ/ngày hoặc giờ/tuần.
    """
    conflicts: Dict[int, List[dict]] = defaultdict(list)
    by_employee: Dict[int, List[PhanCongCa]] = defaultdict(list)
    for pc in assignments:
        by_employee[pc.ma_nv].append(pc)

    for ma_nv, items in by_employee.items():
        nv = items[0].nhan_vien

        # Nhân viên nghỉ phép / đã nghỉ việc / đã xóa
        reason = employee_block_reason(nv)
        if reason:
            for pc in items:
                conflicts[pc.id].append({"loai": "trang_thai", "muc_do": "loi", "thong_bao": reason})

        # Hai ca chồng lấp thời gian (kể cả ca qua đêm)
        intervals = []
        for pc in items:
            interval = shift_interval(pc.loai_ca, pc.ngay_lam) if pc.ngay_lam else None
            if interval:
                intervals.append((pc, interval))
        for i in range(len(intervals)):
            for j in range(i + 1, len(intervals)):
                (a, (a_start, a_end)), (b, (b_start, b_end)) = intervals[i], intervals[j]
                if a_start < b_end and b_start < a_end:
                    conflicts[a.id].append({
                        "loai": "trung_ca", "muc_do": "loi",
                        "thong_bao": f"Trùng giờ với {shift_label(b.loai_ca)} ngày {format_day(b.ngay_lam)}"
                    })
                    conflicts[b.id].append({
                        "loai": "trung_ca", "muc_do": "loi",
                        "thong_bao": f"Trùng giờ với {shift_label(a.loai_ca)} ngày {format_day(a.ngay_lam)}"
                    })

        # Tổng giờ theo ngày và theo tuần
        hours_by_day: Dict[date, float] = defaultdict(float)
        for pc in items:
            hours_by_day[pc.ngay_lam] += shift_hours(pc.loai_ca)
        for ngay, hours in hours_by_day.items():
            if hours > settings.MAX_HOURS_PER_DAY:
                for pc in items:
                    if pc.ngay_lam == ngay:
                        conflicts[pc.id].append({
                            "loai": "qua_gio_ngay", "muc_do": "canh_bao",
                            "thong_bao": f"Tổng {hours:g} giờ ngày {format_day(ngay)}, vượt mức {settings.MAX_HOURS_PER_DAY:g} giờ/ngày"
                        })
        week_hours = sum(hours_by_day.values())
        if week_hours > settings.MAX_HOURS_PER_WEEK:
            for pc in items:
                conflicts[pc.id].append({
                    "loai": "qua_gio_tuan", "muc_do": "canh_bao",
                    "thong_bao": f"Tổng {week_hours:g} giờ trong tuần, vượt mức {settings.MAX_HOURS_PER_WEEK:g} giờ/tuần"
                })

    return conflicts


def slot_warnings(so_nguoi: int, loai_ca: LoaiCa) -> List[dict]:
    """FR-08: cảnh báo thiếu/thừa người cho từng ô ca"""
    toi_thieu = loai_ca.so_nv_toi_thieu or 0
    toi_da = loai_ca.so_nv_toi_da
    if so_nguoi < toi_thieu:
        return [{"loai": "thieu_nguoi", "muc_do": "canh_bao",
                 "thong_bao": f"Thiếu ca: mới có {so_nguoi}/{toi_thieu} người"}]
    if toi_da is not None and so_nguoi > toi_da:
        return [{"loai": "du_nguoi", "muc_do": "canh_bao",
                 "thong_bao": f"Vượt số người tối đa: {so_nguoi}/{toi_da} người"}]
    return []


# ---------- Xếp ca tự động (FR-08) ----------

def auto_schedule(db: Session, start: date) -> int:
    """
    Xếp ca tự động cho tuần bắt đầu từ 'start', dựa trên nguyện vọng đã đăng ký.
    - Xóa các phân công nháp cũ của tuần rồi xếp lại từ đầu.
    - Lượt 1 lấp đủ số người tối thiểu cho mọi ô ca, lượt 2 lấp tới số tối đa.
    - Ưu tiên người có ít giờ hơn trong tuần để chia ca công bằng.
    - Không xếp trùng giờ, không vượt số giờ/ngày và giờ/tuần.
    Ô ca không đủ người sẽ hiện cảnh báo "thiếu ca" để Quản lý bổ sung thủ công.
    Trả về số lượt phân công đã tạo.
    """
    week = get_or_create_week(db, start)
    for pc in list(week_assignments(db, start)):
        db.delete(pc)
    db.flush()

    shift_types = [lc for lc in active_shift_types(db) if shift_interval(lc, start)]
    employees = {nv.id: nv for nv in schedulable_employees(db)}
    days = week_days(start)

    wishes: Dict[Tuple[date, int], List[int]] = defaultdict(list)
    for dk in week_registrations(db, start):
        if dk.ma_nv in employees:
            wishes[(dk.ngay_dang_ky, dk.ma_ca)].append(dk.ma_nv)

    busy: Dict[int, List[Tuple[datetime, datetime]]] = defaultdict(list)
    hours_week: Dict[int, float] = defaultdict(float)
    hours_day: Dict[Tuple[int, date], float] = defaultdict(float)
    slots: Dict[Tuple[date, int], List[int]] = defaultdict(list)

    def can_assign(ma_nv: int, ngay: date, lc: LoaiCa) -> bool:
        s, e = shift_interval(lc, ngay)
        h = shift_hours(lc)
        if any(s < be and bs < e for bs, be in busy[ma_nv]):
            return False
        if hours_day[(ma_nv, ngay)] + h > settings.MAX_HOURS_PER_DAY:
            return False
        if hours_week[ma_nv] + h > settings.MAX_HOURS_PER_WEEK:
            return False
        return True

    created = 0
    for use_max in (False, True):
        for ngay in days:
            for lc in shift_types:
                key = (ngay, lc.id)
                target = (lc.so_nv_toi_da or 0) if use_max else (lc.so_nv_toi_thieu or 0)
                candidates = [m for m in wishes.get(key, []) if m not in slots[key]]
                candidates.sort(key=lambda m: (hours_week[m], m))
                for ma_nv in candidates:
                    if len(slots[key]) >= target:
                        break
                    if not can_assign(ma_nv, ngay, lc):
                        continue
                    db.add(PhanCongCa(
                        ma_nv=ma_nv, ma_ca=lc.id, ngay_lam=ngay, ma_lich_tuan=week.id,
                        trang_thai="nhap", theo_nguyen_vong=True
                    ))
                    slots[key].append(ma_nv)
                    busy[ma_nv].append(shift_interval(lc, ngay))
                    hours_week[ma_nv] += shift_hours(lc)
                    hours_day[(ma_nv, ngay)] += shift_hours(lc)
                    created += 1

    db.commit()
    return created


# ---------- Thông báo (FR-08) ----------

def notify(db: Session, ma_nv: int, tieu_de: str, noi_dung: str = None, lien_ket: str = None):
    db.add(ThongBao(ma_nv=ma_nv, tieu_de=tieu_de, noi_dung=noi_dung, lien_ket=lien_ket))


def week_label(start: date) -> str:
    end = start + timedelta(days=6)
    return f"{start.strftime('%d/%m')} - {end.strftime('%d/%m/%Y')}"
