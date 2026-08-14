from io import BytesIO
import pytest
from botocore.exceptions import ClientError, EndpointConnectionError
from app.storage.errors import ObjectNotFoundError, StorageUnavailableError
from app.storage.s3 import S3ReceiptImageStorage

class FakeClient:
    def __init__(self) -> None: self.objects = {}; self.fail = False
    def _check(self) -> None:
        if self.fail: raise EndpointConnectionError(endpoint_url="http://storage.invalid")
    def put_object(self, **kwargs) -> None: self._check(); self.objects[kwargs["Key"]] = kwargs["Body"]
    def get_object(self, **kwargs):
        self._check()
        if kwargs["Key"] not in self.objects: raise _not_found()
        return {"Body": BytesIO(self.objects[kwargs["Key"]])}
    def head_object(self, **kwargs) -> None:
        self._check()
        if kwargs["Key"] not in self.objects: raise _not_found()
    def delete_object(self, **kwargs) -> None: self._check(); del self.objects[kwargs["Key"]]

def _not_found() -> ClientError: return ClientError({"Error": {"Code": "NoSuchKey"}}, "GetObject")

def test_s3_put_get_delete() -> None:
    client = FakeClient(); storage = S3ReceiptImageStorage(client, "receipts"); key = "receipts/id.webp"
    storage.put(key, b"image", "image/webp"); assert storage.get(key) == b"image"; storage.delete(key)
    with pytest.raises(ObjectNotFoundError): storage.get(key)

def test_s3_maps_not_found() -> None:
    with pytest.raises(ObjectNotFoundError): S3ReceiptImageStorage(FakeClient(), "receipts").get("receipts/missing.jpg")

def test_s3_maps_sdk_failure() -> None:
    client = FakeClient(); client.fail = True
    with pytest.raises(StorageUnavailableError): S3ReceiptImageStorage(client, "receipts").put("receipts/id.jpg", b"image", "image/jpeg")
