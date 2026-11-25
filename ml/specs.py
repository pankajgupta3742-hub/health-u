"""Dataset and model specifications for Health-U disease models.

Every model is defined here: the public dataset it comes from, its licence, the label, the features
it may use, and the columns that are excluded on purpose (with the reason). Nothing is trained on a
column that would leak the diagnosis (diagnostic tests, labels, outcomes, or the diagnosis itself).
"""
from dataclasses import dataclass, field

ROOT_RAW = "data/raw"
BRAZIL_ZIP_URL = "https://data.mendeley.com/public-api/zip/2d3kr8zynf/download/1"


@dataclass
class DatasetSpec:
    key: str
    title: str
    source_name: str
    source_urls: list[str]
    licence: str
    citation: str
    raw_files: list[str]
    n_raw_note: str
    notes: list[str] = field(default_factory=list)


DATASETS: dict[str, DatasetSpec] = {
    "burkina_vector_borne": DatasetSpec(
        key="burkina_vector_borne",
        title="Clinical dataset on malaria, dengue, yellow fever and other vector-borne diseases (Burkina Faso)",
        source_name="GitHub zombiboy/Tabular-dataset-for-AI-based-vector-borne-disease-prediction",
        source_urls=["https://github.com/zombiboy/Tabular-dataset-for-AI-based-vector-borne-disease-prediction",
                     "https://raw.githubusercontent.com/zombiboy/Tabular-dataset-for-AI-based-vector-borne-disease-prediction/main/data.csv",
                     "https://raw.githubusercontent.com/zombiboy/Tabular-dataset-for-AI-based-vector-borne-disease-prediction/main/desciption.xlsx"],
        licence="CC BY 4.0 (stated in the dataset README)",
        citation="Nazi Boni University, Burkina Faso (AI4D Africa). 300 consultations from the DO and DAFRA districts, Sept–Nov 2024.",
        raw_files=["vector_borne_burkina_faso.csv", "vector_borne_burkina_faso_description.xlsx"],
        n_raw_note="300 records, 109 columns, semicolon-separated, French/English headers",
    ),
    "chittagong_dengue": DatasetSpec(
        key="chittagong_dengue",
        title="Early detection of dengue, Chittagong and Cox's Bazar (Bangladesh)",
        source_name="GitHub TurhanSakib/Machine-Learning-based-Early-detection-of-dengue-Case-study-Chittagong",
        source_urls=["https://github.com/TurhanSakib/Machine-Learning-based-Early-detection-of-dengue-Case-study-Chittagong"],
        licence="MIT (repository licence). The README says the raw patient data is 'not included' and asks researchers to contact the authors, yet the CSV is present in the repository. Confirm permission with the authors before any public release.",
        citation="Sakib T. et al., BSc thesis, IIUC, Bangladesh. 308 patients from public and private hospitals.",
        raw_files=["dengue_chittagong.csv", "dengue_chittagong_README.md"],
        n_raw_note="308 records, 20 columns, normalised 0–2 scale values",
        notes=["Provenance conflict: see licence field."],
    ),
    "brazil_sinan_arboviral": DatasetSpec(
        key="brazil_sinan_arboviral",
        title="Brazil SINAN notifications: dengue and chikungunya",
        source_name="Mendeley Data 2d3kr8zynf (pre-processed SINAN notifications, Brazil 2013–2020)",
        source_urls=["https://data.mendeley.com/datasets/2d3kr8zynf/1", BRAZIL_ZIP_URL],
        licence="CC BY 4.0 (stated on Mendeley Data)",
        citation="Pre-processed SINAN (Brazilian national notifiable-disease system) data, 2013–2020, on Mendeley Data 2d3kr8zynf.",
        raw_files=[],  # 197 MB archive, 2 GB CSV: downloaded by ml/download_data.py, not stored in the workspace
        n_raw_note="6,732,542 rows, 56 columns; CLASSI_FIN: Dengue 4,307,513 / Discarded-Inconclusive 2,100,029 / Chikungunya 325,000",
        notes=["Surveillance data, not a triage population. Labels are the national case classification."],
    ),
    "typhodx_bd_typhoid": DatasetSpec(
        key="typhodx_bd_typhoid",
        title="TyphoDx-BD: clinically validated typhoid dataset (Bangladesh)",
        source_name="Mendeley Data m9pnvv2vpv",
        source_urls=["https://data.mendeley.com/datasets/m9pnvv2vpv/1", "https://data.mendeley.com/public-api/zip/m9pnvv2vpv/download/1"],
        licence="CC BY 4.0 (stated on Mendeley Data)",
        citation="TyphoDx-BD clinical dataset, 1,106 patients, Bangladesh, Oct 2024–Jan 2025 (Mendeley Data m9pnvv2vpv).",
        raw_files=["typhodx_bd_original.csv", "typhodx_bd_validation_certificate.pdf"],
        n_raw_note="1,106 records, 17 columns",
    ),
    "srilanka_leptospirosis": DatasetSpec(
        key="srilanka_leptospirosis",
        title="Febrile patients in Sri Lanka, leptospirosis confirmation (2016–2019)",
        source_name="Mendeley Data zmxmp42g9p",
        source_urls=["https://data.mendeley.com/datasets/zmxmp42g9p/1", "https://data.mendeley.com/public-api/zip/zmxmp42g9p/download/1"],
        licence="CC BY 4.0 (stated on Mendeley Data)",
        citation="Hospital-based study of febrile patients in Sri Lanka, 2016–2019 (Mendeley Data zmxmp42g9p).",
        raw_files=["leptospirosis_srilanka.sav"],
        n_raw_note="1,734 records, 806 variables (SPSS .sav)",
    ),
}


@dataclass
class ModelSpec:
    key: str
    title: str
    dataset: str
    task: str  # 'binary' or 'multiclass'
    label_column: str
    label_description: str
    intended_use: str
    requires_lab_input: bool
    limitations: list[str]


MODELS: dict[str, ModelSpec] = {
    "malaria": ModelSpec(
        key="malaria", title="Malaria (screening probability)", dataset="burkina_vector_borne", task="binary",
        label_column="label",
        label_description="Malaria listed as a diagnosis in the clinical record (diagnosis column = 1). Patients with the flag missing were dropped.",
        intended_use="Estimate how likely malaria is among febrile patients with the listed clinical features, to support testing decisions.",
        requires_lab_input=False,
        limitations=[
            "Only 29 negative patients in the whole dataset, so the negative class is very small and the metrics have wide confidence intervals.",
            "Rapid malaria test (TDR) and thick blood smear (goutte épaisse) are diagnostic tests, so they are excluded as features.",
            "One district pair in Burkina Faso (300 consultations). Not validated outside that setting.",
        ],
    ),
    "vector_borne": ModelSpec(
        key="vector_borne", title="Vector-borne fever (malaria, dengue, typhoid or yellow fever)", dataset="burkina_vector_borne",
        task="binary", label_column="label",
        label_description="Any of the four vector-borne diagnoses flagged in the clinical record (malaria, dengue, typhoid, yellow fever).",
        intended_use="Flag febrile patients whose features resemble a vector-borne infection, to prioritise diagnostic testing.",
        requires_lab_input=False,
        limitations=[
            "Small sample (300). Confidence intervals are wide.",
            "Label groups four different diseases; it does not say which one.",
            "Diagnostic test results and the free-text diagnosis column are excluded to prevent leakage.",
        ],
    ),
    "dengue": ModelSpec(
        key="dengue", title="Dengue (NS1-antigen positive)", dataset="chittagong_dengue", task="binary",
        label_column="label",
        label_description="NS1 antigen result positive (1) or negative (0), as recorded in the dataset.",
        intended_use="Estimate dengue NS1 positivity for febrile patients from age, vitals and symptoms, to support NS1 test ordering.",
        requires_lab_input=False,
        limitations=[
            "The label is itself a laboratory test (NS1). The model predicts NS1 positivity, not clinical dengue.",
            "IgG, IgM and platelet counts are laboratory results and are excluded.",
            "308 patients from two cities in Bangladesh. Not validated elsewhere.",
            "Licence/provenance needs confirmation (see dataset notes).",
        ],
    ),
    "dengue_chikungunya": ModelSpec(
        key="dengue_chikungunya", title="Dengue vs chikungunya vs neither (surveillance)", dataset="brazil_sinan_arboviral",
        task="multiclass", label_column="label",
        label_description="National SINAN case classification: Dengue, Chikungunya, or Discarded/Inconclusive (neither).",
        intended_use="Support clinical differentiation between dengue and chikungunya in the surveillance setting, with symptoms and demographics only.",
        requires_lab_input=False,
        limitations=[
            "Trained on a random 2% sample of 6.7 million national notifications (see manifest). Class mix is kept, but the model is not calibrated to any hospital.",
            "Laboratory results (NS1, PCR, serology, histopathology) and outcome fields are excluded as they define or follow the diagnosis.",
            "Symptom reporting in surveillance forms is incomplete; blanks are imputed.",
        ],
    ),
    "typhoid": ModelSpec(
        key="typhoid", title="Typhoid (clinical features, Widal titres excluded)", dataset="typhodx_bd_typhoid", task="binary",
        label_column="label",
        label_description="Typhoid column = Positive (1) or Negative (0). 'Minimal' results are dropped as ambiguous.",
        intended_use="Research only: estimate typhoid likelihood from age, sex and suspicion of rickettsial infection. Not a diagnostic tool.",
        requires_lab_input=False,
        limitations=[
            "Widal titres were excluded. Alone, they separate the label almost perfectly (depth-2 tree, CV AUC 1.000), so the label appears to be defined by them and a model using them would be circular.",
            "Without Widal titres the model has no reliable discrimination (test AUC about 0.56, CI includes 0.5). Do not use it.",
            "Acute-typhoid and paratyphoid columns are other outcomes and are excluded.",
            "Patient name (encrypted token) is dropped during preparation.",
        ],
    ),
    "leptospirosis": ModelSpec(
        key="leptospirosis", title="Leptospirosis (confirmed)", dataset="srilanka_leptospirosis", task="binary",
        label_column="label",
        label_description="Final diagnosis 'Confirmed' (1) versus 'Not detected' (0), per the dataset's final classification. Mapping verified against the .sav value labels (1 = Confirmed, 2 = Not detected; 591 and 1,143 rows).",
        intended_use="Estimate leptospirosis likelihood in febrile patients from admission symptoms and environmental exposure history.",
        requires_lab_input=False,
        limitations=[
            "MAT serology, PCR results, culture, isolates and all day-by-day laboratory series are excluded (they define the diagnosis).",
            "Hospital-based cohort from Sri Lanka (study period not checked against the source paper). Exposure answers come from patient recall.",
        ],
    ),
}
