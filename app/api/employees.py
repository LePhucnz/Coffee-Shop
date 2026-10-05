from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, status, Query, UploadFile, File
from sqlalchemy.orm import Session
from sqlalchemy import or_, func
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
from app.services.file_service import save_upload, IMAGE_EXTENSIONS

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

def sync_account_active(nv: NhanVien):
    """
    FR-06 / BR-05: Tài khoản chỉ hoạt động khi hồ sơ chưa bị xóa mềm
    và nhân viên chưa nghỉ việc. Khôi phục / quay lại làm sẽ mở lại tài khoản.
    """
    if nv.tai_khoan:
        nv.tai_khoan.is_active = (not nv.is_deleted) and nv.trang_thai != "da_nghi"

def check_duplicate_contact(db: Session, email: Optional[str], so_dien_thoai: Optional[str], exclude_id: Optional[int] = None):
    """FR-01/FR-04: Không cho trùng email / số điện thoại giữa các hồ sơ"""
    if email:
        q = db.query(NhanVien).filter(NhanVien.email == email)
        if exclude_id:
            q = q.filter(NhanVien.id != exclude_id)
        if q.first():
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Email '{email}' đã được sử dụng")
    if so_dien_thoai:
        q = db.query(NhanVien).filter(NhanVien.so_dien_thoai == so_dien_thoai)
        if exclude_id:
            q = q.filter(NhanVien.id != exclude_id)
        if q.first():
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Số điện thoại '{so_dien_thoai}' đã được sử dụng")

def get_employee_or_404(db: Session, employee_id: int) -> NhanVien:
    nv = db.query(NhanVien).filter(NhanVien.id == employee_id).first()
    if not nv:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Không tìm thấy hồ sơ nhân viên")
    return nv

@router.get("", response_model=NhanVienListResponse)
def list_employees(
    keyword: Optional[str] = Query(None, description="Tìm kiếm theo họ tên, mã NV, email, SĐT, CCCD hoặc vị trí"),
    ma_vi_tri: Optional[int] = Query(None, description="Lọc theo ID vị trí công việc"),
    vi_tri: Optional[str] = Query(None, description="Lọc theo tên vị trí công việc (vd: Pha chế, Phục vụ, Thu ngân)"),
    ma_cua_hang: Optional[int] = Query(None, description="Lọc theo cửa hàng"),
    trang_thai: Optional[str] = Query(None, description="Lọc theo trạng thái (dang_lam, nghi_phep, da_nghi)"),
    include_deleted: bool = Query(False, description="Bao gồm cả hồ sơ đã xóa mềm / lưu trữ"),
    current_user: TaiKhoan = Depends(require_roles(["Admin", "Manager"])),
    db: Session = Depends(get_db)
):
    """
    FR-04, FR-06: Danh sách hồ sơ nhân sự
    - Tìm kiếm theo họ tên, mã, email, SĐT, CCCD, vị trí
    - Lọc theo vị trí (ID hoặc tên), cửa hàng, trạng thái
    - Mặc định ẩn hồ sơ đã xóa mềm (soft delete / archive)
    """
    query = db.query(NhanVien).outerjoin(ViTri, NhanVien.ma_vi_tri == ViTri.id)

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
                NhanVien.cccd.ilike(kw),
                ViTri.ten_vi_tri.ilike(kw)
            )
        )

    if ma_vi_tri:
        query = query.filter(NhanVien.ma_vi_tri == ma_vi_tri)

    if vi_tri:
        query = query.filter(ViTri.ten_vi_tri.ilike(f"%{vi_tri.strip()}%"))

    if ma_cua_hang:
        query = query.filter(NhanVien.ma_cua_hang == ma_cua_hang)

    if trang_thai:
        query = query.filter(NhanVien.trang_thai == trang_thai)

    items = query.order_by(NhanVien.id.desc()).all()
    return NhanVienListResponse(
        total=len(items),
        items=[map_nhan_vien_response(item) for item in items]
    )

@router.get("/schedulable", response_model=List[NhanVienResponse])
def list_schedulable_employees(
    current_user: TaiKhoan = Depends(require_roles(["Admin", "Manager"])),
    db: Session = Depends(get_db)
):
    """
    FR-06 / BR-05: Danh sách nhân viên được phép xếp ca (dùng cho Sprint 4)
    - Chỉ gồm hồ sơ chưa xóa mềm và đang ở trạng thái 'dang_lam'
    """
    items = db.query(NhanVien).filter(
        NhanVien.is_deleted == False,
        NhanVien.trang_thai == "dang_lam"
    ).order_by(NhanVien.ho_ten).all()
    return [map_nhan_vien_response(nv) for nv in items]

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
        # Dựa trên id lớn nhất (không dùng count) để tránh trùng mã
        next_id = (db.query(func.max(NhanVien.id)).scalar() or 0) + 1
        ma_nv = f"NV{next_id:03d}"
        while db.query(NhanVien).filter(NhanVien.ma_nhan_vien == ma_nv).first():
            next_id += 1
            ma_nv = f"NV{next_id:03d}"
    else:
        existing = db.query(NhanVien).filter(NhanVien.ma_nhan_vien == ma_nv).first()
        if existing:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Mã nhân viên '{ma_nv}' đã tồn tại")

    check_duplicate_contact(db, data.email, data.so_dien_thoai)

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
    nv = get_employee_or_404(db, employee_id)

    check_duplicate_contact(db, data.email, data.so_dien_thoai, exclude_id=employee_id)
    if data.ma_nhan_vien and data.ma_nhan_vien != nv.ma_nhan_vien:
        if db.query(NhanVien).filter(NhanVien.ma_nhan_vien == data.ma_nhan_vien).first():
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Mã nhân viên '{data.ma_nhan_vien}' đã tồn tại")

    update_fields = data.model_dump(exclude_unset=True)
    for field, value in update_fields.items():
        setattr(nv, field, value)

    # FR-06: 'da_nghi' khóa tài khoản, quay lại 'dang_lam'/'nghi_phep' thì mở lại
    sync_account_active(nv)

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
    - Nếu chuyển lại 'dang_lam' / 'nghi_phep': Mở lại tài khoản
    """
    nv = get_employee_or_404(db, employee_id)

    nv.trang_thai = data.trang_thai
    sync_account_active(nv)

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
    FR-04: Xóa mềm / vô hiệu hóa hồ sơ nhân sự (soft delete)
    Bảo toàn toàn vẹn dữ liệu cho lịch sử chấm công và tính lương
    """
    nv = get_employee_or_404(db, employee_id)

    nv.is_deleted = True
    sync_account_active(nv)

    db.commit()
    return {"message": f"Đã vô hiệu hóa (xóa mềm) hồ sơ nhân viên '{nv.ho_ten}' (dữ liệu lịch sử vẫn được bảo toàn)"}

@router.post("/{employee_id}/archive", response_model=NhanVienResponse)
def archive_employee(
    employee_id: int,
    current_user: TaiKhoan = Depends(require_roles(["Admin", "Manager"])),
    db: Session = Depends(get_db)
):
    """
    FR-04: Lưu trữ (archive / vô hiệu hóa) hồ sơ nhân sự (soft delete)
    Bảo toàn toàn vẹn dữ liệu cho lịch sử chấm công và tính lương
    """
    nv = get_employee_or_404(db, employee_id)

    nv.is_deleted = True
    sync_account_active(nv)

    db.commit()
    db.refresh(nv)
    return map_nhan_vien_response(nv)

@router.post("/{employee_id}/restore", response_model=NhanVienResponse)
def restore_employee(
    employee_id: int,
    current_user: TaiKhoan = Depends(require_roles(["Admin", "Manager"])),
    db: Session = Depends(get_db)
):
    """Khôi phục hồ sơ nhân viên đã xóa mềm / lưu trữ (mở lại tài khoản nếu chưa nghỉ việc)"""
    nv = get_employee_or_404(db, employee_id)

    nv.is_deleted = False
    sync_account_active(nv)
    db.commit()
    db.refresh(nv)
    return map_nhan_vien_response(nv)

@router.post("/{employee_id}/unarchive", response_model=NhanVienResponse)
def unarchive_employee(
    employee_id: int,
    current_user: TaiKhoan = Depends(require_roles(["Admin", "Manager"])),
    db: Session = Depends(get_db)
):
    """Khôi phục hồ sơ nhân viên đã lưu trữ (unarchive)"""
    return restore_employee(employee_id, current_user, db)

@router.post("/{employee_id}/avatar", response_model=NhanVienResponse)
def upload_avatar(
    employee_id: int,
    file: UploadFile = File(...),
    current_user: TaiKhoan = Depends(require_roles(["Admin", "Manager"])),
    db: Session = Depends(get_db)
):
    """FR-04: Tải lên ảnh đại diện nhân viên (jpg, png, webp; tối đa 5MB)"""
    nv = get_employee_or_404(db, employee_id)
    nv.anh_dai_dien = save_upload(file, "avatars", IMAGE_EXTENSIONS)
    db.commit()
    db.refresh(nv)
    return map_nhan_vien_response(nv)
