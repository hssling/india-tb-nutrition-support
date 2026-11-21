"""Every source in data/source_manifest.csv is present in data_raw/ with the
recorded size and SHA-256 (the copies made by tools/fetch_sources.py), and the
manifest lists exactly the seven sources the study uses."""
import csv
import hashlib
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "data" / "source_manifest.csv"
COLUMNS = ["path", "origin", "bytes", "sha256"]

EXPECTED_PATHS = {
    "data_raw/india_tb_report/India-TB-Report-2019.pdf",
    "data_raw/india_tb_report/ITR2020.pdf",
    "data_raw/india_tb_report/TBAnnaulReport2022.pdf",
    "data_raw/india_tb_report/ITR2023.pdf",
    "data_raw/india_tb_report/ITR2024.pdf",
    "data_raw/nfhs5/NFHS-5_India_and_State_Factsheet_Compendium_Phase-I.pdf",
    "data_raw/nfhs5/NFHS-5_India_and_State_Factsheet_Compendium_Phase-II.pdf",
}


def _rows() -> list[dict]:
    with open(MANIFEST, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        assert reader.fieldnames == COLUMNS
        return list(reader)


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def test_manifest_has_rows_and_unique_paths():
    rows = _rows()
    paths = [r["path"] for r in rows]
    assert len(paths) == len(set(paths))
    assert set(paths) == EXPECTED_PATHS
    for r in rows:
        assert r["path"].startswith("data_raw/"), r["path"]
        assert len(r["sha256"]) == 64 and r["origin"], r


def test_manifest_digests_match():
    if not (ROOT / "data_raw").is_dir():
        pytest.skip("data_raw/ is not distributed; run python -I tools/fetch_sources.py")
    for r in _rows():
        path = ROOT / r["path"]
        assert path.is_file(), f"missing: {r['path']}"
        assert path.stat().st_size == int(r["bytes"]), r["path"]
        assert _sha256(path) == r["sha256"], r["path"]


def test_manifest_digests_equal_the_pinned_digests():
    from tools import fetch_sources
    pins = {path: (pinned, upstream) for path, _sib, upstream, pinned in fetch_sources.SOURCES}
    rows = _rows()
    assert {r["path"] for r in rows} == set(pins)
    for r in rows:
        assert r["sha256"] == pins[r["path"]][0], r["path"]
        assert ("upstream " + pins[r["path"]][1].split(" (")[0]) in r["origin"], r["path"]
