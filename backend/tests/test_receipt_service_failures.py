from io import BytesIO
from uuid import uuid4

import pytest
from PIL import Image

from app.persistence.models import Receipt, ReceiptStatus
from app.services.errors import PersistenceFailure, ReceiptDeleteFailure
from app.services.receipt_service import ReceiptService
from app.storage.errors import ObjectNotFoundError, StorageUnavailableError
from app.storage.validator import ReceiptImageValidator


def png_bytes() -> bytes:
    stream = BytesIO()
    Image.new("RGB", (4, 3)).save(stream, format="PNG")
    return stream.getvalue()


class Storage:
    def __init__(self, fail_put=False, fail_delete=False, missing_delete=False):
        self.objects = {}
        self.put_calls = 0
        self.delete_calls = 0
        self.fail_put = fail_put
        self.fail_delete = fail_delete
        self.missing_delete = missing_delete

    def put(self, key, data, content_type):
        self.put_calls += 1
        if self.fail_put:
            raise StorageUnavailableError("put failed")
        self.objects[key] = data

    def get(self, key):
        return self.objects[key]

    def delete(self, key):
        self.delete_calls += 1
        if self.fail_delete:
            raise StorageUnavailableError("delete failed")
        if self.missing_delete or key not in self.objects:
            raise ObjectNotFoundError(key)
        del self.objects[key]


class Repo:
    def __init__(self, fail_create=False, fail_delete=False):
        self.receipts = {}
        self.create_calls = 0
        self.fail_create = fail_create
        self.fail_delete = fail_delete

    def create(self, receipt):
        self.create_calls += 1
        if self.fail_create:
            raise PersistenceFailure("db create failed")
        self.receipts[receipt.receipt_id] = receipt
        return receipt

    def get_by_id(self, receipt_id):
        return self.receipts.get(receipt_id)

    def delete(self, receipt_id):
        if self.fail_delete:
            raise PersistenceFailure("db delete failed")
        return self.receipts.pop(receipt_id, None) is not None


def service(storage, repo):
    return ReceiptService(
        validator=ReceiptImageValidator(),
        storage=storage,
        repository=repo,
    )


def test_storage_failure_creates_no_db_record():
    storage = Storage(fail_put=True)
    repo = Repo()
    with pytest.raises(StorageUnavailableError):
        service(storage, repo).create_receipt_from_image(
            user_id="u", original_filename="x.png", image_bytes=png_bytes()
        )
    assert repo.create_calls == 0


def test_db_failure_attempts_storage_cleanup():
    storage = Storage()
    repo = Repo(fail_create=True)
    with pytest.raises(PersistenceFailure):
        service(storage, repo).create_receipt_from_image(
            user_id="u", original_filename="x.png", image_bytes=png_bytes()
        )
    assert storage.delete_calls == 1
    assert storage.objects == {}


def test_cleanup_failure_is_observable(caplog):
    storage = Storage(fail_delete=True)
    repo = Repo(fail_create=True)
    with pytest.raises(PersistenceFailure, match="cleanup also failed"):
        service(storage, repo).create_receipt_from_image(
            user_id="u", original_filename="x.png", image_bytes=png_bytes()
        )
    assert "storage cleanup also failed" in caplog.text


def make_receipt():
    rid = uuid4()
    return Receipt(
        receipt_id=rid,
        user_id="u",
        original_filename="x.png",
        storage_key=f"receipts/{rid}.png",
        content_type="image/png",
        image_width_px=4,
        image_height_px=3,
        status=ReceiptStatus.UPLOADED,
    )


def test_delete_missing_receipt_is_idempotent():
    assert service(Storage(), Repo()).delete_receipt(uuid4()) is False


def test_delete_tolerates_already_missing_object():
    receipt = make_receipt()
    repo = Repo()
    repo.receipts[receipt.receipt_id] = receipt
    storage = Storage(missing_delete=True)
    assert service(storage, repo).delete_receipt(receipt.receipt_id) is True
    assert repo.get_by_id(receipt.receipt_id) is None


def test_delete_storage_unavailable_preserves_db_record():
    receipt = make_receipt()
    repo = Repo()
    repo.receipts[receipt.receipt_id] = receipt
    storage = Storage(fail_delete=True)
    with pytest.raises(ReceiptDeleteFailure):
        service(storage, repo).delete_receipt(receipt.receipt_id)
    assert repo.get_by_id(receipt.receipt_id) is receipt


def test_delete_database_failure_is_observable(caplog):
    receipt = make_receipt()
    repo = Repo(fail_delete=True)
    repo.receipts[receipt.receipt_id] = receipt
    storage = Storage()
    storage.objects[receipt.storage_key] = b"x"
    with pytest.raises(ReceiptDeleteFailure, match="metadata deletion failed"):
        service(storage, repo).delete_receipt(receipt.receipt_id)
    assert "metadata deletion failed" in caplog.text
