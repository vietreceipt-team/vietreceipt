import assert from "node:assert/strict";
import test from "node:test";
import { createApplyCorrectionRequest, MockApi, OptimisticConcurrencyError } from "../assets/js/api.js";
import { CORE_FIELD_TYPES } from "../assets/js/common.js";
import { MOCK_RECEIPTS, RECEIPT_IDS } from "../assets/js/mock-data.js";
import { editFieldStatus, editFieldValue } from "../assets/js/review-state.js";
import { saveCorrectionAndRefresh } from "../assets/js/review-workflow.js";
import { C1_MANUAL, C2_VERIFY_ALL, canVerifyStudyReceipt, createStudyFieldStates, getReviewKeyboardAction } from "../assets/js/study-mode.js";

const syntheticValues = {
  merchant_name: "CỬA HÀNG SYNTHETIC",
  receipt_date: "2026-08-10",
  total_amount: 325000,
  invoice_id: "SYN-0001",
  merchant_address: "01 Đường Kiểm Thử, Việt Nam",
};

function freshMock() {
  return new MockApi({ receipts: MOCK_RECEIPTS, delay: 0, persist: false });
}

async function completeFiveFieldStudy(mode) {
  const api = freshMock();
  let receipt = await api.getReceipt(RECEIPT_IDS.review);
  let states = createStudyFieldStates(receipt.fields, mode);
  if (mode === C1_MANUAL) assert.equal(CORE_FIELD_TYPES.every((name) => states[name].value === null), true);
  assert.equal(canVerifyStudyReceipt(receipt, states, mode), false);

  for (const fieldName of CORE_FIELD_TYPES) {
    states[fieldName] = editFieldStatus(states[fieldName], "PRESENT");
    states[fieldName] = editFieldValue(states[fieldName], fieldName, String(syntheticValues[fieldName]));
    const value = fieldName === "total_amount" ? syntheticValues[fieldName] : states[fieldName].value;
    const request = createApplyCorrectionRequest(receipt.fields[fieldName], value, "PRESENT");
    const result = await saveCorrectionAndRefresh({ api, receipt, fieldStates: states, fieldName, request });
    assert.equal(result.outcome, "REFRESHED");
    receipt = result.receipt;
    states = result.fieldStates;
    assert.equal(states[fieldName].phase, "SAVED");
  }

  assert.equal(canVerifyStudyReceipt(receipt, states, mode), true);
  const verified = await api.verifyReceipt(receipt.receipt_id, receipt.updated_at);
  assert.equal(verified.status, "VERIFIED");
  return { receipt: verified, states };
}

test("synthetic integration dry-run hoàn tất đủ năm field ở C1 manual", async () => {
  const result = await completeFiveFieldStudy(C1_MANUAL);
  assert.equal(result.receipt.status, "VERIFIED");
});

test("synthetic integration dry-run bắt buộc đủ năm field ở C2 verify-all", async () => {
  const result = await completeFiveFieldStudy(C2_VERIFY_ALL);
  assert.equal(result.receipt.status, "VERIFIED");
});

test("integration stale 409 không tự retry mutation", async () => {
  const api = freshMock();
  const receipt = await api.getReceipt(RECEIPT_IDS.review);
  const states = createStudyFieldStates(receipt.fields, C2_VERIFY_ALL);
  const request = createApplyCorrectionRequest({ ...receipt.fields.invoice_id, updated_at: "2020-01-01T00:00:00Z" }, syntheticValues.invoice_id, "PRESENT");
  let calls = 0;
  await assert.rejects(async () => {
    calls += 1;
    await api.updateCorrection(receipt.receipt_id, "invoice_id", request);
  }, OptimisticConcurrencyError);
  assert.equal(calls, 1);
  assert.equal(states.invoice_id.phase, "EDITING");
});

test("integration retryable failure và keyboard contract vẫn hoạt động", async () => {
  const api = freshMock();
  const accepted = await api.retryReceipt(RECEIPT_IDS.failed);
  assert.deepEqual(accepted, { receipt_id: RECEIPT_IDS.failed, retry_accepted: true });
  assert.equal((await api.getReceipt(RECEIPT_IDS.failed)).status, "UPLOADED");
  assert.deepEqual([
    getReviewKeyboardAction({ ctrlKey: true, metaKey: false, altKey: false, key: "Enter" }),
    getReviewKeyboardAction({ ctrlKey: false, metaKey: false, altKey: false, key: "Escape" }),
    getReviewKeyboardAction({ ctrlKey: false, metaKey: false, altKey: true, key: "ArrowDown" }),
  ], ["SAVE", "RESET", "NEXT_FIELD"]);
});
