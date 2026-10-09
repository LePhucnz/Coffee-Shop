"""
Sprint 4: Đăng ký lịch rảnh và xếp ca làm việc
- FR-07: Nhân viên đăng ký nguyện vọng ca theo tuần, khóa sau hạn chót
- FR-08: Quản lý cấu hình nhu cầu nhân lực, xếp ca tự động/bán tự động, công bố lịch
- FR-09: Phát hiện xung đột ca (trùng giờ, nghỉ phép/nghỉ việc, vượt giờ)
"""
from collections import defaultdict
from datetime import date, datetime, timedelta
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.core.deps import get_current_user, require_roles
from app.database import get_db
from app.models.employee import NhanVien
from app.models.shift import LoaiCa, DangKyCa, PhanCongCa
from app.models.user import TaiKhoan
from app.schemas.shift import (
    LoaiCaCreate, LoaiCaUpdate, LoaiCaResponse,
    DangKyItem, DangKyTuanRequest, DangKyTuanResponse,
    PhanCongCreate, PhanCongResponse, NhanVienRutGon, OCa, TongGioNhanVien,
    BangXepCaResponse, TuanRequest, CaCuaToi, LichCuaToiResponse, XungDot
)
from app.services import shift_service as svc

router = APIRouter(prefix="/api/shifts", tags=["Đăng ký & Xếp ca làm việc (Shifts)"])

ADMIN_ROLES = ["Admin", "Manager"]


def map_loai_ca(lc: LoaiCa) -> LoaiCaResponse:
    return LoaiCaResponse(
        id=lc.id,
        ma_loai_ca=lc.ma_loai_ca,
        ten_ca=lc.ten_ca or lc.ma_loai_ca,
        gio_bat_dau=lc.gio_bat_dau,
        gio_ket_thuc=lc.gio_ket_thuc,
        so_nv_toi_thieu=lc.so_nv_toi_thieu,
        so_nv_toi_da=lc.so_nv_toi_da,
        mo_ta=lc.mo_ta,
        trang_thai=bool(lc.trang_thai),
        so_gio=svc.shift_hours(lc)
    )


def resolve_week(value: Optional[date], default_offset_weeks: int = 1) -> date:
    """Đưa ngày bất kỳ về Thứ Hai của tuần; không truyền thì lấy tuần kế tiếp"""
    if value is None:
        value = date.today() + timedelta(weeks=default_offset_weeks)
    return svc.week_start(value)


def ensure_week_editable(db: Session, start: date):
    week = svc.get_week(db, start)
    if week and week.trang_thai == "da_cong_bo":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Lịch tuần này đã công bố. Hãy chuyển lịch về nháp trước khi chỉnh sửa."
        )


# ---------- Loại ca ----------

@router.get("/types", response_model=List[LoaiCaResponse])
def list_shift_types(
    include_inactive: bool = False,
    current_user: TaiKhoan = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Danh sách loại ca (ca sáng, ca chiều, ...) kèm khung giờ và số người cần"""
    if include_inactive:
        items = sorted(db.query(LoaiCa).all(), key=lambda lc: (lc.gio_bat_dau is None, lc.gio_bat_dau or datetime.min.time(), lc.id))
    else:
        items = svc.active_shift_types(db)
    return [map_loai_ca(lc) for lc in items]


@router.post("/types", response_model=LoaiCaResponse, status_code=status.HTTP_201_CREATED)
def create_shift_type(
    data: LoaiCaCreate,
    current_user: TaiKhoan = Depends(require_roles(ADMIN_ROLES)),
    db: Session = Depends(get_db)
):
    """FR-08: Thêm loại ca mới"""
    code = data.ma_loai_ca.upper()
    if db.query(LoaiCa).filter(LoaiCa.ma_loai_ca == code).first():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Mã loại ca '{code}' đã tồn tại")
    lc = LoaiCa(ma_loai_ca=code, **data.model_dump(exclude={"ma_loai_ca"}))
    db.add(lc)
    db.commit()
    db.refresh(lc)
    return map_loai_ca(lc)


@router.put("/types/{type_id}", response_model=LoaiCaResponse)
def update_shift_type(
    type_id: int,
    data: LoaiCaUpdate,
    current_user: TaiKhoan = Depends(require_roles(ADMIN_ROLES)),
    db: Session = Depends(get_db)
):
    """FR-08: Cấu hình khung giờ và số nhân viên tối thiểu/tối đa cho từng ca"""
    lc = db.query(LoaiCa).filter(LoaiCa.id == type_id).first()
    if not lc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Không tìm thấy loại ca")
    for key, value in data.model_dump().items():
        setattr(lc, key, value)
    db.commit()
    db.refresh(lc)
    return map_loai_ca(lc)


# ---------- Đăng ký nguyện vọng (FR-07) ----------

def build_registration_response(db: Session, nv_id: int, start: date) -> DangKyTuanResponse:
    end = start + timedelta(days=6)
    items = db.query(DangKyCa).filter(
        DangKyCa.ma_nv == nv_id,
        DangKyCa.ngay_dang_ky >= start,
        DangKyCa.ngay_dang_ky <= end
    ).order_by(DangKyCa.ngay_dang_ky, DangKyCa.ma_ca).all()
    return DangKyTuanResponse(
        tuan_bat_dau=start,
        tuan_ket_thuc=end,
        han_chot=svc.registration_deadline(start),
        con_mo=svc.is_registration_open(start),
        loai_ca=[map_loai_ca(lc) for lc in svc.active_shift_types(db)],
        dang_ky=[DangKyItem(ngay=dk.ngay_dang_ky, ma_ca=dk.ma_ca) for dk in items]
    )


def require_employee_profile(user: TaiKhoan) -> int:
    if not user.ma_nv:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Tài khoản chưa liên kết với hồ sơ nhân viên"
        )
    return user.ma_nv


@router.get("/registrations/me", response_model=DangKyTuanResponse)
def get_my_registration(
    week: Optional[date] = Query(None, description="Một ngày bất kỳ trong tuần cần xem (mặc định: tuần gần nhất còn hạn đăng ký)"),
    current_user: TaiKhoan = Depends(require_roles(["Staff"])),
    db: Session = Depends(get_db)
):
    """FR-07: Xem nguyện vọng ca đã đăng ký trong tuần và hạn chót đăng ký"""
    nv_id = require_employee_profile(current_user)
    if week is None:
        # Mặc định mở tuần gần nhất còn hạn đăng ký
        start = resolve_week(None)
        while not svc.is_registration_open(start):
            start += timedelta(weeks=1)
    else:
        start = svc.week_start(week)
    return build_registration_response(db, nv_id, start)


@router.put("/registrations/me", response_model=DangKyTuanResponse)
def save_my_registration(
    data: DangKyTuanRequest,
    current_user: TaiKhoan = Depends(require_roles(["Staff"])),
    db: Session = Depends(get_db)
):
    """
    FR-07: Đăng ký / sửa nguyện vọng ca cho cả tuần
    - Ghi đè toàn bộ nguyện vọng của tuần bằng danh sách gửi lên
    - Khóa sau hạn chót (mặc định Thứ Năm 23:59 của tuần trước)
    """
    nv_id = require_employee_profile(current_user)
    start = svc.week_start(data.tuan_bat_dau)
    end = start + timedelta(days=6)

    if not svc.is_registration_open(start):
        han_chot = svc.registration_deadline(start)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Đã quá hạn chót đăng ký ({han_chot.strftime('%H:%M %d/%m/%Y')}). Nguyện vọng tuần này đã bị khóa."
        )

    valid_types = {lc.id for lc in svc.active_shift_types(db)}
    seen = set()
    for item in data.dang_ky:
        if not (start <= item.ngay <= end):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Ngày {item.ngay.strftime('%d/%m/%Y')} không thuộc tuần đang đăng ký"
            )
        if item.ma_ca not in valid_types:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Loại ca không tồn tại hoặc đã ngừng sử dụng")
        seen.add((item.ngay, item.ma_ca))

    db.query(DangKyCa).filter(
        DangKyCa.ma_nv == nv_id,
        DangKyCa.ngay_dang_ky >= start,
        DangKyCa.ngay_dang_ky <= end
    ).delete(synchronize_session=False)
    for ngay, ma_ca in sorted(seen):
        db.add(DangKyCa(ma_nv=nv_id, ma_ca=ma_ca, ngay_dang_ky=ngay, trang_thai="nguyen_vong"))
    db.commit()
    return build_registration_response(db, nv_id, start)


# ---------- Bảng xếp ca (FR-08, FR-09) ----------

def build_schedule(db: Session, start: date) -> BangXepCaResponse:
    end = start + timedelta(days=6)
    days = svc.week_days(start)
    week = svc.get_week(db, start)
    shift_types = svc.active_shift_types(db)
    type_map = {lc.id: lc for lc in db.query(LoaiCa).all()}

    assignments = svc.week_assignments(db, start)
    conflicts = svc.detect_conflicts(assignments)

    phan_cong = []
    for pc in assignments:
        nv = pc.nhan_vien
        phan_cong.append(PhanCongResponse(
            id=pc.id,
            ma_nv=pc.ma_nv,
            ho_ten=nv.ho_ten if nv else None,
            ma_nhan_vien=nv.ma_nhan_vien if nv else None,
            ma_ca=pc.ma_ca,
            ngay_lam=pc.ngay_lam,
            so_gio=svc.shift_hours(type_map.get(pc.ma_ca)),
            theo_nguyen_vong=bool(pc.theo_nguyen_vong),
            xung_dot=[XungDot(**c) for c in conflicts.get(pc.id, [])]
        ))

    wishes = defaultdict(list)
    for dk in svc.week_registrations(db, start):
        nv = dk.nhan_vien
        if nv and svc.employee_block_reason(nv) is None:
            wishes[(dk.ngay_dang_ky, dk.ma_ca)].append(
                NhanVienRutGon(ma_nv=nv.id, ho_ten=nv.ho_ten, ma_nhan_vien=nv.ma_nhan_vien)
            )

    counts = defaultdict(int)
    for pc in assignments:
        counts[(pc.ngay_lam, pc.ma_ca)] += 1

    o_ca = []
    for ngay in days:
        for lc in shift_types:
            n = counts[(ngay, lc.id)]
            o_ca.append(OCa(
                ngay=ngay,
                ma_ca=lc.id,
                so_nguoi=n,
                toi_thieu=lc.so_nv_toi_thieu or 0,
                toi_da=lc.so_nv_toi_da,
                nguyen_vong=wishes.get((ngay, lc.id), []),
                canh_bao=[XungDot(**w) for w in svc.slot_warnings(n, lc)]
            ))

    totals = {}
    for pc in phan_cong:
        t = totals.setdefault(pc.ma_nv, TongGioNhanVien(ma_nv=pc.ma_nv, ho_ten=pc.ho_ten or "", so_ca=0, so_gio=0))
        t.so_ca += 1
        t.so_gio = round(t.so_gio + pc.so_gio, 2)

    so_loi = sum(1 for pc in phan_cong for c in pc.xung_dot if c.muc_do == "loi")
    so_canh_bao = sum(1 for pc in phan_cong for c in pc.xung_dot if c.muc_do == "canh_bao") \
        + sum(len(o.canh_bao) for o in o_ca)

    return BangXepCaResponse(
        tuan_bat_dau=start,
        tuan_ket_thuc=end,
        ngay=days,
        trang_thai=week.trang_thai if week else "chua_tao",
        ngay_cong_bo=week.ngay_cong_bo if week else None,
        han_chot_dang_ky=svc.registration_deadline(start),
        loai_ca=[map_loai_ca(lc) for lc in shift_types],
        phan_cong=phan_cong,
        o_ca=o_ca,
        tong_gio=sorted(totals.values(), key=lambda t: t.ho_ten),
        so_loi=so_loi,
        so_canh_bao=so_canh_bao,
        co_the_cong_bo=bool(phan_cong) and so_loi == 0 and (not week or week.trang_thai != "da_cong_bo")
    )


@router.get("/schedule", response_model=BangXepCaResponse)
def get_schedule(
    week: Optional[date] = Query(None, description="Một ngày bất kỳ trong tuần (mặc định: tuần kế tiếp)"),
    current_user: TaiKhoan = Depends(require_roles(ADMIN_ROLES)),
    db: Session = Depends(get_db)
):
    """FR-08/FR-09: Bảng ca dạng lưới của một tuần, kèm nguyện vọng, cảnh báo thiếu ca và xung đột"""
    return build_schedule(db, resolve_week(week))


@router.post("/schedule/auto", response_model=BangXepCaResponse)
def run_auto_schedule(
    data: TuanRequest,
    current_user: TaiKhoan = Depends(require_roles(ADMIN_ROLES)),
    db: Session = Depends(get_db)
):
    """FR-08: Xếp ca tự động theo nguyện vọng (xóa bản nháp cũ của tuần rồi xếp lại)"""
    start = svc.week_start(data.tuan_bat_dau)
    ensure_week_editable(db, start)
    svc.auto_schedule(db, start)
    return build_schedule(db, start)


@router.post("/assignments", response_model=BangXepCaResponse, status_code=status.HTTP_201_CREATED)
def add_assignment(
    data: PhanCongCreate,
    current_user: TaiKhoan = Depends(require_roles(ADMIN_ROLES)),
    db: Session = Depends(get_db)
):
    """FR-08: Quản lý thêm thủ công một nhân viên vào ô ca (bán tự động)"""
    start = svc.week_start(data.ngay_lam)
    ensure_week_editable(db, start)

    lc = db.query(LoaiCa).filter(LoaiCa.id == data.ma_ca, LoaiCa.trang_thai == True).first()
    if not lc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Loại ca không tồn tại hoặc đã ngừng sử dụng")

    nv = db.query(NhanVien).filter(NhanVien.id == data.ma_nv).first()
    reason = svc.employee_block_reason(nv)
    # BR-05: không xếp ca mới cho người đã nghỉ việc / hồ sơ đã xóa.
    # Người đang nghỉ phép vẫn thêm được nhưng bị đánh dấu xung đột (FR-09) và chặn công bố.
    if nv is None or nv.is_deleted or nv.trang_thai == "da_nghi":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Không thể xếp ca: {reason}")

    duplicate = db.query(PhanCongCa).filter(
        PhanCongCa.ma_nv == data.ma_nv,
        PhanCongCa.ma_ca == data.ma_ca,
        PhanCongCa.ngay_lam == data.ngay_lam
    ).first()
    if duplicate:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"{nv.ho_ten} đã có trong ca này")

    week = svc.get_or_create_week(db, start)
    db.add(PhanCongCa(
        ma_nv=data.ma_nv, ma_ca=data.ma_ca, ngay_lam=data.ngay_lam, ma_lich_tuan=week.id,
        trang_thai="nhap", theo_nguyen_vong=svc.is_preferred(db, data.ma_nv, data.ma_ca, data.ngay_lam)
    ))
    db.commit()
    return build_schedule(db, start)


@router.delete("/assignments/{assignment_id}", response_model=BangXepCaResponse)
def remove_assignment(
    assignment_id: int,
    current_user: TaiKhoan = Depends(require_roles(ADMIN_ROLES)),
    db: Session = Depends(get_db)
):
    """FR-08: Gỡ một nhân viên khỏi ô ca"""
    pc = db.query(PhanCongCa).filter(PhanCongCa.id == assignment_id).first()
    if not pc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Không tìm thấy phân công ca")
    start = svc.week_start(pc.ngay_lam)
    ensure_week_editable(db, start)
    db.delete(pc)
    db.commit()
    return build_schedule(db, start)


@router.post("/schedule/publish", response_model=BangXepCaResponse)
def publish_schedule(
    data: TuanRequest,
    current_user: TaiKhoan = Depends(require_roles(ADMIN_ROLES)),
    db: Session = Depends(get_db)
):
    """
    FR-08 / BR-02: Công bố lịch ca chính thức
    - Không cho công bố khi còn lỗi (trùng giờ, nhân viên nghỉ phép/nghỉ việc)
    - Gửi thông báo trong ứng dụng cho từng nhân viên có ca
    """
    start = svc.week_start(data.tuan_bat_dau)
    ensure_week_editable(db, start)
    schedule = build_schedule(db, start)
    if not schedule.phan_cong:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Tuần này chưa có ca nào để công bố")
    if schedule.so_loi:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Còn {schedule.so_loi} lỗi xung đột ca (ô màu đỏ). Hãy sửa trước khi công bố."
        )

    week = svc.get_or_create_week(db, start)
    week.trang_thai = "da_cong_bo"
    week.ngay_cong_bo = datetime.now()
    week.nguoi_cong_bo = current_user.id

    type_map = {lc.id: lc for lc in db.query(LoaiCa).all()}
    per_employee = defaultdict(list)
    for pc in svc.week_assignments(db, start):
        pc.trang_thai = "da_cong_bo"
        pc.ma_lich_tuan = week.id
        per_employee[pc.ma_nv].append(pc)

    for ma_nv, items in per_employee.items():
        lines = [f"{svc.format_day(pc.ngay_lam)}: {svc.shift_label(type_map[pc.ma_ca])}" for pc in items]
        svc.notify(
            db, ma_nv,
            tieu_de=f"Lịch ca tuần {svc.week_label(start)} đã được công bố: bạn có {len(items)} ca",
            noi_dung="\n".join(lines),
            lien_ket=f"/my-schedule?week={start.isoformat()}"
        )
    db.commit()
    return build_schedule(db, start)


@router.post("/schedule/unpublish", response_model=BangXepCaResponse)
def unpublish_schedule(
    data: TuanRequest,
    current_user: TaiKhoan = Depends(require_roles(ADMIN_ROLES)),
    db: Session = Depends(get_db)
):
    """Chuyển lịch đã công bố về nháp để chỉnh sửa; nhân viên được báo lịch đang điều chỉnh"""
    start = svc.week_start(data.tuan_bat_dau)
    week = svc.get_week(db, start)
    if not week or week.trang_thai != "da_cong_bo":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Lịch tuần này chưa được công bố")
    week.trang_thai = "nhap"
    week.ngay_cong_bo = None
    affected = set()
    for pc in svc.week_assignments(db, start):
        pc.trang_thai = "nhap"
        affected.add(pc.ma_nv)
    for ma_nv in affected:
        svc.notify(
            db, ma_nv,
            tieu_de=f"Lịch ca tuần {svc.week_label(start)} đang được điều chỉnh",
            noi_dung="Quản lý đã thu hồi lịch để chỉnh sửa. Bạn sẽ nhận thông báo khi lịch được công bố lại.",
            lien_ket=f"/my-schedule?week={start.isoformat()}"
        )
    db.commit()
    return build_schedule(db, start)


# ---------- Lịch làm của tôi ----------

@router.get("/my-schedule", response_model=LichCuaToiResponse)
def get_my_schedule(
    week: Optional[date] = Query(None, description="Một ngày bất kỳ trong tuần (mặc định: tuần hiện tại)"),
    current_user: TaiKhoan = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Xem lịch làm việc cá nhân. BR-02: chỉ thấy lịch đã công bố."""
    nv_id = require_employee_profile(current_user)
    start = resolve_week(week, default_offset_weeks=0)
    end = start + timedelta(days=6)
    week_obj = svc.get_week(db, start)
    published = bool(week_obj and week_obj.trang_thai == "da_cong_bo")

    ca = []
    if published:
        items = db.query(PhanCongCa).filter(
            PhanCongCa.ma_nv == nv_id,
            PhanCongCa.ngay_lam >= start,
            PhanCongCa.ngay_lam <= end
        ).order_by(PhanCongCa.ngay_lam).all()
        items.sort(key=lambda pc: (pc.ngay_lam, pc.loai_ca.gio_bat_dau or datetime.min.time()))
        for pc in items:
            ca.append(CaCuaToi(
                id=pc.id,
                ngay_lam=pc.ngay_lam,
                ma_ca=pc.ma_ca,
                ten_ca=pc.loai_ca.ten_ca or pc.loai_ca.ma_loai_ca,
                gio_bat_dau=pc.loai_ca.gio_bat_dau,
                gio_ket_thuc=pc.loai_ca.gio_ket_thuc,
                so_gio=svc.shift_hours(pc.loai_ca)
            ))

    return LichCuaToiResponse(
        tuan_bat_dau=start,
        tuan_ket_thuc=end,
        da_cong_bo=published,
        ngay_cong_bo=week_obj.ngay_cong_bo if published else None,
        ca=ca,
        tong_gio=round(sum(c.so_gio for c in ca), 2)
    )


# ---------- Số liệu cho trang Tổng quan ----------

@router.get("/today")
def today_summary(
    current_user: TaiKhoan = Depends(require_roles(ADMIN_ROLES)),
    db: Session = Depends(get_db)
):
    """Số ca có người làm hôm nay và số ô ca thiếu người trong tuần hiện tại"""
    today = date.today()
    start = svc.week_start(today)
    schedule = build_schedule(db, start)
    today_slots = [o for o in schedule.o_ca if o.ngay == today]
    return {
        "so_ca_hom_nay": sum(1 for o in today_slots if o.so_nguoi > 0),
        "so_luot_hom_nay": sum(o.so_nguoi for o in today_slots),
        # Tuần chưa xếp ca thì chưa tính thiếu ca
        "so_o_thieu_tuan_nay": None if schedule.trang_thai == "chua_tao"
        else sum(1 for o in schedule.o_ca if any(c.loai == "thieu_nguoi" for c in o.canh_bao)),
        "trang_thai_tuan_nay": schedule.trang_thai
    }
