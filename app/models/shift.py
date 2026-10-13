from datetime import datetime
from sqlalchemy import Column, Integer, String, Text, Boolean, Date, DateTime, Time, ForeignKey, Numeric, UniqueConstraint
from sqlalchemy.orm import relationship
from app.database import Base

class LoaiCa(Base):
    __tablename__ = "loai_ca"

    id = Column(Integer, primary_key=True, index=True)
    ma_loai_ca = Column(String(50), unique=True, nullable=False)
    mo_ta = Column(Text, nullable=True)
    trang_thai = Column(Boolean, default=True)

    # Sprint 4 (FR-07, FR-08): khung giờ và nhu cầu nhân lực của từng ca
    ten_ca = Column(String(100), nullable=True)
    gio_bat_dau = Column(Time, nullable=True)
    gio_ket_thuc = Column(Time, nullable=True)
    so_nv_toi_thieu = Column(Integer, default=1)
    so_nv_toi_da = Column(Integer, default=3)


class LichTrinh(Base):
    __tablename__ = "lich_trinh"

    id = Column(Integer, primary_key=True, index=True)
    ma_nv = Column(Integer, ForeignKey("nhan_vien.id"), nullable=False)
    ngay_bat_dau = Column(Date, nullable=True)
    ngay_ket_thuc = Column(Date, nullable=True)
    trang_thai = Column(String(20), nullable=True)
    da_duoc_duyet = Column(Date, nullable=True)


class DangKyCa(Base):
    __tablename__ = "dang_ky_ca"

    id = Column(Integer, primary_key=True, index=True)
    ma_nv = Column(Integer, ForeignKey("nhan_vien.id"), nullable=False)
    ma_ca = Column(Integer, ForeignKey("loai_ca.id"), nullable=False)
    ngay_dang_ky = Column(Date, nullable=True)  # FR-07: ngày nhân viên muốn làm ca này
    trang_thai = Column(String(20), nullable=True)
    da_duyet = Column(Boolean, default=False)
    ngay_tao = Column(DateTime, default=datetime.utcnow)

    nhan_vien = relationship("NhanVien")
    loai_ca = relationship("LoaiCa")


class PhanCongCa(Base):
    __tablename__ = "phan_cong_ca"

    id = Column(Integer, primary_key=True, index=True)
    ma_lich_trinh = Column(Integer, ForeignKey("lich_trinh.id"), nullable=True)
    ma_nv = Column(Integer, ForeignKey("nhan_vien.id"), nullable=False)
    ma_ca = Column(Integer, ForeignKey("loai_ca.id"), nullable=False)
    bat_dau_thuc_te = Column(DateTime, nullable=True)
    ket_thuc_thuc_te = Column(DateTime, nullable=True)
    trang_thai = Column(String(20), nullable=True)
    ghi_chu = Column(String(255), nullable=True)

    # Sprint 4 (FR-08): ngày làm và lịch tuần chứa ca này
    ngay_lam = Column(Date, nullable=True)
    ma_lich_tuan = Column(Integer, ForeignKey("lich_ca_tuan.id"), nullable=True)
    theo_nguyen_vong = Column(Boolean, default=False)

    # Sprint 5 (EX-18): ca bị hủy do quán đóng cửa đột xuất, mất điện...
    da_huy = Column(Boolean, default=False)
    ly_do_huy = Column(String(255), nullable=True)
    tinh_cong_khi_huy = Column(Boolean, default=False)  # Có tính công cho thời gian đã làm hay không
    nguoi_huy = Column(Integer, ForeignKey("tai_khoan.id"), nullable=True)
    ngay_huy = Column(DateTime, nullable=True)

    nhan_vien = relationship("NhanVien")
    loai_ca = relationship("LoaiCa")
    lich_tuan = relationship("LichCaTuan", back_populates="phan_cong_list")


class LichCaTuan(Base):
    """Sprint 4 (FR-08, BR-02): lịch ca của một tuần, ở trạng thái 'nhap' cho tới khi Quản lý công bố"""
    __tablename__ = "lich_ca_tuan"

    id = Column(Integer, primary_key=True, index=True)
    tuan_bat_dau = Column(Date, unique=True, nullable=False)  # Luôn là ngày Thứ Hai
    trang_thai = Column(String(20), default="nhap")  # 'nhap', 'da_cong_bo'
    ngay_cong_bo = Column(DateTime, nullable=True)
    nguoi_cong_bo = Column(Integer, ForeignKey("tai_khoan.id"), nullable=True)
    ngay_tao = Column(DateTime, default=datetime.utcnow)

    phan_cong_list = relationship("PhanCongCa", back_populates="lich_tuan")


class ThongBao(Base):
    """Sprint 4 (FR-08): thông báo trong ứng dụng gửi tới nhân viên"""
    __tablename__ = "thong_bao"

    id = Column(Integer, primary_key=True, index=True)
    ma_nv = Column(Integer, ForeignKey("nhan_vien.id"), nullable=False)
    tieu_de = Column(String(255), nullable=False)
    noi_dung = Column(Text, nullable=True)
    lien_ket = Column(String(255), nullable=True)
    da_doc = Column(Boolean, default=False)
    ngay_tao = Column(DateTime, default=datetime.utcnow)


class ChamCong(Base):
    __tablename__ = "cham_cong"

    id = Column(Integer, primary_key=True, index=True)
    ma_phan_cong = Column(Integer, ForeignKey("phan_cong_ca.id"), nullable=False)
    check_in_lan_1 = Column(DateTime, nullable=True)
    check_out_lan_1 = Column(DateTime, nullable=True)
    check_in_lan_2 = Column(DateTime, nullable=True)
    check_out_lan_2 = Column(DateTime, nullable=True)
    check_in_lan_3 = Column(DateTime, nullable=True)
    check_out_lan_3 = Column(DateTime, nullable=True)
    so_gio_di_trong = Column(Integer, nullable=True)
    tac_vu_phu = Column(String(25), nullable=True)
    gio_phut_nghi = Column(Integer, nullable=True)
    tong_gio_lam = Column(Numeric(6, 2), nullable=True)
    thang = Column(String(7), nullable=True)
    nam = Column(Integer, nullable=True)

    # Sprint 5 (FR-10): giờ gốc do máy ghi nhận, không bao giờ bị sửa (BR-06).
    # check_in_lan_1 / check_out_lan_1 ở trên là giờ đang có hiệu lực (sau điều chỉnh nếu có).
    gio_vao_goc = Column(DateTime, nullable=True)
    gio_ra_goc = Column(DateTime, nullable=True)

    # Vị trí lúc chấm công (GPS trình duyệt + IP + thiết bị)
    vi_do_vao = Column(Numeric(9, 6), nullable=True)
    kinh_do_vao = Column(Numeric(9, 6), nullable=True)
    ip_vao = Column(String(45), nullable=True)
    khoang_cach_vao = Column(Integer, nullable=True)  # mét tới quán
    thiet_bi_vao = Column(String(120), nullable=True)
    vi_do_ra = Column(Numeric(9, 6), nullable=True)
    kinh_do_ra = Column(Numeric(9, 6), nullable=True)
    ip_ra = Column(String(45), nullable=True)
    khoang_cach_ra = Column(Integer, nullable=True)
    thiet_bi_ra = Column(String(120), nullable=True)

    # Cờ bất thường (FR-10, FR-11D)
    ngoai_vi_tri = Column(Boolean, default=False)      # EX-07: ngoài bán kính cho phép
    khong_dinh_vi = Column(Boolean, default=False)     # EX-08: không lấy được GPS
    thiet_bi_trung = Column(Boolean, default=False)    # EX-17: nhiều tài khoản cùng thiết bị
    da_xac_minh_co = Column(Boolean, default=False)    # Quản lý đã xác nhận giải trình, gỡ cờ
    ghi_chu_xac_minh = Column(String(255), nullable=True)

    # FR-11: kết quả đối chiếu với giờ ca, là đầu vào cho tính lương (Sprint 6)
    an_han_ap_dung = Column(Integer, nullable=True)    # Số phút ân hạn tại thời điểm chấm công
    phut_di_tre = Column(Integer, default=0)
    phut_ve_som = Column(Integer, default=0)
    phut_vuot_ca = Column(Integer, default=0)          # EX-06: giờ ra sau giờ kết thúc ca
    phut_vuot_ca_duyet = Column(Integer, default=0)    # BR-09: chỉ phần được duyệt mới tính công
    trang_thai = Column(String(20), nullable=True)

    # FR-11A: điều chỉnh, miễn phạt
    da_dieu_chinh = Column(Boolean, default=False)
    mien_phat = Column(Boolean, default=False)
    ly_do_mien_phat = Column(String(255), nullable=True)

    # Ghi chú xử lý gần nhất của Quản lý
    da_xu_ly = Column(Boolean, default=False)
    ghi_chu_quan_ly = Column(String(255), nullable=True)
    nguoi_xu_ly = Column(Integer, ForeignKey("tai_khoan.id"), nullable=True)
    ngay_xu_ly = Column(DateTime, nullable=True)

    phan_cong = relationship("PhanCongCa")
