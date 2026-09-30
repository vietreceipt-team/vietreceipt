"""Document envelope compatible with TV5 PR #53 and TV6 PR #54."""

from ai.ocr.contract import validate_ocr_result


def validate_document(document):
    if set(document) != {"schema_version", "receipt_id", "ocr_run_id", "pages"}:
        raise ValueError("Unexpected document envelope keys")
    if document["schema_version"] != "document-2.0" or not document["pages"]:
        raise ValueError("Expected nonempty document-2.0 pages")
    ids = set()
    for index, page in enumerate(document["pages"]):
        if set(page) != {"page_index", "evidence"} or page["page_index"] != index:
            raise ValueError("Page indexes must be zero-based and contiguous")
        evidence = page["evidence"]
        validate_ocr_result(evidence)
        for key in ("receipt_id", "ocr_run_id"):
            if evidence[key] != document[key]:
                raise ValueError("Page run identity mismatch")
        for block in evidence["blocks"]:
            if block["block_id"] in ids:
                raise ValueError("Duplicate block ID across pages")
            ids.add(block["block_id"])
