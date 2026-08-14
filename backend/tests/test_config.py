import pytest

from app.storage.config import ReceiptImageStorageConfig


def test_config_uses_canonical_defaults(monkeypatch: pytest.MonkeyPatch) -> None:
    for name in (
        "MAX_UPLOAD_SIZE_BYTES", "MAX_IMAGE_PIXELS", "ALLOWED_IMAGE_TYPES",
        "STORAGE_BACKEND", "STORAGE_BUCKET", "STORAGE_SECURE",
    ):
        monkeypatch.delenv(name, raising=False)
    config = ReceiptImageStorageConfig.from_env()
    assert config.max_upload_size_bytes == 10 * 1024 * 1024
    assert config.bucket == "vietreceipt"
    assert config.backend == "filesystem"
    assert set(config.allowed_image_types) == {"image/jpeg", "image/png", "image/webp"}


@pytest.mark.parametrize("value", ["0", "-1", "abc"])
def test_rejects_invalid_max_upload_size(monkeypatch: pytest.MonkeyPatch, value: str) -> None:
    monkeypatch.setenv("MAX_UPLOAD_SIZE_BYTES", value)
    with pytest.raises(ValueError):
        ReceiptImageStorageConfig.from_env()


@pytest.mark.parametrize("value", ["0", "-1", "abc"])
def test_rejects_invalid_max_image_pixels(monkeypatch: pytest.MonkeyPatch, value: str) -> None:
    monkeypatch.setenv("MAX_IMAGE_PIXELS", value)
    with pytest.raises(ValueError):
        ReceiptImageStorageConfig.from_env()


def test_rejects_invalid_storage_secure(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("STORAGE_SECURE", "sometimes")
    with pytest.raises(ValueError):
        ReceiptImageStorageConfig.from_env()


def test_rejects_unknown_storage_backend(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("STORAGE_BACKEND", "ftp")
    with pytest.raises(ValueError):
        ReceiptImageStorageConfig.from_env()


def test_rejects_allowed_types_that_diverge_from_canonical_policy(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ALLOWED_IMAGE_TYPES", "image/jpeg,image/png")
    with pytest.raises(ValueError):
        ReceiptImageStorageConfig.from_env()
