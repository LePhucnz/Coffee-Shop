import os
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from app.config import settings, BASE_DIR
from app.database import engine, Base, SessionLocal, add_missing_columns
import app.models  # Đăng ký toàn bộ metadata models
from app.services.seed_service import seed_database
from app.api import (
    auth_router, employees_router, contracts_router, system_router,
    shifts_router, notifications_router, attendance_router, attendance_requests_router
)

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Khởi tạo bảng cơ sở dữ liệu nếu chưa có
    Base.metadata.create_all(bind=engine)
    # Sprint 4-5: thêm cột mới vào bảng cũ (không cần xóa qlcl.db)
    add_missing_columns(engine)
    # Nạp dữ liệu mẫu ban đầu
    db = SessionLocal()
    try:
        seed_database(db)
    finally:
        db.close()
    yield

app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION,
    description="Hệ thống Quản lý Nhân sự & Ca làm việc cho Quán Cà phê (Sprint 1 - 5: RBAC, HRM, Xếp ca & Chấm công)",
    lifespan=lifespan
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

static_dir = os.path.join(BASE_DIR, "app", "static")
templates_dir = os.path.join(BASE_DIR, "app", "templates")
app.mount("/static", StaticFiles(directory=static_dir), name="static")

templates = Jinja2Templates(directory=templates_dir)

# Đăng ký API Routers
app.include_router(auth_router)
app.include_router(employees_router)
app.include_router(contracts_router)
app.include_router(system_router)
app.include_router(shifts_router)
app.include_router(notifications_router)
app.include_router(attendance_requests_router)
app.include_router(attendance_router)

# UI Routes (Giao diện người dùng render bằng Jinja2)
@app.get("/", response_class=HTMLResponse)
def index_page(request: Request):
    return templates.TemplateResponse(request=request, name="index.html", context={"title": "QL Ca Làm - Trang chủ"})

@app.get("/login", response_class=HTMLResponse)
def login_page(request: Request):
    return templates.TemplateResponse(request=request, name="login.html", context={"title": "Đăng nhập"})

@app.get("/register", response_class=HTMLResponse)
def register_page(request: Request):
    return templates.TemplateResponse(request=request, name="register.html", context={"title": "Đăng ký"})

@app.get("/forgot-password", response_class=HTMLResponse)
def forgot_password_page(request: Request):
    return templates.TemplateResponse(request=request, name="forgot-password.html", context={"title": "Quên mật khẩu"})

@app.get("/reset-password", response_class=HTMLResponse)
def reset_password_page(request: Request):
    return templates.TemplateResponse(request=request, name="reset-password.html", context={"title": "Đặt lại mật khẩu"})

@app.get("/dashboard", response_class=HTMLResponse)
def dashboard_page(request: Request):
    return templates.TemplateResponse(request=request, name="dashboard.html", context={"title": "Bảng điều khiển", "active": "dashboard"})

# Sprint 3: Hồ sơ nhân sự & Hợp đồng (FR-04, FR-05, FR-06)
# Phân quyền dữ liệu được kiểm tra ở API; admin_only chỉ để chuyển hướng Staff khỏi trang quản trị
@app.get("/employees", response_class=HTMLResponse)
def employees_page(request: Request):
    return templates.TemplateResponse(request=request, name="employees.html", context={"title": "Hồ sơ nhân sự", "active": "employees", "admin_only": True})

@app.get("/contracts", response_class=HTMLResponse)
def contracts_page(request: Request):
    return templates.TemplateResponse(request=request, name="contracts.html", context={"title": "Hợp đồng lao động", "active": "contracts", "admin_only": True})

@app.get("/profile", response_class=HTMLResponse)
def profile_page(request: Request):
    return templates.TemplateResponse(request=request, name="profile.html", context={"title": "Hồ sơ của tôi", "active": "profile"})

# Sprint 4: Đăng ký lịch rảnh và xếp ca (FR-07, FR-08, FR-09)
@app.get("/shift-registration", response_class=HTMLResponse)
def shift_registration_page(request: Request):
    return templates.TemplateResponse(request=request, name="shift-registration.html", context={"title": "Đăng ký ca", "active": "shift-registration"})

@app.get("/schedule", response_class=HTMLResponse)
def schedule_page(request: Request):
    return templates.TemplateResponse(request=request, name="schedule.html", context={"title": "Xếp ca", "active": "schedule", "admin_only": True})

@app.get("/my-schedule", response_class=HTMLResponse)
def my_schedule_page(request: Request):
    return templates.TemplateResponse(request=request, name="my-schedule.html", context={"title": "Lịch làm của tôi", "active": "my-schedule"})

# Sprint 5: Chấm công trực tuyến (FR-10, FR-11, FR-11A, FR-11B, FR-11C, FR-11D)
@app.get("/attendance", response_class=HTMLResponse)
def attendance_page(request: Request):
    return templates.TemplateResponse(request=request, name="attendance.html", context={"title": "Chấm công", "active": "attendance"})

@app.get("/attendance-history", response_class=HTMLResponse)
def attendance_history_page(request: Request):
    return templates.TemplateResponse(request=request, name="attendance-history.html", context={"title": "Lịch sử công", "active": "attendance-history"})

@app.get("/attendance-help", response_class=HTMLResponse)
def attendance_help_page(request: Request):
    return templates.TemplateResponse(request=request, name="attendance-help.html", context={"title": "Hướng dẫn chấm công", "active": "attendance-help"})

@app.get("/attendance-manage", response_class=HTMLResponse)
def attendance_manage_page(request: Request):
    return templates.TemplateResponse(request=request, name="attendance-manage.html", context={"title": "Quản lý chấm công", "active": "attendance-manage", "admin_only": True})

@app.get("/attendance-requests", response_class=HTMLResponse)
def attendance_requests_page(request: Request):
    return templates.TemplateResponse(request=request, name="attendance-requests.html", context={"title": "Yêu cầu bù/sửa công", "active": "attendance-requests", "admin_only": True})

@app.get("/attendance-detail", response_class=HTMLResponse)
def attendance_detail_page(request: Request):
    return templates.TemplateResponse(request=request, name="attendance-detail.html", context={"title": "Chi tiết chấm công", "active": "attendance-manage", "admin_only": True})

@app.get("/attendance-adjust", response_class=HTMLResponse)
def attendance_adjust_page(request: Request):
    return templates.TemplateResponse(request=request, name="attendance-adjust.html", context={"title": "Điều chỉnh công", "active": "attendance-manage", "admin_only": True})

@app.get("/attendance-settings", response_class=HTMLResponse)
def attendance_settings_page(request: Request):
    return templates.TemplateResponse(request=request, name="attendance-settings.html", context={"title": "Cài đặt chấm công", "active": "attendance-settings", "admin_only": True})
