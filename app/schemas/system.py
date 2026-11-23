from typing import Optional
from datetime import datetime
from pydantic import BaseModel, Field

class CuaHangBase(BaseModel):
    ten_cua_hang: str = Field(..., min_length=2, max_length=100)
    dia_chi: Optional[str] = Field(None, max_length=255)
    vi_do: Optional[float] = Field(None, ge=-90, le=90)
    kinh_do: Optional[float] = Field(None, ge=-180, le=180)
    trang_thai: bool = True

class CuaHangCreate(CuaHangBase):
    pass

class CuaHangUpdate(BaseModel):
    ten_cua_hang: Optional[str] = Field(None, min_length=2, max_length=100)
    dia_chi: Optional[str] = Field(None, max_length=255)
    vi_do: Optional[float] = Field(None, ge=-90, le=90)
    kinh_do: Optional[float] = Field(None, ge=-180, le=180)
    trang_thai: Optional[bool] = None

class CuaHangResponse(BaseModel):
    id: int
    ten_cua_hang: str
    dia_chi: Optional[str] = None
    vi_do: Optional[float] = None
    kinh_do: Optional[float] = None
    trang_thai: bool

    model_config = {"from_attributes": True}

class ViTriBase(BaseModel):
    ten_vi_tri: str = Field(..., min_length=2, max_length=100)
    mo_ta: Optional[str] = Field(None, max_length=255)

class ViTriCreate(ViTriBase):
    pass

class ViTriUpdate(BaseModel):
    ten_vi_tri: Optional[str] = Field(None, min_length=2, max_length=100)
    mo_ta: Optional[str] = Field(None, max_length=255)

class ViTriResponse(BaseModel):
    id: int
    ten_vi_tri: str
    mo_ta: Optional[str] = None

    model_config = {"from_attributes": True}

class VaiTroResponse(BaseModel):
    id: int
    ten_vai_tro: str
    mo_ta: Optional[str] = None

    model_config = {"from_attributes": True}

class NhatKyHeThongResponse(BaseModel):
    id: int
    ma_tai_khoan: int
    ma_cua_hang: Optional[int] = None
    hanh_dong: str
    thoi_gian: datetime
    ly_do: Optional[str] = None
    trang_thai: Optional[str] = None
    ten_nguoi_dung: Optional[str] = None

    model_config = {"from_attributes": True}
