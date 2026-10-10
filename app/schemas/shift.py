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


# ---------- Mở rộng FR-07: Đăng ký nguyện vọng theo tháng ----------

class TuanInfo(BaseModel):
    tuan_bat_dau: date
    tuan_ket_thuc: date
    han_chot: datetime
    con_mo: bool


class DangKyThangRequest(BaseModel):
    thang: str = Field(..., pattern=r"^\d{4}-\d{2}$", description="Định dạng YYYY-MM")
    dang_ky: List[DangKyItem] = []


class DangKyThangResponse(BaseModel):
    thang: str
    loai_ca: List[LoaiCaResponse]
    tuan_trong_thang: List[TuanInfo]
    dang_ky: List[DangKyItem]
    tong_ca_dang_ky: int


class DangKyChiTietResponse(BaseModel):
    id: int
    ma_nv: int
    ho_ten: Optional[str] = None
    ma_nhan_vien: Optional[str] = None
    ma_ca: int
    ten_ca: Optional[str] = None
    ma_loai_ca: Optional[str] = None
    ngay_dang_ky: date
    ngay_tao: Optional[datetime] = None


# ---------- Mở rộng FR-08: Điều chỉnh phân công ca thủ công ----------

class PhanCongUpdate(BaseModel):
    ma_nv: Optional[int] = None
    ma_ca: Optional[int] = None
    ngay_lam: Optional[date] = None


# ---------- Mở rộng FR-09: Chi tiết xung đột & Tiền kiểm tra xung đột ----------

class ChiTietXungDot(BaseModel):
    ma_phan_cong: Optional[int] = None
    ma_nv: Optional[int] = None
    ho_ten: Optional[str] = None
    ngay_lam: Optional[date] = None
    ma_ca: Optional[int] = None
    ten_ca: Optional[str] = None
    loai: str  # 'trung_ca', 'trang_thai', 'qua_gio_ngay', 'qua_gio_tuan', 'thieu_nguoi', 'du_nguoi'
    muc_do: str  # 'loi' (màu đỏ, chặn công bố) | 'canh_bao' (màu vàng/icon)
    thong_bao: str


class BaoCaoXungDotResponse(BaseModel):
    tuan_bat_dau: date
    tuan_ket_thuc: date
    co_the_cong_bo: bool
    tong_so_loi: int
    tong_so_canh_bao: int
    xung_dot_phan_cong: List[ChiTietXungDot]
    canh_bao_o_ca: List[ChiTietXungDot]


class KiemTraXungDotResponse(BaseModel):
    hop_le: bool
    co_loi: bool
    thong_bao_chinh: Optional[str] = None
    xung_dot: List[XungDot] = []

