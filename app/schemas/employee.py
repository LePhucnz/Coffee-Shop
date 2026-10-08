import re
from typing import Optional, List
from datetime import date, datetime
from pydantic import BaseModel, Field, field_validator

class NhanVienValidationMixin(BaseModel):
    @field_validator("cccd", check_fields=False)
    @classmethod
    def validate_cccd(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return None
        v = v.strip()
        if not v:
            return None
        if not re.match(r"^(\d{9}|\d{12})$", v):
            raise ValueError("CCCD/CMND chỉ được chứa chữ số và phải gồm 9 hoặc 12 số")
        return v

    @field_validator("so_dien_thoai", check_fields=False)
    @classmethod
    def validate_so_dien_thoai(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return None
        v = v.strip()
        if not v:
            return None
        cleaned = re.sub(r"[\s.-]", "", v)
        if not re.match(r"^(?:0|\+84)\d{9}$", cleaned):
            raise ValueError("Số điện thoại không hợp lệ (phải gồm 10 chữ số bắt đầu bằng số 0 và không chứa chữ cái)")
        return cleaned

    @field_validator("ngay_sinh", check_fields=False)
    @classmethod
    def validate_ngay_sinh(cls, v: Optional[date]) -> Optional[date]:
        if v is not None:
            if v >= date.today():
                raise ValueError("Ngày sinh phải trước ngày hôm nay (không được là ngày hôm nay hoặc tương lai)")
            if v.year < 1900:
                raise ValueError("Năm sinh không hợp lệ")
        return v

class NhanVienBase(NhanVienValidationMixin):
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

class NhanVienUpdate(NhanVienValidationMixin):
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
