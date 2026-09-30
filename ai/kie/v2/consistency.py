"""Arithmetic diagnostics only: never fills or changes extracted values."""

from .cells import add_reason
from .config import CONSISTENCY_VERSION, TOLERANCE_VND
from .extraction import row_metadata


def check(result):
    fields, rows = result["fields"], result["line_items"]
    checks = []

    def compare(name, left, right, cells):
        available = left is not None and right is not None
        passed = abs(left - right) <= TOLERANCE_VND if available else None
        checks.append(
            {
                "name": name,
                "status": "SKIPPED"
                if passed is None
                else "PASS"
                if passed
                else "WARNING",
                "difference_vnd": left - right if available else None,
            }
        )
        if passed is False:
            for cell in cells:
                add_reason(cell, "CONSISTENCY_WARNING")

    amounts = [r["amount"] for r in rows]
    line_sum = (
        sum(c["normalized_value"] for c in amounts)
        if amounts and all(c["value_status"] == "PRESENT" for c in amounts)
        else None
    )
    compare(
        "line_sum_subtotal",
        line_sum,
        fields["subtotal"]["normalized_value"],
        amounts + [fields["subtotal"]],
    )
    subtotal, tax, total = (
        fields[f]["normalized_value"]
        for f in ("subtotal", "tax_amount", "total_amount")
    )
    compare(
        "subtotal_tax_total",
        subtotal + tax if subtotal is not None and tax is not None else None,
        total,
        [fields[f] for f in ("subtotal", "tax_amount", "total_amount")],
    )
    for row in rows:
        row_metadata(row)
    result["consistency"] = {
        "version": CONSISTENCY_VERSION,
        "tolerance_vnd": TOLERANCE_VND,
        "checks": checks,
    }
