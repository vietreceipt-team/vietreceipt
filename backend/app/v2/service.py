import logging

from sqlalchemy import select, update

from .errors import V2Error, conflict
from .models import Audit, Cell, Invoice, Outbox, timestamp, uid
from .uploads import validate_upload

logger = logging.getLogger(__name__)


class InvoiceService:
    def __init__(
        self, sessions, storage, *, max_upload_bytes=10 * 1024 * 1024, max_retries=3
    ):
        self.sessions, self.storage = sessions, storage
        self.max_upload_bytes, self.max_retries = max_upload_bytes, max_retries

    def upload(self, filename, mime, data, source_group=None):
        filename, ext = validate_upload(filename, mime, data, self.max_upload_bytes)
        group = source_group or ("PDF" if mime == "application/pdf" else "IMAGE")
        if group not in ("PAPER_DIGITIZED", "IMAGE", "PDF"):
            raise V2Error("INVALID_SOURCE_GROUP", "Unsupported source group.")
        rid = uid()
        key = f"invoices/{rid}/original{ext}"
        try:
            self.storage.put(key, data, mime)
        except Exception as exc:
            raise V2Error(
                "STORAGE_FAILED", "Source storage is unavailable.", 503, True
            ) from exc
        try:
            with self.sessions.begin() as s:
                s.add(
                    Invoice(
                        receipt_id=rid,
                        original_filename=filename,
                        content_type=mime,
                        source_group=group,
                        storage_key=key,
                    )
                )
                s.flush()
                s.add(Outbox(receipt_id=rid))
        except Exception:
            try:
                self.storage.delete(key)
            except Exception:
                logger.warning("Could not clean source for receipt_id=%s", rid)
            raise
        return self.detail(rid)

    @staticmethod
    def get(s, rid):
        invoice = s.get(Invoice, rid)
        if invoice is None:
            raise V2Error("NOT_FOUND", "Invoice not found.", 404)
        return invoice

    def detail(self, rid):
        with self.sessions() as s:
            invoice = self.get(s, rid)
            result = {
                name: getattr(invoice, name)
                for name in (
                    "receipt_id",
                    "original_filename",
                    "content_type",
                    "source_group",
                    "status",
                    "version",
                    "processing_stage",
                    "processing_error",
                    "latest_ocr_run_id",
                    "latest_kie_run_id",
                    "created_at",
                    "updated_at",
                    "verified_at",
                )
            }
            result.update(
                source_url=f"/api/v2/receipts/{rid}/source",
                evidence_url=f"/api/v2/receipts/{rid}/evidence",
                fields={},
                line_items=[],
                tax_breakdown=[],
            )
            rows = s.scalars(
                select(Cell)
                .where(Cell.receipt_id == rid)
                .order_by(Cell.section, Cell.row_index, Cell.field)
            ).all()
            line_rows = {}
            tax_rows = {}
            for cell in rows:
                val = dict(cell.machine)
                effective = cell.correction or {
                    "value": val["normalized_value"],
                    "status": val["value_status"],
                }
                val.update(
                    corrected_value=cell.correction["value"]
                    if cell.correction
                    else None,
                    corrected_status=cell.correction["status"]
                    if cell.correction
                    else None,
                    has_correction=cell.correction is not None,
                    effective_value=effective["value"],
                    effective_status=effective["status"],
                    reviewed=cell.reviewed,
                    effective_needs_review=not cell.reviewed
                    and (
                        val.get("machine_needs_review", True)
                        or effective["status"] in ("UNKNOWN", "AMBIGUOUS", "UNREADABLE")
                    ),
                )
                if cell.section == "header":
                    result["fields"][cell.field] = val
                elif cell.section == "line":
                    line_rows.setdefault(cell.row_id, {"line_id": cell.row_id})[
                        cell.field
                    ] = val
                else:
                    tax_rows.setdefault(cell.row_id, {"tax_id": cell.row_id})[
                        cell.field
                    ] = val
            result["line_items"] = list(line_rows.values())
            result["tax_breakdown"] = list(tax_rows.values())
            return result

    def list(self, limit=50, offset=0):
        with self.sessions() as s:
            invoices = s.scalars(
                select(Invoice)
                .order_by(Invoice.created_at.desc(), Invoice.receipt_id)
                .limit(limit)
                .offset(offset)
            ).all()
            result = []
            for inv in invoices:
                summary = {
                    k: getattr(inv, k)
                    for k in (
                        "receipt_id",
                        "original_filename",
                        "status",
                        "version",
                        "created_at",
                    )
                }
                for field in ("seller_name", "invoice_date", "total_amount"):
                    cell = s.get(Cell, (inv.receipt_id, "header", "", field))
                    summary[field] = (
                        None
                        if cell is None
                        else (
                            cell.correction["value"]
                            if cell.correction
                            else cell.machine["normalized_value"]
                        )
                    )
                result.append(summary)
            return result

    def source(self, rid):
        with self.sessions() as s:
            inv = self.get(s, rid)
            key, mime, name = inv.storage_key, inv.content_type, inv.original_filename
        try:
            return self.storage.get(key), mime, name
        except Exception as exc:
            raise V2Error(
                "STORAGE_FAILED", "Source storage is unavailable.", 503, True
            ) from exc

    def retry(self, rid, expected_version):
        with self.sessions.begin() as s:
            inv = self.get(s, rid)
            if (
                inv.status != "FAILED"
                or not (inv.processing_error or {}).get("retryable")
                or inv.retry_count >= self.max_retries
            ):
                raise conflict("Invoice cannot be retried.")
            changed = s.execute(
                update(Invoice)
                .where(
                    Invoice.receipt_id == rid,
                    Invoice.version == expected_version,
                    Invoice.status == "FAILED",
                )
                .values(
                    status="UPLOADED",
                    version=Invoice.version + 1,
                    retry_count=Invoice.retry_count + 1,
                    updated_at=timestamp(),
                    processing_stage=None,
                    processing_error=None,
                )
            ).rowcount
            if changed != 1:
                raise conflict()
            s.add(Outbox(receipt_id=rid))
        return self.detail(rid)

    def correct(self, rid, section, row_id, field, value, status, expected_version):
        from .review import correct

        return correct(
            self, rid, section, row_id, field, value, status, expected_version
        )

    def verify(self, rid, expected_version):
        from .review import verify

        return verify(self, rid, expected_version)

    def history(self, rid):
        with self.sessions() as s:
            self.get(s, rid)
            return [
                {
                    k: getattr(e, k)
                    for k in (
                        "event_id",
                        "kind",
                        "section",
                        "row_id",
                        "field",
                        "old_value",
                        "new_value",
                        "actor",
                        "created_at",
                    )
                }
                for e in s.scalars(
                    select(Audit)
                    .where(Audit.receipt_id == rid)
                    .order_by(Audit.created_at, Audit.event_id)
                )
            ]

    def export(self, rid, format):
        from .exports import export

        return export(self.detail(rid), format)
