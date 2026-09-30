import assert from "node:assert/strict";
import { existsSync, readFileSync } from "node:fs";
import { dirname, join, resolve } from "node:path";
import test from "node:test";
import { fileURLToPath } from "node:url";
import { MOCK_RECEIPTS } from "../assets/js/mock-data.js";

const root = resolve(dirname(fileURLToPath(import.meta.url)), "..");

test("mock review dùng fixture ảnh thật đã merge ở W2", () => {
  assert.ok(existsSync(join(root, "assets/fixtures/R001.jpg")));
  for (const receipt of MOCK_RECEIPTS.filter((item) => Object.keys(item.fields).length)) assert.equal(receipt.image_url, "/assets/fixtures/R001.jpg");
});

test("frontend không tái dựng receipt hoặc tự sinh evidence khi thiếu image_url", () => {
  const source = readFileSync(join(root, "assets/js/receipt-detail.js"), "utf8");
  assert.doesNotMatch(source, /receipt-edge|HÓA ĐƠN BÁN HÀNG|Cà phê rang xay/);
  assert.match(source, /Frontend không tái dựng ảnh từ OCR\/KIE/);
});
