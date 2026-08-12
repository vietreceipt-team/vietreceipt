
"""Run PaddleOCR baseline on the frozen test set and generate structured JSON output."""
import os
os.environ["FLAGS_enable_pir_api"] = "0"

import json
import logging
import time
from pathlib import Path
from typing import Any

from paddleocr import PaddleOCR


logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)


PROJECT_ROOT = Path(__file__).resolve().parents[1]
TEST_IMAGES_DIR = PROJECT_ROOT / "data" / "test_set" / "images"
OUTPUT_DIR = PROJECT_ROOT / "results" / "ocr_outputs"


def process_image(ocr_engine: PaddleOCR, image_path: Path) -> dict[str, Any]:
    start_time = time.time()

    result = ocr_engine.ocr(str(image_path))
    processing_time_ms = int((time.time() - start_time) * 1000)

    schema: dict[str, Any] = {
        "status": "success",
        "metadata": {
            "file_name": image_path.name,
            "engine": "paddleocr_v4",
            "processing_time_ms": processing_time_ms,
        },
        "detections": [],
    }

    if not result:
        return schema

    
    res = result[0]

    rec_texts = res.get("rec_texts", []) if hasattr(res, "get") else res["rec_texts"]
    rec_scores = res.get("rec_scores", []) if hasattr(res, "get") else res["rec_scores"]
    # Ưu tiên rec_polys (4 điểm góc); nếu không có thì dùng rec_boxes (x1,y1,x2,y2) rồi tự suy ra 4 góc
    rec_polys = res.get("rec_polys") if hasattr(res, "get") else res.get("rec_polys", None)

    if not rec_texts:
        return schema

    for idx, text in enumerate(rec_texts, start=1):
        confidence = rec_scores[idx - 1] if idx - 1 < len(rec_scores) else 1.0

        if rec_polys is not None and idx - 1 < len(rec_polys):
            poly = rec_polys[idx - 1]  # numpy array shape (4, 2)
            box = [[int(pt[0]), int(pt[1])] for pt in poly]
        else:
            box = []

        schema["detections"].append(
            {
                "box": box,
                "text": str(text),
                "confidence": round(float(confidence), 4),
            }
        )

    return schema


def main() -> None:
    if not TEST_IMAGES_DIR.exists():
        logger.error(f"Test directory not found: {TEST_IMAGES_DIR}")
        raise SystemExit(1)

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    logger.info("Initializing PaddleOCR engine...")
    ocr_engine = PaddleOCR(use_textline_orientation=True, lang="vi", enable_mkldnn=False)
    image_paths = sorted(TEST_IMAGES_DIR.glob("*.*"))
    valid_extensions = {".jpg", ".jpeg", ".png"}
    target_images = [p for p in image_paths if p.suffix.lower() in valid_extensions]

    if not target_images:
        logger.warning(f"No valid images found in {TEST_IMAGES_DIR}")
        return

    logger.info(f"Starting OCR processing for {len(target_images)} images.")

    for img_path in target_images:
        logger.info(f"Processing: {img_path.name}")
        schema = process_image(ocr_engine, img_path)

        output_file = OUTPUT_DIR / f"{img_path.stem}.json"
        with output_file.open("w", encoding="utf-8") as handle:
            json.dump(schema, handle, ensure_ascii=False, indent=2)

    logger.info(f"Processing complete. Artifacts saved to: {OUTPUT_DIR}")


if __name__ == "__main__":
    main()