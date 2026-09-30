import io
import warnings
from pathlib import PurePosixPath

from PIL import Image
from pypdf import PdfReader

from .errors import V2Error

TYPES = {
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".png": "image/png",
    ".pdf": "application/pdf",
}


def validate_upload(
    filename, mime, data, max_bytes, max_pixels=40_000_000, max_pages=100
):
    filename = PurePosixPath((filename or "").replace("\\", "/")).name
    ext = PurePosixPath(filename).suffix.lower()
    if (
        not filename
        or len(filename) > 255
        or any(ord(c) < 32 for c in filename)
        or TYPES.get(ext) != mime
    ):
        raise V2Error(
            "INVALID_FILE",
            "Expected a JPEG, PNG or PDF with matching extension and MIME type.",
        )
    if not data:
        raise V2Error("INVALID_FILE", "The source file is empty.")
    if len(data) > max_bytes:
        raise V2Error("FILE_TOO_LARGE", "The source exceeds the upload limit.", 413)
    try:
        if mime == "application/pdf":
            if not data.startswith(b"%PDF-"):
                raise ValueError()
            pdf = PdfReader(io.BytesIO(data), strict=True)
            if pdf.is_encrypted or not 0 < len(pdf.pages) <= max_pages:
                raise ValueError()
            for page in pdf.pages:
                if float(page.mediabox.width) <= 0 or float(page.mediabox.height) <= 0:
                    raise ValueError()
        else:
            with warnings.catch_warnings():
                warnings.simplefilter("error", Image.DecompressionBombWarning)
                with Image.open(io.BytesIO(data)) as img:
                    if (
                        Image.MIME.get(img.format) != mime
                        or img.width * img.height > max_pixels
                    ):
                        raise ValueError()
                    img.verify()
                with Image.open(io.BytesIO(data)) as img:
                    img.load()
    except Exception as exc:
        raise V2Error(
            "INVALID_FILE",
            "The source is malformed, encrypted or exceeds document limits.",
        ) from exc
    return filename, ext
