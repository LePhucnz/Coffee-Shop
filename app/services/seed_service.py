from datetime import date, datetime, time, timedelta
from sqlalchemy.orm import Session
from app.models.system import CuaHang, ViTri, VaiTro
from app.models.employee import NhanVien, HopDong
from app.models.user import TaiKhoan
from app.models.shift import LoaiCa
from app.core.security import get_password_hash

def seed_database(db: Session):
    """Nạp dữ liệu mẫu ban đầu nếu cơ sở dữ liệu trống"""
    if db.query(VaiTro).first():
        seed_shift_types(db)
        return  # Đã có dữ liệu, không nạp lại

    # 1. Vai trò (Roles)
    vai_tro_data = [
        VaiTro(id=1, ten_vai_tro="Admin", mo_ta="Quản trị viên toàn hệ thống"),
        VaiTro(id=2, ten_vai_tro="Manager", mo_ta="Quản lý cửa hàng"),
        VaiTro(id=3, ten_vai_tro="Staff", mo_ta="Nhân viên thông thường")
    ]
    db.add_all(vai_tro_data)
    db.commit()

    # 2. Vị trí công việc (Positions)
    vi_tri_data = [
        ViTri(id=1, ten_vi_tri="Quản lý", mo_ta="Quản lý vận hành toàn bộ cửa hàng"),
        ViTri(id=2, ten_vi_tri="Pha chế (Barista)", mo_ta="Phụ trách pha chế đồ uống"),
        ViTri(id=3, ten_vi_tri="Phục vụ", mo_ta="Nhận order và phục vụ khách hàng"),
        ViTri(id=4, ten_vi_tri="Thu ngân", mo_ta="Thanh toán và quản lý tiền mặt")
    ]
    db.add_all(vi_tri_data)
    db.commit()

    # 3. Cửa hàng (Stores)
    cua_hang_data = [
        CuaHang(id=1, ten_cua_hang="The Coffee Shop - Quận 1", dia_chi="123 Lê Lợi, Q.1, TP.HCM", vi_do=10.7769, kinh_do=106.7009, trang_thai=True),
        CuaHang(id=2, ten_cua_hang="The Coffee Shop - Quận 3", dia_chi="456 Võ Văn Tần, Q.3, TP.HCM", vi_do=10.7798, kinh_do=106.6874, trang_thai=True)
    ]
    db.add_all(cua_hang_data)
    db.commit()

    # 4. Loại ca làm việc
    loai_ca_data = [
        LoaiCa(id=1, ma_loai_ca="CA_SANG", mo_ta="06:00 - 14:00", trang_thai=True,
               ten_ca="Ca sáng", gio_bat_dau=time(6, 0), gio_ket_thuc=time(14, 0), so_nv_toi_thieu=1, so_nv_toi_da=2),
        LoaiCa(id=2, ma_loai_ca="CA_CHIEU", mo_ta="14:00 - 22:00", trang_thai=True,
               ten_ca="Ca chiều (cao điểm)", gio_bat_dau=time(14, 0), gio_ket_thuc=time(22, 0), so_nv_toi_thieu=2, so_nv_toi_da=3),
        LoaiCa(id=3, ma_loai_ca="CA_PARTTIME_1", mo_ta="08:00 - 12:00", trang_thai=True,
               ten_ca="Part-time sáng", gio_bat_dau=time(8, 0), gio_ket_thuc=time(12, 0), so_nv_toi_thieu=1, so_nv_toi_da=2),
        LoaiCa(id=4, ma_loai_ca="CA_PARTTIME_2", mo_ta="18:00 - 22:00", trang_thai=True,
               ten_ca="Part-time tối", gio_bat_dau=time(18, 0), gio_ket_thuc=time(22, 0), so_nv_toi_thieu=1, so_nv_toi_da=2)
    ]
    db.add_all(loai_ca_data)
    db.commit()

    # 5. Hồ sơ Nhân viên mẫu (Employees)
    nhan_vien_data = [
        NhanVien(
            id=1,
            ma_nhan_vien="NV001",
            ma_cua_hang=1,
            ma_vi_tri=1,
            ho_ten="Nguyễn Văn A",
            so_dien_thoai="0901234567",
            email="nva@coffeeshop.com",
            dia_chi="123 Lê Lợi, Q.1, TP.HCM",
            cccd="079090001111",
            ngay_sinh=date(1995, 5, 20),
            gioi_tinh="Nam",
            tinh_trang_hon_nhan="Độc thân",
            so_nhan_khau=0,
            ngay_vao_lam=date(2023, 1, 1),
            trang_thai="dang_lam"
        ),
        NhanVien(
            id=2,
            ma_nhan_vien="NV002",
            ma_cua_hang=1,
            ma_vi_tri=2,
            ho_ten="Trần Thị B",
            so_dien_thoai="0912345678",
            email="ttb@coffeeshop.com",
            dia_chi="456 Hai Bà Trưng, Q.1, TP.HCM",
            cccd="079092002222",
            ngay_sinh=1999 and date(1999, 8, 15),
            gioi_tinh="Nữ",
            tinh_trang_hon_nhan="Độc thân",
            so_nhan_khau=0,
            ngay_vao_lam=date(2023, 5, 15),
            trang_thai="dang_lam"
        ),
        NhanVien(
            id=3,
            ma_nhan_vien="NV003",
            ma_cua_hang=2,
            ma_vi_tri=3,
            ho_ten="Lê Văn C",
            so_dien_thoai="0923456789",
            email="lvc@coffeeshop.com",
            dia_chi="789 CMT8, Q.3, TP.HCM",
            cccd="079095003333",
            ngay_sinh=date(2001, 11, 2),
            gioi_tinh="Nam",
            tinh_trang_hon_nhan="Độc thân",
            so_nhan_khau=0,
            ngay_vao_lam=date(2023, 8, 1),
            trang_thai="dang_lam"
        ),
        NhanVien(
            id=4,
            ma_nhan_vien="NV004",
            ma_cua_hang=1,
            ma_vi_tri=4,
            ho_ten="Phạm Hoàng D",
            so_dien_thoai="0934567890",
            email="phd@coffeeshop.com",
            dia_chi="12 Điện Biên Phủ, Q.Bình Thạnh, TP.HCM",
            cccd="079096004444",
            ngay_sinh=date(2000, 3, 10),
            gioi_tinh="Nam",
            tinh_trang_hon_nhan="Độc thân",
            so_nhan_khau=0,
            ngay_vao_lam=date(2024, 2, 1),
            trang_thai="nghi_phep"
        )
    ]
    db.add_all(nhan_vien_data)
    db.commit()

    # 6. Tài khoản người dùng (Accounts with bcrypt hashed passwords)
    # Admin/Manager password: Admin@123456
    # Staff password: Staff@123456
    admin_pw_hash = get_password_hash("Admin@123456")
    staff_pw_hash = get_password_hash("Staff@123456")

    tai_khoan_data = [
        TaiKhoan(
            id=1,
            ma_nv=1,
            ma_vai_tro=2,  # Manager (toàn quyền)
            ten_dang_nhap="nguyen.a",
            mat_khau=admin_pw_hash,
            is_active=True
        ),
        TaiKhoan(
            id=2,
            ma_nv=2,
            ma_vai_tro=3,  # Staff
            ten_dang_nhap="tran.b",
            mat_khau=staff_pw_hash,
            is_active=True
        ),
        TaiKhoan(
            id=3,
            ma_nv=3,
            ma_vai_tro=3,  # Staff
            ten_dang_nhap="le.c",
            mat_khau=staff_pw_hash,
            is_active=True
        )
    ]
    db.add_all(tai_khoan_data)
    db.commit()

    # 7. Hợp đồng lao động mẫu (Contracts)
    # Kèm 1 hợp đồng mẫu sắp hết hạn trong 20 ngày để kiểm thử FR-05
    today = date.today()
    hop_dong_data = [
        HopDong(
            id=1,
            ma_nhan_vien=1,
            loai_hop_dong="Toàn thời gian",
            ngay_bat_dau=date(2023, 1, 1),
            ngay_ket_thuc=date(2027, 1, 1),
            muc_luong=15000000,
            trang_thai="hieu_luc"
        ),
        HopDong(
            id=2,
            ma_nhan_vien=2,
            loai_hop_dong="Toàn thời gian",
            ngay_bat_dau=date(2023, 5, 15),
            ngay_ket_thuc=date(2026, 12, 31),
            muc_luong=9000000,
            trang_thai="hieu_luc"
        ),
        HopDong(
            id=3,
            ma_nhan_vien=3,
            loai_hop_dong="Bán thời gian",
            ngay_bat_dau=today - timedelta(days=60),
            ngay_ket_thuc=today + timedelta(days=20),  # Sắp hết hạn trong 20 ngày (cảnh báo 15-30 ngày)
            muc_luong=25000,
            trang_thai="hieu_luc"
        )
    ]
    db.add_all(hop_dong_data)
    db.commit()

    seed_shift_types(db)


# Sprint 4: tên ca, khung giờ và số nhân viên tối thiểu/tối đa cho các loại ca mẫu
SHIFT_TYPE_DEFAULTS = {
    "CA_SANG": ("Ca sáng", time(6, 0), time(14, 0), 1, 2),
    "CA_CHIEU": ("Ca chiều (cao điểm)", time(14, 0), time(22, 0), 2, 3),
    "CA_PARTTIME_1": ("Part-time sáng", time(8, 0), time(12, 0), 1, 2),
    "CA_PARTTIME_2": ("Part-time tối", time(18, 0), time(22, 0), 1, 2),
}

def seed_shift_types(db: Session):
    """
    Sprint 4: bổ sung khung giờ cho các loại ca đã có.
    Chỉ điền vào ô còn trống nên không ghi đè cấu hình Quản lý đã sửa.
    """
    changed = False
    for loai_ca in db.query(LoaiCa).all():
        defaults = SHIFT_TYPE_DEFAULTS.get(loai_ca.ma_loai_ca)
        if not defaults:
            continue
        ten_ca, bat_dau, ket_thuc, toi_thieu, toi_da = defaults
        if not loai_ca.ten_ca:
            loai_ca.ten_ca = ten_ca
            changed = True
        if loai_ca.gio_bat_dau is None:
            loai_ca.gio_bat_dau = bat_dau
            changed = True
        if loai_ca.gio_ket_thuc is None:
            loai_ca.gio_ket_thuc = ket_thuc
            changed = True
        if loai_ca.so_nv_toi_thieu is None:
            loai_ca.so_nv_toi_thieu = toi_thieu
            changed = True
        if loai_ca.so_nv_toi_da is None:
            loai_ca.so_nv_toi_da = toi_da
            changed = True
    if changed:
        db.commit()
