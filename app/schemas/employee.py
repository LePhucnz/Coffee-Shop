from typing import Optional, List
from datetime import date, datetime
from pydantic import BaseModel, Field

class NhanVienBase(BaseModel):
    ma_nhan_vien: Optional[str] = None
    ma_cua_hang: Optional[int] = None
    ma_vi_tri: Optional[int] = None
    ho_ten: str = Field(..., min_length=2, max_length=100)
    so_dien_thoai: Optional[str] = None
    email: Optional[str] = None
    dia_chi: Optional[str] = None
    cccd: Optional[str] = None
    ngay_sinh: Optional[date] = None
    gioi_tinh: Optional[str] = None
    tinh_trang_hon_nhan: Optional[str] = None
    so_nhan_khau: Optional[int] = 0
    ngay_vao_lam: Optional[date] = None
    anh_dai_dien: Optional[str] = None
    trang_thai: Optional[str] = "dang_lam"  # 'dang_lam', 'nghi_phep', 'da_nghi'

class NhanVienCreate(NhanVienBase):
    tao_tai_khoan: Optional[bool] = False
    ten_dang_nhap: Optional[str] = None
    mat_khau: Optional[str] = None
    ma_vai_tro: Optional[int] = 3

class NhanVienUpdate(BaseModel):
    ma_nhan_vien: Optional[str] = None
    ma_cua_hang: Optional[int] = None
    ma_vi_tri: Optional[int] = None
    ho_ten: Optional[str] = None
    so_dien_thoai: Optional[str] = None
    email: Optional[str] = None
    dia_chi: Optional[str] = None
    cccd: Optional[str] = None
    ngay_sinh: Optional[date] = None
    gioi_tinh: Optional[str] = None
    tinh_trang_hon_nhan: Optional[str] = None
    so_nhan_khau: Optional[int] = None
    ngay_vao_lam: Optional[date] = None
    anh_dai_dien: Optional[str] = None
    trang_thai: Optional[str] = Field(None, pattern="^(dang_lam|nghi_phep|da_nghi)$")

class NhanVienStatusUpdate(BaseModel):
    trang_thai: str = Field(..., pattern="^(dang_lam|nghi_phep|da_nghi)$")

class NhanVienResponse(NhanVienBase):
    id: int
    is_deleted: bool
    ngay_tao: Optional[datetime] = None
    ten_cua_hang: Optional[str] = None
    ten_vi_tri: Optional[str] = None
    ten_dang_nhap: Optional[str] = None

    model_config = {"from_attributes": True}

class NhanVienListResponse(BaseModel):
    total: int
    items: List[NhanVienResponse]
