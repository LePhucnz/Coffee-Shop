import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

class Settings:
    PROJECT_NAME: str = "Hệ thống Quản lý Nhân sự & Ca làm - Coffee Shop"
    VERSION: str = "1.0.0"
    
    SECRET_KEY: str = os.getenv("SECRET_KEY", "coffee_shop_secret_key_super_secure_2026_change_in_prod")
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "60"))
    REFRESH_TOKEN_EXPIRE_DAYS: int = int(os.getenv("REFRESH_TOKEN_EXPIRE_DAYS", "14"))
    
    # FR-02: Brute-force protection
    MAX_FAILED_ATTEMPTS: int = 5
    LOCKOUT_MINUTES: int = 15
    
    # Sprint 4 (FR-07): hạn chót đăng ký nguyện vọng ca cho tuần kế tiếp
    # Thứ trong tuần theo Python: 0 = Thứ Hai ... 3 = Thứ Năm ... 6 = Chủ Nhật
    REGISTRATION_DEADLINE_WEEKDAY: int = 3
    REGISTRATION_DEADLINE_HOUR: int = 23
    REGISTRATION_DEADLINE_MINUTE: int = 59

    # Sprint 4 (FR-09): ngưỡng giờ làm tối đa
    MAX_HOURS_PER_DAY: float = 8
    MAX_HOURS_PER_WEEK: float = 48

    # Sprint 5 (FR-11D mục 2): giá trị mặc định của tham số chấm công.
    # Admin sửa được ở trang Cài đặt chấm công (lưu trong bảng cau_hinh_cham_cong).
    ATTENDANCE_DEFAULTS: dict = {
        "mo_truoc_phut": 15,              # Mở nút Check-in trước giờ ca
        "an_han_phut": 5,                 # Trễ/sớm trong mức này vẫn là "Đúng giờ"
        "chong_bam_trung_giay": 60,       # EX-11: bấm trùng trong khoảng này bị bỏ qua
        "ban_kinh_m": 200,                # Ngoài bán kính này gắn cờ "Ngoài vị trí"
        "nguong_chua_checkout_phut": 120, # EX-02: quá giờ kết thúc ca bao lâu thì "Chưa check-out"
        "han_gui_yeu_cau_gio": 48,        # BR-07: hạn gửi yêu cầu bù/sửa công
        "han_xu_ly_ngay": 3,              # Quy tắc 8: hạn Quản lý xử lý yêu cầu
        "han_muc_thang": 3,               # Quy tắc 6: số yêu cầu bù công mỗi tháng
        "do_lech_toi_da_gio": 2,          # Quy tắc 3: lệch quá thì bắt buộc lý do chi tiết
        "so_tep_toi_da": 3,               # Quy tắc 4: minh chứng
        "dung_luong_tep_mb": 5,
        "dai_ip_quan": os.getenv("STORE_IP_PREFIXES", ""),  # VD "113.161.,192.168.1." - IP Wi-Fi quán
    }

    # Sprint 6 (FR-12): chính sách tính lương mặc định.
    # Admin sửa được ở trang Cài đặt lương (lưu chung bảng cau_hinh_cham_cong, khóa riêng).
    PAYROLL_DEFAULTS: dict = {
        "gio_chuan_thang": 208,             # Lương tháng quy đổi ra đơn giá giờ = lương tháng / số giờ này
        "nguong_luong_thang": 1000000,      # Mức lương HĐ từ mức này trở lên được hiểu là lương tháng, dưới là lương giờ
        "cach_phat": "theo_phut",           # 'theo_phut' (trừ theo số phút) | 'co_dinh' (mức cố định mỗi lần)
        "phat_moi_phut": 1000,              # Đồng / phút trễ hoặc sớm
        "phat_moi_lan": 20000,              # Đồng / lần trễ hoặc sớm
        "phat_vang_moi_lan": 0,             # Đồng / ca vắng không phép (0 = không phạt tiền)
        "thuong_chuyen_can": 300000,        # Thưởng khi cả kỳ không trễ, sớm, vắng
        "chuyen_can_so_ca_toi_thieu": 4,    # Phải làm đủ số ca này mới xét chuyên cần
        "chuyen_can_ky_tuan": False,        # Có xét chuyên cần cho kỳ lương tuần hay không
        "he_so_ngay_le_mac_dinh": 2.0,      # Hệ số gợi ý khi thêm ngày lễ mới
    }

    # Database
    DATABASE_URL: str = os.getenv("DATABASE_URL", f"sqlite:///{BASE_DIR / 'qlcl.db'}")

settings = Settings()
