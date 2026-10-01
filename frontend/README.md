# ☕ QL Ca Làm - Frontend Client (Giao diện người dùng)

Thư mục `frontend/` được tách biệt hoàn toàn theo kiến trúc **Client – Server**, chỉ chứa mã nguồn giao diện (HTML/CSS/JavaScript thuần túy), không phụ thuộc vào framework nặng hoặc template engine server.

---

## 📁 Cấu trúc thư mục

```
frontend/
├── index.html            # [Ảnh 1] Trang chủ giới thiệu (Landing Page)
├── register.html         # [Ảnh 2] Đăng ký tài khoản (Register)
├── login.html            # [Ảnh 3] Đăng nhập hệ thống (Login)
├── forgot-password.html  # [Ảnh 4] Đặt lại mật khẩu (Forgot Password)
├── reset-password.html   # [Ảnh 5] Mật khẩu mới (Reset Password)
├── dashboard.html        # [Ảnh 6] Bảng điều khiển Quản lý (Tổng quan quán)
├── css/
│   └── style.css         # Hệ thống Design System, Token màu và Style đồng nhất
├── js/
│   ├── auth.js           # Xử lý form, ẩn/hiện mắt xem mật khẩu, chuyển hướng
│   └── dashboard.js      # Tương tác biểu đồ thanh, thời gian thực, nút lối tắt
└── README.md             # Hướng dẫn này
```

---

## 🎨 Tổng quan các màn hình thiết kế (Pixel-Perfect)

| Tên màn hình | File HTML | Mô tả chi tiết |
| :--- | :--- | :--- |
| **Landing Page** | [`index.html`](./index.html) | Header thương hiệu `QL Ca Làm`, Hero section với nút Dùng thử, Widget Ca Sáng (06:00 - 12:00) với 3 nhân sự thực tế, 3 card tính năng vượt trội (*Xếp ca thông minh, Chấm công GPS, Tính lương tự động*). |
| **Đăng ký tài khoản** | [`register.html`](./register.html) | Card bo tròn căn giữa, 4 trường dữ liệu (*Họ tên, Email, Mật khẩu, Xác nhận*), icon mắt ẩn/hiện mật khẩu, checkbox điều khoản. |
| **Đăng nhập** | [`login.html`](./login.html) | Trường Email/SĐT, Mật khẩu, Ghi nhớ mật khẩu, liên kết Quên mật khẩu & Đăng ký ngay. |
| **Đặt lại mật khẩu** | [`forgot-password.html`](./forgot-password.html) | Icon ổ khóa vàng cam, ô nhập Email, nút Gửi liên kết, liên kết quay lại đăng nhập. |
| **Mật khẩu mới** | [`reset-password.html`](./reset-password.html) | Icon chìa khóa vàng cam, 2 trường mật khẩu mới kèm icon mắt xác thực. |
| **Bảng điều khiển quán** | [`dashboard.html`](./dashboard.html) | Sidebar đen trầm chuẩn phong cách cà phê đậm vị (Menu: Tổng quan, Nhân sự, Ca, Chấm công, Lương, Báo cáo), 3 thẻ thống kê (Nhân viên 18 NV, Ca làm 6 Ca, Thiếu nhân sự 2 Thiếu ca), biểu đồ cột xu hướng giờ làm 12 tháng (T1 - T12), bảng lịch trình hôm nay và hàng lối tắt nhanh. |

---

## 🚀 Cách mở và chạy giao diện

1. **Mở trực tiếp trên trình duyệt (Không cần server):**
   * Bạn có thể mở trực tiếp bất kỳ file `.html` nào bằng cách click đúp chuột hoặc dùng tiện ích Live Server trong VS Code.
   * Tất cả liên kết giữa các trang đều dùng đường dẫn tương đối (`./login.html`, `./dashboard.html`...) nên hoạt động mượt mà ở mọi môi trường.

2. **Chạy qua máy chủ backend FastAPI:**
   * Thư mục `frontend/` được mount trực tiếp tại:
     * `http://localhost:8000/frontend/index.html`
     * `http://localhost:8000/frontend/dashboard.html`
     * `http://localhost:8000/frontend/login.html`
     * `http://localhost:8000/frontend/register.html`
