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
    DangKyThangRequest, DangKyThangResponse, DangKyChiTietResponse, TuanInfo,
    PhanCongCreate, PhanCongUpdate, PhanCongResponse, NhanVienRutGon, OCa, TongGioNhanVien,
    BangXepCaResponse, TuanRequest, CaCuaToi, LichCuaToiResponse, XungDot,
    ChiTietXungDot, BaoCaoXungDotResponse, KiemTraXungDotResponse
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


@router.get("/registrations/month", response_model=DangKyThangResponse)
def get_my_monthly_registration(
    month: Optional[str] = Query(None, description="Tháng dạng YYYY-MM (mặc định: tháng hiện tại)"),
    current_user: TaiKhoan = Depends(require_roles(["Staff"])),
    db: Session = Depends(get_db)
):
    """
    FR-07: Xem nguyện vọng ca đã đăng ký theo tháng
    - Trả về danh sách ngày đã đăng ký trong tháng
    - Cung cấp hạn chót và trạng thái mở/khóa cho từng tuần trong tháng
    """
    nv_id = require_employee_profile(current_user)
    if not month:
        month = date.today().strftime("%Y-%m")

    try:
        start_d, end_d = svc.month_date_range(month)
    except Exception:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Định dạng tháng không hợp lệ (cần YYYY-MM)")

    weeks = svc.month_weeks(month)
    tuan_info = []
    for w in weeks:
        tuan_info.append(TuanInfo(
            tuan_bat_dau=w,
            tuan_ket_thuc=w + timedelta(days=6),
            han_chot=svc.registration_deadline(w),
            con_mo=svc.is_registration_open(w)
        ))

    items = db.query(DangKyCa).filter(
        DangKyCa.ma_nv == nv_id,
        DangKyCa.ngay_dang_ky >= start_d,
        DangKyCa.ngay_dang_ky <= end_d
    ).order_by(DangKyCa.ngay_dang_ky, DangKyCa.ma_ca).all()

    return DangKyThangResponse(
        thang=month,
        loai_ca=[map_loai_ca(lc) for lc in svc.active_shift_types(db)],
        tuan_trong_thang=tuan_info,
        dang_ky=[DangKyItem(ngay=dk.ngay_dang_ky, ma_ca=dk.ma_ca) for dk in items],
        tong_ca_dang_ky=len(items)
    )


@router.put("/registrations/month", response_model=DangKyThangResponse)
def save_my_monthly_registration(
    data: DangKyThangRequest,
    current_user: TaiKhoan = Depends(require_roles(["Staff"])),
    db: Session = Depends(get_db)
):
    """
    FR-07: Đăng ký / cập nhật nguyện vọng ca cho cả tháng
    - Nhân viên chọn các ca rảnh cho từng ngày trong tháng
    - Hệ thống kiểm tra hạn chót từng tuần: các tuần đã khóa sẽ không cho phép chỉnh sửa
    """
    nv_id = require_employee_profile(current_user)
    try:
        start_d, end_d = svc.month_date_range(data.thang)
    except Exception:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Định dạng tháng không hợp lệ (cần YYYY-MM)")

    valid_types = {lc.id for lc in svc.active_shift_types(db)}
    new_by_week = defaultdict(set)
    for item in data.dang_ky:
        if not (start_d <= item.ngay <= end_d):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Ngày {item.ngay.strftime('%d/%m/%Y')} không thuộc tháng {data.thang}"
            )
        if item.ma_ca not in valid_types:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Loại ca không tồn tại hoặc đã ngừng sử dụng")
        w_start = svc.week_start(item.ngay)
        new_by_week[w_start].add((item.ngay, item.ma_ca))

    # Lấy các đăng ký hiện tại trong tháng của nhân viên
    existing_items = db.query(DangKyCa).filter(
        DangKyCa.ma_nv == nv_id,
        DangKyCa.ngay_dang_ky >= start_d,
        DangKyCa.ngay_dang_ky <= end_d
    ).all()
    existing_by_week = defaultdict(set)
    for ex in existing_items:
        w_start = svc.week_start(ex.ngay_dang_ky)
        existing_by_week[w_start].add((ex.ngay_dang_ky, ex.ma_ca))

    # Kiểm tra hạn chót các tuần
    all_weeks = svc.month_weeks(data.thang)
    for w in all_weeks:
        w_existing = existing_by_week.get(w, set())
        w_new = new_by_week.get(w, set())
        if w_existing != w_new and not svc.is_registration_open(w):
            han_chot = svc.registration_deadline(w)
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Tuần {svc.week_label(w)} đã quá hạn chót đăng ký ({han_chot.strftime('%H:%M %d/%m/%Y')}). Không thể chỉnh sửa nguyện vọng của tuần này."
            )

    # Cập nhật cho các tuần còn mở
    for w in all_weeks:
        if svc.is_registration_open(w):
            w_end = w + timedelta(days=6)
            db.query(DangKyCa).filter(
                DangKyCa.ma_nv == nv_id,
                DangKyCa.ngay_dang_ky >= max(start_d, w),
                DangKyCa.ngay_dang_ky <= min(end_d, w_end)
            ).delete(synchronize_session=False)

            for ngay, ma_ca in sorted(new_by_week.get(w, set())):
                db.add(DangKyCa(ma_nv=nv_id, ma_ca=ma_ca, ngay_dang_ky=ngay, trang_thai="nguyen_vong"))

    db.commit()

    # Trả về kết quả mới
    return get_my_monthly_registration(month=data.thang, current_user=current_user, db=db)


@router.delete("/registrations/me")
def delete_my_registration(
    week: Optional[date] = Query(None, description="Ngày Thứ Hai hoặc ngày trong tuần cần xóa nguyện vọng"),
    month: Optional[str] = Query(None, description="Tháng dạng YYYY-MM cần xóa nguyện vọng"),
    current_user: TaiKhoan = Depends(require_roles(["Staff"])),
    db: Session = Depends(get_db)
):
    """FR-07: Hủy / xóa toàn bộ nguyện vọng ca của tuần hoặc tháng trước hạn chót"""
    nv_id = require_employee_profile(current_user)
    if month is not None:
        try:
            start_d, end_d = svc.month_date_range(month)
        except Exception:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Định dạng tháng không hợp lệ (cần YYYY-MM)")
        all_weeks = svc.month_weeks(month)
        for w in all_weeks:
            if not svc.is_registration_open(w):
                w_end = w + timedelta(days=6)
                has_reg = db.query(DangKyCa).filter(
                    DangKyCa.ma_nv == nv_id,
                    DangKyCa.ngay_dang_ky >= max(start_d, w),
                    DangKyCa.ngay_dang_ky <= min(end_d, w_end)
                ).first()
                if has_reg:
                    han_chot = svc.registration_deadline(w)
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail=f"Tuần {svc.week_label(w)} đã quá hạn chót đăng ký ({han_chot.strftime('%H:%M %d/%m/%Y')}). Không thể xóa nguyện vọng tuần này."
                    )
        deleted = db.query(DangKyCa).filter(
            DangKyCa.ma_nv == nv_id,
            DangKyCa.ngay_dang_ky >= start_d,
            DangKyCa.ngay_dang_ky <= end_d
        ).delete(synchronize_session=False)
        db.commit()
        return {"message": f"Đã xóa {deleted} nguyện vọng ca trong tháng {month}", "so_luong": deleted}

    start = resolve_week(week)
    if not svc.is_registration_open(start):
        han_chot = svc.registration_deadline(start)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Đã quá hạn chót đăng ký ({han_chot.strftime('%H:%M %d/%m/%Y')}). Không thể xóa nguyện vọng tuần này."
        )

    end = start + timedelta(days=6)
    deleted = db.query(DangKyCa).filter(
        DangKyCa.ma_nv == nv_id,
        DangKyCa.ngay_dang_ky >= start,
        DangKyCa.ngay_dang_ky <= end
    ).delete(synchronize_session=False)
    db.commit()
    return {"message": f"Đã xóa {deleted} nguyện vọng ca trong tuần {svc.week_label(start)}", "so_luong": deleted}



@router.get("/registrations", response_model=List[DangKyChiTietResponse])
def list_registrations(
    week: Optional[date] = Query(None, description="Lọc theo tuần"),
    month: Optional[str] = Query(None, description="Lọc theo tháng (YYYY-MM)"),
    ma_nv: Optional[int] = Query(None, description="Lọc theo nhân viên"),
    current_user: TaiKhoan = Depends(require_roles(ADMIN_ROLES)),
    db: Session = Depends(get_db)
):
    """FR-07: Quản lý xem danh sách nguyện vọng ca đã đăng ký của nhân viên theo tuần hoặc tháng"""
    q = db.query(DangKyCa).join(DangKyCa.nhan_vien).join(DangKyCa.loai_ca)
    if week is not None:
        start = svc.week_start(week)
        end = start + timedelta(days=6)
        q = q.filter(DangKyCa.ngay_dang_ky >= start, DangKyCa.ngay_dang_ky <= end)
    elif month is not None:
        start_d, end_d = svc.month_date_range(month)
        q = q.filter(DangKyCa.ngay_dang_ky >= start_d, DangKyCa.ngay_dang_ky <= end_d)

    if ma_nv is not None:
        q = q.filter(DangKyCa.ma_nv == ma_nv)

    items = q.order_by(DangKyCa.ngay_dang_ky, DangKyCa.ma_ca).all()
    results = []
    for dk in items:
        results.append(DangKyChiTietResponse(
            id=dk.id,
            ma_nv=dk.ma_nv,
            ho_ten=dk.nhan_vien.ho_ten if dk.nhan_vien else None,
            ma_nhan_vien=dk.nhan_vien.ma_nhan_vien if dk.nhan_vien else None,
            ma_ca=dk.ma_ca,
            ten_ca=dk.loai_ca.ten_ca if dk.loai_ca else None,
            ma_loai_ca=dk.loai_ca.ma_loai_ca if dk.loai_ca else None,
            ngay_dang_ky=dk.ngay_dang_ky,
            ngay_tao=dk.ngay_tao
        ))
    return results



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


@router.put("/assignments/{assignment_id}", response_model=BangXepCaResponse)
def update_assignment(
    assignment_id: int,
    data: PhanCongUpdate,
    current_user: TaiKhoan = Depends(require_roles(ADMIN_ROLES)),
    db: Session = Depends(get_db)
):
    """FR-08: Quản lý điều chỉnh thủ công một phân công ca (đổi nhân viên, ca hoặc ngày làm)"""
    pc = db.query(PhanCongCa).filter(PhanCongCa.id == assignment_id).first()
    if not pc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Không tìm thấy phân công ca")

    start_old = svc.week_start(pc.ngay_lam)
    ensure_week_editable(db, start_old)

    new_nv_id = data.ma_nv if data.ma_nv is not None else pc.ma_nv
    new_ca_id = data.ma_ca if data.ma_ca is not None else pc.ma_ca
    new_ngay = data.ngay_lam if data.ngay_lam is not None else pc.ngay_lam
    start_new = svc.week_start(new_ngay)
    ensure_week_editable(db, start_new)

    lc = db.query(LoaiCa).filter(LoaiCa.id == new_ca_id, LoaiCa.trang_thai == True).first()
    if not lc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Loại ca không tồn tại hoặc đã ngừng sử dụng")

    nv = db.query(NhanVien).filter(NhanVien.id == new_nv_id).first()
    reason = svc.employee_block_reason(nv)
    if nv is None or nv.is_deleted or nv.trang_thai == "da_nghi":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Không thể xếp ca: {reason}")

    dup = db.query(PhanCongCa).filter(
        PhanCongCa.ma_nv == new_nv_id,
        PhanCongCa.ma_ca == new_ca_id,
        PhanCongCa.ngay_lam == new_ngay,
        PhanCongCa.id != assignment_id
    ).first()
    if dup:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"{nv.ho_ten} đã có trong ca này")

    week_new = svc.get_or_create_week(db, start_new)
    pc.ma_nv = new_nv_id
    pc.ma_ca = new_ca_id
    pc.ngay_lam = new_ngay
    pc.ma_lich_tuan = week_new.id
    pc.theo_nguyen_vong = svc.is_preferred(db, new_nv_id, new_ca_id, new_ngay)
    db.commit()
    return build_schedule(db, start_new)


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


@router.delete("/schedule/clear", response_model=BangXepCaResponse)
def clear_schedule(
    week: Optional[date] = Query(None, description="Một ngày bất kỳ trong tuần cần xóa bản nháp"),
    current_user: TaiKhoan = Depends(require_roles(ADMIN_ROLES)),
    db: Session = Depends(get_db)
):
    """FR-08: Xóa toàn bộ phân công nháp trong tuần để xếp lại từ đầu"""
    start = resolve_week(week)
    ensure_week_editable(db, start)
    for pc in list(svc.week_assignments(db, start)):
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
    - Gửi thông báo trong ứng dụng (in-app) và email cho từng nhân viên có ca
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
        tieu_de = f"Lịch ca tuần {svc.week_label(start)} đã được công bố: bạn có {len(items)} ca"
        noi_dung = "\n".join(lines)
        lien_ket = f"/my-schedule?week={start.isoformat()}"

        # Thông báo in-app
        svc.notify(
            db, ma_nv,
            tieu_de=tieu_de,
            noi_dung=noi_dung,
            lien_ket=lien_ket
        )

        # FR-08: Gửi email thông báo nếu nhân viên có email
        nv = db.query(NhanVien).filter(NhanVien.id == ma_nv).first()
        if nv and nv.email:
            svc.send_email_notification(
                to_email=nv.email,
                tieu_de=tieu_de,
                noi_dung=noi_dung
            )

    db.commit()
    return build_schedule(db, start)


# ---------- Kiểm tra & Báo cáo xung đột ca (FR-09) ----------

@router.get("/conflicts", response_model=BaoCaoXungDotResponse)
def get_schedule_conflicts(
    week: Optional[date] = Query(None, description="Một ngày bất kỳ trong tuần cần kiểm tra xung đột"),
    current_user: TaiKhoan = Depends(require_roles(ADMIN_ROLES)),
    db: Session = Depends(get_db)
):
    """
    FR-09: Báo cáo chi tiết các xung đột và cảnh báo trong tuần:
    - Trùng ca/chồng lấp thời gian
    - Nhân viên nghỉ phép hoặc đã nghỉ việc
    - Vượt số giờ quy định (> 8h/ngày hoặc > 48h/tuần)
    - Thiếu nhân sự (understaffed) hoặc thừa nhân sự
    """
    start = resolve_week(week)
    end = start + timedelta(days=6)
    schedule = build_schedule(db, start)
    type_map = {lc.id: lc for lc in db.query(LoaiCa).all()}

    xung_dot_phan_cong = []
    for pc in schedule.phan_cong:
        lc = type_map.get(pc.ma_ca)
        for xd in pc.xung_dot:
            xung_dot_phan_cong.append(ChiTietXungDot(
                ma_phan_cong=pc.id,
                ma_nv=pc.ma_nv,
                ho_ten=pc.ho_ten,
                ngay_lam=pc.ngay_lam,
                ma_ca=pc.ma_ca,
                ten_ca=lc.ten_ca if lc else None,
                loai=xd.loai,
                muc_do=xd.muc_do,
                thong_bao=xd.thong_bao
            ))

    canh_bao_o_ca = []
    for o in schedule.o_ca:
        lc = type_map.get(o.ma_ca)
        for cb in o.canh_bao:
            canh_bao_o_ca.append(ChiTietXungDot(
                ngay_lam=o.ngay,
                ma_ca=o.ma_ca,
                ten_ca=lc.ten_ca if lc else None,
                loai=cb.loai,
                muc_do=cb.muc_do,
                thong_bao=cb.thong_bao
            ))

    return BaoCaoXungDotResponse(
        tuan_bat_dau=start,
        tuan_ket_thuc=end,
        co_the_cong_bo=schedule.co_the_cong_bo,
        tong_so_loi=schedule.so_loi,
        tong_so_canh_bao=schedule.so_canh_bao,
        xung_dot_phan_cong=xung_dot_phan_cong,
        canh_bao_o_ca=canh_bao_o_ca
    )


@router.post("/conflicts/check", response_model=KiemTraXungDotResponse)
def check_shift_conflict(
    data: PhanCongCreate,
    current_user: TaiKhoan = Depends(require_roles(ADMIN_ROLES)),
    db: Session = Depends(get_db)
):
    """
    FR-09: Kiểm tra trước xung đột ca khi dự định xếp một nhân viên vào ô ca (không lưu DB):
    - Trùng giờ / chồng lấp
    - Trạng thái nhân viên (nghỉ phép, nghỉ việc)
    - Vượt quá 8h/ngày hoặc 48h/tuần
    """
    hop_le, co_loi, msg, list_xd = svc.check_assignment_conflicts(db, data.ma_nv, data.ma_ca, data.ngay_lam)
    return KiemTraXungDotResponse(
        hop_le=hop_le,
        co_loi=co_loi,
        thong_bao_chinh=msg,
        xung_dot=[XungDot(**xd) for xd in list_xd]
    )



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
