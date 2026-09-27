from typing import Optional
from pydantic import BaseModel

class CuaHangResponse(BaseModel):
    id: int
    ten_cua_hang: str
    dia_chi: Optional[str] = None
    vi_do: Optional[float] = None
    kinh_do: Optional[float] = None
    trang_thai: bool

    model_config = {"from_attributes": True}

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
