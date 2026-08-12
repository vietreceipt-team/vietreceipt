import os
import json
import csv
import jiwer
from pathlib import Path

def get_text_from_ocr_json(json_path):
    try:
        with open(json_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
            if 'blocks' in data:
                texts = [item['text'] for item in data.get('blocks', [])]
            else:
                texts = [item['text'] for item in data.get('detections', [])]
            return " ".join(texts)
    except Exception as e:
        print(f"Error reading OCR file {json_path}: {e}")
        return ""

def get_text_from_gt(txt_path):
    try:
        with open(txt_path, 'r', encoding='utf-8') as f:
            return " ".join(f.read().split())
    except Exception as e:
        print(f"Error reading GT file {txt_path}: {e}")
        return ""

def main():
    project_root = Path(__file__).resolve().parents[1]
    gt_dir = project_root / "data" / "ground_truth"
    ocr_dir = project_root / "results" / "ocr_outputs"
    test_images_dir = project_root / "data" / "test_set" / "images"
    report_path = project_root / "results" / "evaluation_report.csv"

    expected_samples = []
    if test_images_dir.exists():
        valid_extensions = {".jpg", ".jpeg", ".png"}
        expected_samples = sorted([
            p.stem for p in test_images_dir.glob("*.*") if p.suffix.lower() in valid_extensions
        ])
    
    expected_count = len(expected_samples) if expected_samples else 40

    results = []
    missing_samples = []
    total_cer = 0.0
    total_wer = 0.0
    evaluated_count = 0

    print(f"\n=================== EVALUATION REPORT ===================")
    print(f"{'Image ID':<15} | {'CER (%)':<10} | {'WER (%)':<10} | {'Status':<10}")
    print("-" * 55)

    # Lặp qua toàn bộ mẫu trong frozen test set
    for sample_id in expected_samples:
        gt_path = gt_dir / f"{sample_id}.txt"
        ocr_path = ocr_dir / f"{sample_id}.json"

        if not gt_path.exists() or not ocr_path.exists():
            missing_samples.append(sample_id)
            print(f"{sample_id:<15} | {'N/A':<10} | {'N/A':<10} | MISSING DATA")
            continue

        gt_text = get_text_from_gt(gt_path)
        ocr_text = get_text_from_ocr_json(ocr_path)

        if not gt_text:
            missing_samples.append(sample_id)
            print(f"{sample_id:<15} | {'N/A':<10} | {'N/A':<10} | EMPTY GT")
            continue

        cer = jiwer.cer(gt_text, ocr_text) * 100
        wer = jiwer.wer(gt_text, ocr_text) * 100

        results.append({
            "image_id": sample_id,
            "cer": round(cer, 2),
            "wer": round(wer, 2)
        })

        total_cer += cer
        total_wer += wer
        evaluated_count += 1
        
        print(f"{sample_id:<15} | {cer:<10.2f} | {wer:<10.2f} | EVALUATED")

    run_status = "COMPLETE" if evaluated_count == expected_count else "INCOMPLETE"
    macro_cer = (total_cer / evaluated_count) if evaluated_count > 0 else 0.0
    macro_wer = (total_wer / evaluated_count) if evaluated_count > 0 else 0.0

    print("-" * 55)
    print(f"Scope Summary: Preliminary baseline / Probe on {evaluated_count}/{expected_count} samples")
    print(f"Status       : {run_status} (Evaluated: {evaluated_count}, Missing: {len(missing_samples)})")
    if evaluated_count > 0:
        print(f"MACRO AVG    | CER: {macro_cer:.2f}% | WER: {macro_wer:.2f}%")
    print("=========================================================\n")

    report_path.parent.mkdir(parents=True, exist_ok=True)
    with open(report_path, 'w', newline='', encoding='utf-8') as csvfile:
        fieldnames = ['image_id', 'cer', 'wer']
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        
        writer.writeheader()
        
        for row in results:
            writer.writerow(row)
            
        # Ghi Summary & Metadata làm rõ phạm vi đánh giá
        writer.writerow({'image_id': '--- METADATA ---', 'cer': '', 'wer': ''})
        writer.writerow({'image_id': 'EVALUATION_SCOPE', 'cer': 'Preliminary baseline / Probe', 'wer': ''})
        writer.writerow({'image_id': 'STATUS', 'cer': run_status, 'wer': ''})
        writer.writerow({'image_id': 'EXPECTED_COUNT', 'cer': expected_count, 'wer': ''})
        writer.writerow({'image_id': 'EVALUATED_COUNT', 'cer': evaluated_count, 'wer': ''})
        writer.writerow({'image_id': 'MISSING_COUNT', 'cer': len(missing_samples), 'wer': ''})
        writer.writerow({'image_id': 'MACRO_AVERAGE', 'cer': round(macro_cer, 2), 'wer': round(macro_wer, 2)})

    print(f"Detailed report saved at: {report_path}")

if __name__ == "__main__":
    main()