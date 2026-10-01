import os
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

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

frontend_dir = os.path.join(BASE_DIR, "frontend")
if os.path.exists(frontend_dir):
    app.mount("/frontend", StaticFiles(directory=frontend_dir, html=True), name="frontend")

# Đăng ký API Routers
app.include_router(auth_router)
app.include_router(employees_router)
app.include_router(contracts_router)
app.include_router(system_router)
