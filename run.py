import uvicorn

if __name__ == "__main__":
    print("=" * 60)
    print("☕ HỆ THỐNG QUẢN LÝ NHÂN SỰ & CA LÀM - QUÁN CÀ PHÊ (SPRINT 1 - 3)")
    print("🌐 Máy chủ khởi động tại: http://localhost:8000")
    print("📚 Tài liệu API Swagger:  http://localhost:8000/docs")
    print("=" * 60)
    uvicorn.run("app.main:app", host="127.0.0.1", port=8000, reload=True)
