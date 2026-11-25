"""Builds the processed training files in data/processed/ and the dataset manifest.

Run from the project root:   python ml/prepare_datasets.py
Raw inputs live in data/raw/ (small files) or are downloaded by ml/download_data.py (large files).
Every excluded column and the reason is written to data/dataset_manifest.json.
"""
import io
import json
import os
import re
import sys
from collections import Counter

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from specs import DATASETS  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RAW = os.path.join(ROOT, "data", "raw")
PROC = os.path.join(ROOT, "data", "processed")
BRAZIL_CSV = os.getenv("HEALTHU_BRAZIL_CSV", "/var/tmp/healthu_raw/data set.csv")
BRAZIL_SAMPLE_FRACTION = 0.0223  # ~150k of 6.73M rows, stratification kept by random sampling
SEED = 42

manifest: dict = {"datasets": {}, "built_with": {"seed": SEED}}


def english_label(col: str) -> str:
    """Short English label for the UI, taken from the bilingual header when present."""
    m = re.search(r"\(([^()]*)\)\s*$", col.strip())
    text = (m.group(1) if m else col).strip().strip("/").strip()
    text = re.sub(r"\s+", " ", text)
    return text[:80] if text else col.strip()[:80]


def clean_binary(series: pd.Series) -> pd.Series:
    """1/2 (yes/no coded forms) -> 1/0. 9 and blanks stay missing."""
    s = pd.to_numeric(series, errors="coerce")
    if set(s.dropna().unique()) <= {1, 2}:
        return s.map({1: 1.0, 2: 0.0})
    return s


def record(key: str, entry: dict) -> None:
    manifest["datasets"].setdefault(key, {}).update(entry)


# ---------- 1. Burkina Faso vector-borne (semicolon CSV, bilingual headers) ----------
def build_burkina() -> None:
    df = pd.read_csv(os.path.join(RAW, "vector_borne_burkina_faso.csv"), sep=";", dtype=str)
    cols = list(df.columns)
    num_cols = [c for c in cols if c.strip().startswith(("Âge", "Poids", "Haute", "Circonference", "Température", "Fréquence", "Pression", "Temps", "Fièvre depuis", "Fièvre au cours"))]
    diag_prefix = "Maladies diagnostiquées"
    label_cols = {
        "malaria": f"{diag_prefix}/Paludisme (Malaria)",
        "dengue": f"{diag_prefix}/Dengue",
        "typhoid": f"{diag_prefix}/Fièvre Typhoïde (Thyphoid fever)",
        "yellow_fever": f"{diag_prefix}/Fièvre jaune (yellow fever)",
    }
    excluded = {}
    for c in cols:
        lc = c.lower()
        if c == "_uuid":
            excluded[c] = "record identifier"
        elif c.startswith(diag_prefix) or c.startswith("Autres maladies"):
            excluded[c] = "diagnosis label or diagnosis text (leakage)"
        elif c.startswith("Centre de santé"):
            excluded[c] = "recruitment site (not a clinical feature; would leak site-level prevalence)"
        elif any(k in lc for k in ["test tdr", "goutte épaisse", "hémoconcentration", "transaminases", "thrombocytop",
                                   "lymphocyt", "lymphocytes", "neutro", "nombre de globules", "numération", "neutrophiles",
                                   "crp", "créatinine", "alat", "hematocrite", "hypoglyc", "pâleur", "dengue (dengua)"]):
            excluded[c] = "laboratory or diagnostic test result (not available at triage, or defines the diagnosis)"
        elif c.strip() in ("Pneumonie (Pneumonia)",):
            excluded[c] = "diagnosis-like comorbidity; kept out to keep the feature set clinical"
    features = [c for c in cols if c not in excluded and c != "_uuid"]

    y_flags = {k: clean_binary(df[v]) for k, v in label_cols.items()}
    any_flag = pd.concat([y_flags[k] for k in ["malaria", "dengue", "typhoid", "yellow_fever"]], axis=1)
    label_sets = {
        "malaria": y_flags["malaria"],
        "vector_borne": any_flag.max(axis=1, skipna=False),
    }
    keep_rows = pd.Series(True, index=df.index)
    for lab in label_sets.values():
        keep_rows &= lab.notna()
    rename, seen = {}, Counter()
    for c in features:  # unique English names even when two headers share a translation
        base = english_label(c)
        seen[base] += 1
        rename[c] = base if seen[base] == 1 else f"{base} ({seen[base]})"
    # Malaria and vector-borne share features; build one processed file per model.
    out_path = os.path.join(PROC, "burkina_vector_borne.csv")
    out = pd.DataFrame(index=df.index[keep_rows])
    for c in features:
        out[rename[c]] = df.loc[keep_rows, c]
    out["malaria_label"] = label_sets["malaria"][keep_rows].astype(int)
    out["vector_borne_label"] = label_sets["vector_borne"][keep_rows].astype(int)
    out.to_csv(out_path, index=False)
    feats_meta = {}
    for c in features:
        feats_meta[rename[c]] = {"source_column": c, "kind": "numeric" if c in num_cols else "categorical_or_binary"}
    record("burkina_vector_borne", {
        "processed_file": "data/processed/burkina_vector_borne.csv",
        "rows_raw": int(len(df)), "rows_used_malaria": int(label_sets["malaria"].notna().sum()),
        "rows_used_vector_borne": int(label_sets["vector_borne"].notna().sum()),
        "label_counts": {
            "malaria": {str(k): int(v) for k, v in label_sets["malaria"][keep_rows].value_counts().items()},
            "vector_borne": {str(k): int(v) for k, v in label_sets["vector_borne"][keep_rows].value_counts().items()},
        },
        "features_used": len(features), "excluded_columns": excluded, "feature_map": feats_meta,
    })


# ---------- 2. Chittagong dengue (comma CSV, NS1 label) ----------
def build_chittagong() -> None:
    df = pd.read_csv(os.path.join(RAW, "dengue_chittagong.csv"), skipinitialspace=True)
    df.columns = [c.strip() for c in df.columns]
    excluded = {
        "LLBplatelet": "platelet count is a laboratory result, not available at first contact",
        "IgG": "serology result (laboratory), part of the diagnostic workup",
        "IgM": "serology result (laboratory), part of the diagnostic workup",
    }
    features = ["Age", "Sex", "Work", "BpSys", "Bpdias", "Pulse", "Cough", "Fever", "Headache", "Muscle pain",
                "Bleeding", "Skinrash", "Vomiting", "Diarrhoea", "Fatigue", "Rapid breathing"]
    out = df[features].copy()
    out.columns = [english_label(c) if c not in ("Age", "Sex", "Work") else c for c in out.columns]
    out.columns = [c.replace("Bpdias", "Diastolic BP").replace("BpSys", "Systolic BP") for c in out.columns]
    out["ns1_label"] = df["NS1"].astype(int)
    out.to_csv(os.path.join(PROC, "chittagong_dengue.csv"), index=False)
    record("chittagong_dengue", {
        "processed_file": "data/processed/chittagong_dengue.csv",
        "rows_raw": int(len(df)), "rows_used": int(len(out)),
        "label_counts": {str(k): int(v) for k, v in df["NS1"].value_counts().items()},
        "features_used": len(features), "excluded_columns": excluded,
        "feature_map": {(english_label(c) if c not in ("Age", "Sex", "Work") else c): {"source_column": c} for c in features},
    })


# ---------- 3. Brazil SINAN (2 GB CSV, read in chunks, random sample) ----------
BRAZIL_FEATURES = {
    "FEBRE": "Fever", "MIALGIA": "Myalgia", "CEFALEIA": "Headache", "EXANTEMA": "Rash", "VOMITO": "Vomiting",
    "NAUSEA": "Nausea", "DOR_COSTAS": "Back pain", "CONJUNTVIT": "Conjunctivitis", "ARTRITE": "Arthritis",
    "ARTRALGIA": "Arthralgia", "PETEQUIA_N": "Petechiae", "LACO": "Tourniquet/lace test", "DOR_RETRO": "Retro-orbital pain",
    "DIABETES": "Diabetes", "HEMATOLOG": "Haematological disease", "HEPATOPAT": "Liver disease", "RENAL": "Kidney disease",
    "HIPERTENSA": "Hypertension", "ACIDO_PEPT": "Peptic ulcer", "AUTO_IMUNE": "Autoimmune disease",
}
BRAZIL_EXCLUDED = {
    "RESUL_SORO": "serology result (laboratory; defines the diagnosis)",
    "RESUL_NS1": "NS1 result (laboratory; defines the diagnosis)",
    "RESUL_VI_N": "virus isolation result (laboratory)",
    "RESUL_PCR_": "PCR result (laboratory; defines the diagnosis)",
    "HISTOPA_N": "histopathology (laboratory)",
    "IMUNOH_N": "immunohistochemistry (laboratory)",
    "LEUCOPENIA": "laboratory-derived finding (white-cell count)",
    "HOSPITALIZ": "severity / outcome-related field",
    "EVOLUCAO": "outcome field (follows the diagnosis)",
    "TPAUTOCTO": "case classification detail (defines the diagnosis)",
    "COUFINF": "municipality of infection (geography; excluded)",
    "COPAISINF": "country of infection (geography; excluded)",
    "COMUNINF": "municipality of infection (geography; excluded)",
    "DT_NOTIFIC": "date field (time leakage)", "DT_SIN_PRI": "date field (time leakage)",
    "DT_NASC": "date of birth (identifier-like; age used instead)", "DT_INVEST": "date field",
    "DT_ENCERRA": "closing date (follows the diagnosis)", "ID_AGRAVO": "record identifier",
    "ID_MUNICIP": "geography identifier", "ID_UNIDADE": "health-unit identifier", "ID_REGIONA": "geography identifier",
    "ID_MN_RESI": "geography identifier", "ID_RG_RESI": "geography identifier", "ID_PAIS": "geography identifier",
    "SG_UF": "geography identifier", "SG_UF_NOT": "geography identifier", "CS_RACA": "not clinical (kept out for simplicity)",
    "CS_ESCOL_N": "not clinical (kept out for simplicity)", "SEM_NOT": "time field", "SEM_PRI": "time field",
    "NU_ANO": "year (time leakage)",
}


def decode_sinan_age(v) -> float:
    """SINAN age: first digit = unit (1 hours, 2 days, 3 months, 4 years)."""
    try:
        n = int(float(v))
    except (TypeError, ValueError):
        return np.nan
    unit, value = divmod(n, 1000)
    if unit == 4:
        return float(value)
    if unit == 3:
        return value / 12.0
    if unit in (1, 2):
        return 0.0
    return np.nan


def build_brazil() -> None:
    if not os.path.exists(BRAZIL_CSV):
        raise SystemExit(f"Brazil CSV not found at {BRAZIL_CSV}. Run: python ml/download_data.py")
    rng = np.random.default_rng(SEED)
    usecols = ["CLASSI_FIN", "NU_IDADE_N", "CS_SEXO", "CS_GESTANT"] + list(BRAZIL_FEATURES)
    pieces, total, counts = [], 0, Counter()
    for chunk in pd.read_csv(BRAZIL_CSV, usecols=usecols, chunksize=300_000, dtype=str):
        total += len(chunk)
        keep = rng.random(len(chunk)) < BRAZIL_SAMPLE_FRACTION
        sub = chunk[keep]
        pieces.append(sub)
    df = pd.concat(pieces, ignore_index=True)
    label_map = {"Dengue": "dengue", "Chikungunya": "chikungunya", "Discarded/Inconclusive": "neither"}
    df = df[df["CLASSI_FIN"].isin(label_map)].copy()
    out = pd.DataFrame({"age_years": df["NU_IDADE_N"].map(decode_sinan_age)})
    out["sex"] = df["CS_SEXO"].map({"M": "male", "F": "female"}).fillna("unknown")
    out["pregnant"] = df["CS_GESTANT"].map({"1": "1st trimester", "2": "2nd trimester", "3": "3rd trimester",
                                             "4": "not pregnant", "5": "not pregnant", "6": "not pregnant"}).fillna("unknown")
    for code, name in BRAZIL_FEATURES.items():
        out[name] = clean_binary(df[code]).values
    out["label"] = df["CLASSI_FIN"].map(label_map).values
    out.to_csv(os.path.join(PROC, "brazil_sinan_sample.csv"), index=False)
    record("brazil_sinan_arboviral", {
        "processed_file": "data/processed/brazil_sinan_sample.csv",
        "rows_raw": int(total), "rows_used": int(len(out)),
        "sampling": f"random Bernoulli sample, fraction {BRAZIL_SAMPLE_FRACTION}, seed {SEED}",
        "label_counts": {str(k): int(v) for k, v in out["label"].value_counts().items()},
        "features_used": len(BRAZIL_FEATURES) + 3,
        "excluded_columns": BRAZIL_EXCLUDED,
        "feature_map": {v: {"source_column": k} for k, v in BRAZIL_FEATURES.items()},
    })


# ---------- 4. TyphoDx-BD (Widal titres) ----------
def titre_to_log2(v):
    if not isinstance(v, str):
        return np.nan
    m = re.search(r"1:\s*(\d+)", v)
    return float(np.log2(int(m.group(1)))) if m else np.nan


def build_typhodx() -> None:
    df = pd.read_csv(os.path.join(RAW, "typhodx_bd_original.csv"), dtype=str)
    df.columns = [c.strip() for c in df.columns]
    label = df["Typhoid"].str.strip()
    keep = label.isin(["Positive", "Negative"])
    d = df[keep].copy()
    out = pd.DataFrame()
    age = d["Age"].fillna("")
    years = []
    for a in age:
        m = re.match(r"^(\d+)\s*([ym]?)", a.strip())
        if not m:
            years.append(np.nan)
        elif m.group(2) == "m":
            years.append(int(m.group(1)) / 12.0)
        else:
            years.append(float(m.group(1)))
    out["age_years"] = years
    out["sex"] = d["Gender"].str.strip().str.lower()
    widal = {"TO": "Widal O (TO)", "TH": "Widal H (TH)", "AH": "Widal AH", "BH": "Widal BH", "OX2": "Widal OX2",
             "OXK": "Widal OXK", "OX9": "Widal OX9", "A": "Widal A", "M": "Widal M"}
    for code, name in widal.items():
        out[f"{name} (log2 titre)"] = d[code].map(titre_to_log2).values
    out["Rickettsial infection suspected"] = d["Rickettsia_Suspect"].map({"Yes": 1.0, "No": 0.0}).values
    out["label"] = label[keep].map({"Positive": 1, "Negative": 0}).values
    out.to_csv(os.path.join(PROC, "typhodx_bd.csv"), index=False)
    excluded = {
        "Name": "encrypted patient token; identifier, never used or stored in processed data",
        "Acute_typhoid": "other diagnosis outcome (leakage)",
        "Paratyphoid_A": "other diagnosis outcome (leakage)",
        "Paratyphoid_B": "other diagnosis outcome (leakage)",
    }
    record("typhodx_bd_typhoid", {
        "processed_file": "data/processed/typhodx_bd.csv",
        "rows_raw": int(len(df)), "rows_used": int(keep.sum()),
        "rows_dropped": {"Typhoid = Minimal or missing (ambiguous)": int((~keep).sum())},
        "label_counts": {str(k): int(v) for k, v in out["label"].value_counts().items()},
        "features_used": len(widal) + 3, "excluded_columns": excluded,
    })


# ---------- 5. Sri Lanka leptospirosis (SPSS .sav) ----------
LEPTO_ADMISSION_PREFIXES = ("Feveronset", "Headacheonset", "Musclepainonset", "Cnsuffusiononset", "Jaundiceonset",
                            "Skinrashonset", "Oliguriaonset", "Anuriaonset", "SOBonset", "Coughonset", "Haemoptasisonset",
                            "Chestpainonset", "Nauseaonset", "Vomitingonset", "Diarrhoeaonset", "Bleedingonset",
                            "Mucosalrashonset", "Prostrationonset", "Rigorsonset", "Photophobiaonset", "Chillsonset",
                            "Muscletendernessonset", "Psychoticsymptomsonset", "Confusiononset")
LEPTO_ADMISSION = ("Feverad", "Headachead", "Chillsad", "Rigorsad", "Musclepainad", "Muscletendernessad", "Nauseaad",
                   "Vomitingadmission", "Cnsuffusionad", "Skinrashad", "Mucosalrashad", "Prostrationad", "Diarrhoeaad",
                   "OliguriaAd", "Anuriaad", "Jaundicead", "Hepatictendernessad", "Hepatomegalyad", "Spleenimegalyad",
                   "Lympadenopathyad", "Photophobiaad", "Neckstiffnessad", "Psychoticsymptomsad", "Confusionad",
                   "Coughad", "Haemoptasisad", "SOBadd", "Chestpainad", "PRad", "SBPadd", "DBPadd", "Bleedingad")


def build_leptospirosis() -> None:
    import pyreadstat
    df, _ = pyreadstat.read_sav(os.path.join(RAW, "leptospirosis_srilanka.sav"))
    cols = list(df.columns)
    start, end = cols.index("Possibleexposure"), cols.index("Feveronset")
    exposure_cols = cols[start:end]
    keep_cols = ["Age", "Sex", "Chronicillness"] + exposure_cols + [c for c in cols if c in LEPTO_ADMISSION_PREFIXES or c in LEPTO_ADMISSION]
    keep_cols = list(dict.fromkeys(keep_cols))
    excluded = {}
    for c in cols:
        if c in keep_cols:
            continue
        lc = c.lower()
        if c in ("Serial", "Indexno"):
            excluded[c] = "record identifier"
        elif c in ("Year", "Month"):
            excluded[c] = "time field (not a clinical feature)"
        elif c in ("Hospital", "ICU", "OPD"):
            excluded[c] = "care setting (not a clinical feature)"
        elif any(k in lc for k in ["mat", "pcr", "isolate", "final", "culture", "diagnosis", "qpcr"]) or c[:1].isupper() and c in (
                "Pomona", "Bratislava", "Canicola", "Icterohaemorrhagiae", "Mankarso", "Georgia", "Pyrogene", "Bataviae",
                "Wolfii", "Geyaweera", "Weerasinghe", "Ceylonica", "Alice", "Patoc", "Autumnalis", "Alex", "Ballum", "Djasiman",
                "Australis", "Tarassovi", "Ratnapura", "Borincana", "Celledoni", "Grippotyphosa", "Final"):
            excluded[c] = "microbiological or serological result (defines the diagnosis)"
        elif re.search(r"\d+$", c) and not c.startswith(("Feveronset",)):
            excluded[c] = "day-by-day series (time-varying, follows admission; not used)"
        elif c in ("Education", "TertiaryEducation", "Prophylactics", "Pasttreatments", "Pastantibiotics", "Income",
                   "Ethnicity", "Usualdrinkingwatersource", "Usualbathingwatersource", "Sourceofwaterforhousehold",
                   "Garbagedisposalprocedure", "Accumilationofrefusal", "Availabilityofpublicgarbagecollectionprocedure"):
            excluded[c] = "socio-demographic or household field (kept out to keep the model focused on exposure and symptoms)"
        else:
            excluded[c] = "laboratory variable (not used as a feature)"
    lab_label = pd.to_numeric(df["Final"], errors="coerce")
    d = df[keep_cols].copy()
    out = pd.DataFrame(index=d.index)
    for c in keep_cols:
        vals = pd.to_numeric(d[c], errors="coerce")
        out[c] = vals
    out["label"] = lab_label.map({1.0: 1, 2.0: 0}).astype("Int64")
    out = out[out["label"].notna()]
    out.to_csv(os.path.join(PROC, "srilanka_leptospirosis.csv"), index=False)
    record("srilanka_leptospirosis", {
        "processed_file": "data/processed/srilanka_leptospirosis.csv",
        "rows_raw": int(len(df)), "rows_used": int(len(out)),
        "label_counts": {str(k): int(v) for k, v in out["label"].value_counts().items()},
        "features_used": len(keep_cols) - 0, "excluded_columns": excluded,
    })


if __name__ == "__main__":
    os.makedirs(PROC, exist_ok=True)
    build_burkina()
    build_chittagong()
    build_typhodx()
    build_leptospirosis()
    build_brazil()
    for k, spec in DATASETS.items():
        manifest["datasets"].setdefault(k, {})
        manifest["datasets"][k].update({
            "title": spec.title, "source": spec.source_name, "source_urls": spec.source_urls,
            "licence": spec.licence, "citation": spec.citation, "raw_files": spec.raw_files,
            "raw_description": spec.n_raw_note, "notes": spec.notes,
        })
    with open(os.path.join(ROOT, "data", "dataset_manifest.json"), "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2, ensure_ascii=False, default=str)
    print(json.dumps({k: {kk: vv for kk, vv in v.items() if kk in ("rows_used", "label_counts")}
                      for k, v in manifest["datasets"].items()}, indent=1, ensure_ascii=False, default=str))
