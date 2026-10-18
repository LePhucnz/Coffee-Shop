"""
Sprint 6: Tự động tính lương và xuất báo cáo
- FR-12: tạo kỳ lương (tuần/tháng), tính lương từ chấm công, xem trước, điều chỉnh thủ công, chốt kỳ
- FR-13: xuất báo cáo tổng hợp toàn quán và phiếu lương cá nhân ra Excel (.xlsx) / PDF;
         nhân viên chỉ xem/tải phiếu lương của chính mình sau khi kỳ đã chốt
"""
import json
from datetime import date
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy.orm import Session

from app.api.attendance import account_names, forbid
from app.core.deps import get_current_user, require_roles
from app.database import get_db
from app.models.attendance import CauHinhChamCong
from app.models.employee import NhanVien
from app.models.payroll import KyLuong, PhieuLuong, MucThuChi, NgayLe
from app.models.shift import LoaiCa
from app.models.user import TaiKhoan, NhatKyHeThong
from app.config import settings
from app.schemas.payroll import (
    KyLuongCreate, ChotKyLuongRequest, MucPhieuLuongCreate, MucPhieuLuong, DongCaLuong,
    PhieuLuongTomTat, PhieuLuongChiTiet, TongKyLuong, KyLuongResponse, KyLuongChiTiet,
    HeSoCa, NgayLeSchema, CauHinhLuongSchema
)
from app.services import attendance_service as att
from app.services import payroll_service as svc
from app.services import shift_service as shift_svc
from app.services.excel_service import build_workbook
from app.services.pdf_service import build_pdf

router = APIRouter(prefix="/api/payroll", tags=["Tính lương & Báo cáo lương (Payroll)"])

ADMIN_ROLES = att.ADMIN_ROLES

XLSX_TYPE = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


# ---------- Tiện ích ----------

def is_manager(user: TaiKhoan) -> bool:
    return att.role_of(user) in ADMIN_ROLES


def log(db: Session, user: TaiKhoan, hanh_dong: str, ly_do: str):
    """NFR-05: mọi thao tác trên dữ liệu lương đều ghi nhật ký"""
    db.add(NhatKyHeThong(ma_tai_khoan=user.id, hanh_dong=hanh_dong, ly_do=ly_do, trang_thai="thanh_cong"))


def get_period(db: Session, ky_id: int) -> KyLuong:
    ky = db.query(KyLuong).filter(KyLuong.id == ky_id).first()
    if not ky:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Không tìm thấy kỳ lương")
    return ky


def ensure_draft(ky: KyLuong):
    if ky.trang_thai != "nhap":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
                            detail="Kỳ lương đã chốt, không sửa được nữa. Điều chỉnh công sẽ ghi sang kỳ sau (BR-04).")


def get_payslip(db: Session, phieu_id: int) -> PhieuLuong:
    phieu = db.query(PhieuLuong).filter(PhieuLuong.id == phieu_id, PhieuLuong.ma_ky_luong != None).first()  # noqa: E711
    if not phieu:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Không tìm thấy phiếu lương")
    return phieu


def ensure_can_view(db: Session, user: TaiKhoan, phieu: PhieuLuong):
    """FR-13: nhân viên chỉ xem phiếu của mình, và chỉ khi kỳ đã chốt"""
    if is_manager(user):
        return
    if not user.ma_nv or phieu.ma_nv != user.ma_nv:
        forbid(db, user, "Bạn chỉ được xem phiếu lương của chính mình")
    if phieu.trang_thai != "da_chot":
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Phiếu lương chưa được chốt")


def ensure_can_edit(db: Session, user: TaiKhoan, phieu: PhieuLuong):
    """BR-08: không tự sửa phiếu lương của chính mình, trừ khi quán chỉ có một người quản trị"""
    if user.ma_nv and phieu.ma_nv == user.ma_nv and not att.is_sole_manager(db, user):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN,
                            detail="Không được tự điều chỉnh phiếu lương của chính mình. Hãy nhờ Chủ quán (Admin) xử lý.")


def map_item(m: MucThuChi, names) -> MucPhieuLuong:
    sign = 1 if m.loai in svc.PLUS_TYPES else -1 if m.loai in svc.MINUS_TYPES else 0
    if m.loai == "dieu_chinh_cong":
        sign = 1 if svc.money(m.so_tien) >= 0 else -1
    return MucPhieuLuong(
        id=m.id, loai=m.loai, ten_loai=svc.ITEM_TYPES.get(m.loai, m.loai), nguon=m.nguon or "tu_dong",
        so_tien=abs(svc.money(m.so_tien)), dau=sign, ly_do=m.ly_do, ngay_lam=m.ngay_lam,
        so_gio=float(m.so_gio) if m.so_gio is not None else None,
        nguoi_tao=names.get(m.nguoi_tao), da_tao=m.da_tao
    )


def map_payslip(phieu: PhieuLuong) -> dict:
    ky = phieu.ky_luong
    nv = phieu.nhan_vien
    return dict(
        id=phieu.id, ma_ky_luong=ky.id, ten_ky=ky.ten_ky, tu_ngay=ky.tu_ngay, den_ngay=ky.den_ngay,
        trang_thai=phieu.trang_thai or "nhap", ma_nv=phieu.ma_nv,
        ma_nhan_vien=nv.ma_nhan_vien if nv else None, ho_ten=nv.ho_ten if nv else None,
        ten_vi_tri=nv.vi_tri.ten_vi_tri if nv and nv.vi_tri else None,
        da_nghi_viec=bool(nv and (nv.is_deleted or nv.trang_thai == "da_nghi")),
        loai_luong=phieu.loai_luong,
        muc_luong_hop_dong=float(phieu.muc_luong_hop_dong) if phieu.muc_luong_hop_dong is not None else None,
        don_gia_gio=svc.num(phieu.don_gia_gio), so_ca=phieu.so_ca or 0, tong_gio=svc.num(phieu.tong_gio),
        gio_quy_doi=svc.num(phieu.gio_quy_doi), gio_dieu_chinh=svc.num(phieu.gio_dieu_chinh),
        so_lan_tre=phieu.so_lan_tre or 0, so_lan_som=phieu.so_lan_som or 0,
        phut_tre=phieu.phut_tre or 0, phut_som=phieu.phut_som or 0, so_vang=phieu.so_vang or 0,
        so_ca_thieu_ra=phieu.so_ca_thieu_ra or 0,
        luong_co_ban=svc.money(phieu.luong_co_ban), tien_thuong=svc.money(phieu.tien_thuong),
        tien_phat=svc.money(phieu.tien_phat), thuc_lanh=svc.money(phieu.thanh_tien),
        canh_bao=svc.warnings_of(phieu) if phieu.trang_thai != "da_chot" else []
    )


def payslip_detail(db: Session, phieu: PhieuLuong, user: TaiKhoan) -> PhieuLuongChiTiet:
    names = account_names(db, [m.nguoi_tao for m in phieu.muc_list])
    can_edit = is_manager(user) and phieu.trang_thai != "da_chot" and not (
        user.ma_nv and phieu.ma_nv == user.ma_nv and not att.is_sole_manager(db, user))
    return PhieuLuongChiTiet(
        **map_payslip(phieu),
        ca=[DongCaLuong(**line) for line in svc.lines_of(phieu)],
        khoan=[map_item(m, names) for m in phieu.muc_list],
        ngay_tinh=phieu.ngay_tinh, co_the_sua=can_edit
    )


def sort_key(p: PhieuLuong):
    nv = p.nhan_vien
    return (bool(nv and (nv.is_deleted or nv.trang_thai == "da_nghi")), (nv.ho_ten if nv else "") or "")


def totals(ky: KyLuong) -> TongKyLuong:
    items = ky.phieu_list
    return TongKyLuong(
        so_nhan_vien=len(items),
        tong_gio=round(sum(svc.num(p.tong_gio) + svc.num(p.gio_dieu_chinh) for p in items), 2),
        luong_co_ban=sum(svc.money(p.luong_co_ban) for p in items),
        tien_thuong=sum(svc.money(p.tien_thuong) for p in items),
        tien_phat=sum(svc.money(p.tien_phat) for p in items),
        thuc_lanh=sum(svc.money(p.thanh_tien) for p in items),
    )


def map_period(db: Session, ky: KyLuong) -> dict:
    names = account_names(db, [ky.nguoi_tinh, ky.nguoi_chot])
    return dict(
        id=ky.id, ten_ky=ky.ten_ky, loai_ky=ky.loai_ky, tu_ngay=ky.tu_ngay, den_ngay=ky.den_ngay,
        trang_thai=ky.trang_thai, ghi_chu=ky.ghi_chu, ngay_tao=ky.ngay_tao, ngay_tinh=ky.ngay_tinh,
        nguoi_tinh=names.get(ky.nguoi_tinh), ngay_chot=ky.ngay_chot, nguoi_chot=names.get(ky.nguoi_chot),
        tong=totals(ky)
    )


def period_detail(db: Session, ky: KyLuong) -> KyLuongChiTiet:
    return KyLuongChiTiet(
        **map_period(db, ky),
        phieu=[PhieuLuongTomTat(**map_payslip(p)) for p in sorted(ky.phieu_list, key=sort_key)],
        canh_bao=svc.period_warnings(db, ky),
        so_yeu_cau_cho_duyet=svc.pending_requests(db, ky.tu_ngay, ky.den_ngay) if ky.trang_thai == "nhap" else 0
    )


def vnd(value) -> str:
    return f"{svc.money(value):,}".replace(",", ".") + " đ"


def hours_text(value) -> str:
    return f"{svc.num(value):g}".replace(".", ",")


def file_response(content: bytes, media_type: str, name: str) -> Response:
    return Response(content=content, media_type=media_type,
                    headers={"Content-Disposition": f'attachment; filename="{name}"'})


# ---------- Cấu hình lương (FR-12: hệ số ca, phạt, thưởng) ----------

def settings_response(db: Session) -> CauHinhLuongSchema:
    cfg = svc.get_payroll_config(db)
    types = shift_svc.active_shift_types(db)
    last = db.query(CauHinhChamCong).filter(CauHinhChamCong.khoa.in_(list(settings.PAYROLL_DEFAULTS))) \
        .order_by(CauHinhChamCong.ngay_cap_nhat.desc()).first()
    return CauHinhLuongSchema(
        **cfg,
        he_so_ca=[HeSoCa(id=lc.id, ten_ca=lc.ten_ca or lc.ma_loai_ca,
                         khung_gio=f"{lc.gio_bat_dau:%H:%M}-{lc.gio_ket_thuc:%H:%M}" if lc.gio_bat_dau and lc.gio_ket_thuc else None,
                         he_so_luong=svc.shift_coefficient(lc)) for lc in types],
        ngay_le=[NgayLeSchema(id=h.id, ngay=h.ngay, ten=h.ten, he_so=svc.num(h.he_so, 2.0))
                 for h in db.query(NgayLe).order_by(NgayLe.ngay).all()],
        ngay_cap_nhat=last.ngay_cap_nhat if last else None
    )


@router.get("/settings", response_model=CauHinhLuongSchema)
def get_settings(current_user: TaiKhoan = Depends(require_roles(ADMIN_ROLES)), db: Session = Depends(get_db)):
    return settings_response(db)


@router.put("/settings", response_model=CauHinhLuongSchema)
def update_settings(data: CauHinhLuongSchema, current_user: TaiKhoan = Depends(require_roles(ADMIN_ROLES)),
                    db: Session = Depends(get_db)):
    """Thay đổi áp dụng từ lần tính lương kế tiếp; kỳ đã chốt giữ nguyên số liệu"""
    values = data.model_dump(exclude={"he_so_ca", "ngay_le", "ngay_cap_nhat"})
    svc.save_payroll_config(db, values, current_user.id)
    for item in data.he_so_ca:
        lc = db.query(LoaiCa).filter(LoaiCa.id == item.id).first()
        if lc:
            lc.he_so_luong = item.he_so_luong
    log(db, current_user, "cap_nhat_cau_hinh_luong", json.dumps(
        {**values, "he_so_ca": {h.id: h.he_so_luong for h in data.he_so_ca}}, ensure_ascii=False))
    db.commit()
    return settings_response(db)


@router.post("/holidays", response_model=CauHinhLuongSchema, status_code=status.HTTP_201_CREATED)
def add_holiday(data: NgayLeSchema, current_user: TaiKhoan = Depends(require_roles(ADMIN_ROLES)),
                db: Session = Depends(get_db)):
    if db.query(NgayLe).filter(NgayLe.ngay == data.ngay).first():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Ngày này đã có trong danh sách ngày lễ")
    db.add(NgayLe(ngay=data.ngay, ten=data.ten.strip(), he_so=data.he_so))
    log(db, current_user, "them_ngay_le", f"{data.ngay:%d/%m/%Y} {data.ten} × {data.he_so}")
    db.commit()
    return settings_response(db)


@router.delete("/holidays/{holiday_id}", response_model=CauHinhLuongSchema)
def delete_holiday(holiday_id: int, current_user: TaiKhoan = Depends(require_roles(ADMIN_ROLES)),
                   db: Session = Depends(get_db)):
    h = db.query(NgayLe).filter(NgayLe.id == holiday_id).first()
    if not h:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Không tìm thấy ngày lễ")
    log(db, current_user, "xoa_ngay_le", f"{h.ngay:%d/%m/%Y} {h.ten}")
    db.delete(h)
    db.commit()
    return settings_response(db)


# ---------- Kỳ lương (FR-12) ----------

@router.get("/periods", response_model=List[KyLuongResponse])
def list_periods(current_user: TaiKhoan = Depends(require_roles(ADMIN_ROLES)), db: Session = Depends(get_db)):
    items = db.query(KyLuong).order_by(KyLuong.tu_ngay.desc(), KyLuong.id.desc()).all()
    return [KyLuongResponse(**map_period(db, k)) for k in items]


@router.post("/periods", response_model=KyLuongChiTiet, status_code=status.HTTP_201_CREATED)
def create_period(data: KyLuongCreate, current_user: TaiKhoan = Depends(require_roles(ADMIN_ROLES)),
                  db: Session = Depends(get_db)):
    """Tạo kỳ lương nháp và tính ngay để xem trước (preview)"""
    overlap = svc.overlapping_period(db, data.tu_ngay, data.den_ngay)
    if overlap:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
                            detail=f"Khoảng ngày trùng với kỳ \"{overlap.ten_ky}\" ({overlap.tu_ngay:%d/%m} - {overlap.den_ngay:%d/%m/%Y})")
    ky = KyLuong(ten_ky=(data.ten_ky or "").strip() or svc.period_name(data.loai_ky, data.tu_ngay, data.den_ngay),
                 loai_ky=data.loai_ky, tu_ngay=data.tu_ngay, den_ngay=data.den_ngay, ghi_chu=data.ghi_chu,
                 trang_thai="nhap", ngay_tao=att.now(), nguoi_tao=current_user.id)
    db.add(ky)
    db.flush()
    svc.calculate_period(db, ky, current_user.id)
    log(db, current_user, "tinh_luong", f"Tạo và tính {ky.ten_ky}")
    db.commit()
    return period_detail(db, ky)


@router.get("/periods/{ky_id}", response_model=KyLuongChiTiet)
def period_view(ky_id: int, current_user: TaiKhoan = Depends(require_roles(ADMIN_ROLES)), db: Session = Depends(get_db)):
    return period_detail(db, get_period(db, ky_id))


@router.post("/periods/{ky_id}/calculate", response_model=KyLuongChiTiet)
def recalculate(ky_id: int, current_user: TaiKhoan = Depends(require_roles(ADMIN_ROLES)), db: Session = Depends(get_db)):
    """Tính lại theo chấm công và cấu hình mới nhất; khoản thủ công được giữ"""
    ky = get_period(db, ky_id)
    ensure_draft(ky)
    svc.calculate_period(db, ky, current_user.id)
    log(db, current_user, "tinh_luong", f"Tính lại {ky.ten_ky}")
    db.commit()
    return period_detail(db, ky)


@router.delete("/periods/{ky_id}")
def delete_period(ky_id: int, current_user: TaiKhoan = Depends(require_roles(ADMIN_ROLES)), db: Session = Depends(get_db)):
    ky = get_period(db, ky_id)
    ensure_draft(ky)
    log(db, current_user, "xoa_ky_luong", ky.ten_ky)
    db.delete(ky)
    db.commit()
    return {"message": "Đã xóa kỳ lương nháp"}


@router.post("/periods/{ky_id}/finalize", response_model=KyLuongChiTiet)
def finalize(ky_id: int, data: ChotKyLuongRequest, current_user: TaiKhoan = Depends(require_roles(ADMIN_ROLES)),
             db: Session = Depends(get_db)):
    """
    Chốt kỳ lương: tính lại lần cuối, khóa phiếu lương, chốt luôn kỳ công cùng khoảng ngày (BR-04)
    và báo cho từng nhân viên. Còn yêu cầu chờ duyệt thì phải chọn chuyển sang kỳ sau (Quy tắc 9).
    """
    ky = get_period(db, ky_id)
    ensure_draft(ky)
    if att.now().date() <= ky.den_ngay:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
                            detail=f"Kỳ lương chưa kết thúc (đến hết {ky.den_ngay:%d/%m/%Y}) nên chưa chốt được")
    partial = svc.partial_attendance_lock(db, ky.tu_ngay, ky.den_ngay)
    if partial:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
                            detail=f"Kỳ công đã chốt {partial.tu_ngay:%d/%m} - {partial.den_ngay:%d/%m/%Y} lệch với kỳ lương. "
                                   "Hãy tạo kỳ lương khớp với kỳ công đã chốt.")
    pending = svc.pending_requests(db, ky.tu_ngay, ky.den_ngay)
    if pending and not data.chuyen_yeu_cau_sang_ky_sau:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT,
                            detail=f"Còn {pending} yêu cầu bù/sửa công chưa xử lý trong kỳ. "
                                   "Hãy \"Xử lý ngay\" hoặc chọn \"Chuyển sang kỳ sau dưới dạng điều chỉnh\".")
    svc.finalize_period(db, ky, current_user.id)
    log(db, current_user, "chot_ky_luong",
        f"{ky.ten_ky}: {len(ky.phieu_list)} phiếu, thực lãnh {svc.money(totals(ky).thuc_lanh)} đ"
        + (f", {pending} yêu cầu chuyển sang kỳ sau" if pending else ""))
    db.commit()
    return period_detail(db, ky)


# ---------- Phiếu lương ----------

@router.get("/payslips/me", response_model=List[PhieuLuongTomTat])
def my_payslips(current_user: TaiKhoan = Depends(get_current_user), db: Session = Depends(get_db)):
    """FR-13: nhân viên xem danh sách phiếu lương đã chốt của mình"""
    if not current_user.ma_nv:
        return []
    items = db.query(PhieuLuong).join(KyLuong, PhieuLuong.ma_ky_luong == KyLuong.id).filter(
        PhieuLuong.ma_nv == current_user.ma_nv, PhieuLuong.trang_thai == "da_chot"
    ).order_by(KyLuong.tu_ngay.desc()).all()
    return [PhieuLuongTomTat(**map_payslip(p)) for p in items]


@router.get("/payslips/{phieu_id}", response_model=PhieuLuongChiTiet)
def payslip_view(phieu_id: int, current_user: TaiKhoan = Depends(get_current_user), db: Session = Depends(get_db)):
    phieu = get_payslip(db, phieu_id)
    ensure_can_view(db, current_user, phieu)
    return payslip_detail(db, phieu, current_user)


@router.post("/payslips/{phieu_id}/items", response_model=PhieuLuongChiTiet, status_code=status.HTTP_201_CREATED)
def add_item(phieu_id: int, data: MucPhieuLuongCreate, current_user: TaiKhoan = Depends(require_roles(ADMIN_ROLES)),
             db: Session = Depends(get_db)):
    """FR-12: thêm phụ cấp đột xuất, thưởng, phạt hoặc khấu trừ thủ công trước khi chốt"""
    phieu = get_payslip(db, phieu_id)
    ensure_draft(phieu.ky_luong)
    ensure_can_edit(db, current_user, phieu)
    phieu.muc_list.append(MucThuChi(
        ma_nhan_vien=phieu.ma_nv, loai=data.loai, so_tien=data.so_tien, ly_do=data.ly_do.strip(), nguon="thu_cong",
        trang_thai="nhap", nguoi_tao=current_user.id, da_tao=att.now()
    ))
    db.flush()
    svc.recompute_totals(phieu)
    nv = phieu.nhan_vien
    log(db, current_user, "them_khoan_luong",
        f"{phieu.ky_luong.ten_ky} - {nv.ho_ten if nv else phieu.ma_nv}: {svc.ITEM_TYPES[data.loai]} {data.so_tien} đ ({data.ly_do})")
    db.commit()
    return payslip_detail(db, phieu, current_user)


@router.delete("/payslips/{phieu_id}/items/{item_id}", response_model=PhieuLuongChiTiet)
def delete_item(phieu_id: int, item_id: int, current_user: TaiKhoan = Depends(require_roles(ADMIN_ROLES)),
                db: Session = Depends(get_db)):
    phieu = get_payslip(db, phieu_id)
    ensure_draft(phieu.ky_luong)
    ensure_can_edit(db, current_user, phieu)
    item = next((m for m in phieu.muc_list if m.id == item_id), None)
    if not item:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Không tìm thấy khoản này")
    if item.nguon != "thu_cong":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
                            detail="Khoản do hệ thống tính không xóa được. Hãy miễn phạt ở màn chấm công hoặc thêm khoản bù trừ.")
    phieu.muc_list.remove(item)
    db.delete(item)
    db.flush()
    svc.recompute_totals(phieu)
    log(db, current_user, "xoa_khoan_luong", f"{phieu.ky_luong.ten_ky}: {item.loai} {svc.money(item.so_tien)} đ ({item.ly_do})")
    db.commit()
    return payslip_detail(db, phieu, current_user)


# ---------- Xuất báo cáo (FR-13) ----------

SUMMARY_HEADER = ["Mã NV", "Họ tên", "Vị trí", "Đơn giá/giờ", "Số ca", "Tổng giờ", "Giờ quy đổi (× hệ số)",
                  "Giờ điều chỉnh", "Lần trễ", "Lần sớm", "Phút trễ", "Phút sớm", "Vắng",
                  "Lương cơ bản", "Thưởng + phụ cấp", "Phạt + khấu trừ", "Thực lãnh"]


def summary_rows(ky: KyLuong) -> List[list]:
    rows = []
    for p in sorted(ky.phieu_list, key=sort_key):
        d = map_payslip(p)
        rows.append([d["ma_nhan_vien"], d["ho_ten"] + (" (đã nghỉ)" if d["da_nghi_viec"] else ""), d["ten_vi_tri"],
                     svc.money(d["don_gia_gio"]), d["so_ca"], d["tong_gio"], d["gio_quy_doi"], d["gio_dieu_chinh"],
                     d["so_lan_tre"], d["so_lan_som"], d["phut_tre"], d["phut_som"], d["so_vang"],
                     d["luong_co_ban"], d["tien_thuong"], d["tien_phat"], d["thuc_lanh"]])
    return rows


@router.get("/periods/{ky_id}/export")
def export_period(ky_id: int, dinh_dang: str = Query("xlsx", pattern="^(xlsx|pdf)$"),
                  current_user: TaiKhoan = Depends(require_roles(ADMIN_ROLES)), db: Session = Depends(get_db)):
    """Báo cáo tổng hợp toàn quán theo kỳ lương (đối soát chi phí nhân sự) kèm chi tiết từng nhân viên"""
    ky = get_period(db, ky_id)
    tong = totals(ky)
    rows = summary_rows(ky)
    state = "Đã chốt" if ky.trang_thai == "da_chot" else "Bản nháp (chưa chốt)"
    slug = f"bang-luong-{ky.tu_ngay:%Y%m%d}-{ky.den_ngay:%Y%m%d}"
    log(db, current_user, "xuat_bao_cao_luong", f"{ky.ten_ky} ({dinh_dang})")
    db.commit()
    if dinh_dang == "xlsx":
        total_row = ["", "TỔNG CỘNG", f"{tong.so_nhan_vien} nhân viên", "",
                     sum(r[4] for r in rows), tong.tong_gio, round(sum(r[6] for r in rows), 2),
                     round(sum(r[7] for r in rows), 2), sum(r[8] for r in rows), sum(r[9] for r in rows),
                     sum(r[10] for r in rows), sum(r[11] for r in rows), sum(r[12] for r in rows),
                     tong.luong_co_ban, tong.tien_thuong, tong.tien_phat, tong.thuc_lanh]
        detail_header = ["Mã NV", "Họ tên", "Ngày", "Ca", "Vào", "Ra", "Trạng thái", "Giờ công", "Hệ số",
                         "Ngày lễ", "Đơn giá/giờ", "Thành tiền", "Trễ (phút)", "Sớm (phút)", "Miễn phạt", "Tiền phạt"]
        detail_rows, item_rows = [], []
        for p in sorted(ky.phieu_list, key=sort_key):
            nv = p.nhan_vien
            for line in svc.lines_of(p):
                detail_rows.append([nv.ma_nhan_vien if nv else "", nv.ho_ten if nv else "",
                                    date.fromisoformat(line["ngay"]).strftime("%d/%m/%Y"), line["ca"],
                                    line["vao"] or "", line["ra"] or "", line["ten_trang_thai"], line["so_gio"],
                                    line["he_so"], line["ngay_le"] or "", svc.money(line["don_gia"]),
                                    line["thanh_tien"], line["phut_tre"], line["phut_som"],
                                    "Có" if line["mien_phat"] else "", line["tien_phat"]])
            for m in p.muc_list:
                sign = -1 if m.loai in svc.MINUS_TYPES else 1
                item_rows.append([nv.ma_nhan_vien if nv else "", nv.ho_ten if nv else "",
                                  svc.ITEM_TYPES.get(m.loai, m.loai), "Thủ công" if m.nguon == "thu_cong" else "Tự động",
                                  m.ngay_lam.strftime("%d/%m/%Y") if m.ngay_lam else "", m.ly_do or "",
                                  sign * svc.money(m.so_tien)])
        info = [["Kỳ lương", ky.ten_ky], ["Từ ngày", ky.tu_ngay.strftime("%d/%m/%Y")],
                ["Đến ngày", ky.den_ngay.strftime("%d/%m/%Y")], ["Trạng thái", state],
                ["Số nhân viên", tong.so_nhan_vien], ["Tổng giờ công", tong.tong_gio],
                ["Tổng lương cơ bản", tong.luong_co_ban], ["Tổng thưởng + phụ cấp", tong.tien_thuong],
                ["Tổng phạt + khấu trừ", tong.tien_phat], ["Tổng thực lãnh (chi phí nhân sự)", tong.thuc_lanh]]
        content = build_workbook([
            ("Tong hop", SUMMARY_HEADER, rows + [total_row], [len(rows) + 1]),
            ("Chi tiet ca", detail_header, detail_rows),
            ("Thuong phat", ["Mã NV", "Họ tên", "Loại", "Nguồn", "Ngày", "Nội dung", "Số tiền (+/-)"], item_rows),
            ("Thong tin ky", ["Mục", "Giá trị"], info),
        ])
        return file_response(content, XLSX_TYPE, slug + ".xlsx")

    pdf_rows = [[r[0], r[1], hours_text(r[5]) + (f" ({r[7]:+g})" if r[7] else ""), r[4],
                 f"{r[8]}/{r[9]}", r[12], vnd(r[13]), vnd(r[14]), vnd(r[15]), vnd(r[16])] for r in rows]
    pdf_rows.append(["", "Tổng cộng", hours_text(tong.tong_gio), sum(r[4] for r in rows), "", "",
                     vnd(tong.luong_co_ban), vnd(tong.tien_thuong), vnd(tong.tien_phat), vnd(tong.thuc_lanh)])
    content = build_pdf(
        "Báo cáo lương toàn quán", f"{ky.ten_ky} · {ky.tu_ngay:%d/%m/%Y} - {ky.den_ngay:%d/%m/%Y} · {state}",
        [("Số nhân viên", str(tong.so_nhan_vien)), ("Tổng giờ công", hours_text(tong.tong_gio) + " giờ"),
         ("Tổng lương cơ bản", vnd(tong.luong_co_ban)), ("Tổng thưởng + phụ cấp", vnd(tong.tien_thuong)),
         ("Tổng phạt + khấu trừ", vnd(tong.tien_phat)), ("Tổng thực lãnh", vnd(tong.thuc_lanh))],
        [{"tieu_de": "Bảng lương theo nhân viên",
          "header": ["Mã NV", "Họ tên", "Giờ công", "Số ca", "Trễ/Sớm (lần)", "Vắng", "Lương cơ bản",
                     "Thưởng + phụ cấp", "Phạt + khấu trừ", "Thực lãnh"],
          "rows": pdf_rows, "widths": [18, 46, 22, 14, 22, 14, 32, 32, 32, 32],
          "align_right": [2, 3, 5, 6, 7, 8, 9], "bold_last": True}],
        wide=True,
        notes=["Lương cơ bản = Giờ công × Đơn giá/giờ × Hệ số ca (kể cả giờ điều chỉnh từ kỳ trước).",
               "Thực lãnh = Lương cơ bản + Thưởng + Phụ cấp - Phạt - Khấu trừ."]
    )
    return file_response(content, "application/pdf", slug + ".pdf")


def payslip_files(phieu: PhieuLuong, dinh_dang: str) -> Response:
    d = map_payslip(phieu)
    lines = svc.lines_of(phieu)
    ky = phieu.ky_luong
    rate_text = vnd(d["don_gia_gio"]) + "/giờ"
    if d["loai_luong"] == "thang" and d["muc_luong_hop_dong"]:
        rate_text += f" (lương tháng {vnd(d['muc_luong_hop_dong'])})"
    slug = f"phieu-luong-{d['ma_nhan_vien'] or d['ma_nv']}-{ky.tu_ngay:%Y%m%d}-{ky.den_ngay:%Y%m%d}"
    summary = [("Tổng giờ làm", f"{hours_text(d['tong_gio'])} giờ" + (f" (điều chỉnh {d['gio_dieu_chinh']:+g})" if d["gio_dieu_chinh"] else "")),
               ("Số ca", str(d["so_ca"])),
               ("Số lần trễ / sớm", f"{d['so_lan_tre']} / {d['so_lan_som']} ({d['phut_tre']} / {d['phut_som']} phút)"),
               ("Số ca vắng", str(d["so_vang"])),
               ("Lương cơ bản", vnd(d["luong_co_ban"])), ("Thưởng + phụ cấp", vnd(d["tien_thuong"])),
               ("Phạt + khấu trừ", vnd(d["tien_phat"])), ("THỰC LÃNH", vnd(d["thuc_lanh"]))]
    items = [(svc.ITEM_TYPES.get(m.loai, m.loai), "Thủ công" if m.nguon == "thu_cong" else "Tự động",
              m.ly_do or "", (-1 if m.loai in svc.MINUS_TYPES else 1) * svc.money(m.so_tien)) for m in phieu.muc_list]
    if dinh_dang == "xlsx":
        info = [["Kỳ lương", ky.ten_ky], ["Từ ngày - đến ngày", f"{ky.tu_ngay:%d/%m/%Y} - {ky.den_ngay:%d/%m/%Y}"],
                ["Mã nhân viên", d["ma_nhan_vien"]], ["Họ tên", d["ho_ten"]], ["Vị trí", d["ten_vi_tri"]],
                ["Đơn giá", rate_text], *[[k, v] for k, v in summary]]
        content = build_workbook([
            ("Phieu luong", ["Mục", "Giá trị"], info, [len(info)]),
            ("Chi tiet ca", ["Ngày", "Ca", "Vào", "Ra", "Trạng thái", "Giờ công", "Hệ số", "Ngày lễ",
                             "Thành tiền", "Trễ (phút)", "Sớm (phút)", "Miễn phạt", "Tiền phạt"],
             [[date.fromisoformat(l["ngay"]).strftime("%d/%m/%Y"), l["ca"], l["vao"] or "", l["ra"] or "",
               l["ten_trang_thai"], l["so_gio"], l["he_so"], l["ngay_le"] or "", l["thanh_tien"], l["phut_tre"],
               l["phut_som"], "Có" if l["mien_phat"] else "", l["tien_phat"]] for l in lines]),
            ("Thuong phat", ["Loại", "Nguồn", "Nội dung", "Số tiền (+/-)"], [list(i) for i in items]),
        ])
        return file_response(content, XLSX_TYPE, slug + ".xlsx")
    content = build_pdf(
        "Phiếu lương", f"{ky.ten_ky} · {ky.tu_ngay:%d/%m/%Y} - {ky.den_ngay:%d/%m/%Y}"
                       + ("" if phieu.trang_thai == "da_chot" else " · BẢN NHÁP"),
        [("Nhân viên", f"{d['ho_ten']} ({d['ma_nhan_vien'] or ''})"), ("Vị trí", d["ten_vi_tri"] or "-"),
         ("Đơn giá", rate_text), *summary],
        [{"tieu_de": "Chi tiết ca làm",
          "header": ["Ngày", "Ca", "Vào - Ra", "Trạng thái", "Giờ", "Hệ số", "Thành tiền", "Trễ/Sớm"],
          "rows": [[date.fromisoformat(l["ngay"]).strftime("%d/%m"), l["ca"], f"{l['vao'] or '--'} - {l['ra'] or '--'}",
                    l["ten_trang_thai"] + (f" · {l['ngay_le']}" if l["ngay_le"] else ""), hours_text(l["so_gio"]),
                    f"× {l['he_so']:g}", vnd(l["thanh_tien"]),
                    (f"{l['phut_tre']}/{l['phut_som']} phút" if l["phut_tre"] or l["phut_som"] else "")
                    + (" (miễn phạt)" if l["mien_phat"] else "")] for l in lines],
          "widths": [14, 46, 22, 30, 12, 14, 26, 22], "align_right": [4, 5, 6]},
         {"tieu_de": "Thưởng, phụ cấp, phạt, khấu trừ",
          "header": ["Loại", "Nguồn", "Nội dung", "Số tiền"],
          "rows": [[i[0], i[1], i[2], ("+" if i[3] >= 0 else "-") + vnd(abs(i[3]))] for i in items],
          "widths": [32, 20, 100, 34], "align_right": [3]}],
        notes=["Lương cơ bản = Giờ công × Đơn giá/giờ × Hệ số ca. Thực lãnh = Lương cơ bản + Thưởng + Phụ cấp - Phạt - Khấu trừ.",
               "Có thắc mắc về phiếu lương, vui lòng liên hệ Quản lý cửa hàng."]
    )
    return file_response(content, "application/pdf", slug + ".pdf")


@router.get("/payslips/{phieu_id}/export")
def export_payslip(phieu_id: int, dinh_dang: str = Query("pdf", pattern="^(xlsx|pdf)$"),
                   current_user: TaiKhoan = Depends(get_current_user), db: Session = Depends(get_db)):
    """Phiếu lương cá nhân: nhân viên chỉ tải được phiếu của mình (FR-13)"""
    phieu = get_payslip(db, phieu_id)
    ensure_can_view(db, current_user, phieu)
    return payslip_files(phieu, dinh_dang)
