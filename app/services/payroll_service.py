"""
Sprint 6: Tự động tính lương (FR-12)
Lương = (Tổng giờ làm thực tế × Đơn giá/giờ × Hệ số ca) + Thưởng - Phạt
- Giờ làm lấy từ chấm công Sprint 5: chỉ ca đã đủ vào/ra (hoặc ca hủy có tính công), vượt ca chỉ phần đã duyệt (BR-09)
- Hệ số ca: hệ số của loại ca (VD ca đêm × 1.2) hoặc hệ số ngày lễ (VD × 2.0), lấy mức cao hơn
- Phạt trễ/sớm theo số phút hoặc mức cố định mỗi lần; ca được Quản lý "Miễn phạt" thì không trừ
- Thưởng chuyên cần khi cả kỳ không trễ, sớm, vắng
- Bản ghi điều chỉnh của kỳ công đã chốt (BR-04) được cộng/trừ vào kỳ lương kế tiếp
- Quản lý thêm phụ cấp/khấu trừ thủ công khi kỳ còn nháp; chốt kỳ thì khóa phiếu lương và kỳ công
"""
import json
from datetime import date, datetime
from decimal import Decimal
from typing import Dict, List, Optional, Tuple

from sqlalchemy.orm import Session

from app.config import settings
from app.models.attendance import CauHinhChamCong, BanGhiDieuChinh, KyCongDaChot, YeuCauChamCong
from app.models.employee import NhanVien, HopDong
from app.models.payroll import KyLuong, PhieuLuong, MucThuChi, NgayLe
from app.models.shift import LoaiCa, PhanCongCa
from app.services import attendance_service as att
from app.services import shift_service as shift_svc

ITEM_TYPES = {
    "thuong": "Thưởng",
    "phu_cap": "Phụ cấp",
    "phat": "Phạt",
    "khau_tru": "Khấu trừ",
    "dieu_chinh_cong": "Điều chỉnh công kỳ trước",
}
PLUS_TYPES = ("thuong", "phu_cap")
MINUS_TYPES = ("phat", "khau_tru")
MANUAL_TYPES = ("thuong", "phu_cap", "phat", "khau_tru")

PERIOD_TYPES = {"thang": "Tháng", "tuan": "Tuần", "tuy_chon": "Tùy chọn"}


def money(value) -> int:
    """Làm tròn tới đồng"""
    return int(Decimal(str(value or 0)).quantize(Decimal("1")))


def num(value, default=0.0) -> float:
    return float(value) if value is not None else default


# ---------- Cấu hình (FR-12) ----------

def get_payroll_config(db: Session) -> dict:
    cfg = dict(settings.PAYROLL_DEFAULTS)
    keys = list(cfg.keys())
    for row in db.query(CauHinhChamCong).filter(CauHinhChamCong.khoa.in_(keys)).all():
        if row.gia_tri is None:
            continue
        default = settings.PAYROLL_DEFAULTS[row.khoa]
        try:
            if isinstance(default, bool):
                cfg[row.khoa] = row.gia_tri.strip().lower() in ("1", "true", "co")
            elif isinstance(default, str):
                cfg[row.khoa] = row.gia_tri
            else:
                cfg[row.khoa] = type(default)(float(row.gia_tri)) if isinstance(default, int) else float(row.gia_tri)
        except ValueError:
            pass
    return cfg


def save_payroll_config(db: Session, values: dict, user_id: int):
    for key, value in values.items():
        if key not in settings.PAYROLL_DEFAULTS or value is None:
            continue
        row = db.query(CauHinhChamCong).filter(CauHinhChamCong.khoa == key).first()
        if not row:
            row = CauHinhChamCong(khoa=key)
            db.add(row)
        row.gia_tri = str(value)
        row.ngay_cap_nhat = datetime.utcnow()
        row.nguoi_cap_nhat = user_id


def shift_coefficient(lc: Optional[LoaiCa]) -> float:
    value = num(lc.he_so_luong, 1.0) if lc is not None else 1.0
    return value if value > 0 else 1.0


def holidays_between(db: Session, tu_ngay: date, den_ngay: date) -> Dict[date, NgayLe]:
    items = db.query(NgayLe).filter(NgayLe.ngay >= tu_ngay, NgayLe.ngay <= den_ngay).all()
    return {h.ngay: h for h in items}


def coefficient_for(pc: PhanCongCa, holidays: Dict[date, NgayLe]) -> Tuple[float, Optional[str]]:
    """Hệ số áp dụng cho ca: lấy mức cao hơn giữa hệ số ca và hệ số ngày lễ (không nhân chồng)"""
    coef = shift_coefficient(pc.loai_ca)
    holiday = holidays.get(pc.ngay_lam)
    if holiday and num(holiday.he_so, 1.0) > coef:
        return num(holiday.he_so, 1.0), holiday.ten
    return coef, (holiday.ten if holiday else None)


# ---------- Hợp đồng và đơn giá ----------

def active_contract(db: Session, ma_nv: int, tu_ngay: date, den_ngay: date) -> Optional[HopDong]:
    """Hợp đồng còn hiệu lực trong kỳ (không tính hợp đồng đã hủy), lấy hợp đồng bắt đầu muộn nhất"""
    items = db.query(HopDong).filter(HopDong.ma_nhan_vien == ma_nv, HopDong.trang_thai != "da_huy").all()
    items = [h for h in items
             if (h.ngay_bat_dau is None or h.ngay_bat_dau <= den_ngay)
             and (h.ngay_ket_thuc is None or h.ngay_ket_thuc >= tu_ngay)]
    items.sort(key=lambda h: (h.ngay_bat_dau or date.min, h.id), reverse=True)
    return items[0] if items else None


def hourly_rate(contract: Optional[HopDong], cfg: dict) -> Tuple[Optional[str], float]:
    """
    Hợp đồng ghi "VNĐ / giờ hoặc / ca" (Sprint 3). Mức từ ngưỡng lương tháng trở lên được hiểu là lương tháng
    và quy đổi ra đơn giá giờ = lương tháng / giờ chuẩn tháng; mức thấp hơn là đơn giá giờ.
    """
    if contract is None or contract.muc_luong is None:
        return None, 0.0
    salary = float(contract.muc_luong)
    if salary >= cfg["nguong_luong_thang"]:
        hours = cfg["gio_chuan_thang"] or 208
        return "thang", round(salary / hours, 2)
    return "gio", salary


def penalty_amount(minutes: int, cfg: dict) -> int:
    if minutes <= 0:
        return 0
    if cfg["cach_phat"] == "co_dinh":
        return money(cfg["phat_moi_lan"])
    return money(minutes * cfg["phat_moi_phut"])


# ---------- Kỳ lương ----------

def period_name(loai_ky: str, tu_ngay: date, den_ngay: date) -> str:
    if loai_ky == "thang":
        return f"Lương tháng {tu_ngay.month:02d}/{tu_ngay.year}"
    if loai_ky == "tuan":
        return f"Lương tuần {tu_ngay:%d/%m} - {den_ngay:%d/%m/%Y}"
    return f"Lương {tu_ngay:%d/%m} - {den_ngay:%d/%m/%Y}"


def overlapping_period(db: Session, tu_ngay: date, den_ngay: date, exclude_id: Optional[int] = None) -> Optional[KyLuong]:
    q = db.query(KyLuong).filter(KyLuong.tu_ngay <= den_ngay, KyLuong.den_ngay >= tu_ngay)
    if exclude_id:
        q = q.filter(KyLuong.id != exclude_id)
    return q.first()


def pending_requests(db: Session, tu_ngay: date, den_ngay: date) -> int:
    return db.query(YeuCauChamCong).join(PhanCongCa, YeuCauChamCong.ma_phan_cong == PhanCongCa.id).filter(
        YeuCauChamCong.trang_thai.in_(["cho_duyet", "can_bo_sung"]),
        PhanCongCa.ngay_lam >= tu_ngay, PhanCongCa.ngay_lam <= den_ngay
    ).count()


def adjustments_for(db: Session, ky: KyLuong) -> List[BanGhiDieuChinh]:
    """Bản ghi điều chỉnh áp vào kỳ này: đã tới ngày áp dụng và chưa được kỳ lương đã chốt nào tính"""
    return db.query(BanGhiDieuChinh).filter(
        BanGhiDieuChinh.ap_dung_tu_ngay <= ky.den_ngay,
        (BanGhiDieuChinh.ma_ky_luong == None) | (BanGhiDieuChinh.ma_ky_luong == ky.id)  # noqa: E711
    ).order_by(BanGhiDieuChinh.id).all()


def _shift_text(pc: PhanCongCa) -> str:
    return shift_svc.shift_label(pc.loai_ca) if pc.loai_ca else ""


def calculate_period(db: Session, ky: KyLuong, actor_id: Optional[int]) -> KyLuong:
    """Tính (hoặc tính lại) toàn bộ phiếu lương của kỳ nháp. Khoản thủ công được giữ nguyên."""
    cfg = get_payroll_config(db)
    att_cfg = att.get_config(db)
    at = att.now()
    assignments = att.published_assignments(db, ky.tu_ngay, ky.den_ngay)
    records = att.records_for(db, assignments)
    open_requests = att.open_requests_for(db, [pc.id for pc in assignments])
    holidays = holidays_between(db, ky.tu_ngay, ky.den_ngay)
    adjustments = adjustments_for(db, ky)
    if adjustments:
        # Ca gốc của bản ghi điều chỉnh nằm ở kỳ trước: lấy thêm ngày lễ của những ngày đó
        days = [pc.ngay_lam for pc in db.query(PhanCongCa).filter(
            PhanCongCa.id.in_([a.ma_phan_cong for a in adjustments])).all() if pc.ngay_lam]
        if days:
            holidays.update(holidays_between(db, min(days), max(days)))

    by_nv: Dict[int, List[PhanCongCa]] = {}
    for pc in assignments:
        by_nv.setdefault(pc.ma_nv, []).append(pc)
    adj_by_nv: Dict[int, List[BanGhiDieuChinh]] = {}
    for adj in adjustments:
        adj_by_nv.setdefault(adj.ma_nv, []).append(adj)

    existing = {p.ma_nv: p for p in ky.phieu_list}
    keep_manual = {nv for nv, p in existing.items() if any(m.nguon == "thu_cong" for m in p.muc_list)}
    nv_ids = set(by_nv) | set(adj_by_nv) | keep_manual
    for nv_id, phieu in list(existing.items()):
        if nv_id not in nv_ids:
            ky.phieu_list.remove(phieu)
            db.delete(phieu)

    for nv_id in sorted(nv_ids):
        phieu = existing.get(nv_id)
        if phieu is None:
            phieu = PhieuLuong(ma_nv=nv_id, trang_thai="nhap")
            ky.phieu_list.append(phieu)
        calculate_payslip(db, ky, phieu, by_nv.get(nv_id, []), adj_by_nv.get(nv_id, []), records, open_requests,
                          holidays, cfg, att_cfg, at)

    ky.cau_hinh = json.dumps(cfg, ensure_ascii=False)
    ky.ngay_tinh = at
    ky.nguoi_tinh = actor_id
    db.flush()
    return ky


def calculate_payslip(db: Session, ky: KyLuong, phieu: PhieuLuong, shifts: List[PhanCongCa],
                      adjustments: List[BanGhiDieuChinh], records, open_requests, holidays, cfg, att_cfg, at):
    nv = db.get(NhanVien, phieu.ma_nv)
    contract = active_contract(db, phieu.ma_nv, ky.tu_ngay, ky.den_ngay)
    loai_luong, rate = hourly_rate(contract, cfg)
    warnings: List[str] = []
    if contract is None:
        warnings.append("Chưa có hợp đồng còn hiệu lực trong kỳ nên đơn giá giờ = 0")
    elif contract.muc_luong is None:
        warnings.append("Hợp đồng chưa ghi mức lương nên đơn giá giờ = 0")

    # Xóa khoản tự động cũ, giữ khoản thủ công
    for item in [m for m in phieu.muc_list if m.nguon != "thu_cong"]:
        phieu.muc_list.remove(item)
        db.delete(item)

    def add_item(loai, so_tien, ly_do, pc=None, so_gio=None, ngay=None):
        phieu.muc_list.append(MucThuChi(
            ma_nhan_vien=phieu.ma_nv, loai=loai, so_tien=so_tien, ly_do=ly_do[:255], nguon="tu_dong",
            ma_phan_cong=pc.id if pc else None, ngay_lam=ngay or (pc.ngay_lam if pc else None),
            so_gio=so_gio, trang_thai="nhap", da_tao=at
        ))

    lines = []
    so_ca = so_tre = so_som = phut_tre = phut_som = so_vang = thieu_ra = 0
    tong_gio = gio_quy_doi = 0.0
    luong_gio = 0
    violations = 0
    unfinished = pending_ot = 0
    for pc in shifts:
        cc = records.get(pc.id)
        ev = att.evaluate(pc, cc, att_cfg, at)
        status = ev["trang_thai"]
        hours = ev["so_gio_lam"]
        coef, holiday_name = coefficient_for(pc, holidays)
        amount = money(hours * rate * coef)
        waived = bool(cc and cc.mien_phat)
        late, early = ev["phut_di_tre"], ev["phut_ve_som"]
        penalty = 0
        day = pc.ngay_lam.strftime("%d/%m")
        if late:
            so_tre += 1
            phut_tre += late
            if not waived:
                violations += 1
                fee = penalty_amount(late, cfg)
                if fee:
                    penalty += fee
                    add_item("phat", fee, f"Đi trễ {late} phút ngày {day}", pc)
        if early:
            so_som += 1
            phut_som += early
            if not waived:
                violations += 1
                fee = penalty_amount(early, cfg)
                if fee:
                    penalty += fee
                    add_item("phat", fee, f"Về sớm {early} phút ngày {day}", pc)
        if status == "vang_mat":
            so_vang += 1
            if not waived:
                violations += 1
                fee = money(cfg["phat_vang_moi_lan"])
                if fee:
                    penalty += fee
                    add_item("phat", fee, f"Vắng không phép ngày {day}", pc)
        if status == "chua_check_out":
            thieu_ra += 1
        if status in ("chua_den_ca", "cho_check_in", "dang_lam"):
            unfinished += 1
        if ev["phut_vuot_ca"] > ev["phut_vuot_ca_duyet"]:
            pending_ot += 1
        if status == "hoan_thanh" or (status == "da_huy" and hours > 0):
            so_ca += 1
        tong_gio += hours
        gio_quy_doi += hours * coef
        luong_gio += amount
        lines.append({
            "ma_phan_cong": pc.id, "ngay": pc.ngay_lam.isoformat(), "ca": _shift_text(pc),
            "vao": cc.check_in_lan_1.strftime("%H:%M") if cc and cc.check_in_lan_1 else None,
            "ra": cc.check_out_lan_1.strftime("%H:%M") if cc and cc.check_out_lan_1 else None,
            "trang_thai": status, "ten_trang_thai": att.STATUS_LABELS[status],
            "so_gio": hours, "he_so": coef, "ngay_le": holiday_name, "don_gia": rate, "thanh_tien": amount,
            "phut_tre": late, "phut_som": early, "phut_vuot_ca_duyet": ev["phut_vuot_ca_duyet"],
            "mien_phat": waived, "da_dieu_chinh": bool(cc and cc.da_dieu_chinh), "tien_phat": penalty,
        })

    # Điều chỉnh công của kỳ đã chốt trước đó (BR-04)
    gio_dc = 0.0
    for adj in adjustments:
        pc = db.get(PhanCongCa, adj.ma_phan_cong)
        coef, _ = coefficient_for(pc, holidays) if pc else (1.0, None)
        delta = num(adj.so_gio_chenh)
        if not delta:
            continue
        amount = money(delta * rate * coef)
        gio_dc += delta
        luong_gio += amount
        add_item("dieu_chinh_cong", amount,
                 f"Điều chỉnh công ca {pc.ngay_lam:%d/%m} ({delta:+g} giờ × hệ số {coef:g}): {adj.ly_do}" if pc
                 else f"Điều chỉnh công ({delta:+g} giờ): {adj.ly_do}", pc, round(delta, 2))

    # Thưởng chuyên cần
    bonus = money(cfg["thuong_chuyen_can"])
    apply_bonus = ky.loai_ky == "thang" or cfg["chuyen_can_ky_tuan"]
    if bonus and apply_bonus and so_ca >= cfg["chuyen_can_so_ca_toi_thieu"] and violations == 0 and thieu_ra == 0:
        add_item("thuong", bonus, "Thưởng chuyên cần: không đi trễ, về sớm, vắng trong kỳ")

    if thieu_ra:
        warnings.append(f"{thieu_ra} ca chưa check-out nên chưa được tính giờ")
    if unfinished:
        warnings.append(f"{unfinished} ca chưa kết thúc hoặc chưa chấm công xong")
    if pending_ot:
        warnings.append(f"{pending_ot} ca có giờ vượt ca chưa duyệt (chưa tính vào lương, BR-09)")
    pending = sum(1 for pc in shifts if pc.id in open_requests)
    if pending:
        warnings.append(f"{pending} yêu cầu bù/sửa công đang chờ duyệt")

    db.flush()
    plus = sum(money(m.so_tien) for m in phieu.muc_list if m.loai in PLUS_TYPES)
    minus = sum(money(m.so_tien) for m in phieu.muc_list if m.loai in MINUS_TYPES)

    phieu.ma_hop_dong = contract.id if contract else None
    phieu.muc_luong_hop_dong = contract.muc_luong if contract else None
    phieu.loai_luong = loai_luong
    phieu.don_gia_gio = rate
    phieu.so_ca = so_ca
    phieu.tong_gio = round(tong_gio, 2)
    phieu.gio_quy_doi = round(gio_quy_doi, 2)
    phieu.gio_dieu_chinh = round(gio_dc, 2)
    phieu.so_lan_tre, phieu.so_lan_som = so_tre, so_som
    phieu.phut_tre, phieu.phut_som = phut_tre, phut_som
    phieu.so_vang = so_vang
    phieu.so_ca_thieu_ra = thieu_ra
    phieu.luong_co_ban = luong_gio
    phieu.tien_thuong = plus
    phieu.tien_phat = minus
    phieu.tong_thu_nhap = luong_gio + plus
    phieu.thanh_tien = luong_gio + plus - minus
    phieu.cong_huong = round(gio_quy_doi + gio_dc, 2)
    phieu.thang, phieu.nam = ky.den_ngay.month, ky.den_ngay.year
    if phieu.thanh_tien < 0:
        warnings.append("Thực lãnh âm: kiểm tra lại các khoản phạt/khấu trừ")
    if nv and (nv.is_deleted or nv.trang_thai == "da_nghi"):
        warnings.append("Nhân viên đã nghỉ việc, vẫn tính lương cho các ca đã làm (BR-05)")
    phieu.chi_tiet = json.dumps(lines, ensure_ascii=False)
    phieu.canh_bao = json.dumps(warnings, ensure_ascii=False)
    phieu.ngay_tinh = at


def recompute_totals(phieu: PhieuLuong):
    """Cập nhật lại tổng sau khi thêm/xóa khoản thủ công (không tính lại giờ công)"""
    plus = sum(money(m.so_tien) for m in phieu.muc_list if m.loai in PLUS_TYPES)
    minus = sum(money(m.so_tien) for m in phieu.muc_list if m.loai in MINUS_TYPES)
    base = money(phieu.luong_co_ban)
    phieu.tien_thuong = plus
    phieu.tien_phat = minus
    phieu.tong_thu_nhap = base + plus
    phieu.thanh_tien = base + plus - minus


def period_warnings(db: Session, ky: KyLuong) -> List[str]:
    """Các điểm cần xem trước khi chốt (Quy tắc 9 của FR-11A và rủi ro sai công thức lương)"""
    if ky.trang_thai != "nhap":
        return []
    items = []
    at = att.now()
    if at.date() <= ky.den_ngay:
        items.append(f"Kỳ lương chưa kết thúc (đến hết {ky.den_ngay:%d/%m/%Y}), số liệu còn thay đổi")
    pending = pending_requests(db, ky.tu_ngay, ky.den_ngay)
    if pending:
        items.append(f"Còn {pending} yêu cầu bù/sửa công chờ duyệt trong kỳ")
    no_contract = sum(1 for p in ky.phieu_list if p.ma_hop_dong is None)
    if no_contract:
        items.append(f"{no_contract} nhân viên chưa có hợp đồng/mức lương nên lương = 0")
    missing = sum(p.so_ca_thieu_ra or 0 for p in ky.phieu_list)
    if missing:
        items.append(f"{missing} ca chưa check-out chưa được tính giờ")
    return items


def finalize_period(db: Session, ky: KyLuong, actor_id: int) -> Tuple[KyLuong, bool]:
    """
    Chốt kỳ lương: tính lại lần cuối, khóa phiếu lương, chốt kỳ công cùng khoảng ngày (BR-04),
    đánh dấu các bản ghi điều chỉnh đã được tính. Trả về (kỳ, có tạo kỳ công mới hay không).
    """
    calculate_period(db, ky, actor_id)
    at = att.now()
    covering = db.query(KyCongDaChot).filter(KyCongDaChot.tu_ngay <= ky.tu_ngay,
                                             KyCongDaChot.den_ngay >= ky.den_ngay).first()
    created = False
    if covering is None:
        covering = KyCongDaChot(tu_ngay=ky.tu_ngay, den_ngay=ky.den_ngay, nguoi_chot=actor_id, ngay_chot=at,
                                ghi_chu=f"Chốt cùng {ky.ten_ky}"[:255])
        db.add(covering)
        db.flush()
        created = True
    ky.ma_ky_cong = covering.id
    for adj in adjustments_for(db, ky):
        if any(p.ma_nv == adj.ma_nv for p in ky.phieu_list):
            adj.ma_ky_luong = ky.id
    ky.trang_thai = "da_chot"
    ky.ngay_chot = at
    ky.nguoi_chot = actor_id
    for phieu in ky.phieu_list:
        phieu.trang_thai = "da_chot"
        for item in phieu.muc_list:
            item.trang_thai = "da_chot"
        shift_svc.notify(db, phieu.ma_nv, "Đã có phiếu lương " + ky.ten_ky,
                         f"Thực lãnh: {money(phieu.thanh_tien):,} đ".replace(",", "."), f"/payslip?id={phieu.id}")
    return ky, created


def partial_attendance_lock(db: Session, tu_ngay: date, den_ngay: date) -> Optional[KyCongDaChot]:
    """Kỳ công đã chốt chồng một phần lên kỳ lương (không phủ trọn) thì không chốt được vì số liệu lệch nhau"""
    for k in db.query(KyCongDaChot).filter(KyCongDaChot.tu_ngay <= den_ngay, KyCongDaChot.den_ngay >= tu_ngay).all():
        if not (k.tu_ngay <= tu_ngay and k.den_ngay >= den_ngay):
            return k
    return None


def lines_of(phieu: PhieuLuong) -> List[dict]:
    try:
        return json.loads(phieu.chi_tiet or "[]")
    except ValueError:
        return []


def warnings_of(phieu: PhieuLuong) -> List[str]:
    try:
        return json.loads(phieu.canh_bao or "[]")
    except ValueError:
        return []
