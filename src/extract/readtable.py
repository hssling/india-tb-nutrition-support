"""Table reading shared by the extraction modules (itr_npy, itr_outcomes, itr_sector).

Adapted from hssling/india-tb-diabetes-gap (MIT), src/extract/itr_dm.py at tag v1.0.0
(DOI 10.5281/zenodo.24425259): ``derive_from_percent``, ``cell_count``, ``read_table``,
the printed-total comparison and the merged-unit sum are the same logic; the table
specifications and the panels are this study's own (analysis plan section 3).

Rules (plan sections 3.3 and 3.6):
- Of a ``count (%)`` cell the count is used, never the percentage.
- Where a needed cell prints only a percentage, the count is derived as
  round-half-up(base x % / 100) and flagged ``derived_from_percent`` with the range
  of whole counts that print the same percentage.
- A dash or NA cell is NA (no value). Nothing is imputed.
- Printed counts are summed across the printed rows of a merged unit; a member row
  that is blank adds nothing and the unit carries ``member_missing:<row>``.
"""
from __future__ import annotations

import math
import sys
from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if __package__ in (None, ""):
    sys.path.insert(0, str(ROOT))

from src.extract import annex, cells, crosswalk  # noqa: E402

EXTRACTED = ROOT / "data" / "extracted"

FILES = {
    "TBAR 2022": "data_raw/india_tb_report/TBAnnaulReport2022.pdf",
    "ITR 2023": "data_raw/india_tb_report/ITR2023.pdf",
    "ITR 2024": "data_raw/india_tb_report/ITR2024.pdf",
}
YEAR_OF = {"TBAR 2022": 2021, "ITR 2023": 2022, "ITR 2024": 2023}


@dataclass(frozen=True)
class Field:
    name: str
    index: int  # 0-based value cell after the name
    header: str  # verbatim column header (plan section 3.3)
    base: str | None = None  # field of the same table that is the base of its percentage


@dataclass(frozen=True)
class TableSpec:
    key: str
    edition: str
    table_id: str
    pages: tuple[int, ...]
    ncells: int  # value cells per row
    fields: tuple[Field, ...]
    title: str | None  # text on the first page (None: not in the text layer)
    header: str  # text on every page
    year: int  # data year of the table; for outcomes, the cohort year
    region: tuple[float, float] | None = None
    # False where the printed percentage is not a share of a base in the chain (the
    # Annexure 1.2 percentage is the achievement against a target and may exceed 100).
    pct_is_share: bool = True

    @property
    def source_file(self) -> str:
        return FILES[self.edition]

    def field(self, name: str) -> Field:
        return next(f for f in self.fields if f.name == name)


# ---- cell values ------------------------------------------------------------------

def _pct(text: str) -> Decimal:
    """'(67%)' / '(91.5)' -> Decimal('67') / Decimal('91.5')."""
    t = text.strip()
    if not (t.startswith("(") and t.endswith(")")):
        raise ValueError(f"not a percentage: {text!r}")
    t = t[1:-1].replace("%", "").strip()
    try:
        return Decimal(t)
    except ArithmeticError:
        raise ValueError(f"not a percentage: {text!r}") from None


def pct_value(text: str) -> Decimal | None:
    """The percentage of a printed '(xx)' / '(xx%)' token, or None for NA or empty."""
    t = text.strip().replace(" ", "")
    if "NA" in t or t in ("(%)", "()"):
        return None
    return _pct(t)


def derive_from_percent(base: int, pct_text: str) -> tuple[int, int, int]:
    """(count, lo, hi) for a cell that prints only a percentage of `base`.

    count = round-half-up(base x pct / 100); [lo, hi] are the whole counts whose
    percentage rounds to the printed value (half a unit of its last digit).
    """
    p = _pct(pct_text)
    half = Decimal(1).scaleb(p.as_tuple().exponent) / 2
    count = int((Decimal(base) * p / 100).quantize(Decimal(1), rounding=ROUND_HALF_UP))
    lo = max(0, math.ceil(Decimal(base) * (p - half) / 100))
    hi = min(base, math.floor(Decimal(base) * (p + half) / 100))
    if lo > hi:
        raise ValueError(f"no count of {base} prints as {pct_text!r}")
    return count, lo, hi


def cell_count(cell: annex.Cell | None, base: int | None, where: str
               ) -> tuple[int | None, list[str]]:
    """(count, flags) of one printed cell. A blank or absent cell gives None. A
    percent-only cell is derived from `base` and flagged ``derived_from_percent``."""
    if cell is None:
        return None, []
    if cell.n is not None:
        try:
            return cells.parse_int(cell.n), []
        except ValueError as e:
            raise ValueError(f"{where}: {e}") from None
    if cell.pct is None or pct_value(cell.pct) is None:
        return None, []
    if base is None:
        raise ValueError(f"{where}: percent-only cell {cell.raw!r} has no base")
    v, lo, hi = derive_from_percent(base, cell.pct)
    return v, [f"derived_from_percent:{cell.pct.strip()}_of_{base}_range_{lo}-{hi}"]


# ---- reading ----------------------------------------------------------------------

@dataclass
class Table:
    spec: TableSpec
    cells: dict[str, list[annex.Cell | None]]  # printed unit (and "India") -> cells
    pages: dict[str, int]
    raw_names: dict[str, str]


def _squash(s: str) -> str:
    return "".join(s.split()).casefold()


def read_table(spec: TableSpec, pdf_path: Path | None = None) -> Table:
    import pdfplumber  # only the extraction needs it

    from src.extract import grid, pdftext

    path = pdf_path or ROOT / spec.source_file
    rows: dict[str, list[annex.Cell | None]] = {}
    pages: dict[str, int] = {}
    raw: dict[str, str] = {}
    with pdfplumber.open(path) as pdf:
        for i, p in enumerate(spec.pages):
            chars, w, h = pdftext.page_chars(pdf, p)
            lines = grid.lines_of(chars, w, h, spec.region)
            text = "".join("".join(t.text for t in ln.tokens) for ln in lines).casefold()
            # Title and header are checked as "|"-separated fragments, each a run of
            # text on one printed line (headers wrap, so one string would not match).
            if i == 0 and spec.title is not None:
                for frag in spec.title.split("|"):
                    if _squash(frag) not in text:
                        raise ValueError(f"{spec.key}: title {frag!r} not on PDF p. {p}")
            for frag in spec.header.split("|"):
                if _squash(frag) not in text:
                    raise ValueError(f"{spec.key}: header {frag!r} not on PDF p. {p}")
            try:
                pr = grid.read_page(chars, w, h, spec.year, spec.ncells, spec.region)
            except ValueError as e:
                raise ValueError(f"{spec.key} PDF p. {p}: {e}") from None
            found = list(pr.rows.items())
            if pr.national is not None:
                found.append((crosswalk.NATIONAL, pr.national))
            for name, cs in found:
                if name in rows:
                    raise ValueError(f"{spec.key}: {name} printed on two pages")
                rows[name], pages[name], raw[name] = cs, p, pr.raw_names[name]
    if crosswalk.NATIONAL not in rows:
        raise ValueError(f"{spec.key}: no India row")
    missing = [u for u in crosswalk.PRINTED[spec.year] if u not in rows]
    if missing:
        raise ValueError(f"{spec.key}: printed rows not found: {missing}")
    return Table(spec, rows, pages, raw)


@dataclass
class CellValue:
    value: int | None
    flags: list[str]


def cell_values(tables: dict[str, Table]) -> dict[tuple[str, str, str], CellValue]:
    """(table key, printed unit or "India", field) -> value. A percent-only cell is
    derived from its base field of the same row (``Field.base``), read first. A
    percentage printed above 100 is flagged ``percent_above_100`` (listed as an
    impossible cell, plan section 3.6; not for a table whose percentage is the
    achievement against a target, ``pct_is_share``); the printed count is still taken."""
    out: dict[tuple[str, str, str], CellValue] = {}
    for t in tables.values():
        spec = t.spec
        ordered = sorted(spec.fields, key=lambda f: f.base is not None)
        for u, cs in t.cells.items():
            for f in ordered:
                where = f"{spec.key} {u} {f.name}"
                c = cs[f.index]
                base = None
                if f.base is not None:
                    base = out[(spec.key, u, f.base)].value
                v, flags = cell_count(c, base, where)
                if v is None and c is not None:
                    flags = flags + [f"na_printed:{c.raw}"]
                if spec.pct_is_share and c is not None and c.pct is not None:
                    p = pct_value(c.pct)
                    if p is not None and p > 100:
                        flags = flags + [f"percent_above_100:{c.pct.strip()}"]
                out[(spec.key, u, f.name)] = CellValue(v, flags)
    for t in tables.values():
        blank = [f.name for f in t.spec.fields
                 if out[(t.spec.key, crosswalk.NATIONAL, f.name)].value is None]
        if blank:
            raise ValueError(f"{t.spec.key}: India row blank in {blank}")
    return out


def total_checks(tables: dict[str, Table], vals: dict[tuple[str, str, str], CellValue]
                 ) -> list[dict]:
    """One row per table and extracted column: State sum (36 printed rows, blank
    cells left out), printed India value, the difference and the blank count."""
    out = []
    for key, t in tables.items():
        for f in t.spec.fields:
            states = [vals[(key, u, f.name)].value for u in crosswalk.PRINTED[t.spec.year]]
            s, nat, blanks = annex.total_gaps(states, vals[(key, crosswalk.NATIONAL, f.name)].value)
            out.append({"table_key": key, "field": f.name, "state_sum": s, "printed": nat,
                        "difference": s - nat, "blank_cells": blanks})
    return out


def unrecorded_gaps(checks: list[dict], recorded: dict[tuple[str, str], tuple]) -> list[str]:
    """Differences not in `recorded`, and recorded gaps that are not found."""
    bad = []
    keys = {(c["table_key"], c["field"]) for c in checks}
    for c in checks:
        k = (c["table_key"], c["field"])
        if c["difference"] != 0:
            if recorded.get(k) != (c["state_sum"], c["printed"]):
                bad.append(f"{k[0]} {k[1]}: State sum {c['state_sum']} vs printed "
                           f"{c['printed']} (difference {c['difference']}) is not recorded")
        elif k in recorded:
            bad.append(f"{k[0]} {k[1]}: recorded gap {recorded[k]} no longer present")
    for k in recorded:
        if k not in keys:
            bad.append(f"recorded gap for unknown column {k}")
    return bad


def cell_rows(tables: dict[str, Table], vals: dict[tuple[str, str, str], CellValue],
              cols_year: str = "year") -> list[dict]:
    out = []
    for key, t in tables.items():
        for u in list(crosswalk.PRINTED[t.spec.year]) + [crosswalk.NATIONAL]:
            for f in t.spec.fields:
                c = t.cells[u][f.index]
                cv = vals[(key, u, f.name)]
                out.append({
                    "edition": t.spec.edition, cols_year: t.spec.year, "table_key": key,
                    "source_file": t.spec.source_file,
                    "table_id": t.spec.table_id, "pdf_page": t.pages[u],
                    "printed_name": t.raw_names[u], "printed_unit": u,
                    "unit": "" if u == crosswalk.NATIONAL else crosswalk.coarsen(u),
                    "field": f.name, "column_header": f.header,
                    "cell_printed": "" if c is None else c.raw,
                    "value": cv.value, "flag": ";".join(cv.flags),
                })
    return out


def merged_value(vals: dict[tuple[str, str, str], CellValue], key: str, fieldname: str,
                 unit: str, year: int) -> tuple[int | None, list[str], tuple[str, ...]]:
    """(value summed over the unit's printed rows, flags, the printed member rows). A
    blank member adds nothing and is flagged; all members blank gives None."""
    mem = crosswalk.members(unit, year)
    total, used, flags = 0, [], []
    for m in mem:
        cv = vals[(key, m, fieldname)]
        if cv.value is None:
            flags.append(f"member_missing:{m}")
            flags += [f"{fl}@{m}" if len(mem) > 1 else fl for fl in cv.flags]
            continue
        total += cv.value
        used.append(m)
        flags += [f"{fl}@{m}" if len(mem) > 1 else fl for fl in cv.flags]
    if len(mem) > 1:
        flags.append("merged:" + "+".join(mem))
    if not used:
        flags.append("NA:all_members_missing")
        return None, flags, mem
    return total, flags, mem


def write_cells(path: Path, tables: dict[str, Table],
                vals: dict[tuple[str, str, str], CellValue], year_col: str) -> None:
    """Every extracted printed cell (36 State/UT rows and the India row) before
    coarsening, with its page and the cell as printed."""
    cols = ["edition", year_col, "table_key", "source_file", "table_id", "pdf_page",
            "printed_name", "printed_unit", "unit", "field", "column_header",
            "cell_printed", "value", "flag"]
    annex.write_csv(path, cols, cell_rows(tables, vals, year_col))


def impossible_cells(vals: dict[tuple[str, str, str], CellValue]) -> list[tuple]:
    """(table key, printed unit, field, flag) for every printed cell carrying
    ``percent_above_100`` (plan section 3.6: listed as an impossible cell)."""
    return [(k[0], k[1], k[2], fl) for k, cv in vals.items() for fl in cv.flags
            if fl.startswith("percent_above_100")]
