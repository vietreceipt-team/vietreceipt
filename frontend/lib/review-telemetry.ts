import type { FieldType } from "../types/receipt";

export const REVIEW_TELEMETRY_EVENT = "vietreceipt:review-event";

export type ReviewEventName =
  | "REVIEW_STARTED"
  | "FIELD_FOCUSED"
  | "FIELD_EDITED"
  | "CORRECTION_APPLIED"
  | "CORRECTION_CLEARED"
  | "RECEIPT_VERIFIED"
  | "RECEIPT_CHANGED"
  | "RECEIPT_RETRIED";

export interface ReviewTelemetryEvent {
  event: ReviewEventName;
  occurred_at: string;
  receipt_id: string;
  field_name?: FieldType;
  operation?: "APPLY" | "CLEAR";
  review_mode: "PREFILL_FULL_REVIEW";
}

export type ReviewTelemetrySink = (event: ReviewTelemetryEvent) => void;

export function createReviewTelemetryEvent(
  event: ReviewEventName,
  receiptId: string,
  detail: Pick<ReviewTelemetryEvent, "field_name" | "operation"> = {},
  now = () => new Date(),
): ReviewTelemetryEvent {
  return {
    event,
    occurred_at: now().toISOString(),
    receipt_id: receiptId,
    review_mode: "PREFILL_FULL_REVIEW",
    ...detail,
  };
}

export function emitReviewTelemetry(
  event: ReviewTelemetryEvent,
  sink?: ReviewTelemetrySink,
) {
  if (sink) {
    sink(event);
    return;
  }
  if (typeof window !== "undefined") {
    window.dispatchEvent(new CustomEvent(REVIEW_TELEMETRY_EVENT, { detail: event }));
  }
}
