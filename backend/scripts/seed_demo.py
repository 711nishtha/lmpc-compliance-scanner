"""Seed a deployed (or local) instance with the 12 demo scans.

Why this exists: until now demo data was only reproducible by driving the browser with
Playwright (frontend/qa/02_scan_all.js), which cannot target a deployed backend. This
script talks to the HTTP API directly, so it works against Render, Hugging Face Spaces,
or localhost with no browser involved.

It goes through the real endpoints — real upload, real OCR, real rule engine — so a
successful run is also an end-to-end verification of the deployment, not just a fixture
load.

Usage:
    python backend/scripts/seed_demo.py --base-url https://<your-backend>.onrender.com
    python backend/scripts/seed_demo.py                      # defaults to localhost:8000

Idempotent: re-running registers nothing new (409s on the users are tolerated) but WILL
add another 12 scans, so use --skip-if-populated to make it safe to re-run.
"""
from __future__ import annotations

import argparse
import json
import mimetypes
import sys
import time
import urllib.error
import urllib.request
import uuid
from pathlib import Path

DEMO_DIR = Path(__file__).resolve().parents[2] / "demo_data"

USERS = [
    ("inspector1@example.com", "password123", "inspector"),
    ("admin1@example.com", "password123", "admin"),
]

# Mirrors frontend/qa/02_scan_all.js so the deployed demo matches the local one exactly.
LABELS = [
    ("01_fully_compliant.png", "Fresh Valley Snacks 200g", None),
    ("02_missing_mrp.png", "Golden Crunch Biscuits 100g", None),
    ("03_undersized_mrp_font.png", "Royal Spice Masala 50g", None),
    ("04_missing_consumer_care.png", "Sunrise Cooking Oil 1L", None),
    ("05_wrong_unit_liquid_as_pieces.png", "Clearwater Drinking Water", None),
    ("06_missing_mfg_date.png", "Mountain Herbal Tea 100g", None),
    ("07_imported_missing_country_of_origin.png", "Alpine Chocolate Bar 80g", True),
    ("08_missing_manufacturer.png", "Value Pack Rice 5kg", None),
    ("09_hindi_manufacturer_bilingual.png", "Mountain Herbal Chai 100g", None),
    ("10_gujarati_bilingual_liquid.png", "Sunrise Cooking Oil Gujarati 1L", None),
    ("11_hindi_gujarati_imported_missing_coo.png", "Alpine Chocolate Bar Mixed Script 80g", True),
    ("12_mrp_placed_far_from_group.png", "Value Deal Detergent Powder 500g", None),
]


def _post_json(url: str, payload: dict) -> dict:
    req = urllib.request.Request(
        url, data=json.dumps(payload).encode(), headers={"Content-Type": "application/json"}
    )
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.load(r)


def _get_json(url: str, token: str) -> dict:
    req = urllib.request.Request(url, headers={"Authorization": f"Bearer {token}"})
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.load(r)


def _post_multipart(url: str, token: str, fields: dict, file_path: Path) -> dict:
    """Hand-rolled multipart so the script has no dependency beyond the stdlib."""
    boundary = f"----lmpcseed{uuid.uuid4().hex}"
    body = bytearray()
    for k, v in fields.items():
        if v is None:
            continue
        body += f"--{boundary}\r\n".encode()
        body += f'Content-Disposition: form-data; name="{k}"\r\n\r\n'.encode()
        body += f"{v}\r\n".encode()
    ctype = mimetypes.guess_type(file_path.name)[0] or "application/octet-stream"
    body += f"--{boundary}\r\n".encode()
    body += (
        f'Content-Disposition: form-data; name="file"; filename="{file_path.name}"\r\n'
        f"Content-Type: {ctype}\r\n\r\n"
    ).encode()
    body += file_path.read_bytes() + b"\r\n"
    body += f"--{boundary}--\r\n".encode()

    req = urllib.request.Request(
        url,
        data=bytes(body),
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": f"multipart/form-data; boundary={boundary}",
        },
    )
    with urllib.request.urlopen(req, timeout=300) as r:
        return json.load(r)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--base-url", default="http://127.0.0.1:8000",
                    help="Backend origin, e.g. https://lmpc-backend.onrender.com")
    ap.add_argument("--password", default="password123",
                    help="Demo account password. CHANGE THIS for any instance that is "
                         "reachable publicly and not purely a throwaway demo.")
    ap.add_argument("--skip-if-populated", action="store_true",
                    help="Exit successfully if the instance already has scans.")
    args = ap.parse_args()
    base = args.base_url.rstrip("/")

    print(f"seeding {base}")

    # --- health ---
    try:
        with urllib.request.urlopen(f"{base}/api/health", timeout=120) as r:
            print(f"  health: {json.load(r)}")
    except Exception as e:
        print(f"  ERROR: backend not reachable at {base} -> {e}")
        return 1

    # --- users (409 = already present, which is fine) ---
    tokens: dict[str, str] = {}
    for email, _pw, role in USERS:
        pw = args.password
        try:
            _post_json(f"{base}/api/auth/register", {"email": email, "password": pw, "role": role})
            print(f"  registered {email} ({role})")
        except urllib.error.HTTPError as e:
            if e.code in (400, 409):
                print(f"  {email} already exists")
            else:
                print(f"  ERROR registering {email}: {e.code} {e.read()[:200]!r}")
                return 1
        tokens[role] = _post_json(f"{base}/api/auth/login", {"email": email, "password": pw})["access_token"]

    inspector = tokens["inspector"]

    if args.skip_if_populated:
        existing = _get_json(f"{base}/api/dashboard/summary", tokens["admin"]).get("total_scans", 0)
        if existing:
            print(f"  already populated ({existing} scans) - skipping")
            return 0

    # --- scans ---
    ok = 0
    for i, (fname, product, imported) in enumerate(LABELS, 1):
        path = DEMO_DIR / fname
        if not path.exists():
            print(f"  [{i:02d}] MISSING {fname}")
            continue
        fields = {"product_name": product}
        if imported is not None:
            fields["is_imported"] = "true" if imported else "false"
        t0 = time.time()
        try:
            res = _post_multipart(f"{base}/api/scans", inspector, fields, path)
            print(f"  [{i:02d}] {product[:40]:42s} -> {str(res.get('overall_status')):20s} "
                  f"({time.time() - t0:.1f}s)")
            ok += 1
        except urllib.error.HTTPError as e:
            print(f"  [{i:02d}] FAILED {fname}: {e.code} {e.read()[:200]!r}")
        except Exception as e:
            print(f"  [{i:02d}] FAILED {fname}: {e}")

    summary = _get_json(f"{base}/api/dashboard/summary", tokens["admin"])
    print(f"\nseeded {ok}/{len(LABELS)} scans; instance now reports "
          f"{summary.get('total_scans')} total {summary.get('by_status')}")
    return 0 if ok == len(LABELS) else 1


if __name__ == "__main__":
    sys.exit(main())
