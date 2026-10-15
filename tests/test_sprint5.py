"""
Sprint 5: Chấm công trực tuyến (FR-10, FR-11, FR-11A, FR-11B, FR-11D)
Mỗi test dùng một tuần riêng ở tương lai và nhân viên riêng; giờ hiện tại được giả lập bằng fixture `clock`.
"""
import io
import itertools
import zipfile
from datetime import date, datetime, time, timedelta
import pytest

from app.config import settings
from app.services import attendance_service as att
from app.services import shift_service as shift_svc

STORE = (10.8505, 106.7719)       # Tọa độ quán Thủ Đức trong dữ liệu mẫu
FAR_AWAY = (10.7769, 106.7009)    # Cách quán khoảng 11 km (Quận 1)

_counter = itertools.count(1)


# ---------- Tiện ích ----------

def headers_for(client, username, password):
    res = client.post("/api/auth/login", json={"ten_dang_nhap": username, "mat_khau": password})
    assert res.status_code == 200, res.text
    return {"Authorization": f"Bearer {res.json()['access_token']}"}


def admin_headers(client):
    """nguyen.a: Quản lý cửa hàng (Manager)"""
    return headers_for(client, "nguyen.a", "Admin@123456")


def owner_headers(client):
    """chu.quan: Chủ quán (Admin) - thêm ở Sprint 5"""
    return headers_for(client, "chu.quan", "Admin@123456")


_week_counter = itertools.count(60)


def future_week(offset=None):
    """Mỗi lần gọi trả về một tuần mới chưa ai dùng (tuần đã công bố sẽ bị khóa chỉnh sửa)"""
    return shift_svc.week_start(date.today()) + timedelta(weeks=next(_week_counter))


def shift_ids(client, headers):
    types = client.get("/api/shifts/types", headers=headers).json()
    return {t["ma_loai_ca"]: t["id"] for t in types}


def new_staff(client, admin, role=3):
    """Tạo nhân viên + tài khoản riêng để không ảnh hưởng dữ liệu mẫu"""
    n = next(_counter)
    username = f"chamcong.{n}"
    res = client.post("/api/employees", headers=admin, json={
        "ho_ten": f"Nhân Viên Chấm Công {n}", "trang_thai": "dang_lam", "ma_cua_hang": 1, "ma_vi_tri": 2,
        "tao_tai_khoan": True, "ten_dang_nhap": username, "mat_khau": "Staff@123456", "ma_vai_tro": role
    })
    assert res.status_code == 201, res.text
    return res.json()["id"], headers_for(client, username, "Staff@123456")


def assign(client, admin, ma_nv, ma_ca, ngay, publish=True):
    """Xếp ca (và công bố tuần nếu publish=True), trả về id phân công"""
    res = client.post("/api/shifts/assignments", headers=admin,
                      json={"ma_nv": ma_nv, "ma_ca": ma_ca, "ngay_lam": ngay.isoformat()})
    assert res.status_code == 201, res.text
    if publish:
        res = client.post("/api/shifts/schedule/publish", headers=admin,
                          json={"tuan_bat_dau": shift_svc.week_start(ngay).isoformat()})
        assert res.status_code == 200, res.text
    return next(p["id"] for p in res.json()["phan_cong"]
                if p["ma_nv"] == ma_nv and p["ma_ca"] == ma_ca and p["ngay_lam"] == ngay.isoformat())


@pytest.fixture()
def clock(monkeypatch):
    """Giả lập giờ máy chủ"""
    state = {"now": datetime.now()}
    monkeypatch.setattr(att, "now", lambda: state["now"])

    def set_time(value):
        state["now"] = value
    return set_time


def at(d, hh, mm=0):
    return datetime.combine(d, time(hh, mm))


def check_in(client, headers, pc_id, pos=STORE, extra_headers=None):
    return client.post("/api/attendance/check-in", headers={**headers, **(extra_headers or {})},
                       json={"ma_phan_cong": pc_id, "vi_do": pos[0] if pos else None, "kinh_do": pos[1] if pos else None})


def check_out(client, headers, pc_id, pos=STORE, extra_headers=None):
    return client.post("/api/attendance/check-out", headers={**headers, **(extra_headers or {})},
                       json={"ma_phan_cong": pc_id, "vi_do": pos[0] if pos else None, "kinh_do": pos[1] if pos else None})


def codes(row):
    return {n["ma"] for n in row["nhan"]}


def history(client, headers, ngay):
    res = client.get(f"/api/attendance/me?tu_ngay={ngay}&den_ngay={ngay}", headers=headers)
    assert res.status_code == 200, res.text
    return res.json()


def row_of(client, headers, ngay, pc):
    return next(r for r in history(client, headers, ngay)["items"] if r["ma_phan_cong"] == pc)


def send_request(client, headers, pc, loai, vao=None, ra=None, ly_do="Tôi quên chấm công vì đông khách", **extra):
    payload = {"ma_phan_cong": pc, "loai": loai, "ly_do": ly_do,
               "gio_vao_de_xuat": vao.isoformat() if vao else None, "gio_ra_de_xuat": ra.isoformat() if ra else None}
    payload.update(extra)
    return client.post("/api/attendance/requests", headers=headers, json=payload)


# ---------- Hàm tính toán ----------

def test_distance_meters():
    assert att.distance_meters(*STORE, *STORE) == 0
    assert 9000 < att.distance_meters(*STORE, *FAR_AWAY) < 13000


def test_default_config_matches_brd(client, db_session):
    cfg = att.get_config(db_session)
    assert cfg["mo_truoc_phut"] == 15 and cfg["an_han_phut"] == 5 and cfg["ban_kinh_m"] == 200
    assert cfg["nguong_chua_checkout_phut"] == 120 and cfg["han_gui_yeu_cau_gio"] == 48
    assert cfg["han_muc_thang"] == 3 and cfg["so_tep_toi_da"] == 3 and cfg["dung_luong_tep_mb"] == 5


# ---------- FR-10: Check-in / Check-out ----------

def test_checkin_opens_15_minutes_before_shift(client, clock):
    admin = admin_headers(client)
    ids = shift_ids(client, admin)
    nv, staff = new_staff(client, admin)
    ngay = future_week(30)
    pc = assign(client, admin, nv, ids["CA_SANG"], ngay)  # 06:00 - 14:00

    # EX-03: chưa tới giờ mở chấm công
    clock(at(ngay, 5, 40))
    today = client.get("/api/attendance/today", headers=staff).json()
    ca = next(c for c in today["ca"] if c["ma_phan_cong"] == pc)
    assert ca["trang_thai"] == "chua_den_ca" and ca["co_the_check_in"] is False
    res = check_in(client, staff, pc)
    assert res.status_code == 400 and "05:45" in res.json()["detail"]

    clock(at(ngay, 5, 50))
    assert check_in(client, staff, pc).status_code == 200
    row = row_of(client, staff, ngay, pc)
    assert row["trang_thai"] == "dang_lam" and row["dung_gio"] is True and row["co_the_check_out"] is True
    assert row["vi_tri"] == "trong_pham_vi"
    # Nhân viên không thấy khoảng cách / IP (FR-11B mục 3)
    assert row["khoang_cach_vao"] is None and row["ip_vao"] is None

    clock(at(ngay, 14, 2))
    row = check_out(client, staff, pc).json()
    assert row["trang_thai"] == "hoan_thanh" and codes(row) == {"dung_gio"}
    assert row["so_gio_lam"] == 8


def test_double_click_within_60_seconds_is_ignored(client, clock):
    """EX-11"""
    admin = admin_headers(client)
    ids = shift_ids(client, admin)
    nv, staff = new_staff(client, admin)
    ngay = future_week(30) + timedelta(days=1)
    pc = assign(client, admin, nv, ids["CA_SANG"], ngay)
    clock(at(ngay, 6, 0))
    first = check_in(client, staff, pc).json()
    clock(at(ngay, 6, 0) + timedelta(seconds=30))
    again = check_in(client, staff, pc)
    assert again.status_code == 200 and again.json()["gio_vao"] == first["gio_vao"]
    clock(at(ngay, 6, 5))
    assert check_in(client, staff, pc).status_code == 400


def test_cannot_check_in_for_someone_else_or_unpublished_week(client, clock):
    admin = admin_headers(client)
    ids = shift_ids(client, admin)
    nv1, staff1 = new_staff(client, admin)
    nv2, staff2 = new_staff(client, admin)
    ngay = future_week(31)
    pc = assign(client, admin, nv1, ids["CA_CHIEU"], ngay, publish=False)
    clock(at(ngay, 14, 0))
    assert check_in(client, staff1, pc).status_code == 400   # lịch còn nháp
    client.post("/api/shifts/schedule/publish", headers=admin, json={"tuan_bat_dau": ngay.isoformat()})
    assert check_in(client, staff2, pc).status_code == 403   # BR-03
    assert check_in(client, staff1, pc).status_code == 200


def test_no_shift_today_message(client, clock):
    """EX-12"""
    admin = admin_headers(client)
    _, staff = new_staff(client, admin)
    clock(at(future_week(31) + timedelta(days=5), 9, 0))
    today = client.get("/api/attendance/today", headers=staff).json()
    assert today["ca"] == [] and "không có ca làm hiện tại" in today["thong_bao"]


def test_check_in_after_shift_ended_is_rejected(client, clock):
    """EX-04"""
    admin = admin_headers(client)
    ids = shift_ids(client, admin)
    nv, staff = new_staff(client, admin)
    ngay = future_week(32)
    pc = assign(client, admin, nv, ids["CA_PARTTIME_1"], ngay)  # 08:00 - 12:00
    clock(at(ngay, 12, 1))
    res = check_in(client, staff, pc)
    assert res.status_code == 400 and "bù công" in res.json()["detail"]


def test_employee_on_leave_cannot_check_in(client, clock):
    """EX-16"""
    admin = admin_headers(client)
    ids = shift_ids(client, admin)
    nv, staff = new_staff(client, admin)
    ngay = future_week(32) + timedelta(days=1)
    pc = assign(client, admin, nv, ids["CA_PARTTIME_1"], ngay)
    client.patch(f"/api/employees/{nv}/status", headers=admin, json={"trang_thai": "nghi_phep"})
    clock(at(ngay, 8, 0))
    res = check_in(client, staff, pc)
    assert res.status_code == 400 and "nghỉ phép" in res.json()["detail"]


def test_outside_location_is_flagged_not_blocked(client, clock):
    """EX-07"""
    admin = admin_headers(client)
    ids = shift_ids(client, admin)
    nv, staff = new_staff(client, admin)
    ngay = future_week(33)
    pc = assign(client, admin, nv, ids["CA_PARTTIME_1"], ngay)
    clock(at(ngay, 8, 0))
    row = check_in(client, staff, pc, pos=FAR_AWAY).json()
    assert row["vi_tri"] == "ngoai_pham_vi" and "ngoai_vi_tri" in codes(row)
    mgr = client.get(f"/api/attendance?ngay={ngay}&ma_nv={nv}", headers=admin).json()["items"][0]
    assert mgr["khoang_cach_vao"] > 200


def test_no_gps_is_flagged_unless_store_wifi(client, clock, monkeypatch):
    """EX-08: không có GPS thì dùng IP làm căn cứ phụ"""
    admin = admin_headers(client)
    ids = shift_ids(client, admin)
    nv, staff = new_staff(client, admin)
    ngay = future_week(34)
    pc1 = assign(client, admin, nv, ids["CA_PARTTIME_1"], ngay, publish=False)
    pc2 = assign(client, admin, nv, ids["CA_PARTTIME_1"], ngay + timedelta(days=1))

    clock(at(ngay, 8, 0))
    row = check_in(client, staff, pc1, pos=None).json()
    assert row["vi_tri"] == "khong_dinh_vi" and "khong_dinh_vi" in codes(row)

    monkeypatch.setitem(settings.ATTENDANCE_DEFAULTS, "dai_ip_quan", "10.0.0.")
    clock(at(ngay + timedelta(days=1), 8, 0))
    row = check_in(client, staff, pc2, pos=None, extra_headers={"X-Forwarded-For": "10.0.0.25"}).json()
    assert row["vi_tri"] == "trong_pham_vi" and not ({"khong_dinh_vi", "ngoai_vi_tri"} & codes(row))


def test_same_device_for_two_accounts_is_flagged(client, clock):
    """EX-17"""
    admin = admin_headers(client)
    ids = shift_ids(client, admin)
    nv1, staff1 = new_staff(client, admin)
    nv2, staff2 = new_staff(client, admin)
    ngay = future_week(34) + timedelta(days=3)
    pc1 = assign(client, admin, nv1, ids["CA_SANG"], ngay, publish=False)
    pc2 = assign(client, admin, nv2, ids["CA_SANG"], ngay)
    device = {"X-Device-Id": "may-quay-1"}
    clock(at(ngay, 6, 0))
    check_in(client, staff1, pc1, extra_headers=device)
    clock(at(ngay, 6, 3))
    row = check_in(client, staff2, pc2, extra_headers=device).json()
    assert "thiet_bi_trung" in codes(row)
    assert "thiet_bi_trung" in codes(row_of(client, staff1, ngay, pc1))


# ---------- FR-11: Đúng giờ / Đi trễ / Về sớm / Vắng / Chưa check-out / Vượt ca ----------

def test_late_and_early_are_labelled_with_minutes(client, clock):
    admin = admin_headers(client)
    ids = shift_ids(client, admin)
    nv, staff = new_staff(client, admin)
    ngay = future_week(35)
    pc = assign(client, admin, nv, ids["CA_CHIEU"], ngay)  # 14:00 - 22:00
    clock(at(ngay, 14, 17))
    assert check_in(client, staff, pc).json()["phut_di_tre"] == 17
    clock(at(ngay, 21, 30))
    row = check_out(client, staff, pc).json()
    assert row["phut_ve_som"] == 30 and codes(row) == {"di_tre", "ve_som"}
    names = [n["ten"] for n in row["nhan"]]
    assert "Đi trễ 17 phút" in names and "Về sớm 30 phút" in names
    assert row["so_gio_lam"] == round(7 + 13 / 60, 2)


def test_within_grace_is_on_time(client, clock):
    admin = admin_headers(client)
    ids = shift_ids(client, admin)
    nv, staff = new_staff(client, admin)
    ngay = future_week(36)
    pc = assign(client, admin, nv, ids["CA_PARTTIME_2"], ngay)  # 18:00 - 22:00
    clock(at(ngay, 18, 5))
    assert check_in(client, staff, pc).json()["dung_gio"] is True


def test_absent_and_missing_checkout(client, clock):
    """EX-01, EX-02: quá 2 giờ sau giờ kết thúc ca thì "Chưa check-out", không tự suy đoán giờ ra"""
    admin = admin_headers(client)
    ids = shift_ids(client, admin)
    nv, staff = new_staff(client, admin)
    ngay = future_week(37)
    vang = assign(client, admin, nv, ids["CA_PARTTIME_1"], ngay, publish=False)  # 08:00 - 12:00
    quen = assign(client, admin, nv, ids["CA_PARTTIME_2"], ngay)                 # 18:00 - 22:00
    clock(at(ngay, 18, 0))
    check_in(client, staff, quen)

    clock(at(ngay, 23, 30))
    rows = {r["ma_phan_cong"]: r for r in history(client, staff, ngay)["items"]}
    assert rows[vang]["trang_thai"] == "vang_mat" and rows[quen]["trang_thai"] == "dang_lam"

    clock(at(ngay + timedelta(days=1), 0, 30))
    assert check_out(client, staff, quen).status_code == 400
    data = history(client, staff, ngay)
    rows = {r["ma_phan_cong"]: r for r in data["items"]}
    assert rows[quen]["trang_thai"] == "chua_check_out" and rows[quen]["so_gio_lam"] == 0
    assert data["thong_ke"]["vang_mat"] == 1 and data["thong_ke"]["chua_check_out"] == 1


def test_overtime_counts_only_after_approval(client, clock):
    """EX-06, BR-09"""
    admin = admin_headers(client)
    ids = shift_ids(client, admin)
    nv, staff = new_staff(client, admin)
    ngay = future_week(37) + timedelta(days=2)
    pc = assign(client, admin, nv, ids["CA_PARTTIME_1"], ngay)
    clock(at(ngay, 8, 0))
    check_in(client, staff, pc)
    clock(at(ngay, 12, 40))
    row = check_out(client, staff, pc).json()
    assert row["phut_vuot_ca"] == 40 and row["so_gio_lam"] == 4 and "vuot_ca" in codes(row)

    assert client.post(f"/api/attendance/assignments/{pc}/overtime", headers=admin,
                       json={"so_phut": 50, "ly_do": "Bàn giao ca"}).status_code == 400
    row = client.post(f"/api/attendance/assignments/{pc}/overtime", headers=admin,
                      json={"so_phut": 30, "ly_do": "Bàn giao và vệ sinh quầy"}).json()
    assert row["phut_vuot_ca_duyet"] == 30 and row["so_gio_lam"] == 4.5


def test_overnight_shift_belongs_to_start_day(client, clock):
    """EX-14, BR-11"""
    admin = admin_headers(client)
    res = client.post("/api/shifts/types", headers=admin, json={
        "ma_loai_ca": "CA_DEM_CC", "ten_ca": "Ca đêm chấm công", "gio_bat_dau": "22:00:00", "gio_ket_thuc": "06:00:00",
        "so_nv_toi_thieu": 0, "so_nv_toi_da": 2
    })
    assert res.status_code == 201, res.text
    ca_dem = res.json()["id"]
    nv, staff = new_staff(client, admin)
    ngay = future_week(38)
    pc = assign(client, admin, nv, ca_dem, ngay)
    clock(at(ngay, 22, 0))
    assert check_in(client, staff, pc).status_code == 200
    clock(at(ngay + timedelta(days=1), 6, 0))
    assert pc in [c["ma_phan_cong"] for c in client.get("/api/attendance/today", headers=staff).json()["ca"]]
    row = check_out(client, staff, pc).json()
    assert row["trang_thai"] == "hoan_thanh" and row["so_gio_lam"] == 8 and row["ngay_lam"] == ngay.isoformat()
    client.put(f"/api/shifts/types/{ca_dem}", headers=admin, json={
        "ten_ca": "Ca đêm chấm công", "gio_bat_dau": "22:00:00", "gio_ket_thuc": "06:00:00",
        "so_nv_toi_thieu": 0, "so_nv_toi_da": 2, "trang_thai": False
    })


def test_record_keeps_original_times_and_saves_payroll_data(client, clock, db_session):
    from app.models.shift import ChamCong
    admin = admin_headers(client)
    ids = shift_ids(client, admin)
    nv, staff = new_staff(client, admin)
    ngay = future_week(39)
    pc = assign(client, admin, nv, ids["CA_PARTTIME_1"], ngay)
    clock(at(ngay, 8, 10))
    check_in(client, staff, pc)
    clock(at(ngay, 12, 0))
    check_out(client, staff, pc)
    db_session.expire_all()
    cc = db_session.query(ChamCong).filter(ChamCong.ma_phan_cong == pc).one()
    assert cc.phut_di_tre == 10 and cc.phut_ve_som == 0 and cc.trang_thai == "hoan_thanh"
    assert float(cc.tong_gio_lam) == round(3 + 50 / 60, 2) and cc.thang == ngay.strftime("%Y-%m")
    assert cc.gio_vao_goc == at(ngay, 8, 10)


# ---------- FR-11B: lịch sử và màn Quản lý ----------

def test_manager_daily_view_highlights_and_filters(client, clock):
    admin = admin_headers(client)
    ids = shift_ids(client, admin)
    nv1, staff1 = new_staff(client, admin)
    nv2, staff2 = new_staff(client, admin)
    ngay = future_week(40)
    on_time = assign(client, admin, nv1, ids["CA_PARTTIME_1"], ngay, publish=False)
    late = assign(client, admin, nv2, ids["CA_PARTTIME_1"], ngay)
    clock(at(ngay, 8, 0))
    check_in(client, staff1, on_time)
    clock(at(ngay, 8, 20))
    check_in(client, staff2, late)

    assert client.get("/api/attendance", headers=staff1).status_code == 403
    data = client.get(f"/api/attendance?ngay={ngay}", headers=admin).json()
    order = [r["ma_phan_cong"] for r in data["items"] if r["ma_phan_cong"] in (on_time, late)]
    assert order == [late, on_time]  # dòng bất thường lên đầu
    assert data["thong_ke"]["di_tre"] >= 1

    only_late = client.get(f"/api/attendance?ngay={ngay}&nhan=di_tre", headers=admin).json()
    assert late in [r["ma_phan_cong"] for r in only_late["items"]]
    assert on_time not in [r["ma_phan_cong"] for r in only_late["items"]]
    by_name = client.get(f"/api/attendance?ngay={ngay}&tu_khoa={data['items'][0]['ho_ten']}", headers=admin).json()
    assert by_name["tong_so"] == 1
    paged = client.get(f"/api/attendance?ngay={ngay}&so_dong=1&trang=2", headers=admin).json()
    assert paged["trang"] == 2 and len(paged["items"]) == 1 and paged["so_trang"] >= 2


def test_staff_history_only_own_and_detail_is_forbidden_for_others(client, clock):
    admin = admin_headers(client)
    ids = shift_ids(client, admin)
    nv1, staff1 = new_staff(client, admin)
    nv2, _ = new_staff(client, admin)
    ngay = future_week(41)
    own = assign(client, admin, nv1, ids["CA_SANG"], ngay, publish=False)
    other = assign(client, admin, nv2, ids["CA_CHIEU"], ngay)
    clock(at(ngay, 23, 0))
    assert {r["ma_nv"] for r in history(client, staff1, ngay)["items"]} == {nv1}
    assert client.get(f"/api/attendance/assignments/{own}", headers=staff1).status_code == 200
    assert client.get(f"/api/attendance/assignments/{other}", headers=staff1).status_code == 403
    # Nhân viên chỉ xem 12 tháng gần nhất
    old = (ngay - timedelta(days=500)).isoformat()
    assert client.get(f"/api/attendance/me?tu_ngay={old}&den_ngay={ngay}", headers=staff1).status_code == 400


def test_period_grid_and_excel_export(client, clock):
    admin = admin_headers(client)
    ids = shift_ids(client, admin)
    nv, staff = new_staff(client, admin)
    ngay = future_week(42)
    d1 = assign(client, admin, nv, ids["CA_PARTTIME_1"], ngay, publish=False)
    d2 = assign(client, admin, nv, ids["CA_PARTTIME_1"], ngay + timedelta(days=1), publish=False)
    assign(client, admin, nv, ids["CA_PARTTIME_1"], ngay + timedelta(days=2))
    clock(at(ngay, 8, 0))
    check_in(client, staff, d1)
    clock(at(ngay, 12, 0))
    check_out(client, staff, d1)
    clock(at(ngay + timedelta(days=1), 8, 30))
    check_in(client, staff, d2)
    clock(at(ngay + timedelta(days=1), 12, 0))
    check_out(client, staff, d2)
    clock(at(ngay + timedelta(days=3), 9, 0))

    end = ngay + timedelta(days=6)
    grid = client.get(f"/api/attendance/period?tu_ngay={ngay}&den_ngay={end}&ma_nv={nv}", headers=admin).json()
    line = grid["nhan_vien"][0]
    assert line["o"][ngay.isoformat()][0]["ma"] == "D"
    assert line["o"][(ngay + timedelta(days=1)).isoformat()][0]["ma"] == "T"
    assert line["o"][(ngay + timedelta(days=2)).isoformat()][0]["ma"] == "V"
    assert line["tong_gio"] == 7.5 and line["phut_tre"] == 30 and line["so_vang"] == 1
    assert len(grid["ngay"]) == 7

    for mode in ("ky", "ngay"):
        res = client.get(f"/api/attendance/export?che_do={mode}&tu_ngay={ngay}&den_ngay={end}&ma_nv={nv}", headers=admin)
        assert res.status_code == 200
        assert res.headers["content-type"].startswith("application/vnd.openxmlformats")
        sheet = zipfile.ZipFile(io.BytesIO(res.content)).read("xl/worksheets/sheet1.xml").decode()
        assert "Nhân Viên Chấm Công" in sheet
    assert client.get("/api/attendance/export", headers=staff).status_code == 403


# ---------- FR-11A: Quản lý điều chỉnh trực tiếp ----------

def test_manager_direct_adjustment_keeps_original_and_logs(client, clock):
    admin = admin_headers(client)
    ids = shift_ids(client, admin)
    nv, staff = new_staff(client, admin)
    ngay = future_week(43)
    pc = assign(client, admin, nv, ids["CA_PARTTIME_1"], ngay)
    clock(at(ngay, 8, 0))
    check_in(client, staff, pc)
    clock(at(ngay + timedelta(days=1), 9, 0))

    # Lý do bắt buộc
    assert client.put(f"/api/attendance/assignments/{pc}", headers=admin,
                      json={"gio_ra": at(ngay, 12, 0).isoformat()}).status_code == 422
    assert client.put(f"/api/attendance/assignments/{pc}", headers=admin,
                      json={"gio_ra": at(ngay, 7, 0).isoformat(), "ly_do": "Quên check-out sau ca"}).status_code == 400
    res = client.put(f"/api/attendance/assignments/{pc}", headers=admin,
                     json={"gio_ra": at(ngay, 12, 0).isoformat(), "ly_do": "Quên check-out, đã xác nhận camera"})
    assert res.status_code == 200, res.text
    row = res.json()
    assert row["trang_thai"] == "hoan_thanh" and row["so_gio_lam"] == 4 and "da_dieu_chinh" in codes(row)
    assert row["gio_ra_goc"] is None  # giờ gốc không bị ghi đè

    detail = client.get(f"/api/attendance/assignments/{pc}", headers=staff).json()
    assert [l["hanh_dong"] for l in detail["nhat_ky"]] == ["check_in", "dieu_chinh_truc_tiep"]
    assert detail["nhat_ky"][1]["truoc"]["ra"] is None and detail["nhat_ky"][1]["sau"]["ra"].endswith("12:00")
    notes = client.get("/api/notifications/me", headers=staff).json()
    assert "điều chỉnh công" in notes["items"][0]["tieu_de"]
    assert client.put(f"/api/attendance/assignments/{pc}", headers=staff,
                      json={"gio_ra": at(ngay, 12, 0).isoformat(), "ly_do": "Tự sửa giờ của mình"}).status_code == 403


def test_manager_cannot_adjust_own_record(client, clock):
    """BR-08: Quản lý không tự sửa công của mình khi còn người quản trị khác"""
    admin = admin_headers(client)
    ids = shift_ids(client, admin)
    me = client.get("/api/auth/me", headers=admin).json()["ma_nv"]
    ngay = future_week(44)
    pc = assign(client, admin, me, ids["CA_PARTTIME_1"], ngay)
    clock(at(ngay, 13, 0))
    res = client.put(f"/api/attendance/assignments/{pc}", headers=admin,
                     json={"gio_vao": at(ngay, 8, 0).isoformat(), "gio_ra": at(ngay, 12, 0).isoformat(),
                           "ly_do": "Tự điều chỉnh công của mình"})
    assert res.status_code == 403


def test_waive_verify_flags_and_cancel_shift(client, clock):
    admin = admin_headers(client)
    ids = shift_ids(client, admin)
    nv, staff = new_staff(client, admin)
    ngay = future_week(44) + timedelta(days=1)
    pc = assign(client, admin, nv, ids["CA_PARTTIME_1"], ngay, publish=False)
    huy = assign(client, admin, nv, ids["CA_PARTTIME_2"], ngay)
    clock(at(ngay, 8, 25))
    check_in(client, staff, pc, pos=FAR_AWAY)

    row = client.post(f"/api/attendance/assignments/{pc}/waive", headers=admin,
                      json={"ly_do": "Lỗi hệ thống buổi sáng"}).json()
    assert row["mien_phat"] is True and "mien_phat" in codes(row) and row["phut_di_tre"] == 25

    row = client.post(f"/api/attendance/assignments/{pc}/verify-flags", headers=admin,
                      json={"xac_nhan": True, "ghi_chu": "Đi mua nguyên liệu theo chỉ đạo"}).json()
    assert "ngoai_vi_tri" not in codes(row) and row["da_xac_minh_co"] is True

    row = client.post(f"/api/attendance/assignments/{huy}/cancel", headers=admin,
                      json={"ly_do": "Mất điện cả khu", "tinh_cong": False}).json()
    assert row["trang_thai"] == "da_huy"
    clock(at(ngay, 23, 0))
    assert check_in(client, staff, huy).status_code == 400
    stats = history(client, staff, ngay)["thong_ke"]
    assert stats["vang_mat"] == 0  # EX-18: ca hủy không bị tính vắng


def test_bulk_adjust_preview_then_apply(client, clock):
    """EX-09: sự cố hệ thống, Quản lý nhập giờ thực tế cho nhiều ca"""
    admin = admin_headers(client)
    ids = shift_ids(client, admin)
    nv1, staff1 = new_staff(client, admin)
    nv2, _ = new_staff(client, admin)
    ngay = future_week(45)
    pc1 = assign(client, admin, nv1, ids["CA_SANG"], ngay, publish=False)
    pc2 = assign(client, admin, nv2, ids["CA_SANG"], ngay)
    clock(at(ngay, 15, 0))
    payload = {"items": [{"ma_phan_cong": pc1, "gio_vao": at(ngay, 6, 0).isoformat(), "gio_ra": at(ngay, 14, 0).isoformat()},
                         {"ma_phan_cong": pc2, "gio_vao": at(ngay, 6, 10).isoformat(), "gio_ra": at(ngay, 14, 0).isoformat()}],
               "ly_do": "Sự cố mạng cửa hàng, xác nhận bằng bảng giao ca", "mien_phat": True, "xem_truoc": True}
    preview = client.post("/api/attendance/bulk-adjust", headers=admin, json=payload).json()
    assert preview["xem_truoc"] is True and len(preview["items"]) == 2 and preview["da_ap_dung"] == 0
    assert history(client, staff1, ngay)["items"][0]["trang_thai"] == "vang_mat"

    payload["xem_truoc"] = False
    done = client.post("/api/attendance/bulk-adjust", headers=admin, json=payload).json()
    assert done["da_ap_dung"] == 2
    row = history(client, staff1, ngay)["items"][0]
    assert row["trang_thai"] == "hoan_thanh" and {"da_dieu_chinh", "mien_phat"} <= codes(row)


def test_locked_period_creates_next_period_adjustment(client, clock, db_session):
    """BR-04, EX-19"""
    from app.models.attendance import BanGhiDieuChinh
    admin = admin_headers(client)
    ids = shift_ids(client, admin)
    nv, staff = new_staff(client, admin)
    ngay = future_week(46)
    pc = assign(client, admin, nv, ids["CA_PARTTIME_1"], ngay)
    clock(at(ngay + timedelta(days=8), 9, 0))
    res = client.post("/api/attendance/periods/lock", headers=admin,
                      json={"tu_ngay": ngay.isoformat(), "den_ngay": (ngay + timedelta(days=6)).isoformat()})
    assert res.status_code == 201, res.text
    ky_id = res.json()["id"]
    row = client.put(f"/api/attendance/assignments/{pc}", headers=admin, json={
        "gio_vao": at(ngay, 8, 0).isoformat(), "gio_ra": at(ngay, 12, 0).isoformat(),
        "ly_do": "Phát hiện sai sót sau khi chốt kỳ"}).json()
    assert row["trang_thai"] == "vang_mat" and row["ky_da_chot"] is True  # bản ghi gốc không đổi
    adj = db_session.query(BanGhiDieuChinh).filter(BanGhiDieuChinh.ma_phan_cong == pc).one()
    assert float(adj.so_gio_chenh) == 4 and adj.ap_dung_tu_ngay == ngay + timedelta(days=7)
    # Chỉ Admin mới mở khóa được kỳ
    assert client.delete(f"/api/attendance/periods/{ky_id}", headers=admin).status_code == 403
    assert client.delete(f"/api/attendance/periods/{ky_id}", headers=owner_headers(client)).status_code == 200


# ---------- FR-11A: Yêu cầu bù/sửa công ----------

def test_request_flow_ask_update_approve(client, clock):
    admin = admin_headers(client)
    ids = shift_ids(client, admin)
    nv, staff = new_staff(client, admin)
    ngay = future_week(47)
    pc = assign(client, admin, nv, ids["CA_PARTTIME_1"], ngay)  # 08:00 - 12:00
    clock(at(ngay, 8, 0))
    check_in(client, staff, pc)
    clock(at(ngay, 15, 0))

    # Quy tắc 4: lý do tối thiểu 10 ký tự
    assert send_request(client, staff, pc, "bu_check_out", ra=at(ngay, 12, 0), ly_do="quên").status_code == 422
    # Loại yêu cầu không khớp trạng thái bản ghi
    assert send_request(client, staff, pc, "bu_check_in", vao=at(ngay, 8, 0)).status_code == 400
    res = send_request(client, staff, pc, "bu_check_out", ra=at(ngay, 12, 0))
    assert res.status_code == 201, res.text
    yc = res.json()
    assert yc["trang_thai"] == "cho_duyet" and yc["ten_loai"] == "Bù check-out"
    # Quy tắc 5: một yêu cầu đang xử lý cho mỗi ca
    assert send_request(client, staff, pc, "bu_check_out", ra=at(ngay, 12, 0)).status_code == 400
    assert "cho_duyet" in codes(row_of(client, staff, ngay, pc))

    queue = client.get("/api/attendance/requests", headers=admin).json()
    assert yc["id"] in [q["id"] for q in queue]
    assert client.get("/api/attendance/requests/pending-count", headers=admin).json()["so_cho_duyet"] >= 1

    # Yêu cầu bổ sung -> nhân viên cập nhật -> duyệt
    asked = client.post(f"/api/attendance/requests/{yc['id']}/ask", headers=admin,
                        json={"cau_hoi": "Bạn có bảng bàn giao ca không?"}).json()
    assert asked["trang_thai"] == "can_bo_sung"
    updated = client.put(f"/api/attendance/requests/{yc['id']}", headers=staff, json={
        "gio_ra_de_xuat": at(ngay, 12, 0).isoformat(), "ly_do": "Có bảng bàn giao ca ký lúc 12:00, đã đính kèm"}).json()
    assert updated["trang_thai"] == "cho_duyet"

    approved = client.post(f"/api/attendance/requests/{yc['id']}/approve", headers=admin, json={"ghi_chu": "Đã kiểm tra"})
    assert approved.status_code == 200, approved.text
    assert approved.json()["trang_thai"] == "da_duyet" and approved.json()["nguoi_xu_ly"]
    row = row_of(client, staff, ngay, pc)
    assert row["trang_thai"] == "hoan_thanh" and "da_dieu_chinh" in codes(row) and row["so_gio_lam"] == 4
    detail = client.get(f"/api/attendance/assignments/{pc}", headers=admin).json()
    log = detail["nhat_ky"][-1]
    assert log["hanh_dong"] == "duyet_yeu_cau" and log["nguoi_yeu_cau"] and log["nguoi_thuc_hien"]
    assert "đã được duyệt" in client.get("/api/notifications/me", headers=staff).json()["items"][0]["tieu_de"]
    # Đã duyệt là trạng thái cuối
    assert client.post(f"/api/attendance/requests/{yc['id']}/reject", headers=admin,
                       json={"ly_do": "Đổi ý"}).status_code == 400


def test_request_deadline_48_hours(client, clock):
    """BR-07"""
    admin = admin_headers(client)
    ids = shift_ids(client, admin)
    nv, staff = new_staff(client, admin)
    ngay = future_week(48)
    pc = assign(client, admin, nv, ids["CA_PARTTIME_1"], ngay)
    clock(at(ngay, 12, 0) + timedelta(hours=48, minutes=1))
    res = send_request(client, staff, pc, "bu_ca_hai", vao=at(ngay, 8, 0), ra=at(ngay, 12, 0))
    assert res.status_code == 400 and "48 giờ" in res.json()["detail"]
    clock(at(ngay, 12, 0) + timedelta(hours=47))
    assert send_request(client, staff, pc, "bu_ca_hai", vao=at(ngay, 8, 0), ra=at(ngay, 12, 0)).status_code == 201


def test_request_validations_and_flags(client, clock):
    """Quy tắc 1, 3, 6"""
    admin = admin_headers(client)
    ids = shift_ids(client, admin)
    nv, staff = new_staff(client, admin)
    nv_other, staff_other = new_staff(client, admin)
    ngay = future_week()
    while (ngay + timedelta(days=3)).month != ngay.month:   # 4 ca phải cùng tháng để kiểm tra hạn mức
        ngay = future_week()
    days = [assign(client, admin, nv, ids["CA_PARTTIME_1"], ngay + timedelta(days=i), publish=False) for i in range(4)]
    evening = assign(client, admin, nv, ids["CA_PARTTIME_2"], ngay)
    last = ngay + timedelta(days=3)
    clock(at(ngay, 23, 0))

    # Quy tắc 1: không gửi cho ca của người khác
    assert send_request(client, staff_other, days[0], "bu_ca_hai", vao=at(ngay, 8, 0), ra=at(ngay, 12, 0)).status_code == 403
    # Giờ vào phải trước giờ ra (validator chạy ở máy chủ)
    assert send_request(client, staff, days[0], "bu_ca_hai", vao=at(ngay, 12, 0), ra=at(ngay, 8, 0)).status_code == 400
    # BR-01: trùng với ca khác của mình
    res = send_request(client, staff, days[0], "bu_ca_hai", vao=at(ngay, 8, 0), ra=at(ngay, 19, 0),
                       ly_do="Tôi ở lại làm thêm tới tối vì thiếu người, có quản lý ca xác nhận")
    assert res.status_code == 400 and "trùng" in res.json()["detail"]
    # Lệch quá 2 giờ: bắt buộc lý do chi tiết, gắn cờ
    assert send_request(client, staff, days[0], "bu_ca_hai", vao=at(ngay, 5, 0), ra=at(ngay, 12, 0),
                        ly_do="Tôi quên chấm công").status_code == 400
    res = send_request(client, staff, days[0], "bu_ca_hai", vao=at(ngay, 5, 0), ra=at(ngay, 12, 0),
                       ly_do="Tôi đến sớm nhận hàng nguyên liệu theo chỉ đạo của quản lý ca sáng")
    assert res.status_code == 201 and res.json()["lech_nhieu"] is True

    # Quy tắc 6: yêu cầu thứ 4 trong tháng vẫn gửi được nhưng gắn cờ vượt hạn mức
    flags = []
    for pc_id, d in zip(days[1:], range(1, 4)):
        clock(at(ngay + timedelta(days=d), 13, 0))   # gửi trong hạn 48 giờ của từng ca
        r = send_request(client, staff, pc_id, "bu_ca_hai", vao=at(ngay + timedelta(days=d), 8, 0),
                         ra=at(ngay + timedelta(days=d), 12, 0))
        assert r.status_code == 201, r.text
        flags.append(r.json()["vuot_han_muc"])
    assert flags == [False, False, True]
    vuot = client.get(f"/api/attendance?tu_ngay={ngay}&den_ngay={last}&co=vuot_han_muc&ma_nv={nv}", headers=admin).json()
    assert vuot["tong_so"] >= 1


def test_request_reject_cancel_and_no_self_approval(client, clock):
    admin = admin_headers(client)
    owner = owner_headers(client)
    ids = shift_ids(client, admin)
    nv, staff = new_staff(client, admin)
    ngay = future_week(50)
    me = client.get("/api/auth/me", headers=admin).json()["ma_nv"]
    pc1 = assign(client, admin, nv, ids["CA_PARTTIME_1"], ngay, publish=False)
    mgr_pc = assign(client, admin, me, ids["CA_SANG"], ngay + timedelta(days=1), publish=False)
    pc2 = assign(client, admin, nv, ids["CA_PARTTIME_2"], ngay)
    clock(at(ngay, 23, 0))

    yc1 = send_request(client, staff, pc1, "bu_ca_hai", vao=at(ngay, 8, 0), ra=at(ngay, 12, 0)).json()
    assert client.post(f"/api/attendance/requests/{yc1['id']}/approve", headers=staff, json={}).status_code == 403
    assert client.post(f"/api/attendance/requests/{yc1['id']}/reject", headers=admin, json={}).status_code == 422
    rejected = client.post(f"/api/attendance/requests/{yc1['id']}/reject", headers=admin,
                           json={"ly_do": "Không có ai xác nhận bạn có mặt"}).json()
    assert rejected["trang_thai"] == "tu_choi" and rejected["ly_do_tu_choi"]
    # Bị từ chối thì được gửi yêu cầu mới nếu còn hạn
    assert send_request(client, staff, pc1, "bu_ca_hai", vao=at(ngay, 8, 0), ra=at(ngay, 12, 0)).status_code == 201

    yc2 = send_request(client, staff, pc2, "bu_ca_hai", vao=at(ngay, 18, 0), ra=at(ngay, 22, 0)).json()
    cancelled = client.post(f"/api/attendance/requests/{yc2['id']}/cancel", headers=staff).json()
    assert cancelled["trang_thai"] == "da_huy"
    mine = client.get("/api/attendance/requests/me", headers=staff).json()
    assert {r["trang_thai"] for r in mine} >= {"tu_choi", "da_huy", "cho_duyet"}

    # BR-08: yêu cầu của Quản lý do Chủ quán (Admin) duyệt, Quản lý không tự duyệt
    clock(at(ngay + timedelta(days=1), 15, 0))
    yc3 = send_request(client, admin, mgr_pc, "bu_ca_hai", vao=at(ngay + timedelta(days=1), 6, 0),
                       ra=at(ngay + timedelta(days=1), 14, 0)).json()
    assert client.post(f"/api/attendance/requests/{yc3['id']}/approve", headers=admin, json={}).status_code == 403
    res = client.post(f"/api/attendance/requests/{yc3['id']}/approve", headers=owner, json={})
    assert res.status_code == 200 and res.json()["trang_thai"] == "da_duyet"


def test_request_evidence_upload_rules(client, clock):
    admin = admin_headers(client)
    ids = shift_ids(client, admin)
    nv, staff = new_staff(client, admin)
    ngay = future_week(51)
    pc = assign(client, admin, nv, ids["CA_PARTTIME_1"], ngay)
    clock(at(ngay, 13, 0))
    yc = send_request(client, staff, pc, "bu_ca_hai", vao=at(ngay, 8, 0), ra=at(ngay, 12, 0)).json()
    url = f"/api/attendance/requests/{yc['id']}/files"
    assert client.post(url, headers=staff, files={"file": ("a.exe", b"x", "application/octet-stream")}).status_code == 400
    big = b"0" * (5 * 1024 * 1024 + 1)
    assert client.post(url, headers=staff, files={"file": ("big.pdf", big, "application/pdf")}).status_code == 400
    for i in range(3):
        res = client.post(url, headers=staff, files={"file": (f"bang-giao-ca-{i}.png", b"\x89PNG data", "image/png")})
        assert res.status_code == 200, res.text
    assert len(res.json()["tep"]) == 3
    assert client.post(url, headers=staff, files={"file": ("4.png", b"\x89PNG", "image/png")}).status_code == 400
    first = res.json()["tep"][0]["id"]
    assert len(client.delete(f"{url}/{first}", headers=staff).json()["tep"]) == 2


def test_explanation_request_removes_flag(client, clock):
    """Giải trình chấm công bị gắn cờ"""
    admin = admin_headers(client)
    ids = shift_ids(client, admin)
    nv, staff = new_staff(client, admin)
    ngay = future_week(52)
    pc = assign(client, admin, nv, ids["CA_PARTTIME_1"], ngay)
    clock(at(ngay, 8, 0))
    check_in(client, staff, pc, pos=FAR_AWAY)
    yc = send_request(client, staff, pc, "giai_trinh", ly_do="GPS điện thoại bị sai, tôi đang ở quầy pha chế").json()
    client.post(f"/api/attendance/requests/{yc['id']}/approve", headers=admin, json={})
    row = row_of(client, staff, ngay, pc)
    assert "ngoai_vi_tri" not in codes(row) and row["ghi_chu_xac_minh"]


def test_wrong_shift_request_moves_record(client, clock):
    """Sửa ca chấm công: chấm nhầm sang ca khác trong cùng ngày"""
    admin = admin_headers(client)
    ids = shift_ids(client, admin)
    nv, staff = new_staff(client, admin)
    ngay = future_week(53)
    wrong = assign(client, admin, nv, ids["CA_PARTTIME_1"], ngay, publish=False)  # 08-12
    right = assign(client, admin, nv, ids["CA_PARTTIME_2"], ngay)                 # 18-22
    clock(at(ngay, 8, 0))
    check_in(client, staff, wrong)
    clock(at(ngay, 11, 0))
    yc = send_request(client, staff, wrong, "sua_ca", ma_phan_cong_dung=right,
                      ly_do="Tôi bấm nhầm ca, hôm nay tôi làm ca tối").json()
    assert yc["ten_ca_dung"]
    client.post(f"/api/attendance/requests/{yc['id']}/approve", headers=admin, json={})
    detail = client.get(f"/api/attendance/assignments/{right}", headers=staff).json()
    assert detail["ca"]["gio_vao"] is not None


def test_lock_period_warns_about_pending_requests(client, clock):
    """Quy tắc 9"""
    admin = admin_headers(client)
    ids = shift_ids(client, admin)
    nv, staff = new_staff(client, admin)
    ngay = future_week(54)
    pc = assign(client, admin, nv, ids["CA_PARTTIME_1"], ngay)
    clock(at(ngay, 13, 0))
    yc = send_request(client, staff, pc, "bu_ca_hai", vao=at(ngay, 8, 0), ra=at(ngay, 12, 0)).json()
    body = {"tu_ngay": ngay.isoformat(), "den_ngay": (ngay + timedelta(days=6)).isoformat()}
    assert client.post("/api/attendance/periods/lock", headers=admin, json=body).status_code == 409
    res = client.post("/api/attendance/periods/lock", headers=admin, json={**body, "chuyen_yeu_cau_sang_ky_sau": True})
    assert res.status_code == 201 and res.json()["so_yeu_cau_chuyen_ky_sau"] == 1
    # Duyệt sau khi chốt: ghi thành điều chỉnh kỳ sau, không sửa bản ghi gốc
    client.post(f"/api/attendance/requests/{yc['id']}/approve", headers=admin, json={})
    detail = client.get(f"/api/attendance/assignments/{pc}", headers=admin).json()
    assert detail["ca"]["trang_thai"] == "vang_mat" and len(detail["dieu_chinh_ky_sau"]) == 1
    client.delete(f"/api/attendance/periods/{res.json()['id']}", headers=owner_headers(client))


def test_need_info_request_expires(client, clock):
    admin = admin_headers(client)
    ids = shift_ids(client, admin)
    nv, staff = new_staff(client, admin)
    ngay = future_week(55)
    pc = assign(client, admin, nv, ids["CA_PARTTIME_1"], ngay)
    clock(at(ngay, 13, 0))
    yc = send_request(client, staff, pc, "bu_ca_hai", vao=at(ngay, 8, 0), ra=at(ngay, 12, 0)).json()
    client.post(f"/api/attendance/requests/{yc['id']}/ask", headers=admin, json={"cau_hoi": "Ai xác nhận cho bạn?"})
    clock(at(ngay, 13, 0) + timedelta(hours=49))
    mine = client.get("/api/attendance/requests/me", headers=staff).json()
    assert next(r for r in mine if r["id"] == yc["id"])["trang_thai"] == "het_han"


# ---------- FR-11D: cấu hình ----------

def test_only_admin_can_change_settings(client):
    admin = admin_headers(client)
    owner = owner_headers(client)
    _, staff = new_staff(client, admin)
    current = client.get("/api/attendance/settings", headers=admin).json()
    assert current["co_the_sua"] is True
    assert client.get("/api/attendance/settings", headers=staff).status_code == 403
    assert client.put("/api/attendance/settings", headers=staff, json=current).status_code == 403
    changed = {**current, "mo_truoc_phut": 10}
    res = client.put("/api/attendance/settings", headers=admin, json=changed)
    assert res.status_code == 200 and res.json()["mo_truoc_phut"] == 10
    res = client.put("/api/attendance/settings", headers=owner, json=changed)
    assert res.status_code == 200 and res.json()["mo_truoc_phut"] == 10
    assert client.put("/api/attendance/settings", headers=owner, json={**current, "ban_kinh_m": 5}).status_code == 422
    client.put("/api/attendance/settings", headers=owner, json={**current, "mo_truoc_phut": 15})


# ---------- Dữ liệu mẫu và trang giao diện ----------

def test_seed_has_sample_attendance_last_week(client):
    admin = admin_headers(client)
    last_monday = shift_svc.week_start(date.today()) - timedelta(days=7)
    data = client.get(f"/api/attendance?tu_ngay={last_monday}&den_ngay={last_monday + timedelta(days=6)}&so_dong=200",
                      headers=admin).json()
    labels = set().union(*[codes(r) for r in data["items"]])
    assert {"dung_gio", "di_tre", "vang_mat", "chua_check_out", "ngoai_vi_tri", "khong_dinh_vi", "vuot_ca", "cho_duyet"} <= labels


@pytest.mark.parametrize("path", ["/attendance", "/attendance-history", "/attendance-manage", "/attendance-requests",
                                  "/attendance-detail", "/attendance-adjust", "/attendance-settings", "/attendance-help"])
def test_sprint5_pages_render(client, path):
    res = client.get(path)
    assert res.status_code == 200 and "<html" in res.text
