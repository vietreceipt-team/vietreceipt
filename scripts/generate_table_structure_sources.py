"""Reproduce public synthetic ruling PNGs and source/expectation hashes.

Images and evidence are generated from the same literal scene, not OCR output.
Pillow is a generation-only dependency; the strategy never consumes pixels.
"""

import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from tests.kie_table_structure_fixtures import cases  # noqa: E402


def generate(output):
    from PIL import __version__ as pillow_version
    from PIL import Image, ImageDraw, ImageFont

    output.mkdir(parents=True, exist_ok=True)
    manifest = {
        "version": "synthetic-table-rulings-1.0.0",
        "synthetic": True,
        "license": "project-authored synthetic software fixtures; no private data",
        "generator": "scripts/generate_table_structure_sources.py",
        "generator_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "pillow_version": pillow_version,
        "split": "development",
        "base_document_id": "ruling-base-1",
        "template_id": "synthetic-five-column-1",
        "qa_status": "NOT_INDEPENDENTLY_REVIEWED",
        "evidence_origin": "literal scene coordinates; NOT an OCR run",
        "coordinate_system": "normalized original page; top-left origin",
        "records": [],
    }
    for name in ("bordered", "borderless", "horizontal", "vertical"):
        case = cases()[name]
        source = case["evidence"]
        image = Image.new("RGB", (1000, 1400), "white")
        draw = ImageDraw.Draw(image)
        draw.text(
            (40, 210),
            "SYNTHETIC DEVELOPMENT FIXTURE - NO FINANCIAL VALUE",
            fill="black",
        )
        xs = [35, 365, 505, 660, 815, 980]
        ys = [265, 330, 445, 565]
        if name in {"bordered", "horizontal"}:
            for y in ys:
                draw.line((xs[0], y, xs[-1], y), fill="black", width=2)
        if name in {"bordered", "vertical"}:
            for x in xs:
                draw.line((x, ys[0], x, ys[-1]), fill="black", width=2)
        font = ImageFont.load_default(size=14)
        for block in source["blocks"]:
            left = min(p["x"] for p in block["polygon"])
            top = min(p["y"] for p in block["polygon"])
            draw.text(
                (round(left * 1000), round(top * 1400)),
                block["text"],
                fill="black",
                font=font,
            )
        artifacts = {}
        image_path = output / f"{name}.png"
        image.save(image_path)
        for kind, value in (("evidence", source), ("expected", case["gold"])):
            path = output / f"{name}.{kind}.json"
            path.write_text(
                json.dumps(value, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
                newline="\n",
            )
            artifacts[kind] = {
                "path": path.name,
                "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
            }
        artifacts["image"] = {
            "path": image_path.name,
            "sha256": hashlib.sha256(image_path.read_bytes()).hexdigest(),
        }
        manifest["records"].append({"ruling": name, **artifacts})
    (output / "provenance.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
        newline="\n",
    )


if __name__ == "__main__":
    generate(ROOT / "tests/fixtures/table_structure")
