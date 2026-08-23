/**
 * Chuyển dataMode thành "api" khi Backend đã sẵn sàng.
 * apiBaseUrl để trống sẽ gọi cùng origin tại /api/v1 (khuyến nghị).
 * Không đặt token, mật khẩu hoặc secret trong file public này.
 */
const runtimeConfig = globalThis.VIETRECEIPT_CONFIG ?? {};

export const APP_CONFIG = Object.freeze({
  dataMode: runtimeConfig.dataMode ?? "mock",
  apiBaseUrl: (runtimeConfig.apiBaseUrl ?? "").replace(/\/$/, ""),
  requestCredentials: runtimeConfig.requestCredentials ?? "include",
});

export const API_BASE_PATH = "/api/v1";
