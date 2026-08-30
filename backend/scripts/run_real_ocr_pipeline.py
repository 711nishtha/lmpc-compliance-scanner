"""Runs the ACTUAL image -> OCR -> extraction -> rule-engine path (no ground-truth substitution)
against every demo_data label, and diffs the result against the expected verdicts in
tests/demo_labels.py. This is the live-Tesseract check that test_e2e.py explicitly does NOT do
(it feeds ground-truth OCR regions instead, see its module docstring) -- run once Tesseract +
eng/hin/guj packs are actually installed on the host.
"""
import io
import sys
import time
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import cv2

from app.extraction.fields import extract_declarations
from app.ocr.engine import OcrUnavailableError, run_ocr
from app.ocr.preprocess import preprocess
from app.rules.engine import run_all_checks
from tests.demo_labels import DEMO_LABELS

DEMO_DIR = Path(__file__).resolve().parents[2] / "demo_data"


def main():
    print(f"Tesseract check...")
    try:
        run_ocr.__module__  # noop, just import path sanity
    except Exception:
        pass

    total = len(DEMO_LABELS)
    passed = 0
    for label in DEMO_LABELS:
        img_path = DEMO_DIR / label.filename
        print(f"\n{'=' * 70}\n{label.filename}  ({label.key})")
        image = cv2.imread(str(img_path))
        if image is None:
            print(f"  ERROR: could not read {img_path}")
            continue

        t0 = time.time()
        pre = preprocess(image)
        try:
            regions = run_ocr(pre.final)
        except OcrUnavailableError as exc:
            print(f"  OCR UNAVAILABLE: {exc}")
            continue
        t_ocr = time.time() - t0

        raw_text = " | ".join(r.text for r in regions)
        avg_conf = sum(r.confidence for r in regions) / len(regions) if regions else 0.0
        low_conf = [r for r in regions if r.confidence < 60]

        print(f"  preprocess stages: {pre.stages_applied}")
        print(f"  OCR regions: {len(regions)}  avg_conf={avg_conf:.1f}  time={t_ocr:.2f}s")
        print(f"  raw OCR text: {raw_text}")
        if low_conf:
            print(f"  LOW-CONF regions (<60): {[(r.text, r.confidence) for r in low_conf]}")

        declarations = extract_declarations(regions)
        declarations.commodity_category = label.commodity_category
        declarations.is_perishable_category = label.is_perishable_category
        declarations.is_imported = label.is_imported
        declarations.image_height_px, declarations.image_width_px = pre.final.shape[:2]

        print(f"  extracted fields: {declarations.model_dump(exclude={'text_heights_px'})}")

        report = run_all_checks(declarations)
        results_by_id = {r.rule_id: r for r in report.results}

        label_ok = True
        for rule_id, expected_status in label.expected.items():
            actual = results_by_id.get(rule_id)
            actual_status = actual.status if actual else None
            match = "OK" if actual_status == expected_status else "MISMATCH"
            if match == "MISMATCH":
                label_ok = False
            print(f"  {rule_id}: expected={expected_status.value} actual="
                  f"{actual_status.value if actual_status else 'MISSING'} [{match}]"
                  + (f"  notes={actual.notes!r}" if actual and match == 'MISMATCH' else ""))

        if label_ok:
            passed += 1
        print(f"  LABEL RESULT: {'PASS' if label_ok else 'FAIL'}")

    print(f"\n{'=' * 70}\nSUMMARY: {passed}/{total} labels matched expected verdicts via REAL OCR")


if __name__ == "__main__":
    main()
