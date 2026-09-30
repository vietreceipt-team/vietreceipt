"""Public TV4 provider: V2_KIE_CALLABLE=ai.kie.v2:extract_invoice."""

from uuid import UUID

from .cells import select
from .config import CONFIGURATION, EXTRACTOR, HEADER_FIELDS
from .consistency import check
from .evidence import flatten
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
