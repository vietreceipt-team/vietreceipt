class ReceiptImageError(Exception):
    """Base error for receipt image validation and persistence."""

class InvalidImageError(ReceiptImageError):
    """The supplied bytes do not form a valid image."""

class ImageTooLargeError(InvalidImageError):
    """The image exceeds the configured byte limit."""

class UnsupportedImageFormatError(InvalidImageError):
    """The decoded image format is unsupported."""

class StorageUnavailableError(ReceiptImageError):
    """The storage backend could not complete an operation."""

class ObjectNotFoundError(ReceiptImageError):
    """The requested object key does not exist."""
