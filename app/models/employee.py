from datetime import datetime
from sqlalchemy import Column, Integer, String, Date, DateTime, Numeric, Boolean, ForeignKey
from sqlalchemy.orm import relationship
from app.database import Base

class NhanVien(Base):
    __tablename__ = "nhan_vien"

    id = Column(Integer, primary_key=True, index=True)
    ma_nhan_vien = Column(String(50), unique=True, index=True, nullable=True)
    ma_cua_hang = Column(Integer, ForeignKey("cua_hang.id"), nullable=True)
    ma_vi_tri = Column(Integer, ForeignKey("vi_tri.id"), nullable=True)
    ho_ten = Column(String(100), nullable=False)
    so_dien_thoai = Column(String(20), nullable=True)
    email = Column(String(255), nullable=True)
    dia_chi = Column(String(255), nullable=True)
    cccd = Column(String(20), nullable=True)  # CMND / CCCD (FR-04)
    ngay_sinh = Column(Date, nullable=True)
    gioi_tinh = Column(String(10), nullable=True)
    tinh_trang_hon_nhan = Column(String(50), nullable=True)
    so_nhan_khau = Column(Integer, default=0)
    ngay_vao_lam = Column(Date, nullable=True)
    anh_dai_dien = Column(String(255), nullable=True)
    
    # FR-06: 'dang_lam', 'nghi_phep', 'da_nghi'
    trang_thai = Column(String(20), default="dang_lam")
    
    # FR-04: Soft delete
    is_deleted = Column(Boolean, default=False)
    
    ngay_tao = Column(DateTime, default=datetime.utcnow)

    # Relationships
    cua_hang = relationship("CuaHang", back_populates="nhan_vien_list")
    vi_tri = relationship("ViTri", back_populates="nhan_vien_list")
    tai_khoan = relationship("TaiKhoan", back_populates="nhan_vien", uselist=False)
    hop_dong_list = relationship("HopDong", back_populates="nhan_vien", cascade="all, delete-orphan")


class HopDong(Base):
    __tablename__ = "hop_dong"

    id = Column(Integer, primary_key=True, index=True)
    ma_nhan_vien = Column(Integer, ForeignKey("nhan_vien.id"), nullable=False)
    loai_hop_dong = Column(String(50), nullable=True)  # 'Toàn thời gian', 'Bán thời gian', 'Thử việc', 'Thời vụ'
    ngay_bat_dau = Column(Date, nullable=True)
    ngay_ket_thuc = Column(Date, nullable=True)
    muc_luong = Column(Numeric(12, 2), nullable=True)
    ma_bang_luong = Column(String(25), nullable=True)
    file_dinh_kem = Column(String(255), nullable=True)
    trang_thai = Column(String(20), default="hieu_luc")  # 'hieu_luc', 'het_han', 'da_huy'
    ngay_tao = Column(DateTime, default=datetime.utcnow)

    nhan_vien = relationship("NhanVien", back_populates="hop_dong_list")
