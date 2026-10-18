from datetime import datetime
from sqlalchemy import Column, Integer, String, Text, Boolean, Date, DateTime, ForeignKey, Numeric
from sqlalchemy.orm import relationship
from app.database import Base

class YeuCauThanhToan(Base):
    __tablename__ = "yeu_cau_thanh_toan"

    id = Column(Integer, primary_key=True, index=True)
    ma_nv = Column(Integer, ForeignKey("nhan_vien.id"), nullable=False)
    so_tien = Column(Numeric(10, 2), nullable=True)
    mo_ta = Column(String(255), nullable=True)
    trang_thai = Column(String(20), nullable=True)
    da_duyet = Column(Boolean, default=False)


class MucThuChi(Base):
    """
    Sprint 6: một khoản trên phiếu lương (PayslipItem).
    loai: thuong | phu_cap | phat | khau_tru | dieu_chinh_cong
    nguon: tu_dong (hệ thống tính, tính lại sẽ thay mới) | thu_cong (Quản lý thêm, giữ khi tính lại)
    """
    __tablename__ = "muc_thu_chi"

    id = Column(Integer, primary_key=True, index=True)
    ma_phan_cong = Column(Integer, ForeignKey("phan_cong_ca.id"), nullable=True)
    ma_nhan_vien = Column(Integer, ForeignKey("nhan_vien.id"), nullable=False)
    loai = Column(String(20), nullable=True)
    so_tien = Column(Numeric(12, 2), nullable=True)
    ly_do = Column(String(255), nullable=True)
    trang_thai = Column(String(20), nullable=True)
    da_tao = Column(DateTime, default=datetime.utcnow)

    # Sprint 6 (FR-12)
    ma_phieu_luong = Column(Integer, ForeignKey("phieu_luong.id"), nullable=True)
    nguon = Column(String(20), default="tu_dong")
    ngay_lam = Column(Date, nullable=True)
    so_gio = Column(Numeric(6, 2), nullable=True)
    nguoi_tao = Column(Integer, ForeignKey("tai_khoan.id"), nullable=True)

    phieu_luong = relationship("PhieuLuong", back_populates="muc_list")


class PhieuLuong(Base):
    """Sprint 6: phiếu lương của một nhân viên trong một kỳ lương (Payslip)"""
    __tablename__ = "phieu_luong"

    id = Column(Integer, primary_key=True, index=True)
    ma_phan_cong = Column(Integer, ForeignKey("phan_cong_ca.id"), nullable=True)
    cong_huong = Column(Numeric(10, 2), nullable=True)
    tong_thu_nhap = Column(Numeric(14, 2), nullable=True)   # Lương cơ bản + thưởng (trước phạt)
    luong_co_ban = Column(Numeric(14, 2), nullable=True)    # Giờ làm × đơn giá × hệ số ca (kể cả điều chỉnh công)
    thanh_tien = Column(Numeric(14, 2), nullable=True)      # Thực lãnh
    thang = Column(Integer, nullable=True)
    nam = Column(Integer, nullable=True)

    # Sprint 6 (FR-12, FR-13)
    ma_ky_luong = Column(Integer, ForeignKey("ky_luong.id"), nullable=True)
    ma_nv = Column(Integer, ForeignKey("nhan_vien.id"), nullable=True)
    ma_hop_dong = Column(Integer, ForeignKey("hop_dong.id"), nullable=True)
    loai_luong = Column(String(10), nullable=True)          # 'gio' | 'thang' (lương tháng quy đổi ra giờ)
    muc_luong_hop_dong = Column(Numeric(14, 2), nullable=True)
    don_gia_gio = Column(Numeric(12, 2), nullable=True)
    so_ca = Column(Integer, default=0)
    tong_gio = Column(Numeric(8, 2), default=0)             # Giờ công đã xác nhận
    gio_quy_doi = Column(Numeric(8, 2), default=0)          # Giờ công × hệ số ca
    gio_dieu_chinh = Column(Numeric(8, 2), default=0)       # Từ bản ghi điều chỉnh của kỳ đã chốt (BR-04)
    so_lan_tre = Column(Integer, default=0)
    so_lan_som = Column(Integer, default=0)
    phut_tre = Column(Integer, default=0)
    phut_som = Column(Integer, default=0)
    so_vang = Column(Integer, default=0)
    so_ca_thieu_ra = Column(Integer, default=0)
    tien_thuong = Column(Numeric(14, 2), default=0)         # Thưởng + phụ cấp
    tien_phat = Column(Numeric(14, 2), default=0)           # Phạt + khấu trừ
    chi_tiet = Column(Text, nullable=True)                  # JSON: từng ca, giữ nguyên sau khi chốt
    canh_bao = Column(Text, nullable=True)                  # JSON: các điểm cần kiểm tra trước khi chốt
    trang_thai = Column(String(20), default="nhap")         # 'nhap' | 'da_chot'
    ngay_tinh = Column(DateTime, nullable=True)

    ky_luong = relationship("KyLuong", back_populates="phieu_list")
    nhan_vien = relationship("NhanVien")
    muc_list = relationship("MucThuChi", back_populates="phieu_luong", cascade="all, delete-orphan",
                            order_by="MucThuChi.id")


class KyLuong(Base):
    """Sprint 6: kỳ lương tuần/tháng (PayrollPeriod). Nháp thì tính lại được, đã chốt thì khóa (BR-04)."""
    __tablename__ = "ky_luong"

    id = Column(Integer, primary_key=True, index=True)
    ten_ky = Column(String(100), nullable=False)
    loai_ky = Column(String(10), default="thang")           # 'thang' | 'tuan' | 'tuy_chon'
    tu_ngay = Column(Date, nullable=False)
    den_ngay = Column(Date, nullable=False)
    trang_thai = Column(String(20), default="nhap")         # 'nhap' | 'da_chot'
    cau_hinh = Column(Text, nullable=True)                  # JSON: chính sách lương áp dụng lần tính gần nhất
    ghi_chu = Column(String(255), nullable=True)
    ngay_tao = Column(DateTime, default=datetime.now)
    nguoi_tao = Column(Integer, ForeignKey("tai_khoan.id"), nullable=True)
    ngay_tinh = Column(DateTime, nullable=True)
    nguoi_tinh = Column(Integer, ForeignKey("tai_khoan.id"), nullable=True)
    ngay_chot = Column(DateTime, nullable=True)
    nguoi_chot = Column(Integer, ForeignKey("tai_khoan.id"), nullable=True)
    ma_ky_cong = Column(Integer, ForeignKey("ky_cong_da_chot.id"), nullable=True)

    phieu_list = relationship("PhieuLuong", back_populates="ky_luong", cascade="all, delete-orphan")


class NgayLe(Base):
    """Sprint 6: ngày lễ, ca làm trong ngày này nhân hệ số ngày lễ (VD × 2.0)"""
    __tablename__ = "ngay_le"

    id = Column(Integer, primary_key=True, index=True)
    ngay = Column(Date, unique=True, nullable=False)
    ten = Column(String(100), nullable=False)
    he_so = Column(Numeric(4, 2), default=2.0)
