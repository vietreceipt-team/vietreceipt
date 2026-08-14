#!/usr/bin/env python3
"""Build a deterministic, duplicate-free candidate pool for manual OCR test-set review."""

from __future__ import annotations

import csv
import hashlib
import random
import shutil
from dataclasses import dataclass
from pathlib import Path

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageOps


PROJECT = Path(__file__).resolve().parents[1]
RAW_DIR = PROJECT / "data" / "raw"
CANDIDATE_DIR = PROJECT / "data" / "candidates"
MANIFEST_PATH = PROJECT / "data" / "manifests" / "candidate_pool.csv"
SHEET_DIR = PROJECT / "results" / "candidate_sheets"
SEED = 20260810
PER_GROUP = 16


@dataclass(frozen=True)
class Item:
    path: Path
    sha256: str
    width: int
    height: int
    aspect_ratio: float
    brightness: float
    contrast: float
    sharpness: float
    illumination_range: float


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def image_metrics(path: Path) -> tuple[int, int, float, float, float, float, float]:
    image = cv2.imread(str(path), cv2.IMREAD_GRAYSCALE)
    if image is None:
        raise ValueError(f"Cannot read image: {path}")

    height, width = image.shape
    scale = min(1.0, 900.0 / max(width, height))
    if scale < 1.0:
        image = cv2.resize(
            image,
            (max(1, round(width * scale)), max(1, round(height * scale))),
            interpolation=cv2.INTER_AREA,
        )

    brightness = float(np.mean(image))
    contrast = float(np.std(image))
    sharpness = float(cv2.Laplacian(image, cv2.CV_64F).var())

    grid_means: list[float] = []
    grid_size = 4
    h, w = image.shape
    for row in range(grid_size):
        for col in range(grid_size):
            y0, y1 = row * h // grid_size, (row + 1) * h // grid_size
            x0, x1 = col * w // grid_size, (col + 1) * w // grid_size
            block = image[y0:y1, x0:x1]
            if block.size:
                grid_means.append(float(np.mean(block)))
    illumination_range = max(grid_means) - min(grid_means)

    return (
        width,
        height,
        height / max(width, 1),
        brightness,
        contrast,
        sharpness,
        illumination_range,
    )


def take_unique(
    ordered: list[Item], used: set[str], count: int
) -> list[Item]:
    selected: list[Item] = []
    for item in ordered:
        if item.sha256 in used:
            continue
        selected.append(item)
        used.add(item.sha256)
        if len(selected) == count:
            break
    if len(selected) != count:
        raise RuntimeError(f"Only selected {len(selected)} of {count} requested items")
    return selected


def make_contact_sheet(group: str, rows: list[tuple[str, Item]]) -> None:
    columns = 4
    cell_width, cell_height = 340, 430
    header_height = 55
    sheet_rows = (len(rows) + columns - 1) // columns
    canvas = Image.new(
        "RGB",
        (columns * cell_width, header_height + sheet_rows * cell_height),
        "white",
    )
    draw = ImageDraw.Draw(canvas)
    font = ImageFont.load_default(size=14)
    title_font = ImageFont.load_default(size=22)
    draw.text((12, 12), f"Candidate group: {group}", fill="black", font=title_font)

    for index, (candidate_id, item) in enumerate(rows):
        row, col = divmod(index, columns)
        x = col * cell_width
        y = header_height + row * cell_height
        with Image.open(item.path) as source:
            thumb = ImageOps.contain(source.convert("RGB"), (310, 330))
        px = x + (cell_width - thumb.width) // 2
        py = y + 8
        canvas.paste(thumb, (px, py))
        label_y = y + 344
        draw.text((x + 8, label_y), candidate_id, fill="black", font=font)
        draw.text(
            (x + 8, label_y + 20),
            item.path.name[:38],
            fill="black",
            font=font,
        )
        draw.text(
            (x + 8, label_y + 40),
            f"C={item.contrast:.1f} S={item.sharpness:.1f} "
            f"B={item.brightness:.1f} I={item.illumination_range:.1f}",
            fill="black",
            font=font,
        )
        draw.text(
            (x + 8, label_y + 60),
            f"{item.width}x{item.height}  aspect={item.aspect_ratio:.2f}",
            fill="black",
            font=font,
        )

    canvas.save(SHEET_DIR / f"{group}.jpg", quality=90)


def main() -> None:
    paths = sorted(RAW_DIR.rglob("*.jpg"))
    if not paths:
        raise SystemExit(f"No JPG files found under {RAW_DIR}")

    unique_by_hash: dict[str, Path] = {}
    for path in paths:
        digest = file_sha256(path)
        unique_by_hash.setdefault(digest, path)

    items: list[Item] = []
    for digest, path in sorted(unique_by_hash.items(), key=lambda pair: pair[1].name):
        metrics = image_metrics(path)
        items.append(Item(path, digest, *metrics))

    used: set[str] = set()
    groups: dict[str, list[Item]] = {}
    groups["low_contrast"] = take_unique(
        sorted(items, key=lambda item: item.contrast), used, PER_GROUP
    )
    groups["low_sharpness"] = take_unique(
        sorted(items, key=lambda item: item.sharpness), used, PER_GROUP
    )
    groups["uneven_lighting"] = take_unique(
        sorted(items, key=lambda item: item.illumination_range, reverse=True),
        used,
        PER_GROUP,
    )
    groups["long_receipt"] = take_unique(
        sorted(items, key=lambda item: item.aspect_ratio, reverse=True),
        used,
        PER_GROUP,
    )
    rng = random.Random(SEED)
    general_order = list(items)
    rng.shuffle(general_order)
    groups["general"] = take_unique(general_order, used, PER_GROUP)

    if CANDIDATE_DIR.exists():
        shutil.rmtree(CANDIDATE_DIR)
    if SHEET_DIR.exists():
        shutil.rmtree(SHEET_DIR)
    CANDIDATE_DIR.mkdir(parents=True)
    SHEET_DIR.mkdir(parents=True)
    MANIFEST_PATH.parent.mkdir(parents=True, exist_ok=True)

    fieldnames = [
        "candidate_id",
        "heuristic_group",
        "source_file",
        "sha256",
        "width",
        "height",
        "aspect_ratio",
        "brightness",
        "contrast",
        "sharpness",
        "illumination_range",
        "manual_keep",
        "manual_quality",
        "manual_merchant_type",
        "manual_notes",
    ]
    with MANIFEST_PATH.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for group, group_items in groups.items():
            sheet_rows: list[tuple[str, Item]] = []
            group_dir = CANDIDATE_DIR / group
            group_dir.mkdir()
            prefix = "".join(part[0].upper() for part in group.split("_"))
            for number, item in enumerate(group_items, start=1):
                candidate_id = f"{prefix}{number:02d}"
                destination = group_dir / f"{candidate_id}_{item.path.name}"
                shutil.copy2(item.path, destination)
                sheet_rows.append((candidate_id, item))
                writer.writerow(
                    {
                        "candidate_id": candidate_id,
                        "heuristic_group": group,
                        "source_file": str(item.path.relative_to(PROJECT)),
                        "sha256": item.sha256,
                        "width": item.width,
                        "height": item.height,
                        "aspect_ratio": f"{item.aspect_ratio:.6f}",
                        "brightness": f"{item.brightness:.6f}",
                        "contrast": f"{item.contrast:.6f}",
                        "sharpness": f"{item.sharpness:.6f}",
                        "illumination_range": f"{item.illumination_range:.6f}",
                        "manual_keep": "",
                        "manual_quality": "",
                        "manual_merchant_type": "",
                        "manual_notes": "",
                    }
                )
            make_contact_sheet(group, sheet_rows)

    print(f"raw_images={len(paths)}")
    print(f"unique_images={len(items)}")
    print(f"candidate_images={sum(len(group) for group in groups.values())}")
    print(f"manifest={MANIFEST_PATH}")
    print(f"contact_sheets={SHEET_DIR}")


if __name__ == "__main__":
    main()
