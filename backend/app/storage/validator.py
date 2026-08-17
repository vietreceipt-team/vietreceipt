"""Content-based receipt image validation."""

from io import BytesIO
import warnings

from PIL import Image, UnidentifiedImageError

from .config import DEFAULT_MAX_IMAGE_PIXELS, DEFAULT_MAX_UPLOAD_SIZE_BYTES
from .errors import ImageTooLargeError, InvalidImageError, UnsupportedImageFormatError
from .models import ImageFormat, ValidatedImage


class ReceiptImageValidator:
    def __init__(
        self,
        max_size_bytes: int = DEFAULT_MAX_UPLOAD_SIZE_BYTES,
        max_pixels: int = DEFAULT_MAX_IMAGE_PIXELS,
    ) -> None:
        if max_size_bytes <= 0:
            raise ValueError("max_size_bytes must be greater than zero")
        if max_pixels <= 0:
            raise ValueError("max_pixels must be greater than zero")
        self._max_size_bytes = max_size_bytes
        self._max_pixels = max_pixels

    def validate(self, data: bytes) -> ValidatedImage:
        if not data:
            raise InvalidImageError("Image is empty")
        if len(data) > self._max_size_bytes:
            raise ImageTooLargeError(f"Image exceeds the {self._max_size_bytes}-byte upload limit")

        try:
            with warnings.catch_warnings():
                warnings.simplefilter("error", Image.DecompressionBombWarning)
                with Image.open(BytesIO(data)) as image:
                    detected_format = image.format
                    width, height = image.size
                    if width <= 0 or height <= 0 or width * height > self._max_pixels:
                        raise InvalidImageError(
                            f"Image dimensions exceed the {self._max_pixels}-pixel decode limit"
                        )
                    image.verify()
        except InvalidImageError:
            raise
        except (Image.DecompressionBombWarning, Image.DecompressionBombError) as exc:
            raise InvalidImageError("Image dimensions are unsafe to decode") from exc
        except (UnidentifiedImageError, OSError, SyntaxError, ValueError) as exc:
            raise InvalidImageError("Content is not a valid image") from exc

        try:
            image_format = ImageFormat(detected_format)
        except (ValueError, TypeError) as exc:
            raise UnsupportedImageFormatError(
                f"Decoded image format {detected_format!r} is unsupported"
            ) from exc
        return ValidatedImage(
            data=data,
            format=image_format,
            width_px=width,
            height_px=height,
        )
