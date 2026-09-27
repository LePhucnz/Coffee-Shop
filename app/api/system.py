from typing import List
from datetime import date
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.database import get_db
from app.core.deps import get_current_user
from app.models.system import CuaHang, ViTri, VaiTro
from app.models.employee import NhanVien, HopDong
from app.models.user import TaiKhoan
from app.schemas.system import CuaHangResponse, ViTriResponse, VaiTroResponse

router = APIRouter(prefix="/api/system", tags=["Danh mục Hệ thống (System)"])

@router.get("/stores", response_model=List[CuaHangResponse])
def get_stores(db: Session = Depends(get_db)):
    """Danh mục chi nhánh cửa hàng cà phê"""
    return db.query(CuaHang).filter(CuaHang.trang_thai == True).all()

@router.get("/positions", response_model=List[ViTriResponse])
def get_positions(db: Session = Depends(get_db)):
    """Danh mục vị trí công việc (Quản lý, Pha chế, Phục vụ, Thu ngân)"""
    return db.query(ViTri).all()

@router.get("/roles", response_model=List[VaiTroResponse])
def get_roles(db: Session = Depends(get_db)):
    """Danh mục vai trò người dùng (Admin, Manager, Staff)"""
    return db.query(VaiTro).all()

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
