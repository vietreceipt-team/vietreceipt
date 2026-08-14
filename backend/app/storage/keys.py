from uuid import UUID, uuid4
from .models import ImageFormat

def generate_receipt_object_key(image_format: ImageFormat, receipt_id: UUID | None = None) -> str:
    """Generate a safe key; an upload's original filename is never an input."""
    return f"receipts/{receipt_id or uuid4()}.{image_format.extension}"
