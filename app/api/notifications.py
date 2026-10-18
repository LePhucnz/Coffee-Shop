"""Sprint 4 (FR-08): Thông báo trong ứng dụng cho nhân viên (ví dụ: lịch ca đã công bố)"""
from typing import List, Optional
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.deps import get_current_user, require_roles
from app.database import get_db
from app.models.shift import ThongBao
from app.models.employee import NhanVien
from app.models.user import TaiKhoan
from app.schemas.shift import DanhSachThongBao, ThongBaoResponse, ThongBaoCreate

router = APIRouter(prefix="/api/notifications", tags=["Thông báo (Notifications)"])


@router.get("/me", response_model=DanhSachThongBao)
def my_notifications(
    limit: int = 30,
    current_user: TaiKhoan = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Danh sách thông báo mới nhất của người đang đăng nhập"""
    if not current_user.ma_nv:
        return DanhSachThongBao(so_chua_doc=0, items=[])
    query = db.query(ThongBao).filter(ThongBao.ma_nv == current_user.ma_nv)
    so_chua_doc = query.filter(ThongBao.da_doc == False).count()
    items = query.order_by(ThongBao.ngay_tao.desc(), ThongBao.id.desc()).limit(min(max(limit, 1), 100)).all()
    return DanhSachThongBao(so_chua_doc=so_chua_doc, items=[ThongBaoResponse.model_validate(tb) for tb in items])


@router.post("", response_model=List[ThongBaoResponse], status_code=status.HTTP_201_CREATED)
def create_notification(
    data: ThongBaoCreate,
    current_user: TaiKhoan = Depends(require_roles(["Admin", "Manager"])),
    db: Session = Depends(get_db)
):
    """
    Gửi thông báo tới nhân viên cụ thể hoặc toàn bộ nhân viên đang làm việc (Admin/Manager)
    """
    created = []
    at = datetime.utcnow()
    if data.ma_nv:
        nv = db.query(NhanVien).filter(NhanVien.id == data.ma_nv).first()
        if not nv:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Không tìm thấy nhân viên")
        tb = ThongBao(
            ma_nv=data.ma_nv,
            tieu_de=data.tieu_de.strip(),
            noi_dung=data.noi_dung.strip(),
            lien_ket=data.lien_ket,
            da_doc=False,
            ngay_tao=at
        )
        db.add(tb)
        db.commit()
        db.refresh(tb)
        created.append(tb)
    else:
        active_emps = db.query(NhanVien).filter(
            NhanVien.is_deleted == False,
            NhanVien.trang_thai == "dang_lam"
        ).all()
        for emp in active_emps:
            tb = ThongBao(
                ma_nv=emp.id,
                tieu_de=data.tieu_de.strip(),
                noi_dung=data.noi_dung.strip(),
                lien_ket=data.lien_ket,
                da_doc=False,
                ngay_tao=at
            )
            db.add(tb)
            created.append(tb)
        db.commit()
        for tb in created:
            db.refresh(tb)

    return [ThongBaoResponse.model_validate(tb) for tb in created]


@router.post("/{notification_id}/read", response_model=ThongBaoResponse)
def mark_read(
    notification_id: int,
    current_user: TaiKhoan = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    tb = db.query(ThongBao).filter(ThongBao.id == notification_id).first()
    if not tb or tb.ma_nv != current_user.ma_nv:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Không tìm thấy thông báo")
    tb.da_doc = True
    db.commit()
    db.refresh(tb)
    return ThongBaoResponse.model_validate(tb)


@router.post("/read-all")
def mark_all_read(
    current_user: TaiKhoan = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    if not current_user.ma_nv:
        return {"da_cap_nhat": 0}
    updated = db.query(ThongBao).filter(
        ThongBao.ma_nv == current_user.ma_nv,
        ThongBao.da_doc == False
    ).update({"da_doc": True}, synchronize_session=False)
    db.commit()
    return {"da_cap_nhat": updated}


@router.delete("/{notification_id}")
def delete_notification(
    notification_id: int,
    current_user: TaiKhoan = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Xóa thông báo (Admin/Manager hoặc nhân viên sở hữu thông báo đó)"""
    tb = db.query(ThongBao).filter(ThongBao.id == notification_id).first()
    if not tb:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Không tìm thấy thông báo")
    role_name = current_user.vai_tro.ten_vai_tro if current_user.vai_tro else "Staff"
    if role_name not in ["Admin", "Manager"] and tb.ma_nv != current_user.ma_nv:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Không có quyền xóa thông báo này")
    db.delete(tb)
    db.commit()
    return {"message": "Đã xóa thông báo thành công"}
