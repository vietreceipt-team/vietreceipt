import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { dirname, join, resolve } from "node:path";
import test from "node:test";
import { fileURLToPath } from "node:url";
import { CORE_FIELD_TYPES } from "../assets/js/common.js";
import { MOCK_RECEIPTS } from "../assets/js/mock-data.js";
import { createReviewTelemetry, withReviewActivityPaused } from "../assets/js/review-telemetry.js";
import {
  C1_MANUAL,
  C2_VERIFY_ALL,
  canVerifyStudyReceipt,
  createStudyFieldStates,
  createStudySession,
  getReviewKeyboardAction,
  renderC1ManualForm,
  shouldRenderEvidence,
  studyPendingCount,
} from "../assets/js/study-mode.js";
import { createRuntimeConfigScript } from "../server.js";

const root = resolve(dirname(fileURLToPath(import.meta.url)), "..");
const detailSource = readFileSync(join(root, "assets/js/receipt-detail.js"), "utf8");

function memoryStorage() {
  const values = new Map();
  return {
    getItem(key) { return values.has(key) ? values.get(key) : null; },
    setItem(key, value) { values.set(key, String(value)); },
    removeItem(key) { values.delete(key); },
  };
}

test("runtime config chỉ chấp nhận C1/C2 và thứ tự counterbalance đầy đủ", () => {
  const c1 = createRuntimeConfigScript({ studyMode: C1_MANUAL, studyOrder: [C1_MANUAL, C2_VERIFY_ALL] });
  const c2 = createRuntimeConfigScript({ studyMode: C2_VERIFY_ALL, studyOrder: `${C2_VERIFY_ALL},${C1_MANUAL}` });
  assert.match(c1, /"studyMode":"C1_MANUAL"/);
  assert.match(c2, /"studyOrder":\["C2_VERIFY_ALL","C1_MANUAL"\]/);
  assert.throws(() => createRuntimeConfigScript({ studyMode: "C3_SELECTIVE", studyOrder: [C1_MANUAL, C2_VERIFY_ALL] }));
  assert.throws(() => createRuntimeConfigScript({ studyMode: C1_MANUAL, studyOrder: [C2_VERIFY_ALL, C1_MANUAL] }));
  assert.throws(() => createRuntimeConfigScript({ studyMode: C1_MANUAL, studyOrder: [C1_MANUAL, C1_MANUAL] }));
});

test("study session theo configured order, advance và reset không lưu field data", () => {
  const storage = memoryStorage();
  const session = createStudySession({ studyMode: C2_VERIFY_ALL, studyOrder: [C2_VERIFY_ALL, C1_MANUAL] }, storage);
  assert.equal(session.currentMode, C2_VERIFY_ALL);
  assert.equal(session.completeCondition(), C1_MANUAL);
  assert.equal(session.currentMode, C1_MANUAL);
  assert.equal(session.reset(), C2_VERIFY_ALL);
  assert.equal(session.currentMode, C2_VERIFY_ALL);
  const persisted = storage.getItem("vietreceipt:study-session:v1");
  assert.deepEqual(Object.keys(JSON.parse(persisted)).sort(), ["index", "signature"]);
});

test("C1 tạo form trống đủ năm field và DOM không chứa machine output/evidence", () => {
  const receipt = structuredClone(MOCK_RECEIPTS[0]);
  receipt.fields.merchant_name.raw_text = "SENTINEL_RAW_TEXT";
  receipt.fields.merchant_name.predicted_value = "SENTINEL_PREDICTION";
  receipt.fields.merchant_name.normalized_value = "SENTINEL_NORMALIZED";
  receipt.fields.merchant_name.review_reasons = ["SENTINEL_REASON"];
  receipt.fields.merchant_name.source_block_ids = ["SENTINEL_BLOCK"];
  const states = createStudyFieldStates(receipt.fields, C1_MANUAL);
  const html = renderC1ManualForm(states);
  assert.equal(CORE_FIELD_TYPES.filter((name) => html.includes(`data-field-card="${name}"`)).length, 5);
  assert.equal(CORE_FIELD_TYPES.every((name) => states[name].value === null && states[name].phase === "EDITING"), true);
  for (const sentinel of ["SENTINEL_RAW_TEXT", "SENTINEL_PREDICTION", "SENTINEL_NORMALIZED", "SENTINEL_REASON", "SENTINEL_BLOCK"]) assert.equal(html.includes(sentinel), false);
  assert.equal(shouldRenderEvidence(C1_MANUAL), false);
  assert.match(detailSource, /shouldRenderEvidence\(studyMode\)/);
  assert.match(detailSource, /renderC1ManualForm\(fieldStates, canEdit\)/);
});

test("C2 bắt buộc xác nhận đủ năm field bất kể confidence", () => {
  const receipt = structuredClone(MOCK_RECEIPTS[0]);
  for (const field of Object.values(receipt.fields)) field.effective_needs_review = false;
  const states = createStudyFieldStates(receipt.fields, C2_VERIFY_ALL);
  assert.equal(studyPendingCount(receipt.fields, states, C2_VERIFY_ALL), 5);
  assert.equal(canVerifyStudyReceipt(receipt, states, C2_VERIFY_ALL), false);
  for (const state of Object.values(states)) state.phase = "SAVED";
  assert.equal(studyPendingCount(receipt.fields, states, C2_VERIFY_ALL), 0);
  assert.equal(canVerifyStudyReceipt(receipt, states, C2_VERIFY_ALL), true);
  states.total_amount.value = "325000";
  assert.equal(canVerifyStudyReceipt(receipt, states, C2_VERIFY_ALL), false);
});

test("telemetry tách waiting/processing/active time và chỉ xuất count", () => {
  let now = 0;
  const events = [];
  const telemetry = createReviewTelemetry("receipt-synthetic", (payload) => events.push(payload), {
    reviewMode: C1_MANUAL,
    monotonicNow: () => now,
    wallNow: () => `2026-08-25T00:00:${String(Math.floor(now / 1000)).padStart(2, "0")}Z`,
  });
  telemetry.observeReceipt("PROCESSING", false);
  now = 100;
  telemetry.observeReceipt("NEEDS_REVIEW", true);
  now = 150;
  telemetry.startReview();
  now = 200;
  telemetry.recordKeystroke();
  now = 250;
  const manualPause = telemetry.pauseActive("test-manual-pause");
  now = 300;
  telemetry.resumeActive(manualPause);
  now = 340;
  telemetry.confirmField("merchant_name", "APPLY");
  now = 400;
  const summary = telemetry.complete();
  assert.equal(summary.review_mode, C1_MANUAL);
  assert.equal(summary.waiting_time_ms, 100);
  assert.equal(summary.processing_time_ms, 100);
  assert.equal(summary.active_review_time_ms, 200);
  assert.equal(summary.confirmation_count, 1);
  assert.equal(summary.correction_count, 1);
  assert.equal(summary.keystroke_count, 1);
  assert.equal(events.filter((event) => event.event === "REVIEW_COMPLETED").length, 1);
  const serialized = JSON.stringify(events);
  for (const forbidden of ["raw_text", "predicted_value", "effective_value", "field_value", "ocr_text", "image_data", "access_token", "credential", "SENTINEL_PREDICTION"]) assert.equal(serialized.includes(forbidden), false);
});

test("API latency không được cộng vào active time và xác nhận không đổi không phải correction", () => {
  let now = 0;
  const telemetry = createReviewTelemetry("receipt-latency", () => {}, {
    reviewMode: C2_VERIFY_ALL,
    monotonicNow: () => now,
    wallNow: () => "2026-08-26T00:00:00Z",
  });
  telemetry.observeReceipt("NEEDS_REVIEW", true);
  telemetry.startReview();
  now = 100;
  const apiPause = telemetry.pauseActive("test-api");
  now = 5100;
  telemetry.resumeActive(apiPause);
  now = 5200;
  for (const fieldName of CORE_FIELD_TYPES) telemetry.confirmField(fieldName, "APPLY", false);
  const summary = telemetry.complete();
  assert.equal(summary.active_review_time_ms, 200);
  assert.equal(summary.confirmation_count, 5);
  assert.equal(summary.correction_count, 0);
});

test("stale reload GET chậm năm giây không làm tăng active review time", async () => {
  let now = 0;
  const telemetry = createReviewTelemetry("receipt-stale-reload", () => {}, {
    reviewMode: C2_VERIFY_ALL,
    monotonicNow: () => now,
    wallNow: () => "2026-08-28T00:00:00Z",
  });
  telemetry.observeReceipt("NEEDS_REVIEW", true);
  telemetry.startReview();
  now = 100;
  await withReviewActivityPaused(telemetry, "reload-latest", async () => { now = 5100; });
  now = 5200;
  const summary = telemetry.complete();
  assert.equal(summary.active_review_time_ms, 200);
  assert.match(detailSource, /withReviewActivityPaused\(telemetry, "reload-latest"/);
});

test("API wait chồng nhau và visibility hidden chỉ resume sau pause token cuối", async () => {
  let now = 0;
  const telemetry = createReviewTelemetry("receipt-overlap", () => {}, {
    reviewMode: C2_VERIFY_ALL,
    monotonicNow: () => now,
    wallNow: () => "2026-08-28T00:00:00Z",
  });
  telemetry.observeReceipt("NEEDS_REVIEW", true);
  telemetry.startReview();
  now = 100;

  let finishFirst;
  let finishSecond;
  const firstWait = withReviewActivityPaused(telemetry, "correction-api", () => new Promise((resolve) => { finishFirst = resolve; }));
  const secondWait = withReviewActivityPaused(telemetry, "correction-api", () => new Promise((resolve) => { finishSecond = resolve; }));
  const hiddenPause = telemetry.pauseActive("document-hidden");

  now = 5100;
  finishFirst();
  await firstWait;
  now = 6100;
  finishSecond();
  await secondWait;
  now = 7100;
  telemetry.resumeActive(hiddenPause);
  now = 7200;

  const summary = telemetry.complete();
  assert.equal(summary.active_review_time_ms, 200);
});

test("keyboard mapping giữ save/reset/navigation mà không ghi nội dung phím vào telemetry", () => {
  assert.equal(getReviewKeyboardAction({ ctrlKey: true, metaKey: false, altKey: false, key: "Enter" }), "SAVE");
  assert.equal(getReviewKeyboardAction({ ctrlKey: false, metaKey: false, altKey: false, key: "Escape" }), "RESET");
  assert.equal(getReviewKeyboardAction({ ctrlKey: false, metaKey: false, altKey: true, key: "ArrowUp" }), "PREVIOUS_FIELD");
  assert.equal(getReviewKeyboardAction({ ctrlKey: false, metaKey: false, altKey: true, key: "ArrowDown" }), "NEXT_FIELD");
  assert.equal(getReviewKeyboardAction({ ctrlKey: false, metaKey: false, altKey: false, key: "a" }), null);
});
