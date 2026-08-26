export const REVIEW_EVENT_NAME = "vietreceipt:review-event";

export function createReviewTelemetry(receiptId, publish = defaultPublish, options = {}) {
  const reviewMode = options.reviewMode ?? "PREFILL_FULL_REVIEW";
  const monotonicNow = options.monotonicNow ?? (() => globalThis.performance?.now?.() ?? Date.now());
  const wallNow = options.wallNow ?? (() => new Date().toISOString());
  const createdAt = monotonicNow();
  let processingStartedAt = null;
  let readyAt = null;
  let reviewStarted = false;
  let activeStartedAt = null;
  let activeElapsed = 0;
  let confirmationCount = 0;
  let correctionCount = 0;
  let keystrokeCount = 0;
  let lastFocusedField = null;
  let completed = false;

  function duration(from, to) { return from === null || to === null ? 0 : Math.max(0, Math.round(to - from)); }

  function emit(event, extra = {}) {
    const payload = { event, occurred_at: wallNow(), receipt_id: receiptId, review_mode: reviewMode, ...extra };
    publish(payload);
    return payload;
  }

  function pauseActive() {
    if (activeStartedAt === null) return;
    activeElapsed += Math.max(0, monotonicNow() - activeStartedAt);
    activeStartedAt = null;
  }

  return {
    observeReceipt(status, hasFields = false) {
      const now = monotonicNow();
      if (processingStartedAt === null && ["UPLOADED", "PROCESSING"].includes(status)) processingStartedAt = now;
      if (hasFields && readyAt === null) {
        readyAt = now;
        return emit("REVIEW_READY", {
          waiting_time_ms: duration(createdAt, readyAt),
          processing_time_ms: duration(processingStartedAt, readyAt),
        });
      }
      return null;
    },
    startReview() {
      if (reviewStarted) return null;
      reviewStarted = true;
      activeStartedAt = monotonicNow();
      return emit("REVIEW_STARTED");
    },
    pauseActive,
    resumeActive() {
      if (!reviewStarted || completed || activeStartedAt !== null) return;
      activeStartedAt = monotonicNow();
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
    recordKeystroke() {
      this.startReview();
      keystrokeCount += 1;
      return keystrokeCount;
    },
    confirmField(fieldName, operation, changed = true) {
      confirmationCount += 1;
      if (!changed) return emit("FIELD_CONFIRMED", { field_name: fieldName, operation });
      correctionCount += 1;
      return emit(operation === "CLEAR" ? "CORRECTION_CLEARED" : "CORRECTION_APPLIED", { field_name: fieldName, operation });
    },
    verify() { return emit("RECEIPT_VERIFIED"); },
    complete() {
      if (completed) return null;
      pauseActive();
      completed = true;
      const completedAt = monotonicNow();
      return emit("REVIEW_COMPLETED", {
        waiting_time_ms: duration(createdAt, readyAt ?? completedAt),
        processing_time_ms: duration(processingStartedAt, readyAt ?? completedAt),
        active_review_time_ms: Math.max(0, Math.round(activeElapsed)),
        confirmation_count: confirmationCount,
        correction_count: correctionCount,
        keystroke_count: keystrokeCount,
        completed_at: wallNow(),
      });
    },
    resetSession() { return emit("STUDY_SESSION_RESET"); },
    changeReceipt() { pauseActive(); return emit("RECEIPT_CHANGED"); },
    retry() { return emit("RETRY_REQUESTED"); },
  };
}

function defaultPublish(payload) {
  if (typeof globalThis.dispatchEvent !== "function" || typeof globalThis.CustomEvent !== "function") return;
  globalThis.dispatchEvent(new CustomEvent(REVIEW_EVENT_NAME, { detail: payload }));
}
