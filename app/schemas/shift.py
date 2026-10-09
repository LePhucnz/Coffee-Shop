from typing import Optional, List
from datetime import date, time, datetime
from pydantic import BaseModel, Field, model_validator


# ---------- Loại ca (FR-08: cấu hình nhu cầu nhân lực) ----------

class LoaiCaBase(BaseModel):
    ten_ca: str = Field(..., min_length=2, max_length=100)
    gio_bat_dau: time
    gio_ket_thuc: time
    so_nv_toi_thieu: int = Field(1, ge=0, le=50)
    so_nv_toi_da: int = Field(3, ge=1, le=50)
    mo_ta: Optional[str] = None
    trang_thai: bool = True

    @model_validator(mode="after")
    def check_range(self):
        if self.so_nv_toi_da < self.so_nv_toi_thieu:
            raise ValueError("Số nhân viên tối đa phải lớn hơn hoặc bằng số tối thiểu")
        if self.gio_bat_dau == self.gio_ket_thuc:
            raise ValueError("Giờ bắt đầu và giờ kết thúc không được trùng nhau")
        return self


class LoaiCaCreate(LoaiCaBase):
    ma_loai_ca: str = Field(..., min_length=2, max_length=50, pattern=r"^[A-Za-z0-9_]+$")


class LoaiCaUpdate(LoaiCaBase):
    pass


class LoaiCaResponse(BaseModel):
    id: int
    ma_loai_ca: str
    ten_ca: Optional[str] = None
    gio_bat_dau: Optional[time] = None
    gio_ket_thuc: Optional[time] = None
    so_nv_toi_thieu: Optional[int] = None
    so_nv_toi_da: Optional[int] = None
    mo_ta: Optional[str] = None
    trang_thai: bool = True
    so_gio: float = 0

    model_config = {"from_attributes": True}


# ---------- Đăng ký nguyện vọng (FR-07) ----------

class DangKyItem(BaseModel):
    ngay: date
    ma_ca: int


class DangKyTuanRequest(BaseModel):
    tuan_bat_dau: date
    dang_ky: List[DangKyItem] = []


class DangKyTuanResponse(BaseModel):
    tuan_bat_dau: date
    tuan_ket_thuc: date
    han_chot: datetime
    con_mo: bool
    loai_ca: List[LoaiCaResponse]
    dang_ky: List[DangKyItem]


# ---------- Bảng xếp ca (FR-08, FR-09) ----------

class XungDot(BaseModel):
    loai: str
    muc_do: str  # 'loi' | 'canh_bao'
    thong_bao: str


class PhanCongCreate(BaseModel):
    ma_nv: int
    ma_ca: int
    ngay_lam: date


class PhanCongResponse(BaseModel):
    id: int
    ma_nv: int
    ho_ten: Optional[str] = None
    ma_nhan_vien: Optional[str] = None
    ma_ca: int
    ngay_lam: date
    so_gio: float = 0
    theo_nguyen_vong: bool = False
    xung_dot: List[XungDot] = []


class NhanVienRutGon(BaseModel):
    ma_nv: int
    ho_ten: str
    ma_nhan_vien: Optional[str] = None


class OCa(BaseModel):
    ngay: date
    ma_ca: int
    so_nguoi: int
    toi_thieu: int
    toi_da: Optional[int] = None
    nguyen_vong: List[NhanVienRutGon] = []
    canh_bao: List[XungDot] = []


class TongGioNhanVien(BaseModel):
    ma_nv: int
    ho_ten: str
    so_ca: int
    so_gio: float


class BangXepCaResponse(BaseModel):
    tuan_bat_dau: date
    tuan_ket_thuc: date
    ngay: List[date]
    trang_thai: str  # 'chua_tao' | 'nhap' | 'da_cong_bo'
    ngay_cong_bo: Optional[datetime] = None
    han_chot_dang_ky: datetime
    loai_ca: List[LoaiCaResponse]
    phan_cong: List[PhanCongResponse]
    o_ca: List[OCa]
    tong_gio: List[TongGioNhanVien]
    so_loi: int
    so_canh_bao: int
    co_the_cong_bo: bool


class TuanRequest(BaseModel):
    tuan_bat_dau: date


# ---------- Lịch làm cá nhân ----------

class CaCuaToi(BaseModel):
    id: int
    ngay_lam: date
    ma_ca: int
    ten_ca: Optional[str] = None
    gio_bat_dau: Optional[time] = None
    gio_ket_thuc: Optional[time] = None
    so_gio: float = 0


class LichCuaToiResponse(BaseModel):
    tuan_bat_dau: date
    tuan_ket_thuc: date
    da_cong_bo: bool
    ngay_cong_bo: Optional[datetime] = None
    ca: List[CaCuaToi]
    tong_gio: float


# ---------- Thông báo ----------

class ThongBaoResponse(BaseModel):
    id: int
    tieu_de: str
    noi_dung: Optional[str] = None
    lien_ket: Optional[str] = None
    da_doc: bool
    ngay_tao: datetime

    model_config = {"from_attributes": True}


class DanhSachThongBao(BaseModel):
    so_chua_doc: int
    items: List[ThongBaoResponse]
