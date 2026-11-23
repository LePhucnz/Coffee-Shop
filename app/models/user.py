from datetime import datetime
from sqlalchemy import Column, Integer, String, DateTime, Boolean, ForeignKey, Text
from sqlalchemy.orm import relationship
from app.database import Base

class TaiKhoan(Base):
    __tablename__ = "tai_khoan"

    id = Column(Integer, primary_key=True, index=True)
    ma_nv = Column(Integer, ForeignKey("nhan_vien.id"), nullable=True)
    ma_vai_tro = Column(Integer, ForeignKey("vai_tro.id"), nullable=True)
    ten_dang_nhap = Column(String(255), unique=True, index=True, nullable=False)
    mat_khau = Column(String(255), nullable=False)
    is_active = Column(Boolean, default=True)
    da_dang_nhap_lan_cuoi = Column(DateTime, nullable=True)
    lockout_until = Column(DateTime, nullable=True)
    so_lan_dang_nhap_sai = Column(Integer, default=0)
    ngay_tao = Column(DateTime, default=datetime.utcnow)

    # Relationships
    nhan_vien = relationship("NhanVien", back_populates="tai_khoan")
    vai_tro = relationship("VaiTro", back_populates="tai_khoan_list")
    lich_su_dang_nhap_list = relationship("LichSuDangNhap", back_populates="tai_khoan", cascade="all, delete-orphan")


class LichSuDangNhap(Base):
    __tablename__ = "lich_su_dang_nhap"

    id = Column(Integer, primary_key=True, index=True)
    ma_tai_khoan = Column(Integer, ForeignKey("tai_khoan.id"), nullable=False)
    thoi_gian_dang_nhap = Column(DateTime, default=datetime.utcnow)
    dia_chi_ip = Column(String(45), nullable=True)
    trang_thai = Column(String(20), nullable=True)  # 'thanh_cong', 'that_bai', 'khoa_tam_thoi'

    tai_khoan = relationship("TaiKhoan", back_populates="lich_su_dang_nhap_list")


class NhatKyHeThong(Base):
    __tablename__ = "nhat_ky_he_thong"

    id = Column(Integer, primary_key=True, index=True)
    ma_tai_khoan = Column(Integer, ForeignKey("tai_khoan.id"), nullable=False)
    ma_cua_hang = Column(Integer, ForeignKey("cua_hang.id"), nullable=True)
    hanh_dong = Column(String(100), nullable=False)
    thoi_gian = Column(DateTime, default=datetime.utcnow)
    ly_do = Column(Text, nullable=True)
    trang_thai = Column(String(255), nullable=True)
