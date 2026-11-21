"""The illustrative budget (analysis plan section 9).

- Main: U(2023) x Rs 1,000 x 6 months, U(2023) the sum over the units with data (the
  units excluded are named). Its interval is that of sum_u U^(d) over the 2023 draws.
- Ranges: rate in {Rs 500, Rs 1,000} per month x months in {6, 8}.
- Benchmark scenario: C_bench = the pct-th percentile (75 main; 50, 90) across the units
  with non-NA U of C_hat_u = 1 - post_mean_u; the national number paid at least once in
  the scenario = sum_u D_u max(C_u, C_bench), cost x Rs 6,000; the increment over the
  current number = sum_u D_u max(0, C_bench - C_u), cost x Rs 6,000.

Every figure is an illustration, not a forecast. It counts people not paid at least once
and does not count instalments owed to people paid at least once, so it understates the
gap.
"""
from __future__ import annotations

import numpy as np

YEAR = 2023
RATE_MAIN, MONTHS_MAIN = 1000, 6
RATES, MONTHS = (500, 1000), (6, 8)
SCENARIO_TOTAL = 6000
NOTE = ("an illustration, not a forecast; counts people not paid at least once and not "
        "instalments owed to people paid at least once, so it understates the gap")


def c_bench(C_hat: dict[str, float], pct: float) -> float:
    return float(np.percentile(np.array([C_hat[u] for u in sorted(C_hat)]), pct,
                               method="linear"))


def total_draws(U_draws: dict[str, np.ndarray]) -> np.ndarray:
    """sum_u U^(d) over the draw set's units (alphabetical)."""
    return np.sum(np.vstack([U_draws[u] for u in sorted(U_draws)]), axis=0)


def compute(chain_rows: list[dict], bench: dict[str, float], rate: int, months: int,
            year: int = YEAR) -> dict:
    """``bench``: spec -> C_bench. Returns the unpaid total over the units with data, the
    excluded units, the cost at rate x months, and per spec the benchmark scenario."""
    rows = sorted((r for r in chain_rows if r["year"] == year), key=lambda r: r["unit"])
    use = [r for r in rows if r["U"] is not None]
    U_total = sum(r["U"] for r in use)
    out = {"year": year, "U_total": U_total, "units_with_data": [r["unit"] for r in use],
           "units_excluded": [r["unit"] for r in rows if r["U"] is None],
           "rate": rate, "months": months, "cost": U_total * rate * months,
           "scenarios": {}}
    for spec, cb in bench.items():
        inc_by = {r["unit"]: r["D"] * max(0.0, cb - r["Q"] / r["D"]) for r in use}
        number = sum(r["D"] * max(r["Q"] / r["D"], cb) for r in use)
        inc = sum(inc_by.values())
        out["scenarios"][spec] = {
            "C_bench": cb, "current_number_paid": sum(r["Q"] for r in use),
            "number_paid": number, "cost_number_paid": number * SCENARIO_TOTAL,
            "increment": inc, "cost_increment": inc * SCENARIO_TOTAL,
            "increment_by_unit": inc_by}
    return out
