from sqlalchemy import select, update

from .contracts import HEADER_FIELDS, validate_value
from .errors import V2Error, conflict
from .models import Audit, Cell, Invoice, timestamp


def acquire(s, rid, version):
    changed = s.execute(
        update(Invoice)
        .where(
            Invoice.receipt_id == rid,
            Invoice.version == version,
            Invoice.status == "NEEDS_REVIEW",
        )
        .values(version=Invoice.version + 1, updated_at=timestamp())
    ).rowcount
    if changed != 1:
        raise conflict()


def correct(service, rid, section, row_id, field, value, status, version):
    validate_value(section, field, value, status)
    with service.sessions.begin() as s:
        service.get(s, rid)
        acquire(s, rid, version)
        cell = s.get(Cell, (rid, section, row_id, field))
        if cell is None:
            raise V2Error("NOT_FOUND", "Invoice field or row not found.", 404)
        old = cell.correction or {
            "value": cell.machine["normalized_value"],
            "status": cell.machine["value_status"],
        }
        cell.correction = {"value": value, "status": status}
        cell.reviewed = True
        s.add(
            Audit(
                receipt_id=rid,
                kind="CORRECTION",
                section=section,
                row_id=row_id,
                field=field,
                old_value=old,
                new_value=cell.correction,
            )
        )
    return service.detail(rid)


def verify(service, rid, version):
    with service.sessions.begin() as s:
        inv = service.get(s, rid)
        acquire(s, rid, version)
        rows = s.scalars(select(Cell).where(Cell.receipt_id == rid)).all()
        if not inv.latest_kie_run_id or {
            c.field for c in rows if c.section == "header"
        } != set(HEADER_FIELDS):
            raise V2Error(
                "REVIEW_REQUIRED", "A complete latest invoice result is required."
            )
        for cell in rows:
            status = (
                cell.correction["status"]
                if cell.correction
                else cell.machine["value_status"]
            )
            if not cell.reviewed and (
                cell.machine.get("machine_needs_review", True)
                or status in ("UNKNOWN", "UNREADABLE", "AMBIGUOUS")
            ):
                raise V2Error(
                    "REVIEW_REQUIRED",
                    "Explicitly review unresolved or flagged invoice cells before verification.",
                )
        inv.status = "VERIFIED"
        inv.verified_at = timestamp()
        s.add(Audit(receipt_id=rid, kind="VERIFIED"))
    return service.detail(rid)
