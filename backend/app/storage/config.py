"""Environment-backed configuration for receipt image storage."""

from dataclasses import dataclass
import os

DEFAULT_MAX_UPLOAD_SIZE_BYTES = 10 * 1024 * 1024
DEFAULT_MAX_IMAGE_PIXELS = 40_000_000
DEFAULT_ALLOWED_IMAGE_TYPES = ("image/jpeg", "image/png", "image/webp")
_ALLOWED_STORAGE_BACKENDS = {"filesystem", "s3"}


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


def _storage_backend() -> str:
    backend = os.getenv("STORAGE_BACKEND", "filesystem").strip().lower()
    if backend not in _ALLOWED_STORAGE_BACKENDS:
        raise ValueError("STORAGE_BACKEND must be one of: filesystem, s3")
    return backend


def _allowed_image_types() -> tuple[str, ...]:
    raw = os.getenv("ALLOWED_IMAGE_TYPES")
    if raw is None or not raw.strip():
        return DEFAULT_ALLOWED_IMAGE_TYPES
    values = tuple(part.strip().lower() for part in raw.split(",") if part.strip())
    if set(values) != set(DEFAULT_ALLOWED_IMAGE_TYPES) or len(values) != len(DEFAULT_ALLOWED_IMAGE_TYPES):
        raise ValueError("ALLOWED_IMAGE_TYPES must contain exactly image/jpeg,image/png,image/webp")
    return values


@dataclass(frozen=True, slots=True)
class ReceiptImageStorageConfig:
    max_upload_size_bytes: int = DEFAULT_MAX_UPLOAD_SIZE_BYTES
    max_image_pixels: int = DEFAULT_MAX_IMAGE_PIXELS
    allowed_image_types: tuple[str, ...] = DEFAULT_ALLOWED_IMAGE_TYPES
    backend: str = "filesystem"
    filesystem_root: str = ".data/receipt-images"
    endpoint: str | None = None
    region: str | None = None
    bucket: str = "vietreceipt"
    access_key: str | None = None
    secret_key: str | None = None
    secure: bool | None = None

    @classmethod
    def from_env(cls) -> "ReceiptImageStorageConfig":
        return cls(
            max_upload_size_bytes=_positive_int("MAX_UPLOAD_SIZE_BYTES", DEFAULT_MAX_UPLOAD_SIZE_BYTES),
            max_image_pixels=_positive_int("MAX_IMAGE_PIXELS", DEFAULT_MAX_IMAGE_PIXELS),
            allowed_image_types=_allowed_image_types(),
            backend=_storage_backend(),
            filesystem_root=os.getenv("STORAGE_FILESYSTEM_ROOT", ".data/receipt-images"),
            endpoint=os.getenv("STORAGE_ENDPOINT") or None,
            region=os.getenv("STORAGE_REGION") or None,
            bucket=os.getenv("STORAGE_BUCKET", "vietreceipt") or "vietreceipt",
            access_key=os.getenv("STORAGE_ACCESS_KEY") or None,
            secret_key=os.getenv("STORAGE_SECRET_KEY") or None,
            secure=_optional_bool("STORAGE_SECURE"),
        )
