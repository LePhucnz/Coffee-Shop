import pytest
from app.core.security import validate_password_complexity

def test_password_complexity():
    """FR-01: Mật khẩu phải đạt độ phức tạp tối thiểu: ≥ 8 ký tự, gồm chữ và số"""
    assert validate_password_complexity("short1") is False  # < 8 chars
    assert validate_password_complexity("alllettersonly") is False  # no digit
    assert validate_password_complexity("1234567890") is False  # no letters
    assert validate_password_complexity("ValidPass123") is True
    assert validate_password_complexity("Admin@123456") is True

def test_register_account(client):
    """FR-01: Đăng ký tài khoản người dùng mới thành công"""
    response = client.post(
        "/api/auth/register",
        json={
            "ten_dang_nhap": "nv_test_01",
            "mat_khau": "Password123",
            "ho_ten": "Nhân viên Test 01",
            "email": "test01@coffeeshop.com",
            "so_dien_thoai": "0988111222",
            "ma_vai_tro": 3
        }
    )
    assert response.status_code == 201
    data = response.json()
    assert data["ten_dang_nhap"] == "nv_test_01"
    assert data["is_active"] is True

def test_register_duplicate_username(client):
    """FR-01: Kiểm tra chống trùng lặp tên đăng nhập"""
    response = client.post(
        "/api/auth/register",
        json={
            "ten_dang_nhap": "nguyen.a",  # Đã tồn tại từ seed
            "mat_khau": "Password123",
            "ho_ten": "Trùng tên",
            "email": "trung@coffeeshop.com"
        }
    )
    assert response.status_code == 400
    assert "đã tồn tại" in response.json()["detail"]

def test_login_success(client):
    """FR-02: Đăng nhập thành công trả về JWT tokens"""
    response = client.post(
        "/api/auth/login",
        json={
            "ten_dang_nhap": "nguyen.a",
            "mat_khau": "Admin@123456"
        }
    )
    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert "refresh_token" in data
    assert data["token_type"] == "bearer"
    assert data["user"]["ten_dang_nhap"] == "nguyen.a"

def test_brute_force_lockout(client):
    """
    FR-02: Đăng nhập sai quá 5 lần liên tiếp:
    Tạm khóa tài khoản trong 15 phút (chống brute-force)
    """
    # 5 lần thử sai mật khẩu
    for i in range(1, 5):
        resp = client.post(
            "/api/auth/login",
            json={"ten_dang_nhap": "tran.b", "mat_khau": "WrongPass"}
        )
        assert resp.status_code == 400
        assert "Mật khẩu không chính xác" in resp.json()["detail"]

    # Lần thứ 5 sai -> bị khóa
    resp5 = client.post(
        "/api/auth/login",
        json={"ten_dang_nhap": "tran.b", "mat_khau": "WrongPass"}
    )
    assert resp5.status_code == 403 or resp5.status_code == 400
    assert "tạm khóa 15 phút" in resp5.json()["detail"]

    # Lần thứ 6 (kể cả nhập đúng mật khẩu trong lúc đang bị khóa vẫn bị chặn)
    resp6 = client.post(
        "/api/auth/login",
        json={"ten_dang_nhap": "tran.b", "mat_khau": "Staff@123456"}
    )
    assert resp6.status_code == 403
    assert "tạm khóa" in resp6.json()["detail"]

def test_rbac_access_control(client):
    """
    FR-03: Phân quyền vai trò:
    - Staff truy cập endpoint Admin bị từ chối 403 Forbidden
    - Admin truy cập endpoint Admin thành công 200 OK
    """
    # 1. Đăng nhập tài khoản Staff: le.c
    staff_login = client.post(
        "/api/auth/login",
        json={"ten_dang_nhap": "le.c", "mat_khau": "Staff@123456"}
    )
    assert staff_login.status_code == 200
    staff_token = staff_login.json()["access_token"]

    # Staff thử truy cập danh sách nhân sự toàn quán (chỉ dành cho Admin/Manager)
    staff_resp = client.get(
        "/api/employees",
        headers={"Authorization": f"Bearer {staff_token}"}
    )
    assert staff_resp.status_code == 403
    assert "Truy cập bị từ chối" in staff_resp.json()["detail"]

    # 2. Đăng nhập tài khoản Admin: nguyen.a
    admin_login = client.post(
        "/api/auth/login",
        json={"ten_dang_nhap": "nguyen.a", "mat_khau": "Admin@123456"}
    )
    admin_token = admin_login.json()["access_token"]

    # Admin truy cập danh sách nhân sự
    admin_resp = client.get(
        "/api/employees",
        headers={"Authorization": f"Bearer {admin_token}"}
    )
    assert admin_resp.status_code == 200
    assert "items" in admin_resp.json()

def test_login_history_logged(client):
    """FR-02: Hệ thống ghi log lịch sử đăng nhập (thời gian, IP)"""
    admin_login = client.post(
        "/api/auth/login",
        json={"ten_dang_nhap": "nguyen.a", "mat_khau": "Admin@123456"}
    )
    admin_token = admin_login.json()["access_token"]

    resp = client.get(
        "/api/auth/login-history",
        headers={"Authorization": f"Bearer {admin_token}"}
    )
    assert resp.status_code == 200
    logs = resp.json()
    assert len(logs) > 0
    assert "thoi_gian_dang_nhap" in logs[0]

def test_login_with_email_and_phone(client):
    """FR-02: Đăng nhập bằng Email và Số điện thoại"""
    # Đăng nhập bằng email
    resp_email = client.post(
        "/api/auth/login",
        json={"ten_dang_nhap": "nva@coffeeshop.com", "mat_khau": "Admin@123456"}
    )
    assert resp_email.status_code == 200
    assert "access_token" in resp_email.json()

    # Đăng nhập bằng số điện thoại
    resp_phone = client.post(
        "/api/auth/login",
        json={"ten_dang_nhap": "0901234567", "mat_khau": "Admin@123456"}
    )
    assert resp_phone.status_code == 200
    assert "access_token" in resp_phone.json()

def test_register_weak_password(client):
    """FR-01: Đăng ký thất bại nếu mật khẩu không đạt chuẩn độ phức tạp"""
    # Mật khẩu quá ngắn
    resp1 = client.post(
        "/api/auth/register",
        json={"ten_dang_nhap": "weak_user_1", "mat_khau": "short", "ho_ten": "Weak Pass 1"}
    )
    assert resp1.status_code in [400, 422]

    # Mật khẩu không chứa số
    resp2 = client.post(
        "/api/auth/register",
        json={"ten_dang_nhap": "weak_user_2", "mat_khau": "onlyletters", "ho_ten": "Weak Pass 2"}
    )
    assert resp2.status_code == 400
    assert "độ dài tối thiểu 8 ký tự" in resp2.json()["detail"]

def test_forgot_password_and_reset_flow(client):
    """
    Test toàn bộ luồng Quên mật khẩu & Đặt lại mật khẩu:
    1. Gửi yêu cầu quên mật khẩu với email
    2. Nhận reset_token
    3. Đặt lại mật khẩu mới với token
    4. Đăng nhập thành công với mật khẩu mới
    """
    # 1. Yêu cầu quên mật khẩu với email hợp lệ
    forgot_resp = client.post(
        "/api/auth/forgot-password",
        json={"email": "nva@coffeeshop.com"}
    )
    assert forgot_resp.status_code == 200
    forgot_data = forgot_resp.json()
    assert forgot_data["success"] is True
    assert forgot_data["reset_token"] is not None
    assert "/reset-password?token=" in forgot_data["reset_url"]

    reset_token = forgot_data["reset_token"]

    # 2. Thử đặt mật khẩu mới quá yếu -> lỗi
    weak_reset = client.post(
        "/api/auth/reset-password",
        json={"token": reset_token, "mat_khau": "weakpass"}
    )
    assert weak_reset.status_code == 400
    assert "độ dài tối thiểu 8 ký tự" in weak_reset.json()["detail"]

    # 3. Đặt mật khẩu mới hợp lệ
    valid_reset = client.post(
        "/api/auth/reset-password",
        json={"token": reset_token, "mat_khau": "NewPassword2026!"}
    )
    assert valid_reset.status_code == 200
    assert valid_reset.json()["success"] is True

    # 4. Đăng nhập bằng mật khẩu mới
    new_login = client.post(
        "/api/auth/login",
        json={"ten_dang_nhap": "nguyen.a", "mat_khau": "NewPassword2026!"}
    )
    assert new_login.status_code == 200
    assert "access_token" in new_login.json()

    # Phục hồi lại mật khẩu cũ để không ảnh hưởng các bài test khác
    restore_resp = client.post(
        "/api/auth/reset-password",
        json={"email": "nva@coffeeshop.com", "mat_khau": "Admin@123456"}
    )
    assert restore_resp.status_code == 200

def test_forgot_password_nonexistent_email(client):
    """Quên mật khẩu với email không tồn tại vẫn trả về thông báo an toàn"""
    resp = client.post(
        "/api/auth/forgot-password",
        json={"email": "unknown_email_9999@test.com"}
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["success"] is True
    assert data["reset_token"] is None

def test_reset_password_invalid_token(client):
    """Đặt lại mật khẩu với token giả mạo hoặc sai định dạng"""
    resp = client.post(
        "/api/auth/reset-password",
        json={"token": "invalid_token_xyz", "mat_khau": "ValidPass123"}
    )
    assert resp.status_code == 400
    assert "không hợp lệ hoặc đã hết hạn" in resp.json()["detail"]
