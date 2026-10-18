import pytest
import io

@pytest.fixture()
def admin_token(client):
    res = client.post("/api/auth/login", json={"ten_dang_nhap": "nguyen.a", "mat_khau": "Admin@123456"})
    assert res.status_code == 200
    return res.json()["access_token"]

@pytest.fixture()
def staff_token(client):
    res = client.post("/api/auth/login", json={"ten_dang_nhap": "le.c", "mat_khau": "Staff@123456"})
    assert res.status_code == 200
    return res.json()["access_token"]


# ==================== AUTH EXTENDED ====================

def test_auth_logout(client, staff_token):
    res = client.post("/api/auth/logout", headers={"Authorization": f"Bearer {staff_token}"})
    assert res.status_code == 200
    assert "Đăng xuất thành công" in res.json()["message"]


def test_auth_change_password(client):
    # Register a new user to test password change
    reg = client.post(
        "/api/auth/register",
        json={
            "ten_dang_nhap": "user_pw_test",
            "mat_khau": "OldPassword123",
            "ho_ten": "User PW Test",
            "email": "unique_pw_test@coffeeshop.com",
            "so_dien_thoai": "0912999888"
        }
    )
    assert reg.status_code == 201
    
    login = client.post("/api/auth/login", json={"ten_dang_nhap": "user_pw_test", "mat_khau": "OldPassword123"})
    token = login.json()["access_token"]
    
    # 1. Wrong old password
    bad_old = client.post(
        "/api/auth/change-password",
        headers={"Authorization": f"Bearer {token}"},
        json={"mat_khau_cu": "WrongPass123", "mat_khau_moi": "NewPassword123"}
    )
    assert bad_old.status_code == 400
    assert "không chính xác" in bad_old.json()["detail"]
    
    # 2. Invalid new password (too short or no digit)
    bad_new = client.post(
        "/api/auth/change-password",
        headers={"Authorization": f"Bearer {token}"},
        json={"mat_khau_cu": "OldPassword123", "mat_khau_moi": "short"}
    )
    assert bad_new.status_code in [400, 422]

    # 3. Successful change
    ok_change = client.post(
        "/api/auth/change-password",
        headers={"Authorization": f"Bearer {token}"},
        json={"mat_khau_cu": "OldPassword123", "mat_khau_moi": "NewPassword123"}
    )
    assert ok_change.status_code == 200
    assert "Đổi mật khẩu thành công" in ok_change.json()["message"]

    # 4. Verify login with new password
    new_login = client.post("/api/auth/login", json={"ten_dang_nhap": "user_pw_test", "mat_khau": "NewPassword123"})
    assert new_login.status_code == 200


def test_auth_list_and_get_users(client, admin_token, staff_token):
    # Staff forbidden
    staff_res = client.get("/api/auth/users", headers={"Authorization": f"Bearer {staff_token}"})
    assert staff_res.status_code == 403

    # Admin allowed
    admin_res = client.get("/api/auth/users", headers={"Authorization": f"Bearer {admin_token}"})
    assert admin_res.status_code == 200
    users = admin_res.json()
    assert len(users) >= 4
    
    # Filter by keyword
    kw_res = client.get("/api/auth/users?keyword=nguyen.a", headers={"Authorization": f"Bearer {admin_token}"})
    assert kw_res.status_code == 200
    assert any(u["ten_dang_nhap"] == "nguyen.a" for u in kw_res.json())

    # Get single user
    user_id = users[0]["id"]
    single_res = client.get(f"/api/auth/users/{user_id}", headers={"Authorization": f"Bearer {admin_token}"})
    assert single_res.status_code == 200
    assert single_res.json()["id"] == user_id

    # Get non-existent user
    not_found = client.get("/api/auth/users/999999", headers={"Authorization": f"Bearer {admin_token}"})
    assert not_found.status_code == 404


# ==================== SYSTEM EXTENDED ====================

def test_system_stores_crud(client, admin_token, staff_token):
    # 1. List stores (public/auth)
    list_res = client.get("/api/system/stores")
    assert list_res.status_code == 200
    initial_count = len(list_res.json())

    # 2. Staff cannot create store
    staff_create = client.post(
        "/api/system/stores",
        headers={"Authorization": f"Bearer {staff_token}"},
        json={"ten_cua_hang": "Chi nhánh Test Staff", "dia_chi": "Hà Nội"}
    )
    assert staff_create.status_code == 403

    # 3. Admin creates store
    admin_create = client.post(
        "/api/system/stores",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={"ten_cua_hang": "Chi nhánh Bình Thạnh", "dia_chi": "456 Điện Biên Phủ, Bình Thạnh", "vi_do": 10.8000, "kinh_do": 106.7000}
    )
    assert admin_create.status_code == 201
    store = admin_create.json()
    store_id = store["id"]
    assert store["ten_cua_hang"] == "Chi nhánh Bình Thạnh"

    # 4. Get store detail
    get_res = client.get(f"/api/system/stores/{store_id}")
    assert get_res.status_code == 200
    assert get_res.json()["dia_chi"] == "456 Điện Biên Phủ, Bình Thạnh"

    # 5. Admin updates store
    update_res = client.put(
        f"/api/system/stores/{store_id}",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={"ten_cua_hang": "The Coffee Shop - Bình Thạnh"}
    )
    assert update_res.status_code == 200
    assert update_res.json()["ten_cua_hang"] == "The Coffee Shop - Bình Thạnh"

    # 6. Admin deletes store
    del_res = client.delete(f"/api/system/stores/{store_id}", headers={"Authorization": f"Bearer {admin_token}"})
    assert del_res.status_code == 200

    # Verify not found after delete
    del_verify = client.get(f"/api/system/stores/{store_id}")
    assert del_verify.status_code == 404


def test_system_positions_crud(client, admin_token, staff_token):
    # 1. Staff cannot create position
    staff_create = client.post(
        "/api/system/positions",
        headers={"Authorization": f"Bearer {staff_token}"},
        json={"ten_vi_tri": "Tạp vụ", "mo_ta": "Vệ sinh cửa hàng"}
    )
    assert staff_create.status_code == 403

    # 2. Admin creates position
    create_res = client.post(
        "/api/system/positions",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={"ten_vi_tri": "Bảo vệ", "mo_ta": "Trông giữ xe và an ninh"}
    )
    assert create_res.status_code == 201
    pos = create_res.json()
    pos_id = pos["id"]
    assert pos["ten_vi_tri"] == "Bảo vệ"

    # 3. Get position
    get_res = client.get(f"/api/system/positions/{pos_id}")
    assert get_res.status_code == 200
    assert get_res.json()["mo_ta"] == "Trông giữ xe và an ninh"

    # 4. Update position
    up_res = client.put(
        f"/api/system/positions/{pos_id}",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={"ten_vi_tri": "Nhân viên An ninh"}
    )
    assert up_res.status_code == 200
    assert up_res.json()["ten_vi_tri"] == "Nhân viên An ninh"

    # 5. Delete position
    del_res = client.delete(f"/api/system/positions/{pos_id}", headers={"Authorization": f"Bearer {admin_token}"})
    assert del_res.status_code == 200

    assert client.get(f"/api/system/positions/{pos_id}").status_code == 404


def test_system_audit_logs(client, admin_token, staff_token):
    # Staff forbidden
    assert client.get("/api/system/audit-logs", headers={"Authorization": f"Bearer {staff_token}"}).status_code == 403

    # Admin allowed
    res = client.get("/api/system/audit-logs", headers={"Authorization": f"Bearer {admin_token}"})
    assert res.status_code == 200
    assert isinstance(res.json(), list)


# ==================== EMPLOYEES EXTENDED ====================

def test_employee_me_and_avatar(client, staff_token, admin_token):
    # Staff gets own profile
    me_res = client.get("/api/employees/me", headers={"Authorization": f"Bearer {staff_token}"})
    assert me_res.status_code == 200
    data = me_res.json()
    assert data["ho_ten"] == "Lê Văn C"
    staff_emp_id = data["id"]

    # Staff updates own profile
    update_me = client.put(
        "/api/employees/me",
        headers={"Authorization": f"Bearer {staff_token}"},
        json={"dia_chi": "Số 99 Lê Văn Việt, TP Thủ Đức"}
    )
    assert update_me.status_code == 200
    assert update_me.json()["dia_chi"] == "Số 99 Lê Văn Việt, TP Thủ Đức"

    # Staff uploads own avatar
    fake_img = io.BytesIO(b"\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01\x01\x01\x00`\x00`\x00\x00\xff\xdb\x00C\x00")
    avatar_res = client.post(
        f"/api/employees/{staff_emp_id}/avatar",
        headers={"Authorization": f"Bearer {staff_token}"},
        files={"file": ("avatar.jpg", fake_img, "image/jpeg")}
    )
    assert avatar_res.status_code == 200
    assert avatar_res.json()["anh_dai_dien"] is not None

    # Staff cannot upload someone else's avatar
    other_avatar = client.post(
        "/api/employees/1/avatar",
        headers={"Authorization": f"Bearer {staff_token}"},
        files={"file": ("avatar.jpg", io.BytesIO(b"fake image data"), "image/jpeg")}
    )
    assert other_avatar.status_code == 403


# ==================== SHIFTS EXTENDED ====================

def test_shift_types_and_assignments(client, admin_token, staff_token):
    # 1. Get shift type detail
    types = client.get("/api/shifts/types", headers={"Authorization": f"Bearer {admin_token}"}).json()
    assert len(types) > 0
    type_id = types[0]["id"]

    res_type = client.get(f"/api/shifts/types/{type_id}", headers={"Authorization": f"Bearer {staff_token}"})
    assert res_type.status_code == 200
    assert res_type.json()["id"] == type_id

    # 2. Create and delete temporary shift type
    new_type = client.post(
        "/api/shifts/types",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={
            "ma_loai_ca": "CA_DEM_TEST",
            "ten_ca": "Ca Đêm Test",
            "gio_bat_dau": "22:00:00",
            "gio_ket_thuc": "06:00:00",
            "so_nv_toi_thieu": 1,
            "so_nv_toi_da": 2
        }
    )
    assert new_type.status_code == 201
    new_type_id = new_type.json()["id"]

    del_type = client.delete(f"/api/shifts/types/{new_type_id}", headers={"Authorization": f"Bearer {admin_token}"})
    assert del_type.status_code == 200

    # 3. Get assignment detail
    sched = client.get("/api/shifts/schedule", headers={"Authorization": f"Bearer {admin_token}"}).json()
    if sched.get("phan_cong"):
        pc_id = sched["phan_cong"][0]["id"]
        res_pc = client.get(f"/api/shifts/assignments/{pc_id}", headers={"Authorization": f"Bearer {admin_token}"})
        assert res_pc.status_code == 200
        assert res_pc.json()["id"] == pc_id


# ==================== ATTENDANCE EXTENDED ====================

def test_attendance_periods_get(client, admin_token):
    res = client.get("/api/attendance/periods", headers={"Authorization": f"Bearer {admin_token}"})
    assert res.status_code == 200
    periods = res.json()
    if periods:
        p_id = periods[0]["id"]
        single = client.get(f"/api/attendance/periods/{p_id}", headers={"Authorization": f"Bearer {admin_token}"})
        assert single.status_code == 200
        assert single.json()["id"] == p_id

    not_found = client.get("/api/attendance/periods/999999", headers={"Authorization": f"Bearer {admin_token}"})
    assert not_found.status_code == 404


# ==================== PAYROLL EXTENDED ====================

def test_payroll_holidays_and_payslips(client, admin_token, staff_token):
    # 1. List holidays
    holidays = client.get("/api/payroll/holidays", headers={"Authorization": f"Bearer {admin_token}"})
    assert holidays.status_code == 200
    items = holidays.json()
    assert len(items) > 0

    # 2. Get single holiday
    h_id = items[0]["id"]
    single_h = client.get(f"/api/payroll/holidays/{h_id}", headers={"Authorization": f"Bearer {admin_token}"})
    assert single_h.status_code == 200
    assert single_h.json()["id"] == h_id

    # 3. Update holiday
    up_h = client.put(
        f"/api/payroll/holidays/{h_id}",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={"ngay": items[0]["ngay"], "ten": "Lễ cập nhật test", "he_so": 2.5}
    )
    assert up_h.status_code == 200

    # 4. List all payslips
    payslips = client.get("/api/payroll/payslips", headers={"Authorization": f"Bearer {admin_token}"})
    assert payslips.status_code == 200
    assert isinstance(payslips.json(), list)

    # Staff forbidden for /payslips
    assert client.get("/api/payroll/payslips", headers={"Authorization": f"Bearer {staff_token}"}).status_code == 403


# ==================== NOTIFICATIONS EXTENDED ====================

def test_notifications_create_and_delete(client, admin_token, staff_token):
    # 1. Staff forbidden to create notification
    bad_create = client.post(
        "/api/notifications",
        headers={"Authorization": f"Bearer {staff_token}"},
        json={"tieu_de": "Thông báo thử", "noi_dung": "Nội dung thử"}
    )
    assert bad_create.status_code == 403

    # 2. Admin creates notification for all employees
    ok_create = client.post(
        "/api/notifications",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={"tieu_de": "Họp toàn quán", "noi_dung": "Họp tổng kết tuần sáng thứ Hai lúc 8h00"}
    )
    assert ok_create.status_code == 201
    created_list = ok_create.json()
    assert len(created_list) > 0
    notif_id = created_list[0]["id"]

    # 3. Delete notification
    del_res = client.delete(f"/api/notifications/{notif_id}", headers={"Authorization": f"Bearer {admin_token}"})
    assert del_res.status_code == 200


# ==================== FRONTEND MOUNT ====================

def test_frontend_mount(client):
    res = client.get("/frontend/index.html")
    assert res.status_code == 200
    assert "QL Ca Làm" in res.text
