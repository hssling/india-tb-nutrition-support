"""Unpaid-rate draws, P(top-5) and tiers (analysis plan sections 5.3, 6, 8.5).

Draw set of a data year: tbprio.harm.estimate(rows, "unpaid", year, "p75", True, rng)
.rate_draws on a fresh numpy.random.default_rng(20261123) passed by the caller; rows in the
panel format of tbprio.panel.cells (unit, year as int, step "unpaid", numerator = U,
denominator = D, na). U^(d) = D rate^(d). Only rate_draws and post_mean are used;
C_hat_u = 1 - post_mean_u.

Edge cases: no usable unit -> tbprio raises "no non-NA cell" and the year has no tiers;
sum U = 0 -> tbprio returns zero draws (no_harm); the prior cannot be fitted -> the call is
repeated with shrinkage off (the Jeffreys prior) and the flag ``prior_fallback_jeffreys``
is set.

Tiers: P(top-5) = tbprio.priority.p_topk({unit: draws}, 5), units in alphabetical order;
tier = tbprio.priority.tier(P(top-5), False). Harms: U (unweighted) and U wt_u (the
weighted draws are the U draws times the fixed wt_u; units with wt_u NA are left out).
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
from tbprio import harm as tbharm
from tbprio import priority as tbp

from . import SEED

STEP = "unpaid"
K = 5
FALLBACK = "prior_fallback_jeffreys"
ACT_NOW = "act now"
UNWEIGHTED = "unweighted"


@dataclass
class DrawSet:
    year: int
    units: list[str]                 # alphabetical, units with U non-NA
    D: dict[str, int]
    U: dict[str, int]
    alpha: float | None
    beta: float | None
    flag: str
    no_harm: bool
    absent: bool                     # no usable unit: no tiers this year
    post_mean: dict[str, float]
    C_hat: dict[str, float]
    rate_draws: dict[str, np.ndarray] = field(repr=False)
    U_draws: dict[str, np.ndarray] = field(repr=False)
    excluded: list[str] = field(default_factory=list)
    excluded_reason: dict[str, str] = field(default_factory=dict)


def unpaid_rows(chain_rows: list[dict], year: int, omit: str | None = None) -> list[dict]:
    """The year's cells in the tbprio panel format; U NA -> na True."""
    out = []
    for r in sorted((r for r in chain_rows if r["year"] == year), key=lambda r: r["unit"]):
        if r["unit"] == omit:
            continue
        out.append({"unit": r["unit"], "year": int(year), "step": STEP,
                    "numerator": r["U"], "denominator": r["D"],
                    "na": r["U"] is None or r["C"] is None})
    return out


def draw_set(chain_rows: list[dict], year: int, rng: np.random.Generator,
             omit: str | None = None) -> DrawSet:
    rows = unpaid_rows(chain_rows, year, omit)
    # U NA, or D = 0 (U = 0 but the rate U/D is undefined): no draws, no tier
    excluded = [r["unit"] for r in rows if r["na"]]
    why = {r["unit"]: ("U NA" if r["numerator"] is None else "D = 0 (U = 0; rate undefined)")
           for r in rows if r["na"]}
    flag = ""
    try:
        sy = tbharm.estimate(rows, STEP, year, "p75", True, rng)
    except ValueError as e:
        if str(e).startswith("no non-NA cell"):
            return DrawSet(year, [], {}, {}, None, None, "no usable unit", False, True,
                           {}, {}, {}, {}, excluded, why)
        # the shrinkage cannot be fitted; tbprio raised before drawing, so the stream is
        # untouched
        sy = tbharm.estimate(rows, STEP, year, "p75", False, rng)
        flag = FALLBACK
    units = list(sy.units)
    D = {u: int(sy.n[u]) for u in units}
    U = {u: int(sy.x[u]) for u in units}
    U_draws = {u: D[u] * sy.rate_draws[u] for u in units}
    alpha = None if sy.no_harm else sy.alpha
    beta = None if sy.no_harm else sy.beta
    post = dict(sy.post_mean)
    return DrawSet(year, units, D, U, alpha, beta, flag, bool(sy.no_harm), False, post,
                   {u: 1.0 - post[u] for u in units}, dict(sy.rate_draws), U_draws,
                   excluded, why)


def harm_draws(ds: DrawSet, weights: dict[str, float | None] | None) -> dict[str, np.ndarray]:
    """unit -> harm draws: U^(d), or U^(d) wt_u over the units with wt_u non-NA."""
    if weights is None:
        return {u: ds.U_draws[u] for u in ds.units}
    return {u: ds.U_draws[u] * weights[u] for u in ds.units if weights.get(u) is not None}


def p_top5(ds: DrawSet, weights: dict[str, float | None] | None) -> dict[str, float]:
    return tbp.p_topk(harm_draws(ds, weights), K)


def tiers(ds: DrawSet, weights: dict[str, float | None] | None, spec: str = UNWEIGHTED,
          falling: dict[str, bool] | None = None, all_units: list[str] | None = None
          ) -> list[dict]:
    """One row per unit (all_units, alphabetical): counts first, then per 100,000, then
    P(top-5) and the tier. Units with no harm value are listed with the reason."""
    h = harm_draws(ds, weights)
    p = tbp.p_topk(h, K) if h else {}
    per = "per 100,000 eligible beneficiaries" if ds.year == 2023 else "per 100,000 notified"
    out = []
    for u in sorted(all_units if all_units is not None else ds.units):
        wt = None if weights is None else weights.get(u)
        row = {"unit": u, "year": ds.year, "spec": spec, "D": ds.D.get(u),
               "U_observed": ds.U.get(u), "wt_u": wt, "harm_observed": None,
               "harm_mean": None, "harm_lo": None, "harm_hi": None,
               "harm_per_100000": None, "per_100000_basis": per,
               "unpaid_rate_post_mean": ds.post_mean.get(u), "C_hat": ds.C_hat.get(u),
               "p_top5": None, "tier": None,
               "falling_coverage_2021_2022": None if falling is None else falling.get(u),
               "prior": ds.flag or ("" if ds.absent else "empirical Bayes"),
               "no_unpaid_people_in_year": ds.no_harm, "status": ""}
        if u in h:
            obs = ds.U[u] * (1.0 if weights is None else wt)
            m, lo, hi = tbharm.summary(h[u])
            row.update(harm_observed=obs, harm_mean=m, harm_lo=lo, harm_hi=hi,
                       harm_per_100000=m / ds.D[u] * 100_000, p_top5=p[u],
                       tier=tbp.tier(p[u], False), status="tiered")
        elif ds.absent:
            row["status"] = "not tiered: the year has no unit with data"
        elif u not in ds.units:
            row["status"] = "not tiered: " + ds.excluded_reason.get(u, "U NA")
        else:
            row["status"] = "not tiered: wt_u NA"
        out.append(row)
    return out


def run(chain_rows: list[dict], weights: dict[str, float | None] | None, year: int,
        rng: np.random.Generator) -> list[dict]:
    """The year's tiers for one harm (weights None: U; else U wt_u)."""
    ds = draw_set(chain_rows, year, rng)
    return tiers(ds, weights, UNWEIGHTED if weights is None else "need_weighted")


def act_now(rows: list[dict]) -> set[str]:
    return {r["unit"] for r in rows if r["tier"] == ACT_NOW}


def leave_one_out(chain_rows: list[dict], year: int, units: list[str],
                  weights_for: callable, main_unweighted: set[str],
                  main_weighted: set[str]) -> list[dict]:
    """Plan section 8.5, act-now sets: each unit removed in turn, the draw set refitted on
    the remaining units with a fresh rng(20261123), the weights recomputed by
    ``weights_for(omit)`` (n_bar and wt_u over the remaining units), P(top-5) and tiers;
    the number of remaining units whose act-now membership changes."""
    out = []
    for omit in units:
        ds = draw_set(chain_rows, year, np.random.default_rng(SEED), omit=omit)
        for harm, w, main in (("U", None, main_unweighted),
                              ("U_wt_sex_weighted", weights_for(omit), main_weighted)):
            rows = tiers(ds, w)
            now = act_now(rows)
            remaining = {r["unit"] for r in rows if r["tier"] is not None}
            changed = sorted(u for u in remaining if (u in now) != (u in main))
            out.append({"analysis": f"act-now set {year}", "harm": harm, "omitted": omit,
                        "n_changed": len(changed), "changed_units": changed,
                        "act_now_without": sorted(now)})
    return out
