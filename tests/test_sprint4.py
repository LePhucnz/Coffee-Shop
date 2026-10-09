"""
Sprint 4: Đăng ký lịch rảnh và xếp ca làm việc (FR-07, FR-08, FR-09)
"""
from datetime import date, datetime, timedelta
import pytest
from sqlalchemy import create_engine, inspect, text

from app.services import shift_service as svc


def login(client, username, password):
    return client.post("/api/auth/login", json={"ten_dang_nhap": username, "mat_khau": password})


def headers_for(client, username, password):
    res = login(client, username, password)
    assert res.status_code == 200, res.text
    return {"Authorization": f"Bearer {res.json()['access_token']}"}


def admin_headers(client):
    return headers_for(client, "nguyen.a", "Admin@123456")


def staff_c(client):
    return headers_for(client, "le.c", "Staff@123456")


def future_week(offset):
    """Mỗi test dùng một tuần riêng ở tương lai để không ảnh hưởng nhau"""
    return svc.week_start(date.today()) + timedelta(weeks=offset)


def day(week, i):
    return (week + timedelta(days=i)).isoformat()


def shift_ids(client, headers):
    types = client.get("/api/shifts/types", headers=headers).json()
    return {t["ma_loai_ca"]: t["id"] for t in types}


def add(client, headers, ma_nv, ma_ca, ngay):
    return client.post("/api/shifts/assignments", headers=headers, json={"ma_nv": ma_nv, "ma_ca": ma_ca, "ngay_lam": ngay})


def create_employee(client, headers, **extra):
    payload = {"ho_ten": "Nhân Viên Ca", "trang_thai": "dang_lam"}
    payload.update(extra)
    res = client.post("/api/employees", headers=headers, json=payload)
    assert res.status_code == 201, res.text
    return res.json()


# ---------- Loại ca ----------

def test_shift_types_have_time_and_staffing(client):
    types = client.get("/api/shifts/types", headers=staff_c(client)).json()
    sang = next(t for t in types if t["ma_loai_ca"] == "CA_SANG")
    assert sang["gio_bat_dau"] == "06:00:00" and sang["gio_ket_thuc"] == "14:00:00"
    assert sang["so_gio"] == 8
    assert all(t["so_nv_toi_da"] >= t["so_nv_toi_thieu"] for t in types)


def test_only_admin_can_configure_shift_type(client):
    admin = admin_headers(client)
    ids = shift_ids(client, admin)
    payload = {"ten_ca": "Part-time tối", "gio_bat_dau": "18:00", "gio_ket_thuc": "22:00",
               "so_nv_toi_thieu": 1, "so_nv_toi_da": 3}
    assert client.put(f"/api/shifts/types/{ids['CA_PARTTIME_2']}", headers=staff_c(client), json=payload).status_code == 403

    res = client.put(f"/api/shifts/types/{ids['CA_PARTTIME_2']}", headers=admin, json=payload)
    assert res.status_code == 200
    assert res.json()["so_nv_toi_da"] == 3

    bad = dict(payload, so_nv_toi_thieu=4, so_nv_toi_da=2)
    assert client.put(f"/api/shifts/types/{ids['CA_PARTTIME_2']}", headers=admin, json=bad).status_code == 422

    payload["so_nv_toi_da"] = 2
    client.put(f"/api/shifts/types/{ids['CA_PARTTIME_2']}", headers=admin, json=payload)


def test_create_overnight_shift_type(client):
    admin = admin_headers(client)
    res = client.post("/api/shifts/types", headers=admin, json={
        "ma_loai_ca": "ca_dem_test", "ten_ca": "Ca đêm test", "gio_bat_dau": "22:00",
        "gio_ket_thuc": "02:00", "so_nv_toi_thieu": 0, "so_nv_toi_da": 1, "trang_thai": False
    })
    assert res.status_code == 201, res.text
    assert res.json()["ma_loai_ca"] == "CA_DEM_TEST"
    assert res.json()["so_gio"] == 4


# ---------- FR-07: Đăng ký nguyện vọng ----------

def test_deadline_is_thursday_before_week():
    monday = date(2026, 10, 12)
    assert svc.registration_deadline(monday) == datetime(2026, 10, 8, 23, 59, 59)
    assert svc.is_registration_open(monday, now=datetime(2026, 10, 8, 23, 0))
    assert not svc.is_registration_open(monday, now=datetime(2026, 10, 9, 0, 0))


def test_staff_register_and_edit_before_deadline(client):
    headers = staff_c(client)
    ids = shift_ids(client, headers)
    week = future_week(3)

    res = client.put("/api/shifts/registrations/me", headers=headers, json={
        "tuan_bat_dau": week.isoformat(),
        "dang_ky": [{"ngay": day(week, 0), "ma_ca": ids["CA_SANG"]}, {"ngay": day(week, 2), "ma_ca": ids["CA_CHIEU"]}]
    })
    assert res.status_code == 200, res.text
    assert res.json()["con_mo"] is True
    assert len(res.json()["dang_ky"]) == 2

    # Sửa lại trước hạn chót: danh sách mới thay hoàn toàn danh sách cũ
    res = client.put("/api/shifts/registrations/me", headers=headers, json={
        "tuan_bat_dau": day(week, 3),  # ngày bất kỳ trong tuần đều được đưa về Thứ Hai
        "dang_ky": [{"ngay": day(week, 4), "ma_ca": ids["CA_PARTTIME_2"]}]
    })
    assert res.status_code == 200
    got = client.get(f"/api/shifts/registrations/me?week={week}", headers=headers).json()
    assert got["dang_ky"] == [{"ngay": day(week, 4), "ma_ca": ids["CA_PARTTIME_2"]}]


def test_registration_locked_after_deadline(client):
    headers = staff_c(client)
    ids = shift_ids(client, headers)
    this_week = svc.week_start(date.today())  # hạn chót là Thứ Năm tuần trước nên đã khóa
    info = client.get(f"/api/shifts/registrations/me?week={this_week}", headers=headers).json()
    assert info["con_mo"] is False
    res = client.put("/api/shifts/registrations/me", headers=headers, json={
        "tuan_bat_dau": this_week.isoformat(),
        "dang_ky": [{"ngay": this_week.isoformat(), "ma_ca": ids["CA_SANG"]}]
    })
    assert res.status_code == 400
    assert "hạn chót" in res.json()["detail"]


def test_default_registration_week_is_still_open(client):
    data = client.get("/api/shifts/registrations/me", headers=staff_c(client)).json()
    assert data["con_mo"] is True
    assert date.fromisoformat(data["tuan_bat_dau"]) > date.today()


def test_registration_rejects_day_outside_week(client):
    headers = staff_c(client)
    ids = shift_ids(client, headers)
    week = future_week(4)
    res = client.put("/api/shifts/registrations/me", headers=headers, json={
        "tuan_bat_dau": week.isoformat(),
        "dang_ky": [{"ngay": day(week, 7), "ma_ca": ids["CA_SANG"]}]
    })
    assert res.status_code == 400


def test_manager_does_not_register_preferences(client):
    # Ma trận phân quyền BRD: Admin/Manager không đăng ký lịch rảnh
    assert client.get("/api/shifts/registrations/me", headers=admin_headers(client)).status_code == 403


# ---------- FR-08: Xếp ca tự động / bán tự động ----------

def test_auto_schedule_follows_preferences_without_conflicts(client):
    admin = admin_headers(client)
    emp_b = create_employee(client, admin, ho_ten="Nhân Viên Xếp Ca", tao_tai_khoan=True,
                            ten_dang_nhap="xepca.b", mat_khau="Staff@123456", ma_vai_tro=3)
    b, c = headers_for(client, "xepca.b", "Staff@123456"), staff_c(client)
    ids = shift_ids(client, admin)
    week = future_week(5)
    nv_b = emp_b["id"]
    nv_c = login(client, "le.c", "Staff@123456").json()["user"]["ma_nv"]

    client.put("/api/shifts/registrations/me", headers=b, json={"tuan_bat_dau": week.isoformat(), "dang_ky": [
        {"ngay": day(week, 0), "ma_ca": ids["CA_SANG"]},
        {"ngay": day(week, 1), "ma_ca": ids["CA_CHIEU"]},
    ]})
    client.put("/api/shifts/registrations/me", headers=c, json={"tuan_bat_dau": week.isoformat(), "dang_ky": [
        {"ngay": day(week, 0), "ma_ca": ids["CA_SANG"]},
        {"ngay": day(week, 0), "ma_ca": ids["CA_CHIEU"]},
        {"ngay": day(week, 0), "ma_ca": ids["CA_PARTTIME_2"]},  # chồng giờ với ca chiều
    ]})

    res = client.post("/api/shifts/schedule/auto", headers=admin, json={"tuan_bat_dau": week.isoformat()})
    assert res.status_code == 200, res.text
    data = res.json()
    assert data["trang_thai"] == "nhap"
    assert data["so_loi"] == 0

    wishes = {(nv_b, day(week, 0), ids["CA_SANG"]), (nv_b, day(week, 1), ids["CA_CHIEU"]),
              (nv_c, day(week, 0), ids["CA_SANG"]), (nv_c, day(week, 0), ids["CA_CHIEU"]),
              (nv_c, day(week, 0), ids["CA_PARTTIME_2"])}
    got = {(p["ma_nv"], p["ngay_lam"], p["ma_ca"]) for p in data["phan_cong"]}
    assert got and got <= wishes
    assert all(p["theo_nguyen_vong"] for p in data["phan_cong"])
    # Không ai làm quá 8 giờ trong một ngày
    for t in data["tong_gio"]:
        per_day = {}
        for p in data["phan_cong"]:
            if p["ma_nv"] == t["ma_nv"]:
                per_day[p["ngay_lam"]] = per_day.get(p["ngay_lam"], 0) + p["so_gio"]
        assert max(per_day.values()) <= 8

    # Ô ca chiều cao điểm cần tối thiểu 2 người nên báo thiếu ca
    slot = next(o for o in data["o_ca"] if o["ngay"] == day(week, 1) and o["ma_ca"] == ids["CA_CHIEU"])
    assert slot["so_nguoi"] == 1
    assert slot["canh_bao"][0]["loai"] == "thieu_nguoi"
    assert [n["ma_nv"] for n in slot["nguyen_vong"]] == [nv_b]


def test_staff_cannot_use_scheduling_tools(client):
    headers = staff_c(client)
    week = future_week(6).isoformat()
    assert client.get("/api/shifts/schedule", headers=headers).status_code == 403
    assert client.post("/api/shifts/schedule/auto", headers=headers, json={"tuan_bat_dau": week}).status_code == 403
    assert client.post("/api/shifts/schedule/publish", headers=headers, json={"tuan_bat_dau": week}).status_code == 403


# ---------- FR-09: Phát hiện xung đột ----------

def test_overlapping_shifts_block_publish(client):
    admin = admin_headers(client)
    ids = shift_ids(client, admin)
    week = future_week(7)
    emp = create_employee(client, admin, ho_ten="Trùng Ca")

    assert add(client, admin, emp["id"], ids["CA_SANG"], day(week, 0)).status_code == 201
    res = add(client, admin, emp["id"], ids["CA_PARTTIME_1"], day(week, 0))  # 08-12 nằm trong 06-14
    data = res.json()
    mine = [p for p in data["phan_cong"] if p["ma_nv"] == emp["id"]]
    assert all(any(c["loai"] == "trung_ca" and c["muc_do"] == "loi" for c in p["xung_dot"]) for p in mine)
    assert data["co_the_cong_bo"] is False

    res = client.post("/api/shifts/schedule/publish", headers=admin, json={"tuan_bat_dau": week.isoformat()})
    assert res.status_code == 400

    # Thêm trùng đúng ô ca bị chặn ngay
    assert add(client, admin, emp["id"], ids["CA_SANG"], day(week, 0)).status_code == 400

    # Gỡ một ca thì hết lỗi và công bố được
    client.delete(f"/api/shifts/assignments/{mine[1]['id']}", headers=admin)
    res = client.post("/api/shifts/schedule/publish", headers=admin, json={"tuan_bat_dau": week.isoformat()})
    assert res.status_code == 200, res.text
    assert res.json()["trang_thai"] == "da_cong_bo"


def test_hours_over_limit_are_warnings(client):
    admin = admin_headers(client)
    ids = shift_ids(client, admin)
    week = future_week(8)
    emp = create_employee(client, admin, ho_ten="Làm Nhiều Giờ")

    for i in range(7):
        add(client, admin, emp["id"], ids["CA_SANG"], day(week, i))  # 7 x 8 = 56 giờ
    data = add(client, admin, emp["id"], ids["CA_PARTTIME_2"], day(week, 2)).json()  # ngày thứ 3: 12 giờ

    kinds = {c["loai"] for p in data["phan_cong"] if p["ma_nv"] == emp["id"] for c in p["xung_dot"]}
    assert {"qua_gio_ngay", "qua_gio_tuan"} <= kinds
    assert data["so_loi"] == 0  # chỉ là cảnh báo, vẫn được công bố
    assert data["co_the_cong_bo"] is True


def test_leave_is_flagged_and_resigned_is_blocked(client):
    admin = admin_headers(client)
    ids = shift_ids(client, admin)
    week = future_week(9)
    working = create_employee(client, admin, ho_ten="Sắp Nghỉ Phép")
    resigned = create_employee(client, admin, ho_ten="Nghỉ Hẳn", trang_thai="da_nghi")

    # BR-05: người đã nghỉ việc không được xếp ca mới
    assert add(client, admin, resigned["id"], ids["CA_SANG"], day(week, 0)).status_code == 400

    # Xếp ca xong mới chuyển sang nghỉ phép: ô ca bị đánh dấu lỗi
    assert add(client, admin, working["id"], ids["CA_SANG"], day(week, 0)).status_code == 201
    client.patch(f"/api/employees/{working['id']}/status", headers=admin, json={"trang_thai": "nghi_phep"})
    data = client.get(f"/api/shifts/schedule?week={week}", headers=admin).json()
    p = next(p for p in data["phan_cong"] if p["ma_nv"] == working["id"])
    assert p["xung_dot"][0]["loai"] == "trang_thai"
    assert p["xung_dot"][0]["muc_do"] == "loi"


# ---------- Công bố, thông báo, lịch cá nhân ----------

def test_publish_notifies_staff_and_locks_week(client):
    admin = admin_headers(client)
    staff = staff_c(client)
    ids = shift_ids(client, admin)
    week = future_week(10)
    nv_c = login(client, "le.c", "Staff@123456").json()["user"]["ma_nv"]

    assert add(client, admin, nv_c, ids["CA_SANG"], day(week, 3)).status_code == 201

    # BR-02: lịch nháp nhân viên chưa thấy
    mine = client.get(f"/api/shifts/my-schedule?week={week}", headers=staff).json()
    assert mine["da_cong_bo"] is False and mine["ca"] == []

    before = client.get("/api/notifications/me", headers=staff).json()["so_chua_doc"]
    res = client.post("/api/shifts/schedule/publish", headers=admin, json={"tuan_bat_dau": week.isoformat()})
    assert res.status_code == 200, res.text

    mine = client.get(f"/api/shifts/my-schedule?week={week}", headers=staff).json()
    assert mine["da_cong_bo"] is True
    assert [c["ngay_lam"] for c in mine["ca"]] == [day(week, 3)]
    assert mine["tong_gio"] == 8

    notes = client.get("/api/notifications/me", headers=staff).json()
    assert notes["so_chua_doc"] == before + 1
    assert "đã được công bố" in notes["items"][0]["tieu_de"]
    assert client.post("/api/notifications/read-all", headers=staff).status_code == 200
    assert client.get("/api/notifications/me", headers=staff).json()["so_chua_doc"] == 0

    # Đã công bố thì phải chuyển về nháp mới sửa được
    assert add(client, admin, nv_c, ids["CA_CHIEU"], day(week, 4)).status_code == 400
    res = client.post("/api/shifts/schedule/unpublish", headers=admin, json={"tuan_bat_dau": week.isoformat()})
    assert res.json()["trang_thai"] == "nhap"
    assert add(client, admin, nv_c, ids["CA_CHIEU"], day(week, 4)).status_code == 201


def test_cannot_publish_empty_week(client):
    admin = admin_headers(client)
    res = client.post("/api/shifts/schedule/publish", headers=admin, json={"tuan_bat_dau": future_week(11).isoformat()})
    assert res.status_code == 400


def test_today_summary(client):
    res = client.get("/api/shifts/today", headers=admin_headers(client))
    assert res.status_code == 200
    assert "so_ca_hom_nay" in res.json()


# ---------- Hạ tầng ----------

def test_add_missing_columns_upgrades_old_database():
    from app.database import Base, add_missing_columns
    old = create_engine("sqlite:///:memory:")
    with old.begin() as conn:
        conn.execute(text("CREATE TABLE loai_ca (id INTEGER PRIMARY KEY, ma_loai_ca VARCHAR(50), mo_ta TEXT, trang_thai BOOLEAN)"))
    Base.metadata.create_all(bind=old)
    add_missing_columns(old)
    cols = {c["name"] for c in inspect(old).get_columns("loai_ca")}
    assert {"ten_ca", "gio_bat_dau", "gio_ket_thuc", "so_nv_toi_thieu", "so_nv_toi_da"} <= cols


@pytest.mark.parametrize("path", ["/shift-registration", "/schedule", "/my-schedule"])
def test_sprint4_pages_render(client, path):
    res = client.get(path)
    assert res.status_code == 200
    assert "<html" in res.text
