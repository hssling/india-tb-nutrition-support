"""The payment chain and the unpaid counts (analysis plan sections 3.6, 5.1, 5.2).

For unit u and data year t, from data/extracted/npy_panel.csv: D the denominator, B the
number with bank details available, Q the number paid at least once, and (2023 only) the
number with bank details validated. A = B/D, P = Q/B, C = Q/D, V = validated/B and
paid/validated (2023, descriptive); U = D - Q, U_acc = D - B, U_pay = B - Q.

Which steps are NA is decided by the extraction's single rule, src.extract.itr_npy.chain_na
(plan section 3.6), and by nothing in this module:
- A NA (B > D, D = 0 or a missing input): A, U_acc and U_pay are NA;
- P NA (Q > B, B = 0 or a missing input): P and U_pay are NA (U_acc is kept);
- C NA (Q > D, D = 0 or a missing input): C is NA; U is NA unless Q <= D (with D = 0,
  only D = Q = 0, which gives U = 0).
paid/validated applies the same rule to (validated, paid), through chain_na's first step.
Counts are never altered and nothing is imputed.

Intervals: Jeffreys (2.5th and 97.5th percentiles of Beta(1/2 + x, 1/2 + n - x)) for each
unit-year ratio; Wilson for the national values.
"""
from __future__ import annotations

import csv
import math
from pathlib import Path

from scipy.stats import beta as beta_dist

from src.extract import itr_npy

ROOT = Path(__file__).resolve().parents[2]
PANEL = ROOT / "data" / "extracted" / "npy_panel.csv"
Z = 1.96

# step -> (numerator, denominator) of the ratio
STEPS = {"A": ("B", "D"), "P": ("Q", "B"), "C": ("Q", "D"), "V": ("Vd", "B"),
         "PV": ("Q", "Vd")}
MEASURE_KEY = {"denominator": "D", "bank_available": "B", "paid": "Q",
               "bank_validated": "Vd"}


def load(path: Path = PANEL) -> list[dict]:
    with open(path, encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def _int(v) -> int | None:
    return None if v in (None, "") else int(v)


def jeffreys(x: int | None, n: int | None) -> tuple[float | None, float | None]:
    if x is None or n is None or n <= 0:
        return None, None
    lo, hi = beta_dist.ppf([0.025, 0.975], 0.5 + x, 0.5 + n - x)
    return float(lo), float(hi)


def wilson(x: int | None, n: int | None, z: float = Z) -> tuple[float | None, float | None]:
    """Wilson score interval: centre (x + z^2/2)/(n + z^2), half-width
    z sqrt(x(n - x)/n + z^2/4)/(n + z^2)."""
    if x is None or n is None or n <= 0:
        return None, None
    c = (x + z * z / 2) / (n + z * z)
    h = z * math.sqrt(x * (n - x) / n + z * z / 4) / (n + z * z)
    return c - h, c + h


def _pv_reason(d_validated, q) -> str | None:
    """paid/validated: chain_na's first step applied to (validated, paid)."""
    r = itr_npy.chain_na(d_validated, q, None).get("A")
    if r is None:
        return None
    return r.replace("bank_available", "paid").replace("denominator", "bank_validated")


def _u_valid(na: dict[str, str], q: int | None) -> bool:
    """U = D - Q is kept whenever Q <= D (plan section 3.6: a unit with the chain NA still
    enters the unpaid count if Q <= D). From chain_na's C step: C not NA means Q <= D;
    C NA for a zero denominator means D = 0, where Q <= D holds only for Q = 0."""
    if "C" not in na:
        return True
    return na["C"] == "denominator_zero" and q == 0


def compute(npy_rows: list[dict]) -> list[dict]:
    """One row per unit-year (sorted by year, then unit): the counts, the ratios with
    Jeffreys intervals, the unpaid counts, the NA steps and the provenance."""
    by: dict[tuple[str, int], dict[str, dict]] = {}
    for r in npy_rows:
        by.setdefault((r["unit"], int(r["year"])), {})[r["measure"]] = r
    out = []
    for (unit, year) in sorted(by, key=lambda k: (k[1], k[0])):
        m = by[(unit, year)]
        v = {MEASURE_KEY[k]: _int(r["value"]) for k, r in m.items()}
        D, B, Q = v.get("D"), v.get("B"), v.get("Q")
        has_v = "Vd" in v
        Vd = v.get("Vd")
        na = dict(itr_npy.chain_na(D, B, Q, Vd, with_validated=has_v))
        if has_v:
            pv = _pv_reason(Vd, Q)
            if pv is not None:
                na["PV"] = pv
        row = {"unit": unit, "year": year,
               "denominator_basis": next(iter(m.values()))["denominator_basis"],
               "D": D, "B": B, "Q": Q, "Vd": Vd if has_v else None, "has_validated": has_v}
        for step, (num, den) in STEPS.items():
            if step in ("V", "PV") and not has_v:
                row[step] = row[f"{step}_lo"] = row[f"{step}_hi"] = None
                continue
            if step in na:
                row[step] = row[f"{step}_lo"] = row[f"{step}_hi"] = None
                continue
            x, n = row[num], row[den]
            row[step] = x / n
            row[f"{step}_lo"], row[f"{step}_hi"] = jeffreys(x, n)
        row["U"] = D - Q if _u_valid(na, Q) else None
        row["U_acc"] = None if "A" in na else D - B
        row["U_pay"] = None if ("A" in na or "P" in na) else B - Q
        row["na"] = na
        row["na_steps"] = ";".join(f"{s}:{na[s]}" for s in sorted(na))
        row["flag"] = ";".join(f"{k}:{r['flag']}" for k, r in m.items() if r["flag"])
        row["source_file"] = next(iter(m.values()))["source_file"]
        row["pdf_page"] = ";".join(sorted({p for r in m.values()
                                           for p in r["pdf_page"].split(";") if p}, key=int))
        row["table_id"] = next(iter(m.values()))["table_id"]
        out.append(row)
    return out


def na_listing(npy_rows: list[dict]) -> list[dict]:
    """The NA unit-year steps of plan section 3.6, as listed by the extraction's own
    itr_npy.na_cells (never re-derived here)."""
    return itr_npy.na_cells(npy_rows)


def national(chain_rows: list[dict], year: int) -> list[dict]:
    """A, P and C for the year over the units with the step non-NA (sums of the counts),
    with Wilson intervals and the number of units."""
    out = []
    rows = [r for r in chain_rows if r["year"] == year]
    for step in ("A", "P", "C"):
        num, den = STEPS[step]
        use = [r for r in rows if r[step] is not None]
        x = sum(r[num] for r in use)
        n = sum(r[den] for r in use)
        lo, hi = wilson(x, n)
        out.append({"year": year, "step": step, "numerator": x, "denominator": n,
                    "value": x / n if n else None, "lo": lo, "hi": hi,
                    "n_units": len(use),
                    "units_excluded": [r["unit"] for r in rows if r[step] is None]})
    return out
