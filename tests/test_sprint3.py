"""
Sprint 3: Quản lý hồ sơ nhân sự, hợp đồng và trạng thái làm việc (FR-04, FR-05, FR-06)
"""
import io
from datetime import date, timedelta
import pytest
from app.services import file_service


def login(client, username, password):
    return client.post("/api/auth/login", json={"ten_dang_nhap": username, "mat_khau": password})


def admin_headers(client):
    res = login(client, "nguyen.a", "Admin@123456")
    return {"Authorization": f"Bearer {res.json()['access_token']}"}


def staff_headers(client):
    res = login(client, "le.c", "Staff@123456")
    return {"Authorization": f"Bearer {res.json()['access_token']}"}


def create_employee(client, headers, **extra):
    payload = {"ho_ten": "Nhân Viên Test", "trang_thai": "dang_lam"}
    payload.update(extra)
    res = client.post("/api/employees", headers=headers, json=payload)
    assert res.status_code == 201, res.text
    return res.json()


@pytest.fixture()
def upload_dir(tmp_path, monkeypatch):
    """Ghi file upload vào thư mục tạm thay vì app/static/uploads"""
    monkeypatch.setattr(file_service, "UPLOAD_ROOT", str(tmp_path))
    return tmp_path


# ---------- FR-03 / Phân quyền ----------

def test_staff_cannot_list_or_create_employees(client):
    headers = staff_headers(client)
    assert client.get("/api/employees", headers=headers).status_code == 403
    assert client.post("/api/employees", headers=headers, json={"ho_ten": "Hacker"}).status_code == 403


def test_staff_can_only_view_own_profile(client):
    headers = staff_headers(client)
    me = login(client, "le.c", "Staff@123456").json()["user"]
    assert client.get(f"/api/employees/{me['ma_nv']}", headers=headers).status_code == 200
    other_id = 1 if me["ma_nv"] != 1 else 2
    assert client.get(f"/api/employees/{other_id}", headers=headers).status_code == 403


def test_staff_only_sees_own_contracts(client):
    headers = staff_headers(client)
    me = login(client, "le.c", "Staff@123456").json()["user"]
    res = client.get("/api/contracts", headers=headers)
    assert res.status_code == 200
    assert all(c["ma_nhan_vien"] == me["ma_nv"] for c in res.json())


# ---------- FR-04: Hồ sơ nhân sự ----------

def test_update_rejects_duplicate_email_and_phone(client):
    headers = admin_headers(client)
    a = create_employee(client, headers, ho_ten="Trùng A", email="trung.a@test.com", so_dien_thoai="0900000101")
    b = create_employee(client, headers, ho_ten="Trùng B", email="trung.b@test.com", so_dien_thoai="0900000102")

    res = client.put(f"/api/employees/{b['id']}", headers=headers, json={"email": a["email"]})
    assert res.status_code == 400
    res = client.put(f"/api/employees/{b['id']}", headers=headers, json={"so_dien_thoai": a["so_dien_thoai"]})
    assert res.status_code == 400
    # Giữ nguyên email của chính mình thì không bị báo trùng
    res = client.put(f"/api/employees/{b['id']}", headers=headers, json={"email": b["email"], "dia_chi": "Q1"})
    assert res.status_code == 200
    assert res.json()["dia_chi"] == "Q1"


def test_update_rejects_invalid_status(client):
    headers = admin_headers(client)
    emp = create_employee(client, headers, ho_ten="Sai Trạng Thái")
    res = client.put(f"/api/employees/{emp['id']}", headers=headers, json={"trang_thai": "abc"})
    assert res.status_code == 422


def test_auto_employee_code_is_unique(client):
    headers = admin_headers(client)
    first = create_employee(client, headers, ho_ten="Mã Tự Sinh 1")
    # Có người nhập tay đúng mã kế tiếp, mã tự sinh tiếp theo vẫn không được trùng
    next_num = int(first["ma_nhan_vien"][2:]) + 1
    create_employee(client, headers, ho_ten="Mã Nhập Tay", ma_nhan_vien=f"NV{next_num:03d}")
    third = create_employee(client, headers, ho_ten="Mã Tự Sinh 2")
    codes = {e["ma_nhan_vien"] for e in client.get("/api/employees?include_deleted=true", headers=headers).json()["items"]}
    assert third["ma_nhan_vien"] in codes
    all_codes = [e["ma_nhan_vien"] for e in client.get("/api/employees?include_deleted=true", headers=headers).json()["items"]]
    assert len(all_codes) == len(set(all_codes))


def test_soft_delete_and_restore_reactivates_account(client):
    headers = admin_headers(client)
    emp = create_employee(
        client, headers, ho_ten="Xóa Mềm", tao_tai_khoan=True,
        ten_dang_nhap="xoa.mem", mat_khau="Staff@123456"
    )
    assert login(client, "xoa.mem", "Staff@123456").status_code == 200

    assert client.delete(f"/api/employees/{emp['id']}", headers=headers).status_code == 200
    ids = [e["id"] for e in client.get("/api/employees", headers=headers).json()["items"]]
    assert emp["id"] not in ids
    ids_all = [e["id"] for e in client.get("/api/employees?include_deleted=true", headers=headers).json()["items"]]
    assert emp["id"] in ids_all
    assert login(client, "xoa.mem", "Staff@123456").status_code == 403

    res = client.post(f"/api/employees/{emp['id']}/restore", headers=headers)
    assert res.status_code == 200
    assert res.json()["is_deleted"] is False
    assert login(client, "xoa.mem", "Staff@123456").status_code == 200


def test_search_and_filter(client):
    headers = admin_headers(client)
    create_employee(client, headers, ho_ten="Tìm Kiếm Độc Nhất", ma_vi_tri=1, trang_thai="nghi_phep")
    items = client.get("/api/employees?keyword=Độc Nhất", headers=headers).json()["items"]
    assert len(items) == 1
    items = client.get("/api/employees?trang_thai=nghi_phep&ma_vi_tri=1", headers=headers).json()["items"]
    assert all(e["trang_thai"] == "nghi_phep" and e["ma_vi_tri"] == 1 for e in items)


def test_upload_avatar(client, upload_dir):
    headers = admin_headers(client)
    emp = create_employee(client, headers, ho_ten="Có Ảnh")
    res = client.post(
        f"/api/employees/{emp['id']}/avatar", headers=headers,
        files={"file": ("avatar.png", io.BytesIO(b"\x89PNG fake"), "image/png")}
    )
    assert res.status_code == 200
    url = res.json()["anh_dai_dien"]
    assert url.startswith("/static/uploads/avatars/") and url.endswith(".png")
    assert (upload_dir / "avatars" / url.split("/")[-1]).exists()


def test_upload_rejects_bad_extension(client, upload_dir):
    headers = admin_headers(client)
    emp = create_employee(client, headers, ho_ten="Ảnh Sai")
    res = client.post(
        f"/api/employees/{emp['id']}/avatar", headers=headers,
        files={"file": ("virus.exe", io.BytesIO(b"MZ"), "application/octet-stream")}
    )
    assert res.status_code == 400


# ---------- FR-06: Trạng thái làm việc ----------

def test_resigned_employee_cannot_login_and_can_come_back(client):
    headers = admin_headers(client)
    emp = create_employee(
        client, headers, ho_ten="Nghỉ Rồi Quay Lại", tao_tai_khoan=True,
        ten_dang_nhap="quay.lai", mat_khau="Staff@123456"
    )
    res = client.patch(f"/api/employees/{emp['id']}/status", headers=headers, json={"trang_thai": "da_nghi"})
    assert res.status_code == 200
    assert login(client, "quay.lai", "Staff@123456").status_code == 403

    res = client.patch(f"/api/employees/{emp['id']}/status", headers=headers, json={"trang_thai": "dang_lam"})
    assert res.status_code == 200
    assert login(client, "quay.lai", "Staff@123456").status_code == 200


def test_schedulable_excludes_resigned_leave_and_deleted(client):
    headers = admin_headers(client)
    working = create_employee(client, headers, ho_ten="Xếp Ca Được")
    leave = create_employee(client, headers, ho_ten="Nghỉ Phép", trang_thai="nghi_phep")
    resigned = create_employee(client, headers, ho_ten="Đã Nghỉ", trang_thai="da_nghi")
    deleted = create_employee(client, headers, ho_ten="Đã Xóa")
    client.delete(f"/api/employees/{deleted['id']}", headers=headers)

    res = client.get("/api/employees/schedulable", headers=headers)
    assert res.status_code == 200
    ids = {e["id"] for e in res.json()}
    assert working["id"] in ids
    assert not ids & {leave["id"], resigned["id"], deleted["id"]}
    assert client.get("/api/employees/schedulable", headers=staff_headers(client)).status_code == 403


# ---------- FR-05: Hợp đồng ----------

def test_contract_rejects_start_after_end(client):
    headers = admin_headers(client)
    today = date.today()
    res = client.post("/api/contracts", headers=headers, json={
        "ma_nhan_vien": 1, "loai_hop_dong": "Thời vụ",
        "ngay_bat_dau": str(today), "ngay_ket_thuc": str(today - timedelta(days=1))
    })
    assert res.status_code == 400


def test_expiring_window_and_auto_expire(client):
    headers = admin_headers(client)
    emp = create_employee(client, headers, ho_ten="Hợp Đồng Test")
    today = date.today()

    def make(days_left):
        res = client.post("/api/contracts", headers=headers, json={
            "ma_nhan_vien": emp["id"], "loai_hop_dong": "Thời vụ",
            "ngay_bat_dau": str(today - timedelta(days=100)),
            "ngay_ket_thuc": str(today + timedelta(days=days_left))
        })
        assert res.status_code == 201
        return res.json()["id"]

    soon, later, past = make(10), make(60), make(-3)

    expiring_ids = {c["id"] for c in client.get("/api/contracts/expiring?days=30", headers=headers).json()}
    assert soon in expiring_ids
    assert later not in expiring_ids
    assert past not in expiring_ids

    contracts = {c["id"]: c for c in client.get(f"/api/contracts?ma_nhan_vien={emp['id']}", headers=headers).json()}
    assert contracts[past]["trang_thai"] == "het_han"
    assert contracts[soon]["trang_thai"] == "hieu_luc"
    assert contracts[soon]["canh_bao_het_han"] is True


def test_upload_contract_file(client, upload_dir):
    headers = admin_headers(client)
    res = client.post("/api/contracts", headers=headers, json={"ma_nhan_vien": 1, "loai_hop_dong": "Thử việc"})
    contract_id = res.json()["id"]
    res = client.post(
        f"/api/contracts/{contract_id}/file", headers=headers,
        files={"file": ("hop-dong.pdf", io.BytesIO(b"%PDF-1.4 fake"), "application/pdf")}
    )
    assert res.status_code == 200
    assert res.json()["file_dinh_kem"].startswith("/static/uploads/contracts/")
    # Staff không được upload
    res = client.post(
        f"/api/contracts/{contract_id}/file", headers=staff_headers(client),
        files={"file": ("hop-dong.pdf", io.BytesIO(b"%PDF"), "application/pdf")}
    )
    assert res.status_code == 403


# ---------- Giao diện ----------

@pytest.mark.parametrize("path", ["/dashboard", "/employees", "/contracts", "/profile"])
def test_pages_render(client, path):
    res = client.get(path)
    assert res.status_code == 200
    assert "QL Ca Làm" in res.text
