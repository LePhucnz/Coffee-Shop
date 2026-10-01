from typing import Optional
from datetime import datetime
from pydantic import BaseModel, Field

class LoginRequest(BaseModel):
    ten_dang_nhap: str = Field(..., description="Tên đăng nhập, email hoặc số điện thoại")
    mat_khau: str = Field(..., description="Mật khẩu tài khoản")

class RefreshTokenRequest(BaseModel):
    refresh_token: str

class RegisterRequest(BaseModel):
    ten_dang_nhap: Optional[str] = Field(None, max_length=50)
    mat_khau: str = Field(..., min_length=8, description="Tối thiểu 8 ký tự gồm cả chữ và số")
    ho_ten: str = Field(..., min_length=2, max_length=100)
    email: Optional[str] = None
    so_dien_thoai: Optional[str] = None
    ma_vai_tro: Optional[int] = 3  # Mặc định Staff
    ma_cua_hang: Optional[int] = None
    ma_vi_tri: Optional[int] = None

class ForgotPasswordRequest(BaseModel):
    email: str

class ResetPasswordRequest(BaseModel):
    email: Optional[str] = None
    mat_khau: str = Field(..., min_length=8, description="Tối thiểu 8 ký tự")

class UserResponse(BaseModel):
    id: int
    ten_dang_nhap: str
    is_active: bool
    ma_vai_tro: Optional[int] = None
    ten_vai_tro: Optional[str] = None
    ma_nv: Optional[int] = None
    ho_ten: Optional[str] = None
    email: Optional[str] = None
    so_dien_thoai: Optional[str] = None
    trang_thai_nhan_vien: Optional[str] = None

    model_config = {"from_attributes": True}

class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int
    user: UserResponse

class LoginHistoryResponse(BaseModel):
    id: int
    thoi_gian_dang_nhap: datetime
    dia_chi_ip: Optional[str]
    trang_thai: Optional[str]

    model_config = {"from_attributes": True}

class ToggleActiveRequest(BaseModel):
    is_active: bool
