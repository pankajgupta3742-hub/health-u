"""PDF report generation. Writes only to the configured reports directory, under a server-chosen name."""
import os
import uuid
from datetime import datetime

from fpdf import FPDF

from app.config import REPORTS_DIR

DISCLAIMER = (
    "DISCLAIMER: Health-U is an AI-assisted triage tool. It is NOT a diagnosis and does not "
    "prescribe treatment. If you feel this is an emergency, seek professional medical help immediately."
)
_COLORS = {"High": (200, 0, 0), "Moderate": (200, 150, 0), "Low": (0, 150, 0)}


def _safe(text) -> str:
    """FPDF's core fonts only support Latin-1. Replace anything else rather than failing."""
    return str(text if text is not None else "Not specified").encode("latin-1", "replace").decode("latin-1")


def _missing_section(pdf: FPDF, missing: dict) -> None:
    """Which answers were missing, and for each answered value: where it came from and when."""
    pdf.set_font("Helvetica", "B", 12)
    pdf.cell(190, 9, "Missing information and sources", new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("Helvetica", "", 10)
    fields = missing.get("missing_fields") or []
    if fields:
        names = ", ".join(str(f).replace("_", " ") for f in fields)
        pdf.multi_cell(180, 6, _safe(f"Not answered (no urgency was calculated from these): {names}."))
    prov = missing.get("provenance") or {}
    for field, info in prov.items():
        if field.startswith("__"):
            continue
        if info.get("source") == "retrieved":
            how = f"from your earlier answer dated {info.get('source_date', 'unknown')}, accepted by you"
        else:
            how = f"entered by you on {info.get('source_date', 'unknown')}"
        pdf.multi_cell(180, 6, _safe(f"- {field.replace('_', ' ')}: {how}"))
    if not fields and not prov:
        pdf.multi_cell(180, 6, "No information was missing.")
    pdf.ln(3)


def generate_pdf(input_data: dict, final_urgency: str, rule_output: dict, explanation: dict,
                 report_id: str, created_at: datetime, missing: dict | None = None) -> str:
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Helvetica", "B", 18)
    pdf.cell(190, 12, _safe("Health-U - Clinical Triage Report"), new_x="LMARGIN", new_y="NEXT", align="C")
    pdf.set_font("Helvetica", "", 9)
    pdf.cell(190, 6, _safe(f"Report {report_id} | Assessed {created_at:%Y-%m-%d %H:%M} UTC"),
             new_x="LMARGIN", new_y="NEXT", align="C")
    pdf.ln(6)

    pdf.set_text_color(*_COLORS.get(final_urgency, (0, 0, 0)))
    pdf.set_font("Helvetica", "B", 14)
    pdf.cell(190, 12, _safe(f"URGENCY LEVEL: {final_urgency}"), new_x="LMARGIN", new_y="NEXT", fill=False)
    pdf.set_text_color(0, 0, 0)
    pdf.ln(3)

    pdf.set_font("Helvetica", "B", 12)
    pdf.cell(190, 9, "Assessment inputs", new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("Helvetica", "", 10)
    rows = [
        ("Primary symptom", input_data.get("primary_symptom")),
        ("Severity (1-10)", input_data.get("severity_score")),
        ("Duration", input_data.get("duration_category")),
        ("Frequency", input_data.get("frequency")),
        ("Age group", input_data.get("age_group")),
        ("Shortness of breath", input_data.get("breathlessness_level")),
        ("Vomiting", input_data.get("vomiting_severity")),
        ("Fever", input_data.get("fever_level")),
        ("Type of pain", input_data.get("pain_type")),
    ]
    for label, value in rows:
        pdf.cell(60, 7, _safe(label))
        pdf.cell(130, 7, _safe(str(value).replace("_", " ").capitalize() if value is not None else "Not specified"),
                 new_x="LMARGIN", new_y="NEXT")
    pdf.ln(4)

    pdf.set_font("Helvetica", "B", 12)
    pdf.cell(190, 9, "Rule that matched", new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("Helvetica", "", 10)
    pdf.multi_cell(180, 6, _safe(f"{rule_output.get('matching_rule', '')}: {rule_output.get('logic', '')}"))
    pdf.ln(3)

    pdf.set_font("Helvetica", "B", 12)
    pdf.cell(190, 9, "Explanation (AI-written, urgency comes from the rules)", new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("Helvetica", "", 10)
    pdf.multi_cell(180, 6, _safe(explanation.get("narrative", "")))
    pdf.ln(3)

    pdf.set_font("Helvetica", "B", 12)
    pdf.cell(190, 9, "Recommended next steps", new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("Helvetica", "", 10)
    pdf.multi_cell(180, 6, _safe(explanation.get("recommendation", "")))
    pdf.ln(3)

    pdf.set_font("Helvetica", "B", 12)
    pdf.cell(190, 9, "First aid and medicine information", new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("Helvetica", "", 10)
    pdf.multi_cell(180, 6, _safe(f"First aid: {explanation.get('first_aid', '')}"))
    pdf.multi_cell(180, 6, _safe(f"Medicine: {explanation.get('medicine_info', '')}"))
    pdf.ln(8)

    if missing is not None:
        _missing_section(pdf, missing)

    pdf.set_font("Helvetica", "I", 8)
    pdf.multi_cell(180, 4.5, _safe(DISCLAIMER))

    os.makedirs(REPORTS_DIR, exist_ok=True)
    path = os.path.join(REPORTS_DIR, f"{uuid.uuid4()}.pdf")
    pdf.output(path)
    return path
