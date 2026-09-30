import { expect, test } from "@playwright/test";
import { CORE_FIELD_TYPES } from "../assets/js/common.js";
import { MOCK_RECEIPTS, RECEIPT_IDS } from "../assets/js/mock-data.js";

const C1_ORIGIN = "http://127.0.0.1:3101";
const C2_ORIGIN = "http://127.0.0.1:3102";
const MOCK_STORAGE_KEY = "vietreceipt:mock-receipts:v1";

function allPresentReceipts() {
  const receipts = structuredClone(MOCK_RECEIPTS);
  const receipt = receipts.find((item) => item.receipt_id === RECEIPT_IDS.review);
  const amount = receipt.fields.total_amount;
  amount.normalized_value = 325000;
  amount.value_status = "PRESENT";
  amount.corrected_value = null;
  amount.corrected_status = null;
  amount.has_correction = false;
  amount.effective_value = 325000;
  amount.effective_status = "PRESENT";
  amount.machine_needs_review = false;
  amount.effective_needs_review = false;
  amount.review_reasons = [];
  amount.review_policy_version = null;
  return receipts;
}

async function prepareStudyPage(page, receipts = MOCK_RECEIPTS) {
  await page.addInitScript(({ mockReceipts, storageKey }) => {
    sessionStorage.clear();
    sessionStorage.setItem(storageKey, JSON.stringify(mockReceipts));
    globalThis.__vietreceiptReviewEvents = [];
    globalThis.addEventListener("vietreceipt:review-event", (event) => {
      globalThis.__vietreceiptReviewEvents.push(event.detail);
    });
  }, { mockReceipts: receipts, storageKey: MOCK_STORAGE_KEY });
}

function receiptUrl(origin, receiptId) {
  return `${origin}/receipts/${receiptId}/`;
}

test("C1 render trang thật với năm field trống và không lộ machine output trong DOM", async ({ page }) => {
  await prepareStudyPage(page);
  await page.goto(receiptUrl(C1_ORIGIN, RECEIPT_IDS.review));

  await expect(page.locator("#review-mode-badge")).toHaveText("C1 · Nhập thủ công");
  await expect(page.locator("#field-list [data-field-card]")).toHaveCount(5);
  await expect(page.locator("#field-list [data-field-input]")).toHaveCount(5);
  const values = await page.locator("#field-list [data-field-input]").evaluateAll((inputs) => inputs.map((input) => input.value));
  expect(values).toEqual(["", "", "", "", ""]);
  await expect(page.locator("#verify-button")).toBeDisabled();
  await expect(page.locator("[data-block-id]")).toHaveCount(0);

  const html = await page.locator("body").innerHTML();
  for (const forbidden of [
    "CỬA HÀNG TIỆN LỢI AN NAM",
    "28 Nguyễn Huệ, P. Bến Nghé, Q.1, TP.HCM",
    "325.OOO VND",
    "Machine normalized",
    "KIE predicted",
    "LOW_CONFIDENCE",
    "data-block-id",
  ]) expect(html).not.toContain(forbidden);
});

test("C2 bắt buộc xác nhận đủ năm field qua UI và năm giá trị không đổi tạo 0 correction", async ({ page }) => {
  await prepareStudyPage(page, allPresentReceipts());
  await page.goto(receiptUrl(C2_ORIGIN, RECEIPT_IDS.review));

  await expect(page.locator("#review-mode-badge")).toHaveText("C2 · Kiểm tra toàn bộ");
  await expect(page.locator("#review-count")).toHaveText("5/5 cần xử lý");
  await expect(page.locator("#verify-button")).toBeDisabled();

  for (const [index, fieldName] of CORE_FIELD_TYPES.entries()) {
    const card = page.locator(`[data-field-card="${fieldName}"]`);
    await card.locator(`[data-save-field="${fieldName}"]`).click();
    await expect(page.locator("#review-count")).toHaveText(`${4 - index}/5 cần xử lý`);
  }

  await expect(page.locator("#review-count")).toHaveText("0/5 cần xử lý");
  await expect(page.locator("#verify-button")).toBeEnabled();
  await page.locator("#verify-button").click();
  await expect(page.locator("#verify-button")).toHaveText("Đã xác minh");

  const summary = await page.evaluate(() => globalThis.__vietreceiptReviewEvents.find((event) => event.event === "REVIEW_COMPLETED"));
  expect(summary.confirmation_count).toBe(5);
  expect(summary.correction_count).toBe(0);
});

test("keyboard UI hỗ trợ chuyển field, xác nhận và bỏ draft", async ({ page }) => {
  await prepareStudyPage(page, allPresentReceipts());
  await page.goto(receiptUrl(C2_ORIGIN, RECEIPT_IDS.review));

  const merchantName = page.locator('[data-field-input="merchant_name"]');
  const receiptDate = page.locator('[data-field-input="receipt_date"]');
  await merchantName.focus();
  await page.keyboard.press("Alt+ArrowDown");
  await expect(receiptDate).toBeFocused();
  await page.keyboard.press("Alt+ArrowUp");
  await expect(merchantName).toBeFocused();
  await page.keyboard.press("Control+Enter");
  await expect(page.locator("#review-count")).toHaveText("4/5 cần xử lý");

  await receiptDate.fill("2026-08-12");
  await page.keyboard.press("Escape");
  await expect(receiptDate).toHaveValue("2026-08-10");
});

test("stale 409 reload GET chậm năm giây không bị tính vào active review time", async ({ page }) => {
  await prepareStudyPage(page, allPresentReceipts());
  await page.goto(receiptUrl(C2_ORIGIN, RECEIPT_IDS.review));

  await page.evaluate(async () => {
    const { OptimisticConcurrencyError, vietReceiptApi } = await import("/assets/js/api.js");
    const originalUpdate = vietReceiptApi.updateCorrection.bind(vietReceiptApi);
    const originalGet = vietReceiptApi.getReceipt.bind(vietReceiptApi);
    globalThis.__staleMutationCalls = 0;
    globalThis.__delayReload = false;
    vietReceiptApi.updateCorrection = async (...args) => {
      globalThis.__staleMutationCalls += 1;
      if (globalThis.__staleMutationCalls === 1) throw new OptimisticConcurrencyError("Field đã thay đổi ở nơi khác.");
      return originalUpdate(...args);
    };
    vietReceiptApi.getReceipt = async (...args) => {
      if (globalThis.__delayReload) {
        globalThis.__delayReload = false;
        await new Promise((resolve) => setTimeout(resolve, 5000));
      }
      return originalGet(...args);
    };
    globalThis.__reviewWallStart = performance.now();
  });

  await page.locator('[data-save-field="merchant_name"]').click();
  await expect(page.getByText("Cần tải phiên bản hóa đơn mới.", { exact: true })).toBeVisible();
  await expect(page.getByText("Mutation không được tự retry bằng token cũ.", { exact: true })).toBeVisible();
  await expect(page.locator("#verify-button")).toBeDisabled();
  expect(await page.evaluate(() => globalThis.__staleMutationCalls)).toBe(1);

  await page.evaluate(() => { globalThis.__delayReload = true; });
  await page.locator("#reload-latest").click();
  await expect(page.getByText("Cần tải phiên bản hóa đơn mới.", { exact: true })).toHaveCount(0, { timeout: 7500 });

  for (const [index, fieldName] of CORE_FIELD_TYPES.entries()) {
    await page.locator(`[data-save-field="${fieldName}"]`).click();
    await expect(page.locator("#review-count")).toHaveText(`${4 - index}/5 cần xử lý`);
  }
  await page.locator("#verify-button").click();
  await expect(page.locator("#verify-button")).toHaveText("Đã xác minh");

  const timing = await page.evaluate(() => {
    const summary = globalThis.__vietreceiptReviewEvents.find((event) => event.event === "REVIEW_COMPLETED");
    return {
      active: summary.active_review_time_ms,
      wall: performance.now() - globalThis.__reviewWallStart,
    };
  });
  expect(timing.wall - timing.active).toBeGreaterThanOrEqual(4800);
});

test("FAILED retryable thực hiện retry qua UI và chuyển về trạng thái UPLOADED", async ({ page }) => {
  await prepareStudyPage(page);
  await page.goto(receiptUrl(C2_ORIGIN, RECEIPT_IDS.failed));

  await expect(page.locator("#retry-receipt")).toBeVisible();
  await page.locator("#retry-receipt").click();
  await expect(page.getByText("Đã tải hóa đơn. Đang chờ hệ thống bắt đầu xử lý.", { exact: true })).toBeVisible();
  await expect(page.locator("#retry-receipt")).toHaveCount(0);
});
