"""Public TV4 provider: V2_KIE_CALLABLE=ai.kie.v2:extract_invoice."""

from uuid import UUID

from .cells import add_reason, select
from .config import CONFIGURATION, EXTRACTOR, HEADER_FIELDS
from .consistency import check
from .evidence import flatten
from .normalization import folded
from .extraction import extract_tables, header_candidates, inline_taxes, table_regions


def extract_invoice(evidence: dict, *, kie_run_id: UUID) -> dict:
    if not isinstance(kie_run_id, UUID):
        raise TypeError("kie_run_id must be uuid.UUID")
    blocks = flatten(evidence)
    regions, excluded = table_regions(blocks)
    candidates = header_candidates(blocks, excluded)
    currency_cell = select("currency", candidates["currency"])
    currency = currency_cell["normalized_value"]
    if currency is None and "UNSUPPORTED_CURRENCY" in currency_cell["review_reasons"]:
        currency = "UNSUPPORTED"
    fields = {
        field: select(field, candidates[field], currency=currency)
        for field in HEADER_FIELDS
    }
    fields["currency"] = currency_cell
    number = fields["invoice_number"]
    if number["normalized_value"] and number["normalized_value"].endswith("-"):
        add_reason(number, "AMBIGUOUS_FORMAT")
    if fields["seller_name"]["value_status"] == "PRESENT" and any(
        c.value == fields["seller_name"]["predicted_value"]
        and c.blocks[0].text in c.value
        for c in candidates["seller_name"]
    ):
        add_reason(fields["seller_name"], "SOURCE_ROLE_UNCLEAR")
    if (
        currency == "VND"
        and currency_cell["raw_text"]
        and "hoadon" in folded(currency_cell["raw_text"]).replace(" ", "")
    ):
        add_reason(currency_cell, "AMBIGUOUS_FORMAT")
    lines, taxes = extract_tables(regions, currency)
    taxes.extend(inline_taxes(blocks, excluded, currency))
    result = {
        "schema_version": "2.0",
        "receipt_id": evidence["receipt_id"],
        "kie_run_id": str(kie_run_id),
        "source_ocr_run_id": evidence["ocr_run_id"],
        "extractor": dict(EXTRACTOR),
        "configuration": dict(CONFIGURATION),
        "fields": fields,
        "line_items": lines,
        "tax_breakdown": taxes,
    }
    check(result)
    from .contract import validate_result

    validate_result(result, evidence, kie_run_id=kie_run_id)
    return result
