from uuid import UUID
from app.storage import ImageFormat, generate_receipt_object_key

def test_key_uses_trusted_format_and_uuid_not_original_filename() -> None:
    key = generate_receipt_object_key(ImageFormat.JPEG, UUID("12345678-1234-5678-1234-567812345678"))
    assert key == "receipts/12345678-1234-5678-1234-567812345678.jpg"
    assert "invoice" not in key
