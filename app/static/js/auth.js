// Auth logic for Login / Register / Logout
document.addEventListener("DOMContentLoaded", () => {
    const loginForm = document.getElementById("login-form");
    const registerForm = document.getElementById("register-form");
    const toggleToRegister = document.getElementById("toggle-to-register");
    const toggleToLogin = document.getElementById("toggle-to-login");
    const loginCard = document.getElementById("login-card");
    const registerCard = document.getElementById("register-card");
    const loginAlert = document.getElementById("login-alert");

    // Toggle forms
    if (toggleToRegister && toggleToLogin) {
        toggleToRegister.addEventListener("click", (e) => {
            e.preventDefault();
            loginCard.classList.add("hidden");
            registerCard.classList.remove("hidden");
        });
        toggleToLogin.addEventListener("click", (e) => {
            e.preventDefault();
            registerCard.classList.add("hidden");
            loginCard.classList.remove("hidden");
        });
    }

    // Handle Login
    if (loginForm) {
        loginForm.addEventListener("submit", async (e) => {
            e.preventDefault();
            loginAlert.classList.add("hidden");

            const username = document.getElementById("username").value.trim();
            const password = document.getElementById("password").value;

            if (!username || !password) {
                showToast("Vui lòng nhập đầy đủ tên đăng nhập và mật khẩu", "warning");
                return;
            }

            const submitBtn = loginForm.querySelector("button[type='submit']");
            submitBtn.disabled = true;
            submitBtn.innerText = "Đang xác thực...";

            try {
                const res = await API.request("/api/auth/login", {
                    method: "POST",
                    body: JSON.stringify({
                        ten_dang_nhap: username,
                        mat_khau: password
                    })
                });

                API.setSession(res);
                showToast("Đăng nhập thành công! Đang chuyển hướng...", "success");
                setTimeout(() => {
                    window.location.href = "/dashboard";
                }, 800);
            } catch (err) {
                loginAlert.classList.remove("hidden");
                loginAlert.innerText = err.message;
                showToast(err.message, "error");
            } finally {
                submitBtn.disabled = false;
                submitBtn.innerText = "Đăng nhập";
            }
        });
    }

    // Handle Register
    if (registerForm) {
        registerForm.addEventListener("submit", async (e) => {
            e.preventDefault();
            const username = document.getElementById("reg-username").value.trim();
            const fullName = document.getElementById("reg-fullname").value.trim();
            const email = document.getElementById("reg-email").value.trim() || null;
            const phone = document.getElementById("reg-phone").value.trim() || null;
            const password = document.getElementById("reg-password").value;
            const confirmPassword = document.getElementById("reg-confirm-password").value;

            if (password !== confirmPassword) {
                showToast("Mật khẩu xác nhận không trùng khớp!", "warning");
                return;
            }

            if (password.length < 8) {
                showToast("Mật khẩu phải có tối thiểu 8 ký tự!", "warning");
                return;
            }

            const submitBtn = registerForm.querySelector("button[type='submit']");
            submitBtn.disabled = true;
            submitBtn.innerText = "Đang tạo tài khoản...";

            try {
                await API.request("/api/auth/register", {
                    method: "POST",
                    body: JSON.stringify({
                        ten_dang_nhap: username,
                        ho_ten: fullName,
                        email: email,
                        so_dien_thoai: phone,
                        mat_khau: password,
                        ma_vai_tro: 3 // Staff
                    })
                });

                showToast("Đăng ký tài khoản thành công! Vui lòng đăng nhập.", "success");
                registerForm.reset();
                registerCard.classList.add("hidden");
                loginCard.classList.remove("hidden");
            } catch (err) {
                showToast(err.message, "error");
            } finally {
                submitBtn.disabled = false;
                submitBtn.innerText = "Tạo tài khoản";
            }
        });
    }
});

function logout() {
    API.clearSession();
    window.location.href = "/login";
}
