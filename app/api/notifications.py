"""Sprint 4 (FR-08): Thông báo trong ứng dụng cho nhân viên (ví dụ: lịch ca đã công bố)"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.deps import get_current_user
from app.database import get_db
from app.models.shift import ThongBao
from app.models.user import TaiKhoan
from app.schemas.shift import DanhSachThongBao, ThongBaoResponse

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
