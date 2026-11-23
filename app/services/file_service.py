import os
import uuid
from fastapi import UploadFile, HTTPException, status
from app.config import BASE_DIR

# Thư mục lưu file upload (ảnh đại diện, file hợp đồng)
UPLOAD_ROOT = os.path.join(BASE_DIR, "app", "static", "uploads")
MAX_UPLOAD_SIZE = 5 * 1024 * 1024  # 5MB

IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp"}
CONTRACT_EXTENSIONS = {".pdf", ".jpg", ".jpeg", ".png"}


def save_upload(file: UploadFile, subdir: str, allowed_ext: set) -> str:
    """
    Lưu file upload vào app/static/uploads/<subdir>/ với tên ngẫu nhiên.
    Trả về đường dẫn public dạng /static/uploads/<subdir>/<ten_file>.
    """
    ext = os.path.splitext(file.filename or "")[1].lower()
    if ext not in allowed_ext:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Định dạng file không hợp lệ. Chỉ chấp nhận: {', '.join(sorted(allowed_ext))}"
        )

    data = file.file.read()
    if not data:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="File rỗng")
    if len(data) > MAX_UPLOAD_SIZE:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="File vượt quá dung lượng cho phép (5MB)")

    folder = os.path.join(UPLOAD_ROOT, subdir)
    os.makedirs(folder, exist_ok=True)
    # Không dùng tên gốc để tránh trùng tên và path traversal
    filename = f"{uuid.uuid4().hex}{ext}"
    with open(os.path.join(folder, filename), "wb") as f:
        f.write(data)
    return f"/static/uploads/{subdir}/{filename}"
