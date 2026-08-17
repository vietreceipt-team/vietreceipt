class ReceiptApplicationError(Exception):
    """Base application-layer error."""


class PersistenceFailure(ReceiptApplicationError):
    """Receipt metadata persistence failed."""


class ReceiptDeleteFailure(ReceiptApplicationError):
    """Receipt deletion could not be completed consistently."""
