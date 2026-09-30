"""Conservative V2 rules with explicitly versioned legacy primitive reuse."""

import math
import re
import unicodedata

from ai.kie.models import Candidate
from ai.kie.normalization.invoice_id import normalize_invoice_id
from ai.kie.normalization.merchant_address import normalize_merchant_address
from ai.kie.normalization.merchant_name import normalize_merchant_name
from ai.kie.normalization.receipt_date import normalize_receipt_date
from ai.kie.normalization.total_amount import normalize_total_amount

from .config import MONEY_FIELDS, NORMALIZATION_VERSION


def text(value: str) -> str:
    return " ".join(unicodedata.normalize("NFC", value).split())


def folded(value: str) -> str:
    return "".join(
        c
        for c in unicodedata.normalize("NFD", text(value).lower())
        if not unicodedata.combining(c)
    ).replace("đ", "d")


def legacy(field, value, raw, normalizer):
    candidate = Candidate(field, value, (), raw, (), (), 0, 0, 0, 0, 0)
    result = normalizer(candidate)
    return result.normalized_value, result.provenance()


def normalize(field: str, value: str, raw: str, currency: str | None):
    """Return value, provenance, failure reason; never repairs source text."""
    value = text(value)
    rule = "nfc_whitespace"
    result = None
    provenance = None
    if field in MONEY_FIELDS:
        if currency != "VND":
            return (
                None,
                None,
                "UNSUPPORTED_CURRENCY" if currency else "AMBIGUOUS_FORMAT",
            )
        result, provenance = legacy("total_amount", value, raw, normalize_total_amount)
    elif field == "invoice_date":
        # No implicit locale: reuse legacy calendar parser without its transaction
        # label override. Vietnamese word-form dates supply explicit components.
        words = re.fullmatch(
            r"ngay (\d{1,2}) thang (\d{1,2}) nam (\d{4})", folded(value)
        )
        if words:
            day, month, year = map(int, words.groups())
            value = f"{year:04}-{month:02}-{day:02}"
        result, provenance = legacy("receipt_date", value, "", normalize_receipt_date)
        if result is None:
            return None, None, "AMBIGUOUS_FORMAT"
    elif field in {"invoice_number", "invoice_symbol", "invoice_template_number"}:
        result, provenance = legacy("invoice_id", value, raw, normalize_invoice_id)
    elif field.endswith("tax_id"):
        # Only printed separators, never digit repair; accept 10 or 13 digits.
        if re.fullmatch(r"[0-9 .-]+", value):
            digits = re.sub(r"[ .-]", "", value)
            if len(digits) in (10, 13):
                result, rule = digits, "tax_id_printed_separators"
    elif field == "quantity":
        if re.fullmatch(r"[0-9]+(?:[.,][0-9]+)?", value):
            result = float(value.replace(",", "."))
            if not math.isfinite(result):
                result = None
            rule = "quantity_decimal_no_grouping"
    elif field == "currency":
        if folded(value) in {"vnd", "vndong", "vnđ", "d", "₫", "dong"}:
            result, rule = "VND", "explicit_vnd_marker"
        else:
            return None, None, "UNSUPPORTED_CURRENCY"
    elif field == "rate":
        if re.fullmatch(r"[0-9]+(?:[.,][0-9]+)?\s*%", value):
            result, rule = value.replace(" ", "").replace(",", "."), "printed_percent"
        elif folded(value) in {"kct", "khong chiu thue", "kkkt"}:
            result, rule = value, "printed_tax_category"
    elif field == "seller_address":
        result, provenance = legacy(
            "merchant_address", value, raw, normalize_merchant_address
        )
    else:
        result, provenance = legacy(
            "merchant_name", value, raw, normalize_merchant_name
        )
    if result is None:
        return None, None, "NORMALIZATION_FAILED"
    return result, provenance or {"rule": rule, "version": NORMALIZATION_VERSION}, None
