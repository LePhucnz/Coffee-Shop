from datetime import datetime
from sqlalchemy import Column, Integer, String, Text, Boolean, Date, DateTime, ForeignKey, Numeric
from app.database import Base

class LoaiCa(Base):
    __tablename__ = "loai_ca"

    id = Column(Integer, primary_key=True, index=True)
    ma_loai_ca = Column(String(50), unique=True, nullable=False)
    mo_ta = Column(Text, nullable=True)
    trang_thai = Column(Boolean, default=True)


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
    ngay_dang_ky = Column(Date, nullable=True)
    trang_thai = Column(String(20), nullable=True)
    da_duyet = Column(Boolean, default=False)


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
