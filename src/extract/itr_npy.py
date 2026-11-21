"""Extract the Ni-kshay Poshan Yojana (NPY) State tables (analysis plan sections 3.2,
3.3, 3.5 and 3.6).

Run: python -I src/extract/itr_npy.py   (from the repository root)

Reads the three NPY State annexures from the India TB Reports in data_raw/ and writes:

- data/extracted/npy_cells.csv: every extracted printed cell, one row per printed row
  (36 State/UT rows and the India row) and column, before coarsening, with its page
  and the cell as printed;
- data/extracted/npy_panel.csv: ``unit, year, measure, value, denominator_basis,
  source_file, pdf_page, table_id, flag``, one row per coarsened unit (33), data year
  (2021, 2022, 2023) and measure (denominator, bank_available, paid; bank_validated in
  2023 only). ``value`` is the printed count summed over the unit's printed rows.
  Nothing else is computed: no ratio, share, unpaid count or weight;
- data/extracted/npy_national_check.csv: the plan section 3.2 check that the India row
  of each State table prints the same "paid at least once" figure as the edition's
  national DBT table.

Tables (plan section 3.3):
  2021  TBAR 2022 section 9, PDF p. 143: TOTAL NOTIFICATION; BANK DETAILS AVAILABLE
        OF TOTAL NOTIFIED (count part); BENEFICIARIES PAID AT LEAST ONE BENEFIT OF TOTAL
        NOTIFIED (count part). Basis "notified".
  2022  ITR 2023 section 9, PDF pp. 323-324: the same three columns, printed as
        ``count (xx)``. Basis "notified".
  2023  ITR 2024 section 9, PDF p. 309: Eligible beneficiaries; Bank details available
        of total eligible; Bank details validated of total eligible; Beneficiaries paid
        at least one benefit of total eligible beneficiaries; counts only.
        Basis "eligible".

Rules (plan sections 3.5 and 3.6):
- Of a ``count (%)`` cell the count is used. A percent-only cell would be derived as
  round-half-up(base x % / 100) from the same row's denominator and flagged
  ``derived_from_percent``; no NPY cell needs this.
- A dash or NA cell is NA: the unit has no value, the row carries ``na_printed`` and
  ``NA:all_members_missing`` (or ``member_missing:<row>`` for a merged unit).
- Merged units sum their printed rows (DNH&DD into Gujarat, Lakshadweep into Kerala,
  Ladakh into Jammu and Kashmir).
- A step ratio above 1 is NOT turned into NA here and no count is changed. The row
  that carries the numerator is flagged ``impossible_chain:<step>:<reason>`` (``chain_na``
  is the rule), so that the analysis applies the plan's NA rule and lists the cell.
- A percentage printed above 100 is flagged ``percent_above_100``.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if __package__ in (None, ""):
    sys.path.insert(0, str(ROOT))

from src.extract import annex, crosswalk, readtable  # noqa: E402
from src.extract.readtable import Field as F  # noqa: E402
from src.extract.readtable import TableSpec  # noqa: E402

EXTRACTED = readtable.EXTRACTED
CELLS_CSV = EXTRACTED / "npy_cells.csv"
PANEL_CSV = EXTRACTED / "npy_panel.csv"
NATIONAL_CSV = EXTRACTED / "npy_national_check.csv"
PANEL_COLS = ["unit", "year", "measure", "value", "denominator_basis", "source_file",
              "pdf_page", "table_id", "flag"]
NATIONAL_COLS = ["year", "national_table", "national_pdf_page", "printed_national_paid",
                 "state_table_india_paid", "equal", "source_file"]

MEASURES = ("denominator", "bank_available", "bank_validated", "paid")

SPECS: dict[int, TableSpec] = {s.year: s for s in (
    TableSpec("TBAR2022_NPY", "TBAR 2022", "NPY State annexure (section 9)", (143,), 3, (
        F("denominator", 0, "TOTAL NOTIFICATION"),
        F("bank_available", 1, "BANK DETAILS AVAILABLE OF TOTAL NOTIFIED: count part",
          base="denominator"),
        F("paid", 2, "BENEFICIARIES PAID AT LEAST ONE BENEFIT OF TOTAL NOTIFIED: count part",
          base="denominator"),
    ), "NIKSHAY POSHAN YOJANA", "BANK DETAILS AVAILABLE|PAID AT LEAST ONE BENEFIT", 2021),
    TableSpec("ITR2023_NPY", "ITR 2023", "NPY State annexure (section 9)", (323, 324), 3, (
        F("denominator", 0, "TOTAL NOTIFICATION"),
        F("bank_available", 1, "BANK DETAILS AVAILABLE OF TOTAL NOTIFIED (%): count part",
          base="denominator"),
        F("paid", 2, "BENEFICIARIES PAID AT LEAST ONE BENEFIT OF TOTAL NOTIFIED (%): "
                     "count part", base="denominator"),
    ), "NI-KSHAY POSHAN YOJANA",
        "State/UTs/UTs TOTAL BANK DETAILS BENEFICIARIES PAID|"
        "NOTIFICATION AVAILABLE OF AT LEAST ONE BENEFIT|TOTAL NOTIFIED OF TOTAL NOTIFIED",
        2022),
    TableSpec("ITR2024_NPY", "ITR 2024", "NPY State annexure (section 9)", (309,), 4, (
        F("denominator", 0, "Eligible beneficiaries"),
        F("bank_available", 1, "Bank details available of total eligible"),
        F("bank_validated", 2, "Bank details validated of total eligible"),
        F("paid", 3, "Beneficiaries paid at least one benefit of total eligible beneficiaries"),
    ), "Nikshay Poshan Yojana",
        "Bank details Bank details|Eligible available of validated of least one benefit of "
        "total|States/UTs beneficiaries total eligible total eligible eligible beneficiaries",
        2023),
)}
YEARS = tuple(SPECS)
BASIS = {2021: "notified", 2022: "notified", 2023: "eligible"}
TABLES = {s.key: s for s in SPECS.values()}

# The national DBT table that states each data year (plan section 3.2): year ->
# (table, PDF page, the printed India "paid at least once" figure, digits only).
NATIONAL_TABLES: dict[int, tuple[str, int, int]] = {
    2021: ("TBAR 2022 National Figures, DBT schemes table", 45, 1326306),
    2022: ("ITR 2023 Table 8.1, column 2022", 115, 1601896),
    2023: ("ITR 2024 Table 8.2, column Jan-Dec 2023", 88, 1875510),
}

# Printed-total differences found at extraction (plan section 3.6): (table key, field)
# -> (sum of the 36 printed State/UT rows, printed India value). Recorded, not
# corrected; any other difference fails the check.
RECORDED_GAPS: dict[tuple[str, str], tuple[int, int]] = {}


# ---- the chain rule -----------------------------------------------------------------

def chain_na(d: int | None, b: int | None, q: int | None, v: int | None = None,
             with_validated: bool = False) -> dict[str, str]:
    """Plan section 3.6: the step ratios that are NA for one unit-year, with the reason.

    A = B/D (bank details available over the denominator), P = Q/B (paid over bank
    details), C = Q/D (paid over the denominator), V = validated/B (2023 only: pass
    ``v``, or ``with_validated=True`` when the validated count is missing). A step is NA when an input is missing, when its denominator is 0, or when
    its numerator exceeds its denominator (an impossible chain). Counts are never
    altered, and C is kept when Q <= D whatever B is.
    """
    out: dict[str, str] = {}
    steps = [("A", b, d, "bank_available", "denominator"),
             ("P", q, b, "paid", "bank_available"),
             ("C", q, d, "paid", "denominator")]
    if v is not None or with_validated:
        steps.append(("V", v, b, "bank_validated", "bank_available"))
    for step, num, den, num_name, den_name in steps:
        if num is None or den is None:
            out[step] = "input_missing"
        elif den == 0:
            out[step] = f"{den_name}_zero"
        elif num > den:
            out[step] = f"{num_name}_exceeds_{den_name}"
    return out


# The row (measure) that carries the numerator of each step, where the flag is written.
FLAG_ROW = {"A": "bank_available", "P": "paid", "C": "paid", "V": "bank_validated"}


# ---- panel ---------------------------------------------------------------------------

def panel_rows(tables: dict[str, readtable.Table],
               vals: dict[tuple[str, str, str], readtable.CellValue]) -> list[dict]:
    out = []
    for year, spec in SPECS.items():
        t = tables[spec.key]
        measures = [f.name for f in spec.fields]
        for unit in crosswalk.UNITS:
            rows: dict[str, dict] = {}
            for m_name in measures:
                value, flags, mem = readtable.merged_value(vals, spec.key, m_name, unit, year)
                rows[m_name] = {
                    "unit": unit, "year": year, "measure": m_name, "value": value,
                    "denominator_basis": BASIS[year], "source_file": spec.source_file,
                    "pdf_page": ";".join(str(p) for p in sorted({t.pages[m] for m in mem})),
                    "table_id": spec.table_id, "flag": flags,
                }
            # V (validated over bank details) exists only where validated is printed.
            na = chain_na(rows["denominator"]["value"], rows["bank_available"]["value"],
                          rows["paid"]["value"],
                          rows["bank_validated"]["value"] if "bank_validated" in rows
                          else None, with_validated="bank_validated" in rows)
            for step, reason in na.items():
                if reason != "input_missing":
                    rows[FLAG_ROW[step]]["flag"].append(f"impossible_chain:{step}:{reason}")
            for m_name in measures:
                r = rows[m_name]
                r["flag"] = ";".join(r["flag"])
                out.append(r)
    return out


def na_cells(panel: list[dict]) -> list[dict]:
    """The unit-year steps that the plan's rule makes NA, from the panel alone: one row
    per (unit, year, step) with the reason, for the impossible chains and for the NA
    cells (a missing input). Used by the check and by the analysis."""
    by: dict[tuple[str, int], dict[str, int | None]] = {}
    for r in panel:
        v = r["value"]
        by.setdefault((r["unit"], int(r["year"])), {})[r["measure"]] = \
            None if v in (None, "") else int(v)
    out = []
    for (unit, year), m in sorted(by.items()):
        na = chain_na(m.get("denominator"), m.get("bank_available"), m.get("paid"),
                      m.get("bank_validated"), with_validated="bank_validated" in m)
        for step, reason in na.items():
            out.append({"unit": unit, "year": year, "step": step, "reason": reason})
    return out


# ---- the national table check (plan section 3.2) --------------------------------------

def national_check(tables: dict[str, readtable.Table],
                   vals: dict[tuple[str, str, str], readtable.CellValue],
                   page_text=None) -> list[dict]:
    """For each data year: is the India "paid at least once" figure of the State table
    printed in the edition's national DBT table? ``page_text(file, page)`` returns the
    text of a PDF page (default: pdfplumber)."""
    if page_text is None:
        page_text = _page_text
    out = []
    for year, spec in SPECS.items():
        name, page, printed = NATIONAL_TABLES[year]
        india = vals[(spec.key, crosswalk.NATIONAL, "paid")].value
        text = re.sub(r"[,\s]", "", page_text(spec.source_file, page))
        found = str(printed) in text
        out.append({"year": year, "national_table": name, "national_pdf_page": page,
                    "printed_national_paid": printed, "state_table_india_paid": india,
                    "equal": bool(found and india == printed), "source_file": spec.source_file})
    return out


def _page_text(source_file: str, page: int) -> str:
    import pdfplumber

    with pdfplumber.open(ROOT / source_file) as pdf:
        pg = pdf.pages[page - 1]
        text = pg.extract_text() or ""
        pg.flush_cache()
        pg.close()
    return text


# ---- driver ---------------------------------------------------------------------------

def read_all() -> dict[str, readtable.Table]:
    return {s.key: readtable.read_table(s) for s in SPECS.values()}


def write_all(tables: dict[str, readtable.Table], out_dir: Path = EXTRACTED,
              page_text=None) -> dict[str, Path]:
    vals = readtable.cell_values(tables)
    paths = {"cells": out_dir / CELLS_CSV.name, "panel": out_dir / PANEL_CSV.name,
             "national": out_dir / NATIONAL_CSV.name}
    readtable.write_cells(paths["cells"], tables, vals, "year")
    annex.write_csv(paths["panel"], PANEL_COLS, panel_rows(tables, vals))
    annex.write_csv(paths["national"], NATIONAL_COLS, national_check(tables, vals, page_text))
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
    for n in national_check(tables, vals):
        print(f"{'ok' if n['equal'] else 'FAIL'}: {n['year']} India paid {n['state_table_india_paid']}"
              f" vs {n['national_table']} p. {n['national_pdf_page']}")
        if not n["equal"]:
            bad.append(f"{n['year']}: the State table's India paid figure is not the national "
                       f"table's; the year is excluded and recorded in plan section 12")
    for b in bad:
        print(f"FAIL: {b}")
    if bad:
        return 1
    for p in write_all(tables).values():
        print(f"wrote {p.relative_to(ROOT).as_posix()}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
