import os
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings, BASE_DIR
from app.database import engine, Base, SessionLocal
import app.models  # Đăng ký toàn bộ metadata models
from app.services.seed_service import seed_database
from app.api import auth_router, employees_router, contracts_router, system_router

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Khởi tạo bảng cơ sở dữ liệu nếu chưa có
    Base.metadata.create_all(bind=engine)
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
    description="Hệ thống Quản lý Nhân sự & Ca làm việc cho Quán Cà phê (Sprint 1 - 3: RBAC & HRM)",
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

# Đăng ký thư mục Static và Templates
static_dir = os.path.join(BASE_DIR, "app", "static")
templates_dir = os.path.join(BASE_DIR, "app", "templates")
os.makedirs(static_dir, exist_ok=True)
os.makedirs(templates_dir, exist_ok=True)

app.mount("/static", StaticFiles(directory=static_dir), name="static")
templates = Jinja2Templates(directory=templates_dir)

# Đăng ký API Routers
app.include_router(auth_router)
app.include_router(employees_router)
app.include_router(contracts_router)
app.include_router(system_router)

# UI Routes (Giao diện người dùng)
@app.get("/", response_class=HTMLResponse)
def index_page():
    return RedirectResponse(url="/dashboard")

@app.get("/login", response_class=HTMLResponse)
def login_page(request: Request):
    return templates.TemplateResponse("login.html", {"request": request, "title": "Đăng nhập hệ thống"})

@app.get("/dashboard", response_class=HTMLResponse)
def dashboard_page(request: Request):
    return templates.TemplateResponse("dashboard.html", {"request": request, "title": "Bảng điều khiển"})

@app.get("/employees", response_class=HTMLResponse)
def employees_page(request: Request):
    return templates.TemplateResponse("employees.html", {"request": request, "title": "Quản lý Hồ sơ Nhân sự"})

@app.get("/contracts", response_class=HTMLResponse)
def contracts_page(request: Request):
    return templates.TemplateResponse("contracts.html", {"request": request, "title": "Quản lý Hợp đồng Lao động"})
