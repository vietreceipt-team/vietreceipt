// @ts-check
import { MutationOutcomeUnknownError } from "./api.js";
import { createFieldState, reconcileStatesAfterCorrection } from "./review-state.js";

/**
 * HTTP 2xx chỉ authoritative sau khi response projector chấp nhận payload.
 * Nếu payload malformed, workflow reload receipt và không retry mutation bằng token cũ.
 */
export async function saveCorrectionAndRefresh({ api, receipt, fieldStates, fieldName, request }) {
  let savedField;
  try {
    savedField = await api.updateCorrection(receipt.receipt_id, fieldName, request, { ocrBlocks: receipt.ocr_blocks });
  } catch (error) {
    if (!(error instanceof MutationOutcomeUnknownError)) {
      return { outcome: "MUTATION_ERROR", error, receipt, fieldStates };
    }
    try {
      const latestReceipt = await api.getReceipt(receipt.receipt_id);
      const refreshedStates = reconcileStatesAfterCorrection(fieldStates, latestReceipt.fields, fieldName);
      refreshedStates[fieldName] = createFieldState(latestReceipt.fields[fieldName]);
      return {
        outcome: "REFRESHED_AFTER_UNKNOWN_MUTATION",
        error,
        receipt: latestReceipt,
        fieldStates: refreshedStates,
      };
    } catch (refreshError) {
      return {
        outcome: "MUTATION_OUTCOME_UNKNOWN",
        error,
        refreshError,
        receipt,
        fieldStates: {
          ...fieldStates,
          [fieldName]: {
            ...fieldStates[fieldName],
            phase: "STALE",
            error: "Kết quả correction chưa xác định; phải tải lại receipt trước khi tiếp tục.",
          },
        },
      };
    }
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
