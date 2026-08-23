import assert from "node:assert/strict";
import { execFileSync } from "node:child_process";
import { existsSync, readFileSync, readdirSync } from "node:fs";
import { dirname, extname, join, resolve } from "node:path";
import test from "node:test";
import { fileURLToPath } from "node:url";
import { apiPaths, createApplyCorrectionRequest, validateCorrectionValue } from "../assets/js/api.js";
import { CORE_FIELD_TYPES, PUBLIC_RECEIPT_STATUSES } from "../assets/js/common.js";
import { MOCK_RECEIPTS } from "../assets/js/mock-data.js";
import { resolveRequestPath } from "../server.js";

const root = resolve(dirname(fileURLToPath(import.meta.url)), "..");

function walk(directory) {
  return readdirSync(directory, { withFileTypes: true }).flatMap((entry) => {
    const fullPath = join(directory, entry.name);
    return entry.isDirectory() ? walk(fullPath) : [fullPath];
  });
}

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
  assert.match(html, /type="module" src="\/assets\/js\/receipts\.js"/);
});
