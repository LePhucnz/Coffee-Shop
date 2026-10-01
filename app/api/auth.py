from typing import List, Optional
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, status, Request
from sqlalchemy.orm import Session
from app.database import get_db
from app.core.deps import get_current_user, require_roles
from app.core.security import (
    decode_token, create_access_token, get_password_hash,
    create_reset_token, validate_password_complexity
)
from app.models.user import TaiKhoan, LichSuDangNhap
from app.schemas.auth import (
    LoginRequest, TokenResponse, RefreshTokenRequest,
    RegisterRequest, UserResponse, LoginHistoryResponse, ToggleActiveRequest,
    ForgotPasswordRequest, ForgotPasswordResponse,
    ResetPasswordRequest, ResetPasswordResponse
)
from app.services.auth_service import AuthService
from app.config import settings

router = APIRouter(prefix="/api/auth", tags=["Xác thực & Phân quyền (Auth)"])

def get_client_ip(request: Request) -> str:
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "127.0.0.1"

@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
def register(data: RegisterRequest, db: Session = Depends(get_db)):
    """
    FR-01: Đăng ký tài khoản người dùng mới
    - Mật khẩu tối thiểu 8 ký tự, gồm cả chữ và số
    - Mã hóa băm bcrypt trước khi lưu
    - Chống trùng lặp tên đăng nhập, email, số điện thoại
    """
    ten_dang_nhap = data.ten_dang_nhap
    if not ten_dang_nhap:
        if data.email:
            base_name = data.email.split("@")[0].lower()
            # Đảm bảo tối thiểu 3 ký tự
            if len(base_name) :
                base_name = f"{base_name}"
            ten_dang_nhap = base_name
        elif data.ho_ten:
            ten_dang_nhap = data.ho_ten.lower().replace(" ", "")
        else:
            ten_dang_nhap = f"user_{datetime.utcnow().strftime('%y%m%d%H%M%S')}"

    user, err = AuthService.register_account(
        db=db,
        ten_dang_nhap=ten_dang_nhap,
        mat_khau=data.mat_khau,
        ho_ten=data.ho_ten,
        email=data.email,
        so_dien_thoai=data.so_dien_thoai,
        ma_vai_tro=data.ma_vai_tro or 3,
        ma_cua_hang=data.ma_cua_hang,
        ma_vi_tri=data.ma_vi_tri
    )
    if err:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=err)

    return UserResponse(
        id=user.id,
        ten_dang_nhap=user.ten_dang_nhap,
        is_active=user.is_active,
        ma_vai_tro=user.ma_vai_tro,
        ten_vai_tro=user.vai_tro.ten_vai_tro if user.vai_tro else None,
        ma_nv=user.ma_nv,
        ho_ten=user.nhan_vien.ho_ten if user.nhan_vien else None,
        email=user.nhan_vien.email if user.nhan_vien else None,
        so_dien_thoai=user.nhan_vien.so_dien_thoai if user.nhan_vien else None,
        trang_thai_nhan_vien=user.nhan_vien.trang_thai if user.nhan_vien else None
    )

@router.post("/forgot-password", response_model=ForgotPasswordResponse)
def forgot_password(data: ForgotPasswordRequest, db: Session = Depends(get_db)):
    """
    Xử lý yêu cầu quên mật khẩu:
    - Kiểm tra email tồn tại trong hệ thống
    - Sinh mã reset token bảo mật (hạn dùng 15 phút)
    - Trả về thông báo kèm reset_token và reset_url
    """
    email = data.email.strip().lower()
    from app.models.employee import NhanVien
    user = db.query(TaiKhoan).outerjoin(NhanVien, TaiKhoan.ma_nv == NhanVien.id).filter(
        NhanVien.email == email
    ).first()

    if not user:
        return ForgotPasswordResponse(
            success=True,
            message=f"Nếu email {email} tồn tại trong hệ thống, hướng dẫn đặt lại mật khẩu đã được gửi đến hộp thư.",
            reset_token=None,
            reset_url=None
        )

    reset_token = create_reset_token(email)
    reset_url = f"/reset-password?token={reset_token}"

    return ForgotPasswordResponse(
        success=True,
        message=f"Liên kết đặt lại mật khẩu đã được gửi đến email {email}. Vui lòng kiểm tra hộp thư.",
        reset_token=reset_token,
        reset_url=reset_url
    )

@router.post("/reset-password", response_model=ResetPasswordResponse)
def reset_password(data: ResetPasswordRequest, db: Session = Depends(get_db)):
    """
    Đặt lại mật khẩu mới:
    - Hỗ trợ xác thực qua token hoặc email
    - Kiểm tra độ phức tạp mật khẩu mới (≥ 8 ký tự, gồm cả chữ và số)
    - Cập nhật mật khẩu băm bcrypt và mở khóa tài khoản
    """
    if not validate_password_complexity(data.mat_khau):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Mật khẩu phải có độ dài tối thiểu 8 ký tự và bao gồm cả chữ cái lẫn chữ số"
        )
    
    target_email = None
    if data.token:
        payload = decode_token(data.token)
        if not payload or payload.get("type") != "reset_password":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Mã token đặt lại mật khẩu không hợp lệ hoặc đã hết hạn"
            )
        target_email = payload.get("sub")
    elif data.email:
        target_email = data.email.strip().lower()
    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Vui lòng cung cấp mã token hoặc email để đặt lại mật khẩu"
        )

    from app.models.employee import NhanVien
    user = db.query(TaiKhoan).outerjoin(NhanVien, TaiKhoan.ma_nv == NhanVien.id).filter(
        NhanVien.email == target_email
    ).first()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Không tìm thấy tài khoản liên kết với email '{target_email}'"
        )

    user.mat_khau = get_password_hash(data.mat_khau)
    user.so_lan_dang_nhap_sai = 0
    user.lockout_until = None
    db.commit()

    return ResetPasswordResponse(
        success=True,
        message="Đặt lại mật khẩu thành công! Bạn có thể đăng nhập ngay bây giờ."
    )


@router.post("/login", response_model=TokenResponse)
def login(data: LoginRequest, request: Request, db: Session = Depends(get_db)):
    """
    FR-02: Đăng nhập / Xác thực
    - Đăng nhập bằng tên đăng nhập, email hoặc số điện thoại
    - Trả về JWT Access Token và Refresh Token
    - Khóa tài khoản 15 phút nếu sai quá 5 lần liên tiếp
    - Ghi log lịch sử đăng nhập kèm IP
    """
    ip = get_client_ip(request)
    user, err, token_data = AuthService.authenticate_user(
        db=db,
        login_identifier=data.ten_dang_nhap,
        password=data.mat_khau,
        client_ip=ip
    )
    if err:
        # Nếu bị khóa hoặc vô hiệu hóa thì trả về 403, ngược lại 400
        if "tạm khóa" in err or "vô hiệu hóa" in err or "Đã nghỉ việc" in err:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=err)
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=err)

    user_resp = UserResponse(
        id=user.id,
        ten_dang_nhap=user.ten_dang_nhap,
        is_active=user.is_active,
        ma_vai_tro=user.ma_vai_tro,
        ten_vai_tro=user.vai_tro.ten_vai_tro if user.vai_tro else None,
        ma_nv=user.ma_nv,
        ho_ten=user.nhan_vien.ho_ten if user.nhan_vien else None,
        email=user.nhan_vien.email if user.nhan_vien else None,
        so_dien_thoai=user.nhan_vien.so_dien_thoai if user.nhan_vien else None,
        trang_thai_nhan_vien=user.nhan_vien.trang_thai if user.nhan_vien else None
    )

    return TokenResponse(
        access_token=token_data["access_token"],
        refresh_token=token_data["refresh_token"],
        token_type="bearer",
        expires_in=token_data["expires_in"],
        user=user_resp
    )

@router.post("/refresh")
def refresh_token(data: RefreshTokenRequest, db: Session = Depends(get_db)):
    """Làm mới Access Token bằng Refresh Token hợp lệ"""
    payload = decode_token(data.refresh_token)
    if not payload or payload.get("type") != "refresh":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Refresh token không hợp lệ hoặc đã hết hạn"
        )
    username = payload.get("sub")
    user = db.query(TaiKhoan).filter(TaiKhoan.ten_dang_nhap == username).first()
    if not user or not user.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Người dùng không hợp lệ")

    role_name = user.vai_tro.ten_vai_tro if user.vai_tro else "Staff"
    new_payload = {
        "sub": user.ten_dang_nhap,
        "user_id": user.id,
        "role": role_name,
        "nv_id": user.ma_nv
    }
    new_access_token = create_access_token(new_payload)
    return {
        "access_token": new_access_token,
        "token_type": "bearer",
        "expires_in": settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60
    }

@router.get("/me", response_model=UserResponse)
def get_me(current_user: TaiKhoan = Depends(get_current_user)):
    """Lấy thông tin tài khoản đang đăng nhập"""
    return UserResponse(
        id=current_user.id,
        ten_dang_nhap=current_user.ten_dang_nhap,
        is_active=current_user.is_active,
        ma_vai_tro=current_user.ma_vai_tro,
        ten_vai_tro=current_user.vai_tro.ten_vai_tro if current_user.vai_tro else None,
        ma_nv=current_user.ma_nv,
        ho_ten=current_user.nhan_vien.ho_ten if current_user.nhan_vien else None,
        email=current_user.nhan_vien.email if current_user.nhan_vien else None,
        so_dien_thoai=current_user.nhan_vien.so_dien_thoai if current_user.nhan_vien else None,
        trang_thai_nhan_vien=current_user.nhan_vien.trang_thai if current_user.nhan_vien else None
    )

@router.get("/login-history", response_model=List[LoginHistoryResponse])
def get_login_history(
    current_user: TaiKhoan = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    FR-02: Lịch sử đăng nhập
    - Staff xem lịch sử của chính mình
    - Admin/Manager xem lịch sử gần đây của toàn hệ thống
    """
    role_name = current_user.vai_tro.ten_vai_tro if current_user.vai_tro else "Staff"
    if role_name in ["Admin", "Manager"]:
        logs = db.query(LichSuDangNhap).order_by(LichSuDangNhap.thoi_gian_dang_nhap.desc()).limit(50).all()
    else:
        logs = db.query(LichSuDangNhap).filter(
            LichSuDangNhap.ma_tai_khoan == current_user.id
        ).order_by(LichSuDangNhap.thoi_gian_dang_nhap.desc()).limit(20).all()

    return logs

@router.patch("/users/{user_id}/status", response_model=UserResponse)
def toggle_user_active(
    user_id: int,
    data: ToggleActiveRequest,
    current_user: TaiKhoan = Depends(require_roles(["Admin", "Manager"])),
    db: Session = Depends(get_db)
):
    """
    FR-03: Kích hoạt / Vô hiệu hóa tài khoản nhân viên (Admin/Manager)
    """
    user = db.query(TaiKhoan).filter(TaiKhoan.id == user_id).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Không tìm thấy tài khoản")
    
    # Không thể tự vô hiệu hóa tài khoản của chính mình
    if user.id == current_user.id and not data.is_active:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Không thể tự vô hiệu hóa tài khoản của chính mình")

    user.is_active = data.is_active
    db.commit()
    db.refresh(user)

    return UserResponse(
        id=user.id,
        ten_dang_nhap=user.ten_dang_nhap,
        is_active=user.is_active,
        ma_vai_tro=user.ma_vai_tro,
        ten_vai_tro=user.vai_tro.ten_vai_tro if user.vai_tro else None,
        ma_nv=user.ma_nv,
        ho_ten=user.nhan_vien.ho_ten if user.nhan_vien else None,
        email=user.nhan_vien.email if user.nhan_vien else None,
        so_dien_thoai=user.nhan_vien.so_dien_thoai if user.nhan_vien else None,
        trang_thai_nhan_vien=user.nhan_vien.trang_thai if user.nhan_vien else None
    )
