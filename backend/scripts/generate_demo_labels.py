"""Renders the synthetic demo label images defined in tests/demo_labels.py into demo_data/.

These are plain, clearly fictional mock labels built to exercise specific rule checks — not
photographs of real branded products (see docs/LEGAL_REQUIREMENTS.md Step 8 IP note in the
build spec: real branded packaging must not be reproduced in the public repo).
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from PIL import Image, ImageDraw, ImageFont

from tests.demo_labels import DEMO_LABELS

OUT_DIR = Path(__file__).resolve().parents[2] / "demo_data"
OUT_DIR.mkdir(exist_ok=True)


MARGIN_RIGHT = 20
MARGIN_BOTTOM = 20

# Windows' pan-Indic UI font -- covers Devanagari and Gujarati (and more) in one file, unlike
# arial.ttf which has no glyphs for either and would silently fall back to tofu/boxes. See
# docs/ARCHITECTURE.md §2 note on why a font substitution here isn't a cosmetic detail: it would
# recreate the same "ground truth doesn't match what's actually in the image" bug hit with the
# 460x260-canvas clipping fix above -- a label the codebase thinks contains Hindi/Gujarati text
# would actually contain empty boxes no OCR engine could ever read.
INDIC_FONT_PATH = r"C:\Windows\Fonts\Nirmala.ttc"
INDIC_FONT_INDEX = 0  # "Nirmala UI Regular" within the .ttc collection

DEVANAGARI_RANGE = (0x0900, 0x097F)
GUJARATI_RANGE = (0x0A80, 0x0AFF)


def _script_of(text: str) -> str:
    has_deva = any(DEVANAGARI_RANGE[0] <= ord(c) <= DEVANAGARI_RANGE[1] for c in text)
    has_guj = any(GUJARATI_RANGE[0] <= ord(c) <= GUJARATI_RANGE[1] for c in text)
    if has_deva and has_guj:
        return "mixed"
    if has_deva:
        return "hin"
    if has_guj:
        return "guj"
    return "eng"


def _font_for(region, fonts: dict):
    font_size = max(8, min(region.height, 28))
    script = _script_of(region.text)
    key = (font_size, script)
    if key not in fonts:
        if script in ("hin", "guj", "mixed"):
            try:
                fonts[key] = ImageFont.truetype(INDIC_FONT_PATH, font_size, index=INDIC_FONT_INDEX)
            except OSError:
                raise RuntimeError(
                    f"Could not load Indic font at {INDIC_FONT_PATH} needed to render "
                    f"{script}-script text {region.text!r}. Without it this text would silently "
                    "render as tofu/boxes rather than raising -- install a pan-Indic font "
                    "(e.g. Nirmala UI) or update INDIC_FONT_PATH."
                )
        else:
            try:
                fonts[key] = ImageFont.truetype("arial.ttf", font_size)
            except OSError:
                fonts[key] = ImageFont.load_default()
    return fonts[key], script


def render(label) -> Path:
    # Canvas is sized to fit every region's rendered text width/height rather than a fixed
    # 460x260 -- a fixed canvas silently clipped long lines (manufacturer address, consumer
    # care email) off the right edge with no pixels for OCR to read, which isn't a rendering
    # detail: it made those "ground truth" images not actually contain the text they were
    # built to test (found by running real Tesseract OCR against demo_data, not the ground-truth
    # OcrRegion fixtures test_e2e.py substitutes in -- see scripts/run_real_ocr_pipeline.py).
    scratch = Image.new("RGB", (1, 1))
    draw_scratch = ImageDraw.Draw(scratch)
    max_right = 460
    max_bottom = 260
    fonts: dict = {}
    region_fonts = []
    for region in label.regions:
        font, script = _font_for(region, fonts)
        region_fonts.append((region, font, script))
        bbox = draw_scratch.textbbox((region.x, region.y), region.text, font=font)
        max_right = max(max_right, bbox[2] + MARGIN_RIGHT)
        max_bottom = max(max_bottom, bbox[3] + MARGIN_BOTTOM)

    img = Image.new("RGB", (max_right, max_bottom), color="white")
    draw = ImageDraw.Draw(img)
    draw.rectangle([2, 2, max_right - 3, max_bottom - 3], outline="black", width=2)
    for region, font, _script in region_fonts:
        draw.text((region.x, region.y), region.text, fill="black", font=font)
    out_path = OUT_DIR / label.filename
    img.save(out_path)

    _verify_non_latin_regions_rendered(img, region_fonts, label)
    return out_path


def _verify_non_latin_regions_rendered(img, region_fonts, label) -> None:
    """Round-trip OCR sanity check for any region with Devanagari/Gujarati text: crop just that
    region and confirm Tesseract reads back at least one character in the expected Unicode
    block. Catches a font silently substituting tofu/boxes for unsupported glyphs -- inspecting
    the source string alone would not (the string is correct Unicode either way; only the
    rendered pixels would be wrong), which is exactly why this check exists."""
    non_latin = [(r, s) for r, _f, s in region_fonts if s != "eng"]
    if not non_latin:
        return
    try:
        import pytesseract
    except ImportError:
        print(f"  [WARN] pytesseract not available -- skipping round-trip OCR check for "
              f"{label.filename} ({len(non_latin)} non-Latin region(s) unverified)")
        return
    import shutil
    if shutil.which("tesseract") is None:
        print(f"  [WARN] tesseract binary not on PATH -- skipping round-trip OCR check for "
              f"{label.filename} ({len(non_latin)} non-Latin region(s) unverified)")
        return

    pad = 6
    for region, script in non_latin:
        crop = img.crop((
            max(0, region.x - pad), max(0, region.y - pad),
            min(img.width, region.x + region.width + pad),
            min(img.height, region.y + region.height + pad),
        ))
        lang = "hin+guj" if script == "mixed" else script
        result = pytesseract.image_to_string(crop, lang=lang)
        expected_ranges = []
        if script in ("hin", "mixed"):
            expected_ranges.append(DEVANAGARI_RANGE)
        if script in ("guj", "mixed"):
            expected_ranges.append(GUJARATI_RANGE)
        found_script_char = any(
            any(lo <= ord(c) <= hi for lo, hi in expected_ranges) for c in result
        )
        if not found_script_char:
            raise RuntimeError(
                f"Round-trip OCR sanity check FAILED for {label.filename} region "
                f"{region.text!r}: OCR read back {result!r}, containing no {script}-script "
                "characters. The font may be rendering tofu/boxes instead of real glyphs -- "
                "do not trust this image as ground truth until this is fixed."
            )


def main():
    lines = ["# Demo Data — Synthetic Mock Labels\n",
             "Plain, clearly fictional labels built to exercise specific Legal Metrology rule "
             "checks in a controlled, repeatable demo walkthrough. None depict real branded "
             "products (see docs/LEGAL_REQUIREMENTS.md Step 8 IP note).\n",
             "| File | Exercises | Description |", "|---|---|---|"]
    for label in DEMO_LABELS:
        render(label)
        rule_ids = ", ".join(label.expected.keys())
        lines.append(f"| {label.filename} | {rule_ids} | {label.description} |")
    (OUT_DIR / "README.md").write_text("\n".join(lines), encoding="utf-8")
    print(f"Generated {len(DEMO_LABELS)} demo labels into {OUT_DIR}")


if __name__ == "__main__":
    main()
