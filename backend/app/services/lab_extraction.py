"""Finds lab values in the text of an uploaded report.

This is a conservative pattern matcher, not a clinical parser. It only returns a value when a known
test name appears on the same line as a number (or a qualitative result such as Positive/Negative).
Every candidate is shown to the user for review; nothing is saved without their confirmation.
"""
import io
import re

from pypdf import PdfReader

from app.config import MAX_UPLOAD_PAGES

# (display name, regex alias, is_qualitative)
ANALYTES: list[tuple[str, str, bool]] = [
    ("Hemoglobin", r"h(?:a)?emoglobin|hgb|hb", False),
    ("Total WBC count", r"total\s+(?:wbc|leu?cocyte)\s*(?:count)?|wbc(?:\s+count)?|tlc", False),
    ("Platelet count", r"platelets?(?:\s+count)?", False),
    ("Hematocrit (PCV)", r"h(?:a)?ematocrit|pcv", False),
    ("RBC count", r"rbc(?:\s+count)?", False),
    ("Neutrophils", r"neutrophils?", False),
    ("Lymphocytes", r"lymphocytes?", False),
    ("Creatinine", r"creatinine", False),
    ("Blood urea", r"(?:blood\s+)?urea", False),
    ("Total bilirubin", r"total\s+bilirubin|bilirubin\s*,?\s*total", False),
    ("SGOT (AST)", r"sgot|ast\s*\(sgot\)|\bast\b", False),
    ("SGPT (ALT)", r"sgpt|alt\s*\(sgpt\)|\balt\b", False),
    ("Blood glucose", r"(?:random\s+|fasting\s+)?blood\s+(?:sugar|glucose)", False),
    ("Dengue NS1 antigen", r"ns1(?:\s+antigen)?", True),
    ("Dengue IgM", r"dengue\s+igm|igm\s+(?:antibod\w*\s+)?dengue", True),
    ("Dengue IgG", r"dengue\s+igg|igg\s+(?:antibod\w*\s+)?dengue", True),
    ("Malaria parasite", r"malaria\s+(?:parasite|antigen|smear|pf|pv)?|plasmodium", True),
]

_NUMBER = r"(\d+(?:\.\d+)?)"
_QUAL = r"(non[- ]?reactive|reactive|positive|negative|detected|not detected)"
_UNIT = r"([a-zA-Zµμ/%³\^\*\.\d]{1,12}(?:/[a-zA-Zµμ]{1,3})?)"


def _line_candidates(line: str) -> list[dict]:
    out: list[dict] = []
    lowered = line.lower()
    for name, alias, qualitative in ANALYTES:
        m = re.search(rf"(?<![a-z])(?:{alias})(?![a-z])", lowered)
        if not m:
            continue
        tail = line[m.end():]
        if qualitative:
            q = re.search(_QUAL, tail, re.IGNORECASE)
            if q:
                out.append({"test_name": name, "value": q.group(1).lower(), "unit": "",
                            "reference_range": "", "source_line": line.strip()[:200]})
            continue
        num = re.search(_NUMBER, tail)
        if not num:
            continue
        after = tail[num.end():num.end() + 14]
        unit_m = re.match(r"\s*" + _UNIT, after)
        unit = unit_m.group(1) if unit_m and not unit_m.group(1).isdigit() else ""
        ref = re.search(r"(\d+(?:\.\d+)?\s*(?:-|–|to)\s*\d+(?:\.\d+)?)", tail[num.end():])
        out.append({"test_name": name, "value": num.group(1), "unit": unit,
                    "reference_range": re.sub(r"\s+", "", ref.group(1)).replace("–", "-").replace("to", "-") if ref else "",
                    "source_line": line.strip()[:200]})
    return out


def extract_text_from_pdf(data: bytes) -> tuple[str, int]:
    reader = PdfReader(io.BytesIO(data))
    pages = reader.pages[:MAX_UPLOAD_PAGES]
    text = "\n".join((p.extract_text() or "") for p in pages)
    return text, len(pages)


def extract_candidates(text: str) -> list[dict]:
    seen: set[tuple[str, str]] = set()
    results: list[dict] = []
    for raw in text.splitlines():
        for cand in _line_candidates(raw):
            key = (cand["test_name"], cand["value"])
            if key in seen:
                continue
            seen.add(key)
            results.append(cand)
    return results[:100]
