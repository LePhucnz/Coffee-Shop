from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from sqlalchemy import or_
from app.database import get_db
from app.core.deps import get_current_user, require_roles
from app.models.employee import NhanVien
from app.models.user import TaiKhoan
from app.models.system import CuaHang, ViTri
from app.schemas.employee import (
    NhanVienCreate, NhanVienUpdate, NhanVienResponse,
    NhanVienListResponse, NhanVienStatusUpdate
)
from app.core.security import get_password_hash, validate_password_complexity

router = APIRouter(prefix="/api/employees", tags=["Quản lý Hồ sơ Nhân sự (HR)"])

def map_nhan_vien_response(nv: NhanVien) -> NhanVienResponse:
    return NhanVienResponse(
        id=nv.id,
        ma_nhan_vien=nv.ma_nhan_vien,
        ma_cua_hang=nv.ma_cua_hang,
        ma_vi_tri=nv.ma_vi_tri,
        ho_ten=nv.ho_ten,
        so_dien_thoai=nv.so_dien_thoai,
        email=nv.email,
        dia_chi=nv.dia_chi,
        cccd=nv.cccd,
        ngay_sinh=nv.ngay_sinh,
        gioi_tinh=nv.gioi_tinh,
        tinh_trang_hon_nhan=nv.tinh_trang_hon_nhan,
        so_nhan_khau=nv.so_nhan_khau,
        ngay_vao_lam=nv.ngay_vao_lam,
        anh_dai_dien=nv.anh_dai_dien,
        trang_thai=nv.trang_thai,
        is_deleted=nv.is_deleted,
        ngay_tao=nv.ngay_tao,
        ten_cua_hang=nv.cua_hang.ten_cua_hang if nv.cua_hang else None,
        ten_vi_tri=nv.vi_tri.ten_vi_tri if nv.vi_tri else None,
        ten_dang_nhap=nv.tai_khoan.ten_dang_nhap if nv.tai_khoan else None
    )

@router.get("", response_model=NhanVienListResponse)
def list_employees(
    keyword: Optional[str] = Query(None, description="Tìm kiếm theo họ tên, mã NV, email, SĐT"),
    ma_vi_tri: Optional[int] = Query(None, description="Lọc theo vị trí công việc"),
    ma_cua_hang: Optional[int] = Query(None, description="Lọc theo cửa hàng"),
    trang_thai: Optional[str] = Query(None, description="Lọc theo trạng thái (dang_lam, nghi_phep, da_nghi)"),
    include_deleted: bool = Query(False, description="Bao gồm cả hồ sơ đã xóa mềm"),
    current_user: TaiKhoan = Depends(require_roles(["Admin", "Manager"])),
    db: Session = Depends(get_db)
):
    """
    FR-04, FR-06: Danh sách hồ sơ nhân sự
    - Tìm kiếm theo họ tên, mã, email, SĐT
    - Lọc theo vị trí, cửa hàng, trạng thái
    - Mặc định ẩn hồ sơ đã xóa mềm (soft delete)
    """
    query = db.query(NhanVien)

    if not include_deleted:
        query = query.filter(NhanVien.is_deleted == False)

    if keyword:
        kw = f"%{keyword.strip()}%"
        query = query.filter(
            or_(
                NhanVien.ho_ten.ilike(kw),
                NhanVien.ma_nhan_vien.ilike(kw),
                NhanVien.email.ilike(kw),
                NhanVien.so_dien_thoai.ilike(kw),
                NhanVien.cccd.ilike(kw)
            )
        )

    if ma_vi_tri:
        query = query.filter(NhanVien.ma_vi_tri == ma_vi_tri)

    if ma_cua_hang:
        query = query.filter(NhanVien.ma_cua_hang == ma_cua_hang)

    if trang_thai:
        query = query.filter(NhanVien.trang_thai == trang_thai)

    items = query.order_by(NhanVien.id.desc()).all()
    return NhanVienListResponse(
        total=len(items),
        items=[map_nhan_vien_response(item) for item in items]
    )

@router.get("/{employee_id}", response_model=NhanVienResponse)
def get_employee(
    employee_id: int,
    current_user: TaiKhoan = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Xem chi tiết hồ sơ nhân sự
    - Admin/Manager: xem được tất cả nhân viên
    - Staff: chỉ xem được hồ sơ của chính mình
    """
    role_name = current_user.vai_tro.ten_vai_tro if current_user.vai_tro else "Staff"
    if role_name not in ["Admin", "Manager"] and current_user.ma_nv != employee_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Nhân viên chỉ có quyền xem hồ sơ cá nhân của chính mình"
        )

    nv = db.query(NhanVien).filter(NhanVien.id == employee_id).first()
    if not nv:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Không tìm thấy hồ sơ nhân viên")

    return map_nhan_vien_response(nv)

@router.post("", response_model=NhanVienResponse, status_code=status.HTTP_201_CREATED)
def create_employee(
    data: NhanVienCreate,
    current_user: TaiKhoan = Depends(require_roles(["Admin", "Manager"])),
    db: Session = Depends(get_db)
):
    """
    FR-04: Thêm mới hồ sơ nhân sự (kèm tùy chọn khởi tạo tài khoản đăng nhập)
    """
    # Tự động sinh mã nhân viên nếu chưa có
    ma_nv = data.ma_nhan_vien
    if not ma_nv:
        count = db.query(NhanVien).count() + 1
        ma_nv = f"NV{count:03d}"
    else:
        existing = db.query(NhanVien).filter(NhanVien.ma_nhan_vien == ma_nv).first()
        if existing:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Mã nhân viên '{ma_nv}' đã tồn tại")

    if data.email:
        if db.query(NhanVien).filter(NhanVien.email == data.email).first():
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Email '{data.email}' đã được sử dụng")

    if data.so_dien_thoai:
        if db.query(NhanVien).filter(NhanVien.so_dien_thoai == data.so_dien_thoai).first():
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Số điện thoại '{data.so_dien_thoai}' đã được sử dụng")

    nv = NhanVien(
        ma_nhan_vien=ma_nv,
        ma_cua_hang=data.ma_cua_hang,
        ma_vi_tri=data.ma_vi_tri,
        ho_ten=data.ho_ten,
        so_dien_thoai=data.so_dien_thoai,
        email=data.email,
        dia_chi=data.dia_chi,
        cccd=data.cccd,
        ngay_sinh=data.ngay_sinh,
        gioi_tinh=data.gioi_tinh,
        tinh_trang_hon_nhan=data.tinh_trang_hon_nhan,
        so_nhan_khau=data.so_nhan_khau or 0,
        ngay_vao_lam=data.ngay_vao_lam,
        anh_dai_dien=data.anh_dai_dien,
        trang_thai=data.trang_thai or "dang_lam",
        is_deleted=False
    )
    db.add(nv)
    db.flush()

    # Nếu có yêu cầu tạo tài khoản đi kèm
    if data.tao_tai_khoan and data.ten_dang_nhap and data.mat_khau:
        if not validate_password_complexity(data.mat_khau):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Mật khẩu tài khoản phải có tối thiểu 8 ký tự gồm cả chữ và số"
            )
        if db.query(TaiKhoan).filter(TaiKhoan.ten_dang_nhap == data.ten_dang_nhap).first():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Tên đăng nhập '{data.ten_dang_nhap}' đã tồn tại"
            )
        tk = TaiKhoan(
            ma_nv=nv.id,
            ma_vai_tro=data.ma_vai_tro or 3,
            ten_dang_nhap=data.ten_dang_nhap,
            mat_khau=get_password_hash(data.mat_khau),
            is_active=True
        )
        db.add(tk)

    db.commit()
    db.refresh(nv)
    return map_nhan_vien_response(nv)

@router.put("/{employee_id}", response_model=NhanVienResponse)
def update_employee(
    employee_id: int,
    data: NhanVienUpdate,
    current_user: TaiKhoan = Depends(require_roles(["Admin", "Manager"])),
    db: Session = Depends(get_db)
):
    """
    FR-04: Cập nhật thông tin hồ sơ nhân sự
    """
    nv = db.query(NhanVien).filter(NhanVien.id == employee_id).first()
    if not nv:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Không tìm thấy hồ sơ nhân viên")

    update_fields = data.model_dump(exclude_unset=True)
    for field, value in update_fields.items():
        setattr(nv, field, value)

    # Nếu đổi trạng thái sang 'da_nghi', cập nhật tài khoản thành inactive (FR-06)
    if data.trang_thai == "da_nghi" and nv.tai_khoan:
        nv.tai_khoan.is_active = False

    db.commit()
    db.refresh(nv)
    return map_nhan_vien_response(nv)

@router.patch("/{employee_id}/status", response_model=NhanVienResponse)
def change_employee_status(
    employee_id: int,
    data: NhanVienStatusUpdate,
    current_user: TaiKhoan = Depends(require_roles(["Admin", "Manager"])),
    db: Session = Depends(get_db)
):
    """
    FR-06: Cập nhật trạng thái làm việc (dang_lam, nghi_phep, da_nghi)
    - Nếu trạng thái là 'da_nghi': Tự động vô hiệu hóa tài khoản đăng nhập
    """
    nv = db.query(NhanVien).filter(NhanVien.id == employee_id).first()
    if not nv:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Không tìm thấy hồ sơ nhân viên")

    nv.trang_thai = data.trang_thai
    if data.trang_thai == "da_nghi" and nv.tai_khoan:
        nv.tai_khoan.is_active = False

    db.commit()
    db.refresh(nv)
    return map_nhan_vien_response(nv)

@router.delete("/{employee_id}")
def delete_employee(
    employee_id: int,
    current_user: TaiKhoan = Depends(require_roles(["Admin", "Manager"])),
    db: Session = Depends(get_db)
):
    """
    FR-04: Xóa mềm hồ sơ nhân sự (soft delete)
    Bảo toàn toàn vẹn dữ liệu cho lịch sử chấm công và tính lương
    """
    nv = db.query(NhanVien).filter(NhanVien.id == employee_id).first()
    if not nv:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Không tìm thấy hồ sơ nhân viên")

    nv.is_deleted = True
    if nv.tai_khoan:
        nv.tai_khoan.is_active = False

    db.commit()
    return {"message": f"Đã xóa mềm hồ sơ nhân viên '{nv.ho_ten}' (dữ liệu lịch sử vẫn được bảo toàn)"}

@router.post("/{employee_id}/restore", response_model=NhanVienResponse)
def restore_employee(
    employee_id: int,
    current_user: TaiKhoan = Depends(require_roles(["Admin", "Manager"])),
    db: Session = Depends(get_db)
):
    """Khôi phục hồ sơ nhân viên đã xóa mềm"""
    nv = db.query(NhanVien).filter(NhanVien.id == employee_id).first()
    if not nv:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Không tìm thấy hồ sơ nhân viên")

    nv.is_deleted = False
    db.commit()
    db.refresh(nv)
    return map_nhan_vien_response(nv)
