from typing import Optional, List
from datetime import date, datetime
from decimal import Decimal
from pydantic import BaseModel, Field

class HopDongBase(BaseModel):
    ma_nhan_vien: int
    loai_hop_dong: str = Field(..., description="Toàn thời gian, Bán thời gian, Thử việc, Thời vụ")
    ngay_bat_dau: Optional[date] = None
    ngay_ket_thuc: Optional[date] = None
    muc_luong: Optional[Decimal] = None
    ma_bang_luong: Optional[str] = None
    file_dinh_kem: Optional[str] = None
    trang_thai: Optional[str] = "hieu_luc"

class HopDongCreate(HopDongBase):
    pass

class HopDongUpdate(BaseModel):
    loai_hop_dong: Optional[str] = None
    ngay_bat_dau: Optional[date] = None
    ngay_ket_thuc: Optional[date] = None
    muc_luong: Optional[Decimal] = None
    ma_bang_luong: Optional[str] = None
    file_dinh_kem: Optional[str] = None
    trang_thai: Optional[str] = None

class HopDongResponse(HopDongBase):
    id: int
    ngay_tao: Optional[datetime] = None
    ho_ten_nhan_vien: Optional[str] = None
    ma_nhan_vien_code: Optional[str] = None
    so_ngay_con_lai: Optional[int] = None
    canh_bao_het_han: Optional[bool] = False

    model_config = {"from_attributes": True}

class HopDongExpiringAlert(BaseModel):
    id: int
    ma_nhan_vien: int
    ho_ten: str
    ma_nhan_vien_code: Optional[str] = None
    loai_hop_dong: Optional[str] = None
    ngay_ket_thuc: date
    so_ngay_con_lai: int
    muc_luong: Optional[Decimal] = None
