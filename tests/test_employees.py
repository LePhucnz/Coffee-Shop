import pytest

def get_admin_token(client):
    res = client.post(
        "/api/auth/login",
        json={"ten_dang_nhap": "nguyen.a", "mat_khau": "Admin@123456"}
    )
    return res.json()["access_token"]

def test_create_and_get_employee(client):
    """FR-04: Thêm và xem chi tiết hồ sơ nhân sự"""
    token = get_admin_token(client)
    headers = {"Authorization": f"Bearer {token}"}

    create_resp = client.post(
        "/api/employees",
        headers=headers,
        json={
            "ho_ten": "Võ Thị Sáu",
            "so_dien_thoai": "0911223344",
            "email": "vtsau@coffeeshop.com",
            "cccd": "079199000888",
            "ma_vi_tri": 2,
            "ma_cua_hang": 1,
            "trang_thai": "dang_lam",
            "tao_tai_khoan": True,
            "ten_dang_nhap": "vo.sau",
            "mat_khau": "Staff@123456"
        }
    )
    assert create_resp.status_code == 201
    emp_data = create_resp.json()
    assert emp_data["ho_ten"] == "Võ Thị Sáu"
    assert emp_data["cccd"] == "079199000888"
    assert emp_data["ten_dang_nhap"] == "vo.sau"

    # Xem chi tiết
    get_resp = client.get(f"/api/employees/{emp_data['id']}", headers=headers)
    assert get_resp.status_code == 200
    assert get_resp.json()["ho_ten"] == "Võ Thị Sáu"

def test_employee_search_and_filter(client):
    """FR-04: Tìm kiếm và lọc hồ sơ theo họ tên, vị trí, trạng thái"""
    token = get_admin_token(client)
    headers = {"Authorization": f"Bearer {token}"}

    # Tìm kiếm theo tên
    search_resp = client.get("/api/employees?keyword=Nguyễn Văn A", headers=headers)
    assert search_resp.status_code == 200
    items = search_resp.json()["items"]
    assert len(items) >= 1
    assert items[0]["ho_ten"] == "Nguyễn Văn A"

    # Lọc theo vị trí Pha chế (ID = 2)
    filter_resp = client.get("/api/employees?ma_vi_tri=2", headers=headers)
    assert filter_resp.status_code == 200
    for it in filter_resp.json()["items"]:
        assert it["ma_vi_tri"] == 2

def test_employee_soft_delete(client):
    """
    FR-04: Xóa hồ sơ thực chất là 'vô hiệu hóa' (soft delete)
    để bảo toàn dữ liệu lịch sử chấm công/lương liên quan
    """
    token = get_admin_token(client)
    headers = {"Authorization": f"Bearer {token}"}

    # Tạo một nhân viên để test xóa
    create_resp = client.post(
        "/api/employees",
        headers=headers,
        json={
            "ho_ten": "Nhân Viên Sẽ Xóa",
            "trang_thai": "dang_lam"
        }
    )
    emp_id = create_resp.json()["id"]

    # Xóa mềm
    del_resp = client.delete(f"/api/employees/{emp_id}", headers=headers)
    assert del_resp.status_code == 200

    # Kiểm tra danh sách mặc định không còn xuất hiện
    list_resp = client.get("/api/employees", headers=headers)
    ids = [e["id"] for e in list_resp.json()["items"]]
    assert emp_id not in ids

    # Nhưng có trong danh sách khi yêu cầu include_deleted=True
    deleted_list_resp = client.get("/api/employees?include_deleted=true", headers=headers)
    deleted_ids = [e["id"] for e in deleted_list_resp.json()["items"]]
    assert emp_id in deleted_ids

def test_resigned_employee_cannot_login(client):
    """
    FR-06: Nhân viên ở trạng thái "Đã nghỉ việc" không thể đăng nhập
    """
    token = get_admin_token(client)
    headers = {"Authorization": f"Bearer {token}"}

    # Tạo nhân viên mới kèm tài khoản
    create_resp = client.post(
        "/api/employees",
        headers=headers,
        json={
            "ho_ten": "Nhân viên Nghỉ việc",
            "trang_thai": "dang_lam",
            "tao_tai_khoan": True,
            "ten_dang_nhap": "nv.nghiviec",
            "mat_khau": "Staff@123456"
        }
    )
    emp_id = create_resp.json()["id"]

    # Chuyển trạng thái sang 'da_nghi'
    status_resp = client.patch(
        f"/api/employees/{emp_id}/status",
        headers=headers,
        json={"trang_thai": "da_nghi"}
    )
    assert status_resp.status_code == 200
    assert status_resp.json()["trang_thai"] == "da_nghi"

    # Thử đăng nhập bằng tài khoản này -> Bị từ chối
    login_resp = client.post(
        "/api/auth/login",
        json={"ten_dang_nhap": "nv.nghiviec", "mat_khau": "Staff@123456"}
    )
    assert login_resp.status_code in [400, 403]
    assert "Đã nghỉ việc" in login_resp.json()["detail"] or "vô hiệu hóa" in login_resp.json()["detail"]
