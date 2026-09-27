from typing import List, Optional
from fastapi import Depends, HTTPException, status, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session
from app.database import get_db
from app.core.security import decode_token
from app.models.user import TaiKhoan

security_bearer = HTTPBearer(auto_error=False)

def get_token_from_request(
    request: Request,
    cred: Optional[HTTPAuthorizationCredentials] = Depends(security_bearer)
) -> Optional[str]:
    # 1. Bearer header
    if cred and cred.credentials:
        return cred.credentials
    # 2. Authorization header fallback
    auth_header = request.headers.get("Authorization")
    if auth_header and auth_header.startswith("Bearer "):
        return auth_header[7:].strip()
    # 3. Cookie fallback
    cookie_token = request.cookies.get("access_token")
    if cookie_token:
        if cookie_token.startswith("Bearer "):
            return cookie_token[7:].strip()
        return cookie_token
    return None

def get_current_user(
    token: Optional[str] = Depends(get_token_from_request),
    db: Session = Depends(get_db)
) -> TaiKhoan:
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Chưa cung cấp token xác thực (Vui lòng đăng nhập)",
            headers={"WWW-Authenticate": "Bearer"},
        )
    payload = decode_token(token)
    if not payload or payload.get("type") != "access":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token không hợp lệ hoặc đã hết hạn",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    username: str = payload.get("sub")
    if not username:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token thiếu thông tin người dùng",
        )

    user = db.query(TaiKhoan).filter(TaiKhoan.ten_dang_nhap == username).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Tài khoản không tồn tại trên hệ thống",
        )
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Tài khoản này đã bị vô hiệu hóa bởi Quản trị viên",
        )
    # FR-06: Check employee status
    if user.nhan_vien and user.nhan_vien.trang_thai == "da_nghi":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Nhân viên đã nghỉ việc không có quyền truy cập hệ thống",
        )

    return user

def require_roles(allowed_roles: List[str]):
    def role_checker(current_user: TaiKhoan = Depends(get_current_user)) -> TaiKhoan:
        role_name = current_user.vai_tro.ten_vai_tro if current_user.vai_tro else "Staff"
        if role_name not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Truy cập bị từ chối: Chức năng yêu cầu quyền [{', '.join(allowed_roles)}], nhưng bạn đang có quyền [{role_name}]"
            )
        return current_user
    return role_checker
