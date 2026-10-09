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
