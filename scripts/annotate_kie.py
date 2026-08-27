#!/usr/bin/env python3
"""Local, prediction-free GUI for independent KIE annotation A or B."""

from __future__ import annotations

import argparse
import json
import sys
import tkinter as tk
from datetime import datetime
from pathlib import Path
from tkinter import messagebox, ttk
from typing import Any

from PIL import Image, ImageDraw, ImageFont, ImageTk


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from ai.kie.gold_workflow import annotation_errors, load_json


FIELD_NAMES = (
    "merchant_name",
    "receipt_date",
    "total_amount",
    "invoice_id",
    "merchant_address",
)
FIELD_LABELS = {
    "merchant_name": "Tên cửa hàng",
    "receipt_date": "Ngày giao dịch",
    "total_amount": "Tổng tiền",
    "invoice_id": "Mã hóa đơn/giao dịch",
    "merchant_address": "Địa chỉ cửa hàng",
}
STATUSES = ("", "PRESENT", "NOT_PRESENT", "UNREADABLE", "AMBIGUOUS", "UNKNOWN")


def _annotation_path(slot: str, test_id: str) -> Path:
    return (
        PROJECT_ROOT
        / "data"
        / "kie_annotations"
        / f"annotator_{slot}"
        / f"{test_id}.json"
    )


def _ocr_path(test_id: str) -> Path:
    return PROJECT_ROOT / "results" / "ocr_outputs" / f"{test_id}.json"


def _image_path(test_id: str) -> Path:
    return PROJECT_ROOT / "data" / "test_set" / "images" / f"{test_id}.jpg"


def _split_ids(value: str) -> list[str]:
    return [item.strip() for item in value.replace("\n", ",").split(",") if item.strip()]


def _candidate_values(field_name: str, value: str) -> list[str | int]:
    raw_values = [line.strip() for line in value.splitlines() if line.strip()]
    if field_name == "total_amount":
        return [int(item.replace(",", "").replace(".", "")) for item in raw_values]
    return raw_values


class FieldForm:
    def __init__(self, parent: ttk.Frame, field_name: str) -> None:
        self.field_name = field_name
        self.status = tk.StringVar()
        self.transcribed = tk.StringVar()
        self.normalized = tk.StringVar()
        self.source_blocks = tk.StringVar()

        parent.columnconfigure(1, weight=1)
        row = 0
        ttk.Label(parent, text="Status").grid(row=row, column=0, sticky="nw", padx=8, pady=6)
        ttk.Combobox(
            parent,
            textvariable=self.status,
            values=STATUSES[1:],
            state="readonly",
            width=24,
        ).grid(row=row, column=1, sticky="ew", padx=8, pady=6)

        row += 1
        ttk.Label(parent, text="Đọc từ ảnh").grid(row=row, column=0, sticky="nw", padx=8, pady=6)
        ttk.Entry(parent, textvariable=self.transcribed).grid(
            row=row, column=1, sticky="ew", padx=8, pady=6
        )

        row += 1
        normalized_hint = "JSON integer VND" if field_name == "total_amount" else "Giá trị canonical"
        ttk.Label(parent, text=f"Chuẩn hóa\n({normalized_hint})").grid(
            row=row, column=0, sticky="nw", padx=8, pady=6
        )
        ttk.Entry(parent, textvariable=self.normalized).grid(
            row=row, column=1, sticky="ew", padx=8, pady=6
        )

        row += 1
        ttk.Label(parent, text="Real OCR block IDs\n(cách nhau bằng dấu phẩy)").grid(
            row=row, column=0, sticky="nw", padx=8, pady=6
        )
        ttk.Entry(parent, textvariable=self.source_blocks).grid(
            row=row, column=1, sticky="ew", padx=8, pady=6
        )

        row += 1
        ttk.Label(parent, text="Candidate values\n(mỗi dòng một giá trị)").grid(
            row=row, column=0, sticky="nw", padx=8, pady=6
        )
        self.candidates = tk.Text(parent, height=4, wrap="word")
        self.candidates.grid(row=row, column=1, sticky="nsew", padx=8, pady=6)

        row += 1
        ttk.Label(parent, text="Ghi chú").grid(row=row, column=0, sticky="nw", padx=8, pady=6)
        self.note = tk.Text(parent, height=6, wrap="word")
        self.note.grid(row=row, column=1, sticky="nsew", padx=8, pady=6)
        parent.rowconfigure(row, weight=1)

    def load(self, field: dict[str, Any]) -> None:
        self.status.set(field.get("annotation_status") or "")
        self.transcribed.set(field.get("transcribed_value") or "")
        normalized = field.get("normalized_value")
        self.normalized.set("" if normalized is None else str(normalized))
        self.source_blocks.set(", ".join(field.get("source_block_ids", [])))
        self.candidates.delete("1.0", "end")
        self.candidates.insert(
            "1.0", "\n".join(str(item) for item in field.get("candidate_values", []))
        )
        self.note.delete("1.0", "end")
        self.note.insert("1.0", field.get("annotator_note") or "")

    def apply(self, field: dict[str, Any]) -> None:
        status = self.status.get().strip() or None
        transcribed = self.transcribed.get().strip() or None
        normalized_text = self.normalized.get().strip()
        if self.field_name == "total_amount" and normalized_text:
            normalized: str | int | None = int(
                normalized_text.replace(",", "").replace(".", "")
            )
        else:
            normalized = normalized_text or None

        field.update(
            annotation_status=status,
            transcribed_value=transcribed,
            normalized_value=normalized,
            source_block_ids=_split_ids(self.source_blocks.get()),
            candidate_values=_candidate_values(
                self.field_name, self.candidates.get("1.0", "end")
            ),
            annotator_note=self.note.get("1.0", "end").strip() or None,
        )


class AnnotationApp:
    def __init__(
        self,
        root: tk.Tk,
        *,
        slot: str,
        annotator_id: str,
        initial_test_id: str | None,
    ) -> None:
        self.root = root
        self.slot = slot
        self.test_ids = [f"R{index:03d}" for index in range(1, 41)]
        self.current_index = self._initial_index(initial_test_id)
        self.document: dict[str, Any] = {}
        self.ocr: dict[str, Any] = {}
        self.photo: ImageTk.PhotoImage | None = None

        root.title(f"VietReceipt W3 — Independent annotator {slot.upper()}")
        root.geometry("1450x900")
        root.minsize(1100, 700)

        self.test_id_var = tk.StringVar()
        self.annotator_var = tk.StringVar(value=annotator_id)
        self.provenance_var = tk.StringVar()
        self.show_blocks_var = tk.BooleanVar(value=True)
        self.progress_var = tk.StringVar()

        self._build_ui()
        self._load_current()
        root.bind("<Control-s>", lambda _event: self._save(validate=False))
        root.bind("<Control-Return>", lambda _event: self._save(validate=True))

    def _initial_index(self, requested: str | None) -> int:
        if requested:
            return self.test_ids.index(requested)
        for index, test_id in enumerate(self.test_ids):
            document = load_json(_annotation_path(self.slot, test_id))
            if any(
                document["fields"][field_name].get("annotation_status") is None
                for field_name in FIELD_NAMES
            ):
                return index
        return 0

    def _build_ui(self) -> None:
        toolbar = ttk.Frame(self.root, padding=6)
        toolbar.pack(fill="x")
        ttk.Button(toolbar, text="← Trước", command=lambda: self._navigate(-1)).pack(side="left")
        ttk.Label(toolbar, text="Receipt:").pack(side="left", padx=(12, 4))
        selector = ttk.Combobox(
            toolbar,
            textvariable=self.test_id_var,
            values=self.test_ids,
            state="readonly",
            width=8,
        )
        selector.pack(side="left")
        selector.bind("<<ComboboxSelected>>", self._select_test_id)
        ttk.Button(toolbar, text="Sau →", command=lambda: self._navigate(1)).pack(
            side="left", padx=4
        )
        ttk.Checkbutton(
            toolbar,
            text="Hiện block trên ảnh",
            variable=self.show_blocks_var,
            command=self._render_image,
        ).pack(side="left", padx=16)
        ttk.Label(toolbar, textvariable=self.progress_var).pack(side="right")

        paned = ttk.Panedwindow(self.root, orient="horizontal")
        paned.pack(fill="both", expand=True, padx=6, pady=(0, 6))

        left = ttk.Frame(paned)
        right = ttk.Frame(paned)
        paned.add(left, weight=3)
        paned.add(right, weight=2)

        image_frame = ttk.Frame(left)
        image_frame.pack(fill="both", expand=True)
        self.canvas = tk.Canvas(image_frame, background="#202020")
        image_y = ttk.Scrollbar(image_frame, orient="vertical", command=self.canvas.yview)
        image_x = ttk.Scrollbar(image_frame, orient="horizontal", command=self.canvas.xview)
        self.canvas.configure(yscrollcommand=image_y.set, xscrollcommand=image_x.set)
        self.canvas.grid(row=0, column=0, sticky="nsew")
        image_y.grid(row=0, column=1, sticky="ns")
        image_x.grid(row=1, column=0, sticky="ew")
        image_frame.rowconfigure(0, weight=1)
        image_frame.columnconfigure(0, weight=1)

        block_frame = ttk.LabelFrame(left, text="Real OCR blocks — dùng ID này cho source_block_ids")
        block_frame.pack(fill="x", pady=(6, 0))
        self.block_text = tk.Text(block_frame, height=10, wrap="none", font=("Consolas", 9))
        block_scroll = ttk.Scrollbar(block_frame, orient="vertical", command=self.block_text.yview)
        self.block_text.configure(yscrollcommand=block_scroll.set, state="disabled")
        self.block_text.pack(side="left", fill="both", expand=True)
        block_scroll.pack(side="right", fill="y")

        meta = ttk.LabelFrame(right, text=f"Metadata annotator {self.slot.upper()}", padding=6)
        meta.pack(fill="x")
        meta.columnconfigure(1, weight=1)
        ttk.Label(meta, text="annotator_id").grid(row=0, column=0, sticky="w", padx=4, pady=4)
        ttk.Entry(meta, textvariable=self.annotator_var).grid(
            row=0, column=1, sticky="ew", padx=4, pady=4
        )
        ttk.Label(meta, text="data_provenance").grid(row=1, column=0, sticky="w", padx=4, pady=4)
        ttk.Entry(meta, textvariable=self.provenance_var).grid(
            row=1, column=1, sticky="ew", padx=4, pady=4
        )

        notebook = ttk.Notebook(right)
        notebook.pack(fill="both", expand=True, pady=6)
        self.forms: dict[str, FieldForm] = {}
        for field_name in FIELD_NAMES:
            frame = ttk.Frame(notebook)
            notebook.add(frame, text=FIELD_LABELS[field_name])
            self.forms[field_name] = FieldForm(frame, field_name)

        actions = ttk.Frame(right)
        actions.pack(fill="x")
        ttk.Button(
            actions,
            text="Lưu nháp  Ctrl+S",
            command=lambda: self._save(validate=False),
        ).pack(side="left")
        ttk.Button(
            actions,
            text="Kiểm tra & hoàn thành  Ctrl+Enter",
            command=lambda: self._save(validate=True),
        ).pack(side="right")

    def _select_test_id(self, _event: tk.Event[Any]) -> None:
        self.current_index = self.test_ids.index(self.test_id_var.get())
        self._load_current()

    def _navigate(self, offset: int) -> None:
        self.current_index = max(0, min(39, self.current_index + offset))
        self._load_current()

    def _load_current(self) -> None:
        test_id = self.test_ids[self.current_index]
        self.test_id_var.set(test_id)
        self.document = load_json(_annotation_path(self.slot, test_id))
        self.ocr = load_json(_ocr_path(test_id))
        existing_id = self.document.get("annotator_id") or self.annotator_var.get()
        self.annotator_var.set(existing_id)
        self.provenance_var.set(self.document.get("data_provenance") or "")
        for field_name, form in self.forms.items():
            form.load(self.document["fields"][field_name])
        self._render_image()
        self._render_blocks()
        self._update_progress()

    def _render_image(self) -> None:
        test_id = self.test_ids[self.current_index]
        image = Image.open(_image_path(test_id)).convert("RGB")
        target_width = 720
        scale = max(1.0, target_width / image.width)
        display = image.resize(
            (round(image.width * scale), round(image.height * scale)),
            Image.Resampling.LANCZOS,
        )
        if self.show_blocks_var.get():
            draw = ImageDraw.Draw(display)
            font = ImageFont.load_default(size=12)
            for block in self.ocr.get("blocks", []):
                points = [
                    (
                        round(point["x"] * display.width),
                        round(point["y"] * display.height),
                    )
                    for point in block["polygon"]
                ]
                draw.line(points + [points[0]], fill="#ff2d55", width=2)
                x, y = points[0]
                label = block["block_id"].replace("block_", "b")
                box = draw.textbbox((x, y), label, font=font)
                draw.rectangle(box, fill="#ff2d55")
                draw.text((x, y), label, fill="white", font=font)
        self.photo = ImageTk.PhotoImage(display)
        self.canvas.delete("all")
        self.canvas.create_image(0, 0, anchor="nw", image=self.photo)
        self.canvas.configure(scrollregion=(0, 0, display.width, display.height))
        self.canvas.xview_moveto(0)
        self.canvas.yview_moveto(0)

    def _render_blocks(self) -> None:
        lines = [
            f"{block['block_id']:>9}  order={block['reading_order']:>2}  {block['text']}"
            for block in sorted(
                self.ocr.get("blocks", []), key=lambda item: item["reading_order"]
            )
        ]
        self.block_text.configure(state="normal")
        self.block_text.delete("1.0", "end")
        self.block_text.insert("1.0", "\n".join(lines))
        self.block_text.configure(state="disabled")

    def _apply_form(self, completed: bool) -> dict[str, Any]:
        document = json.loads(json.dumps(self.document, ensure_ascii=False))
        document["annotator_id"] = self.annotator_var.get().strip()
        document["data_provenance"] = self.provenance_var.get().strip()
        if completed:
            document["annotated_at"] = datetime.now().astimezone().isoformat()
        for field_name, form in self.forms.items():
            form.apply(document["fields"][field_name])
        return document

    def _save(self, *, validate: bool) -> None:
        try:
            document = self._apply_form(completed=validate)
        except ValueError as exc:
            messagebox.showerror("Sai định dạng", str(exc), parent=self.root)
            return
        if validate:
            errors = annotation_errors(document, self.ocr)
            if errors:
                messagebox.showerror(
                    "Phiếu chưa hợp lệ",
                    "\n".join(errors[:25]),
                    parent=self.root,
                )
                return
        path = _annotation_path(self.slot, self.test_ids[self.current_index])
        path.write_text(
            json.dumps(document, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        self.document = document
        self._update_progress()
        messagebox.showinfo(
            "Đã lưu",
            "Phiếu hợp lệ và hoàn thành." if validate else "Đã lưu nháp.",
            parent=self.root,
        )

    def _update_progress(self) -> None:
        completed = 0
        for test_id in self.test_ids:
            document = load_json(_annotation_path(self.slot, test_id))
            if all(
                document["fields"][field_name].get("annotation_status") is not None
                for field_name in FIELD_NAMES
            ):
                completed += 1
        self.progress_var.set(f"Đã điền status: {completed}/40")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--slot", choices=("a", "b"), required=True)
    parser.add_argument("--annotator-id", default="")
    parser.add_argument(
        "--test-id",
        choices=[f"R{index:03d}" for index in range(1, 41)],
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    root = tk.Tk()
    AnnotationApp(
        root,
        slot=args.slot,
        annotator_id=args.annotator_id,
        initial_test_id=args.test_id,
    )
    root.mainloop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
