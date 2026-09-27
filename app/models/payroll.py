from datetime import datetime
from sqlalchemy import Column, Integer, String, Boolean, DateTime, ForeignKey, Numeric
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
    __tablename__ = "muc_thu_chi"

    id = Column(Integer, primary_key=True, index=True)
    ma_phan_cong = Column(Integer, ForeignKey("phan_cong_ca.id"), nullable=True)
    ma_nhan_vien = Column(Integer, ForeignKey("nhan_vien.id"), nullable=False)
    loai = Column(String(20), nullable=True)
    so_tien = Column(Numeric(10, 2), nullable=True)
    ly_do = Column(String(255), nullable=True)
    trang_thai = Column(String(20), nullable=True)
    da_tao = Column(DateTime, default=datetime.utcnow)


class PhieuLuong(Base):
    __tablename__ = "phieu_luong"

    id = Column(Integer, primary_key=True, index=True)
    ma_phan_cong = Column(Integer, ForeignKey("phan_cong_ca.id"), nullable=True)
    cong_huong = Column(Numeric(10, 2), nullable=True)
    tong_thu_nhap = Column(Numeric(10, 2), nullable=True)
    luong_co_ban = Column(Numeric(10, 2), nullable=True)
    thanh_tien = Column(Numeric(10, 2), nullable=True)
    thang = Column(Integer, nullable=True)
    nam = Column(Integer, nullable=True)
