from typing import List, Optional
from datetime import date, datetime
from pydantic import BaseModel, Field, model_validator


# ---------- Sprint 6: Tính lương (FR-12) và báo cáo lương (FR-13) ----------

class KyLuongCreate(BaseModel):
    loai_ky: str = Field("thang", pattern="^(thang|tuan|tuy_chon)$")
    tu_ngay: date
    den_ngay: date
    ten_ky: Optional[str] = Field(None, max_length=100)
    ghi_chu: Optional[str] = Field(None, max_length=255)

    @model_validator(mode="after")
    def check_range(self):
        if self.den_ngay < self.tu_ngay:
            raise ValueError("Ngày kết thúc kỳ phải sau ngày bắt đầu")
        if (self.den_ngay - self.tu_ngay).days > 62:
            raise ValueError("Một kỳ lương tối đa 62 ngày")
        return self


class ChotKyLuongRequest(BaseModel):
    # Quy tắc 9 (FR-11A): còn yêu cầu bù/sửa công chờ duyệt thì phải chọn "Chuyển sang kỳ sau"
    chuyen_yeu_cau_sang_ky_sau: bool = False


class MucPhieuLuongCreate(BaseModel):
    """Quản lý thêm khoản thủ công trước khi chốt (VD phụ cấp đột xuất)"""
    loai: str = Field(..., pattern="^(thuong|phu_cap|phat|khau_tru)$")
    so_tien: int = Field(..., gt=0, le=1_000_000_000)
    ly_do: str = Field(..., min_length=3, max_length=255)


class MucPhieuLuong(BaseModel):
    id: int
    loai: str
    ten_loai: str
    nguon: str
    so_tien: int
    dau: int  # +1 cộng vào lương, -1 trừ khỏi lương
    ly_do: Optional[str] = None
    ngay_lam: Optional[date] = None
    so_gio: Optional[float] = None
    nguoi_tao: Optional[str] = None
    da_tao: Optional[datetime] = None


class DongCaLuong(BaseModel):
    """Một ca trong phiếu lương"""
    ma_phan_cong: int
    ngay: date
    ca: str
    vao: Optional[str] = None
    ra: Optional[str] = None
    trang_thai: str
    ten_trang_thai: str
    so_gio: float = 0
    he_so: float = 1
    ngay_le: Optional[str] = None
    don_gia: float = 0
    thanh_tien: int = 0
    phut_tre: int = 0
    phut_som: int = 0
    phut_vuot_ca_duyet: int = 0
    mien_phat: bool = False
    da_dieu_chinh: bool = False
    tien_phat: int = 0


class PhieuLuongTomTat(BaseModel):
    id: int
    ma_ky_luong: int
    ten_ky: str
    tu_ngay: date
    den_ngay: date
    trang_thai: str
    ma_nv: int
    ma_nhan_vien: Optional[str] = None
    ho_ten: Optional[str] = None
    ten_vi_tri: Optional[str] = None
    da_nghi_viec: bool = False
    loai_luong: Optional[str] = None
    muc_luong_hop_dong: Optional[float] = None
    don_gia_gio: float = 0
    so_ca: int = 0
    tong_gio: float = 0
    gio_quy_doi: float = 0
    gio_dieu_chinh: float = 0
    so_lan_tre: int = 0
    so_lan_som: int = 0
    phut_tre: int = 0
    phut_som: int = 0
    so_vang: int = 0
    so_ca_thieu_ra: int = 0
    luong_co_ban: int = 0
    tien_thuong: int = 0
    tien_phat: int = 0
    thuc_lanh: int = 0
    canh_bao: List[str] = []


class PhieuLuongChiTiet(PhieuLuongTomTat):
    ca: List[DongCaLuong] = []
    khoan: List[MucPhieuLuong] = []
    ngay_tinh: Optional[datetime] = None
    co_the_sua: bool = False


class TongKyLuong(BaseModel):
    so_nhan_vien: int = 0
    tong_gio: float = 0
    luong_co_ban: int = 0
    tien_thuong: int = 0
    tien_phat: int = 0
    thuc_lanh: int = 0


class KyLuongResponse(BaseModel):
    id: int
    ten_ky: str
    loai_ky: str
    tu_ngay: date
    den_ngay: date
    trang_thai: str
    ghi_chu: Optional[str] = None
    ngay_tao: Optional[datetime] = None
    ngay_tinh: Optional[datetime] = None
    nguoi_tinh: Optional[str] = None
    ngay_chot: Optional[datetime] = None
    nguoi_chot: Optional[str] = None
    tong: TongKyLuong = TongKyLuong()


class KyLuongChiTiet(KyLuongResponse):
    phieu: List[PhieuLuongTomTat] = []
    canh_bao: List[str] = []
    so_yeu_cau_cho_duyet: int = 0


class HeSoCa(BaseModel):
    id: int
    ten_ca: Optional[str] = None
    khung_gio: Optional[str] = None
    he_so_luong: float = Field(1.0, ge=0.5, le=5)


class NgayLeSchema(BaseModel):
    id: Optional[int] = None
    ngay: date
    ten: str = Field(..., min_length=2, max_length=100)
    he_so: float = Field(2.0, ge=1, le=5)


class CauHinhLuongSchema(BaseModel):
    gio_chuan_thang: int = Field(208, ge=1, le=400)
    nguong_luong_thang: int = Field(1000000, ge=0)
    cach_phat: str = Field("theo_phut", pattern="^(theo_phut|co_dinh)$")
    phat_moi_phut: int = Field(1000, ge=0, le=1_000_000)
    phat_moi_lan: int = Field(20000, ge=0, le=10_000_000)
    phat_vang_moi_lan: int = Field(0, ge=0, le=10_000_000)
    thuong_chuyen_can: int = Field(300000, ge=0, le=100_000_000)
    chuyen_can_so_ca_toi_thieu: int = Field(4, ge=0, le=100)
    chuyen_can_ky_tuan: bool = False
    he_so_ngay_le_mac_dinh: float = Field(2.0, ge=1, le=5)
    he_so_ca: List[HeSoCa] = []
    ngay_le: List[NgayLeSchema] = []
    ngay_cap_nhat: Optional[datetime] = None
