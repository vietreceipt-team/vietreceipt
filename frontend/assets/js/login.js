import { renderNavigation, setBusy } from "./common.js";

renderNavigation();

document.querySelector("#main-content").innerHTML = `<div class="relative min-h-[calc(100dvh-56px)] overflow-hidden bg-slate-950 px-4 py-10 sm:px-6">
  <div class="pointer-events-none absolute -left-32 top-16 size-96 rounded-full bg-teal-500/15 blur-3xl"></div>
  <div class="pointer-events-none absolute -right-32 bottom-0 size-[30rem] rounded-full bg-cyan-400/10 blur-3xl"></div>
  <div class="relative mx-auto grid min-h-[calc(100dvh-148px)] max-w-5xl items-center gap-12 lg:grid-cols-[1.05fr_0.95fr]">
    <section class="hidden lg:block">
      <p class="mb-6 inline-flex items-center gap-2 rounded-full border border-white/10 bg-white/5 px-3 py-1.5 text-xs font-bold uppercase tracking-[0.16em] text-teal-200">Human-in-the-Loop</p>
      <h1 class="max-w-xl text-5xl font-bold leading-[1.05] tracking-[-0.045em] text-white">Mỗi hóa đơn rõ ràng. Mỗi dữ liệu đáng tin.</h1>
      <p class="mt-6 max-w-lg text-lg leading-8 text-slate-400">Kiểm tra kết quả OCR, sửa đúng chỗ cần thiết và đưa dữ liệu hóa đơn vào quy trình của bạn.</p>
      <div class="mt-10 flex items-center gap-8 text-sm text-slate-400">
        <span><strong class="block text-lg text-white">Dữ liệu gốc</strong> luôn được giữ nguyên</span><span class="h-10 w-px bg-white/10"></span><span><strong class="block text-lg text-white">Người kiểm duyệt</strong> quyết định giá trị cuối</span>
      </div>
    </section>
    <section class="mx-auto w-full max-w-md rounded-3xl border border-white/10 bg-white p-6 shadow-2xl shadow-black/30 sm:p-8">
      <div class="mb-8">
        <div class="mb-5 grid size-11 place-items-center rounded-2xl bg-teal-800 text-lg font-black text-white lg:hidden">V</div>
        <p class="text-sm font-bold text-teal-700">Chào mừng trở lại</p>
        <h2 class="mt-2 text-3xl font-bold tracking-[-0.035em] text-slate-950">Đăng nhập VietReceipt</h2>
        <p class="mt-2 text-sm leading-6 text-slate-500">Tiếp tục không gian xử lý hóa đơn của bạn.</p>
      </div>
      <form id="login-form" class="space-y-5">
        <label class="block"><span class="mb-2 block text-sm font-bold text-slate-700">Email công việc</span><input type="email" name="email" value="reviewer@vietreceipt.vn" autocomplete="email" required class="h-12 w-full rounded-xl border border-slate-200 bg-white px-4 text-sm text-slate-900 outline-none transition placeholder:text-slate-400 focus:border-teal-700 focus:ring-4 focus:ring-teal-700/10" placeholder="ban@congty.vn"></label>
        <label class="block"><span class="mb-2 block text-sm font-bold text-slate-700">Mật khẩu</span><input type="password" name="password" value="vietreceipt-demo" autocomplete="current-password" required minlength="8" class="h-12 w-full rounded-xl border border-slate-200 bg-white px-4 text-sm text-slate-900 outline-none transition placeholder:text-slate-400 focus:border-teal-700 focus:ring-4 focus:ring-teal-700/10" placeholder="Tối thiểu 8 ký tự"></label>
        <div class="flex items-center justify-between gap-4 text-sm"><label class="flex items-center gap-2 font-medium text-slate-600"><input type="checkbox" checked class="size-4 rounded border-slate-300 accent-teal-700">Ghi nhớ tôi</label><button type="button" class="font-bold text-teal-700 hover:text-teal-900">Quên mật khẩu?</button></div>
        <button id="login-submit" type="submit" class="flex h-12 w-full items-center justify-center rounded-xl bg-teal-800 px-4 text-sm font-bold text-white shadow-sm shadow-teal-950/20 transition hover:bg-teal-900 focus:outline-none focus-visible:ring-2 focus-visible:ring-teal-700 focus-visible:ring-offset-2 disabled:opacity-70">Đăng nhập</button>
      </form>
      <p class="mt-6 border-t border-slate-100 pt-5 text-center text-xs leading-5 text-slate-400">Đây là giao diện demo. Backend hiện chưa expose auth trong runtime router nên không có dữ liệu đăng nhập thật được gửi đi.</p>
    </section>
  </div>
</div>`;

document.querySelector("#login-form").addEventListener("submit", (event) => {
  event.preventDefault();
  const button = document.querySelector("#login-submit");
  setBusy(button, true, "Đang mở không gian...", "Đăng nhập");
  window.setTimeout(() => { window.location.assign("/upload/"); }, 450);
});
