"""Trend in coverage (analysis plan section 7).

Main (7.1): for each unit with non-NA C in 2021 and 2022, d = C2022 - C2021 with
Newcombe's hybrid-score interval from the two Wilson intervals: lower = d - sqrt((c2 -
l2)^2 + (u1 - c1)^2), upper = d + sqrt((u2 - c2)^2 + (c1 - l1)^2), z = 1.96. Nationally the
same over the sums of Q and D across those units. "Falling coverage": upper < 0. The flag
never changes a tier.

Descriptive 2023 (7.2): C2023 and its change from 2022 with the Jeffreys interval of each
year, labelled "denominator basis changes between 2022 and 2023"; no flag.

Sensitivities (7.3):
- saturated: from tbprio.trend.transform, beta1 = L2022 - L2021, SE = sqrt(V2021 + V2022),
  phi = 1, interval beta1 +/- 1.96 SE; falling if the upper end < 0;
- descriptive: tbprio.trend.fit(years, Q, D, indicator=False) over 2021-2023 with
  phi = tbprio.trend.pooled_phi over the units' fits and tbprio.trend.interval; it does not
  separate the denominator basis.
"""
from __future__ import annotations

import math

from tbprio import trend as tbt

from .chain import wilson

Z = 1.96
BASIS_NOTE = "denominator basis changes between 2022 and 2023"
MAIN, SATURATED, WLS, DESC = ("main_newcombe_2021_2022", "sensitivity_saturated_logit",
                              "sensitivity_wls_no_indicator_2021_2023",
                              "descriptive_2022_2023")


def newcombe(x1: int, n1: int, x2: int, n2: int) -> tuple[float, float, float]:
    c1, c2 = x1 / n1, x2 / n2
    l1, u1 = wilson(x1, n1)
    l2, u2 = wilson(x2, n2)
    d = c2 - c1
    return (d, d - math.sqrt((c2 - l2) ** 2 + (u1 - c1) ** 2),
            d + math.sqrt((u2 - c2) ** 2 + (c1 - l1) ** 2))


def saturated(q1: int, d1: int, q2: int, d2: int) -> tuple[float, float, float, float]:
    """(beta1, se, lo, hi) of the saturated 2023-indicator model (section 7.3)."""
    L, V = tbt.transform([q1, q2], [d1, d2], False)
    b = float(L[1] - L[0])
    se = math.sqrt(float(V[0] + V[1]))
    return b, se, b - Z * se, b + Z * se


def _by(chain_rows):
    return {(r["unit"], r["year"]): r for r in chain_rows}


def run(chain_rows: list[dict]) -> tuple[list[dict], dict[str, bool]]:
    """(rows, falling): the trend rows of every spec, and the main falling flag by unit."""
    by = _by(chain_rows)
    units = sorted({r["unit"] for r in chain_rows})
    rows: list[dict] = []
    falling: dict[str, bool] = {}
    sat_flag: dict[str, bool] = {}
    both = [u for u in units if by[(u, 2021)]["C"] is not None
            and by[(u, 2022)]["C"] is not None]
    for u in units:
        r1, r2 = by[(u, 2021)], by[(u, 2022)]
        base = {"level": "unit", "unit": u, "spec": MAIN, "C_2021": r1["C"],
                "C_2022": r2["C"], "C_2023": None, "estimate": None, "lo": None, "hi": None,
                "se": None, "phi": None, "falling_coverage": None, "status": "",
                "note": ""}
        if u in both:
            d, lo, hi = newcombe(r1["Q"], r1["D"], r2["Q"], r2["D"])
            falling[u] = hi < 0
            rows.append(base | {"estimate": d, "lo": lo, "hi": hi,
                                "falling_coverage": falling[u], "status": "estimated"})
            b, se, slo, shi = saturated(r1["Q"], r1["D"], r2["Q"], r2["D"])
            sat_flag[u] = shi < 0
            rows.append(base | {"spec": SATURATED, "estimate": b, "lo": slo, "hi": shi,
                                "se": se, "phi": 1.0, "falling_coverage": sat_flag[u],
                                "status": "estimated",
                                "note": "empirical logit; saturated, phi = 1"})
        else:
            rows.append(base | {"status": "not estimable: C NA in 2021 or 2022"})
            rows.append(base | {"spec": SATURATED,
                                "status": "not estimable: C NA in 2021 or 2022"})
    # national main
    x1 = sum(by[(u, 2021)]["Q"] for u in both)
    n1 = sum(by[(u, 2021)]["D"] for u in both)
    x2 = sum(by[(u, 2022)]["Q"] for u in both)
    n2 = sum(by[(u, 2022)]["D"] for u in both)
    d, lo, hi = newcombe(x1, n1, x2, n2)
    rows.append({"level": "national", "unit": f"units with data ({len(both)})", "spec": MAIN,
                 "C_2021": x1 / n1, "C_2022": x2 / n2, "C_2023": None, "estimate": d,
                 "lo": lo, "hi": hi, "se": None, "phi": None, "falling_coverage": hi < 0,
                 "status": "estimated",
                 "note": "excluded: " + (", ".join(u for u in units if u not in both)
                                         or "none")})
    # descriptive WLS without the indicator over 2021-2023
    fits = {}
    status = {}
    for u in units:
        ys = [t for t in (2021, 2022, 2023) if by[(u, t)]["C"] is not None]
        try:
            fits[u] = tbt.fit(ys, [by[(u, t)]["Q"] for t in ys], [by[(u, t)]["D"] for t in ys],
                              indicator=False)
            status[u] = "estimated"
        except tbt.NotEstimable as e:
            status[u] = f"not estimable ({e})"
    phi = tbt.pooled_phi(fits.values())
    wls_flag: dict[str, bool] = {}
    for u in units:
        row = {"level": "unit", "unit": u, "spec": WLS, "C_2021": by[(u, 2021)]["C"],
               "C_2022": by[(u, 2022)]["C"], "C_2023": by[(u, 2023)]["C"], "estimate": None,
               "lo": None, "hi": None, "se": None, "phi": phi, "falling_coverage": None,
               "status": status[u],
               "note": "descriptive; does not separate the denominator basis"}
        if u in fits:
            se, lo, hi = tbt.interval(fits[u], phi)
            wls_flag[u] = hi < 0
            row.update(estimate=fits[u].slope, lo=lo, hi=hi, se=se,
                       falling_coverage=wls_flag[u])
        rows.append(row)
    # descriptive 2023
    for u in units:
        r2, r3 = by[(u, 2022)], by[(u, 2023)]
        row = {"level": "unit", "unit": u, "spec": DESC, "C_2021": None, "C_2022": r2["C"],
               "C_2023": r3["C"], "estimate": None, "lo": None, "hi": None, "se": None,
               "phi": None, "falling_coverage": None, "status": "", "note": BASIS_NOTE,
               "C_2022_lo": r2["C_lo"], "C_2022_hi": r2["C_hi"], "C_2023_lo": r3["C_lo"],
               "C_2023_hi": r3["C_hi"]}
        if r2["C"] is not None and r3["C"] is not None:
            row.update(estimate=r3["C"] - r2["C"], status="described")
        else:
            row["status"] = "not described: C NA in 2022 or 2023"
        rows.append(row)
    # summary: units whose falling flag differs from the main flag
    for spec, flags in ((SATURATED, sat_flag), (WLS, wls_flag)):
        common = [u for u in falling if u in flags]
        diff = sorted(u for u in common if flags[u] != falling[u])
        rows.append({"level": "summary", "unit": "", "spec": spec, "estimate": len(diff),
                     "status": "units whose falling flag differs from the main flag",
                     "note": "; ".join(diff) if diff else "none",
                     "n_compared": len(common)})
    rows.append({"level": "summary", "unit": "", "spec": MAIN,
                 "estimate": sum(falling.values()),
                 "status": "units with falling coverage (2021 to 2022)",
                 "note": "; ".join(sorted(u for u, f in falling.items() if f)) or "none",
                 "n_compared": len(falling)})
    return rows, falling


COLUMNS = ["level", "unit", "spec", "C_2021", "C_2022", "C_2023", "estimate", "lo", "hi",
           "se", "phi", "falling_coverage", "status", "note", "C_2022_lo", "C_2022_hi",
           "C_2023_lo", "C_2023_hi", "n_compared"]
