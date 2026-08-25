// @ts-check
/**
 * server.js inject cấu hình triển khai qua /runtime-config.js trước ES modules.
 * Local mặc định mock; Docker đặt FRONTEND_DATA_MODE=api và gọi cùng origin /api/v1.
 * Không đặt token, mật khẩu hoặc secret trong runtime config public.
 */
const runtimeConfig = /** @type {{ dataMode?: "mock" | "api", apiBaseUrl?: string, requestCredentials?: RequestCredentials }} */ (globalThis["VIETRECEIPT_CONFIG"] ?? {});

export const APP_CONFIG = Object.freeze({
  dataMode: runtimeConfig.dataMode ?? "mock",
  apiBaseUrl: (runtimeConfig.apiBaseUrl ?? "").replace(/\/$/, ""),
  requestCredentials: runtimeConfig.requestCredentials ?? "include",
});

export const API_BASE_PATH = "/api/v1";
