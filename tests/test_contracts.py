from datetime import date, timedelta
import pytest

def get_admin_token(client):
    res = client.post(
        "/api/auth/login",
        json={"ten_dang_nhap": "nguyen.a", "mat_khau": "Admin@123456"}
    )
    return res.json()["access_token"]

def test_create_and_list_contracts(client):
    """FR-05: Tạo và lấy danh sách hợp đồng lao động"""
    token = get_admin_token(client)
    headers = {"Authorization": f"Bearer {token}"}

    today = date.today()
    create_resp = client.post(
        "/api/contracts",
        headers=headers,
        json={
            "ma_nhan_vien": 1,
            "loai_hop_dong": "Thử việc",
            "muc_luong": 7000000,
            "ngay_bat_dau": str(today),
            "ngay_ket_thuc": str(today + timedelta(days=60)),
            "trang_thai": "hieu_luc"
        }
    )
    assert create_resp.status_code == 201
    contract = create_resp.json()
    assert contract["loai_hop_dong"] == "Thử việc"
    assert contract["ma_nhan_vien"] == 1

    list_resp = client.get("/api/contracts", headers=headers)
    assert list_resp.status_code == 200
    assert len(list_resp.json()) >= 1

def test_expiring_contracts_alert(client):
    """
    FR-05: Hệ thống cảnh báo Admin trước 15-30 ngày khi hợp đồng sắp hết hạn
    """
    token = get_admin_token(client)
    headers = {"Authorization": f"Bearer {token}"}

    today = date.today()
    # Tạo hợp đồng hết hạn sau 20 ngày (nằm trong khoảng 15-30 ngày)
    client.post(
        "/api/contracts",
        headers=headers,
        json={
            "ma_nhan_vien": 2,
            "loai_hop_dong": "Toàn thời gian",
            "muc_luong": 10000000,
            "ngay_bat_dau": str(today - timedelta(days=340)),
            "ngay_ket_thuc": str(today + timedelta(days=20)),
            "trang_thai": "hieu_luc"
        }
    )

    alert_resp = client.get("/api/contracts/expiring?days=30", headers=headers)
    assert alert_resp.status_code == 200
    expiring_list = alert_resp.json()
    assert len(expiring_list) >= 1

    # Kiểm tra hợp đồng sắp hết hạn có số ngày còn lại <= 30
    found_20_days = any(c["so_ngay_con_lai"] == 20 for c in expiring_list)
    assert found_20_days is True

def test_fr05_contract_types_and_file_upload(client):
    """
    FR-05: Hợp đồng với các loại: thử việc, chính thức, thời vụ, mức lương, file đính kèm PDF/scan
    """
    token = get_admin_token(client)
    headers = {"Authorization": f"Bearer {token}"}

    today = date.today()
    create_resp = client.post(
        "/api/contracts",
        headers=headers,
        json={
            "ma_nhan_vien": 1,
            "loai_hop_dong": "Chính thức",
            "muc_luong": 35000,  # mức lương theo giờ
            "ngay_bat_dau": str(today),
            "ngay_ket_thuc": str(today + timedelta(days=365)),
            "trang_thai": "hieu_luc"
        }
    )
    assert create_resp.status_code == 201
    contract = create_resp.json()
    assert contract["loai_hop_dong"] == "Chính thức"
    assert float(contract["muc_luong"]) == 35000.0
    contract_id = contract["id"]

    # Upload file đính kèm (PDF / scan)
    fake_pdf = b"%PDF-1.4 test contract content"
    files = {"file": ("hop_dong_lao_dong.pdf", fake_pdf, "application/pdf")}
    upload_resp = client.post(
        f"/api/contracts/{contract_id}/file",
        headers=headers,
        files=files
    )
    assert upload_resp.status_code == 200
    uploaded_data = upload_resp.json()
    assert uploaded_data["file_dinh_kem"] is not None
    assert uploaded_data["file_dinh_kem"].endswith(".pdf")

def test_fr05_alert_window_15_to_30_days(client):
    """
    FR-05: Hệ thống cảnh báo Admin trước 15-30 ngày khi hợp đồng sắp hết hạn
    """
    token = get_admin_token(client)
    headers = {"Authorization": f"Bearer {token}"}

    today = date.today()
    # Hợp đồng còn 25 ngày (thuộc cửa sổ 15-30 ngày)
    client.post(
        "/api/contracts",
        headers=headers,
        json={
            "ma_nhan_vien": 3,
            "loai_hop_dong": "Thời vụ",
            "muc_luong": 30000,
            "ngay_bat_dau": str(today - timedelta(days=60)),
            "ngay_ket_thuc": str(today + timedelta(days=25)),
            "trang_thai": "hieu_luc"
        }
    )

    # Lấy danh sách cảnh báo trong khoảng 15-30 ngày
    resp = client.get("/api/contracts/expiring?min_days=15&max_days=30", headers=headers)
    assert resp.status_code == 200
    alerts = resp.json()
    assert any(c["so_ngay_con_lai"] == 25 for c in alerts)

