# Receipt State Machine v1

## Canonical states

The public receipt lifecycle has exactly five states:

| State | Meaning | User-visible action |
| --- | --- | --- |
| `UPLOADED` | Image and receipt metadata are stored; Backend will schedule processing automatically | View or delete |
| `PROCESSING` | A worker is preprocessing, running OCR/KIE or persisting results | View progress |
| `NEEDS_REVIEW` | Machine results are stored and await human verification | Review, correct and verify |
| `VERIFIED` | User confirmed the effective status/value of all five fields | View, search and export |
| `FAILED` | Pipeline stopped because a processing attempt failed | View error, retry or delete |

`QUEUED` is an internal task-transport condition, not a receipt state and must not cross the public API boundary.

## Valid transitions

```mermaid
stateDiagram-v2
    [*] --> UPLOADED
    UPLOADED --> PROCESSING: Backend auto-starts job
    PROCESSING --> NEEDS_REVIEW: OCR and KIE saved
    PROCESSING --> FAILED: pipeline error
    FAILED --> PROCESSING: authorized retry
    NEEDS_REVIEW --> VERIFIED: user verifies
    VERIFIED --> [*]
```

| From | To | Trigger | Actor |
| --- | --- | --- | --- |
| none | `UPLOADED` | Valid image stored and metadata committed | Backend |
| `UPLOADED` | `PROCESSING` | Backend automatically schedules and starts the processing attempt | Backend/Worker |
| `PROCESSING` | `NEEDS_REVIEW` | OCR/KIE results persisted | Worker |
| `PROCESSING` | `FAILED` | Processing attempt fails or expires | Worker |
| `FAILED` | `PROCESSING` | Authorized retry accepted | Backend/Worker |
| `NEEDS_REVIEW` | `VERIFIED` | User submits the current receipt concurrency token and all fields are resolved | Backend |

Frontend never calls a public `/process` endpoint. It uploads the image and polls the receipt status. All other transitions return HTTP `409` with code `RECEIPT_STATE_CONFLICT`.

## Invariants

1. `UPLOADED` implies an object-storage key and original filename exist.
2. Backend automatically schedules processing after a successful upload; task-queue details remain internal.
3. Only `PROCESSING` may append a new machine prediction set; prior OCR/KIE runs are never overwritten.
4. `NEEDS_REVIEW` implies a latest OCR/KIE run and exactly five canonical extracted field records exist.
5. Missing KIE values use `null` plus an explicit `value_status`; missing fields do not force `FAILED`.
6. `VERIFIED` implies every field has a human-resolved `effective_status`; `AMBIGUOUS` and `UNKNOWN` cannot remain unresolved.
7. Verification includes `expected_updated_at` from the latest receipt response. A stale token returns HTTP `409` and does not verify the receipt.
8. Only `VERIFIED` receipts are included in official export/dashboard spending totals by default.
9. `FAILED` records contain a safe `last_error` object with stage and code; sensitive OCR text is excluded.
10. Retry creates a new processing attempt and transitions directly to `PROCESSING`; it never destroys prior OCR/KIE runs or correction history.
11. Deletion is a separate resource operation, not a receipt status. It must remove or schedule removal of related database rows and image objects.

## Progress stage

Status describes lifecycle; `processing_stage` describes progress while `PROCESSING`:

```text
PREPROCESSING | OCR | KIE | PERSISTING
```

`processing_stage` is `null` outside `PROCESSING`.

## Error representation

```json
{
  "stage": "OCR",
  "code": "OCR_TIMEOUT",
  "message": "OCR processing exceeded the configured time limit.",
  "retryable": true,
  "occurred_at": "2026-08-10T08:30:00Z"
}
```

The public message must be safe for users. Stack traces and receipt text stay in protected server logs.
