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

    // Form Submissions with feedback and transitions
    const loginForm = document.getElementById("form-login");
    if (loginForm) {
        loginForm.addEventListener("submit", (e) => {
            e.preventDefault();
            const btn = loginForm.querySelector("button[type='submit']");
            btn.disabled = true;
            btn.innerText = "Đang đăng nhập...";
            setTimeout(() => {
                window.location.href = "./dashboard.html";
            }, 600);
        });
    }

    const registerForm = document.getElementById("form-register");
    if (registerForm) {
        registerForm.addEventListener("submit", (e) => {
            e.preventDefault();
            const pw = document.getElementById("reg-password")?.value;
            const confirmPw = document.getElementById("reg-confirm-password")?.value;
            if (pw !== confirmPw) {
                alert("Mật khẩu xác nhận không trùng khớp!");
                return;
            }
            const btn = registerForm.querySelector("button[type='submit']");
            btn.disabled = true;
            btn.innerText = "Đang tạo tài khoản...";
            setTimeout(() => {
                alert("Tạo tài khoản thành công! Đang chuyển đến màn hình Đăng nhập.");
                window.location.href = "./login.html";
            }, 600);
        });
    }

    const forgotForm = document.getElementById("form-forgot");
    if (forgotForm) {
        forgotForm.addEventListener("submit", (e) => {
            e.preventDefault();
            const btn = forgotForm.querySelector("button[type='submit']");
            btn.disabled = true;
            btn.innerText = "Đang gửi liên kết...";
            setTimeout(() => {
                alert("Liên kết đặt lại mật khẩu đã được gửi đến email! Đang mở màn hình đặt mật khẩu mới.");
                window.location.href = "./reset-password.html";
            }, 600);
        });
    }

    const resetForm = document.getElementById("form-reset");
    if (resetForm) {
        resetForm.addEventListener("submit", (e) => {
            e.preventDefault();
            const pw = document.getElementById("reset-password")?.value;
            const confirmPw = document.getElementById("reset-confirm-password")?.value;
            if (pw !== confirmPw) {
                alert("Mật khẩu xác nhận không trùng khớp!");
                return;
            }
            const btn = resetForm.querySelector("button[type='submit']");
            btn.disabled = true;
            btn.innerText = "Đang xác nhận...";
            setTimeout(() => {
                alert("Đặt lại mật khẩu thành công! Đang chuyển đến màn hình Đăng nhập.");
                window.location.href = "./login.html";
            }, 600);
        });
    }
});
