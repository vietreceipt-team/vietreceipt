// @ts-check
/**
 * server.js inject cấu hình triển khai qua /runtime-config.js trước ES modules.
 * Không đặt token, mật khẩu, participant identifier hoặc secret trong runtime config public.
 */
const runtimeConfig = /** @type {{ dataMode?: "mock" | "api", apiBaseUrl?: string, requestCredentials?: RequestCredentials, studyMode?: "C1_MANUAL" | "C2_VERIFY_ALL" | null, studyOrder?: Array<"C1_MANUAL" | "C2_VERIFY_ALL"> }} */ (globalThis["VIETRECEIPT_CONFIG"] ?? {});

export const APP_CONFIG = Object.freeze({
  dataMode: runtimeConfig.dataMode ?? "api",
  apiBaseUrl: (runtimeConfig.apiBaseUrl ?? "").replace(/\/$/, ""),
  requestCredentials: runtimeConfig.requestCredentials ?? "include",
  studyMode: runtimeConfig.studyMode ?? null,
  studyOrder: Object.freeze(runtimeConfig.studyOrder ?? ["C1_MANUAL", "C2_VERIFY_ALL"]),
});

export const API_BASE_PATH = "/api/v1";
