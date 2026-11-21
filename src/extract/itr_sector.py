"""Extract the notification-by-sector State tables (Annexure 1.2) and the 2022
notified-by-sex table (Annexure 1.6) (analysis plan sections 3.3 and 4.3).

Run: python -I src/extract/itr_sector.py   (from the repository root)

Reads, from the India TB Reports in data_raw/:

- 2021: TBAR 2022 Annexure 1.2 "TB Case Notification", PDF p. 89;
- 2022: ITR 2023 Annexure 1.2 "TB CASE NOTIFICATION", PDF pp. 213-214;
- 2023: ITR 2024 Annexure 1.2 "TB case notification", PDF pp. 187-188;
  the Public, Private and Total columns of "TB patients notified" (a printed
  ``count (%)`` cell: the count is used);
- 2022: ITR 2023 Annexure 1.6 "GENDER DISAGGREGATED DATA ON TOTAL TB NOTIFICATION,
  PAEDIATRIC TB NOTIFICATION AND TREATMENT INITIATION", PDF pp. 221-222, the columns
  "TB Cases Notified" (Male, Female, Trans Gender).

Writes:

- data/extracted/sector_cells.csv: every extracted printed cell of the three Annexure 1.2
  tables, before coarsening, with its page and the cell as printed;
- data/extracted/sector_panel.csv: ``unit, year, measure, value, source_file, pdf_page,
  table_id, flag``, one row per coarsened unit (33), data year (2021, 2022, 2023) and
  measure (public, private, total). ``value`` is the printed count summed over the
  unit's printed rows. No share is computed;
- data/extracted/tb_sex_2022.csv: the Annexure 1.6 counts, one row per printed row
  (36 rows and the India row), before coarsening (``printed_name, printed_unit, unit,
  male, female, transgender, source_file, pdf_page, table_id, flag``). Its logic is that
  of the diabetes study's tb_sex_2022.csv (re-extracted from the PDF here, not copied).

Rules as in itr_npy.py. A cell printed ``NA`` (the private column of Lakshadweep in TBAR
2022 and ITR 2024) is NA: the merged unit Kerala carries ``member_missing:Lakshadweep``
and the sum of the printed members. ITR 2023 prints ``0 (NA)`` for Lakshadweep private:
the printed count 0 is taken. The printed percentage is the achievement against the
target, which may exceed 100, so it is not flagged as an impossible cell.
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
CELLS_CSV = EXTRACTED / "sector_cells.csv"
PANEL_CSV = EXTRACTED / "sector_panel.csv"
SEX_CSV = EXTRACTED / "tb_sex_2022.csv"
PANEL_COLS = ["unit", "year", "measure", "value", "source_file", "pdf_page", "table_id",
              "flag"]
SEX_COLS = ["printed_name", "printed_unit", "unit", "male", "female", "transgender",
            "source_file", "pdf_page", "table_id", "flag"]
MEASURES = ("public", "private", "total")

_ROWS = "Public Private Total Public Private Total Public Private Total"
SPECS: dict[int, TableSpec] = {s.year: s for s in (
    TableSpec("TBAR2022_A1.2", "TBAR 2022", "Annexure 1.2", (89,), 9, (
        F("public", 3, "TB patients notified (Achievement against target %): Public, count part"),
        F("private", 4, "TB patients notified (Achievement against target %): Private, "
                        "count part"),
        F("total", 5, "TB patients notified (Achievement against target %): Total, count part"),
    ), "1.2 TB Case Notification",
        "Target TB patients expected to be notified|" + _ROWS, 2021, pct_is_share=False),
    TableSpec("ITR2023_A1.2", "ITR 2023", "Annexure 1.2", (213, 214), 9, (
        F("public", 3, "TB patients notified, n (% achievement against target): Public, "
                       "count part"),
        F("private", 4, "TB patients notified, n (% achievement against target): Private, "
                        "count part"),
        F("total", 5, "TB patients notified, n (% achievement against target): Total, "
                      "count part"),
    ), None, "Target TB patients expected|" + _ROWS, 2022, pct_is_share=False),
    TableSpec("ITR2024_A1.2", "ITR 2024", "Annexure 1.2", (187, 188), 9, (
        F("public", 3, "TB patients notified, n(% of achievement against target): Public, "
                       "count part"),
        F("private", 4, "TB patients notified, n(% of achievement against target): Private, "
                        "count part"),
        F("total", 5, "TB patients notified, n(% of achievement against target): Total, "
                      "count part"),
    ), "1.2. TB case notification", "Target of TB patients expected|" + _ROWS, 2023, pct_is_share=False),
)}
SEX_SPEC = TableSpec("ITR2023_A1.6", "ITR 2023", "Annexure 1.6", (221, 222), 9, (
    F("male", 0, "TB Cases Notified: Male"),
    F("female", 1, "TB Cases Notified: Female"),
    F("transgender", 2, "TB Cases Notified: Trans Gender"),
), "1.6 GENDER DISAGGREGATED DATA ON TOTAL TB NOTIFICATION", "TB Cases Notified", 2022)

# Printed-total differences (plan section 3.6): (table key, field) -> (State sum, printed).
RECORDED_GAPS: dict[tuple[str, str], tuple[int, int]] = {}


def panel_rows(tables: dict[str, readtable.Table],
               vals: dict[tuple[str, str, str], readtable.CellValue]) -> list[dict]:
    out = []
    for year, spec in SPECS.items():
        t = tables[spec.key]
        for unit in crosswalk.UNITS:
            for m_name in MEASURES:
                value, flags, mem = readtable.merged_value(vals, spec.key, m_name, unit, year)
                out.append({
                    "unit": unit, "year": year, "measure": m_name, "value": value,
                    "source_file": spec.source_file,
                    "pdf_page": ";".join(str(p) for p in sorted({t.pages[m] for m in mem})),
                    "table_id": spec.table_id, "flag": ";".join(flags),
                })
    return out


def sex_rows(tables: dict[str, readtable.Table],
             vals: dict[tuple[str, str, str], readtable.CellValue]) -> list[dict]:
    t = tables[SEX_SPEC.key]
    out = []
    for u in list(crosswalk.PRINTED[SEX_SPEC.year]) + [crosswalk.NATIONAL]:
        r = {s: vals[(SEX_SPEC.key, u, s)].value for s in ("male", "female", "transgender")}
        flags = []
        if u == crosswalk.NATIONAL:
            flags.append("national_row")
        flags += [f"blank:{s}" for s, v in r.items() if v is None]
        out.append({"printed_name": t.raw_names[u], "printed_unit": u,
                    "unit": "" if u == crosswalk.NATIONAL else crosswalk.coarsen(u), **r,
                    "source_file": SEX_SPEC.source_file, "pdf_page": t.pages[u],
                    "table_id": SEX_SPEC.table_id, "flag": ";".join(flags)})
    return out


def read_all() -> dict[str, readtable.Table]:
    return {s.key: readtable.read_table(s) for s in (*SPECS.values(), SEX_SPEC)}


def write_all(tables: dict[str, readtable.Table], out_dir: Path = EXTRACTED) -> dict[str, Path]:
    sector = {k: t for k, t in tables.items() if k != SEX_SPEC.key}
    vals = readtable.cell_values(tables)
    paths = {"cells": out_dir / CELLS_CSV.name, "panel": out_dir / PANEL_CSV.name,
             "sex": out_dir / SEX_CSV.name}
    readtable.write_cells(paths["cells"], sector, vals, "year")
    annex.write_csv(paths["panel"], PANEL_COLS, panel_rows(tables, vals))
    annex.write_csv(paths["sex"], SEX_COLS, sex_rows(tables, vals))
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
