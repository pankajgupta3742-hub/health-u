"""Downloads the raw public datasets used by the Health-U disease models.

Usage (from the project root):
    python ml/download_data.py                 # everything except the large Brazil zip
    python ml/download_data.py --brazil        # also fetch the Brazil SINAN zip (~ hundreds of MB)

Destinations:
    data/raw/                 small files (Burkina Faso, Chittagong, TyphoDx-BD, Sri Lanka leptospirosis)
    /var/tmp/healthu_raw/     Brazil SINAN zip and extracted CSV (too large for the 1 GB /tmp tmpfs)

Each file is written only if it is missing, so re-running is safe. Every download is checked against
its expected minimum size, and the script exits with an error if any dataset is unreachable.
Licences and citations are recorded in ml/specs.py and in data/dataset_manifest.json.
"""
import argparse
import io
import json
import os
import shutil
import sys
import urllib.request
import zipfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RAW = os.path.join(ROOT, "data", "raw")
BRAZIL_DIR = os.environ.get("HEALTHU_BRAZIL_DIR", "/var/tmp/healthu_raw")
UA = "Health-U dataset fetcher (research use; contact: project owner)"

GH = "https://raw.githubusercontent.com/zombiboy/Tabular-dataset-for-AI-based-vector-borne-disease-prediction/main/"
MENDELEY_ZIP = "https://data.mendeley.com/public-api/zip/{id}/download/1"
CHITTAGONG_API = "https://api.github.com/repos/TurhanSakib/Machine-Learning-based-Early-detection-of-dengue-Case-study-Chittagong/contents"

SMALL = [
    # (destination file in data/raw, URL, minimum expected bytes)
    ("vector_borne_burkina_faso.csv", GH + "data.csv", 10_000),
    ("vector_borne_burkina_faso_description.xlsx", GH + "desciption.xlsx", 5_000),
]
MENDELEY_SMALL = [
    # (Mendeley dataset id, [(member name in zip, destination in data/raw)])
    ("zmxmp42g9p", [("Leptospirosis clinical data.sav", "leptospirosis_srilanka.sav")]),
    ("m9pnvv2vpv", [(None, "typhodx_bd_original.csv"), (None, "typhodx_bd_validation_certificate.pdf")]),
]


def fetch(url: str) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=120) as r:
        return r.read()


def save(dest: str, data: bytes, min_bytes: int):
    if len(data) < min_bytes:
        raise RuntimeError(f"{dest}: only {len(data)} bytes, expected at least {min_bytes}")
    os.makedirs(os.path.dirname(dest), exist_ok=True)
    with open(dest, "wb") as f:
        f.write(data)
    print(f"  saved {dest} ({len(data):,} bytes)")


def download_small():
    for name, url, min_bytes in SMALL:
        dest = os.path.join(RAW, name)
        if os.path.exists(dest):
            print(f"  exists {dest}")
            continue
        print(f"  fetching {url}")
        save(dest, fetch(url), min_bytes)


def download_chittagong():
    dest = os.path.join(RAW, "dengue_chittagong.csv")
    if os.path.exists(dest):
        print(f"  exists {dest}")
        return
    listing = json.loads(fetch(CHITTAGONG_API).decode("utf-8"))
    csv_item = next(i for i in listing if i["name"].lower().endswith(".csv"))
    save(dest, fetch(csv_item["download_url"]), 10_000)
    readme = next((i for i in listing if i["name"].lower().startswith("readme")), None)
    if readme:
        save(os.path.join(RAW, "dengue_chittagong_README.md"), fetch(readme["download_url"]), 100)


def download_mendeley_small():
    for dataset_id, members in MENDELEY_SMALL:
        wanted = [os.path.join(RAW, dest) for _, dest in members]
        if all(os.path.exists(p) for p in wanted):
            print(f"  exists {dataset_id} files")
            continue
        print(f"  fetching Mendeley {dataset_id}")
        z = zipfile.ZipFile(io.BytesIO(fetch(MENDELEY_ZIP.format(id=dataset_id))))
        for member, dest in members:
            target = os.path.join(RAW, dest)
            if os.path.exists(target):
                continue
            ext = os.path.splitext(dest)[1]
            # Use the named member, or the first file in the zip with the same extension.
            name = member or next(n for n in z.namelist() if n.lower().endswith(ext))
            with z.open(name) as src, open(target, "wb") as out:
                shutil.copyfileobj(src, out)
            print(f"  saved {target} (from {name})")


def download_brazil():
    os.makedirs(BRAZIL_DIR, exist_ok=True)
    zip_path = os.path.join(BRAZIL_DIR, "2d3kr8zynf.zip")
    if not os.path.exists(zip_path):
        print("  fetching Brazil SINAN zip (large)")
        req = urllib.request.Request(MENDELEY_ZIP.format(id="2d3kr8zynf"), headers={"User-Agent": UA})
        with urllib.request.urlopen(req, timeout=1800) as r, open(zip_path, "wb") as out:
            shutil.copyfileobj(r, out, length=1 << 20)
    csv_path = os.path.join(BRAZIL_DIR, "data set.csv")
    if not os.path.exists(csv_path):
        with zipfile.ZipFile(zip_path) as z:
            member = next(n for n in z.namelist() if n.lower().endswith(".csv"))
            with z.open(member) as src, open(csv_path, "wb") as out:
                shutil.copyfileobj(src, out, length=1 << 20)
    print(f"  Brazil CSV at {csv_path}; set HEALTHU_BRAZIL_CSV to this path if it differs")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--brazil", action="store_true", help="also fetch the large Brazil SINAN zip")
    args = ap.parse_args()
    steps = [("Burkina Faso vector-borne", download_small),
             ("Chittagong dengue", download_chittagong),
             ("Sri Lanka leptospirosis and TyphoDx-BD (Mendeley)", download_mendeley_small)]
    if args.brazil:
        steps.append(("Brazil SINAN (large)", download_brazil))
    failed = []
    for label, fn in steps:
        print(label)
        try:
            fn()
        except Exception as e:  # report and continue, so one dataset cannot hide others
            print(f"  FAILED: {e}", file=sys.stderr)
            failed.append(label)
    if failed:
        print("Failed:", ", ".join(failed), file=sys.stderr)
        sys.exit(1)
    print("All requested datasets are present.")


if __name__ == "__main__":
    main()
