"""Environment-backed configuration for receipt image storage."""

from dataclasses import dataclass
import os

DEFAULT_MAX_IMAGE_SIZE_BYTES = 10 * 1024 * 1024

def _positive_int(name: str, default: int) -> int:
    raw = os.getenv(name)
    if raw is None:
        return default
    try:
        value = int(raw)
    except ValueError as exc:
        raise ValueError(f"{name} must be an integer") from exc
    if value <= 0:
        raise ValueError(f"{name} must be greater than zero")
    return value

def _optional_bool(name: str) -> bool | None:
    raw = os.getenv(name)
    if raw is None or raw == "":
        return None
    normalized = raw.strip().lower()
    if normalized in {"1", "true", "yes", "on"}:
        return True
    if normalized in {"0", "false", "no", "off"}:
        return False
    raise ValueError(f"{name} must be a boolean")

@dataclass(frozen=True, slots=True)
class ReceiptImageStorageConfig:
    max_image_size_bytes: int = DEFAULT_MAX_IMAGE_SIZE_BYTES
    backend: str = "filesystem"
    filesystem_root: str = ".data/receipt-images"
    endpoint: str | None = None
    region: str | None = None
    bucket: str | None = None
    access_key: str | None = None
    secret_key: str | None = None
    use_ssl: bool | None = None

    @classmethod
    def from_env(cls) -> "ReceiptImageStorageConfig":
        return cls(max_image_size_bytes=_positive_int("RECEIPT_IMAGE_MAX_SIZE_BYTES", DEFAULT_MAX_IMAGE_SIZE_BYTES), backend=os.getenv("STORAGE_BACKEND", "filesystem").strip().lower(), filesystem_root=os.getenv("STORAGE_FILESYSTEM_ROOT", ".data/receipt-images"), endpoint=os.getenv("STORAGE_ENDPOINT") or None, region=os.getenv("STORAGE_REGION") or None, bucket=os.getenv("STORAGE_BUCKET") or None, access_key=os.getenv("STORAGE_ACCESS_KEY") or None, secret_key=os.getenv("STORAGE_SECRET_KEY") or None, use_ssl=_optional_bool("STORAGE_USE_SSL"))
