from sqlalchemy import Column, Integer, String, Boolean, Numeric
from sqlalchemy.orm import relationship
from app.database import Base

class CuaHang(Base):
    __tablename__ = "cua_hang"

    id = Column(Integer, primary_key=True, index=True)
    ten_cua_hang = Column(String(100), nullable=False)
    dia_chi = Column(String(255), nullable=True)
    vi_do = Column(Numeric(9, 6), nullable=True)
    kinh_do = Column(Numeric(9, 6), nullable=True)
    trang_thai = Column(Boolean, default=True)

    nhan_vien_list = relationship("NhanVien", back_populates="cua_hang")


class ViTri(Base):
    __tablename__ = "vi_tri"

    id = Column(Integer, primary_key=True, index=True)
    ten_vi_tri = Column(String(100), nullable=False)
    mo_ta = Column(String(255), nullable=True)

    nhan_vien_list = relationship("NhanVien", back_populates="vi_tri")


class VaiTro(Base):
    __tablename__ = "vai_tro"

    id = Column(Integer, primary_key=True, index=True)
    ten_vai_tro = Column(String(50), nullable=False)  # Admin, Manager, Staff
    mo_ta = Column(String(255), nullable=True)

    tai_khoan_list = relationship("TaiKhoan", back_populates="vai_tro")
