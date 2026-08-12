"""Content-based receipt image validation."""

from io import BytesIO
from PIL import Image, UnidentifiedImageError
from .config import DEFAULT_MAX_IMAGE_SIZE_BYTES
from .errors import ImageTooLargeError, InvalidImageError, UnsupportedImageFormatError
from .models import ImageFormat, ValidatedImage

class ReceiptImageValidator:
    def __init__(self, max_size_bytes: int = DEFAULT_MAX_IMAGE_SIZE_BYTES) -> None:
        if max_size_bytes <= 0:
            raise ValueError("max_size_bytes must be greater than zero")
        self._max_size_bytes = max_size_bytes

    def validate(self, data: bytes) -> ValidatedImage:
        if not data:
            raise InvalidImageError("Image is empty")
        if len(data) > self._max_size_bytes:
            raise ImageTooLargeError(f"Image exceeds the {self._max_size_bytes}-byte limit")
        try:
            with Image.open(BytesIO(data)) as image:
                detected_format = image.format
                image.verify()
        except (UnidentifiedImageError, OSError, SyntaxError, ValueError) as exc:
            raise InvalidImageError("Content is not a valid image") from exc
        try:
            image_format = ImageFormat(detected_format)
        except (ValueError, TypeError) as exc:
            raise UnsupportedImageFormatError(f"Decoded image format {detected_format!r} is unsupported") from exc
        return ValidatedImage(data=data, format=image_format)
