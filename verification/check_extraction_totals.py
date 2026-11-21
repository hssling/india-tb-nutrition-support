"""Check the extracted tables against their printed India totals (analysis plan
sections 3.2, 3.5 and 3.6).

Run: python -I verification/check_extraction_totals.py   (from the repository root)

Adapted from hssling/india-tb-diabetes-gap (MIT), verification/check_extraction_totals.py
at tag v1.0.0 (DOI 10.5281/zenodo.24425259).

Reads only the committed extracts (no PDF is needed):

1. Printed totals. For every table and extracted column of data/extracted/npy_cells.csv,
   outcomes_cells.csv and sector_cells.csv, the sum of the 36 printed State/UT rows
   (before coarsening) is compared with the printed India row. A difference must be one
   recorded, with its size, in RECORDED_GAPS of the extraction module; any other
   difference fails. The same is done for data/extracted/tb_sex_2022.csv.
2. Coarsening. For every data year (cohort year) and measure, the 33 unit values of the
   panel sum to the printed rows of the cells file they are built from (merging adds the
   member rows and loses nothing), and each panel has 33 units x years x measures rows.
3. The national table (plan section 3.2). The India "paid at least once" figure of each
   State table equals the figure of the edition's national DBT table
   (data/extracted/npy_national_check.csv).

Then it lists the flagged cells: NA cells, impossible chains (counts above their
denominator, as flagged in npy_panel.csv) and percentages printed above 100. The
printed-total results are written to data/extracted/total_checks.csv. Exit status 1 if a
check fails.
"""
from __future__ import annotations

import csv
import sys
from decimal import Decimal
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.extract import itr_npy, itr_outcomes, itr_sector, readtable  # noqa: E402

EXTRACTED = ROOT / "data" / "extracted"
NATIONAL = "India"
N_ROWS = 36

# (cells file, panel file, year column, extraction module, expected panel rows)
GROUPS = (
    ("npy_cells.csv", "npy_panel.csv", "year", itr_npy, 330),
    ("outcomes_cells.csv", "outcomes_panel.csv", "cohort_year", itr_outcomes, 264),
    ("sector_cells.csv", "sector_panel.csv", "year", itr_sector, 297),
)


def _read(name: str) -> list[dict]:
    with open(EXTRACTED / name, encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def _num(s: str) -> int | Decimal | None:
    if s == "":
        return None
    return Decimal(s) if "." in s else int(s)


def printed_totals(cells: list[dict]) -> list[dict]:
    groups: dict[tuple[str, str], dict[str, int | Decimal | None]] = {}
    for r in cells:
        groups.setdefault((r["table_key"], r["field"]), {})[r["printed_unit"]] = _num(r["value"])
    out = []
    for (key, field), vals in groups.items():
        states = [v for u, v in vals.items() if u != NATIONAL]
        if len(vals) != N_ROWS + 1 or NATIONAL not in vals:
            raise SystemExit(f"FAIL: {key} {field}: {len(vals)} printed rows")
        s = sum((v for v in states if v is not None), start=type(vals[NATIONAL])(0))
        out.append({"table_key": key, "field": field, "state_sum": s,
                    "printed": vals[NATIONAL], "difference": s - vals[NATIONAL],
                    "blank_cells": sum(v is None for v in states)})
    return out


def sex_totals(rows: list[dict]) -> list[dict]:
    out = []
    for s in ("male", "female", "transgender"):
        states = [int(r[s]) for r in rows if r["printed_unit"] != NATIONAL and r[s] != ""]
        nat = int(next(r[s] for r in rows if r["printed_unit"] == NATIONAL))
        out.append({"table_key": "tb_sex_2022", "field": s, "state_sum": sum(states),
                    "printed": nat, "difference": sum(states) - nat,
                    "blank_cells": len(rows) - 1 - len(states)})
    return out


def coarsening(cells: list[dict], panel: list[dict], year_col: str, specs: dict,
               expected_rows: int) -> list[str]:
    """33 units x years x measures rows; per year and measure the panel sum equals the
    sum of the printed State/UT rows of the table (blank cells add nothing)."""
    bad = []
    if len(panel) != expected_rows:
        bad.append(f"panel has {len(panel)} rows, expected {expected_rows}")
    if len({r["unit"] for r in panel}) != 33:
        bad.append(f"panel has {len({r['unit'] for r in panel})} units, expected 33")
    for year, spec in specs.items():
        for f in spec.fields:
            printed = sum(int(r["value"]) for r in cells
                          if r["table_key"] == spec.key and r["field"] == f.name
                          and r["printed_unit"] != NATIONAL and r["value"] != "")
            merged = sum(int(r["value"]) for r in panel if int(r[year_col]) == year
                         and r["measure"] == f.name and r["value"] != "")
            if printed != merged:
                bad.append(f"{year} {f.name}: panel sum {merged} != printed rows {printed}")
    return bad


def national_table(rows: list[dict]) -> list[str]:
    bad = [f"{r['year']}: India paid {r['state_table_india_paid']} is not the national "
           f"table's {r['printed_national_paid']}" for r in rows if r["equal"] != "True"]
    if sorted(int(r["year"]) for r in rows) != [2021, 2022, 2023]:
        bad.append("npy_national_check.csv does not cover 2021, 2022 and 2023")
    return bad


def flagged_cells() -> list[str]:
    """One line per NA cell, impossible chain and percentage above 100."""
    out = []
    for r in _read("npy_panel.csv"):
        for fl in r["flag"].split(";"):
            if fl.startswith(("impossible_chain", "NA:")):
                out.append(f"npy_panel {r['unit']} {r['year']} {r['measure']}: {fl}")
    for r in _read("npy_cells.csv") + _read("outcomes_cells.csv"):
        for fl in r["flag"].split(";"):
            if fl.startswith(("percent_above_100", "na_printed")):
                out.append(f"{r['table_key']} {r['printed_unit']} {r['field']} "
                           f"({r['cell_printed']}): {fl}")
    for r in _read("sector_cells.csv"):
        if r["flag"].startswith("na_printed"):
            out.append(f"{r['table_key']} {r['printed_unit']} {r['field']} "
                       f"({r['cell_printed']}): {r['flag']}")
    return out


def _write(name: str, rows: list[dict]) -> None:
    with open(EXTRACTED / name, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]), lineterminator="\n")
        w.writeheader()
        w.writerows(rows)


def main() -> int:
    bad: list[str] = []
    all_checks: list[dict] = []
    for cells_name, panel_name, year_col, mod, n_rows in GROUPS:
        cells, panel = _read(cells_name), _read(panel_name)
        checks = printed_totals(cells)
        all_checks += checks
        bad += readtable.unrecorded_gaps(checks, mod.RECORDED_GAPS)
        bad += [f"{panel_name}: {b}" for b in
                coarsening(cells, panel, year_col, {s.year: s for s in mod.SPECS.values()},
                           n_rows)]
        for c in checks:
            mark = "ok " if c["difference"] == 0 else "GAP"
            print(f"{mark} {c['table_key']:>14} {c['field']:<14} State sum {c['state_sum']}, "
                  f"printed {c['printed']}, difference {c['difference']}, "
                  f"blank {c['blank_cells']}")
    sex = sex_totals(_read("tb_sex_2022.csv"))
    all_checks += sex
    for c in sex:
        print(f"{'ok ' if c['difference'] == 0 else 'GAP'} {c['table_key']:>14} {c['field']:<14} "
              f"State sum {c['state_sum']}, printed {c['printed']}, "
              f"difference {c['difference']}, blank {c['blank_cells']}")
    bad += [f"tb_sex_2022 {c['field']}: difference {c['difference']}"
            for c in sex if c["difference"] != 0]
    bad += national_table(_read("npy_national_check.csv"))
    _write("total_checks.csv", all_checks)
    print("flagged cells:")
    for line in flagged_cells():
        print("  " + line)
    for b in bad:
        print(f"FAIL: {b}")
    if bad:
        return 1
    print("OK: printed totals match or are recorded; coarsening preserves the totals; "
          "the State tables' India paid figures equal the national tables'")
    return 0


if __name__ == "__main__":
    sys.exit(main())
