import { renderNavigation } from "./common.js";
renderNavigation();
document.querySelector("#main-content").innerHTML = `<div class="v2-container"><div class="v2-card"><p class="eyebrow">Bản thử nghiệm</p><h1 class="text-2xl font-bold">Chưa có đăng nhập production</h1><p class="mt-3 text-slate-600">Backend V2 hiện dùng người dùng demo cố định. Trang này không xác thực tài khoản và không gửi mật khẩu.</p><a class="v2-button mt-5" href="/upload/">Mở khu vực hóa đơn</a></div></div>`;
