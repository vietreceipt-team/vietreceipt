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

export interface ReviewInteractionSession {
  receiptId: string;
  started: boolean;
  lastFocusedField: FieldType | null;
}

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

export function createReviewInteractionSession(receiptId: string): ReviewInteractionSession {
  return { receiptId, started: false, lastFocusedField: null };
}

export function recordReviewInteraction(
  session: ReviewInteractionSession,
  fieldName?: FieldType,
  now = () => new Date(),
): { session: ReviewInteractionSession; events: ReviewTelemetryEvent[] } {
  const events: ReviewTelemetryEvent[] = [];
  let next = session;

  if (!next.started) {
    events.push(createReviewTelemetryEvent("REVIEW_STARTED", next.receiptId, {}, now));
    next = { ...next, started: true };
  }

  if (fieldName && next.lastFocusedField !== fieldName) {
    events.push(
      createReviewTelemetryEvent(
        "FIELD_FOCUSED",
        next.receiptId,
        { field_name: fieldName },
        now,
      ),
    );
    next = { ...next, lastFocusedField: fieldName };
  }

  return { session: next, events };
}
