import re
from datetime import datetime, timedelta
from typing import Optional, Tuple
from sqlalchemy.orm import Session
from sqlalchemy import or_
from app.models.user import TaiKhoan, LichSuDangNhap
from app.models.employee import NhanVien
from app.core.security import (
    verify_password, create_access_token, create_refresh_token,
    validate_password_complexity, get_password_hash
)
from app.config import settings

class AuthService:
    @staticmethod
    def authenticate_user(
        db: Session,
        login_identifier: str,
        password: str,
        client_ip: Optional[str] = None
    ) -> Tuple[Optional[TaiKhoan], Optional[str], Optional[dict]]:
        """
        Xác thực đăng nhập theo FR-02:
        - Cho phép đăng nhập bằng tên đăng nhập, email hoặc số điện thoại.
        - Kiểm tra khóa tài khoản (Brute-force lockout).
        - Ghi log lịch sử đăng nhập.
        - Trả về (user, error_message, tokens).
        """
        # Tìm tài khoản qua ten_dang_nhap hoặc qua liên kết nhân viên (email, số điện thoại)
        user = db.query(TaiKhoan).outerjoin(NhanVien, TaiKhoan.ma_nv == NhanVien.id).filter(
            or_(
                TaiKhoan.ten_dang_nhap == login_identifier,
                NhanVien.email == login_identifier,
                NhanVien.so_dien_thoai == login_identifier
            )
        ).first()

        if not user:
            return None, "Tên đăng nhập, email hoặc số điện thoại không tồn tại trên hệ thống", None

        # Kiểm tra nếu tài khoản bị vô hiệu hóa
        if not user.is_active:
            return None, "Tài khoản của bạn đã bị vô hiệu hóa bởi Quản trị viên", None

        # FR-06: Kiểm tra nếu nhân viên đã nghỉ việc
        if user.nhan_vien and user.nhan_vien.trang_thai == "da_nghi":
            return None, "Tài khoản không thể đăng nhập vì nhân viên đã ở trạng thái 'Đã nghỉ việc'", None

        now = datetime.utcnow()

        # Kiểm tra brute-force lockout
        if user.lockout_until:
            if user.lockout_until > now:
                remaining_seconds = int((user.lockout_until - now).total_seconds())
                remaining_minutes = max(1, remaining_seconds // 60)
                # Ghi log lần thử trong lúc đang bị khóa
                log_entry = LichSuDangNhap(
                    ma_tai_khoan=user.id,
                    dia_chi_ip=client_ip,
                    trang_thai="khoa_tam_thoi"
                )
                db.add(log_entry)
                db.commit()
                return None, f"Tài khoản đang bị tạm khóa do nhập sai quá 5 lần. Vui lòng thử lại sau {remaining_minutes} phút", None
            else:
                # Đã hết thời gian khóa, reset lại
                user.lockout_until = None
                user.so_lan_dang_nhap_sai = 0
                db.commit()

        # Xác thực mật khẩu
        if not verify_password(password, user.mat_khau):
            user.so_lan_dang_nhap_sai = (user.so_lan_dang_nhap_sai or 0) + 1
            if user.so_lan_dang_nhap_sai >= settings.MAX_FAILED_ATTEMPTS:
                user.lockout_until = now + timedelta(minutes=settings.LOCKOUT_MINUTES)
                log_entry = LichSuDangNhap(
                    ma_tai_khoan=user.id,
                    dia_chi_ip=client_ip,
                    trang_thai="khoa_tam_thoi"
                )
                db.add(log_entry)
                db.commit()
                return None, f"Bạn đã nhập sai 5 lần liên tiếp. Tài khoản đã bị tạm khóa 15 phút để bảo đảm an toàn", None
            else:
                remaining_attempts = settings.MAX_FAILED_ATTEMPTS - user.so_lan_dang_nhap_sai
                log_entry = LichSuDangNhap(
                    ma_tai_khoan=user.id,
                    dia_chi_ip=client_ip,
                    trang_thai="that_bai"
                )
                db.add(log_entry)
                db.commit()
                return None, f"Mật khẩu không chính xác. Bạn còn {remaining_attempts} lần thử trước khi tài khoản bị khóa 15 phút", None

        # Đăng nhập thành công
        user.so_lan_dang_nhap_sai = 0
        user.lockout_until = None
        user.da_dang_nhap_lan_cuoi = now

        log_entry = LichSuDangNhap(
            ma_tai_khoan=user.id,
            dia_chi_ip=client_ip,
            trang_thai="thanh_cong"
        )
        db.add(log_entry)
        db.commit()

        # Tạo tokens
        role_name = user.vai_tro.ten_vai_tro if user.vai_tro else "Staff"
        payload = {
            "sub": user.ten_dang_nhap,
            "user_id": user.id,
            "role": role_name,
            "nv_id": user.ma_nv
        }
        access_token = create_access_token(payload)
        refresh_token = create_refresh_token(payload)

        return user, None, {
            "access_token": access_token,
            "refresh_token": refresh_token,
            "expires_in": settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60
        }

    @staticmethod
    def register_account(
        db: Session,
        ten_dang_nhap: str,
        mat_khau: str,
        ho_ten: str,
        email: Optional[str] = None,
        so_dien_thoai: Optional[str] = None,
        ma_vai_tro: int = 3,
        ma_cua_hang: Optional[int] = None,
        ma_vi_tri: Optional[int] = None
    ) -> Tuple[Optional[TaiKhoan], Optional[str]]:
        """
        Đăng ký tài khoản theo FR-01:
        - Kiểm tra độ phức tạp mật khẩu (≥ 8 ký tự, gồm chữ và số).
        - Kiểm tra trùng lặp tên đăng nhập, email, số điện thoại.
        - Băm mật khẩu bằng bcrypt.
        """
        # Kiểm tra độ phức tạp mật khẩu
        if not validate_password_complexity(mat_khau):
            return None, "Mật khẩu phải có độ dài tối thiểu 8 ký tự và bao gồm cả chữ cái lẫn chữ số"

        # Kiểm tra trùng lặp tên đăng nhập
        if db.query(TaiKhoan).filter(TaiKhoan.ten_dang_nhap == ten_dang_nhap).first():
            return None, f"Tên đăng nhập '{ten_dang_nhap}' đã tồn tại trên hệ thống"

        # Kiểm tra trùng lặp email
        if email and db.query(NhanVien).filter(NhanVien.email == email).first():
            return None, f"Email '{email}' đã được đăng ký cho nhân viên khác"

        # Kiểm tra định dạng số điện thoại
        if so_dien_thoai:
            cleaned_phone = re.sub(r"[\s.-]", "", so_dien_thoai.strip())
            if not re.match(r"^(?:0|\+84)\d{9}$", cleaned_phone):
                return None, "Số điện thoại không hợp lệ (phải gồm 10 chữ số bắt đầu bằng số 0 và không chứa chữ cái)"
            so_dien_thoai = cleaned_phone

        # Kiểm tra trùng lặp số điện thoại
        if so_dien_thoai and db.query(NhanVien).filter(NhanVien.so_dien_thoai == so_dien_thoai).first():
            return None, f"Số điện thoại '{so_dien_thoai}' đã được đăng ký cho nhân viên khác"

        # Tạo hồ sơ nhân viên trước
        # Sinh mã nhân viên tự động NVxxx
        count = db.query(NhanVien).count() + 1
        ma_nv_gen = f"NV{count:03d}"

        nhan_vien = NhanVien(
            ma_nhan_vien=ma_nv_gen,
            ma_cua_hang=ma_cua_hang,
            ma_vi_tri=ma_vi_tri,
            ho_ten=ho_ten,
            email=email,
            so_dien_thoai=so_dien_thoai,
            trang_thai="dang_lam"
        )
        db.add(nhan_vien)
        db.flush()

        # Tạo tài khoản đăng nhập với mật khẩu băm bcrypt
        hashed_password = get_password_hash(mat_khau)
        tai_khoan = TaiKhoan(
            ma_nv=nhan_vien.id,
            ma_vai_tro=ma_vai_tro,
            ten_dang_nhap=ten_dang_nhap,
            mat_khau=hashed_password,
            is_active=True
        )
        db.add(tai_khoan)
        db.commit()
        db.refresh(tai_khoan)

        return tai_khoan, None
