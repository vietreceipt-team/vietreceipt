from io import BytesIO
import pytest
from PIL import Image
from app.storage import ImageFormat, ImageTooLargeError, InvalidImageError, ReceiptImageValidator, UnsupportedImageFormatError

def synthetic_image(format_name: str) -> bytes:
    buffer = BytesIO()
    Image.new("RGB", (2, 2), color=(12, 34, 56)).save(buffer, format=format_name)
    return buffer.getvalue()

@pytest.mark.parametrize(("format_name", "expected"), [("JPEG", ImageFormat.JPEG), ("PNG", ImageFormat.PNG), ("WEBP", ImageFormat.WEBP)])
def test_accepts_supported_images(format_name: str, expected: ImageFormat) -> None:
    result = ReceiptImageValidator().validate(synthetic_image(format_name))
    assert result.format is expected
    assert result.content_type == expected.content_type

def test_rejects_fake_jpeg_content_regardless_of_filename() -> None:
    with pytest.raises(InvalidImageError): ReceiptImageValidator().validate(b"not an image despite a .jpg name")

def test_rejects_empty_file() -> None:
    with pytest.raises(InvalidImageError): ReceiptImageValidator().validate(b"")

def test_rejects_file_over_configured_limit() -> None:
    with pytest.raises(ImageTooLargeError): ReceiptImageValidator(max_size_bytes=3).validate(b"1234")

def test_rejects_corrupt_supported_image() -> None:
    with pytest.raises(InvalidImageError): ReceiptImageValidator().validate(b"\x89PNG\r\n\x1a\ncorrupt")

def test_rejects_valid_unsupported_image() -> None:
    with pytest.raises(UnsupportedImageFormatError): ReceiptImageValidator().validate(synthetic_image("GIF"))
