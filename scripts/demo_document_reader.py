"""Run real TV3 reader and create a local source/evidence inspection page."""

import argparse
import html
import json
import mimetypes
from contextlib import closing
from pathlib import Path
from uuid import uuid4

import pypdfium2 as pdfium
from PIL import Image, ImageOps

from ai.document_reader import DocumentReader, ReaderConfig


def write_preview(source, document, output):
    output.mkdir(parents=True, exist_ok=True)
    if source.suffix.lower() == ".pdf":
        with pdfium.PdfDocument(source) as pdf:
            for index in range(len(pdf)):
                with closing(pdf[index]) as page:
                    page.set_rotation(0)
                    with closing(page.render(scale=1.5)) as bitmap:
                        bitmap.to_pil().save(output / f"page-{index}.png")
    else:
        with Image.open(source) as image:
            ImageOps.exif_transpose(image).convert("RGB").save(output / "page-0.png")
    sections = []
    for page in document["pages"]:
        index = page["page_index"]
        polygons, items = [], []
        for block in page["evidence"]["blocks"]:
            bid, text = html.escape(block["block_id"]), html.escape(block["text"])
            points = " ".join(
                f"{p['x'] * 100},{p['y'] * 100}" for p in block["polygon"]
            )
            polygons.append(
                f'<a href="#{bid}"><polygon points="{points}"><title>{text}</title></polygon></a>'
            )
            items.append(f'<li id="{bid}"><code>{bid}</code> {text}</li>')
        sections.append(
            f'<section><h2>Trang {index + 1} · {html.escape(page["evidence"]["engine"]["name"])}</h2><div class="grid"><div class="source"><img src="page-{index}.png" alt="Tài liệu nguồn trang {index + 1}"><svg viewBox="0 0 100 100" preserveAspectRatio="none">{"".join(polygons)}</svg></div><ol>{"".join(items)}</ol></div></section>'
        )
    markup = """<!doctype html><html lang="vi"><meta charset="utf-8"><meta name="viewport" content="width=device-width"><title>VietReceipt · TV3 evidence demo</title><style>
body{font:16px system-ui;margin:32px;background:#f3f5f8;color:#18283d}main{max-width:1400px;margin:auto}h1{color:#174e70}section{background:white;padding:24px;margin:24px 0;border-radius:12px}.grid{display:grid;grid-template-columns:1.2fr 1fr;gap:24px}.source{position:relative;align-self:start}.source img{width:100%;display:block}.source svg{position:absolute;inset:0;width:100%;height:100%}polygon{fill:#2299ff15;stroke:#1776ba;stroke-width:.12}polygon:hover{fill:#ffc40066}li{padding:7px;overflow-wrap:anywhere}li:target{background:#fff2b0}code{font-size:11px;color:#65778a}ol{max-height:85vh;overflow:auto;padding-left:30px}@media(max-width:800px){.grid{grid-template-columns:1fr}}
</style><main><h1>VietReceipt · Document Reader</h1><p>Demo TV3: chữ, vị trí và trang. Bấm vùng chữ để đối chiếu evidence. Đây chưa phải KIE hay nghiệm thu end-to-end toàn hệ thống.</p>"""
    (output / "index.html").write_text(
        markup + "".join(sections) + "</main></html>", encoding="utf-8"
    )


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("source", type=Path)
    p.add_argument("--output", type=Path, required=True)
    p.add_argument("--orientation", choices=["auto", "none"], default="auto")
    p.add_argument(
        "--evidence",
        type=Path,
        help="Preview an existing real run without rerunning OCR",
    )
    a = p.parse_args()
    if a.output.exists():
        p.error("Output already exists; use a new run directory")
    if a.evidence:
        from ai.document_reader.contract import validate_document

        document = json.loads(a.evidence.read_text(encoding="utf-8"))
        validate_document(document)
        metadata = {"evidence_source": str(a.evidence)}
    else:
        document, metadata = DocumentReader(
            config=ReaderConfig(orientation=a.orientation)
        ).process_with_metadata(
            a.source,
            content_type=mimetypes.guess_type(a.source)[0],
            receipt_id=uuid4(),
            ocr_run_id=uuid4(),
        )
    write_preview(a.source, document, a.output)
    for name, value in [("evidence", document), ("metadata", metadata)]:
        (a.output / f"{name}.json").write_text(
            json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8"
        )
    print(a.output / "index.html")


if __name__ == "__main__":
    main()
