#!/usr/bin/env python3
"""Freeze the Week-1 OCR test set before any OCR engine is evaluated."""

from __future__ import annotations

import csv
import hashlib
import shutil
import argparse
from collections import Counter
from pathlib import Path


PROJECT = Path(__file__).resolve().parents[1]
CANDIDATE_MANIFEST = PROJECT / "data" / "manifests" / "candidate_pool.csv"
TEST_ROOT = PROJECT / "data" / "test_set"
IMAGE_DIR = TEST_ROOT / "images"
TEST_MANIFEST = TEST_ROOT / "test_manifest.csv"
CHECKSUM_FILE = TEST_ROOT / "SHA256SUMS.txt"


# This list is intentionally explicit. Changing it creates a different test set.
SELECTION: list[tuple[str, str]] = [
    # Twenty mixed-layout images selected before running OCR.
    ("G01", "standard_mixed_layout"),
    ("G02", "standard_mixed_layout"),
    ("G03", "standard_mixed_layout"),
    ("G04", "standard_mixed_layout"),
    ("G05", "standard_mixed_layout"),
    ("G06", "standard_mixed_layout"),
    ("G07", "standard_mixed_layout"),
    ("G08", "standard_mixed_layout"),
    ("G09", "standard_mixed_layout"),
    ("G10", "standard_mixed_layout"),
    ("G11", "standard_mixed_layout"),
    ("G12", "standard_mixed_layout"),
    ("G13", "standard_mixed_layout"),
    ("G15", "standard_mixed_layout"),
    ("G16", "standard_mixed_layout"),
    ("LC03", "standard_mixed_layout"),
    ("LC09", "standard_mixed_layout"),
    ("LC11", "standard_mixed_layout"),
    ("LC12", "standard_mixed_layout"),
    ("LS12", "standard_mixed_layout"),
    # Twenty challenge images, five in each diagnostic stratum.
    ("LC01", "challenge_low_contrast"),
    ("LC02", "challenge_low_contrast"),
    ("LC04", "challenge_low_contrast"),
    ("LC05", "challenge_low_contrast"),
    ("LC07", "challenge_low_contrast"),
    ("LS01", "challenge_low_sharpness_or_distance"),
    ("LS04", "challenge_low_sharpness_or_distance"),
    ("LS06", "challenge_low_sharpness_or_distance"),
    ("LS08", "challenge_low_sharpness_or_distance"),
    ("LS15", "challenge_low_sharpness_or_distance"),
    ("UL01", "challenge_lighting_or_perspective"),
    ("UL06", "challenge_lighting_or_perspective"),
    ("UL10", "challenge_lighting_or_perspective"),
    ("UL12", "challenge_lighting_or_perspective"),
    ("UL15", "challenge_lighting_or_perspective"),
    ("LR02", "challenge_long_receipt"),
    ("LR06", "challenge_long_receipt"),
    ("LR08", "challenge_long_receipt"),
    ("LR14", "challenge_long_receipt"),
    ("LR16", "challenge_long_receipt"),
]


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def reconstruct_existing() -> None:
    """Rebuild ignored local images from an authorized source snapshot."""
    if not TEST_MANIFEST.exists():
        raise SystemExit(f"Existing manifest not found: {TEST_MANIFEST}")
    with TEST_MANIFEST.open(encoding="utf-8", newline="") as handle:
        manifest_rows = list(csv.DictReader(handle))
    if len(manifest_rows) != 40:
        raise SystemExit(f"Expected 40 manifest rows, found {len(manifest_rows)}")

    IMAGE_DIR.mkdir(parents=True, exist_ok=True)
    for row in manifest_rows:
        source = PROJECT / Path(row["source_file"])
        destination = TEST_ROOT / Path(row["test_file"])
        if not source.is_file():
            raise SystemExit(
                f"Authorized source image not found for {row['test_id']}: {source}"
            )
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, destination)
        copied_digest = sha256(destination)
        if copied_digest != row["sha256"]:
            raise SystemExit(f"Checksum mismatch for {row['test_id']}")

    print(f"reconstructed_images={len(manifest_rows)}")
    print(f"image_dir={IMAGE_DIR}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--reconstruct-existing",
        action="store_true",
        help="Rebuild ignored local images from the committed manifest.",
    )
    args = parser.parse_args()
    if args.reconstruct_existing:
        reconstruct_existing()
        return

    if TEST_ROOT.exists():
        raise SystemExit(
            f"Refusing to overwrite the frozen test set: {TEST_ROOT}\n"
            "Delete or rename it manually only if a new test-set version is intended."
        )

    with CANDIDATE_MANIFEST.open(encoding="utf-8", newline="") as handle:
        candidate_rows = list(csv.DictReader(handle))
    by_id = {row["candidate_id"]: row for row in candidate_rows}

    selected_ids = [candidate_id for candidate_id, _ in SELECTION]
    if len(SELECTION) != 40:
        raise SystemExit(f"Expected 40 selections, found {len(SELECTION)}")
    if len(set(selected_ids)) != len(selected_ids):
        raise SystemExit("Duplicate candidate ID in SELECTION")
    missing = [candidate_id for candidate_id in selected_ids if candidate_id not in by_id]
    if missing:
        raise SystemExit(f"Unknown candidate IDs: {missing}")

    IMAGE_DIR.mkdir(parents=True)
    manifest_rows: list[dict[str, str]] = []
    checksum_lines: list[str] = []

    for index, (candidate_id, stratum) in enumerate(SELECTION, start=1):
        candidate = by_id[candidate_id]
        source = PROJECT / candidate["source_file"]
        extension = source.suffix.lower()
        test_id = f"R{index:03d}"
        destination = IMAGE_DIR / f"{test_id}{extension}"
        shutil.copy2(source, destination)

        copied_digest = sha256(destination)
        if copied_digest != candidate["sha256"]:
            raise SystemExit(f"Checksum mismatch after copying {candidate_id}")

        checksum_lines.append(f"{copied_digest}  images/{destination.name}")
        manifest_rows.append(
            {
                "test_id": test_id,
                "candidate_id": candidate_id,
                "selection_stratum": stratum,
                "source_file": candidate["source_file"],
                "test_file": destination.relative_to(TEST_ROOT).as_posix(),
                "sha256": copied_digest,
                "width": candidate["width"],
                "height": candidate["height"],
                "brightness": candidate["brightness"],
                "contrast": candidate["contrast"],
                "sharpness": candidate["sharpness"],
                "illumination_range": candidate["illumination_range"],
                "merchant_type_manual": "",
                "quality_label_manual": "",
                "ground_truth_status": "not_started",
                "notes": "",
            }
        )

    fieldnames = list(manifest_rows[0].keys())
    with TEST_MANIFEST.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(manifest_rows)

    CHECKSUM_FILE.write_text("\n".join(checksum_lines) + "\n", encoding="utf-8")

    counts = Counter(stratum for _, stratum in SELECTION)

    print(f"test_images={len(manifest_rows)}")
    for stratum, count in counts.items():
        print(f"{stratum}={count}")
    print(f"test_root={TEST_ROOT}")
    print(f"manifest={TEST_MANIFEST}")
    print(f"checksums={CHECKSUM_FILE}")


if __name__ == "__main__":
    main()
