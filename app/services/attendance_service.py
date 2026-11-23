"""
Sprint 5: Chấm công trực tuyến (FR-10, FR-11, FR-11A, FR-11B, FR-11D)
Các hàm nghiệp vụ dùng chung cho API chấm công:
- Cấu hình chấm công (Admin chỉnh được)
- Đối chiếu giờ chấm công với giờ ca: Đúng giờ, Đi trễ, Về sớm, Vắng, Chưa check-out, Vượt ca
- Kiểm tra vị trí (GPS/IP), thiết bị trùng
- Nhật ký thay đổi (BR-06), kỳ đã chốt và bản ghi phụ lục (BR-04)
"""
import calendar
import json
import math
from collections import defaultdict
from datetime import date, datetime, time, timedelta
from types import SimpleNamespace
from typing import Dict, List, Optional, Tuple

from sqlalchemy.orm import Session

from app.config import settings
from app.models.attendance import (
    CauHinhChamCong, YeuCauChamCong, NhatKyChamCong, KyCongDaChot, BanGhiDieuChinh
)
from app.models.employee import NhanVien
from app.models.shift import PhanCongCa, LichCaTuan, ChamCong
from app.models.system import CuaHang, VaiTro
from app.models.user import TaiKhoan
from app.services import shift_service as shift_svc

ADMIN_ROLES = ["Admin", "Manager"]

STATUS_LABELS = {
    "chua_den_ca": "Chưa đến giờ",
    "cho_check_in": "Chờ check-in",
    "dang_lam": "Đang làm",
    "chua_check_out": "Chưa check-out",
    "hoan_thanh": "Đã hoàn thành",
    "vang_mat": "Vắng không phép",
    "da_huy": "Ca đã hủy",
}

# Cờ bất thường có thể lọc ở màn Quản lý (FR-11B)
FLAG_CODES = ["ngoai_vi_tri", "khong_dinh_vi", "thiet_bi_trung", "vuot_han_muc"]

# Thứ tự ưu tiên khi làm nổi bật dòng bất thường lên đầu bảng "Theo ngày"
HIGHLIGHT_ORDER = ["chua_check_in", "vang_mat", "di_tre", "ngoai_vi_tri", "khong_dinh_vi",
                   "chua_check_out", "thiet_bi_trung", "ve_som", "vuot_ca", "cho_duyet"]

DEVICE_WINDOW_MINUTES = 10  # EX-17: cùng thiết bị, khác tài khoản trong khoảng này thì gắn cờ


def now() -> datetime:
    """Giờ máy chủ của quán (BR-10). Tách riêng để test giả lập được thời gian."""
    return datetime.now()


def minutes_between(a: datetime, b: datetime) -> int:
    """Số phút nguyên từ a tới b (âm nếu b trước a)"""
    return int((b - a).total_seconds() // 60)


# ---------- Cấu hình (FR-11D mục 2) ----------

def get_config(db: Session) -> dict:
    cfg = dict(settings.ATTENDANCE_DEFAULTS)
    for row in db.query(CauHinhChamCong).all():
        if row.khoa not in cfg or row.gia_tri is None:
            continue
        default = settings.ATTENDANCE_DEFAULTS[row.khoa]
        try:
            cfg[row.khoa] = type(default)(row.gia_tri) if not isinstance(default, str) else row.gia_tri
        except ValueError:
            pass
    return cfg


def save_config(db: Session, values: dict, user_id: int):
    for key, value in values.items():
        if key not in settings.ATTENDANCE_DEFAULTS or value is None:
            continue
        row = db.query(CauHinhChamCong).filter(CauHinhChamCong.khoa == key).first()
        if not row:
            row = CauHinhChamCong(khoa=key)
            db.add(row)
        row.gia_tri = str(value)
        row.ngay_cap_nhat = datetime.utcnow()
        row.nguoi_cap_nhat = user_id


def store_ip_prefixes(cfg: dict) -> List[str]:
    return [p.strip() for p in str(cfg.get("dai_ip_quan") or "").split(",") if p.strip()]


# ---------- Vị trí (FR-10, EX-07, EX-08) ----------

def distance_meters(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Khoảng cách giữa 2 tọa độ GPS theo công thức Haversine"""
    r = 6371000
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = math.radians(lat2 - lat1)
    dl = math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


def store_of(db: Session, nv: Optional[NhanVien]) -> Optional[CuaHang]:
    if nv and nv.cua_hang:
        return nv.cua_hang
    return db.query(CuaHang).filter(CuaHang.trang_thai == True).order_by(CuaHang.id).first()


def check_location(db: Session, nv: NhanVien, cfg: dict, vi_do: Optional[float], kinh_do: Optional[float],
                   ip: Optional[str]) -> Tuple[Optional[int], bool, bool]:
    """
    Trả về (khoảng cách tới quán tính bằng mét, ngoài vị trí, không có định vị).
    Không chặn chấm công: chỉ gắn cờ để Quản lý xem xét.
    - Có GPS: ngoài bán kính cho phép thì gắn cờ "Ngoài vị trí" (trừ khi đang dùng Wi-Fi quán).
    - Không có GPS: dùng IP làm căn cứ phụ; IP không thuộc mạng quán thì gắn cờ "Không có định vị".
    """
    in_store_network = bool(ip) and any(ip.startswith(p) for p in store_ip_prefixes(cfg))
    if vi_do is None or kinh_do is None:
        return None, False, not in_store_network
    store = store_of(db, nv)
    if not store or store.vi_do is None or store.kinh_do is None:
        return None, False, False
    d = distance_meters(float(vi_do), float(kinh_do), float(store.vi_do), float(store.kinh_do))
    return int(round(d)), d > cfg["ban_kinh_m"] and not in_store_network, False


def check_device(db: Session, cc: ChamCong, ma_nv: int, device: Optional[str], at: datetime):
    """EX-17: nhiều tài khoản chấm công trên cùng thiết bị trong thời gian ngắn thì gắn cờ cả hai bản ghi"""
    if not device:
        return
    since = at - timedelta(minutes=DEVICE_WINDOW_MINUTES)
    others = db.query(ChamCong).join(PhanCongCa, ChamCong.ma_phan_cong == PhanCongCa.id).filter(
        PhanCongCa.ma_nv != ma_nv,
        ((ChamCong.thiet_bi_vao == device) & (ChamCong.gio_vao_goc >= since)) |
        ((ChamCong.thiet_bi_ra == device) & (ChamCong.gio_ra_goc >= since))
    ).all()
    for other in others:
        other.thiet_bi_trung = True
        cc.thiet_bi_trung = True


# ---------- Ca được phân công ----------

def is_published(pc: PhanCongCa) -> bool:
    return bool(pc.lich_tuan and pc.lich_tuan.trang_thai == "da_cong_bo")


def interval_of(pc: PhanCongCa) -> Optional[Tuple[datetime, datetime]]:
    """Ca xuyên đêm tính vào ngày bắt đầu ca (BR-11)"""
    return shift_svc.shift_interval(pc.loai_ca, pc.ngay_lam) if pc.ngay_lam else None


def checkin_window(pc: PhanCongCa, cfg: dict) -> Optional[Tuple[datetime, datetime]]:
    """EX-03, EX-04: nút Check-in mở trước giờ ca X phút cho tới khi ca kết thúc"""
    interval = interval_of(pc)
    if not interval:
        return None
    return interval[0] - timedelta(minutes=cfg["mo_truoc_phut"]), interval[1]


def checkout_deadline(pc: PhanCongCa, cfg: dict) -> Optional[datetime]:
    interval = interval_of(pc)
    if not interval:
        return None
    return interval[1] + timedelta(minutes=cfg["nguong_chua_checkout_phut"])


def get_record(db: Session, ma_phan_cong: int) -> Optional[ChamCong]:
    return db.query(ChamCong).filter(ChamCong.ma_phan_cong == ma_phan_cong).first()


# ---------- Đối chiếu (FR-11) ----------

def evaluate(pc: PhanCongCa, cc, cfg: dict, at: Optional[datetime] = None, pending: bool = False) -> dict:
    """
    Đối chiếu chấm công với giờ ca. cc có thể là ChamCong hoặc bản nháp (SimpleNamespace) để xem trước.
    Trả về trạng thái, số phút trễ/sớm/vượt ca, giờ công được xác nhận, các nhãn và quyền bấm nút.
    """
    at = at or now()
    interval = interval_of(pc)
    get = (lambda name, default=None: getattr(cc, name, default) if cc is not None else default)
    gio_vao = get("check_in_lan_1")
    gio_ra = get("check_out_lan_1")
    result = {
        "trang_thai": "chua_den_ca", "phut_di_tre": 0, "phut_ve_som": 0, "phut_vuot_ca": 0,
        "phut_vuot_ca_duyet": 0, "so_gio_lam": 0.0, "dung_gio": False,
        "co_the_check_in": False, "co_the_check_out": False, "nhan": [], "co": []
    }
    if not interval:
        return result
    start, end = interval
    grace = get("an_han_ap_dung")
    grace = cfg["an_han_phut"] if grace is None else grace

    if gio_vao:
        tre = minutes_between(start, gio_vao)
        result["phut_di_tre"] = tre if tre > grace else 0
    if gio_ra:
        # Về sớm: ra sớm hơn giờ kết thúc ca (FR-11B mục 4)
        result["phut_ve_som"] = max(minutes_between(gio_ra, end), 0)
        vuot = minutes_between(end, gio_ra)
        result["phut_vuot_ca"] = vuot if vuot > grace else 0
        result["phut_vuot_ca_duyet"] = min(get("phut_vuot_ca_duyet", 0) or 0, result["phut_vuot_ca"])
    if gio_vao and gio_ra:
        # Giờ công chỉ tính trong khung ca; phần vượt ca chỉ cộng khi được duyệt (BR-09)
        worked = (min(gio_ra, end) - max(gio_vao, start)).total_seconds() / 3600
        result["so_gio_lam"] = round(max(worked, 0) + result["phut_vuot_ca_duyet"] / 60, 2)

    labels = []
    if pc.da_huy:
        # EX-18: ca bị hủy không đánh giá vắng/trễ/sớm
        result.update({"trang_thai": "da_huy", "phut_di_tre": 0, "phut_ve_som": 0})
        if not (pc.tinh_cong_khi_huy and gio_vao and gio_ra):
            result["so_gio_lam"] = 0.0
        labels.append({"ma": "da_huy", "ten": "Ca đã hủy" + (" · có tính công" if pc.tinh_cong_khi_huy else "")})
    elif gio_vao and gio_ra:
        result["trang_thai"] = "hoan_thanh"
    elif gio_vao:
        deadline = end + timedelta(minutes=cfg["nguong_chua_checkout_phut"])
        result["trang_thai"] = "chua_check_out" if at > deadline else "dang_lam"
        result["co_the_check_out"] = at <= deadline
    elif at > end:
        result["trang_thai"] = "vang_mat"
    else:
        open_at = start - timedelta(minutes=cfg["mo_truoc_phut"])
        result["trang_thai"] = "cho_check_in" if at >= open_at else "chua_den_ca"
        result["co_the_check_in"] = at >= open_at

    status = result["trang_thai"]
    if status == "vang_mat":
        labels.append({"ma": "vang_mat", "ten": "Vắng không phép"})
    if status == "cho_check_in" and at > start + timedelta(minutes=grace):
        labels.append({"ma": "chua_check_in", "ten": "Chưa check-in (quá giờ ca)"})
    if result["phut_di_tre"]:
        labels.append({"ma": "di_tre", "ten": f"Đi trễ {result['phut_di_tre']} phút"})
    if result["phut_ve_som"]:
        labels.append({"ma": "ve_som", "ten": f"Về sớm {result['phut_ve_som']} phút"})
    if status == "chua_check_out":
        labels.append({"ma": "chua_check_out", "ten": "Chưa check-out"})
    if result["phut_vuot_ca"]:
        if result["phut_vuot_ca_duyet"]:
            labels.append({"ma": "vuot_ca", "ten": f"Vượt ca {result['phut_vuot_ca']} phút · duyệt {result['phut_vuot_ca_duyet']} phút"})
        else:
            labels.append({"ma": "vuot_ca", "ten": f"Vượt ca {result['phut_vuot_ca']} phút · chờ duyệt"})
    if not get("da_xac_minh_co"):
        if get("ngoai_vi_tri"):
            result["co"].append("ngoai_vi_tri")
            labels.append({"ma": "ngoai_vi_tri", "ten": "Ngoài vị trí"})
        if get("khong_dinh_vi"):
            result["co"].append("khong_dinh_vi")
            labels.append({"ma": "khong_dinh_vi", "ten": "Không có định vị"})
        if get("thiet_bi_trung"):
            result["co"].append("thiet_bi_trung")
            labels.append({"ma": "thiet_bi_trung", "ten": "Thiết bị trùng"})
    if get("da_dieu_chinh"):
        labels.append({"ma": "da_dieu_chinh", "ten": "Đã điều chỉnh"})
    if get("mien_phat"):
        labels.append({"ma": "mien_phat", "ten": "Miễn phạt"})
    if pending:
        labels.append({"ma": "cho_duyet", "ten": "Chờ duyệt"})
    if gio_vao and not pc.da_huy and not result["phut_di_tre"] and not result["phut_ve_som"] \
            and status != "chua_check_out":
        result["dung_gio"] = True
        labels.insert(0, {"ma": "dung_gio", "ten": "Đúng giờ"})
    result["nhan"] = labels
    # Giờ đã xác nhận: chỉ ca đã đủ giờ vào - ra mới được tính (EX-02)
    if status not in ("hoan_thanh", "da_huy"):
        result["so_gio_lam"] = 0.0
    return result


def save_evaluation(pc: PhanCongCa, cc: ChamCong, cfg: dict, at: Optional[datetime] = None) -> dict:
    """Lưu kết quả đối chiếu vào bản ghi chấm công (đầu vào cho tính lương Sprint 6)"""
    ev = evaluate(pc, cc, cfg, at)
    cc.phut_di_tre = ev["phut_di_tre"]
    cc.phut_ve_som = ev["phut_ve_som"]
    cc.phut_vuot_ca = ev["phut_vuot_ca"]
    cc.tong_gio_lam = ev["so_gio_lam"] if cc.check_out_lan_1 else None
    cc.trang_thai = ev["trang_thai"]
    if pc.ngay_lam:
        cc.thang = pc.ngay_lam.strftime("%Y-%m")
        cc.nam = pc.ngay_lam.year
    return ev


def preview_record(cc: Optional[ChamCong], **changes) -> SimpleNamespace:
    """Bản nháp của bản ghi chấm công với giá trị mới, dùng để xem trước mà không sửa dữ liệu"""
    fields = ["check_in_lan_1", "check_out_lan_1", "an_han_ap_dung", "phut_vuot_ca_duyet", "ngoai_vi_tri",
              "khong_dinh_vi", "thiet_bi_trung", "da_xac_minh_co", "da_dieu_chinh", "mien_phat"]
    data = {f: getattr(cc, f, None) if cc is not None else None for f in fields}
    data.update(changes)
    return SimpleNamespace(**data)


# ---------- Truy vấn danh sách ----------

def published_assignments(db: Session, tu_ngay: date, den_ngay: date, ma_nv: Optional[int] = None) -> List[PhanCongCa]:
    """BR-02, BR-03: chỉ các ca thuộc lịch tuần đã công bố mới được chấm công và đối chiếu"""
    q = db.query(PhanCongCa).join(LichCaTuan, PhanCongCa.ma_lich_tuan == LichCaTuan.id).filter(
        LichCaTuan.trang_thai == "da_cong_bo",
        PhanCongCa.ngay_lam >= tu_ngay,
        PhanCongCa.ngay_lam <= den_ngay
    )
    if ma_nv is not None:
        q = q.filter(PhanCongCa.ma_nv == ma_nv)
    items = q.all()
    items.sort(key=lambda pc: (pc.ngay_lam, pc.loai_ca.gio_bat_dau or time(0, 0), pc.id))
    return items


def today_assignments(db: Session, ma_nv: int, cfg: dict, at: Optional[datetime] = None) -> List[PhanCongCa]:
    """Ca hôm nay, kèm ca xuyên đêm bắt đầu từ hôm qua mà vẫn còn hạn check-out (EX-14)"""
    at = at or now()
    today = at.date()
    items = []
    for pc in published_assignments(db, today - timedelta(days=1), today, ma_nv):
        if pc.ngay_lam == today:
            items.append(pc)
        else:
            deadline = checkout_deadline(pc, cfg)
            if deadline and deadline >= at:
                items.append(pc)
    return items


def records_for(db: Session, assignments: List[PhanCongCa]) -> Dict[int, ChamCong]:
    if not assignments:
        return {}
    ids = [pc.id for pc in assignments]
    return {cc.ma_phan_cong: cc for cc in db.query(ChamCong).filter(ChamCong.ma_phan_cong.in_(ids)).all()}


def open_requests_for(db: Session, assignment_ids: List[int]) -> Dict[int, YeuCauChamCong]:
    if not assignment_ids:
        return {}
    items = db.query(YeuCauChamCong).filter(
        YeuCauChamCong.ma_phan_cong.in_(assignment_ids),
        YeuCauChamCong.trang_thai.in_(["cho_duyet", "can_bo_sung"])
    ).all()
    return {yc.ma_phan_cong: yc for yc in items}


# ---------- Nhật ký (BR-06) ----------

def snapshot(cc: Optional[ChamCong], pc: Optional[PhanCongCa] = None) -> dict:
    if cc is None:
        return {"vao": None, "ra": None}
    fmt = lambda v: v.strftime("%Y-%m-%d %H:%M") if v else None
    data = {"vao": fmt(cc.check_in_lan_1), "ra": fmt(cc.check_out_lan_1)}
    if cc.tong_gio_lam is not None:
        data["gio"] = float(cc.tong_gio_lam)
    if cc.trang_thai:
        data["trang_thai"] = cc.trang_thai
    if pc is not None:
        data["ca"] = pc.id
    return data


def write_log(db: Session, pc_id: int, cc: Optional[ChamCong], hanh_dong: str, truoc: Optional[dict],
              sau: Optional[dict], ly_do: Optional[str], nguoi_thuc_hien: Optional[int],
              nguoi_yeu_cau: Optional[int] = None, ma_yeu_cau: Optional[int] = None, tu_duyet: bool = False):
    db.add(NhatKyChamCong(
        ma_phan_cong=pc_id, ma_cham_cong=cc.id if cc is not None else None, ma_yeu_cau=ma_yeu_cau,
        hanh_dong=hanh_dong,
        truoc=json.dumps(truoc, ensure_ascii=False) if truoc is not None else None,
        sau=json.dumps(sau, ensure_ascii=False) if sau is not None else None,
        ly_do=ly_do, nguoi_yeu_cau=nguoi_yeu_cau, nguoi_thuc_hien=nguoi_thuc_hien,
        tu_duyet=tu_duyet, thoi_gian=now()
    ))


# ---------- Kỳ đã chốt (BR-04) ----------

def locked_period(db: Session, ngay: date) -> Optional[KyCongDaChot]:
    return db.query(KyCongDaChot).filter(KyCongDaChot.tu_ngay <= ngay, KyCongDaChot.den_ngay >= ngay).first()


def apply_time_change(db: Session, pc: PhanCongCa, cc: Optional[ChamCong], cfg: dict, *,
                      gio_vao=None, gio_ra=None, set_vao=False, set_ra=False, target: Optional[PhanCongCa] = None,
                      ly_do: str, actor_id: int, hanh_dong: str, requester_id: Optional[int] = None,
                      request_id: Optional[int] = None, tu_duyet: bool = False) -> Tuple[str, object]:
    """
    Áp dụng thay đổi giờ vào/ra (hoặc chuyển sang ca đúng) cho một ca, có ghi nhật ký.
    - Kỳ chưa chốt: cập nhật giờ hiệu lực, giữ nguyên giờ gốc, gắn nhãn "Đã điều chỉnh".
    - Kỳ đã chốt: không sửa bản ghi, tạo bản ghi phụ lục áp vào kỳ sau (BR-04, EX-19).
    Trả về ("cap_nhat", ChamCong) hoặc ("phu_luc", BanGhiDieuChinh).
    """
    at = now()
    new_vao = gio_vao if set_vao else (cc.check_in_lan_1 if cc else None)
    new_ra = gio_ra if set_ra else (cc.check_out_lan_1 if cc else None)
    dest = target or pc

    ky = locked_period(db, pc.ngay_lam)
    if ky:
        old_hours = evaluate(pc, cc, cfg, at)["so_gio_lam"]
        new_hours = evaluate(dest, preview_record(cc, check_in_lan_1=new_vao, check_out_lan_1=new_ra), cfg, at)["so_gio_lam"]
        adj = BanGhiDieuChinh(
            ma_phan_cong=pc.id, ma_nv=pc.ma_nv, ma_ky_goc=ky.id, ap_dung_tu_ngay=ky.den_ngay + timedelta(days=1),
            gio_vao_moi=new_vao, gio_ra_moi=new_ra, so_gio_chenh=round(new_hours - old_hours, 2),
            ly_do=ly_do, ma_yeu_cau=request_id, nguoi_tao=actor_id
        )
        db.add(adj)
        write_log(db, pc.id, cc, hanh_dong + "_ky_sau", snapshot(cc),
                  {"vao": new_vao.strftime("%Y-%m-%d %H:%M") if new_vao else None,
                   "ra": new_ra.strftime("%Y-%m-%d %H:%M") if new_ra else None,
                   "gio_chenh": float(adj.so_gio_chenh), "ap_dung_tu": adj.ap_dung_tu_ngay.isoformat()},
                  ly_do, actor_id, requester_id, request_id, tu_duyet)
        return "phu_luc", adj

    before = snapshot(cc, pc)
    if cc is None:
        cc = ChamCong(ma_phan_cong=dest.id, ngoai_vi_tri=False, khong_dinh_vi=False, thiet_bi_trung=False,
                      an_han_ap_dung=cfg["an_han_phut"])
        db.add(cc)
    if target is not None:
        cc.ma_phan_cong = target.id
        pc.bat_dau_thuc_te = pc.ket_thuc_thuc_te = None
    cc.check_in_lan_1 = new_vao
    cc.check_out_lan_1 = new_ra
    if cc.an_han_ap_dung is None:
        cc.an_han_ap_dung = cfg["an_han_phut"]
    cc.da_dieu_chinh = True
    cc.nguoi_xu_ly = actor_id
    cc.ngay_xu_ly = at
    cc.ghi_chu_quan_ly = ly_do[:255]
    dest.bat_dau_thuc_te, dest.ket_thuc_thuc_te = new_vao, new_ra
    db.flush()
    save_evaluation(dest, cc, cfg, at)
    write_log(db, pc.id, cc, hanh_dong, before, snapshot(cc, dest), ly_do, actor_id, requester_id, request_id, tu_duyet)
    return "cap_nhat", cc


# ---------- Thông báo ----------

def notify_staff(db: Session, ma_nv: int, tieu_de: str, noi_dung: str = None, lien_ket: str = None):
    shift_svc.notify(db, ma_nv, tieu_de, noi_dung, lien_ket)


def manager_accounts(db: Session) -> List[TaiKhoan]:
    return db.query(TaiKhoan).join(VaiTro, TaiKhoan.ma_vai_tro == VaiTro.id).filter(
        VaiTro.ten_vai_tro.in_(ADMIN_ROLES), TaiKhoan.is_active == True
    ).all()


def notify_managers(db: Session, tieu_de: str, noi_dung: str = None, lien_ket: str = None,
                    exclude_account: Optional[int] = None):
    for tk in manager_accounts(db):
        if tk.ma_nv and tk.id != exclude_account:
            shift_svc.notify(db, tk.ma_nv, tieu_de, noi_dung, lien_ket)


def role_of(user: TaiKhoan) -> str:
    return user.vai_tro.ten_vai_tro if user.vai_tro else "Staff"


def is_sole_manager(db: Session, user: TaiKhoan) -> bool:
    """Quy tắc 7: quán chỉ có một người quản trị thì được tự điều chỉnh, ghi "Tự duyệt" vào nhật ký"""
    return all(tk.id == user.id for tk in manager_accounts(db))


# ---------- Hạn xử lý yêu cầu (Quy tắc 2, 8) ----------

def payroll_cutoff(ngay: date) -> datetime:
    """Ngày chốt kỳ lương mặc định: cuối tháng của ca (Sprint 6 có thể đổi theo kỳ lương thực tế)"""
    last = calendar.monthrange(ngay.year, ngay.month)[1]
    return datetime.combine(date(ngay.year, ngay.month, last), time(23, 59))


def request_deadline(pc: PhanCongCa, cfg: dict, created: datetime) -> datetime:
    by_days = created + timedelta(days=cfg["han_xu_ly_ngay"])
    cutoff = payroll_cutoff(pc.ngay_lam)
    return min(by_days, cutoff) if cutoff > created else by_days


def submit_deadline(pc: PhanCongCa, cfg: dict) -> Optional[datetime]:
    interval = interval_of(pc)
    if not interval:
        return None
    return interval[1] + timedelta(hours=cfg["han_gui_yeu_cau_gio"])


def run_request_maintenance(db: Session, cfg: dict, at: Optional[datetime] = None):
    """
    - Yêu cầu "Cần bổ sung" quá hạn bổ sung (bằng hạn gửi) thì chuyển "Hết hạn" và báo nhân viên.
    - Yêu cầu "Chờ duyệt" còn dưới 24 giờ tới hạn xử lý thì nhắc Quản lý một lần.
    """
    at = at or now()
    changed = False
    limit = timedelta(hours=cfg["han_gui_yeu_cau_gio"])
    for yc in db.query(YeuCauChamCong).filter(YeuCauChamCong.trang_thai == "can_bo_sung").all():
        if yc.ngay_yeu_cau_bo_sung and yc.ngay_yeu_cau_bo_sung + limit < at:
            yc.trang_thai = "het_han"
            yc.ngay_cap_nhat = at
            notify_staff(db, yc.ma_nv, "Yêu cầu bù/sửa công đã hết hạn",
                         "Bạn chưa bổ sung thông tin đúng hạn. Vui lòng liên hệ Quản lý để điều chỉnh trực tiếp.",
                         "/attendance-history?tab=requests")
            changed = True
    for yc in db.query(YeuCauChamCong).filter(YeuCauChamCong.trang_thai == "cho_duyet",
                                              YeuCauChamCong.da_nhac == False).all():
        if yc.han_xu_ly and yc.han_xu_ly - at <= timedelta(hours=24):
            yc.da_nhac = True
            nv = yc.nhan_vien
            notify_managers(db, "Yêu cầu bù/sửa công sắp quá hạn xử lý",
                            f"Yêu cầu của {nv.ho_ten if nv else ''} cần xử lý trước {yc.han_xu_ly.strftime('%H:%M %d/%m')}.",
                            f"/attendance-requests?id={yc.id}")
            changed = True
    if changed:
        db.commit()
