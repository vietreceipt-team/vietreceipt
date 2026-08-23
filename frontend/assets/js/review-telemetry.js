export const REVIEW_EVENT_NAME = "vietreceipt:review-event";

export function createReviewTelemetry(receiptId, publish = defaultPublish) {
  let reviewStarted = false;
  let lastFocusedField = null;

  function emit(event, extra = {}) {
    const payload = {
      event,
      occurred_at: new Date().toISOString(),
      receipt_id: receiptId,
      review_mode: "PREFILL_FULL_REVIEW",
      ...extra,
    };
    publish(payload);
    return payload;
  }

  return {
    startReview() {
      if (reviewStarted) return null;
      reviewStarted = true;
      return emit("REVIEW_STARTED");
    },
    focusField(fieldName) {
      this.startReview();
      if (lastFocusedField === fieldName) return null;
      lastFocusedField = fieldName;
      return emit("FIELD_FOCUSED", { field_name: fieldName });
    },
    editField(fieldName) {
      this.startReview();
      return emit("FIELD_EDITED", { field_name: fieldName });
    },
    correction(fieldName, operation) {
      return emit(operation === "CLEAR" ? "CORRECTION_CLEARED" : "CORRECTION_APPLIED", { field_name: fieldName, operation });
    },
    verify() { return emit("RECEIPT_VERIFIED"); },
    changeReceipt() { return emit("RECEIPT_CHANGED"); },
    retry() { return emit("RETRY_REQUESTED"); },
  };
}

function defaultPublish(payload) {
  if (typeof globalThis.dispatchEvent !== "function" || typeof globalThis.CustomEvent !== "function") return;
  globalThis.dispatchEvent(new CustomEvent(REVIEW_EVENT_NAME, { detail: payload }));
}
