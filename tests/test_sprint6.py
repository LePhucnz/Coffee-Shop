"""
Sprint 6: Tự động tính lương và xuất báo cáo (FR-12, FR-13)
Mỗi test dùng một tuần riêng ở xa trong tương lai (không trùng tuần của test Sprint 5) và nhân viên riêng.
"""
import io
import itertools
import zipfile
from datetime import date, timedelta

import pytest

from app.models.attendance import BanGhiDieuChinh, KyCongDaChot
from app.services import payroll_service as payroll
from app.services import shift_service as shift_svc
from tests.test_sprint5 import (
    admin_headers, owner_headers, headers_for, shift_ids, new_staff, assign, at, check_in, check_out, send_request,
    clock  # noqa: F401 (fixture)
)

_week_counter = itertools.count(300)


def payroll_week():
    return shift_svc.week_start(date.today()) + timedelta(weeks=next(_week_counter))


def add_contract(client, admin, ma_nv, muc_luong, loai="Bán thời gian"):
    res = client.post("/api/contracts", headers=admin, json={
        "ma_nhan_vien": ma_nv, "loai_hop_dong": loai, "ngay_bat_dau": "2020-01-01",
        "ngay_ket_thuc": "2099-12-31", "muc_luong": muc_luong})
    assert res.status_code == 201, res.text


def work(client, clock, staff, pc, ngay, vao, ra):
    """Check-in / check-out đúng giờ cho trước, vao/ra là (giờ, phút)"""
    clock(at(ngay, *vao))
    res = check_in(client, staff, pc)
    assert res.status_code == 200, res.text
    if ra:
        clock(at(ngay, *ra))
        res = check_out(client, staff, pc)
        assert res.status_code == 200, res.text


def create_period(client, admin, tu, den, loai="tuan"):
    res = client.post("/api/payroll/periods", headers=admin,
                      json={"loai_ky": loai, "tu_ngay": tu.isoformat(), "den_ngay": den.isoformat()})
    assert res.status_code == 201, res.text
    return res.json()


def slip_of(period, ma_nv):
    return next(p for p in period["phieu"] if p["ma_nv"] == ma_nv)


def test_default_payroll_config_and_seed(client, db_session):
    cfg = payroll.get_payroll_config(db_session)
    assert cfg["gio_chuan_thang"] == 208 and cfg["cach_phat"] == "theo_phut"
    admin = admin_headers(client)
    data = client.get("/api/payroll/settings", headers=admin).json()
    coef = {h["ten_ca"]: h["he_so_luong"] for h in data["he_so_ca"]}
    assert coef["Part-time tối"] == 1.2 and coef["Ca sáng"] == 1.0
    assert any(h["ten"] == "Quốc khánh" and h["he_so"] == 2.0 for h in data["ngay_le"])


def test_hourly_salary_penalty_absence_and_shift_coefficient(client, clock):
    """Lương = giờ × đơn giá × hệ số ca - phạt trễ; vắng không có giờ công"""
    admin = admin_headers(client)
    ids = shift_ids(client, admin)
    nv, staff = new_staff(client, admin)
    add_contract(client, admin, nv, 25000)
    w = payroll_week()
    pcs = [assign(client, admin, nv, ids["CA_PARTTIME_1"], w + timedelta(days=d), publish=False) for d in range(3)]
    pc_night = assign(client, admin, nv, ids["CA_PARTTIME_2"], w + timedelta(days=3))
    work(client, clock, staff, pcs[0], w, (8, 0), (12, 0))                          # Đúng giờ: 4h
    work(client, clock, staff, pcs[1], w + timedelta(days=1), (8, 20), (12, 0))     # Trễ 20 phút: 3.67h
    work(client, clock, staff, pc_night, w + timedelta(days=3), (18, 0), (22, 0))   # Ca tối × 1.2: 4h
    clock(at(w + timedelta(days=8), 9, 0))                                          # Ngày 3 vắng

    period = create_period(client, admin, w, w + timedelta(days=6))
    slip = slip_of(period, nv)
    assert slip["don_gia_gio"] == 25000 and slip["loai_luong"] == "gio"
    assert slip["so_ca"] == 3 and slip["so_vang"] == 1 and slip["so_lan_tre"] == 1 and slip["phut_tre"] == 20
    assert slip["tong_gio"] == pytest.approx(11.67)
    assert slip["luong_co_ban"] == 100000 + 91750 + 120000
    assert slip["tien_phat"] == 20000            # 20 phút × 1.000 đ
    assert slip["tien_thuong"] == 0              # Kỳ tuần không xét chuyên cần
    assert slip["thuc_lanh"] == 311750 - 20000

    detail = client.get(f"/api/payroll/payslips/{slip['id']}", headers=admin).json()
    assert len(detail["ca"]) == 4
    night = next(c for c in detail["ca"] if c["ma_phan_cong"] == pc_night)
    assert night["he_so"] == 1.2 and night["thanh_tien"] == 120000
    assert any(k["loai"] == "phat" and k["nguon"] == "tu_dong" and k["so_tien"] == 20000 for k in detail["khoan"])


def test_monthly_contract_is_converted_and_holiday_coefficient(client, clock):
    admin = admin_headers(client)
    ids = shift_ids(client, admin)
    nv, staff = new_staff(client, admin)
    add_contract(client, admin, nv, 10400000, "Toàn thời gian")          # 10.400.000 / 208 = 50.000 đ/giờ
    w = payroll_week()
    holiday = w + timedelta(days=2)
    res = client.post("/api/payroll/holidays", headers=admin, json={"ngay": holiday.isoformat(), "ten": "Ngày lễ thử", "he_so": 2})
    assert res.status_code == 201, res.text
    assert client.post("/api/payroll/holidays", headers=admin,
                       json={"ngay": holiday.isoformat(), "ten": "Trùng", "he_so": 2}).status_code == 400
    pc = assign(client, admin, nv, ids["CA_PARTTIME_1"], holiday)
    work(client, clock, staff, pc, holiday, (7, 58), (12, 1))
    clock(at(w + timedelta(days=8), 9, 0))
    slip = slip_of(create_period(client, admin, w, w + timedelta(days=6), "tuy_chon"), nv)
    assert slip["loai_luong"] == "thang" and slip["don_gia_gio"] == 50000
    assert slip["luong_co_ban"] == 4 * 50000 * 2
    line = client.get(f"/api/payroll/payslips/{slip['id']}", headers=admin).json()["ca"][0]
    assert line["ngay_le"] == "Ngày lễ thử" and line["he_so"] == 2.0


def test_no_contract_gives_zero_with_warning(client, clock):
    admin = admin_headers(client)
    ids = shift_ids(client, admin)
    nv, staff = new_staff(client, admin)
    w = payroll_week()
    pc = assign(client, admin, nv, ids["CA_PARTTIME_1"], w)
    work(client, clock, staff, pc, w, (8, 0), (12, 0))
    clock(at(w + timedelta(days=8), 9, 0))
    period = create_period(client, admin, w, w + timedelta(days=6))
    slip = slip_of(period, nv)
    assert slip["thuc_lanh"] == 0 and slip["tong_gio"] == 4
    assert any("hợp đồng" in c for c in slip["canh_bao"])
    assert any("chưa có hợp đồng" in c for c in period["canh_bao"])


def test_attendance_bonus_for_monthly_period(client, clock):
    """Thưởng chuyên cần: kỳ tháng, đủ số ca tối thiểu, không trễ/sớm/vắng"""
    admin = admin_headers(client)
    ids = shift_ids(client, admin)
    good, good_h = new_staff(client, admin)
    late, late_h = new_staff(client, admin)
    add_contract(client, admin, good, 25000)
    add_contract(client, admin, late, 25000)
    w = payroll_week()
    plan = []
    for d in range(4):
        day = w + timedelta(days=d)
        a = assign(client, admin, good, ids["CA_PARTTIME_1"], day, publish=False)
        b = assign(client, admin, late, ids["CA_PARTTIME_1"], day, publish=(d == 3))
        plan.append((day, a, b))
    for day, a, b in plan:
        clock(at(day, 8, 0))
        assert check_in(client, good_h, a).status_code == 200
        if day != w:
            assert check_in(client, late_h, b).status_code == 200
        clock(at(day, 8, 30))
        if day == w:
            assert check_in(client, late_h, b).status_code == 200
        clock(at(day, 12, 0))
        assert check_out(client, good_h, a).status_code == 200
        assert check_out(client, late_h, b).status_code == 200
    clock(at(w + timedelta(days=8), 9, 0))
    period = create_period(client, admin, w, w + timedelta(days=6), "thang")
    assert slip_of(period, good)["tien_thuong"] == 300000
    assert slip_of(period, late)["tien_thuong"] == 0
    assert slip_of(period, late)["tien_phat"] == 30000


def test_waived_penalty_overtime_and_manual_items(client, clock):
    admin = admin_headers(client)
    ids = shift_ids(client, admin)
    nv, staff = new_staff(client, admin)
    add_contract(client, admin, nv, 30000)
    w = payroll_week()
    pc = assign(client, admin, nv, ids["CA_PARTTIME_1"], w)
    work(client, clock, staff, pc, w, (8, 15), (12, 30))   # Trễ 15 phút, vượt ca 30 phút
    clock(at(w + timedelta(days=8), 9, 0))
    period = create_period(client, admin, w, w + timedelta(days=6))
    slip = slip_of(period, nv)
    assert slip["tien_phat"] == 15000 and slip["tong_gio"] == 3.75   # Vượt ca chưa duyệt không tính (BR-09)
    assert any("vượt ca" in c for c in slip["canh_bao"])

    assert client.post(f"/api/attendance/assignments/{pc}/waive", headers=admin,
                       json={"mien_phat": True, "ly_do": "Kẹt xe do mưa lớn"}).status_code == 200
    assert client.post(f"/api/attendance/assignments/{pc}/overtime", headers=admin,
                       json={"so_phut": 30, "ly_do": "Đông khách cần ở lại"}).status_code == 200
    res = client.post(f"/api/payroll/payslips/{slip['id']}/items", headers=admin,
                      json={"loai": "phu_cap", "so_tien": 200000, "ly_do": "Phụ cấp làm sự kiện"})
    assert res.status_code == 201, res.text
    assert res.json()["tien_thuong"] == 200000

    period = client.post(f"/api/payroll/periods/{period['id']}/calculate", headers=admin).json()
    slip = slip_of(period, nv)
    assert slip["tien_phat"] == 0 and slip["tong_gio"] == 4.25
    assert slip["tien_thuong"] == 200000                 # Khoản thủ công được giữ khi tính lại
    assert slip["thuc_lanh"] == round(4.25 * 30000) + 200000

    detail = client.get(f"/api/payroll/payslips/{slip['id']}", headers=admin).json()
    manual = next(k for k in detail["khoan"] if k["nguon"] == "thu_cong")
    assert manual["nguoi_tao"] == "Nguyễn Văn A"
    res = client.delete(f"/api/payroll/payslips/{slip['id']}/items/{manual['id']}", headers=admin)
    assert res.status_code == 200 and res.json()["thuc_lanh"] == round(4.25 * 30000)


def test_overlapping_period_and_validation(client):
    admin = admin_headers(client)
    w = payroll_week()
    period = create_period(client, admin, w, w + timedelta(days=6))
    res = client.post("/api/payroll/periods", headers=admin,
                      json={"loai_ky": "tuan", "tu_ngay": (w + timedelta(days=3)).isoformat(),
                            "den_ngay": (w + timedelta(days=9)).isoformat()})
    assert res.status_code == 400 and "trùng" in res.json()["detail"]
    res = client.post("/api/payroll/periods", headers=admin,
                      json={"loai_ky": "thang", "tu_ngay": w.isoformat(), "den_ngay": (w - timedelta(days=1)).isoformat()})
    assert res.status_code == 422
    assert client.delete(f"/api/payroll/periods/{period['id']}", headers=admin).status_code == 200


def test_staff_cannot_use_payroll_admin(client):
    staff = headers_for(client, "le.c", "Staff@123456")
    assert client.get("/api/payroll/periods", headers=staff).status_code == 403
    assert client.get("/api/payroll/settings", headers=staff).status_code == 403
    assert client.post("/api/payroll/periods", headers=staff,
                       json={"tu_ngay": "2030-01-01", "den_ngay": "2030-01-31"}).status_code == 403


def test_manager_cannot_edit_own_payslip(client, clock):
    """BR-08: nguyen.a (Quản lý) không tự thêm khoản vào phiếu của mình, Chủ quán thì được"""
    admin = admin_headers(client)
    ids = shift_ids(client, admin)
    w = payroll_week()
    pc = assign(client, admin, 1, ids["CA_PARTTIME_1"], w)
    clock(at(w + timedelta(days=8), 9, 0))
    slip = slip_of(create_period(client, admin, w, w + timedelta(days=6)), 1)
    body = {"loai": "thuong", "so_tien": 100000, "ly_do": "Thưởng nóng"}
    assert client.post(f"/api/payroll/payslips/{slip['id']}/items", headers=admin, json=body).status_code == 403
    assert client.get(f"/api/payroll/payslips/{slip['id']}", headers=admin).json()["co_the_sua"] is False
    assert client.post(f"/api/payroll/payslips/{slip['id']}/items", headers=owner_headers(client), json=body).status_code == 201
    assert pc


def test_finalize_flow_locks_attendance_and_staff_sees_own_payslip(client, clock, db_session):
    admin = admin_headers(client)
    ids = shift_ids(client, admin)
    nv, staff = new_staff(client, admin)
    other, other_h = new_staff(client, admin)
    add_contract(client, admin, nv, 25000)
    w = payroll_week()
    pc1 = assign(client, admin, nv, ids["CA_PARTTIME_1"], w, publish=False)
    pc2 = assign(client, admin, nv, ids["CA_PARTTIME_1"], w + timedelta(days=1))
    work(client, clock, staff, pc1, w, (8, 0), (12, 0))
    clock(at(w + timedelta(days=1), 13, 0))
    yc = send_request(client, staff, pc2, "bu_ca_hai", vao=at(w + timedelta(days=1), 8, 0),
                      ra=at(w + timedelta(days=1), 12, 0))
    assert yc.status_code == 201, yc.text

    period = create_period(client, admin, w, w + timedelta(days=6))
    slip = slip_of(period, nv)
    # Kỳ chưa kết thúc thì chưa chốt được
    res = client.post(f"/api/payroll/periods/{period['id']}/finalize", headers=admin, json={})
    assert res.status_code == 400 and "chưa kết thúc" in res.json()["detail"]
    # Nhân viên chưa thấy phiếu nháp
    assert client.get(f"/api/payroll/payslips/{slip['id']}", headers=staff).status_code == 404
    assert client.get("/api/payroll/payslips/me", headers=staff).json() == []

    clock(at(w + timedelta(days=8), 9, 0))
    res = client.post(f"/api/payroll/periods/{period['id']}/finalize", headers=admin, json={})
    assert res.status_code == 409
    res = client.post(f"/api/payroll/periods/{period['id']}/finalize", headers=admin,
                      json={"chuyen_yeu_cau_sang_ky_sau": True})
    assert res.status_code == 200, res.text
    period = res.json()
    assert period["trang_thai"] == "da_chot" and period["nguoi_chot"] == "Nguyễn Văn A"
    assert slip_of(period, nv)["thuc_lanh"] == 100000
    lock = db_session.query(KyCongDaChot).filter(KyCongDaChot.tu_ngay == w).one()
    assert lock.den_ngay == w + timedelta(days=6)

    # Đã chốt thì không tính lại, không thêm khoản, không xóa
    assert client.post(f"/api/payroll/periods/{period['id']}/calculate", headers=admin).status_code == 400
    assert client.post(f"/api/payroll/payslips/{slip['id']}/items", headers=owner_headers(client),
                       json={"loai": "thuong", "so_tien": 1000, "ly_do": "Thử sau chốt"}).status_code == 400
    assert client.delete(f"/api/payroll/periods/{period['id']}", headers=admin).status_code == 400

    # Nhân viên xem/tải phiếu của mình, không xem được của người khác
    mine = client.get("/api/payroll/payslips/me", headers=staff).json()
    assert [p["id"] for p in mine] == [slip["id"]]
    assert client.get(f"/api/payroll/payslips/{slip['id']}", headers=staff).status_code == 200
    assert client.get(f"/api/payroll/payslips/{slip['id']}", headers=other_h).status_code == 403
    assert client.get(f"/api/payroll/payslips/{slip['id']}/export?dinh_dang=pdf", headers=other_h).status_code == 403
    pdf = client.get(f"/api/payroll/payslips/{slip['id']}/export?dinh_dang=pdf", headers=staff)
    assert pdf.status_code == 200 and pdf.content.startswith(b"%PDF")
    notif = client.get("/api/notifications/me", headers=staff).json()
    assert any("phiếu lương" in n["tieu_de"].lower() for n in notif["items"])

    # Duyệt yêu cầu sau khi chốt: thành bản ghi điều chỉnh, cộng vào kỳ lương sau (BR-04)
    assert client.post(f"/api/attendance/requests/{yc.json()['id']}/approve", headers=admin, json={}).status_code == 200
    adj = db_session.query(BanGhiDieuChinh).filter(BanGhiDieuChinh.ma_phan_cong == pc2).one()
    assert float(adj.so_gio_chenh) == 4.0
    nxt = create_period(client, admin, w + timedelta(days=7), w + timedelta(days=13))
    nslip = slip_of(nxt, nv)
    assert nslip["gio_dieu_chinh"] == 4.0 and nslip["luong_co_ban"] == 100000
    assert client.delete(f"/api/payroll/periods/{nxt['id']}", headers=admin).status_code == 200


def test_exports_excel_and_pdf(client, clock):
    admin = admin_headers(client)
    ids = shift_ids(client, admin)
    nv, staff = new_staff(client, admin)
    add_contract(client, admin, nv, 25000)
    w = payroll_week()
    pc = assign(client, admin, nv, ids["CA_PARTTIME_1"], w)
    work(client, clock, staff, pc, w, (8, 0), (12, 0))
    clock(at(w + timedelta(days=8), 9, 0))
    period = create_period(client, admin, w, w + timedelta(days=6))

    res = client.get(f"/api/payroll/periods/{period['id']}/export?dinh_dang=xlsx", headers=admin)
    assert res.status_code == 200 and "bang-luong-" in res.headers["content-disposition"]
    z = zipfile.ZipFile(io.BytesIO(res.content))
    assert {"xl/worksheets/sheet1.xml", "xl/worksheets/sheet4.xml"} <= set(z.namelist())
    sheet = z.read("xl/worksheets/sheet1.xml").decode()
    assert "Thực lãnh" in sheet and "TỔNG CỘNG" in sheet and "100000" in sheet

    res = client.get(f"/api/payroll/periods/{period['id']}/export?dinh_dang=pdf", headers=admin)
    assert res.status_code == 200 and res.content.startswith(b"%PDF")
    slip = slip_of(period, nv)
    res = client.get(f"/api/payroll/payslips/{slip['id']}/export?dinh_dang=xlsx", headers=admin)
    assert res.status_code == 200
    assert "THỰC LÃNH" in zipfile.ZipFile(io.BytesIO(res.content)).read("xl/worksheets/sheet1.xml").decode()
    assert client.get(f"/api/payroll/periods/{period['id']}/export?dinh_dang=pdf",
                      headers=headers_for(client, "le.c", "Staff@123456")).status_code == 403


def test_settings_update_applies_on_next_calculation(client, clock):
    owner = owner_headers(client)
    admin = admin_headers(client)
    original = client.get("/api/payroll/settings", headers=owner).json()
    body = {**original, "cach_phat": "co_dinh", "phat_moi_lan": 50000}
    res = client.put("/api/payroll/settings", headers=owner, json=body)
    assert res.status_code == 200 and res.json()["cach_phat"] == "co_dinh"
    try:
        ids = shift_ids(client, admin)
        nv, staff = new_staff(client, admin)
        add_contract(client, admin, nv, 25000)
        w = payroll_week()
        pc = assign(client, admin, nv, ids["CA_PARTTIME_1"], w)
        work(client, clock, staff, pc, w, (8, 10), (11, 50))   # Trễ 10 + sớm 10 = 2 lần × 50.000
        clock(at(w + timedelta(days=8), 9, 0))
        slip = slip_of(create_period(client, admin, w, w + timedelta(days=6)), nv)
        assert slip["tien_phat"] == 100000
    finally:
        client.put("/api/payroll/settings", headers=owner, json=original)
    assert client.get("/api/payroll/settings", headers=owner).json()["cach_phat"] == original["cach_phat"]


@pytest.mark.parametrize("path", ["/payroll", "/payslip", "/my-payslips", "/payroll-settings"])
def test_sprint6_pages_render(client, path):
    res = client.get(path)
    assert res.status_code == 200 and "QL Ca Làm" in res.text
