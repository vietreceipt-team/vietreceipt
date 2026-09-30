// @ts-check
import { createReadStream, existsSync, readFileSync, statSync } from "node:fs";
import { createServer, request as httpRequest } from "node:http";
import { request as httpsRequest } from "node:https";
import { dirname, extname, isAbsolute, join, normalize, relative, resolve } from "node:path";
import { fileURLToPath, pathToFileURL } from "node:url";

const projectRoot = dirname(fileURLToPath(import.meta.url));
const contentTypes = {
  ".css": "text/css; charset=utf-8", ".html": "text/html; charset=utf-8", ".js": "text/javascript; charset=utf-8", ".mjs": "text/javascript; charset=utf-8",
  ".json": "application/json; charset=utf-8", ".png": "image/png", ".svg": "image/svg+xml", ".woff2": "font/woff2",
};
const DATA_MODES = new Set(["mock", "api"]);
const STUDY_MODES = new Set(["C1_MANUAL", "C2_VERIFY_ALL"]);

function parseStudyOrder(value) {
  const order = Array.isArray(value) ? value : String(value).split(",");
  const normalized = order.map((mode) => String(mode).trim()).filter(Boolean);
  if (normalized.length !== 2 || new Set(normalized).size !== 2 || normalized.some((mode) => !STUDY_MODES.has(mode))) {
    throw new Error("FRONTEND_STUDY_ORDER phải chứa đúng C1_MANUAL và C2_VERIFY_ALL, mỗi mode một lần.");
  }
  return normalized;
}

export function createRuntimeConfigScript({
  dataMode = process.env.FRONTEND_DATA_MODE ?? "api",
  apiBaseUrl = process.env.FRONTEND_API_BASE_URL ?? "",
  requestCredentials = process.env.FRONTEND_REQUEST_CREDENTIALS ?? "include",
  studyMode = process.env.FRONTEND_STUDY_MODE ?? "",
  studyOrder = process.env.FRONTEND_STUDY_ORDER ?? "C1_MANUAL,C2_VERIFY_ALL",
} = {}) {
  if (!DATA_MODES.has(dataMode)) throw new Error(`FRONTEND_DATA_MODE không hợp lệ: ${dataMode}`);
  if (studyMode !== "" && !STUDY_MODES.has(studyMode)) throw new Error(`FRONTEND_STUDY_MODE không hợp lệ: ${studyMode}`);
  const normalizedOrder = parseStudyOrder(studyOrder);
  if (studyMode && normalizedOrder[0] !== studyMode) throw new Error("FRONTEND_STUDY_MODE phải đứng đầu FRONTEND_STUDY_ORDER.");
  const config = {
    dataMode,
    apiBaseUrl: apiBaseUrl.replace(/\/$/, ""),
    requestCredentials,
    studyMode: studyMode || null,
    studyOrder: normalizedOrder,
  };
  return `globalThis.VIETRECEIPT_CONFIG = Object.freeze(${JSON.stringify(config)});\n`;
}

export function resolveRequestPath(pathname) {
  const decoded = decodeURIComponent(pathname).replaceAll("\\", "/");
  if (decoded === "/") return "index.html";
  if (/^\/receipts\/[^/]+\/?$/.test(decoded) && !decoded.endsWith("detail.html")) return "receipts/detail.html";
  const clean = decoded.replace(/^\/+/, "");
  return decoded.endsWith("/") ? `${clean}index.html` : clean;
}

export function proxyApiRequest(request, response, backendOrigin, requestUrl = new URL(request.url ?? "/", "http://frontend.invalid")) {
  let target;
  try {
    const configuredOrigin = new URL(backendOrigin);
    if (!["http:", "https:"].includes(configuredOrigin.protocol)) throw new Error("Unsupported Backend protocol.");
    target = new URL(`${requestUrl.pathname}${requestUrl.search}`, configuredOrigin.origin);
    if (target.origin !== configuredOrigin.origin) throw new Error("Backend proxy origin drifted from configuration.");
  } catch { response.writeHead(502, { "content-type": "application/json" }); response.end('{"error":{"code":"PROXY_CONFIG_ERROR","message":"Backend proxy is not configured correctly."}}'); return; }
  const transport = target.protocol === "https:" ? httpsRequest : httpRequest;
  const headers = { ...request.headers, host: target.host, "x-forwarded-host": request.headers.host ?? "", "x-forwarded-proto": "http" };
  const upstream = transport(target, { method: request.method, headers }, (upstreamResponse) => {
    response.writeHead(upstreamResponse.statusCode ?? 502, upstreamResponse.headers);
    upstreamResponse.pipe(response);
  });
  upstream.on("error", () => {
    if (response.headersSent) return response.destroy();
    response.writeHead(502, { "content-type": "application/json; charset=utf-8" });
    response.end('{"error":{"code":"BACKEND_UNAVAILABLE","message":"Không thể kết nối Backend."}}');
  });
  request.pipe(upstream);
}

export function createStaticServer(root = projectRoot, {
  backendOrigin = process.env.BACKEND_API_ORIGIN ?? "",
  runtimeConfig = /** @type {{ dataMode?: string }} */ ({}),
} = {}) {
  const absoluteRoot = resolve(root);
  const runtimeConfigScript = createRuntimeConfigScript(runtimeConfig);
  const useLegacyMockPages = (runtimeConfig.dataMode ?? process.env.FRONTEND_DATA_MODE ?? "api") === "mock";
  return createServer((request, response) => {
    try {
      const requestUrl = new URL(request.url ?? "/", "http://localhost");
      if (requestUrl.pathname === "/runtime-config.js") {
        response.writeHead(200, { "content-type": "text/javascript; charset=utf-8", "cache-control": "no-store" });
        response.end(runtimeConfigScript);
        return;
      }
      if (/^\/api\/v[12]\//.test(requestUrl.pathname)) {
        if (backendOrigin) return proxyApiRequest(request, response, backendOrigin, requestUrl);
        response.writeHead(503, { "content-type": "application/json; charset=utf-8" });
        response.end('{"error":{"code":"BACKEND_NOT_CONFIGURED","message":"Chưa cấu hình BACKEND_API_ORIGIN cho frontend."}}');
        return;
      }
      const relativePath = normalize(resolveRequestPath(requestUrl.pathname));
      const filePath = resolve(join(absoluteRoot, relativePath));
      const pathFromRoot = relative(absoluteRoot, filePath);
      const outsideRoot = pathFromRoot.startsWith("..") || isAbsolute(pathFromRoot);
      if (outsideRoot || !existsSync(filePath) || !statSync(filePath).isFile()) {
        response.writeHead(404, { "content-type": "text/plain; charset=utf-8" });
        response.end("Không tìm thấy tài nguyên.");
        return;
      }
      if (useLegacyMockPages && ["upload/index.html", "receipts/index.html", "receipts/detail.html"].includes(relativePath.replaceAll("\\", "/"))) {
        const html = readFileSync(filePath, "utf8").replaceAll("-v2.js", ".js");
        response.writeHead(200, { "content-type": "text/html; charset=utf-8", "cache-control": "no-cache" });
        response.end(html);
        return;
      }
      response.writeHead(200, { "content-type": contentTypes[extname(filePath).toLowerCase()] ?? "application/octet-stream", "cache-control": extname(filePath) === ".html" ? "no-cache" : "public, max-age=3600" });
      createReadStream(filePath).pipe(response);
    } catch {
      response.writeHead(400, { "content-type": "text/plain; charset=utf-8" });
      response.end("Yêu cầu không hợp lệ.");
    }
  });
}

function argumentValue(name) {
  const index = process.argv.indexOf(name);
  return index >= 0 ? process.argv[index + 1] : undefined;
}

const isMain = process.argv[1] && pathToFileURL(resolve(process.argv[1])).href === import.meta.url;
if (isMain) {
  const port = Number(argumentValue("--port") ?? process.env.PORT ?? 3000);
  const hostname = argumentValue("--hostname") ?? argumentValue("--host") ?? process.env.HOST ?? "127.0.0.1";
  createStaticServer().listen(port, hostname, () => console.log(`VietReceipt đang chạy tại http://${hostname}:${port}`));
}
