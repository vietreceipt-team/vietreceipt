import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";

async function render(pathname = "/receipts") {
  const workerUrl = new URL("../dist/server/index.js", import.meta.url);
  workerUrl.searchParams.set("test", `${process.pid}-${Date.now()}`);
  const { default: worker } = await import(workerUrl.href);

  return worker.fetch(
    new Request(`http://localhost${pathname}`, {
      headers: { accept: "text/html" },
    }),
    {
      ASSETS: {
        fetch: async () => new Response("Not found", { status: 404 }),
      },
    },
    {
      waitUntil() {},
      passThroughOnException() {},
    },
  );
}

test("server-renders the receipt dashboard", async () => {
  const response = await render();
  assert.equal(response.status, 200);
  assert.match(response.headers.get("content-type") ?? "", /^text\/html\b/i);

  const html = await response.text();
  assert.match(html, /<html lang="vi">/i);
  assert.match(html, /VietReceipt/);
  assert.match(html, /Hóa đơn/);
  assert.match(html, /Tải hóa đơn/);
  assert.match(html, /Danh sách hóa đơn/);
});

test("keeps visual density and upload scope explicit", async () => {
  const [dashboard, navigation, thumbnail, upload, mockData] = await Promise.all([
    readFile(new URL("../app/receipts/page.tsx", import.meta.url), "utf8"),
    readFile(new URL("../components/navigation.tsx", import.meta.url), "utf8"),
    readFile(new URL("../components/receipt-thumbnail.tsx", import.meta.url), "utf8"),
    readFile(new URL("../app/upload/page.tsx", import.meta.url), "utf8"),
    readFile(new URL("../data/mock-receipts.ts", import.meta.url), "utf8"),
  ]);

  assert.match(navigation, /h-14 border-b/);
  assert.match(dashboard, /space-y-4 px-5 py-5/);
  assert.match(dashboard, /text-\[32px\]/);
  assert.match(dashboard, /min-h-20/);
  assert.match(dashboard, /h-10 border-b/);
  assert.match(dashboard, /tabular-nums/);
  assert.match(dashboard, /lucide-react/);
  assert.match(thumbnail, /onError=/);
  assert.match(upload, /image\/jpeg/);
  assert.match(upload, /image\/png/);
  assert.match(upload, /image\/webp/);
  assert.doesNotMatch(upload, /application\/pdf/i);
  assert.doesNotMatch(mockData, /\.pdf\b/i);
});

test("mirrors the Backend and KIE v1.3 contract", async () => {
  const [receiptTypes, mockData, apiContract] = await Promise.all([
    readFile(new URL("../types/receipt.ts", import.meta.url), "utf8"),
    readFile(new URL("../data/mock-receipts.ts", import.meta.url), "utf8"),
    readFile(new URL("../lib/vietreceipt-api.ts", import.meta.url), "utf8"),
  ]);

  for (const fieldType of [
    "merchant_name",
    "receipt_date",
    "total_amount",
    "invoice_id",
    "merchant_address",
  ]) {
    assert.match(receiptTypes, new RegExp(`"${fieldType}"`));
  }

  for (const valueStatus of ["PRESENT", "NOT_PRESENT", "UNREADABLE", "AMBIGUOUS", "UNKNOWN"]) {
    assert.match(receiptTypes, new RegExp(`"${valueStatus}"`));
  }

  assert.match(receiptTypes, /machine_needs_review/);
  assert.match(receiptTypes, /effective_needs_review/);
  assert.match(receiptTypes, /expected_updated_at/);
  assert.doesNotMatch(receiptTypes, /LIKELY_CORRECT|valueStatus|needsReview:/);

  assert.match(mockData, /normalized_value: null/);
  assert.match(mockData, /review_reasons: \["LOW_CONFIDENCE"\]/);
  assert.doesNotMatch(mockData, /"Không nhận diện được"/);

  assert.match(apiContract, /\/api\/v1/);
  assert.match(apiContract, /\/process/);
  assert.match(apiContract, /\/fields\/\$\{encodeId\(fieldId\)\}/);
  assert.match(apiContract, /createFieldCorrectionRequest/);
});

test("renders the effective review contract on receipt detail", async () => {
  const response = await render("/receipts/11111111-1111-4111-8111-111111111111");
  assert.equal(response.status, 200);

  const html = await response.text();
  assert.match(html, /Đối chiếu thông tin/);
  assert.match(html, /Cảnh báo hiện tại dùng effective_needs_review/);
  assert.match(html, /Không chuẩn hóa an toàn/);
  assert.match(html, /Giá trị này không tự động trở thành effective value/);
});
