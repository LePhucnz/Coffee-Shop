from typing import Dict, Optional, List
from datetime import date, time, datetime
from pydantic import BaseModel, Field, model_validator


# ---------- Sprint 5: Chấm công trực tuyến (FR-10, FR-11, FR-11A, FR-11B, FR-11D) ----------

class ChamCongRequest(BaseModel):
    """Nhân viên bấm Check-in / Check-out; tọa độ do trình duyệt cung cấp (bỏ trống nếu bị chặn)"""
    ma_phan_cong: int
    vi_do: Optional[float] = Field(None, ge=-90, le=90)
    kinh_do: Optional[float] = Field(None, ge=-180, le=180)


class NhanChamCong(BaseModel):
    ma: str
    ten: str


class CaChamCong(BaseModel):
    """Một ca được phân công kèm kết quả chấm công"""
    ma_phan_cong: int
    ma_cham_cong: Optional[int] = None
    ma_nv: int
    ma_nhan_vien: Optional[str] = None
    ho_ten: Optional[str] = None
    ten_vi_tri: Optional[str] = None
    ngay_lam: date
    ma_ca: int
    ten_ca: Optional[str] = None
    gio_bat_dau: Optional[time] = None
    gio_ket_thuc: Optional[time] = None
    so_gio_ca: float = 0

    gio_vao: Optional[datetime] = None
    gio_ra: Optional[datetime] = None
    gio_vao_goc: Optional[datetime] = None
    gio_ra_goc: Optional[datetime] = None
    # Chỉ Quản lý mới thấy khoảng cách, IP, thiết bị (FR-11B mục 3)
    khoang_cach_vao: Optional[int] = None
    khoang_cach_ra: Optional[int] = None
    ip_vao: Optional[str] = None
    ip_ra: Optional[str] = None
    thiet_bi_vao: Optional[str] = None
    thiet_bi_ra: Optional[str] = None
    vi_tri: str = "khong_ro"  # trong_pham_vi | ngoai_pham_vi | khong_dinh_vi | khong_ro

    trang_thai: str
    ten_trang_thai: str
    phut_di_tre: int = 0
    phut_ve_som: int = 0
    phut_vuot_ca: int = 0
    phut_vuot_ca_duyet: int = 0
    so_gio_lam: float = 0
    dung_gio: bool = False
    co: List[str] = []
    nhan: List[NhanChamCong] = []

    co_the_check_in: bool = False
    co_the_check_out: bool = False
    mo_check_in_luc: Optional[datetime] = None
    han_gui_yeu_cau: Optional[datetime] = None
    co_the_gui_yeu_cau: bool = False

    da_dieu_chinh: bool = False
    mien_phat: bool = False
    ly_do_mien_phat: Optional[str] = None
    da_xac_minh_co: bool = False
    ghi_chu_xac_minh: Optional[str] = None
    da_huy: bool = False
    ly_do_huy: Optional[str] = None
    ky_da_chot: bool = False
    ma_yeu_cau_dang_mo: Optional[int] = None
    ghi_chu_quan_ly: Optional[str] = None


class HomNayResponse(BaseModel):
    ngay: date
    gio_hien_tai: datetime
    ca: List[CaChamCong]
    thong_bao: Optional[str] = None  # Lý do không chấm công được (EX-12, EX-16)
    # Để trình duyệt báo trước "trong / ngoài phạm vi quán" (kết quả cuối cùng do máy chủ tính)
    ten_cua_hang: Optional[str] = None
    vi_do_quan: Optional[float] = None
    kinh_do_quan: Optional[float] = None
    ban_kinh_cho_phep: float = 200
    mo_truoc_phut: int = 15
    an_han_phut: int = 5


class ThongKeChamCong(BaseModel):
    tong_ca: int = 0
    so_ca_da_lam: int = 0
    dung_gio: int = 0
    di_tre: int = 0
    ve_som: int = 0
    vang_mat: int = 0
    chua_check_out: int = 0
    ngoai_vi_tri: int = 0
    da_dieu_chinh: int = 0
    tong_gio_lam: float = 0
    tong_phut_tre: int = 0
    tong_phut_som: int = 0
    phut_vuot_ca_cho_duyet: int = 0
    so_yeu_cau_cho_duyet: int = 0
    so_du_vao_ra: int = 0


class LichSuChamCongResponse(BaseModel):
    tu_ngay: date
    den_ngay: date
    thong_ke: ThongKeChamCong
    items: List[CaChamCong]
    tong_so: int = 0
    trang: int = 1
    so_trang: int = 1
    cap_nhat_luc: Optional[datetime] = None


class OBangCong(BaseModel):
    ma: str          # D | T | S | TS | V | DC | ? | H | -
    nhan: str
    so_gio: float = 0
    ma_phan_cong: Optional[int] = None


class DongBangCong(BaseModel):
    ma_nv: int
    ma_nhan_vien: Optional[str] = None
    ho_ten: Optional[str] = None
    ten_vi_tri: Optional[str] = None
    trang_thai_nv: Optional[str] = None
    o: Dict[str, List[OBangCong]] = {}
    so_ca: int = 0
    tong_gio: float = 0
    phut_tre: int = 0
    phut_som: int = 0
    so_vang: int = 0
    so_thieu_ra: int = 0


class BangCongKyResponse(BaseModel):
    tu_ngay: date
    den_ngay: date
    ngay: List[date]
    nhan_vien: List[DongBangCong]
    tong_gio_xac_nhan: float = 0
    phut_vuot_ca_cho_duyet: int = 0
    so_ca_thieu_ra: int = 0


class NhatKyResponse(BaseModel):
    id: int
    hanh_dong: str
    ten_hanh_dong: str
    truoc: Optional[dict] = None
    sau: Optional[dict] = None
    ly_do: Optional[str] = None
    nguoi_yeu_cau: Optional[str] = None
    nguoi_thuc_hien: Optional[str] = None
    tu_duyet: bool = False
    thoi_gian: datetime


class TepResponse(BaseModel):
    id: int
    ten_tep: str
    duong_dan: str
    kich_thuoc: Optional[int] = None


class YeuCauResponse(BaseModel):
    id: int
    ma_phan_cong: int
    ma_nv: int
    ho_ten: Optional[str] = None
    ma_nhan_vien: Optional[str] = None
    ten_vi_tri: Optional[str] = None
    nguoi_gui: Optional[str] = None
    ngay_lam: Optional[date] = None
    ten_ca: Optional[str] = None
    gio_bat_dau: Optional[time] = None
    gio_ket_thuc: Optional[time] = None
    loai: str
    ten_loai: str
    gio_vao_de_xuat: Optional[datetime] = None
    gio_ra_de_xuat: Optional[datetime] = None
    ma_phan_cong_dung: Optional[int] = None
    ten_ca_dung: Optional[str] = None
    ly_do: str
    trang_thai: str
    ten_trang_thai: str
    vuot_han_muc: bool = False
    lech_nhieu: bool = False
    han_xu_ly: Optional[datetime] = None
    cau_hoi_bo_sung: Optional[str] = None
    ly_do_tu_choi: Optional[str] = None
    ghi_chu_duyet: Optional[str] = None
    nguoi_xu_ly: Optional[str] = None
    ngay_xu_ly: Optional[datetime] = None
    ngay_tao: datetime
    tep: List[TepResponse] = []


class ChiTietChamCongResponse(BaseModel):
    ca: CaChamCong
    vi_do_vao: Optional[float] = None
    kinh_do_vao: Optional[float] = None
    vi_do_ra: Optional[float] = None
    kinh_do_ra: Optional[float] = None
    nhat_ky: List[NhatKyResponse] = []
    yeu_cau: List[YeuCauResponse] = []
    yeu_cau_gan_day: List[YeuCauResponse] = []
    dieu_chinh_ky_sau: List[dict] = []
    ca_cung_ngay: List[dict] = []  # Để chọn ca đúng khi "Sửa ca"


# ---------- Quản lý xử lý (FR-11A, FR-11B) ----------

class DieuChinhRequest(BaseModel):
    """Quản lý điều chỉnh trực tiếp: nhập giờ đúng và lý do (bắt buộc)"""
    gio_vao: Optional[datetime] = None
    gio_ra: Optional[datetime] = None
    xoa_gio_ra: bool = False
    ma_phan_cong_dung: Optional[int] = None
    ly_do: str = Field(..., min_length=10, max_length=500)

    @model_validator(mode="after")
    def check_times(self):
        if self.gio_vao and self.gio_ra and self.gio_ra <= self.gio_vao:
            raise ValueError("Giờ ra phải sau giờ vào")
        return self


class DuyetVuotCaRequest(BaseModel):
    so_phut: int = Field(..., ge=0, le=24 * 60)
    ly_do: str = Field(..., min_length=5, max_length=500)


class MienPhatRequest(BaseModel):
    mien_phat: bool = True
    ly_do: str = Field(..., min_length=5, max_length=255)


class XacMinhCoRequest(BaseModel):
    xac_nhan: bool = True   # True: chấp nhận giải trình, gỡ cờ; False: giữ cờ để theo dõi
    ghi_chu: str = Field(..., min_length=5, max_length=255)


class HuyCaRequest(BaseModel):
    ly_do: str = Field(..., min_length=5, max_length=255)
    tinh_cong: bool = False


class DongDieuChinh(BaseModel):
    ma_phan_cong: int
    gio_vao: Optional[datetime] = None
    gio_ra: Optional[datetime] = None


class DieuChinhHangLoatRequest(BaseModel):
    items: List[DongDieuChinh] = Field(..., min_length=1, max_length=100)
    ly_do: str = Field(..., min_length=10, max_length=500)
    mien_phat: bool = False
    xem_truoc: bool = True


class ChotKyRequest(BaseModel):
    tu_ngay: date
    den_ngay: date
    ghi_chu: Optional[str] = Field(None, max_length=255)
    # Quy tắc 9: còn yêu cầu chờ duyệt thì phải chọn "Chuyển sang kỳ sau"
    chuyen_yeu_cau_sang_ky_sau: bool = False

    @model_validator(mode="after")
    def check_range(self):
        if self.den_ngay < self.tu_ngay:
            raise ValueError("Ngày kết thúc kỳ phải sau ngày bắt đầu")
        return self


# ---------- Yêu cầu bù/sửa công (FR-11A) ----------

LOAI_YEU_CAU = {
    "bu_check_in": "Bù check-in",
    "bu_check_out": "Bù check-out",
    "bu_ca_hai": "Bù cả vào và ra",
    "sua_gio": "Sửa giờ chấm công",
    "sua_ca": "Sửa ca chấm công",
    "giai_trinh": "Giải trình cờ chấm công",
}

TRANG_THAI_YEU_CAU = {
    "cho_duyet": "Chờ duyệt",
    "can_bo_sung": "Cần bổ sung",
    "da_duyet": "Đã duyệt",
    "tu_choi": "Từ chối",
    "da_huy": "Đã hủy",
    "het_han": "Hết hạn",
}


class YeuCauCreate(BaseModel):
    ma_phan_cong: int
    loai: str
    gio_vao_de_xuat: Optional[datetime] = None
    gio_ra_de_xuat: Optional[datetime] = None
    ma_phan_cong_dung: Optional[int] = None
    ly_do: str = Field(..., max_length=1000)

    @model_validator(mode="after")
    def check(self):
        if self.loai not in LOAI_YEU_CAU:
            raise ValueError("Loại yêu cầu không hợp lệ")
        if len(self.ly_do.strip()) < 10:
            raise ValueError("Lý do bắt buộc, tối thiểu 10 ký tự")
        return self


class YeuCauUpdate(BaseModel):
    """Nhân viên cập nhật yêu cầu khi Quản lý cần bổ sung thông tin"""
    gio_vao_de_xuat: Optional[datetime] = None
    gio_ra_de_xuat: Optional[datetime] = None
    ma_phan_cong_dung: Optional[int] = None
    ly_do: str = Field(..., max_length=1000)

    @model_validator(mode="after")
    def check(self):
        if len(self.ly_do.strip()) < 10:
            raise ValueError("Lý do bắt buộc, tối thiểu 10 ký tự")
        return self


class DuyetYeuCauRequest(BaseModel):
    ghi_chu: Optional[str] = Field(None, max_length=500)
    mien_phat: bool = False
    ly_do_mien_phat: Optional[str] = Field(None, max_length=255)


class TuChoiRequest(BaseModel):
    ly_do: str = Field(..., min_length=5, max_length=500)


class BoSungRequest(BaseModel):
    cau_hoi: str = Field(..., min_length=5, max_length=500)


# ---------- Cấu hình (FR-11D mục 2) ----------

class CauHinhChamCongSchema(BaseModel):
    mo_truoc_phut: int = Field(15, ge=0, le=120)
    an_han_phut: int = Field(5, ge=0, le=60)
    chong_bam_trung_giay: int = Field(60, ge=0, le=600)
    ban_kinh_m: int = Field(200, ge=20, le=5000)
    nguong_chua_checkout_phut: int = Field(120, ge=0, le=24 * 60)
    han_gui_yeu_cau_gio: int = Field(48, ge=1, le=24 * 30)
    han_xu_ly_ngay: int = Field(3, ge=1, le=30)
    han_muc_thang: int = Field(3, ge=0, le=100)
    do_lech_toi_da_gio: int = Field(2, ge=0, le=24)
    so_tep_toi_da: int = Field(3, ge=0, le=10)
    dung_luong_tep_mb: int = Field(5, ge=1, le=20)
    dai_ip_quan: str = Field("", max_length=255)
    # Tọa độ cửa hàng (bảng cua_hang)
    ma_cua_hang: Optional[int] = None
    ten_cua_hang: Optional[str] = None
    vi_do_quan: Optional[float] = Field(None, ge=-90, le=90)
    kinh_do_quan: Optional[float] = Field(None, ge=-180, le=180)
    ngay_cap_nhat: Optional[datetime] = None
    co_the_sua: bool = False
