"""Experimental, region-scoped Table extraction boundary."""

from .extractor import extract_table
from .pipeline import extract_invoice_with_tables

__all__ = ["extract_table", "extract_invoice_with_tables"]
