"""Versioned, fixed configuration for the deterministic Invoice V2 baseline."""

HEADER_FIELDS = (
    "invoice_template_number",
    "invoice_symbol",
    "invoice_number",
    "invoice_date",
    "seller_name",
    "seller_tax_id",
    "seller_address",
    "buyer_name",
    "buyer_tax_id",
    "subtotal",
    "tax_amount",
    "total_amount",
    "currency",
)
LINE_FIELDS = ("description", "unit", "quantity", "unit_price", "amount")
TAX_FIELDS = ("rate", "taxable_amount", "tax_amount")
MONEY_FIELDS = {
    "subtotal",
    "tax_amount",
    "total_amount",
    "unit_price",
    "amount",
    "taxable_amount",
}
EXTRACTOR = {"name": "deterministic-invoice-kie", "version": "2.0.4"}
CONFIGURATION = {"name": "invoice-baseline", "version": "2.1.0"}
REVIEW_VERSION = "invoice-review-2.0.0"
SCORE_VERSION = "invoice-heuristic-2.0.0"
NORMALIZATION_VERSION = "invoice-normalization-2.0.0"
CONSISTENCY_VERSION = "invoice-consistency-2.0.0"
TOLERANCE_VND = 1
LOW_SCORE = 0.8
TIE_MARGIN = 0.1
ROW_OVERLAP = 0.35
CONTINUATION_HEIGHTS = 1.8
