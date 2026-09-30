import logging
import time

from sqlalchemy import exists, select, update
from sqlalchemy.exc import SQLAlchemyError

from .contracts import cells, validate_evidence, validate_result
from .errors import V2Error
from .models import Attempt, Cell, Invoice, MachineRun, Outbox, timestamp, uid

log = logging.getLogger(__name__)


class Processor:
    def __init__(self, service, document_reader, kie, *, lease_seconds=900):
        if lease_seconds <= 0:
            raise ValueError("lease_seconds must be positive")
        self.service, self.reader, self.kie, self.lease_seconds = (
            service,
            document_reader,
            kie,
            lease_seconds,
        )

    def claim(self, rid):
        aid, ocr, kie = uid(), uid(), uid()
        with self.service.sessions.begin() as s:
            changed = s.execute(
                update(Invoice)
                .where(
                    Invoice.receipt_id == rid,
                    Invoice.status == "UPLOADED",
                    Invoice.active_attempt_id.is_(None),
                )
                .values(
                    status="PROCESSING",
                    active_attempt_id=aid,
                    processing_stage="DOCUMENT_READING",
                    processing_error=None,
                    version=Invoice.version + 1,
                    updated_at=timestamp(),
                )
            ).rowcount
            if changed != 1:
                return None
            s.add(
                Attempt(
                    attempt_id=aid,
                    receipt_id=rid,
                    active_receipt_id=rid,
                    ocr_run_id=ocr,
                    kie_run_id=kie,
                    lease_until=time.time() + self.lease_seconds,
                )
            )
        return dict(attempt_id=aid, receipt_id=rid, ocr_run_id=ocr, kie_run_id=kie)

    @staticmethod
    def fence(s, a, **changes):
        live = exists().where(
            Attempt.attempt_id == a["attempt_id"],
            Attempt.status == "ACTIVE",
            Attempt.lease_until > time.time(),
        )
        count = s.execute(
            update(Invoice)
            .where(
                Invoice.receipt_id == a["receipt_id"],
                Invoice.status == "PROCESSING",
                Invoice.active_attempt_id == a["attempt_id"],
                live,
            )
            .values(version=Invoice.version + 1, updated_at=timestamp(), **changes)
        ).rowcount
        return count == 1

    def process(self, rid):
        a = self.claim(rid)
        if a is None:
            return False
        stage = "DOCUMENT_READING"
        log.info(
            "Processing receipt_id=%s attempt_id=%s ocr_run_id=%s kie_run_id=%s",
            rid,
            a["attempt_id"],
            a["ocr_run_id"],
            a["kie_run_id"],
        )
        try:
            data, mime, _ = self.service.source(rid)
            evidence = self.reader(
                data, content_type=mime, receipt_id=rid, ocr_run_id=a["ocr_run_id"]
            )
            validate_evidence(evidence, rid, a["ocr_run_id"])
            with self.service.sessions.begin() as s:
                if not self.fence(
                    s, a, processing_stage="KIE", latest_ocr_run_id=a["ocr_run_id"]
                ):
                    return False
                s.add(
                    MachineRun(
                        run_id=a["ocr_run_id"],
                        receipt_id=rid,
                        attempt_id=a["attempt_id"],
                        kind="OCR",
                        payload=evidence,
                    )
                )
                s.get(Attempt, a["attempt_id"]).stage = "KIE"
            stage = "KIE"
            result = self.kie(evidence, kie_run_id=a["kie_run_id"])
            validate_result(result, evidence, rid, a["kie_run_id"], a["ocr_run_id"])
            stage = "PERSISTING"
            with self.service.sessions.begin() as s:
                if not self.fence(
                    s,
                    a,
                    status="NEEDS_REVIEW",
                    active_attempt_id=None,
                    processing_stage=None,
                    latest_kie_run_id=a["kie_run_id"],
                ):
                    return False
                s.add(
                    MachineRun(
                        run_id=a["kie_run_id"],
                        receipt_id=rid,
                        attempt_id=a["attempt_id"],
                        kind="KIE",
                        source_ocr_run_id=a["ocr_run_id"],
                        payload=result,
                    )
                )
                s.flush()
                # Failed attempts never publish projections, so there are no old review cells to erase.
                for section, row, index, field, value in cells(result):
                    s.add(
                        Cell(
                            receipt_id=rid,
                            section=section,
                            row_id=row,
                            row_index=index,
                            field=field,
                            kie_run_id=a["kie_run_id"],
                            machine=value,
                        )
                    )
                attempt = s.get(Attempt, a["attempt_id"])
                attempt.status = "SUCCEEDED"
                attempt.active_receipt_id = None
                attempt.finished_at = timestamp()
                attempt.stage = "PERSISTING"
            return True
        except SQLAlchemyError:
            # Celery retries transient persistence failures; reaper handles exhausted/lost attempts.
            raise
        except Exception as exc:
            error = (
                exc
                if isinstance(exc, V2Error)
                else V2Error(
                    "DOCUMENT_READ_FAILED"
                    if stage == "DOCUMENT_READING"
                    else "KIE_FAILED",
                    "The document provider could not complete processing.",
                    503,
                    True,
                )
            )
            metadata = dict(
                stage=stage,
                code=error.code,
                message=error.message,
                retryable=error.retryable,
            )
            with self.service.sessions.begin() as s:
                if not self.fence(
                    s,
                    a,
                    status="FAILED",
                    active_attempt_id=None,
                    processing_error=metadata,
                    processing_stage=stage,
                ):
                    return False
                attempt = s.get(Attempt, a["attempt_id"])
                attempt.status = "FAILED"
                attempt.active_receipt_id = None
                attempt.finished_at = timestamp()
                attempt.error = metadata
            log.warning(
                "Processing failed receipt_id=%s attempt_id=%s stage=%s code=%s",
                rid,
                a["attempt_id"],
                stage,
                error.code,
            )
            return False


def recover_expired(service, now=None):
    now = time.time() if now is None else now
    with service.sessions() as s:
        candidates = [
            (a.attempt_id, a.receipt_id)
            for a in s.scalars(
                select(Attempt)
                .where(Attempt.status == "ACTIVE", Attempt.lease_until <= now)
                .limit(100)
            )
        ]
    recovered = 0
    for aid, rid in candidates:
        error = dict(
            stage="PROCESSING",
            code="WORKER_LEASE_EXPIRED",
            message="Processing worker stopped before completing the attempt.",
            retryable=True,
        )
        with service.sessions.begin() as s:
            expired = exists().where(
                Attempt.attempt_id == aid,
                Attempt.status == "ACTIVE",
                Attempt.lease_until <= now,
            )
            count = s.execute(
                update(Invoice)
                .where(
                    Invoice.receipt_id == rid,
                    Invoice.status == "PROCESSING",
                    Invoice.active_attempt_id == aid,
                    expired,
                )
                .values(
                    status="FAILED",
                    active_attempt_id=None,
                    processing_error=error,
                    version=Invoice.version + 1,
                    updated_at=timestamp(),
                )
            ).rowcount
            if count != 1:
                continue
            attempt = s.get(Attempt, aid)
            attempt.status = "FAILED"
            attempt.active_receipt_id = None
            attempt.error = error
            attempt.finished_at = timestamp()
            recovered += 1
    return recovered


def dispatch_pending(service, scheduler, now=None):
    now = time.time() if now is None else now
    with service.sessions() as s:
        events = [
            (e.event_id, e.receipt_id)
            for e in s.scalars(
                select(Outbox)
                .join(Invoice, Invoice.receipt_id == Outbox.receipt_id)
                .where(
                    Invoice.status == "UPLOADED",
                    ((Outbox.sent.is_(False)) | (Outbox.sent_at < now - 60)),
                )
                .order_by(Outbox.created_at)
                .limit(100)
            )
        ]
    sent = 0
    for event_id, rid in events:
        try:
            scheduler(rid)
        except Exception:
            log.warning("Queue dispatch deferred receipt_id=%s", rid)
            continue
        with service.sessions.begin() as s:
            s.execute(
                update(Outbox)
                .where(Outbox.event_id == event_id)
                .values(sent=True, sent_at=now)
            )
        sent += 1
    return sent
