import { createReadStream, existsSync, statSync } from "node:fs";
import { createServer, request as httpRequest } from "node:http";
import { request as httpsRequest } from "node:https";
import { dirname, extname, isAbsolute, join, normalize, relative, resolve } from "node:path";
import { fileURLToPath, pathToFileURL } from "node:url";

const projectRoot = dirname(fileURLToPath(import.meta.url));
const contentTypes = {
  ".css": "text/css; charset=utf-8", ".html": "text/html; charset=utf-8", ".js": "text/javascript; charset=utf-8",
  ".json": "application/json; charset=utf-8", ".png": "image/png", ".svg": "image/svg+xml", ".woff2": "font/woff2",
};

export function resolveRequestPath(pathname) {
  const decoded = decodeURIComponent(pathname).replaceAll("\\", "/");
  if (decoded === "/") return "index.html";
  if (/^\/receipts\/[^/]+\/?$/.test(decoded) && !decoded.endsWith("detail.html")) return "receipts/detail.html";
  const clean = decoded.replace(/^\/+/, "");
  return decoded.endsWith("/") ? `${clean}index.html` : clean;
}

export function proxyApiRequest(request, response, backendOrigin) {
  let target;
  try { target = new URL(request.url ?? "/", backendOrigin.endsWith("/") ? backendOrigin : `${backendOrigin}/`); }
  catch { response.writeHead(502, { "content-type": "application/json" }); response.end('{"error":{"code":"PROXY_CONFIG_ERROR","message":"Backend proxy is not configured correctly."}}'); return; }
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

export function createStaticServer(root = projectRoot, { backendOrigin = process.env.BACKEND_API_ORIGIN ?? "" } = {}) {
  const absoluteRoot = resolve(root);
  return createServer((request, response) => {
    try {
      const requestUrl = new URL(request.url ?? "/", "http://localhost");
      if (backendOrigin && requestUrl.pathname.startsWith("/api/v1/")) return proxyApiRequest(request, response, backendOrigin);
      const relativePath = normalize(resolveRequestPath(requestUrl.pathname));
      const filePath = resolve(join(absoluteRoot, relativePath));
      const pathFromRoot = relative(absoluteRoot, filePath);
      const outsideRoot = pathFromRoot.startsWith("..") || isAbsolute(pathFromRoot);
      if (outsideRoot || !existsSync(filePath) || !statSync(filePath).isFile()) {
        response.writeHead(404, { "content-type": "text/plain; charset=utf-8" });
        response.end("Không tìm thấy tài nguyên.");
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
