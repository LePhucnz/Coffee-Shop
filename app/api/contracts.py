from typing import Optional, List
from datetime import date
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from app.database import get_db
from app.core.deps import get_current_user, require_roles
from app.models.employee import HopDong, NhanVien
from app.models.user import TaiKhoan
from app.schemas.contract import (
    HopDongCreate, HopDongUpdate, HopDongResponse, HopDongExpiringAlert
)

router = APIRouter(prefix="/api/contracts", tags=["Quản lý Hợp đồng Lao động (Contracts)"])

def map_hop_dong_response(hd: HopDong) -> HopDongResponse:
    today = date.today()
    so_ngay = None
    canh_bao = False
    if hd.ngay_ket_thuc:
        so_ngay = (hd.ngay_ket_thuc - today).days
        # FR-05: Cảnh báo trước 15-30 ngày khi hợp đồng sắp hết hạn
        if 0 <= so_ngay <= 30 and hd.trang_thai == "hieu_luc":
            canh_bao = True

    return HopDongResponse(
        id=hd.id,
        ma_nhan_vien=hd.ma_nhan_vien,
        loai_hop_dong=hd.loai_hop_dong,
        ngay_bat_dau=hd.ngay_bat_dau,
        ngay_ket_thuc=hd.ngay_ket_thuc,
        muc_luong=hd.muc_luong,
        ma_bang_luong=hd.ma_bang_luong,
        file_dinh_kem=hd.file_dinh_kem,
        trang_thai=hd.trang_thai,
        ngay_tao=hd.ngay_tao,
        ho_ten_nhan_vien=hd.nhan_vien.ho_ten if hd.nhan_vien else None,
        ma_nhan_vien_code=hd.nhan_vien.ma_nhan_vien if hd.nhan_vien else None,
        so_ngay_con_lai=so_ngay,
        canh_bao_het_han=canh_bao
    )

@router.get("", response_model=List[HopDongResponse])
def list_contracts(
    ma_nhan_vien: Optional[int] = Query(None, description="Lọc theo mã nhân viên"),
    loai_hop_dong: Optional[str] = Query(None, description="Lọc theo loại hợp đồng"),
    trang_thai: Optional[str] = Query(None, description="Lọc theo trạng thái hợp đồng"),
    current_user: TaiKhoan = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    FR-05: Danh sách hợp đồng
    - Admin/Manager xem toàn bộ
    - Staff chỉ xem hợp đồng của chính mình
    """
    role_name = current_user.vai_tro.ten_vai_tro if current_user.vai_tro else "Staff"
    query = db.query(HopDong)

    if role_name not in ["Admin", "Manager"]:
        if not current_user.ma_nv:
            return []
        query = query.filter(HopDong.ma_nhan_vien == current_user.ma_nv)
    else:
        if ma_nhan_vien:
            query = query.filter(HopDong.ma_nhan_vien == ma_nhan_vien)

    if loai_hop_dong:
        query = query.filter(HopDong.loai_hop_dong == loai_hop_dong)
    if trang_thai:
        query = query.filter(HopDong.trang_thai == trang_thai)

    items = query.order_by(HopDong.id.desc()).all()
    return [map_hop_dong_response(item) for item in items]

@router.get("/expiring", response_model=List[HopDongExpiringAlert])
def list_expiring_contracts(
    days: int = Query(30, ge=1, le=90, description="Ngưỡng ngày cảnh báo hết hạn (mặc định 30 ngày)"),
    current_user: TaiKhoan = Depends(require_roles(["Admin", "Manager"])),
    db: Session = Depends(get_db)
):
    """
    FR-05: Cảnh báo hợp đồng sắp hết hạn trong vòng 15-30 ngày
    """
    today = date.today()
    contracts = db.query(HopDong).filter(
        HopDong.trang_thai == "hieu_luc",
        HopDong.ngay_ket_thuc.isnot(None)
    ).all()

    alert_list = []
    for hd in contracts:
        delta = (hd.ngay_ket_thuc - today).days
        if 0 <= delta <= days:
            alert_list.append(
                HopDongExpiringAlert(
                    id=hd.id,
                    ma_nhan_vien=hd.ma_nhan_vien,
                    ho_ten=hd.nhan_vien.ho_ten if hd.nhan_vien else "N/A",
                    ma_nhan_vien_code=hd.nhan_vien.ma_nhan_vien if hd.nhan_vien else None,
                    loai_hop_dong=hd.loai_hop_dong,
                    ngay_ket_thuc=hd.ngay_ket_thuc,
                    so_ngay_con_lai=delta,
                    muc_luong=hd.muc_luong
                )
            )

    alert_list.sort(key=lambda x: x.so_ngay_con_lai)
    return alert_list

@router.post("", response_model=HopDongResponse, status_code=status.HTTP_201_CREATED)
def create_contract(
    data: HopDongCreate,
    current_user: TaiKhoan = Depends(require_roles(["Admin", "Manager"])),
    db: Session = Depends(get_db)
):
    """FR-05: Thêm mới hợp đồng lao động"""
    nv = db.query(NhanVien).filter(NhanVien.id == data.ma_nhan_vien).first()
    if not nv:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Không tìm thấy nhân viên được chỉ định")

    if data.ngay_bat_dau and data.ngay_ket_thuc and data.ngay_bat_dau > data.ngay_ket_thuc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Ngày bắt đầu không được lớn hơn ngày kết thúc")

    hd = HopDong(
        ma_nhan_vien=data.ma_nhan_vien,
        loai_hop_dong=data.loai_hop_dong,
        ngay_bat_dau=data.ngay_bat_dau,
        ngay_ket_thuc=data.ngay_ket_thuc,
        muc_luong=data.muc_luong,
        ma_bang_luong=data.ma_bang_luong,
        file_dinh_kem=data.file_dinh_kem,
        trang_thai=data.trang_thai or "hieu_luc"
    )
    db.add(hd)
    db.commit()
    db.refresh(hd)
    return map_hop_dong_response(hd)

@router.get("/{contract_id}", response_model=HopDongResponse)
def get_contract(
    contract_id: int,
    current_user: TaiKhoan = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Xem chi tiết hợp đồng"""
    hd = db.query(HopDong).filter(HopDong.id == contract_id).first()
    if not hd:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Không tìm thấy hợp đồng")

    role_name = current_user.vai_tro.ten_vai_tro if current_user.vai_tro else "Staff"
    if role_name not in ["Admin", "Manager"] and current_user.ma_nv != hd.ma_nhan_vien:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Không có quyền xem hợp đồng này")

    return map_hop_dong_response(hd)

@router.put("/{contract_id}", response_model=HopDongResponse)
def update_contract(
    contract_id: int,
    data: HopDongUpdate,
    current_user: TaiKhoan = Depends(require_roles(["Admin", "Manager"])),
    db: Session = Depends(get_db)
):
    """Cập nhật thông tin hợp đồng"""
    hd = db.query(HopDong).filter(HopDong.id == contract_id).first()
    if not hd:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Không tìm thấy hợp đồng")

    update_fields = data.model_dump(exclude_unset=True)
    for field, value in update_fields.items():
        setattr(hd, field, value)

    if hd.ngay_bat_dau and hd.ngay_ket_thuc and hd.ngay_bat_dau > hd.ngay_ket_thuc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Ngày bắt đầu không được lớn hơn ngày kết thúc")

    db.commit()
    db.refresh(hd)
    return map_hop_dong_response(hd)

@router.delete("/{contract_id}")
def delete_contract(
    contract_id: int,
    current_user: TaiKhoan = Depends(require_roles(["Admin", "Manager"])),
    db: Session = Depends(get_db)
):
    """Xóa hợp đồng"""
    hd = db.query(HopDong).filter(HopDong.id == contract_id).first()
    if not hd:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Không tìm thấy hợp đồng")

    db.delete(hd)
    db.commit()
    return {"message": "Đã xóa hợp đồng thành công"}
