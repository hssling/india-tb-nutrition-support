"""Extract the DS-TB treatment-outcome State tables, Annexure 3.3 (analysis plan
sections 3.3 and 3.4: the outcome cohorts of H3).

Run: python -I src/extract/itr_outcomes.py   (from the repository root)

Reads, from the India TB Reports in data_raw/:

- 2021 cohort: ITR 2023 Annexure 3.3 "TREATMENT OUTCOME OF TB PATIENTS NOTIFIED IN 2021
  (TOTAL)", PDF pp. 251-252;
- 2022 cohort: ITR 2024 Annexure 3.3 "Treatment outcome of TB patients notified in 2022
  (total)", PDF pp. 222-223.

(TBAR 2022 Annexure 3.3 is the 2020 cohort and is not used; no source prints the 2023
cohort.) Writes:

- data/extracted/outcomes_cells.csv: every extracted printed cell (36 State/UT rows and
  the India row) before coarsening, with its page and the cell as printed;
- data/extracted/outcomes_panel.csv: ``unit, cohort_year, measure, value, source_file,
  pdf_page, table_id, flag``, one row per coarsened unit (33), cohort year (2021, 2022)
  and measure (cohort, success, died, ltfu). ``value`` is the printed count summed over
  the unit's printed rows. No rate is computed.

``cohort`` is the column "TB patients Notified" (a bare count). ``success``, ``died``
and ``ltfu`` are the counts ``n`` of the ``n (%)`` cells of "Success Rate", "Death Rate"
and "Lost to follow up". A percent-only cell would be derived from the same row's cohort
size (round-half-up, flagged ``derived_from_percent``); no cell of these tables needs
it. A dash or NA cell is NA. An outcome count above the cohort size is flagged
``impossible_outcome:<measure>_exceeds_cohort`` (the count is kept); a percentage above
100 is flagged ``percent_above_100``.

The ITR 2024 table prints "Numerator is outcomes in DSTB patients initiated on
treatment, and Denominator is total notified DSTB cases by current facility"; no such
note was found for ITR 2023, so the two cohorts may differ in definition (plan section
10.4). That is recorded here as the flag ``cohort_definition_dstb_current_facility``
(ITR 2024 rows) and ``cohort_definition_not_stated`` (ITR 2023 rows).
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if __package__ in (None, ""):
    sys.path.insert(0, str(ROOT))

from src.extract import annex, crosswalk, readtable  # noqa: E402
from src.extract.readtable import Field as F  # noqa: E402
from src.extract.readtable import TableSpec  # noqa: E402

EXTRACTED = readtable.EXTRACTED
CELLS_CSV = EXTRACTED / "outcomes_cells.csv"
PANEL_CSV = EXTRACTED / "outcomes_panel.csv"
PANEL_COLS = ["unit", "cohort_year", "measure", "value", "source_file", "pdf_page",
              "table_id", "flag"]
MEASURES = ("cohort", "success", "died", "ltfu")

SPECS: dict[int, TableSpec] = {s.year: s for s in (
    TableSpec("ITR2023_A3.3", "ITR 2023", "Annexure 3.3", (251, 252), 8, (
        F("cohort", 0, "TB patients Notified"),
        F("success", 2, "Success Rate, n (%): count part", base="cohort"),
        F("died", 3, "Death Rate, n (%): count part", base="cohort"),
        F("ltfu", 4, "Lost to follow up, n (%): count part", base="cohort"),
    ), "3.3 TREATMENT OUTCOME OF TB PATIENTS|NOTIFIED IN 2021 (TOTAL)",
        "Cure Success Death Lost to Treatment Regimen Not", 2021),
    TableSpec("ITR2024_A3.3", "ITR 2024", "Annexure 3.3", (222, 223), 8, (
        F("cohort", 0, "TB patients notified"),
        F("success", 2, "Success rate, n(%): count part", base="cohort"),
        F("died", 3, "Death rate, n(%): count part", base="cohort"),
        F("ltfu", 4, "Lost to follow up, n(%): count part", base="cohort"),
    ), "3.3. Treatment outcome of TB patients notified in 2022 (total)",
        "TB patients Success Death rate, Lost to follow failure rate, Regimen Not evaluated,|"
        "States/UTs notified Cure rate, n (%)", 2022),
)}
COHORT_YEARS = tuple(SPECS)
DEFINITION_FLAG = {2021: "cohort_definition_not_stated",
                   2022: "cohort_definition_dstb_current_facility"}

# Printed-total differences (plan section 3.6): (table key, field) -> (State sum, printed).
RECORDED_GAPS: dict[tuple[str, str], tuple[int, int]] = {}


def panel_rows(tables: dict[str, readtable.Table],
               vals: dict[tuple[str, str, str], readtable.CellValue]) -> list[dict]:
    out = []
    for cy, spec in SPECS.items():
        t = tables[spec.key]
        for unit in crosswalk.UNITS:
            rows: dict[str, dict] = {}
            for m_name in MEASURES:
                value, flags, mem = readtable.merged_value(vals, spec.key, m_name, unit, cy)
                rows[m_name] = {
                    "unit": unit, "cohort_year": cy, "measure": m_name, "value": value,
                    "source_file": spec.source_file,
                    "pdf_page": ";".join(str(p) for p in sorted({t.pages[m] for m in mem})),
                    "table_id": spec.table_id, "flag": flags,
                }
            rows["cohort"]["flag"].append(DEFINITION_FLAG[cy])
            n = rows["cohort"]["value"]
            for m_name in MEASURES[1:]:
                v = rows[m_name]["value"]
                if n is not None and v is not None and v > n:
                    rows[m_name]["flag"].append(f"impossible_outcome:{m_name}_exceeds_cohort")
            for m_name in MEASURES:
                r = rows[m_name]
                r["flag"] = ";".join(r["flag"])
                out.append(r)
    return out


def read_all() -> dict[str, readtable.Table]:
    return {s.key: readtable.read_table(s) for s in SPECS.values()}


def write_all(tables: dict[str, readtable.Table], out_dir: Path = EXTRACTED) -> dict[str, Path]:
    vals = readtable.cell_values(tables)
    paths = {"cells": out_dir / CELLS_CSV.name, "panel": out_dir / PANEL_CSV.name}
    readtable.write_cells(paths["cells"], tables, vals, "cohort_year")
    annex.write_csv(paths["panel"], PANEL_COLS, panel_rows(tables, vals))
    return paths


def main() -> int:
    tables = read_all()
    vals = readtable.cell_values(tables)
    checks = readtable.total_checks(tables, vals)
    for c in checks:
        mark = "ok" if c["difference"] == 0 else "GAP"
        print(f"{mark}: {c['table_key']} {c['field']}: State sum {c['state_sum']}, "
              f"printed {c['printed']}, blanks {c['blank_cells']}")
    bad = readtable.unrecorded_gaps(checks, RECORDED_GAPS)
    for b in bad:
        print(f"FAIL: {b}")
    if bad:
        return 1
    for p in write_all(tables).values():
        print(f"wrote {p.relative_to(ROOT).as_posix()}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
