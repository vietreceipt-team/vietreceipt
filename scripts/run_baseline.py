"""Run PaddleOCR baseline on the frozen test set and generate canonical structured JSON output."""
import os
os.environ["FLAGS_enable_pir_api"] = "0"

import json
import logging
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from PIL import Image
from paddleocr import PaddleOCR

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).resolve().parents[1]
TEST_IMAGES_DIR = PROJECT_ROOT / "data" / "test_set" / "images"
OUTPUT_DIR = PROJECT_ROOT / "results" / "ocr_outputs"


def process_image(ocr_engine: PaddleOCR, image_path: Path) -> dict[str, Any]:
    start_time = time.time()

    with Image.open(image_path) as img:
        img_width, img_height = img.size

    result = ocr_engine.ocr(str(image_path))
    duration_ms = int((time.time() - start_time) * 1000)

    receipt_id = image_path.stem
    ocr_run_id = f"run_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}"

    schema: dict[str, Any] = {
        "schema_version": "1.0.0",
        "receipt_id": receipt_id,
        "ocr_run_id": ocr_run_id,
        "engine": "paddleocr_v4",
        "image_size": {
            "width": img_width,
            "height": img_height
        },
        "duration_ms": duration_ms,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "blocks": []
    }

    if not result or not result[0]:
        return schema

    res = result[0]
    rec_texts = res.get("rec_texts", []) if hasattr(res, "get") else res["rec_texts"]
    rec_scores = res.get("rec_scores", []) if hasattr(res, "get") else res["rec_scores"]
    rec_polys = res.get("rec_polys") if hasattr(res, "get") else res.get("rec_polys", None)

    if not rec_texts:
        return schema

    for idx, text in enumerate(rec_texts):
        confidence = rec_scores[idx] if idx < len(rec_scores) else 1.0

        if rec_polys is not None and idx < len(rec_polys):
            poly_pixel = rec_polys[idx]  # 4 điểm [[x1,y1], [x2,y2], [x3,y3], [x4,y4]]
            polygon_norm = [
                [
                    round(float(pt[0]) / img_width, 4) if img_width > 0 else 0.0,
                    round(float(pt[1]) / img_height, 4) if img_height > 0 else 0.0
                ]
                for pt in poly_pixel
            ]
        else:
            polygon_norm = []

        schema["blocks"].append({
            "block_id": idx,
            "text": str(text),
            "polygon": polygon_norm,
            "confidence": round(float(confidence), 4),
            "reading_order": idx
        })

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