"""MinIO/S3-compatible adapter isolated behind ReceiptImageStorage."""

from typing import Any
from botocore.exceptions import BotoCoreError, ClientError
from .errors import ObjectNotFoundError, StorageUnavailableError
from .key_safety import validate_object_key

class S3ReceiptImageStorage:
    def __init__(self, client: Any, bucket: str) -> None:
        if not bucket:
            raise ValueError("bucket is required")
        self._client = client
        self._bucket = bucket

    def put(self, key: str, data: bytes, content_type: str) -> None:
        validate_object_key(key)
        try:
            self._client.put_object(Bucket=self._bucket, Key=key, Body=data, ContentType=content_type)
        except (BotoCoreError, ClientError) as exc:
            raise StorageUnavailableError("Could not write receipt image") from exc

    def get(self, key: str) -> bytes:
        validate_object_key(key)
        try:
            return self._client.get_object(Bucket=self._bucket, Key=key)["Body"].read()
        except ClientError as exc:
            if _is_not_found(exc):
                raise ObjectNotFoundError(f"Object not found: {key}") from exc
            raise StorageUnavailableError("Could not read receipt image") from exc
        except (BotoCoreError, OSError, KeyError) as exc:
            raise StorageUnavailableError("Could not read receipt image") from exc

    def delete(self, key: str) -> None:
        validate_object_key(key)
        try:
            self._client.head_object(Bucket=self._bucket, Key=key)
            self._client.delete_object(Bucket=self._bucket, Key=key)
        except ClientError as exc:
            if _is_not_found(exc):
                raise ObjectNotFoundError(f"Object not found: {key}") from exc
            raise StorageUnavailableError("Could not delete receipt image") from exc
        except BotoCoreError as exc:
            raise StorageUnavailableError("Could not delete receipt image") from exc

def _is_not_found(exc: ClientError) -> bool:
    return str(exc.response.get("Error", {}).get("Code")) in {"404", "NoSuchKey", "NotFound"}
