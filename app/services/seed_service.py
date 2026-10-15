from datetime import date, datetime, time, timedelta
from sqlalchemy.orm import Session
from app.models.system import CuaHang, ViTri, VaiTro
from app.models.employee import NhanVien, HopDong
from app.models.user import TaiKhoan
from app.models.shift import LoaiCa
from app.core.security import get_password_hash

def migrate_stores(db: Session):
    """
    Cập nhật cơ sở:
    - Đổi cơ sở Quận 1 thành cơ sở Thủ Đức
    - Chuyển toàn bộ nhân viên ở cơ sở Quận 3 sang cơ sở Thủ Đức (id=1)
    - Xóa cơ sở Quận 3
    """
    try:
        # Chuyển nhân viên từ cơ sở 2 sang cơ sở 1
        db.query(NhanVien).filter(NhanVien.ma_cua_hang == 2).update({NhanVien.ma_cua_hang: 1})
        # Xóa cơ sở Quận 3 nếu có
        q3_stores = db.query(CuaHang).filter(
            (CuaHang.id == 2) | (CuaHang.ten_cua_hang.ilike("%Quận 3%"))
        ).all()
        for s in q3_stores:
            db.query(NhanVien).filter(NhanVien.ma_cua_hang == s.id).update({NhanVien.ma_cua_hang: 1})
            db.delete(s)

        # Đổi cơ sở Quận 1 thành cơ sở Thủ Đức
        s1 = db.query(CuaHang).filter(CuaHang.id == 1).first()
        if s1 and "Quận 1" in s1.ten_cua_hang:
            s1.ten_cua_hang = "The Coffee Shop - Thủ Đức"
            s1.dia_chi = "123 Võ Văn Ngân, TP. Thủ Đức, TP.HCM"
            s1.vi_do = 10.8505
            s1.kinh_do = 106.7719
        db.commit()
    except Exception:
        db.rollback()


def seed_database(db: Session):
    """Nạp dữ liệu mẫu ban đầu nếu cơ sở dữ liệu trống"""
    if db.query(VaiTro).first():
        migrate_stores(db)
        seed_shift_types(db)
        seed_sprint5(db)
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
        CuaHang(id=1, ten_cua_hang="The Coffee Shop - Thủ Đức", dia_chi="123 Võ Văn Ngân, TP. Thủ Đức, TP.HCM", vi_do=10.8505, kinh_do=106.7719, trang_thai=True)
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
            dia_chi="123 Võ Văn Ngân, TP. Thủ Đức, TP.HCM",
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
            dia_chi="456 Kha Vạn Cân, TP. Thủ Đức, TP.HCM",
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
            ma_cua_hang=1,
            ma_vi_tri=3,
            ho_ten="Lê Văn C",
            so_dien_thoai="0923456789",
            email="lvc@coffeeshop.com",
            dia_chi="789 Đặng Văn Bi, TP. Thủ Đức, TP.HCM",
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
    seed_sprint5(db)


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


def seed_sprint5(db: Session):
    """
    Sprint 5: tài khoản Chủ quán (Admin) để duyệt yêu cầu của Quản lý (BR-08) và đổi cấu hình chấm công,
    cùng dữ liệu chấm công mẫu của tuần trước để xem thử các màn hình chấm công.
    Chỉ thêm khi chưa có, không ghi đè dữ liệu nhóm đã tạo.
    """
    from app.models.shift import PhanCongCa, LichCaTuan, ChamCong
    from app.models.attendance import YeuCauChamCong

    if not db.query(TaiKhoan).filter(TaiKhoan.ma_vai_tro == 1).first() and \
            not db.query(TaiKhoan).filter(TaiKhoan.ten_dang_nhap == "chu.quan").first():
        db.add(TaiKhoan(ma_vai_tro=1, ten_dang_nhap="chu.quan",
                        mat_khau=get_password_hash("Admin@123456"), is_active=True))
        db.commit()

    # Dữ liệu chấm công mẫu: tuần trước, cho Trần Thị B (NV002) và Lê Văn C (NV003)
    today = date.today()
    week = today - timedelta(days=today.weekday() + 7)
    if db.query(LichCaTuan).filter(LichCaTuan.tuan_bat_dau == week).first():
        return
    if not db.query(NhanVien).filter(NhanVien.id.in_([2, 3])).count() == 2:
        return
    shift_ids = {lc.ma_loai_ca: lc for lc in db.query(LoaiCa).all()}
    if not {"CA_SANG", "CA_CHIEU", "CA_PARTTIME_1", "CA_PARTTIME_2"} <= set(shift_ids):
        return
    lich = LichCaTuan(tuan_bat_dau=week, trang_thai="da_cong_bo", ngay_cong_bo=datetime.combine(week, time(8, 0)) - timedelta(days=3))
    db.add(lich)
    db.flush()

    def at(day, hh, mm):
        return datetime.combine(week + timedelta(days=day), time(hh, mm))

    store = (10.8505, 106.7719)
    far = (10.8580, 106.7760)  # Cách quán khoảng 900 m
    # (nhân viên, mã ca, thứ, giờ vào, giờ ra, tọa độ)
    samples = [
        (2, "CA_SANG", 0, at(0, 5, 55), at(0, 14, 2), store),         # Đúng giờ
        (2, "CA_SANG", 1, at(1, 6, 12), at(1, 14, 0), store),         # Đi trễ 12 phút
        (2, "CA_CHIEU", 2, at(2, 14, 0), None, store),                # Quên check-out
        (2, "CA_CHIEU", 3, None, None, None),                         # Vắng không phép
        (2, "CA_SANG", 4, at(4, 6, 0), at(4, 13, 30), far),           # Ngoài vị trí, về sớm 30 phút
        (3, "CA_CHIEU", 0, at(0, 13, 58), at(0, 22, 10), store),      # Vượt ca 10 phút chờ duyệt
        (3, "CA_PARTTIME_1", 1, at(1, 8, 0), at(1, 12, 0), store),    # Đúng giờ
        (3, "CA_PARTTIME_2", 2, at(2, 18, 20), at(2, 22, 0), store),  # Đi trễ 20 phút
        (3, "CA_CHIEU", 3, at(3, 14, 1), at(3, 22, 0), None),         # Không có định vị
    ]
    forgot = None
    for ma_nv, ma_ca, day, gio_vao, gio_ra, pos in samples:
        lc = shift_ids[ma_ca]
        pc = PhanCongCa(ma_nv=ma_nv, ma_ca=lc.id, ngay_lam=week + timedelta(days=day), ma_lich_tuan=lich.id,
                        trang_thai="da_cong_bo", bat_dau_thuc_te=gio_vao, ket_thuc_thuc_te=gio_ra)
        db.add(pc)
        db.flush()
        if not gio_vao:
            continue
        cc = ChamCong(
            ma_phan_cong=pc.id, check_in_lan_1=gio_vao, gio_vao_goc=gio_vao, check_out_lan_1=gio_ra, gio_ra_goc=gio_ra,
            vi_do_vao=pos[0] if pos else None, kinh_do_vao=pos[1] if pos else None, ip_vao="192.0.2.24",
            khoang_cach_vao=(0 if pos == store else 900) if pos else None,
            ngoai_vi_tri=pos == far, khong_dinh_vi=pos is None, thiet_bi_trung=False, an_han_ap_dung=5,
            thang=pc.ngay_lam.strftime("%Y-%m"), nam=pc.ngay_lam.year
        )
        db.add(cc)
        if ma_ca == "CA_CHIEU" and gio_ra is None:
            forgot = pc
    db.flush()
    if forgot:
        db.add(YeuCauChamCong(
            ma_phan_cong=forgot.id, ma_nv=2, ma_tai_khoan=2, loai="bu_check_out",
            gio_ra_de_xuat=datetime.combine(forgot.ngay_lam, time(22, 0)),
            ly_do="Tôi quên bấm check-out sau khi bàn giao ca cho ca tối.", trang_thai="cho_duyet",
            han_xu_ly=datetime.combine(forgot.ngay_lam, time(22, 0)) + timedelta(days=3),
            ngay_tao=datetime.combine(forgot.ngay_lam + timedelta(days=1), time(9, 15)),
            ngay_cap_nhat=datetime.combine(forgot.ngay_lam + timedelta(days=1), time(9, 15))
        ))
    db.commit()
