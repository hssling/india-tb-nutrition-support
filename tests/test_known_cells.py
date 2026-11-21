"""Pinned values, read by eye from the source pages, so that a wrong column, a wrong
row or a wrong page fails.

Every value below was read from the rendered PDF page (PyMuPDF images at 100-110 dpi),
not from the extraction: TBAR 2022 PDF pp. 89 and 143; ITR 2023 pp. 213-214, 251 and
323; ITR 2024 pp. 187, 222 and 309; NFHS-5 Phase I p. 85 and Phase II pp. 81 and 87.
Merged-unit values are the sums of the printed member rows, each read by eye. The
Annexure 1.6 values are those pinned in the diabetes study (re-read here).
"""
import csv
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
EXTRACTED = ROOT / "data" / "extracted"


def _read(name: str) -> list[dict]:
    with open(EXTRACTED / name, encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


CELLS = {(r["table_key"], r["printed_unit"], r["field"]): r["value"]
         for n in ("npy_cells.csv", "outcomes_cells.csv", "sector_cells.csv") for r in _read(n)}
NPY = {(r["unit"], int(r["year"]), r["measure"]): r for r in _read("npy_panel.csv")}
OUT = {(r["unit"], int(r["cohort_year"]), r["measure"]): r for r in _read("outcomes_panel.csv")}
SECTOR = {(r["unit"], int(r["year"]), r["measure"]): r for r in _read("sector_panel.csv")}
SEX = {r["printed_unit"]: r for r in _read("tb_sex_2022.csv")}
NFHS = {(r["unit"], r["sex"]): r["bmi_below_normal_pct"] for r in _read("nfhs_bmi.csv")}

DNHDD = "Dadra and Nagar Haveli and Daman and Diu"

# (table key, printed row, field): the count as printed (count part of a count (%) cell).
KNOWN_CELLS = {
    # 2021, TBAR 2022 NPY, PDF p. 143: TOTAL NOTIFICATION, bank details, paid at least once
    ("TBAR2022_NPY", "Himachal Pradesh", "denominator"): "14797",
    ("TBAR2022_NPY", "Himachal Pradesh", "bank_available"): "15075",  # 15075 (101.9%)
    ("TBAR2022_NPY", "Himachal Pradesh", "paid"): "14468",
    ("TBAR2022_NPY", "Delhi", "denominator"): "84367",
    ("TBAR2022_NPY", "Delhi", "bank_available"): "56734",
    ("TBAR2022_NPY", "Delhi", "paid"): "25504",
    ("TBAR2022_NPY", "Lakshadweep", "paid"): "18",
    ("TBAR2022_NPY", "Ladakh", "denominator"): "319",
    ("TBAR2022_NPY", DNHDD, "bank_available"): "774",  # 774 (101.4%)
    # 2022, ITR 2023 NPY, PDF p. 323: counts printed with a whole-number percent
    ("ITR2023_NPY", "Kerala", "denominator"): "23388",
    ("ITR2023_NPY", "Kerala", "bank_available"): "20473",  # 20473 (88)
    ("ITR2023_NPY", "Kerala", "paid"): "17170",  # 17170 (73)
    ("ITR2023_NPY", "Lakshadweep", "denominator"): "11",
    ("ITR2023_NPY", DNHDD, "denominator"): "1399",
    ("ITR2023_NPY", "Karnataka", "paid"): "50647",
    ("ITR2023_NPY", "Manipur", "paid"): "140",  # 140 (5)
    # 2023, ITR 2024 NPY, PDF p. 309: counts only, with a validated column
    ("ITR2024_NPY", "Kerala", "denominator"): "21726",
    ("ITR2024_NPY", "Kerala", "bank_available"): "19737",
    ("ITR2024_NPY", "Kerala", "bank_validated"): "18610",
    ("ITR2024_NPY", "Kerala", "paid"): "16098",
    ("ITR2024_NPY", "Lakshadweep", "paid"): "11",
    ("ITR2024_NPY", "Himachal Pradesh", "bank_validated"): "16103",
    ("ITR2024_NPY", "Punjab", "paid"): "2796",
    ("ITR2024_NPY", "Karnataka", "paid"): "52925",  # the other three cells print a dash
    ("ITR2024_NPY", "Karnataka", "denominator"): "",
    ("ITR2024_NPY", "Karnataka", "bank_available"): "",
    ("ITR2024_NPY", "Karnataka", "bank_validated"): "",
    # 2021 cohort, ITR 2023 Annexure 3.3, PDF p. 251
    ("ITR2023_A3.3", "Kerala", "cohort"): "21886",
    ("ITR2023_A3.3", "Kerala", "success"): "17394",  # 17394 (79.5)
    ("ITR2023_A3.3", "Kerala", "died"): "1779",
    ("ITR2023_A3.3", "Kerala", "ltfu"): "481",
    ("ITR2023_A3.3", "Bihar", "success"): "109250",
    ("ITR2023_A3.3", "Bihar", "ltfu"): "5156",
    ("ITR2023_A3.3", "Lakshadweep", "died"): "1",
    ("ITR2023_A3.3", "Ladakh", "cohort"): "320",
    # 2022 cohort, ITR 2024 Annexure 3.3, PDF p. 222 (rotated page)
    ("ITR2024_A3.3", "Kerala", "cohort"): "23135",
    ("ITR2024_A3.3", "Kerala", "success"): "18918",
    ("ITR2024_A3.3", "Kerala", "died"): "1950",
    ("ITR2024_A3.3", "Kerala", "ltfu"): "606",
    ("ITR2024_A3.3", "Bihar", "cohort"): "163263",
    ("ITR2024_A3.3", "Bihar", "died"): "5158",
    ("ITR2024_A3.3", "Lakshadweep", "success"): "21",
    ("ITR2024_A3.3", "Ladakh", "ltfu"): "1",
    # 2021, TBAR 2022 Annexure 1.2, PDF p. 89 (Public, Private, Total of "TB patients notified")
    ("TBAR2022_A1.2", "Kerala", "public"): "15364",
    ("TBAR2022_A1.2", "Kerala", "private"): "6508",  # 6508 (108%)
    ("TBAR2022_A1.2", "Kerala", "total"): "21872",
    ("TBAR2022_A1.2", "Lakshadweep", "public"): "12",
    ("TBAR2022_A1.2", "Lakshadweep", "private"): "",  # NA
    ("TBAR2022_A1.2", "Bihar", "private"): "70236",
    ("TBAR2022_A1.2", "Ladakh", "total"): "291",
    # 2022, ITR 2023 Annexure 1.2, PDF pp. 213-214
    ("ITR2023_A1.2", "Madhya Pradesh", "public"): "130830",
    ("ITR2023_A1.2", "Madhya Pradesh", "private"): "55463",
    ("ITR2023_A1.2", "Punjab", "total"): "55150",
    ("ITR2023_A1.2", "Lakshadweep", "private"): "0",  # 0 (NA): the printed count is taken
    ("ITR2023_A1.2", "Ladakh", "total"): "320",
    # 2023, ITR 2024 Annexure 1.2, PDF pp. 187-188 (rotated pages)
    ("ITR2024_A1.2", "Kerala", "public"): "15173",
    ("ITR2024_A1.2", "Kerala", "private"): "6626",
    ("ITR2024_A1.2", "Kerala", "total"): "21799",
    ("ITR2024_A1.2", "Bihar", "total"): "186974",
    ("ITR2024_A1.2", "Lakshadweep", "private"): "",  # NA
    ("ITR2024_A1.2", "Ladakh", "public"): "312",
}

# Coarsened units: (unit, year, measure) -> sum of the printed member rows.
KNOWN_NPY = {
    ("Himachal Pradesh", 2021, "bank_available"): "15075",
    ("Gujarat", 2021, "denominator"): str(141290 + 763),  # Gujarat + DNH&DD
    ("Kerala", 2021, "denominator"): str(22023 + 20),  # Kerala + Lakshadweep
    ("Kerala", 2022, "paid"): str(17170 + 11),
    ("Jammu and Kashmir", 2022, "denominator"): str(11804 + 320),  # J&K + Ladakh
    ("Kerala", 2023, "paid"): str(16098 + 11),
    ("Jammu and Kashmir", 2023, "bank_validated"): str(10487 + 317),
    ("Karnataka", 2023, "paid"): "52925",
    ("Karnataka", 2023, "denominator"): "",
}
KNOWN_OUT = {
    ("Kerala", 2021, "cohort"): str(21886 + 20),  # Kerala + Lakshadweep
    ("Jammu and Kashmir", 2022, "cohort"): str(11802 + 343),  # J&K + Ladakh
    ("Bihar", 2022, "died"): "5158",
}
KNOWN_SECTOR = {
    ("Kerala", 2021, "public"): str(15364 + 12),
    ("Kerala", 2021, "private"): "6508",  # Lakshadweep NA adds nothing
    ("Kerala", 2023, "total"): str(21799 + 6),
    ("Bihar", 2023, "total"): "186974",
}

# ITR 2023 A1.6, PDF p. 221: (male, female, transgender).
KNOWN_SEX = {
    "Kerala": ("15235", "8289", "5"),
    "Lakshadweep": ("13", "9", "0"),
    "Himachal Pradesh": ("10258", "6243", "4"),
    "Gujarat": ("93866", "54204", "55"),
}

# NFHS-5 Total column, item 86 (women) and item 87 (men), as printed.
KNOWN_NFHS = {
    ("Chandigarh", "women"): "13.0",  # Phase II p. 81; Rural is "*" and is not used
    ("Chandigarh", "men"): "15.1",
    ("Ladakh", "women"): "4.4",  # Phase I p. 85
    ("Ladakh", "men"): "2.1",
    ("Delhi", "women"): "10.0",  # Phase II p. 87, "NCT Delhi"
    ("Delhi", "men"): "9.1",
}


def test_at_least_twelve_values_across_every_table_type_and_year():
    keys = {k[0] for k in KNOWN_CELLS}
    assert keys >= {"TBAR2022_NPY", "ITR2023_NPY", "ITR2024_NPY", "ITR2023_A3.3",
                    "ITR2024_A3.3", "TBAR2022_A1.2", "ITR2023_A1.2", "ITR2024_A1.2"}
    assert len(KNOWN_CELLS) + len(KNOWN_NFHS) + len(KNOWN_SEX) >= 12
    assert {u for u, _ in KNOWN_NFHS} >= {"Ladakh", "Chandigarh", "Delhi"}
    # the bank-details-validated column exists in 2023 only
    assert {k[2] for k in KNOWN_CELLS if k[0] == "ITR2024_NPY"} >= {"bank_validated"}
    assert not any(k[2] == "bank_validated" for k in KNOWN_CELLS if k[0] != "ITR2024_NPY")


@pytest.mark.parametrize("key", sorted(KNOWN_CELLS))
def test_known_cells(key):
    assert CELLS[key] == KNOWN_CELLS[key]


@pytest.mark.parametrize("key", sorted(KNOWN_NPY))
def test_known_npy_panel(key):
    assert NPY[key]["value"] == KNOWN_NPY[key]


@pytest.mark.parametrize("key", sorted(KNOWN_OUT))
def test_known_outcomes_panel(key):
    assert OUT[key]["value"] == KNOWN_OUT[key]


@pytest.mark.parametrize("key", sorted(KNOWN_SECTOR))
def test_known_sector_panel(key):
    assert SECTOR[key]["value"] == KNOWN_SECTOR[key]


@pytest.mark.parametrize("unit", sorted(KNOWN_SEX))
def test_known_sex(unit):
    r = SEX[unit]
    assert (r["male"], r["female"], r["transgender"]) == KNOWN_SEX[unit]


@pytest.mark.parametrize("key", sorted(KNOWN_NFHS))
def test_known_nfhs(key):
    assert NFHS[key] == KNOWN_NFHS[key]
