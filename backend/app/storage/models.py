from dataclasses import dataclass
from enum import Enum


class ImageFormat(str, Enum):
    JPEG = "JPEG"
    PNG = "PNG"
    WEBP = "WEBP"

    @property
    def content_type(self) -> str:
        return {self.JPEG: "image/jpeg", self.PNG: "image/png", self.WEBP: "image/webp"}[self]

    @property
    def extension(self) -> str:
        return {self.JPEG: "jpg", self.PNG: "png", self.WEBP: "webp"}[self]


@dataclass(frozen=True, slots=True)
class ValidatedImage:
    data: bytes
    format: ImageFormat
    width_px: int
    height_px: int

    @property
    def content_type(self) -> str:
        return self.format.content_type
