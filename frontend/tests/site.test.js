import assert from "node:assert/strict";
import { execFileSync } from "node:child_process";
import { existsSync, readFileSync, readdirSync } from "node:fs";
import { createServer as createHttpServer } from "node:http";
import { createConnection } from "node:net";
import { dirname, extname, join, resolve } from "node:path";
import test from "node:test";
import { fileURLToPath } from "node:url";
import { apiPaths, createApplyCorrectionRequest, validateCorrectionValue } from "../assets/js/api.js";
import { CORE_FIELD_TYPES, PUBLIC_RECEIPT_STATUSES } from "../assets/js/common.js";
import { MOCK_RECEIPTS } from "../assets/js/mock-data.js";
import { createRuntimeConfigScript, createStaticServer, resolveRequestPath } from "../server.js";

const root = resolve(dirname(fileURLToPath(import.meta.url)), "..");

const excludedDirectories = new Set([".git", "dist", "node_modules"]);

function walk(directory) {
  return readdirSync(directory, { withFileTypes: true }).flatMap((entry) => {
    if (entry.isDirectory() && excludedDirectories.has(entry.name)) return [];
    const fullPath = join(directory, entry.name);
    return entry.isDirectory() ? walk(fullPath) : [fullPath];
  });
}

test("Backend proxy khóa configured origin với raw absolute-form và protocol-relative targets", async () => {
  const configuredRequests = [];
  let attackerRequests = 0;
  const configuredUpstream = createHttpServer((request, response) => {
    configuredRequests.push({ url: request.url, host: request.headers.host });
    response.writeHead(200, { "content-type": "application/json" });
    response.end('{"proxied":true}');
  });
  const attackerUpstream = createHttpServer((_request, response) => {
    attackerRequests += 1;
    response.writeHead(418, { "content-type": "application/json" });
    response.end('{"proxied":false}');
  });
  await Promise.all([listenOnLoopback(configuredUpstream), listenOnLoopback(attackerUpstream)]);
  const configuredAddress = configuredUpstream.address();
  const attackerAddress = attackerUpstream.address();
  const frontend = createStaticServer(root, {
    backendOrigin: `http://127.0.0.1:${configuredAddress.port}`,
    runtimeConfig: { dataMode: "api" },
  });
  await listenOnLoopback(frontend);
  const frontendAddress = frontend.address();
  const requestTargets = [
    `http://127.0.0.1:${attackerAddress.port}/api/v1/receipts?form=absolute`,
    `//127.0.0.1:${attackerAddress.port}/api/v1/receipts?form=protocol-relative`,
  ];
  try {
    for (const requestTarget of requestTargets) {
      const rawResponse = await sendRawHttpRequest(frontendAddress.port, requestTarget);
      assert.match(rawResponse, /^HTTP\/1\.1 200/);
    }
    assert.equal(attackerRequests, 0);
    assert.deepEqual(configuredRequests, [
      { url: "/api/v1/receipts?form=absolute", host: `127.0.0.1:${configuredAddress.port}` },
      { url: "/api/v1/receipts?form=protocol-relative", host: `127.0.0.1:${configuredAddress.port}` },
    ]);
  } finally {
    await Promise.all([closeServer(frontend), closeServer(configuredUpstream), closeServer(attackerUpstream)]);
  }
});

test("site chỉ chứa source HTML/CSS/JavaScript, không còn TypeScript", () => {
  const sourceFiles = walk(root).filter((file) => !file.includes(`${join(root, ".git")}`));
  assert.equal(sourceFiles.filter((file) => [".ts", ".tsx"].includes(extname(file))).length, 0);
  for (const page of ["index.html", "login/index.html", "upload/index.html", "receipts/index.html", "receipts/detail.html"]) assert.ok(existsSync(join(root, page)), `${page} phải tồn tại`);
});

test("mọi JavaScript file đều parse hợp lệ", () => {
  for (const file of walk(root).filter((path) => extname(path) === ".js")) execFileSync(process.execPath, ["--check", file], { stdio: "pipe" });
});

test("static server giữ route /receipts/{id}", () => {
  assert.equal(resolveRequestPath("/"), "index.html");
  assert.equal(resolveRequestPath("/receipts/"), "receipts/index.html");
  assert.equal(resolveRequestPath("/receipts/11111111-1111-4111-8111-111111111111/"), "receipts/detail.html");
  assert.equal(resolveRequestPath("/assets/js/api.js"), "assets/js/api.js");
});

test("adapter dùng đúng endpoint correction và không có process endpoint", () => {
  const receiptId = "11111111-1111-4111-8111-111111111111";
  assert.equal(apiPaths.fieldCorrection(receiptId, "total_amount"), `/api/v1/receipts/${receiptId}/fields/total_amount/correction`);
  assert.equal(Object.hasOwn(apiPaths, "processReceipt"), false);
});

test("mock data dùng đúng năm public states và năm canonical fields", () => {
  assert.deepEqual(PUBLIC_RECEIPT_STATUSES, ["UPLOADED", "PROCESSING", "NEEDS_REVIEW", "VERIFIED", "FAILED"]);
  assert.equal(MOCK_RECEIPTS.some((receipt) => receipt.status === "QUEUED"), false);
  for (const receipt of MOCK_RECEIPTS.filter((item) => Object.keys(item.fields).length)) assert.deepEqual(Object.keys(receipt.fields), CORE_FIELD_TYPES);
});

test("correction payload giữ type canonical và optimistic concurrency token", () => {
  validateCorrectionValue("total_amount", 325000, "PRESENT");
  assert.throws(() => validateCorrectionValue("total_amount", "325000", "PRESENT"));
  const request = createApplyCorrectionRequest({ field_name: "invoice_id", updated_at: "2026-08-10T08:30:00Z" }, "00018427", "PRESENT");
  assert.deepEqual(request, { operation: "APPLY", value: "00018427", value_status: "PRESENT", expected_updated_at: "2026-08-10T08:30:00Z" });
});

test("HTML shell dùng shared stylesheet và ES modules", () => {
  const html = readFileSync(join(root, "receipts/index.html"), "utf8");
  assert.match(html, /assets\/css\/tailwind\.css/);
  assert.match(html, /type="module" src="\/assets\/js\/receipts-v2\.js"/);
});


test("mọi app shell nạp runtime config trước ES module", () => {
  for (const page of ["login/index.html", "upload/index.html", "receipts/index.html", "receipts/detail.html"]) {
    const html = readFileSync(join(root, page), "utf8");
    assert.ok(html.indexOf('/runtime-config.js') >= 0, `${page} thiếu runtime config`);
    assert.ok(html.indexOf('/runtime-config.js') < html.indexOf('type="module"'), `${page} phải nạp config trước module`);
  }
  assert.match(createRuntimeConfigScript({ dataMode: "api" }), /"dataMode":"api"/);
  assert.throws(() => createRuntimeConfigScript({ dataMode: "invalid" }));
});

function listenOnLoopback(server) {
  return new Promise((resolvePromise) => server.listen(0, "127.0.0.1", resolvePromise));
}

function closeServer(server) {
  return new Promise((resolvePromise, rejectPromise) => server.close((error) => error ? rejectPromise(error) : resolvePromise()));
}

function sendRawHttpRequest(port, requestTarget) {
  return new Promise((resolvePromise, rejectPromise) => {
    const chunks = [];
    const socket = createConnection({ host: "127.0.0.1", port }, () => {
      socket.write(`GET ${requestTarget} HTTP/1.1\r\nHost: frontend.test\r\nConnection: close\r\n\r\n`);
    });
    socket.setEncoding("utf8");
    socket.on("data", (chunk) => chunks.push(chunk));
    socket.on("end", () => resolvePromise(chunks.join("")));
    socket.on("error", rejectPromise);
  });
}

test("API mode runtime chuyển request frontend qua Backend proxy", async () => {
  let upstreamPath = null;
  const upstream = createHttpServer((request, response) => {
    upstreamPath = request.url;
    response.writeHead(200, { "content-type": "application/json", "x-request-id": "proxy-smoke-request" });
    response.end('{"items":[],"page":1,"page_size":1,"total_items":0,"total_pages":0}');
  });
  await new Promise((resolvePromise) => upstream.listen(0, "127.0.0.1", resolvePromise));
  const upstreamAddress = upstream.address();
  const frontend = createStaticServer(root, {
    backendOrigin: `http://127.0.0.1:${upstreamAddress.port}`,
    runtimeConfig: { dataMode: "api" },
  });
  await new Promise((resolvePromise) => frontend.listen(0, "127.0.0.1", resolvePromise));
  const frontendAddress = frontend.address();
  try {
    const configResponse = await fetch(`http://127.0.0.1:${frontendAddress.port}/runtime-config.js`);
    assert.equal(configResponse.status, 200);
    assert.match(await configResponse.text(), /"dataMode":"api"/);
    const apiResponse = await fetch(`http://127.0.0.1:${frontendAddress.port}/api/v1/receipts?page=1&page_size=1`);
    assert.equal(apiResponse.status, 200);
    assert.equal(apiResponse.headers.get("x-request-id"), "proxy-smoke-request");
    assert.equal(upstreamPath, "/api/v1/receipts?page=1&page_size=1");
    const v2Response = await fetch(`http://127.0.0.1:${frontendAddress.port}/api/v2/receipts?limit=2`);
    assert.equal(v2Response.status, 200);
    assert.equal(v2Response.headers.get("x-request-id"), "proxy-smoke-request");
    assert.equal(upstreamPath, "/api/v2/receipts?limit=2");
  } finally {
    await Promise.all([
      new Promise((resolvePromise, rejectPromise) => frontend.close((error) => error ? rejectPromise(error) : resolvePromise())),
      new Promise((resolvePromise, rejectPromise) => upstream.close((error) => error ? rejectPromise(error) : resolvePromise())),
    ]);
  }
});

test("API V2 thiếu backend trả 503 rõ ràng", async () => {
  const frontend = createStaticServer(root, { backendOrigin: "", runtimeConfig: { dataMode: "api" } });
  await listenOnLoopback(frontend);
  try {
    const response = await fetch(`http://127.0.0.1:${frontend.address().port}/api/v2/receipts`);
    assert.equal(response.status, 503);
    assert.equal((await response.json()).error.code, "BACKEND_NOT_CONFIGURED");
  } finally { await closeServer(frontend); }
});
