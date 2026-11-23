from typing import List, Optional
from datetime import date
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from app.database import get_db
from app.core.deps import get_current_user, require_roles
from app.models.system import CuaHang, ViTri, VaiTro
from app.models.employee import NhanVien, HopDong
from app.models.user import TaiKhoan, NhatKyHeThong
from app.schemas.system import (
    CuaHangResponse, CuaHangCreate, CuaHangUpdate,
    ViTriResponse, ViTriCreate, ViTriUpdate,
    VaiTroResponse, NhatKyHeThongResponse
)

router = APIRouter(prefix="/api/system", tags=["Danh mục Hệ thống (System)"])

# ---------- Cửa hàng (Stores) ----------

@router.get("/stores", response_model=List[CuaHangResponse])
def get_stores(include_inactive: bool = False, db: Session = Depends(get_db)):
    """Danh mục chi nhánh cửa hàng cà phê"""
    query = db.query(CuaHang)
    if not include_inactive:
        query = query.filter(CuaHang.trang_thai == True)
    return query.all()

@router.get("/stores/{store_id}", response_model=CuaHangResponse)
def get_store(store_id: int, db: Session = Depends(get_db)):
    """Chi tiết chi nhánh cửa hàng cà phê theo ID"""
    store = db.query(CuaHang).filter(CuaHang.id == store_id).first()
    if not store:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Không tìm thấy chi nhánh cửa hàng")
    return store

@router.post("/stores", response_model=CuaHangResponse, status_code=status.HTTP_201_CREATED)
def create_store(
    data: CuaHangCreate,
    current_user: TaiKhoan = Depends(require_roles(["Admin", "Manager"])),
    db: Session = Depends(get_db)
):
    """Tạo chi nhánh cửa hàng mới (Admin/Manager)"""
    store = CuaHang(
        ten_cua_hang=data.ten_cua_hang.strip(),
        dia_chi=data.dia_chi.strip() if data.dia_chi else None,
        vi_do=data.vi_do,
        kinh_do=data.kinh_do,
        trang_thai=data.trang_thai
    )
    db.add(store)
    db.commit()
    db.refresh(store)
    return store

@router.put("/stores/{store_id}", response_model=CuaHangResponse)
def update_store(
    store_id: int,
    data: CuaHangUpdate,
    current_user: TaiKhoan = Depends(require_roles(["Admin", "Manager"])),
    db: Session = Depends(get_db)
):
    """Cập nhật thông tin chi nhánh cửa hàng (Admin/Manager)"""
    store = db.query(CuaHang).filter(CuaHang.id == store_id).first()
    if not store:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Không tìm thấy chi nhánh cửa hàng")

    update_fields = data.model_dump(exclude_unset=True)
    for field, value in update_fields.items():
        if isinstance(value, str):
            value = value.strip()
        setattr(store, field, value)

    db.commit()
    db.refresh(store)
    return store

@router.delete("/stores/{store_id}")
def delete_store(
    store_id: int,
    current_user: TaiKhoan = Depends(require_roles(["Admin", "Manager"])),
    db: Session = Depends(get_db)
):
    """Xóa / ngừng hoạt động chi nhánh cửa hàng (Admin/Manager)"""
    store = db.query(CuaHang).filter(CuaHang.id == store_id).first()
    if not store:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Không tìm thấy chi nhánh cửa hàng")

    has_employees = db.query(NhanVien).filter(NhanVien.ma_cua_hang == store_id).first()
    if has_employees:
        store.trang_thai = False
        db.commit()
        return {"message": f"Chi nhánh '{store.ten_cua_hang}' có nhân viên trực thuộc nên được chuyển sang trạng thái Ngừng hoạt động"}

    db.delete(store)
    db.commit()
    return {"message": f"Đã xóa chi nhánh '{store.ten_cua_hang}' thành công"}

# ---------- Vị trí công việc (Positions) ----------

@router.get("/positions", response_model=List[ViTriResponse])
def get_positions(db: Session = Depends(get_db)):
    """Danh mục vị trí công việc (Quản lý, Pha chế, Phục vụ, Thu ngân)"""
    return db.query(ViTri).all()

@router.get("/positions/{position_id}", response_model=ViTriResponse)
def get_position(position_id: int, db: Session = Depends(get_db)):
    """Chi tiết vị trí công việc theo ID"""
    pos = db.query(ViTri).filter(ViTri.id == position_id).first()
    if not pos:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Không tìm thấy vị trí công việc")
    return pos

@router.post("/positions", response_model=ViTriResponse, status_code=status.HTTP_201_CREATED)
def create_position(
    data: ViTriCreate,
    current_user: TaiKhoan = Depends(require_roles(["Admin", "Manager"])),
    db: Session = Depends(get_db)
):
    """Thêm vị trí công việc mới (Admin/Manager)"""
    name = data.ten_vi_tri.strip()
    if db.query(ViTri).filter(ViTri.ten_vi_tri == name).first():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Vị trí '{name}' đã tồn tại")

    pos = ViTri(ten_vi_tri=name, mo_ta=data.mo_ta.strip() if data.mo_ta else None)
    db.add(pos)
    db.commit()
    db.refresh(pos)
    return pos

@router.put("/positions/{position_id}", response_model=ViTriResponse)
def update_position(
    position_id: int,
    data: ViTriUpdate,
    current_user: TaiKhoan = Depends(require_roles(["Admin", "Manager"])),
    db: Session = Depends(get_db)
):
    """Cập nhật vị trí công việc (Admin/Manager)"""
    pos = db.query(ViTri).filter(ViTri.id == position_id).first()
    if not pos:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Không tìm thấy vị trí công việc")

    if data.ten_vi_tri is not None:
        name = data.ten_vi_tri.strip()
        existing = db.query(ViTri).filter(ViTri.ten_vi_tri == name, ViTri.id != position_id).first()
        if existing:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Vị trí '{name}' đã tồn tại")
        pos.ten_vi_tri = name

    if data.mo_ta is not None:
        pos.mo_ta = data.mo_ta.strip() if data.mo_ta else None

    db.commit()
    db.refresh(pos)
    return pos

@router.delete("/positions/{position_id}")
def delete_position(
    position_id: int,
    current_user: TaiKhoan = Depends(require_roles(["Admin", "Manager"])),
    db: Session = Depends(get_db)
):
    """Xóa vị trí công việc (Admin/Manager)"""
    pos = db.query(ViTri).filter(ViTri.id == position_id).first()
    if not pos:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Không tìm thấy vị trí công việc")

    has_employees = db.query(NhanVien).filter(NhanVien.ma_vi_tri == position_id).first()
    if has_employees:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Vị trí '{pos.ten_vi_tri}' đang có nhân viên đảm nhiệm, không thể xóa")

    db.delete(pos)
    db.commit()
    return {"message": f"Đã xóa vị trí '{pos.ten_vi_tri}' thành công"}

# ---------- Vai trò (Roles) ----------

@router.get("/roles", response_model=List[VaiTroResponse])
def get_roles(db: Session = Depends(get_db)):
    """Danh mục vai trò người dùng (Admin, Manager, Staff)"""
    return db.query(VaiTro).all()

# ---------- Thống kê (Dashboard Stats) ----------

@router.get("/stats")
def get_dashboard_stats(
    current_user: TaiKhoan = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Thống kê tổng quan phục vụ Dashboard
    """
    total_employees = db.query(NhanVien).filter(NhanVien.is_deleted == False).count()
    active_employees = db.query(NhanVien).filter(NhanVien.is_deleted == False, NhanVien.trang_thai == "dang_lam").count()
    on_leave_employees = db.query(NhanVien).filter(NhanVien.is_deleted == False, NhanVien.trang_thai == "nghi_phep").count()
    resigned_employees = db.query(NhanVien).filter(NhanVien.is_deleted == False, NhanVien.trang_thai == "da_nghi").count()
    
    total_stores = db.query(CuaHang).count()
    
    today = date.today()
    expiring_contracts = 0
    contracts = db.query(HopDong).filter(HopDong.trang_thai == "hieu_luc", HopDong.ngay_ket_thuc.isnot(None)).all()
    for hd in contracts:
        delta = (hd.ngay_ket_thuc - today).days
        if 0 <= delta <= 30:
            expiring_contracts += 1

    return {
        "total_employees": total_employees,
        "active_employees": active_employees,
        "on_leave_employees": on_leave_employees,
        "resigned_employees": resigned_employees,
        "total_stores": total_stores,
        "expiring_contracts": expiring_contracts
    }

# ---------- Nhật ký hệ thống (Audit Logs) ----------

@router.get("/audit-logs", response_model=List[NhatKyHeThongResponse])
def get_audit_logs(
    hanh_dong: Optional[str] = Query(None, description="Lọc theo mã hành động"),
    ma_tai_khoan: Optional[int] = Query(None, description="Lọc theo mã tài khoản thực hiện"),
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
    current_user: TaiKhoan = Depends(require_roles(["Admin", "Manager"])),
    db: Session = Depends(get_db)
):
    """
    Xem nhật ký kiểm toán hệ thống (Audit Logs) - Dành cho Quản trị viên và Quản lý
    """
    query = db.query(NhatKyHeThong)
    if hanh_dong:
        query = query.filter(NhatKyHeThong.hanh_dong == hanh_dong)
    if ma_tai_khoan:
        query = query.filter(NhatKyHeThong.ma_tai_khoan == ma_tai_khoan)

    logs = query.order_by(NhatKyHeThong.thoi_gian.desc()).offset(offset).limit(limit).all()

    # Enrich với tên người dùng
    user_ids = {log.ma_tai_khoan for log in logs}
    users = db.query(TaiKhoan).filter(TaiKhoan.id.in_(user_ids)).all() if user_ids else []
    user_map = {u.id: (u.nhan_vien.ho_ten if u.nhan_vien else u.ten_dang_nhap) for u in users}

    result = []
    for log in logs:
        result.append(
            NhatKyHeThongResponse(
                id=log.id,
                ma_tai_khoan=log.ma_tai_khoan,
                ma_cua_hang=log.ma_cua_hang,
                hanh_dong=log.hanh_dong,
                thoi_gian=log.thoi_gian,
                ly_do=log.ly_do,
                trang_thai=log.trang_thai,
                ten_nguoi_dung=user_map.get(log.ma_tai_khoan)
            )
        )
    return result
