import pytest
from app.storage import FileSystemReceiptImageStorage, ObjectNotFoundError

def test_put_get_delete(tmp_path) -> None:
    storage = FileSystemReceiptImageStorage(tmp_path); key = "receipts/id.png"
    storage.put(key, b"synthetic bytes", "image/png")
    assert storage.get(key) == b"synthetic bytes"
    storage.delete(key)
    with pytest.raises(ObjectNotFoundError): storage.get(key)

def test_missing_object_operations_have_stable_error(tmp_path) -> None:
    storage = FileSystemReceiptImageStorage(tmp_path)
    with pytest.raises(ObjectNotFoundError): storage.get("receipts/missing.jpg")
    with pytest.raises(ObjectNotFoundError): storage.delete("receipts/missing.jpg")

@pytest.mark.parametrize("key", ["../escape.jpg", "/absolute.jpg", "receipts\\bad.jpg", "receipts//bad.jpg"])
def test_rejects_unsafe_object_keys(tmp_path, key: str) -> None:
    with pytest.raises(ValueError): FileSystemReceiptImageStorage(tmp_path).put(key, b"data", "image/jpeg")
