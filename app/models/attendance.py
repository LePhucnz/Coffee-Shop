"""
Sprint 5: Chấm công trực tuyến - các bảng phục vụ FR-11A, FR-11D
- CauHinhChamCong: tham số cấu hình (Admin chỉnh được)
- YeuCauChamCong + TepMinhChung: yêu cầu bù/sửa công của nhân viên
- NhatKyChamCong: nhật ký mọi thay đổi dữ liệu chấm công (BR-06)
- KyCongDaChot + BanGhiDieuChinh: kỳ đã chốt và bản ghi phụ lục áp vào kỳ sau (BR-04)
"""
from datetime import datetime
from sqlalchemy import Column, Integer, String, Text, Boolean, Date, DateTime, ForeignKey, Numeric
from sqlalchemy.orm import relationship
from app.database import Base


class CauHinhChamCong(Base):
    __tablename__ = "cau_hinh_cham_cong"

    id = Column(Integer, primary_key=True, index=True)
    khoa = Column(String(50), unique=True, nullable=False)
    gia_tri = Column(String(255), nullable=True)
    ngay_cap_nhat = Column(DateTime, default=datetime.utcnow)
    nguoi_cap_nhat = Column(Integer, ForeignKey("tai_khoan.id"), nullable=True)


class YeuCauChamCong(Base):
    __tablename__ = "yeu_cau_cham_cong"

    id = Column(Integer, primary_key=True, index=True)
    ma_phan_cong = Column(Integer, ForeignKey("phan_cong_ca.id"), nullable=False)
    ma_nv = Column(Integer, ForeignKey("nhan_vien.id"), nullable=False)
    ma_tai_khoan = Column(Integer, ForeignKey("tai_khoan.id"), nullable=False)  # Người gửi
    # bu_check_in | bu_check_out | bu_ca_hai | sua_gio | sua_ca | giai_trinh
    loai = Column(String(20), nullable=False)
    gio_vao_de_xuat = Column(DateTime, nullable=True)
    gio_ra_de_xuat = Column(DateTime, nullable=True)
    ma_phan_cong_dung = Column(Integer, ForeignKey("phan_cong_ca.id"), nullable=True)  # Dùng cho "Sửa ca"
    ly_do = Column(Text, nullable=False)

    # cho_duyet | can_bo_sung | da_duyet | tu_choi | da_huy | het_han
    trang_thai = Column(String(20), default="cho_duyet")
    vuot_han_muc = Column(Boolean, default=False)
    lech_nhieu = Column(Boolean, default=False)   # Giờ đề xuất lệch quá ngưỡng so với giờ ca
    han_xu_ly = Column(DateTime, nullable=True)
    da_nhac = Column(Boolean, default=False)       # Đã nhắc Quản lý khi còn 24 giờ

    cau_hoi_bo_sung = Column(Text, nullable=True)
    ngay_yeu_cau_bo_sung = Column(DateTime, nullable=True)
    ly_do_tu_choi = Column(Text, nullable=True)
    ghi_chu_duyet = Column(Text, nullable=True)
    nguoi_xu_ly = Column(Integer, ForeignKey("tai_khoan.id"), nullable=True)
    ngay_xu_ly = Column(DateTime, nullable=True)

    ngay_tao = Column(DateTime, default=datetime.utcnow)
    ngay_cap_nhat = Column(DateTime, default=datetime.utcnow)

    phan_cong = relationship("PhanCongCa", foreign_keys=[ma_phan_cong])
    phan_cong_dung = relationship("PhanCongCa", foreign_keys=[ma_phan_cong_dung])
    nhan_vien = relationship("NhanVien")
    nguoi_gui = relationship("TaiKhoan", foreign_keys=[ma_tai_khoan])
    tep_list = relationship("TepMinhChung", back_populates="yeu_cau", cascade="all, delete-orphan")


class TepMinhChung(Base):
    __tablename__ = "tep_minh_chung"

    id = Column(Integer, primary_key=True, index=True)
    ma_yeu_cau = Column(Integer, ForeignKey("yeu_cau_cham_cong.id"), nullable=False)
    ten_tep = Column(String(255), nullable=False)
    duong_dan = Column(String(255), nullable=False)
    kich_thuoc = Column(Integer, nullable=True)
    ngay_tao = Column(DateTime, default=datetime.utcnow)

    yeu_cau = relationship("YeuCauChamCong", back_populates="tep_list")


class NhatKyChamCong(Base):
    """BR-06: lưu giá trị trước/sau, người yêu cầu, người duyệt, thời điểm, lý do"""
    __tablename__ = "nhat_ky_cham_cong"

    id = Column(Integer, primary_key=True, index=True)
    ma_phan_cong = Column(Integer, ForeignKey("phan_cong_ca.id"), nullable=False)
    ma_cham_cong = Column(Integer, ForeignKey("cham_cong.id"), nullable=True)
    ma_yeu_cau = Column(Integer, ForeignKey("yeu_cau_cham_cong.id"), nullable=True)
    hanh_dong = Column(String(50), nullable=False)
    truoc = Column(Text, nullable=True)   # JSON
    sau = Column(Text, nullable=True)     # JSON
    ly_do = Column(Text, nullable=True)
    nguoi_yeu_cau = Column(Integer, ForeignKey("tai_khoan.id"), nullable=True)
    nguoi_thuc_hien = Column(Integer, ForeignKey("tai_khoan.id"), nullable=True)
    tu_duyet = Column(Boolean, default=False)
    thoi_gian = Column(DateTime, default=datetime.now)


class KyCongDaChot(Base):
    """BR-04: kỳ công đã chốt thì không sửa bản ghi gốc nữa"""
    __tablename__ = "ky_cong_da_chot"

    id = Column(Integer, primary_key=True, index=True)
    tu_ngay = Column(Date, nullable=False)
    den_ngay = Column(Date, nullable=False)
    nguoi_chot = Column(Integer, ForeignKey("tai_khoan.id"), nullable=True)
    ngay_chot = Column(DateTime, default=datetime.now)
    ghi_chu = Column(String(255), nullable=True)


class BanGhiDieuChinh(Base):
    """Bản ghi phụ lục: điều chỉnh công của kỳ đã chốt, áp dụng vào kỳ lương sau"""
    __tablename__ = "ban_ghi_dieu_chinh"

    id = Column(Integer, primary_key=True, index=True)
    ma_phan_cong = Column(Integer, ForeignKey("phan_cong_ca.id"), nullable=False)
    ma_nv = Column(Integer, ForeignKey("nhan_vien.id"), nullable=False)
    ma_ky_goc = Column(Integer, ForeignKey("ky_cong_da_chot.id"), nullable=True)
    ap_dung_tu_ngay = Column(Date, nullable=False)    # Ngày đầu kỳ sau
    gio_vao_moi = Column(DateTime, nullable=True)
    gio_ra_moi = Column(DateTime, nullable=True)
    so_gio_chenh = Column(Numeric(6, 2), default=0)   # Giờ công cộng thêm (+) hoặc trừ đi (-)
    ly_do = Column(Text, nullable=False)
    ma_yeu_cau = Column(Integer, ForeignKey("yeu_cau_cham_cong.id"), nullable=True)
    nguoi_tao = Column(Integer, ForeignKey("tai_khoan.id"), nullable=True)
    ngay_tao = Column(DateTime, default=datetime.now)
