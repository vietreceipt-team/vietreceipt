"""Local adapter intended for development and unit tests."""

from pathlib import Path
from .errors import ObjectNotFoundError, StorageUnavailableError
from .key_safety import validate_object_key

class FileSystemReceiptImageStorage:
    def __init__(self, root: str | Path) -> None:
        self._root = Path(root)

    def _path_for(self, key: str) -> Path:
        safe_key = validate_object_key(key)
        return self._root.joinpath(*safe_key.parts)

    def put(self, key: str, data: bytes, content_type: str) -> None:
        del content_type
        path = self._path_for(key)
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(data)
        except OSError as exc:
            raise StorageUnavailableError("Could not write receipt image") from exc

    def get(self, key: str) -> bytes:
        try:
            return self._path_for(key).read_bytes()
        except FileNotFoundError as exc:
            raise ObjectNotFoundError(f"Object not found: {key}") from exc
        except OSError as exc:
            raise StorageUnavailableError("Could not read receipt image") from exc

    def delete(self, key: str) -> None:
        try:
            self._path_for(key).unlink()
        except FileNotFoundError as exc:
            raise ObjectNotFoundError(f"Object not found: {key}") from exc
        except OSError as exc:
            raise StorageUnavailableError("Could not delete receipt image") from exc
