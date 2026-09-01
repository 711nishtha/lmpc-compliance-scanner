"""Admin manual verification of a NEEDS_VERIFICATION result (api/scans.py::verify_rule_result).

Most of these are guardrail tests rather than happy-path tests, and deliberately so: "let a
person set the status" is the single most dangerous endpoint in a compliance tool. The
constraints -- admin only, only from NEEDS_VERIFICATION, never silent -- are the feature. The
happy path is two lines.
"""
import json
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.api.rate_limit import reset_rate_limits
from app.db import Base, get_db
from app.main import app
from app.models.orm import Product, RuleVerification, Scan
from app.rules.schema import RuleResult, Status


@pytest.fixture()
def db_session_factory(tmp_path):
    """A throwaway SQLite file per test, injected via FastAPI's dependency override.

    Emphatically NOT app.db.engine. That points at backend/data/compliance.db -- the developer's
    real dev database -- and an earlier version of this file wrote its fixture scans straight
    into it, leaving a pile of "Test pack" rows in the running app's repository view. Tests that
    share a database with the app they are testing also inherit its state, so they pass or fail
    depending on what someone scanned yesterday.
    """
    engine = create_engine(
        f"sqlite:///{tmp_path / 'test.db'}", connect_args={"check_same_thread": False}
    )
    Base.metadata.create_all(bind=engine)
    return sessionmaker(autocommit=False, autoflush=False, bind=engine)


@pytest.fixture()
def client(db_session_factory):
    def _get_db():
        db = db_session_factory()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = _get_db
    reset_rate_limits()
    try:
        with TestClient(app) as c:
            yield c
    finally:
        app.dependency_overrides.pop(get_db, None)


def _token(client, email, role):
    resp = client.post("/api/auth/register", json={"email": email, "password": "Passw0rd!", "role": role})
    if resp.status_code != 200:
        resp = client.post("/api/auth/login", json={"email": email, "password": "Passw0rd!"})
    return resp.json()["access_token"]


def _result(rule_id, status, notes="Engine could not decide."):
    return RuleResult(
        rule_id=rule_id, rule_reference="Rule 7(2), Table-I",
        requirement_text="Numeral height must meet Rule 7 Table-I.",
        status=status, notes=notes,
    ).model_dump(mode="json")


@pytest.fixture()
def scan_id(client, db_session_factory):
    """A stored scan carrying one of each status, written straight to the DB -- this endpoint's
    behaviour has nothing to do with how the scan was produced, and going through the real OCR
    pipeline here would make the test slow and dependent on Tesseract."""
    db = db_session_factory()
    try:
        product = Product(name="Test pack")
        db.add(product)
        db.flush()
        scan = Scan(
            product_id=product.id, inspector_email="inspector@example.com",
            image_path="x.jpg", raw_ocr_json="[]", declarations_json="{}",
            rule_results_json=json.dumps([
                _result("R7-1", Status.NEEDS_VERIFICATION),
                _result("R6-4", Status.PASS),
                _result("R6-7", Status.FAIL),
                _result("R6-11", Status.NOT_APPLICABLE),
            ]),
            ruleset_version="test", overall_status="FAIL", compliance_score=25.0,
        )
        db.add(scan)
        db.commit()
        return scan.id
    finally:
        db.close()


def _verify(client, token, scan_id, rule_id="R7-1", note="Checked the physical pack with a rule."):
    return client.post(
        f"/api/scans/{scan_id}/rule-results/{rule_id}/verify",
        json={"note": note}, headers={"Authorization": f"Bearer {token}"},
    )


# ---------- the guardrails ----------

def test_an_inspector_cannot_verify(client, scan_id):
    """Overriding a machine finding is a supervisory act. Ordinary inspectors create scans."""
    resp = _verify(client, _token(client, "insp@example.com", "inspector"), scan_id)
    assert resp.status_code == 403


def test_an_anonymous_caller_cannot_verify(client, scan_id):
    resp = client.post(f"/api/scans/{scan_id}/rule-results/R7-1/verify", json={"note": "x"})
    assert resp.status_code in (401, 403)


def test_a_fail_cannot_be_cleared_by_verification(client, scan_id):
    """The most important test here. A FAIL is a positive finding of non-compliance the engine
    could cite a rule for. This endpoint resolves open questions; it must never become a way to
    overturn a verdict."""
    resp = _verify(client, _token(client, "admin@example.com", "admin"), scan_id, rule_id="R6-7")
    assert resp.status_code == 409
    assert "NEEDS_VERIFICATION" in resp.json()["detail"]


def test_an_existing_pass_cannot_be_re_verified(client, scan_id):
    resp = _verify(client, _token(client, "admin@example.com", "admin"), scan_id, rule_id="R6-4")
    assert resp.status_code == 409


def test_a_not_applicable_rule_cannot_be_verified(client, scan_id):
    resp = _verify(client, _token(client, "admin@example.com", "admin"), scan_id, rule_id="R6-11")
    assert resp.status_code == 409


def test_unknown_rule_and_unknown_scan_are_404(client, scan_id):
    token = _token(client, "admin@example.com", "admin")
    assert _verify(client, token, scan_id, rule_id="R9-99").status_code == 404
    assert _verify(client, token, 999999).status_code == 404


# ---------- the happy path, and its disclosure ----------

def test_verification_upgrades_to_pass_and_records_who_did_it(client, scan_id):
    resp = _verify(client, _token(client, "admin@example.com", "admin"), scan_id)
    assert resp.status_code == 200
    row = next(r for r in resp.json()["rule_results"] if r["rule_id"] == "R7-1")
    assert row["status"] == "PASS"
    assert row["original_status"] == "NEEDS_VERIFICATION", "the engine's own finding must survive"
    assert row["verified_by"] == "admin@example.com"
    assert row["verified_at"]
    assert row["verification_note"] == "Checked the physical pack with a rule."


def test_the_upgrade_is_disclosed_in_notes_so_no_export_can_hide_it(client, scan_id):
    """The PDF and DOCX exporters render `notes` verbatim. Putting the disclosure there is what
    stops a downloaded report showing a PASS with no indication a human made it one."""
    resp = _verify(client, _token(client, "admin@example.com", "admin"), scan_id)
    notes = next(r for r in resp.json()["rule_results"] if r["rule_id"] == "R7-1")["notes"]
    assert "Manually verified" in notes
    assert "admin@example.com" in notes
    assert "NEEDS_VERIFICATION" in notes, "the automated result must be stated in the note"
    assert "Checked the physical pack" in notes
    assert notes.startswith("Manually verified"), "disclosure leads; engine notes follow"


def test_a_verification_with_no_note_still_discloses_who_and_when(client, scan_id):
    resp = client.post(
        f"/api/scans/{scan_id}/rule-results/R7-1/verify", json={},
        headers={"Authorization": f"Bearer {_token(client, 'admin@example.com', 'admin')}"},
    )
    assert resp.status_code == 200
    row = next(r for r in resp.json()["rule_results"] if r["rule_id"] == "R7-1")
    assert row["verification_note"] is None
    assert "admin@example.com" in row["notes"]


def test_score_and_overall_status_are_recomputed(client, scan_id):
    """A verified rule has to move the summary too, or the header contradicts the table below it."""
    before = client.get(
        f"/api/scans/{scan_id}", headers={"Authorization": f"Bearer {_token(client, 'admin@example.com', 'admin')}"}
    ).json()
    resp = _verify(client, _token(client, "admin@example.com", "admin"), scan_id)
    after = resp.json()
    assert after["compliance_score"] > before["compliance_score"]
    # R6-7 is still FAIL, so the scan overall must stay FAIL -- one resolved question does not
    # clear an outstanding violation.
    assert after["overall_status"] == "FAIL"


def test_an_audit_row_is_written(client, scan_id, db_session_factory):
    _verify(client, _token(client, "admin@example.com", "admin"), scan_id)
    db = db_session_factory()
    try:
        rows = db.query(RuleVerification).filter(RuleVerification.scan_id == scan_id).all()
        assert len(rows) == 1
        assert rows[0].rule_id == "R7-1"
        assert rows[0].verified_by == "admin@example.com"
        assert rows[0].original_status == "NEEDS_VERIFICATION"
        assert rows[0].new_status == "PASS"
    finally:
        db.close()


def test_the_change_survives_a_reread(client, scan_id):
    token = _token(client, "admin@example.com", "admin")
    _verify(client, token, scan_id)
    fetched = client.get(f"/api/scans/{scan_id}", headers={"Authorization": f"Bearer {token}"}).json()
    row = next(r for r in fetched["rule_results"] if r["rule_id"] == "R7-1")
    assert row["status"] == "PASS"
    assert row["verified_by"] == "admin@example.com"


def test_verifying_twice_is_refused_the_second_time(client, scan_id):
    """Once upgraded the rule is PASS, so the same guard that protects an engine PASS applies --
    which also means the audit trail cannot be padded with duplicate sign-offs."""
    token = _token(client, "admin@example.com", "admin")
    assert _verify(client, token, scan_id).status_code == 200
    assert _verify(client, token, scan_id).status_code == 409


def test_verification_redraws_the_annotated_image(client, scan_id, db_session_factory, tmp_path):
    """The annotated image is written once at scan time. Without a redraw here, a rule an admin
    had just confirmed stayed invisible on the evidence image -- NEEDS_VERIFICATION rules are no
    longer drawn at all (reports/annotate.py UNDRAWN_STATUSES), so the box only appears once the
    status becomes PASS. The image and the table beside it must not disagree."""
    import cv2
    import numpy as np

    source = tmp_path / "pre.jpg"
    annotated = tmp_path / "annotated.jpg"
    cv2.imwrite(str(source), np.full((300, 300, 3), 255, dtype=np.uint8))
    cv2.imwrite(str(annotated), np.full((300, 300, 3), 255, dtype=np.uint8))

    db = db_session_factory()
    try:
        scan = db.query(Scan).filter(Scan.id == scan_id).first()
        scan.preprocessed_image_path = str(source)
        scan.annotated_image_path = str(annotated)
        results = json.loads(scan.rule_results_json)
        for r in results:
            if r["rule_id"] == "R7-1":
                r["evidence"] = {"bounding_box": {"x": 20, "y": 20, "width": 120, "height": 50}}
        scan.rule_results_json = json.dumps(results)
        db.commit()
    finally:
        db.close()

    before = cv2.imread(str(annotated))
    assert _verify(client, _token(client, "admin@example.com", "admin"), scan_id).status_code == 200
    after = cv2.imread(str(annotated))
    assert not np.array_equal(before, after), "the annotated image must be redrawn on verify"


def test_a_missing_source_image_does_not_lose_the_verification(client, scan_id, db_session_factory):
    """Render's disk is ephemeral, so the stored source image can simply be gone. A redraw that
    cannot happen must not cost the sign-off, which is already recorded."""
    db = db_session_factory()
    try:
        scan = db.query(Scan).filter(Scan.id == scan_id).first()
        scan.preprocessed_image_path = "/nonexistent/definitely-not-here.jpg"
        scan.annotated_image_path = "/nonexistent/annotated.jpg"
        db.commit()
    finally:
        db.close()
    resp = _verify(client, _token(client, "admin@example.com", "admin"), scan_id)
    assert resp.status_code == 200
    assert next(r for r in resp.json()["rule_results"] if r["rule_id"] == "R7-1")["status"] == "PASS"
