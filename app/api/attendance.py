"""
Sprint 5: Chấm công trực tuyến
- FR-10: Check-in / Check-out qua web, mở trước giờ ca, ghi nhận GPS + IP + thiết bị, gắn cờ bất thường
- FR-11: Gắn nhãn Đúng giờ / Đi trễ / Về sớm / Vắng mặt / Chưa check-out
- FR-11A: Quản lý điều chỉnh trực tiếp, điều chỉnh hàng loạt, duyệt vượt ca, miễn phạt, xác minh cờ, hủy ca
- FR-11B: Lịch sử cá nhân, màn Quản lý theo ngày / theo kỳ, xuất Excel
- FR-11D: Cấu hình tham số chấm công, chốt kỳ công
"""
import json
import math
from collections import defaultdict
from datetime import date, datetime, time, timedelta
from typing import Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response, status
from sqlalchemy.orm import Session

from app.core.deps import get_current_user, require_roles
from app.database import get_db
from app.models.attendance import YeuCauChamCong, NhatKyChamCong, KyCongDaChot, BanGhiDieuChinh
from app.models.employee import NhanVien
from app.models.shift import PhanCongCa, ChamCong
from app.models.system import CuaHang
from app.models.user import TaiKhoan, NhatKyHeThong
from app.schemas.attendance import (
    ChamCongRequest, CaChamCong, HomNayResponse, ThongKeChamCong, LichSuChamCongResponse,
    OBangCong, DongBangCong, BangCongKyResponse, NhatKyResponse, ChiTietChamCongResponse,
    DieuChinhRequest, DuyetVuotCaRequest, MienPhatRequest, XacMinhCoRequest, HuyCaRequest,
    DieuChinhHangLoatRequest, ChotKyRequest, CauHinhChamCongSchema, YeuCauResponse
)
from app.services import attendance_service as svc
from app.services import shift_service as shift_svc
from app.services.excel_service import build_xlsx

router = APIRouter(prefix="/api/attendance", tags=["Chấm công (Attendance)"])

ADMIN_ROLES = svc.ADMIN_ROLES
MAX_RANGE_DAYS_MANAGER = 400
STAFF_HISTORY_DAYS = 366     # FR-11B: nhân viên tra cứu 12 tháng gần nhất
PAGE_SIZE = 20

LOG_ACTIONS = {
    "check_in": "Check-in",
    "check_out": "Check-out",
    "dieu_chinh_truc_tiep": "Quản lý điều chỉnh trực tiếp",
    "dieu_chinh_truc_tiep_ky_sau": "Điều chỉnh ghi sang kỳ sau",
    "dieu_chinh_hang_loat": "Điều chỉnh hàng loạt",
    "dieu_chinh_hang_loat_ky_sau": "Điều chỉnh hàng loạt ghi sang kỳ sau",
    "duyet_yeu_cau": "Duyệt yêu cầu bù/sửa công",
    "duyet_yeu_cau_ky_sau": "Duyệt yêu cầu, ghi sang kỳ sau",
    "duyet_vuot_ca": "Duyệt giờ vượt ca",
    "mien_phat": "Miễn phạt",
    "bo_mien_phat": "Bỏ miễn phạt",
    "xac_minh_co": "Xác nhận giải trình, gỡ cờ",
    "giu_co": "Giữ cờ để theo dõi",
    "huy_ca": "Hủy ca",
}


# ---------- Tiện ích ----------

def require_employee_profile(user: TaiKhoan) -> int:
    if not user.ma_nv:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
                            detail="Tài khoản chưa liên kết với hồ sơ nhân viên nên không có ca để chấm công")
    return user.ma_nv


def is_manager(user: TaiKhoan) -> bool:
    return svc.role_of(user) in ADMIN_ROLES


def client_ip(request: Request) -> Optional[str]:
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",")[0].strip()[:45]
    return request.client.host if request.client else None


def client_device(request: Request) -> Optional[str]:
    """Mã thiết bị do trình duyệt tự sinh và lưu lại (dùng để phát hiện thiết bị trùng, EX-17)"""
    value = (request.headers.get("X-Device-Id") or "").strip()
    return value[:120] or None


def forbid(db: Session, user: TaiKhoan, detail: str):
    """Truy cập dữ liệu người khác: trả 403 và ghi log (FR-11B)"""
    db.add(NhatKyHeThong(ma_tai_khoan=user.id, hanh_dong="truy_cap_trai_phep_cham_cong", ly_do=detail,
                         trang_thai="tu_choi"))
    db.commit()
    raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=detail)


def account_names(db: Session, ids) -> Dict[int, str]:
    ids = {i for i in ids if i}
    if not ids:
        return {}
    result = {}
    for tk in db.query(TaiKhoan).filter(TaiKhoan.id.in_(ids)).all():
        result[tk.id] = (tk.nhan_vien.ho_ten if tk.nhan_vien else tk.ten_dang_nhap)
    return result


def location_state(cc: Optional[ChamCong]) -> str:
    if cc is None or cc.check_in_lan_1 is None:
        return "khong_ro"
    if cc.khong_dinh_vi:
        return "khong_dinh_vi"
    if cc.ngoai_vi_tri:
        return "ngoai_pham_vi"
    return "trong_pham_vi"


def map_row(db: Session, pc: PhanCongCa, cc: Optional[ChamCong], cfg: dict, at: datetime, *,
            manager: bool, open_request: Optional[YeuCauChamCong] = None, locked: bool = False) -> CaChamCong:
    ev = svc.evaluate(pc, cc, cfg, at, pending=open_request is not None)
    window = svc.checkin_window(pc, cfg)
    interval = svc.interval_of(pc)
    deadline = svc.submit_deadline(pc, cfg)
    nv = pc.nhan_vien
    row = CaChamCong(
        ma_phan_cong=pc.id,
        ma_cham_cong=cc.id if cc else None,
        ma_nv=pc.ma_nv,
        ma_nhan_vien=nv.ma_nhan_vien if nv else None,
        ho_ten=nv.ho_ten if nv else None,
        ten_vi_tri=nv.vi_tri.ten_vi_tri if nv and nv.vi_tri else None,
        ngay_lam=pc.ngay_lam,
        ma_ca=pc.ma_ca,
        ten_ca=pc.loai_ca.ten_ca or pc.loai_ca.ma_loai_ca,
        gio_bat_dau=pc.loai_ca.gio_bat_dau,
        gio_ket_thuc=pc.loai_ca.gio_ket_thuc,
        so_gio_ca=shift_svc.shift_hours(pc.loai_ca),
        gio_vao=cc.check_in_lan_1 if cc else None,
        gio_ra=cc.check_out_lan_1 if cc else None,
        gio_vao_goc=cc.gio_vao_goc if cc else None,
        gio_ra_goc=cc.gio_ra_goc if cc else None,
        vi_tri=location_state(cc),
        trang_thai=ev["trang_thai"],
        ten_trang_thai=svc.STATUS_LABELS[ev["trang_thai"]],
        phut_di_tre=ev["phut_di_tre"],
        phut_ve_som=ev["phut_ve_som"],
        phut_vuot_ca=ev["phut_vuot_ca"],
        phut_vuot_ca_duyet=ev["phut_vuot_ca_duyet"],
        so_gio_lam=ev["so_gio_lam"],
        dung_gio=ev["dung_gio"],
        co=ev["co"],
        nhan=ev["nhan"],
        co_the_check_in=ev["co_the_check_in"],
        co_the_check_out=ev["co_the_check_out"],
        mo_check_in_luc=window[0] if window else None,
        han_gui_yeu_cau=deadline,
        co_the_gui_yeu_cau=bool(interval and not pc.da_huy and open_request is None
                                and interval[0] <= at <= deadline),
        da_dieu_chinh=bool(cc and cc.da_dieu_chinh),
        mien_phat=bool(cc and cc.mien_phat),
        ly_do_mien_phat=cc.ly_do_mien_phat if cc else None,
        da_xac_minh_co=bool(cc and cc.da_xac_minh_co),
        ghi_chu_xac_minh=cc.ghi_chu_xac_minh if cc else None,
        da_huy=bool(pc.da_huy),
        ly_do_huy=pc.ly_do_huy,
        ky_da_chot=locked,
        ma_yeu_cau_dang_mo=open_request.id if open_request else None,
        ghi_chu_quan_ly=cc.ghi_chu_quan_ly if cc else None,
    )
    if manager and cc:
        # FR-11B mục 3: chỉ Quản lý thấy khoảng cách, IP, thiết bị
        row.khoang_cach_vao, row.khoang_cach_ra = cc.khoang_cach_vao, cc.khoang_cach_ra
        row.ip_vao, row.ip_ra = cc.ip_vao, cc.ip_ra
        row.thiet_bi_vao, row.thiet_bi_ra = cc.thiet_bi_vao, cc.thiet_bi_ra
    return row


def locked_checker(db: Session):
    periods = db.query(KyCongDaChot).all()
    return lambda d: any(k.tu_ngay <= d <= k.den_ngay for k in periods)


def build_rows(db: Session, assignments: List[PhanCongCa], cfg: dict, at: datetime, manager: bool) -> List[CaChamCong]:
    records = svc.records_for(db, assignments)
    requests = svc.open_requests_for(db, [pc.id for pc in assignments])
    is_locked = locked_checker(db)
    return [map_row(db, pc, records.get(pc.id), cfg, at, manager=manager,
                    open_request=requests.get(pc.id), locked=is_locked(pc.ngay_lam)) for pc in assignments]


def summarize(rows: List[CaChamCong], db: Session, ma_nv: Optional[int] = None) -> ThongKeChamCong:
    stats = ThongKeChamCong()
    for r in rows:
        if r.trang_thai in ("chua_den_ca", "da_huy"):
            continue
        codes = {n.ma for n in r.nhan}
        stats.tong_ca += 1
        stats.so_ca_da_lam += r.gio_vao is not None
        stats.so_du_vao_ra += r.gio_vao is not None and r.gio_ra is not None
        stats.dung_gio += "dung_gio" in codes
        stats.di_tre += "di_tre" in codes
        stats.ve_som += "ve_som" in codes
        stats.vang_mat += "vang_mat" in codes
        stats.chua_check_out += "chua_check_out" in codes
        stats.ngoai_vi_tri += bool({"ngoai_vi_tri", "khong_dinh_vi"} & codes)
        stats.da_dieu_chinh += "da_dieu_chinh" in codes
        stats.tong_gio_lam += r.so_gio_lam
        stats.tong_phut_tre += r.phut_di_tre
        stats.tong_phut_som += r.phut_ve_som
        stats.phut_vuot_ca_cho_duyet += max(r.phut_vuot_ca - r.phut_vuot_ca_duyet, 0)
    stats.tong_gio_lam = round(stats.tong_gio_lam, 2)
    q = db.query(YeuCauChamCong).filter(YeuCauChamCong.trang_thai.in_(["cho_duyet", "can_bo_sung"]))
    if ma_nv is not None:
        q = q.filter(YeuCauChamCong.ma_nv == ma_nv)
    stats.so_yeu_cau_cho_duyet = q.count()
    return stats


def filter_rows(rows: List[CaChamCong], *, nhan: Optional[str] = None, co: Optional[str] = None,
                trang_thai: Optional[str] = None, ma_vi_tri: Optional[int] = None, ma_ca: Optional[int] = None,
                tu_khoa: Optional[str] = None, db: Session = None) -> List[CaChamCong]:
    if tu_khoa:
        key = tu_khoa.strip().lower()
        rows = [r for r in rows if key in (r.ho_ten or "").lower() or key in (r.ma_nhan_vien or "").lower()]
    if ma_ca:
        rows = [r for r in rows if r.ma_ca == ma_ca]
    if ma_vi_tri:
        nv_ids = {nv.id for nv in db.query(NhanVien).filter(NhanVien.ma_vi_tri == ma_vi_tri).all()}
        rows = [r for r in rows if r.ma_nv in nv_ids]
    if trang_thai:
        rows = [r for r in rows if r.trang_thai == trang_thai or any(n.ma == trang_thai for n in r.nhan)]
    if nhan:
        rows = [r for r in rows if any(n.ma == nhan for n in r.nhan)]
    if co:
        if co == "vuot_han_muc":
            ids = {yc.ma_phan_cong for yc in db.query(YeuCauChamCong).filter(YeuCauChamCong.vuot_han_muc == True).all()}
            rows = [r for r in rows if r.ma_phan_cong in ids]
        else:
            rows = [r for r in rows if co in r.co]
    return rows


def resolve_range(tu_ngay: Optional[date], den_ngay: Optional[date], default_days: int = 0):
    today = svc.now().date()
    den_ngay = den_ngay or today
    tu_ngay = tu_ngay or (den_ngay - timedelta(days=default_days))
    if den_ngay < tu_ngay:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Ngày kết thúc phải sau ngày bắt đầu")
    return tu_ngay, den_ngay


def highlight_key(r: CaChamCong):
    codes = {n.ma for n in r.nhan}
    rank = next((i for i, c in enumerate(svc.HIGHLIGHT_ORDER) if c in codes), len(svc.HIGHLIGHT_ORDER))
    return (rank, r.gio_bat_dau or time(0, 0), r.ho_ten or "")


def get_assignment(db: Session, ma_phan_cong: int) -> PhanCongCa:
    pc = db.query(PhanCongCa).filter(PhanCongCa.id == ma_phan_cong).first()
    if not pc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Không tìm thấy ca được phân công")
    return pc


def get_own_assignment(db: Session, user: TaiKhoan, ma_phan_cong: int) -> PhanCongCa:
    nv_id = require_employee_profile(user)
    pc = get_assignment(db, ma_phan_cong)
    if pc.ma_nv != nv_id:
        forbid(db, user, "Bạn chỉ được chấm công cho ca được phân công cho mình")  # BR-03
    if not svc.is_published(pc):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
                            detail="Lịch ca này chưa được công bố nên chưa chấm công được")
    if pc.da_huy:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
                            detail=f"Ca này đã bị Quản lý hủy ({pc.ly_do_huy or 'không ghi lý do'})")
    return pc


def ensure_can_manage(db: Session, user: TaiKhoan, pc: PhanCongCa) -> bool:
    """BR-08: không tự điều chỉnh công của chính mình, trừ khi quán chỉ có một người quản trị (ghi "Tự duyệt")"""
    if user.ma_nv and pc.ma_nv == user.ma_nv:
        if not svc.is_sole_manager(db, user):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN,
                                detail="Không được tự điều chỉnh công của chính mình. Hãy nhờ Chủ quán (Admin) xử lý.")
        return True
    return False


# ---------- Nhân viên: chấm công (FR-10) ----------

@router.get("/today", response_model=HomNayResponse)
def my_today(current_user: TaiKhoan = Depends(get_current_user), db: Session = Depends(get_db)):
    """Các ca hôm nay của tôi và nút Check-in / Check-out nào đang mở"""
    nv_id = require_employee_profile(current_user)
    cfg = svc.get_config(db)
    at = svc.now()
    items = svc.today_assignments(db, nv_id, cfg, at)
    store = svc.store_of(db, current_user.nhan_vien)
    message = None
    reason = shift_svc.employee_block_reason(current_user.nhan_vien)
    if reason:
        message = f"{reason} nên không chấm công được (EX-16). Vui lòng liên hệ Quản lý."
    elif not items:
        message = "Bạn không có ca làm hiện tại. Nếu bạn làm thay ca, nhờ Quản lý cập nhật lịch ca trước."
    return HomNayResponse(
        ngay=at.date(), gio_hien_tai=at,
        ca=build_rows(db, items, cfg, at, manager=False),
        thong_bao=message,
        ten_cua_hang=store.ten_cua_hang if store else None,
        vi_do_quan=float(store.vi_do) if store and store.vi_do is not None else None,
        kinh_do_quan=float(store.kinh_do) if store and store.kinh_do is not None else None,
        ban_kinh_cho_phep=cfg["ban_kinh_m"], mo_truoc_phut=cfg["mo_truoc_phut"], an_han_phut=cfg["an_han_phut"]
    )


def single_row(db: Session, pc: PhanCongCa, cfg: dict, at: datetime, manager: bool) -> CaChamCong:
    return build_rows(db, [pc], cfg, at, manager)[0]


@router.post("/check-in", response_model=CaChamCong)
def check_in(data: ChamCongRequest, request: Request,
             current_user: TaiKhoan = Depends(get_current_user), db: Session = Depends(get_db)):
    """FR-10: Check-in. Mở từ trước giờ ca (mặc định 15 phút) cho tới khi hết ca."""
    pc = get_own_assignment(db, current_user, data.ma_phan_cong)
    cfg = svc.get_config(db)
    at = svc.now()
    reason = shift_svc.employee_block_reason(pc.nhan_vien)
    if reason:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
                            detail=f"{reason} nên không chấm công được. Vui lòng liên hệ Quản lý để xếp lại ca.")
    cc = svc.get_record(db, pc.id)
    if cc and cc.check_in_lan_1:
        # EX-11: bấm trùng trong 60 giây thì bỏ qua, báo "Đã ghi nhận"
        if cc.gio_vao_goc and (at - cc.gio_vao_goc).total_seconds() <= cfg["chong_bam_trung_giay"]:
            return single_row(db, pc, cfg, at, False)
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
                            detail=f"Bạn đã check-in ca này lúc {cc.check_in_lan_1.strftime('%H:%M')}")

    open_at, close_at = svc.checkin_window(pc, cfg)
    if at < open_at:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
                            detail=f"Chưa đến giờ chấm công. Chấm công mở lúc {open_at.strftime('%H:%M %d/%m')}")
    if at > close_at:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
                            detail="Ca làm đã kết thúc nên không check-in được nữa. "
                                   "Nếu bạn đã đi làm, hãy gửi yêu cầu bù công trong 48 giờ.")

    ip = client_ip(request)
    device = client_device(request)
    distance, outside, no_gps = svc.check_location(db, pc.nhan_vien, cfg, data.vi_do, data.kinh_do, ip)
    if not cc:
        cc = ChamCong(ma_phan_cong=pc.id)
        db.add(cc)
    cc.check_in_lan_1 = cc.gio_vao_goc = at
    cc.vi_do_vao, cc.kinh_do_vao, cc.ip_vao, cc.thiet_bi_vao = data.vi_do, data.kinh_do, ip, device
    cc.khoang_cach_vao = distance
    cc.ngoai_vi_tri, cc.khong_dinh_vi = outside, no_gps
    cc.an_han_ap_dung = cfg["an_han_phut"]
    cc.thiet_bi_trung = False
    svc.check_device(db, cc, pc.ma_nv, device, at)
    pc.bat_dau_thuc_te = at
    db.flush()
    svc.save_evaluation(pc, cc, cfg, at)
    svc.write_log(db, pc.id, cc, "check_in", None, svc.snapshot(cc), None, current_user.id)
    db.commit()
    return single_row(db, pc, cfg, at, False)


@router.post("/check-out", response_model=CaChamCong)
def check_out(data: ChamCongRequest, request: Request,
              current_user: TaiKhoan = Depends(get_current_user), db: Session = Depends(get_db)):
    """FR-10: Check-out khi kết thúc ca. Quá ngưỡng thì ca bị đánh dấu "Chưa check-out" để Quản lý xử lý."""
    pc = get_own_assignment(db, current_user, data.ma_phan_cong)
    cfg = svc.get_config(db)
    at = svc.now()
    cc = svc.get_record(db, pc.id)
    if not cc or not cc.check_in_lan_1:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Bạn chưa check-in ca này")
    if cc.check_out_lan_1:
        if cc.gio_ra_goc and (at - cc.gio_ra_goc).total_seconds() <= cfg["chong_bam_trung_giay"]:
            return single_row(db, pc, cfg, at, False)
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
                            detail=f"Bạn đã check-out ca này lúc {cc.check_out_lan_1.strftime('%H:%M')}")
    if at > svc.checkout_deadline(pc, cfg):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
                            detail="Đã quá hạn check-out nên ca bị đánh dấu \"Chưa check-out\". "
                                   "Hãy gửi yêu cầu \"Bù check-out\" kèm giờ ra thực tế.")

    ip = client_ip(request)
    device = client_device(request)
    distance, outside, no_gps = svc.check_location(db, pc.nhan_vien, cfg, data.vi_do, data.kinh_do, ip)
    cc.check_out_lan_1 = cc.gio_ra_goc = at
    cc.vi_do_ra, cc.kinh_do_ra, cc.ip_ra, cc.thiet_bi_ra = data.vi_do, data.kinh_do, ip, device
    cc.khoang_cach_ra = distance
    cc.ngoai_vi_tri = bool(cc.ngoai_vi_tri) or outside
    cc.khong_dinh_vi = bool(cc.khong_dinh_vi) or no_gps
    svc.check_device(db, cc, pc.ma_nv, device, at)
    pc.ket_thuc_thuc_te = at
    before = svc.snapshot(cc)
    before["ra"] = None
    svc.save_evaluation(pc, cc, cfg, at)
    svc.write_log(db, pc.id, cc, "check_out", before, svc.snapshot(cc), None, current_user.id)
    db.commit()
    return single_row(db, pc, cfg, at, False)


# ---------- Nhân viên: lịch sử cá nhân (FR-11B mục 1) ----------

@router.get("/me", response_model=LichSuChamCongResponse)
def my_history(
    tu_ngay: Optional[date] = Query(None, description="Mặc định: đầu tháng hiện tại"),
    den_ngay: Optional[date] = Query(None, description="Mặc định: hôm nay"),
    trang_thai: Optional[str] = Query(None, description="dung_gio, di_tre, ve_som, vang_mat, chua_check_out, da_dieu_chinh..."),
    current_user: TaiKhoan = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    nv_id = require_employee_profile(current_user)
    today = svc.now().date()
    tu_ngay, den_ngay = resolve_range(tu_ngay or today.replace(day=1), den_ngay)
    if tu_ngay < today - timedelta(days=STAFF_HISTORY_DAYS):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
                            detail="Nhân viên chỉ tra cứu được dữ liệu 12 tháng gần nhất")
    cfg = svc.get_config(db)
    at = svc.now()
    rows = build_rows(db, svc.published_assignments(db, tu_ngay, den_ngay, nv_id), cfg, at, manager=False)
    stats = summarize(rows, db, ma_nv=nv_id)
    rows = filter_rows(rows, trang_thai=trang_thai, db=db)
    rows.sort(key=lambda r: (r.ngay_lam, r.gio_bat_dau or time(0, 0)), reverse=True)
    return LichSuChamCongResponse(tu_ngay=tu_ngay, den_ngay=den_ngay, thong_ke=stats, items=rows,
                                  tong_so=len(rows), cap_nhat_luc=at)


# ---------- Chi tiết một ca (nhân viên xem của mình, Quản lý xem tất cả) ----------

def map_log(log: NhatKyChamCong, names: Dict[int, str]) -> NhatKyResponse:
    return NhatKyResponse(
        id=log.id, hanh_dong=log.hanh_dong, ten_hanh_dong=LOG_ACTIONS.get(log.hanh_dong, log.hanh_dong),
        truoc=json.loads(log.truoc) if log.truoc else None, sau=json.loads(log.sau) if log.sau else None,
        ly_do=log.ly_do, nguoi_yeu_cau=names.get(log.nguoi_yeu_cau), nguoi_thuc_hien=names.get(log.nguoi_thuc_hien),
        tu_duyet=bool(log.tu_duyet), thoi_gian=log.thoi_gian
    )


@router.get("/assignments/{ma_phan_cong}", response_model=ChiTietChamCongResponse)
def attendance_detail(ma_phan_cong: int, current_user: TaiKhoan = Depends(get_current_user),
                      db: Session = Depends(get_db)):
    from app.api.attendance_requests import map_request
    pc = get_assignment(db, ma_phan_cong)
    manager = is_manager(current_user)
    if not manager and pc.ma_nv != current_user.ma_nv:
        forbid(db, current_user, "Bạn chỉ được xem dữ liệu chấm công của chính mình")
    if not svc.is_published(pc):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Lịch ca này chưa được công bố")
    cfg = svc.get_config(db)
    at = svc.now()
    row = single_row(db, pc, cfg, at, manager)
    cc = svc.get_record(db, pc.id)
    logs = db.query(NhatKyChamCong).filter(NhatKyChamCong.ma_phan_cong == pc.id).order_by(NhatKyChamCong.thoi_gian, NhatKyChamCong.id).all()
    names = account_names(db, [l.nguoi_thuc_hien for l in logs] + [l.nguoi_yeu_cau for l in logs])
    requests = db.query(YeuCauChamCong).filter(YeuCauChamCong.ma_phan_cong == pc.id).order_by(YeuCauChamCong.ngay_tao.desc()).all()
    recent = []
    if manager:
        recent = db.query(YeuCauChamCong).filter(
            YeuCauChamCong.ma_nv == pc.ma_nv, YeuCauChamCong.ma_phan_cong != pc.id,
            YeuCauChamCong.ngay_tao >= at - timedelta(days=30)
        ).order_by(YeuCauChamCong.ngay_tao.desc()).limit(10).all()
    adjustments = db.query(BanGhiDieuChinh).filter(BanGhiDieuChinh.ma_phan_cong == pc.id).all()
    same_day = db.query(PhanCongCa).filter(PhanCongCa.ma_nv == pc.ma_nv, PhanCongCa.ngay_lam == pc.ngay_lam,
                                           PhanCongCa.id != pc.id).all()
    return ChiTietChamCongResponse(
        ca=row,
        vi_do_vao=float(cc.vi_do_vao) if manager and cc and cc.vi_do_vao is not None else None,
        kinh_do_vao=float(cc.kinh_do_vao) if manager and cc and cc.kinh_do_vao is not None else None,
        vi_do_ra=float(cc.vi_do_ra) if manager and cc and cc.vi_do_ra is not None else None,
        kinh_do_ra=float(cc.kinh_do_ra) if manager and cc and cc.kinh_do_ra is not None else None,
        nhat_ky=[map_log(l, names) for l in logs],
        yeu_cau=[map_request(db, yc) for yc in requests],
        yeu_cau_gan_day=[map_request(db, yc) for yc in recent],
        dieu_chinh_ky_sau=[{
            "id": a.id, "ap_dung_tu_ngay": a.ap_dung_tu_ngay, "so_gio_chenh": float(a.so_gio_chenh or 0),
            "gio_vao_moi": a.gio_vao_moi, "gio_ra_moi": a.gio_ra_moi, "ly_do": a.ly_do, "ngay_tao": a.ngay_tao
        } for a in adjustments],
        ca_cung_ngay=[{"ma_phan_cong": p.id, "ten_ca": shift_svc.shift_label(p.loai_ca),
                       "da_co_cham_cong": svc.get_record(db, p.id) is not None} for p in same_day]
    )


# ---------- Quản lý: theo ngày (màn 07) ----------

@router.get("", response_model=LichSuChamCongResponse)
def list_attendance(
    ngay: Optional[date] = Query(None, description="Chế độ theo ngày (mặc định hôm nay)"),
    tu_ngay: Optional[date] = Query(None),
    den_ngay: Optional[date] = Query(None),
    ma_nv: Optional[int] = Query(None),
    ma_vi_tri: Optional[int] = Query(None),
    ma_ca: Optional[int] = Query(None),
    trang_thai: Optional[str] = Query(None),
    nhan: Optional[str] = Query(None),
    co: Optional[str] = Query(None, description="ngoai_vi_tri, khong_dinh_vi, thiet_bi_trung, vuot_han_muc"),
    tu_khoa: Optional[str] = Query(None, description="Tìm theo tên hoặc mã nhân viên"),
    trang: int = Query(1, ge=1),
    so_dong: int = Query(PAGE_SIZE, ge=1, le=200),
    current_user: TaiKhoan = Depends(require_roles(ADMIN_ROLES)),
    db: Session = Depends(get_db)
):
    """FR-11B: bảng chấm công toàn quán, dòng bất thường nổi lên đầu, có bộ lọc và phân trang"""
    daily = ngay is not None or (tu_ngay is None and den_ngay is None)
    if daily:
        ngay = ngay or svc.now().date()
        tu_ngay = den_ngay = ngay
    tu_ngay, den_ngay = resolve_range(tu_ngay, den_ngay)
    if (den_ngay - tu_ngay).days > MAX_RANGE_DAYS_MANAGER:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Khoảng tra cứu quá dài")
    cfg = svc.get_config(db)
    at = svc.now()
    assignments = svc.published_assignments(db, tu_ngay, den_ngay, ma_nv)
    if daily:
        # Nhân viên đã nghỉ việc không còn xuất hiện trong danh sách hằng ngày (BR-05)
        assignments = [pc for pc in assignments if pc.nhan_vien and not pc.nhan_vien.is_deleted
                       and pc.nhan_vien.trang_thai != "da_nghi"]
    rows = build_rows(db, assignments, cfg, at, manager=True)
    rows = filter_rows(rows, tu_khoa=tu_khoa, ma_ca=ma_ca, ma_vi_tri=ma_vi_tri, db=db)
    stats = summarize(rows, db)
    rows = filter_rows(rows, nhan=nhan, co=co, trang_thai=trang_thai, db=db)
    if daily:
        rows.sort(key=highlight_key)
    else:
        rows.sort(key=lambda r: (r.ngay_lam, r.gio_bat_dau or time(0, 0), r.ho_ten or ""), reverse=True)
    total = len(rows)
    pages = max(1, math.ceil(total / so_dong))
    page_rows = rows[(trang - 1) * so_dong: trang * so_dong]
    return LichSuChamCongResponse(tu_ngay=tu_ngay, den_ngay=den_ngay, thong_ke=stats, items=page_rows,
                                  tong_so=total, trang=trang, so_trang=pages, cap_nhat_luc=at)


@router.get("/today-summary", response_model=ThongKeChamCong)
def today_summary(current_user: TaiKhoan = Depends(require_roles(ADMIN_ROLES)), db: Session = Depends(get_db)):
    """Số liệu chấm công hôm nay cho trang Tổng quan"""
    today = svc.now().date()
    cfg = svc.get_config(db)
    rows = build_rows(db, svc.published_assignments(db, today, today), cfg, svc.now(), manager=True)
    return summarize(rows, db)


# ---------- Quản lý: bảng công theo kỳ (màn 08) ----------

CELL_CODES = {"D": "Đ", "T": "T", "S": "S", "TS": "T+S", "V": "V", "DC": "ĐC", "?": "?", "H": "Hủy", "-": "…"}


def cell_of(r: CaChamCong) -> OBangCong:
    codes = {n.ma for n in r.nhan}
    if r.trang_thai == "da_huy":
        code = "H"
    elif r.trang_thai == "vang_mat":
        code = "V"
    elif r.trang_thai == "chua_check_out":
        code = "?"
    elif r.trang_thai != "hoan_thanh":
        code = "-"
    elif "da_dieu_chinh" in codes:
        code = "DC"
    elif r.phut_di_tre and r.phut_ve_som:
        code = "TS"
    elif r.phut_di_tre:
        code = "T"
    elif r.phut_ve_som:
        code = "S"
    else:
        code = "D"
    hours = r.so_gio_lam
    h, m = int(hours), int(round((hours - int(hours)) * 60))
    hours_text = f"{h}h" + (f"{m:02d}" if m else "")
    label = f"{CELL_CODES[code]} · {hours_text}" if code in ("D", "T", "S", "TS", "DC", "H") else \
        {"V": "V · 0h", "?": "? · Thiếu ra", "-": "Chưa xong"}[code]
    if r.phut_vuot_ca > r.phut_vuot_ca_duyet:
        label += f" +{r.phut_vuot_ca - r.phut_vuot_ca_duyet}p chờ"
    return OBangCong(ma=code, nhan=label, so_gio=hours, ma_phan_cong=r.ma_phan_cong)


def build_period(db: Session, tu_ngay: date, den_ngay: date, ma_nv: Optional[int], tu_khoa: Optional[str],
                 trang_thai: Optional[str], co: Optional[str], ma_vi_tri: Optional[int]) -> BangCongKyResponse:
    cfg = svc.get_config(db)
    rows = build_rows(db, svc.published_assignments(db, tu_ngay, den_ngay, ma_nv), cfg, svc.now(), manager=True)
    rows = filter_rows(rows, tu_khoa=tu_khoa, ma_vi_tri=ma_vi_tri, db=db)
    if trang_thai or co:
        # Lọc theo nhân viên có ít nhất một ca khớp, vẫn hiện đủ cả hàng để đối soát
        keep = {r.ma_nv for r in filter_rows(rows, trang_thai=trang_thai, co=co, db=db)}
        rows = [r for r in rows if r.ma_nv in keep]
    by_nv: Dict[int, DongBangCong] = {}
    total_hours, pending_ot, missing_out = 0.0, 0, 0
    for r in rows:
        line = by_nv.get(r.ma_nv)
        if not line:
            nv = db.get(NhanVien, r.ma_nv)
            line = by_nv[r.ma_nv] = DongBangCong(
                ma_nv=r.ma_nv, ma_nhan_vien=r.ma_nhan_vien, ho_ten=r.ho_ten, ten_vi_tri=r.ten_vi_tri,
                trang_thai_nv=("da_nghi" if nv and (nv.is_deleted or nv.trang_thai == "da_nghi") else (nv.trang_thai if nv else None)),
                o={}
            )
        cell = cell_of(r)
        line.o.setdefault(r.ngay_lam.isoformat(), []).append(cell)
        if r.trang_thai not in ("chua_den_ca", "da_huy"):
            line.so_ca += 1
        line.tong_gio = round(line.tong_gio + r.so_gio_lam, 2)
        line.phut_tre += r.phut_di_tre
        line.phut_som += r.phut_ve_som
        line.so_vang += r.trang_thai == "vang_mat"
        line.so_thieu_ra += r.trang_thai == "chua_check_out"
        total_hours += r.so_gio_lam
        pending_ot += max(r.phut_vuot_ca - r.phut_vuot_ca_duyet, 0)
        missing_out += r.trang_thai == "chua_check_out"
    days = [tu_ngay + timedelta(days=i) for i in range((den_ngay - tu_ngay).days + 1)]
    lines = sorted(by_nv.values(), key=lambda l: (l.trang_thai_nv == "da_nghi", l.ho_ten or ""))
    return BangCongKyResponse(tu_ngay=tu_ngay, den_ngay=den_ngay, ngay=days, nhan_vien=lines,
                              tong_gio_xac_nhan=round(total_hours, 2), phut_vuot_ca_cho_duyet=pending_ot,
                              so_ca_thieu_ra=missing_out)


@router.get("/period", response_model=BangCongKyResponse)
def period_grid(
    tu_ngay: Optional[date] = Query(None, description="Mặc định: đầu tháng"),
    den_ngay: Optional[date] = Query(None, description="Mặc định: cuối tháng"),
    ma_nv: Optional[int] = Query(None),
    ma_vi_tri: Optional[int] = Query(None),
    trang_thai: Optional[str] = Query(None),
    co: Optional[str] = Query(None),
    tu_khoa: Optional[str] = Query(None),
    current_user: TaiKhoan = Depends(require_roles(ADMIN_ROLES)),
    db: Session = Depends(get_db)
):
    """FR-11B: bảng công dạng lưới (nhân viên theo hàng, ngày theo cột), khớp tổng giờ dùng tính lương"""
    today = svc.now().date()
    if tu_ngay is None and den_ngay is None:
        tu_ngay, den_ngay = svc.payroll_cutoff(today).date().replace(day=1), svc.payroll_cutoff(today).date()
    tu_ngay, den_ngay = resolve_range(tu_ngay, den_ngay)
    if (den_ngay - tu_ngay).days > 62:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Bảng công theo kỳ tối đa 62 ngày")
    return build_period(db, tu_ngay, den_ngay, ma_nv, tu_khoa, trang_thai, co, ma_vi_tri)


# ---------- Xuất Excel (FR-11B bước 7) ----------

def fmt_dt(value: Optional[datetime]) -> str:
    return value.strftime("%H:%M %d/%m") if value else ""


@router.get("/export")
def export_excel(
    che_do: str = Query("ngay", pattern="^(ngay|ky)$"),
    ngay: Optional[date] = Query(None),
    tu_ngay: Optional[date] = Query(None),
    den_ngay: Optional[date] = Query(None),
    ma_nv: Optional[int] = Query(None),
    ma_vi_tri: Optional[int] = Query(None),
    ma_ca: Optional[int] = Query(None),
    trang_thai: Optional[str] = Query(None),
    co: Optional[str] = Query(None),
    tu_khoa: Optional[str] = Query(None),
    current_user: TaiKhoan = Depends(require_roles(ADMIN_ROLES)),
    db: Session = Depends(get_db)
):
    """Xuất dữ liệu đang lọc ra file Excel, có cột "Đã điều chỉnh" để đối soát"""
    if che_do == "ky":
        grid = period_grid(tu_ngay, den_ngay, ma_nv, ma_vi_tri, trang_thai, co, tu_khoa, current_user, db)
        header = ["Mã NV", "Họ tên", "Vị trí"] + [d.strftime("%d/%m") for d in grid.ngay] + \
                 ["Số ca", "Giờ xác nhận", "Phút trễ", "Phút sớm", "Số lần vắng", "Thiếu check-out"]
        rows = []
        for line in grid.nhan_vien:
            cells = [", ".join(c.nhan for c in line.o.get(d.isoformat(), [])) for d in grid.ngay]
            rows.append([line.ma_nhan_vien, line.ho_ten, line.ten_vi_tri] + cells +
                        [line.so_ca, line.tong_gio, line.phut_tre, line.phut_som, line.so_vang, line.so_thieu_ra])
        name = f"bang-cong-{grid.tu_ngay:%Y%m%d}-{grid.den_ngay:%Y%m%d}.xlsx"
        content = build_xlsx("Bang cong", header, rows)
    else:
        data = list_attendance(ngay, tu_ngay, den_ngay, ma_nv, ma_vi_tri, ma_ca, trang_thai, None, co, tu_khoa,
                               1, 100000, current_user, db)
        header = ["Ngày", "Mã NV", "Họ tên", "Vị trí", "Ca", "Giờ ca", "Vào", "Ra", "Trễ (phút)", "Sớm (phút)",
                  "Vượt ca (phút)", "Giờ xác nhận", "Trạng thái", "Nhãn", "Đã điều chỉnh", "Khoảng cách vào (m)", "IP vào"]
        rows = [[r.ngay_lam.strftime("%d/%m/%Y"), r.ma_nhan_vien, r.ho_ten, r.ten_vi_tri, r.ten_ca,
                 f"{r.gio_bat_dau.strftime('%H:%M') if r.gio_bat_dau else ''}-{r.gio_ket_thuc.strftime('%H:%M') if r.gio_ket_thuc else ''}",
                 fmt_dt(r.gio_vao), fmt_dt(r.gio_ra), r.phut_di_tre, r.phut_ve_som, r.phut_vuot_ca, r.so_gio_lam,
                 r.ten_trang_thai, ", ".join(n.ten for n in r.nhan), "Đã điều chỉnh" if r.da_dieu_chinh else "",
                 r.khoang_cach_vao, r.ip_vao] for r in data.items]
        name = f"cham-cong-{data.tu_ngay:%Y%m%d}-{data.den_ngay:%Y%m%d}.xlsx"
        content = build_xlsx("Cham cong", header, rows)
    return Response(content=content,
                    media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    headers={"Content-Disposition": f'attachment; filename="{name}"'})


# ---------- Quản lý: xử lý từng ca (màn 10, 11) ----------

def finish_manage(db: Session, pc: PhanCongCa, cfg: dict) -> CaChamCong:
    db.commit()
    return single_row(db, pc, cfg, svc.now(), True)


@router.put("/assignments/{ma_phan_cong}", response_model=CaChamCong)
def adjust_directly(ma_phan_cong: int, data: DieuChinhRequest,
                    current_user: TaiKhoan = Depends(require_roles(ADMIN_ROLES)), db: Session = Depends(get_db)):
    """
    FR-11A "Điều chỉnh do Quản lý": nhập giờ đúng, lý do bắt buộc; áp dụng ngay, báo nhân viên, ghi nhật ký.
    Kỳ đã chốt thì tạo bản ghi điều chỉnh sang kỳ sau (BR-04).
    """
    pc = get_assignment(db, ma_phan_cong)
    if not svc.is_published(pc):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Lịch ca này chưa được công bố")
    tu_duyet = ensure_can_manage(db, current_user, pc)
    cfg = svc.get_config(db)
    cc = svc.get_record(db, pc.id)
    gio_vao = data.gio_vao or (cc.check_in_lan_1 if cc else None)
    gio_ra = None if data.xoa_gio_ra else (data.gio_ra or (cc.check_out_lan_1 if cc else None))
    if gio_ra and not gio_vao:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Cần có giờ vào trước khi nhập giờ ra")
    if gio_vao and gio_ra and gio_ra <= gio_vao:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Giờ ra phải sau giờ vào")
    target = None
    if data.ma_phan_cong_dung and data.ma_phan_cong_dung != pc.id:
        target = get_assignment(db, data.ma_phan_cong_dung)
        if target.ma_nv != pc.ma_nv or target.ngay_lam != pc.ngay_lam:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
                                detail="Chỉ chuyển được sang ca khác của cùng nhân viên trong cùng ngày")
        if svc.get_record(db, target.id):
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Ca đúng đã có bản ghi chấm công")
    kind, result = svc.apply_time_change(
        db, pc, cc, cfg, gio_vao=gio_vao, gio_ra=gio_ra, set_vao=True, set_ra=True, target=target,
        ly_do=data.ly_do.strip(), actor_id=current_user.id, hanh_dong="dieu_chinh_truc_tiep", tu_duyet=tu_duyet
    )
    note = "Điều chỉnh được ghi sang kỳ lương sau vì kỳ này đã chốt." if kind == "phu_luc" else ""
    svc.notify_staff(db, pc.ma_nv, "Quản lý đã điều chỉnh công của bạn",
                     f"Ca {shift_svc.shift_label(pc.loai_ca)} ngày {pc.ngay_lam.strftime('%d/%m/%Y')}. "
                     f"Lý do: {data.ly_do.strip()} {note}".strip(), "/attendance-history")
    return finish_manage(db, target or pc, cfg)


@router.post("/assignments/{ma_phan_cong}/overtime", response_model=CaChamCong)
def approve_overtime(ma_phan_cong: int, data: DuyetVuotCaRequest,
                     current_user: TaiKhoan = Depends(require_roles(ADMIN_ROLES)), db: Session = Depends(get_db)):
    """BR-09, EX-06: duyệt số phút vượt ca được tính công (0 = không duyệt)"""
    pc = get_assignment(db, ma_phan_cong)
    tu_duyet = ensure_can_manage(db, current_user, pc)
    cfg = svc.get_config(db)
    cc = svc.get_record(db, pc.id)
    ev = svc.evaluate(pc, cc, cfg, svc.now())
    if not cc or not ev["phut_vuot_ca"]:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Ca này không có giờ vượt ca")
    if data.so_phut > ev["phut_vuot_ca"]:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
                            detail=f"Chỉ duyệt tối đa {ev['phut_vuot_ca']} phút vượt ca")
    before = {"vuot_ca_duyet": cc.phut_vuot_ca_duyet or 0}
    ky = svc.locked_period(db, pc.ngay_lam)
    if ky:
        delta = (data.so_phut - (cc.phut_vuot_ca_duyet or 0)) / 60
        db.add(BanGhiDieuChinh(ma_phan_cong=pc.id, ma_nv=pc.ma_nv, ma_ky_goc=ky.id,
                               ap_dung_tu_ngay=ky.den_ngay + timedelta(days=1), so_gio_chenh=round(delta, 2),
                               ly_do=f"Duyệt vượt ca: {data.ly_do}", nguoi_tao=current_user.id))
    else:
        cc.phut_vuot_ca_duyet = data.so_phut
        svc.save_evaluation(pc, cc, cfg)
    svc.write_log(db, pc.id, cc, "duyet_vuot_ca", before, {"vuot_ca_duyet": data.so_phut}, data.ly_do,
                  current_user.id, tu_duyet=tu_duyet)
    svc.notify_staff(db, pc.ma_nv, "Giờ vượt ca đã được xem xét",
                     f"Ngày {pc.ngay_lam.strftime('%d/%m/%Y')}: được tính {data.so_phut} phút vượt ca.", "/attendance-history")
    return finish_manage(db, pc, cfg)


@router.post("/assignments/{ma_phan_cong}/waive", response_model=CaChamCong)
def waive_penalty(ma_phan_cong: int, data: MienPhatRequest,
                  current_user: TaiKhoan = Depends(require_roles(ADMIN_ROLES)), db: Session = Depends(get_db)):
    """Quy tắc 11: Miễn phạt trễ/sớm kèm lý do, không đổi giờ chấm công"""
    pc = get_assignment(db, ma_phan_cong)
    tu_duyet = ensure_can_manage(db, current_user, pc)
    cfg = svc.get_config(db)
    cc = svc.get_record(db, pc.id)
    if not cc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Ca này chưa có bản ghi chấm công")
    before = {"mien_phat": bool(cc.mien_phat)}
    cc.mien_phat = data.mien_phat
    cc.ly_do_mien_phat = data.ly_do if data.mien_phat else None
    svc.write_log(db, pc.id, cc, "mien_phat" if data.mien_phat else "bo_mien_phat", before,
                  {"mien_phat": data.mien_phat}, data.ly_do, current_user.id, tu_duyet=tu_duyet)
    if data.mien_phat:
        svc.notify_staff(db, pc.ma_nv, "Bạn được miễn phạt chấm công",
                         f"Ngày {pc.ngay_lam.strftime('%d/%m/%Y')}. Lý do: {data.ly_do}", "/attendance-history")
    return finish_manage(db, pc, cfg)


@router.post("/assignments/{ma_phan_cong}/verify-flags", response_model=CaChamCong)
def verify_flags(ma_phan_cong: int, data: XacMinhCoRequest,
                 current_user: TaiKhoan = Depends(require_roles(ADMIN_ROLES)), db: Session = Depends(get_db)):
    """Xác minh cờ (ngoài vị trí, không định vị, thiết bị trùng): gỡ cờ hoặc giữ để theo dõi, không tự kết luận gian lận"""
    pc = get_assignment(db, ma_phan_cong)
    tu_duyet = ensure_can_manage(db, current_user, pc)
    cfg = svc.get_config(db)
    cc = svc.get_record(db, pc.id)
    if not cc or not (cc.ngoai_vi_tri or cc.khong_dinh_vi or cc.thiet_bi_trung):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Bản ghi này không có cờ cần xác minh")
    before = {"da_xac_minh_co": bool(cc.da_xac_minh_co)}
    cc.da_xac_minh_co = data.xac_nhan
    cc.ghi_chu_xac_minh = data.ghi_chu
    svc.write_log(db, pc.id, cc, "xac_minh_co" if data.xac_nhan else "giu_co", before,
                  {"da_xac_minh_co": data.xac_nhan}, data.ghi_chu, current_user.id, tu_duyet=tu_duyet)
    return finish_manage(db, pc, cfg)


@router.post("/assignments/{ma_phan_cong}/cancel", response_model=CaChamCong)
def cancel_shift(ma_phan_cong: int, data: HuyCaRequest,
                 current_user: TaiKhoan = Depends(require_roles(ADMIN_ROLES)), db: Session = Depends(get_db)):
    """EX-18: hủy ca (quán đóng cửa đột xuất...). Ca bị loại khỏi đánh giá vắng/trễ/sớm, bản ghi đã có vẫn giữ."""
    pc = get_assignment(db, ma_phan_cong)
    if not svc.is_published(pc):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
                            detail="Lịch còn nháp: hãy xóa ca trực tiếp ở màn Xếp ca")
    if pc.da_huy:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Ca này đã được hủy trước đó")
    cfg = svc.get_config(db)
    cc = svc.get_record(db, pc.id)
    pc.da_huy = True
    pc.ly_do_huy = data.ly_do
    pc.tinh_cong_khi_huy = data.tinh_cong
    pc.nguoi_huy = current_user.id
    pc.ngay_huy = svc.now()
    if cc:
        svc.save_evaluation(pc, cc, cfg)
    svc.write_log(db, pc.id, cc, "huy_ca", None, {"tinh_cong": data.tinh_cong}, data.ly_do, current_user.id)
    svc.notify_staff(db, pc.ma_nv, "Ca làm của bạn đã bị hủy",
                     f"Ca {shift_svc.shift_label(pc.loai_ca)} ngày {pc.ngay_lam.strftime('%d/%m/%Y')}. Lý do: {data.ly_do}",
                     "/my-schedule")
    return finish_manage(db, pc, cfg)


@router.post("/bulk-adjust")
def bulk_adjust(data: DieuChinhHangLoatRequest,
                current_user: TaiKhoan = Depends(require_roles(ADMIN_ROLES)), db: Session = Depends(get_db)):
    """
    Điều chỉnh hàng loạt khi có sự cố hệ thống (EX-09): xem trước rồi mới xác nhận.
    Quản lý tự nhập giờ thực tế cho từng ca, hệ thống không tự đoán giờ ra.
    """
    cfg = svc.get_config(db)
    at = svc.now()
    preview, errors = [], []
    plan = []
    for item in data.items:
        pc = db.query(PhanCongCa).filter(PhanCongCa.id == item.ma_phan_cong).first()
        if not pc or not svc.is_published(pc):
            errors.append({"ma_phan_cong": item.ma_phan_cong, "loi": "Không tìm thấy ca đã công bố"})
            continue
        if current_user.ma_nv and pc.ma_nv == current_user.ma_nv and not svc.is_sole_manager(db, current_user):
            errors.append({"ma_phan_cong": pc.id, "loi": "Không được tự điều chỉnh công của chính mình"})
            continue
        cc = svc.get_record(db, pc.id)
        gio_vao = item.gio_vao or (cc.check_in_lan_1 if cc else None)
        gio_ra = item.gio_ra or (cc.check_out_lan_1 if cc else None)
        if not gio_vao or (gio_ra and gio_ra <= gio_vao):
            errors.append({"ma_phan_cong": pc.id, "loi": "Thiếu giờ vào hoặc giờ ra không sau giờ vào"})
            continue
        draft = svc.preview_record(cc, check_in_lan_1=gio_vao, check_out_lan_1=gio_ra, da_dieu_chinh=True,
                                   mien_phat=data.mien_phat or bool(cc and cc.mien_phat))
        after = svc.evaluate(pc, draft, cfg, at)
        preview.append({
            "ma_phan_cong": pc.id, "ho_ten": pc.nhan_vien.ho_ten if pc.nhan_vien else None,
            "ca": shift_svc.shift_label(pc.loai_ca), "ngay_lam": pc.ngay_lam,
            "truoc": svc.snapshot(cc), "sau": {"vao": gio_vao.strftime("%Y-%m-%d %H:%M"),
                                              "ra": gio_ra.strftime("%Y-%m-%d %H:%M") if gio_ra else None,
                                              "gio": after["so_gio_lam"]},
            "nhan_sau": after["nhan"], "ky_da_chot": svc.locked_period(db, pc.ngay_lam) is not None
        })
        plan.append((pc, cc, gio_vao, gio_ra))
    if data.xem_truoc or errors:
        return {"xem_truoc": True, "items": preview, "loi": errors, "da_ap_dung": 0}

    for pc, cc, gio_vao, gio_ra in plan:
        tu_duyet = bool(current_user.ma_nv and pc.ma_nv == current_user.ma_nv)
        kind, result = svc.apply_time_change(db, pc, cc, cfg, gio_vao=gio_vao, gio_ra=gio_ra, set_vao=True,
                                             set_ra=True, ly_do=data.ly_do.strip(), actor_id=current_user.id,
                                             hanh_dong="dieu_chinh_hang_loat", tu_duyet=tu_duyet)
        if kind == "cap_nhat" and data.mien_phat:
            result.mien_phat = True
            result.ly_do_mien_phat = data.ly_do.strip()[:255]
        svc.notify_staff(db, pc.ma_nv, "Quản lý đã điều chỉnh công của bạn",
                         f"Ngày {pc.ngay_lam.strftime('%d/%m/%Y')}. Lý do: {data.ly_do.strip()}", "/attendance-history")
    db.commit()
    return {"xem_truoc": False, "items": preview, "loi": [], "da_ap_dung": len(plan)}


# ---------- Chốt kỳ công (BR-04, Quy tắc 9) ----------

@router.get("/periods")
def list_locked_periods(current_user: TaiKhoan = Depends(require_roles(ADMIN_ROLES)), db: Session = Depends(get_db)):
    items = db.query(KyCongDaChot).order_by(KyCongDaChot.tu_ngay.desc()).all()
    names = account_names(db, [k.nguoi_chot for k in items])
    return [{"id": k.id, "tu_ngay": k.tu_ngay, "den_ngay": k.den_ngay, "ngay_chot": k.ngay_chot,
             "nguoi_chot": names.get(k.nguoi_chot), "ghi_chu": k.ghi_chu} for k in items]


@router.post("/periods/lock", status_code=status.HTTP_201_CREATED)
def lock_period(data: ChotKyRequest, current_user: TaiKhoan = Depends(require_roles(ADMIN_ROLES)),
                db: Session = Depends(get_db)):
    overlap = db.query(KyCongDaChot).filter(KyCongDaChot.tu_ngay <= data.den_ngay,
                                            KyCongDaChot.den_ngay >= data.tu_ngay).first()
    if overlap:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
                            detail=f"Đã có kỳ chốt {overlap.tu_ngay:%d/%m} - {overlap.den_ngay:%d/%m/%Y} trùng khoảng này")
    pending = db.query(YeuCauChamCong).join(PhanCongCa, YeuCauChamCong.ma_phan_cong == PhanCongCa.id).filter(
        YeuCauChamCong.trang_thai.in_(["cho_duyet", "can_bo_sung"]),
        PhanCongCa.ngay_lam >= data.tu_ngay, PhanCongCa.ngay_lam <= data.den_ngay
    ).count()
    if pending and not data.chuyen_yeu_cau_sang_ky_sau:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT,
                            detail=f"Còn {pending} yêu cầu bù/sửa công chưa xử lý trong kỳ. "
                                   "Hãy \"Xử lý ngay\" hoặc chọn \"Chuyển sang kỳ sau dưới dạng điều chỉnh\".")
    ky = KyCongDaChot(tu_ngay=data.tu_ngay, den_ngay=data.den_ngay, nguoi_chot=current_user.id,
                      ngay_chot=svc.now(), ghi_chu=data.ghi_chu)
    db.add(ky)
    db.commit()
    return {"id": ky.id, "tu_ngay": ky.tu_ngay, "den_ngay": ky.den_ngay, "so_yeu_cau_chuyen_ky_sau": pending}


@router.delete("/periods/{ky_id}")
def unlock_period(ky_id: int, current_user: TaiKhoan = Depends(require_roles(["Admin"])),
                  db: Session = Depends(get_db)):
    ky = db.query(KyCongDaChot).filter(KyCongDaChot.id == ky_id).first()
    if not ky:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Không tìm thấy kỳ đã chốt")
    db.delete(ky)
    db.commit()
    return {"message": "Đã mở khóa kỳ công"}


# ---------- Cấu hình chấm công (màn 13) ----------

def config_response(db: Session, user: TaiKhoan) -> CauHinhChamCongSchema:
    cfg = svc.get_config(db)
    store = svc.store_of(db, user.nhan_vien)
    from app.models.attendance import CauHinhChamCong
    last = db.query(CauHinhChamCong).order_by(CauHinhChamCong.ngay_cap_nhat.desc()).first()
    return CauHinhChamCongSchema(
        **cfg,
        ma_cua_hang=store.id if store else None,
        ten_cua_hang=store.ten_cua_hang if store else None,
        vi_do_quan=float(store.vi_do) if store and store.vi_do is not None else None,
        kinh_do_quan=float(store.kinh_do) if store and store.kinh_do is not None else None,
        ngay_cap_nhat=last.ngay_cap_nhat if last else None,
        co_the_sua=svc.role_of(user) == "Admin"
    )


@router.get("/settings", response_model=CauHinhChamCongSchema)
def get_settings(current_user: TaiKhoan = Depends(require_roles(ADMIN_ROLES)), db: Session = Depends(get_db)):
    return config_response(db, current_user)


@router.put("/settings", response_model=CauHinhChamCongSchema)
def update_settings(data: CauHinhChamCongSchema, current_user: TaiKhoan = Depends(require_roles(["Admin"])),
                    db: Session = Depends(get_db)):
    """Chỉ Admin (Chủ quán) được đổi. Giá trị mới áp dụng cho các lần chấm công phát sinh sau thời điểm lưu."""
    values = data.model_dump(exclude={"ma_cua_hang", "ten_cua_hang", "vi_do_quan", "kinh_do_quan",
                                      "ngay_cap_nhat", "co_the_sua"})
    svc.save_config(db, values, current_user.id)
    if data.ma_cua_hang and data.vi_do_quan is not None and data.kinh_do_quan is not None:
        store = db.query(CuaHang).filter(CuaHang.id == data.ma_cua_hang).first()
        if store:
            store.vi_do, store.kinh_do = data.vi_do_quan, data.kinh_do_quan
    db.add(NhatKyHeThong(ma_tai_khoan=current_user.id, hanh_dong="cap_nhat_cau_hinh_cham_cong",
                         ly_do=json.dumps(values, ensure_ascii=False), trang_thai="thanh_cong"))
    db.commit()
    return config_response(db, current_user)
