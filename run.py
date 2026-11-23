import os
import sys
import uvicorn

if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        try:
            sys.stdout.reconfigure(encoding="utf-8")
        except Exception:
            pass

    host = os.getenv("HOST", "0.0.0.0")
    port = int(os.getenv("PORT", os.getenv("SERVER_PORT", "8000")))
    reload_enabled = os.getenv("RELOAD", "false").lower() in ("1", "true", "yes")

    print("=" * 60)
    print("☕ HỆ THỐNG QUẢN LÝ NHÂN SỰ & CA LÀM - QUÁN CÀ PHÊ (SPRINT 1 - 6)")
    print(f"🌐 Máy chủ khởi động tại: http://localhost:{port}")
    print(f"📚 Tài liệu API Swagger:  http://localhost:{port}/docs")
    print("=" * 60)
    uvicorn.run("app.main:app", host=host, port=port, reload=reload_enabled)
