// @ts-check
import { reconcileStatesAfterCorrection } from "./review-state.js";

/**
 * PATCH thành công là authoritative ngay cả khi GET receipt kế tiếp thất bại.
 * Caller dùng outcome để phân biệt mutation failure và refresh-required.
 */
export async function saveCorrectionAndRefresh({ api, receipt, fieldStates, fieldName, request }) {
  let savedField;
  try {
    savedField = await api.updateCorrection(receipt.receipt_id, fieldName, request);
  } catch (error) {
    return { outcome: "MUTATION_ERROR", error, receipt, fieldStates };
  }

  const receiptWithSavedField = {
    ...receipt,
    fields: { ...receipt.fields, [fieldName]: savedField },
  };
  const savedStates = reconcileStatesAfterCorrection(fieldStates, receiptWithSavedField.fields, fieldName);

  try {
    const latestReceipt = await api.getReceipt(receipt.receipt_id);
    return {
      outcome: "REFRESHED",
      receipt: latestReceipt,
      fieldStates: reconcileStatesAfterCorrection(savedStates, latestReceipt.fields, fieldName),
    };
  } catch (error) {
    return {
      outcome: "REFRESH_REQUIRED",
      error,
      receipt: receiptWithSavedField,
      fieldStates: savedStates,
    };
  }
}
