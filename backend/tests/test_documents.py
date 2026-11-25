"""Medical report upload: extraction returns candidates only; nothing is saved until the user confirms."""
import io

from fpdf import FPDF

from conftest import auth
from app.services.lab_extraction import extract_candidates

SAMPLE = """
Haemoglobin         11.2 g/dL     (13.0 - 17.0)
Total WBC count     3800 /cumm    (4000 - 11000)
Platelet count      78000 /cumm   (150000 - 410000)
Dengue NS1 Antigen  Positive
Dengue IgM          Negative
Creatinine          0.9 mg/dL     0.6 - 1.2
Patient name: John Doe, age 34
"""


def test_extracts_known_analytes_with_units_and_ranges():
    found = {c["test_name"]: c for c in extract_candidates(SAMPLE)}
    assert found["Hemoglobin"]["value"] == "11.2"
    assert found["Hemoglobin"]["unit"] == "g/dL"
    assert found["Hemoglobin"]["reference_range"] == "13.0-17.0"
    assert found["Total WBC count"]["value"] == "3800"
    assert found["Platelet count"]["value"] == "78000"
    assert found["Dengue NS1 antigen"]["value"] == "positive"
    assert found["Dengue IgM"]["value"] == "negative"
    assert found["Creatinine"]["value"] == "0.9"


def test_no_invented_values_for_unknown_text():
    assert extract_candidates("Nothing relevant here. Ward 4, bed 12.") == []


def _pdf_bytes(text):
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Helvetica", "", 11)
    for line in text.strip().splitlines():
        pdf.cell(190, 7, line.strip(), new_x="LMARGIN", new_y="NEXT")
    return bytes(pdf.output())


def test_pdf_upload_returns_candidates(client, user_a):
    pdf = _pdf_bytes(SAMPLE)
    r = client.post("/api/v1/documents/extract", headers=auth(user_a),
                    files={"file": ("report.pdf", io.BytesIO(pdf), "application/pdf")})
    assert r.status_code == 200, r.text
    names = [c["test_name"] for c in r.json()["candidates"]]
    assert "Hemoglobin" in names and "Platelet count" in names
    assert r.json()["pages_read"] == 1


def test_upload_is_not_stored(client, user_a):
    client.post("/api/v1/documents/extract", headers=auth(user_a),
                files={"file": ("r.txt", io.BytesIO(SAMPLE.encode()), "text/plain")})
    assert client.get("/api/v1/lab-results", headers=auth(user_a)).json() == []


def test_image_upload_rejected_not_guessed(client, user_a):
    png = b"\x89PNG\r\n\x1a\n" + b"0" * 64
    r = client.post("/api/v1/documents/extract", headers=auth(user_a),
                    files={"file": ("scan.png", io.BytesIO(png), "image/png")})
    assert r.status_code == 415


def test_oversize_upload_rejected(client, user_a, monkeypatch):
    import app.routers.documents as docs
    monkeypatch.setattr(docs, "MAX_UPLOAD_BYTES", 100)
    r = client.post("/api/v1/documents/extract", headers=auth(user_a),
                    files={"file": ("big.txt", io.BytesIO(b"x" * 500), "text/plain")})
    assert r.status_code == 413


def test_non_pdf_bytes_named_pdf_rejected(client, user_a):
    r = client.post("/api/v1/documents/extract", headers=auth(user_a),
                    files={"file": ("fake.pdf", io.BytesIO(b"hello world"), "application/pdf")})
    assert r.status_code in (415, 422)


def test_save_confirmed_results_and_owner_scoped_delete(client, user_a, user_b):
    body = {"results": [{"test_name": "Hemoglobin", "value": "11.2", "unit": "g/dL",
                         "reference_range": "13.0-17.0", "recorded_on": "2026-10-01"}]}
    r = client.post("/api/v1/lab-results", json=body, headers=auth(user_a))
    assert r.status_code == 201, r.text
    rid = r.json()[0]["id"]

    assert client.get("/api/v1/lab-results", headers=auth(user_b)).json() == []
    assert client.delete(f"/api/v1/lab-results/{rid}", headers=auth(user_b)).status_code == 404
    assert client.delete(f"/api/v1/lab-results/{rid}", headers=auth(user_a)).status_code == 204


def test_empty_save_rejected(client, user_a):
    assert client.post("/api/v1/lab-results", json={"results": []}, headers=auth(user_a)).status_code == 422
