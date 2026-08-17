from io import BytesIO

import pytest
from PIL import Image

from app.persistence.models import ReceiptStatus
from app.services.receipt_service import ReceiptService
from app.storage.errors import InvalidImageError
from app.storage.validator import ReceiptImageValidator


def image_bytes(fmt: str, size=(7, 5)) -> bytes:
    stream = BytesIO()
    Image.new("RGB", size).save(stream, format=fmt)
    return stream.getvalue()


class MemoryStorage:
    def __init__(self):
        self.objects = {}
        self.put_calls = []

    def put(self, key, data, content_type):
        self.put_calls.append((key, content_type))
        self.objects[key] = data

    def get(self, key):
        return self.objects[key]

    def delete(self, key):
        del self.objects[key]


class MemoryRepository:
    def __init__(self):
        self.receipts = {}

    def create(self, receipt):
        self.receipts[receipt.receipt_id] = receipt
        return receipt

    def get_by_id(self, receipt_id):
        return self.receipts.get(receipt_id)

    def delete(self, receipt_id):
        return self.receipts.pop(receipt_id, None) is not None


@pytest.mark.parametrize(
    ("fmt", "content_type", "extension"),
    [("JPEG", "image/jpeg", ".jpg"), ("PNG", "image/png", ".png"), ("WEBP", "image/webp", ".webp")],
)
def test_valid_images_create_receipt_with_validated_metadata(fmt, content_type, extension):
    storage = MemoryStorage()
    repo = MemoryRepository()
    service = ReceiptService(
        validator=ReceiptImageValidator(),
        storage=storage,
        repository=repo,
    )

    receipt = service.create_receipt_from_image(
        user_id="user-1",
        original_filename="../../client-name.exe",
        image_bytes=image_bytes(fmt),
    )

    assert receipt.status is ReceiptStatus.UPLOADED
    assert receipt.content_type == content_type
    assert receipt.image_width_px == 7
    assert receipt.image_height_px == 5
    assert receipt.storage_key.endswith(extension)
    assert "client-name" not in receipt.storage_key
    assert receipt.original_filename == "../../client-name.exe"
    assert storage.put_calls == [(receipt.storage_key, content_type)]


def test_invalid_image_causes_no_storage_write():
    storage = MemoryStorage()
    service = ReceiptService(
        validator=ReceiptImageValidator(),
        storage=storage,
        repository=MemoryRepository(),
    )

    with pytest.raises(InvalidImageError):
        service.create_receipt_from_image(
            user_id="user-1", original_filename="x.jpg", image_bytes=b"not-an-image"
        )

    assert storage.put_calls == []


def test_receipt_and_storage_keys_are_unique():
    storage = MemoryStorage()
    service = ReceiptService(
        validator=ReceiptImageValidator(),
        storage=storage,
        repository=MemoryRepository(),
    )
    a = service.create_receipt_from_image(
        user_id="u", original_filename="same.png", image_bytes=image_bytes("PNG")
    )
    b = service.create_receipt_from_image(
        user_id="u", original_filename="same.png", image_bytes=image_bytes("PNG")
    )
    assert a.receipt_id != b.receipt_id
    assert a.storage_key != b.storage_key
