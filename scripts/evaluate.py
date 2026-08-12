import os
import json
import jiwer
import csv

def get_text_from_ocr_json(json_path):
    try:
        with open(json_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
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
    gt_dir = "data/ground_truth"
    ocr_dir = "results/ocr_outputs"
    report_path = "results/evaluation_report.csv"

    if not os.path.exists(gt_dir) or not os.path.exists(ocr_dir):
        print("Directory ground_truth or ocr_outputs not found!")
        return

    results = []
    total_cer = 0
    total_wer = 0
    valid_files = 0

    print(f"{'File':<15} | {'CER (%)':<10} | {'WER (%)':<10}")
    print("-" * 45)

    for gt_filename in os.listdir(gt_dir):
        if not gt_filename.endswith('.txt'):
            continue

        base_name = os.path.splitext(gt_filename)[0]
        ocr_filename = f"{base_name}.json"
        
        gt_path = os.path.join(gt_dir, gt_filename)
        ocr_path = os.path.join(ocr_dir, ocr_filename)

        if not os.path.exists(ocr_path):
            continue

        gt_text = get_text_from_gt(gt_path)
        ocr_text = get_text_from_ocr_json(ocr_path)

        if not gt_text:
            continue

        cer = jiwer.cer(gt_text, ocr_text) * 100
        wer = jiwer.wer(gt_text, ocr_text) * 100

        results.append({
            "image_id": base_name,
            "cer": round(cer, 2),
            "wer": round(wer, 2)
        })

        total_cer += cer
        total_wer += wer
        valid_files += 1
        
        print(f"{base_name:<15} | {cer:<10.2f} | {wer:<10.2f}")

    if valid_files > 0:
        avg_cer = total_cer / valid_files
        avg_wer = total_wer / valid_files
        print("-" * 45)
        print(f"{'AVERAGE':<15} | {avg_cer:<10.2f} | {avg_wer:<10.2f}")

        with open(report_path, 'w', newline='', encoding='utf-8') as csvfile:
            fieldnames = ['image_id', 'cer', 'wer']
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
            writer.writeheader()
            for row in results:
                writer.writerow(row)
            writer.writerow({'image_id': 'AVERAGE', 'cer': round(avg_cer, 2), 'wer': round(avg_wer, 2)})
            
        print(f"\nDetailed report saved at: {report_path}")
    else:
        print("No valid files found for evaluation.")

if __name__ == "__main__":
    main()