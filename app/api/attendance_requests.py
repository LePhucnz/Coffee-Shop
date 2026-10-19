"""
Sprint 5 - FR-11A: Yêu cầu bù/sửa công
- Nhân viên gửi yêu cầu cho ca của mình trong 48 giờ sau khi hết ca (BR-07), kèm lý do và minh chứng
- Quản lý duyệt / từ chối / yêu cầu bổ sung; không ai tự duyệt yêu cầu của mình (BR-08)
- Duyệt thì cập nhật giờ hiệu lực, giữ giờ gốc và ghi nhật ký (BR-06); kỳ đã chốt thì ghi sang kỳ sau (BR-04)
"""
import os
import uuid
from datetime import datetime, timedelta
from typing import List, Optional

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile, status
from sqlalchemy.orm import Session

from app.api.attendance import forbid, get_assignment, is_manager, require_employee_profile, account_names
from app.config import BASE_DIR
from app.core.deps import get_current_user, require_roles
from app.database import get_db
from app.models.attendance import YeuCauChamCong, TepMinhChung
from app.models.shift import PhanCongCa, ChamCong
from app.models.user import TaiKhoan
from app.schemas.attendance import (
    YeuCauCreate, YeuCauUpdate, YeuCauResponse, TepResponse, DuyetYeuCauRequest, TuChoiRequest, BoSungRequest,
    LOAI_YEU_CAU, TRANG_THAI_YEU_CAU
)
from app.services import attendance_service as svc
from app.services import shift_service as shift_svc

router = APIRouter(prefix="/api/attendance/requests", tags=["Yêu cầu bù/sửa công (FR-11A)"])

ADMIN_ROLES = svc.ADMIN_ROLES
OPEN_STATES = ["cho_duyet", "can_bo_sung"]
EVIDENCE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".pdf"}
UPLOAD_DIR = os.path.join(BASE_DIR, "app", "static", "uploads", "attendance")


def map_request(db: Session, yc: YeuCauChamCong) -> YeuCauResponse:
    pc = yc.phan_cong
    nv = yc.nhan_vien
    names = account_names(db, [yc.ma_tai_khoan, yc.nguoi_xu_ly])
    return YeuCauResponse(
        id=yc.id, ma_phan_cong=yc.ma_phan_cong, ma_nv=yc.ma_nv,
        ho_ten=nv.ho_ten if nv else None, ma_nhan_vien=nv.ma_nhan_vien if nv else None,
        ten_vi_tri=nv.vi_tri.ten_vi_tri if nv and nv.vi_tri else None,
        nguoi_gui=names.get(yc.ma_tai_khoan),
        ngay_lam=pc.ngay_lam if pc else None,
        ten_ca=(pc.loai_ca.ten_ca or pc.loai_ca.ma_loai_ca) if pc else None,
        gio_bat_dau=pc.loai_ca.gio_bat_dau if pc else None,
        gio_ket_thuc=pc.loai_ca.gio_ket_thuc if pc else None,
        loai=yc.loai, ten_loai=LOAI_YEU_CAU.get(yc.loai, yc.loai),
        gio_vao_de_xuat=yc.gio_vao_de_xuat, gio_ra_de_xuat=yc.gio_ra_de_xuat,
        ma_phan_cong_dung=yc.ma_phan_cong_dung,
        ten_ca_dung=shift_svc.shift_label(yc.phan_cong_dung.loai_ca) if yc.phan_cong_dung else None,
        ly_do=yc.ly_do, trang_thai=yc.trang_thai, ten_trang_thai=TRANG_THAI_YEU_CAU.get(yc.trang_thai, yc.trang_thai),
        vuot_han_muc=bool(yc.vuot_han_muc), lech_nhieu=bool(yc.lech_nhieu), han_xu_ly=yc.han_xu_ly,
        cau_hoi_bo_sung=yc.cau_hoi_bo_sung, ly_do_tu_choi=yc.ly_do_tu_choi, ghi_chu_duyet=yc.ghi_chu_duyet,
        nguoi_xu_ly=names.get(yc.nguoi_xu_ly), ngay_xu_ly=yc.ngay_xu_ly, ngay_tao=yc.ngay_tao,
        tep=[TepResponse(id=t.id, ten_tep=t.ten_tep, duong_dan=t.duong_dan, kich_thuoc=t.kich_thuoc) for t in yc.tep_list]
    )


def get_request(db: Session, request_id: int) -> YeuCauChamCong:
    yc = db.query(YeuCauChamCong).filter(YeuCauChamCong.id == request_id).first()
    if not yc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Không tìm thấy yêu cầu")
    return yc


def bad(detail: str):
    raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=detail)


def validate_request(db: Session, cfg: dict, pc: PhanCongCa, loai: str, gio_vao: Optional[datetime],
                     gio_ra: Optional[datetime], target_id: Optional[int], ly_do: str, at: datetime,
                     check_deadline: bool = True):
    """Kiểm tra theo Quy tắc 2, 3, 4 của FR-11A. Trả về (lệch nhiều, ca đúng nếu "Sửa ca")."""
    if not svc.is_published(pc):
        bad("Lịch ca này chưa được công bố")
    if pc.da_huy:
        bad("Ca này đã bị hủy, vui lòng liên hệ Quản lý")
    start, end = svc.interval_of(pc)
    if at < start:
        bad("Ca này chưa bắt đầu nên chưa gửi được yêu cầu bù/sửa công")
    if check_deadline and at > svc.submit_deadline(pc, cfg):
        bad(f"Đã quá hạn {cfg['han_gui_yeu_cau_gio']} giờ kể từ khi hết ca. Vui lòng liên hệ Quản lý để điều chỉnh trực tiếp.")

    cc = svc.get_record(db, pc.id)
    has_in = bool(cc and cc.check_in_lan_1)
    has_out = bool(cc and cc.check_out_lan_1)
    target = None
    if loai == "bu_check_in":
        if has_in:
            bad("Ca này đã có giờ vào. Hãy chọn \"Sửa giờ chấm công\" nếu giờ vào bị sai.")
        if not gio_vao:
            bad("Vui lòng nhập giờ vào thực tế")
    elif loai == "bu_check_out":
        if not has_in:
            bad("Ca này chưa có giờ vào. Hãy chọn \"Bù cả vào và ra\".")
        if has_out:
            bad("Ca này đã có giờ ra. Hãy chọn \"Sửa giờ chấm công\" nếu giờ ra bị sai.")
        if not gio_ra:
            bad("Vui lòng nhập giờ ra thực tế")
    elif loai == "bu_ca_hai":
        if has_in:
            bad("Ca này đã có giờ vào. Hãy chọn \"Bù check-out\" hoặc \"Sửa giờ chấm công\".")
        if not gio_vao or not gio_ra:
            bad("Vui lòng nhập cả giờ vào và giờ ra")
    elif loai == "sua_gio":
        if not has_in:
            bad("Ca này chưa có bản ghi chấm công để sửa. Hãy chọn loại \"Bù\" phù hợp.")
        if not gio_vao and not gio_ra:
            bad("Vui lòng nhập giờ đúng cần sửa")
    elif loai == "sua_ca":
        if not has_in:
            bad("Ca này chưa có bản ghi chấm công để chuyển")
        if not target_id:
            bad("Vui lòng chọn ca đúng")
        target = db.query(PhanCongCa).filter(PhanCongCa.id == target_id).first()
        if not target or target.ma_nv != pc.ma_nv or target.ngay_lam != pc.ngay_lam or target.id == pc.id:
            bad("Ca đúng phải là ca khác của bạn trong cùng ngày")
        if not svc.is_published(target) or target.da_huy:
            bad("Ca đúng chưa được công bố hoặc đã bị hủy")
        if svc.get_record(db, target.id):
            bad("Ca đúng đã có bản ghi chấm công")
    elif loai == "giai_trinh":
        if not cc or not (cc.ngoai_vi_tri or cc.khong_dinh_vi or cc.thiet_bi_trung) or cc.da_xac_minh_co:
            bad("Bản ghi này không có cờ cần giải trình")

    # Quy tắc 3: giờ đề xuất hợp lệ
    vao = gio_vao or (cc.check_in_lan_1 if cc else None)
    ra = gio_ra or (cc.check_out_lan_1 if cc else None)
    for value in (gio_vao, gio_ra):
        if value and value > at:
            bad("Giờ đề xuất không được sau thời điểm hiện tại")
    if vao and ra and ra <= vao:
        bad("Giờ vào phải trước giờ ra")
    lech = False
    if loai in ("bu_check_in", "bu_check_out", "bu_ca_hai", "sua_gio"):
        limit = timedelta(hours=cfg["do_lech_toi_da_gio"])
        if (gio_vao and abs(gio_vao - start) > limit) or (gio_ra and abs(gio_ra - end) > limit):
            lech = True
            if len(ly_do.strip()) < 30:
                bad(f"Giờ đề xuất lệch quá {cfg['do_lech_toi_da_gio']} giờ so với giờ ca. "
                    "Vui lòng nêu lý do chi tiết (tối thiểu 30 ký tự).")
        # BR-01: không trùng với ca khác của cùng nhân viên
        if vao:
            new_end = ra or vao + timedelta(minutes=1)
            others = db.query(PhanCongCa).filter(PhanCongCa.ma_nv == pc.ma_nv, PhanCongCa.id != pc.id,
                                                 PhanCongCa.ngay_lam >= pc.ngay_lam - timedelta(days=1),
                                                 PhanCongCa.ngay_lam <= pc.ngay_lam + timedelta(days=1)).all()
            for other in others:
                if other.da_huy:
                    continue
                interval = svc.interval_of(other)
                if interval and vao < interval[1] and interval[0] < new_end:
                    bad(f"Khoảng giờ đề xuất trùng với {shift_svc.shift_label(other.loai_ca)} "
                        f"ngày {other.ngay_lam.strftime('%d/%m')} của bạn")
    return lech, target


def count_this_month(db: Session, ma_nv: int, at: datetime, exclude_id: Optional[int] = None) -> int:
    first = at.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    q = db.query(YeuCauChamCong).filter(YeuCauChamCong.ma_nv == ma_nv, YeuCauChamCong.ngay_tao >= first,
                                        YeuCauChamCong.trang_thai != "da_huy",
                                        YeuCauChamCong.loai != "giai_trinh")
    if exclude_id:
        q = q.filter(YeuCauChamCong.id != exclude_id)
    return q.count()


# ---------- Nhân viên ----------

@router.post("", response_model=YeuCauResponse, status_code=status.HTTP_201_CREATED)
def create_request(data: YeuCauCreate, current_user: TaiKhoan = Depends(get_current_user),
                   db: Session = Depends(get_db)):
    nv_id = require_employee_profile(current_user)
    pc = get_assignment(db, data.ma_phan_cong)
    if pc.ma_nv != nv_id:
        forbid(db, current_user, "Bạn chỉ gửi được yêu cầu cho ca được phân công cho mình")  # Quy tắc 1
    cfg = svc.get_config(db)
    at = svc.now()
    # Quy tắc 5: mỗi ca chỉ một yêu cầu đang xử lý
    if db.query(YeuCauChamCong).filter(YeuCauChamCong.ma_phan_cong == pc.id,
                                       YeuCauChamCong.trang_thai.in_(OPEN_STATES)).first():
        bad("Ca này đã có một yêu cầu đang chờ xử lý. Hãy theo dõi ở tab \"Yêu cầu của tôi\".")
    lech, target = validate_request(db, cfg, pc, data.loai, data.gio_vao_de_xuat, data.gio_ra_de_xuat,
                                    data.ma_phan_cong_dung, data.ly_do, at)
    is_quota_request = data.loai != "giai_trinh"
    yc = YeuCauChamCong(
        ma_phan_cong=pc.id, ma_nv=nv_id, ma_tai_khoan=current_user.id, loai=data.loai,
        gio_vao_de_xuat=data.gio_vao_de_xuat, gio_ra_de_xuat=data.gio_ra_de_xuat,
        ma_phan_cong_dung=target.id if target else None, ly_do=data.ly_do.strip(),
        trang_thai="cho_duyet", lech_nhieu=lech,
        # Quy tắc 6: vượt hạn mức vẫn gửi được nhưng gắn cờ
        vuot_han_muc=is_quota_request and count_this_month(db, nv_id, at) >= cfg["han_muc_thang"],
        han_xu_ly=svc.request_deadline(pc, cfg, at), ngay_tao=at, ngay_cap_nhat=at
    )
    db.add(yc)
    db.flush()
    who = current_user.nhan_vien.ho_ten if current_user.nhan_vien else current_user.ten_dang_nhap
    extra = " (cần Chủ quán duyệt)" if svc.role_of(current_user) in ADMIN_ROLES else ""
    svc.notify_managers(db, f"Yêu cầu {LOAI_YEU_CAU[data.loai].lower()} mới{extra}",
                        f"{who} - ca {shift_svc.shift_label(pc.loai_ca)} ngày {pc.ngay_lam.strftime('%d/%m/%Y')}",
                        f"/attendance-requests?id={yc.id}", exclude_account=current_user.id)
    db.commit()
    db.refresh(yc)
    return map_request(db, yc)


@router.get("/me", response_model=List[YeuCauResponse])
def my_requests(trang_thai: Optional[str] = Query(None), current_user: TaiKhoan = Depends(get_current_user),
                db: Session = Depends(get_db)):
    nv_id = require_employee_profile(current_user)
    svc.run_request_maintenance(db, svc.get_config(db))
    q = db.query(YeuCauChamCong).filter(YeuCauChamCong.ma_nv == nv_id)
    if trang_thai:
        q = q.filter(YeuCauChamCong.trang_thai == trang_thai)
    return [map_request(db, yc) for yc in q.order_by(YeuCauChamCong.ngay_tao.desc()).limit(200).all()]


def get_own_open_request(db: Session, user: TaiKhoan, request_id: int) -> YeuCauChamCong:
    yc = get_request(db, request_id)
    if yc.ma_tai_khoan != user.id and yc.ma_nv != user.ma_nv:
        forbid(db, user, "Bạn chỉ được xem và sửa yêu cầu của chính mình")
    if yc.trang_thai not in OPEN_STATES:
        bad(f"Yêu cầu đang ở trạng thái \"{TRANG_THAI_YEU_CAU[yc.trang_thai]}\" nên không thay đổi được")
    return yc


@router.put("/{request_id}", response_model=YeuCauResponse)
def update_request(request_id: int, data: YeuCauUpdate, current_user: TaiKhoan = Depends(get_current_user),
                   db: Session = Depends(get_db)):
    """Nhân viên cập nhật yêu cầu (thường là khi Quản lý cần bổ sung); yêu cầu quay lại "Chờ duyệt" """
    yc = get_own_open_request(db, current_user, request_id)
    cfg = svc.get_config(db)
    at = svc.now()
    pc = yc.phan_cong
    # Đang "Cần bổ sung" thì hạn bổ sung tính từ lúc Quản lý hỏi (thay cho hạn gửi)
    if yc.trang_thai == "can_bo_sung":
        deadline = yc.ngay_yeu_cau_bo_sung + timedelta(hours=cfg["han_gui_yeu_cau_gio"])
        if at > deadline:
            bad("Đã quá hạn bổ sung thông tin")
        lech, target = validate_request(db, cfg, pc, yc.loai, data.gio_vao_de_xuat, data.gio_ra_de_xuat,
                                        data.ma_phan_cong_dung, data.ly_do, at, check_deadline=False)
    else:
        lech, target = validate_request(db, cfg, pc, yc.loai, data.gio_vao_de_xuat, data.gio_ra_de_xuat,
                                        data.ma_phan_cong_dung, data.ly_do, at)
    yc.gio_vao_de_xuat = data.gio_vao_de_xuat
    yc.gio_ra_de_xuat = data.gio_ra_de_xuat
    yc.ma_phan_cong_dung = target.id if target else None
    yc.ly_do = data.ly_do.strip()
    yc.lech_nhieu = lech
    was_asked = yc.trang_thai == "can_bo_sung"
    yc.trang_thai = "cho_duyet"
    yc.ngay_cap_nhat = at
    if was_asked:
        svc.notify_managers(db, "Nhân viên đã bổ sung thông tin cho yêu cầu bù/sửa công",
                            f"{yc.nhan_vien.ho_ten if yc.nhan_vien else ''} - ngày {pc.ngay_lam.strftime('%d/%m/%Y')}",
                            f"/attendance-requests?id={yc.id}", exclude_account=current_user.id)
    db.commit()
    db.refresh(yc)
    return map_request(db, yc)


@router.post("/{request_id}/cancel", response_model=YeuCauResponse)
def cancel_request(request_id: int, current_user: TaiKhoan = Depends(get_current_user), db: Session = Depends(get_db)):
    yc = get_own_open_request(db, current_user, request_id)
    yc.trang_thai = "da_huy"
    yc.ngay_cap_nhat = svc.now()
    db.commit()
    db.refresh(yc)
    return map_request(db, yc)


@router.delete("/{request_id}")
def delete_request(request_id: int, current_user: TaiKhoan = Depends(get_current_user), db: Session = Depends(get_db)):
    """Xóa yêu cầu chấm công (Admin/Manager hoặc người tạo với yêu cầu đã hủy/từ chối)"""
    yc = get_request(db, request_id)
    role_name = current_user.vai_tro.ten_vai_tro if current_user.vai_tro else "Staff"
    is_admin = role_name in ADMIN_ROLES
    is_owner = (yc.ma_tai_khoan == current_user.id or yc.ma_nv == current_user.ma_nv)
    if not is_admin and not is_owner:
        forbid(db, current_user, "Bạn không có quyền xóa yêu cầu này")
    if not is_admin and yc.trang_thai in ["cho_duyet", "da_duyet"]:
        bad("Chỉ có thể xóa yêu cầu đã hủy hoặc từ chối. Hãy hủy yêu cầu trước khi xóa.")
    db.delete(yc)
    db.commit()
    return {"message": "Đã xóa yêu cầu thành công"}



@router.post("/{request_id}/files", response_model=YeuCauResponse)
def upload_evidence(request_id: int, file: UploadFile = File(...), current_user: TaiKhoan = Depends(get_current_user),
                    db: Session = Depends(get_db)):
    """Quy tắc 4: minh chứng JPG/PNG/PDF, tối đa 3 tệp, mỗi tệp tối đa 5 MB (cấu hình được)"""
    yc = get_own_open_request(db, current_user, request_id)
    cfg = svc.get_config(db)
    if len(yc.tep_list) >= cfg["so_tep_toi_da"]:
        bad(f"Mỗi yêu cầu chỉ đính kèm tối đa {cfg['so_tep_toi_da']} tệp")
    ext = os.path.splitext(file.filename or "")[1].lower()
    if ext not in EVIDENCE_EXTENSIONS:
        bad("Chỉ chấp nhận tệp JPG, PNG hoặc PDF")
    content = file.file.read()
    if not content:
        bad("Tệp rỗng")
    if len(content) > cfg["dung_luong_tep_mb"] * 1024 * 1024:
        bad(f"Tệp vượt quá {cfg['dung_luong_tep_mb']} MB")
    os.makedirs(UPLOAD_DIR, exist_ok=True)
    name = f"{uuid.uuid4().hex}{ext}"
    with open(os.path.join(UPLOAD_DIR, name), "wb") as f:
        f.write(content)
    db.add(TepMinhChung(ma_yeu_cau=yc.id, ten_tep=os.path.basename(file.filename or name)[:255],
                        duong_dan=f"/static/uploads/attendance/{name}", kich_thuoc=len(content)))
    db.commit()
    db.refresh(yc)
    return map_request(db, yc)


@router.delete("/{request_id}/files/{file_id}", response_model=YeuCauResponse)
def delete_evidence(request_id: int, file_id: int, current_user: TaiKhoan = Depends(get_current_user),
                    db: Session = Depends(get_db)):
    yc = get_own_open_request(db, current_user, request_id)
    tep = next((t for t in yc.tep_list if t.id == file_id), None)
    if not tep:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Không tìm thấy tệp")
    db.delete(tep)
    db.commit()
    db.refresh(yc)
    return map_request(db, yc)


# ---------- Quản lý: hàng đợi và ra quyết định (màn 09) ----------

@router.get("", response_model=List[YeuCauResponse])
def list_requests(
    trang_thai: Optional[str] = Query("dang_mo", description="dang_mo (Chờ duyệt + Cần bổ sung), cho_duyet, da_duyet..."),
    ma_nv: Optional[int] = Query(None),
    loai: Optional[str] = Query(None),
    current_user: TaiKhoan = Depends(require_roles(ADMIN_ROLES)),
    db: Session = Depends(get_db)
):
    """Hàng đợi yêu cầu, cũ nhất lên đầu để xử lý theo thứ tự"""
    svc.run_request_maintenance(db, svc.get_config(db))
    q = db.query(YeuCauChamCong)
    if trang_thai == "dang_mo":
        q = q.filter(YeuCauChamCong.trang_thai.in_(OPEN_STATES))
    elif trang_thai and trang_thai != "tat_ca":
        q = q.filter(YeuCauChamCong.trang_thai == trang_thai)
    if ma_nv:
        q = q.filter(YeuCauChamCong.ma_nv == ma_nv)
    if loai:
        q = q.filter(YeuCauChamCong.loai == loai)
    return [map_request(db, yc) for yc in q.order_by(YeuCauChamCong.ngay_tao, YeuCauChamCong.id).limit(500).all()]


@router.get("/pending-count")
def pending_count(current_user: TaiKhoan = Depends(require_roles(ADMIN_ROLES)), db: Session = Depends(get_db)):
    """Huy hiệu số yêu cầu chờ duyệt trên menu"""
    return {"so_cho_duyet": db.query(YeuCauChamCong).filter(YeuCauChamCong.trang_thai == "cho_duyet").count()}


@router.get("/{request_id}", response_model=YeuCauResponse)
def request_detail(request_id: int, current_user: TaiKhoan = Depends(get_current_user), db: Session = Depends(get_db)):
    yc = get_request(db, request_id)
    if not is_manager(current_user) and yc.ma_nv != current_user.ma_nv:
        forbid(db, current_user, "Bạn chỉ được xem yêu cầu của chính mình")
    return map_request(db, yc)


def get_decidable_request(db: Session, user: TaiKhoan, request_id: int) -> YeuCauChamCong:
    """Quy tắc 7, BR-08: không tự duyệt; yêu cầu của Quản lý do Chủ quán (Admin) duyệt"""
    yc = get_request(db, request_id)
    if yc.ma_tai_khoan == user.id or (user.ma_nv and yc.ma_nv == user.ma_nv):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN,
                            detail="Không ai được tự duyệt yêu cầu chấm công của chính mình")
    requester = yc.nguoi_gui
    if requester and svc.role_of(requester) in ADMIN_ROLES and svc.role_of(user) != "Admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN,
                            detail="Yêu cầu của Quản lý do Chủ quán (Admin) duyệt")
    if yc.trang_thai not in OPEN_STATES:
        bad(f"Yêu cầu đã ở trạng thái \"{TRANG_THAI_YEU_CAU[yc.trang_thai]}\"")
    return yc


@router.post("/{request_id}/approve", response_model=YeuCauResponse)
def approve_request(request_id: int, data: DuyetYeuCauRequest,
                    current_user: TaiKhoan = Depends(require_roles(ADMIN_ROLES)), db: Session = Depends(get_db)):
    yc = get_decidable_request(db, current_user, request_id)
    cfg = svc.get_config(db)
    at = svc.now()
    pc = yc.phan_cong
    cc = svc.get_record(db, pc.id)
    note = (data.ghi_chu or "").strip()
    reason = f"{LOAI_YEU_CAU[yc.loai]}: {yc.ly_do}" + (f" | Ghi chú duyệt: {note}" if note else "")
    kind = "cap_nhat"
    if yc.loai == "giai_trinh":
        if not cc:
            bad("Bản ghi chấm công không còn tồn tại")
        cc.da_xac_minh_co = True
        cc.ghi_chu_xac_minh = yc.ly_do[:255]
        svc.write_log(db, pc.id, cc, "xac_minh_co", {"da_xac_minh_co": False}, {"da_xac_minh_co": True},
                      reason, current_user.id, yc.ma_tai_khoan, yc.id)
    else:
        target = None
        if yc.loai == "sua_ca":
            target = yc.phan_cong_dung
            if not target or svc.get_record(db, target.id):
                bad("Ca đúng không còn hợp lệ (đã có bản ghi chấm công)")
        kind, result = svc.apply_time_change(
            db, pc, cc, cfg,
            gio_vao=yc.gio_vao_de_xuat, gio_ra=yc.gio_ra_de_xuat,
            set_vao=yc.gio_vao_de_xuat is not None, set_ra=yc.gio_ra_de_xuat is not None,
            target=target, ly_do=reason, actor_id=current_user.id, hanh_dong="duyet_yeu_cau",
            requester_id=yc.ma_tai_khoan, request_id=yc.id
        )
        cc = result if kind == "cap_nhat" else cc
    if data.mien_phat and cc is not None:
        # Quy tắc 11: miễn phạt kèm lý do, ghi nhật ký
        cc.mien_phat = True
        cc.ly_do_mien_phat = (data.ly_do_mien_phat or note or "Miễn phạt khi duyệt yêu cầu")[:255]
        svc.write_log(db, pc.id, cc, "mien_phat", {"mien_phat": False}, {"mien_phat": True},
                      cc.ly_do_mien_phat, current_user.id, yc.ma_tai_khoan, yc.id)
    yc.trang_thai = "da_duyet"
    yc.ghi_chu_duyet = note or None
    yc.nguoi_xu_ly = current_user.id
    yc.ngay_xu_ly = yc.ngay_cap_nhat = at
    extra = " Điều chỉnh được áp dụng vào kỳ lương sau vì kỳ này đã chốt." if kind == "phu_luc" else ""
    svc.notify_staff(db, yc.ma_nv, "Yêu cầu bù/sửa công đã được duyệt",
                     f"{LOAI_YEU_CAU[yc.loai]} ngày {pc.ngay_lam.strftime('%d/%m/%Y')}.{extra}",
                     "/attendance-history?tab=requests")
    db.commit()
    db.refresh(yc)
    return map_request(db, yc)


@router.post("/{request_id}/reject", response_model=YeuCauResponse)
def reject_request(request_id: int, data: TuChoiRequest,
                   current_user: TaiKhoan = Depends(require_roles(ADMIN_ROLES)), db: Session = Depends(get_db)):
    yc = get_decidable_request(db, current_user, request_id)
    at = svc.now()
    yc.trang_thai = "tu_choi"
    yc.ly_do_tu_choi = data.ly_do.strip()
    yc.nguoi_xu_ly = current_user.id
    yc.ngay_xu_ly = yc.ngay_cap_nhat = at
    svc.notify_staff(db, yc.ma_nv, "Yêu cầu bù/sửa công bị từ chối",
                     f"Lý do: {yc.ly_do_tu_choi}. Nếu còn trong hạn, bạn có thể gửi yêu cầu mới kèm minh chứng.",
                     "/attendance-history?tab=requests")
    db.commit()
    db.refresh(yc)
    return map_request(db, yc)


@router.post("/{request_id}/ask", response_model=YeuCauResponse)
def ask_more_info(request_id: int, data: BoSungRequest,
                  current_user: TaiKhoan = Depends(require_roles(ADMIN_ROLES)), db: Session = Depends(get_db)):
    yc = get_decidable_request(db, current_user, request_id)
    at = svc.now()
    yc.trang_thai = "can_bo_sung"
    yc.cau_hoi_bo_sung = data.cau_hoi.strip()
    yc.ngay_yeu_cau_bo_sung = yc.ngay_cap_nhat = at
    yc.nguoi_xu_ly = current_user.id
    svc.notify_staff(db, yc.ma_nv, "Quản lý cần bạn bổ sung thông tin",
                     f"{yc.cau_hoi_bo_sung}", "/attendance-history?tab=requests")
    db.commit()
    db.refresh(yc)
    return map_request(db, yc)
