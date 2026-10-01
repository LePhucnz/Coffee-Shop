// Standalone Frontend Auth Interactions
document.addEventListener("DOMContentLoaded", () => {
    // Password Reveal / Hide Eye Toggle
    document.querySelectorAll(".btn-toggle-pw").forEach(btn => {
        btn.addEventListener("click", () => {
            const targetId = btn.getAttribute("data-target");
            const input = document.getElementById(targetId);
            if (!input) return;

            const iconEye = btn.querySelector(".icon-eye");
            const iconEyeOff = btn.querySelector(".icon-eye-off");

            if (input.type === "password") {
                input.type = "text";
                if (iconEye) iconEye.classList.add("hidden");
                if (iconEyeOff) iconEyeOff.classList.remove("hidden");
            } else {
                input.type = "password";
                if (iconEye) iconEye.classList.remove("hidden");
                if (iconEyeOff) iconEyeOff.classList.add("hidden");
            }
        });
    });

    // Form Submissions with real API calls
    const loginForm = document.getElementById("form-login");
    if (loginForm) {
        loginForm.addEventListener("submit", async (e) => {
            e.preventDefault();
            const identifier = document.getElementById("login-identifier")?.value.trim();
            const password = document.getElementById("login-password")?.value;
            const btn = loginForm.querySelector("button[type='submit']");
            const originalText = btn.innerText;

            btn.disabled = true;
            btn.innerText = "Đang đăng nhập...";

            try {
                const res = await fetch("/api/auth/login", {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({ ten_dang_nhap: identifier, mat_khau: password })
                });
                const data = await res.json();
                if (!res.ok) {
                    alert(data.detail || "Đăng nhập thất bại");
                    btn.disabled = false;
                    btn.innerText = originalText;
                    return;
                }
                localStorage.setItem("access_token", data.access_token);
                localStorage.setItem("refresh_token", data.refresh_token);
                localStorage.setItem("user", JSON.stringify(data.user));
                window.location.href = "/dashboard";
            } catch (err) {
                alert("Lỗi kết nối máy chủ: " + err.message);
                btn.disabled = false;
                btn.innerText = originalText;
            }
        });
    }

    const registerForm = document.getElementById("form-register");
    if (registerForm) {
        registerForm.addEventListener("submit", async (e) => {
            e.preventDefault();
            const hoTen = document.getElementById("reg-fullname")?.value.trim();
            const email = document.getElementById("reg-email")?.value.trim();
            const pw = document.getElementById("reg-password")?.value;
            const confirmPw = document.getElementById("reg-confirm-password")?.value;

            if (pw !== confirmPw) {
                alert("Mật khẩu xác nhận không trùng khớp!");
                return;
            }

            const btn = registerForm.querySelector("button[type='submit']");
            const originalText = btn.innerText;
            btn.disabled = true;
            btn.innerText = "Đang tạo tài khoản...";

            try {
                const res = await fetch("/api/auth/register", {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({ ho_ten: hoTen, email: email, mat_khau: pw })
                });
                const data = await res.json();
                if (!res.ok) {
                    alert(data.detail || "Đăng ký thất bại");
                    btn.disabled = false;
                    btn.innerText = originalText;
                    return;
                }
                alert("Đăng ký tài khoản thành công! Tên đăng nhập của bạn là: " + data.ten_dang_nhap);
                window.location.href = "/login";
            } catch (err) {
                alert("Lỗi kết nối máy chủ: " + err.message);
                btn.disabled = false;
                btn.innerText = originalText;
            }
        });
    }

    const forgotForm = document.getElementById("form-forgot");
    if (forgotForm) {
        forgotForm.addEventListener("submit", async (e) => {
            e.preventDefault();
            const email = document.getElementById("forgot-email")?.value.trim();
            const btn = forgotForm.querySelector("button[type='submit']");
            const originalText = btn.innerText;

            btn.disabled = true;
            btn.innerText = "Đang gửi liên kết...";

            try {
                const res = await fetch("/api/auth/forgot-password", {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({ email: email })
                });
                const data = await res.json();
                if (!res.ok) {
                    alert(data.detail || "Yêu cầu thất bại");
                    btn.disabled = false;
                    btn.innerText = originalText;
                    return;
                }
                alert(data.message);
                if (data.reset_url) {
                    window.location.href = data.reset_url;
                }
            } catch (err) {
                alert("Lỗi kết nối máy chủ: " + err.message);
                btn.disabled = false;
                btn.innerText = originalText;
            }
        });
    }

    const resetForm = document.getElementById("form-reset");
    if (resetForm) {
        const urlParams = new URLSearchParams(window.location.search);
        const tokenFromUrl = urlParams.get("token");

        resetForm.addEventListener("submit", async (e) => {
            e.preventDefault();
            const pw = document.getElementById("reset-password")?.value;
            const confirmPw = document.getElementById("reset-confirm-password")?.value;

            if (pw !== confirmPw) {
                alert("Mật khẩu xác nhận không trùng khớp!");
                return;
            }

            const btn = resetForm.querySelector("button[type='submit']");
            const originalText = btn.innerText;
            btn.disabled = true;
            btn.innerText = "Đang xác nhận...";

            const payload = { mat_khau: pw };
            if (tokenFromUrl) {
                payload.token = tokenFromUrl;
            }

            try {
                const res = await fetch("/api/auth/reset-password", {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify(payload)
                });
                const data = await res.json();
                if (!res.ok) {
                    alert(data.detail || "Đặt lại mật khẩu thất bại");
                    btn.disabled = false;
                    btn.innerText = originalText;
                    return;
                }
                alert(data.message || "Đặt lại mật khẩu thành công!");
                window.location.href = "/login";
            } catch (err) {
                alert("Lỗi kết nối máy chủ: " + err.message);
                btn.disabled = false;
                btn.innerText = originalText;
            }
        });
    }
});
