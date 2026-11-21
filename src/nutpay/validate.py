"""Headline estimates H1-H3, the grids, the label and leave-one-out (analysis plan sections
8.1-8.6).

H1: Spearman rho between C(2023) and n_u (sex-weighted). H2: Spearman rho between C(2023)
and the private-sector share of 2023 notifications (private / total, Annexure 1.2).
rho = tbprio.validate.spearman over the units with both values; interval
tbprio.validate.fisher_ci (Fisher z, variance 1.06/(n - 3)). Associations across units.

H3 (an ecological association, secondary): for each outcome (success, died, lost to
follow-up), Count_ut ~ quasi-binomial(cohort_ut, pi_ut), logit(pi) = b0 + beta logit(C_ut)
+ gamma [t = 2022] (pooled; no year term for a single year) + the grid's adjustment terms;
logit(C) is the empirical logit log((Q + 1/2)/(D - Q + 1/2)); prior weights a = cohort.
Observations: unit-years t in {2021, 2022} with non-NA C(t) and a valid cohort (size > 0,
each of the three counts <= size). IRLS (numpy only), adapted from
hssling/india-tb-diabetes-gap v1.0.0 (MIT), src/dmgap/validate.py: start
mu = (a y + 1/2)/(a + 1), eta = logit(mu); repeat W = a mu (1 - mu),
z = eta + (y - mu)/(mu (1 - mu)), beta = (X'WX)^-1 X'Wz, eta = X beta, mu = expit(eta);
stop when max |delta beta| < 1e-10, at most 100 iterations; non-convergence or a singular
X'WX makes the estimate undefined. Pearson phi = sum a (y - mu)^2/(mu (1 - mu)) /
(n_obs - n_par); the Wald interval is descriptive. Interval: cluster bootstrap over units
(fresh rng(20261123) per outcome; rng.integers(0, N, size=(10000, N)) over the units
sorted alphabetically; each drawn unit brings all its unit-years; undefined fits are
discarded and counted). Kish effective clusters (sum K_u)^2 / sum K_u^2, K_u = sum_t a_ut.

Label: tbprio.validate.label((lo, hi), 0, signs, sign(main)); "supported" only if the 95%
interval excludes the null AND >= 80% of grid entries agree in sign.
"""
from __future__ import annotations

import csv
from dataclasses import dataclass
from pathlib import Path

import numpy as np
from scipy.stats import kendalltau
from tbprio import validate as tbv

from . import N_DRAWS, SEED
from .need import MEN, SEX_WEIGHTED, SIMPLE, WEIGHTINGS, WOMEN  # noqa: F401

ROOT = Path(__file__).resolve().parents[2]
OUTCOMES = ROOT / "data" / "extracted" / "outcomes_panel.csv"
SECTOR = ROOT / "data" / "extracted" / "sector_panel.csv"

Z = 1.96
TOL = 1e-10
MAX_ITER = 100
NULL = 0.0
YEARS = (2021, 2022, 2023)
H3_YEARS = (2021, 2022)
OUTCOME_NAMES = ("success", "died", "ltfu")
SPEARMAN, KENDALL = "spearman", "kendall"
POOLED = "pooled 2021+2022"
YEAR_SETS = {POOLED: (2021, 2022), "2021": (2021,), "2022": (2022,)}
NONE, PRIVATE, PREV, PREV_PRIVATE = ("none", "private-sector share",
                                     "previous-year success",
                                     "previous-year success + private-sector share")
H3_GRID = [(POOLED, NONE), (POOLED, PRIVATE), ("2021", NONE), ("2021", PRIVATE),
           ("2022", NONE), ("2022", PRIVATE), ("2022", PREV), ("2022", PREV_PRIVATE)]
H3_NOTE = "ecological association across units; not a causal estimate"


class Undefined(Exception):
    """The IRLS fit is undefined (non-convergence or a singular X'WX)."""


# ---- inputs ---------------------------------------------------------------------------

def _int(v):
    return None if v in (None, "") else int(v)


def load_outcomes(path: Path = OUTCOMES) -> dict[tuple[str, int], dict[str, int | None]]:
    out: dict[tuple[str, int], dict[str, int | None]] = {}
    with open(path, encoding="utf-8", newline="") as f:
        for r in csv.DictReader(f):
            out.setdefault((r["unit"], int(r["cohort_year"])), {})[r["measure"]] = \
                _int(r["value"])
    return out


def load_sector(path: Path = SECTOR) -> dict[tuple[str, int], dict[str, int | None]]:
    out: dict[tuple[str, int], dict[str, int | None]] = {}
    with open(path, encoding="utf-8", newline="") as f:
        for r in csv.DictReader(f):
            out.setdefault((r["unit"], int(r["year"])), {})[r["measure"]] = _int(r["value"])
    return out


def private_share(sector: dict) -> dict[tuple[str, int], float | None]:
    out = {}
    for k, m in sector.items():
        p, t = m.get("private"), m.get("total")
        out[k] = p / t if (p is not None and t) else None
    return out


def coverage(chain_rows: list[dict], year: int) -> dict[str, float | None]:
    return {r["unit"]: r["C"] for r in chain_rows if r["year"] == year}


# ---- correlations ---------------------------------------------------------------------

def correlation(x, y, method: str = SPEARMAN) -> float | None:
    if method == SPEARMAN:
        return tbv.spearman(x, y)
    if method == KENDALL:
        v = float(kendalltau(x, y).statistic)
        return None if v != v else v
    raise ValueError(f"unknown method {method!r}")


def corr_entry(x: dict, y: dict, method: str = SPEARMAN, omit: str | None = None) -> dict:
    units = sorted(u for u in x if u in y and x[u] is not None and y[u] is not None
                   and u != omit)
    est = correlation([x[u] for u in units], [y[u] for u in units], method)
    return {"estimate": est, "n": len(units), "units": units, "method": method}


def label(estimate, ci, grid_signs) -> str:
    """Plan section 8.6, by tbprio.validate.label; an undefined main estimate is never
    supported."""
    ms = tbv.sign(estimate)
    if ms is None:
        return tbv.NOT_ESTABLISHED
    return tbv.label(tuple(ci), NULL, list(grid_signs), ms)


def _labelled(main: dict, grid: list[dict]) -> dict:
    signs = [tbv.sign(e["estimate"]) for e in grid]
    ms = tbv.sign(main["estimate"])
    for e, s in zip(grid, signs):
        e["sign"] = s
        e["agrees"] = ms in (1, -1) and s == ms
    return {"label": label(main["estimate"], (main["lo"], main["hi"]), signs),
            "n_agree": tbv.n_agree(signs, ms), "n_entries": len(grid), "main_sign": ms}


def _loo(fn, units: list[str]) -> list[dict]:
    return [{"omitted": u, "estimate": fn(u)} for u in units]


def h1(chain_rows: list[dict], n_by: dict[str, dict[str, float | None]]) -> dict:
    """H1 and its 12-entry grid (weighting x year); n_by: weighting -> n_u."""
    C = {t: coverage(chain_rows, t) for t in YEARS}
    main = corr_entry(C[2023], n_by[SEX_WEIGHTED])
    main["lo"], main["hi"] = tbv.fisher_ci(main["estimate"], main["n"])
    grid = []
    for w in WEIGHTINGS:
        for t in YEARS:
            e = corr_entry(C[t], n_by[w])
            e.update(weighting=w, year=t, main=(w == SEX_WEIGHTED and t == 2023))
            grid.append(e)
    res = {"main": main, "grid": grid, **_labelled(main, grid)}
    res["loo"] = _loo(lambda u: corr_entry(C[2023], n_by[SEX_WEIGHTED], omit=u)["estimate"],
                      main["units"])
    return res


def h2(chain_rows: list[dict], share: dict[tuple[str, int], float | None]) -> dict:
    """H2 and its 6-entry grid (year x {Spearman, Kendall tau-b})."""
    C = {t: coverage(chain_rows, t) for t in YEARS}
    S = {t: {u: v for (u, y), v in share.items() if y == t} for t in YEARS}
    main = corr_entry(C[2023], S[2023])
    main["lo"], main["hi"] = tbv.fisher_ci(main["estimate"], main["n"])
    grid = []
    for t in YEARS:
        for m in (SPEARMAN, KENDALL):
            e = corr_entry(C[t], S[t], m)
            e.update(year=t, main=(t == 2023 and m == SPEARMAN))
            grid.append(e)
    res = {"main": main, "grid": grid, **_labelled(main, grid)}
    res["loo"] = _loo(lambda u: corr_entry(C[2023], S[2023], omit=u)["estimate"],
                      main["units"])
    return res


# ---- H3: IRLS -------------------------------------------------------------------------

@dataclass
class GLMFit:
    beta: np.ndarray
    cov_unscaled: np.ndarray
    phi: float
    n_obs: int
    n_par: int
    iterations: int

    @property
    def b1(self) -> float:
        return float(self.beta[1])

    def wald(self) -> tuple[float, float, float]:
        se = float(np.sqrt(self.phi * self.cov_unscaled[1, 1]))
        return se, self.b1 - Z * se, self.b1 + Z * se


def expit(x):
    return 1.0 / (1.0 + np.exp(-np.asarray(x, dtype=float)))


def irls(X: np.ndarray, y: np.ndarray, a: np.ndarray, tol: float = TOL,
         max_iter: int = MAX_ITER) -> GLMFit:
    X = np.asarray(X, dtype=float)
    y = np.asarray(y, dtype=float)
    a = np.asarray(a, dtype=float)
    n_par = X.shape[1]
    mu = (a * y + 0.5) / (a + 1.0)
    eta = np.log(mu / (1.0 - mu))
    beta_old = None
    for it in range(1, max_iter + 1):
        v = mu * (1.0 - mu)
        w = a * v
        z = eta + (y - mu) / v
        XtW = X.T * w
        M = XtW @ X
        if np.linalg.matrix_rank(M) < n_par:
            raise Undefined("singular X'WX")
        try:
            beta = np.linalg.solve(M, XtW @ z)
        except np.linalg.LinAlgError as e:
            raise Undefined("singular X'WX") from e
        eta = X @ beta
        mu = expit(eta)
        if not (np.all(np.isfinite(beta)) and np.all((mu > 0) & (mu < 1))):
            raise Undefined("non-finite fit")
        if beta_old is not None and float(np.max(np.abs(beta - beta_old))) < tol:
            v = mu * (1.0 - mu)
            M = (X.T * (a * v)) @ X
            if np.linalg.matrix_rank(M) < n_par:
                raise Undefined("singular X'WX")
            cov = np.linalg.inv(M)
            n_obs = len(y)
            phi = (float(np.sum(a * (y - mu) ** 2 / v)) / (n_obs - n_par)
                   if n_obs > n_par else float("nan"))
            return GLMFit(beta, cov, phi, n_obs, n_par, it)
        beta_old = beta
    raise Undefined("non-convergence")


@dataclass
class H3Data:
    outcome: str
    year_set: str
    adjust: str
    units: list[str]             # alphabetical: units with at least one observation
    obs_unit: list[str]
    obs_year: list[int]
    X: np.ndarray
    y: np.ndarray
    a: np.ndarray
    rows_of: list[np.ndarray]
    excluded: list[tuple[str, int, str]]


def _valid_cohort(o: dict | None) -> bool:
    if not o:
        return False
    n = o.get("cohort")
    if n is None or n <= 0:
        return False
    return all(o.get(k) is not None and o[k] <= n for k in OUTCOME_NAMES)


def elogit(q: int, d: int) -> float:
    return float(np.log((q + 0.5) / (d - q + 0.5)))


def h3_data(chain_rows: list[dict], outcomes: dict, share: dict, outcome: str,
            year_set: str = POOLED, adjust: str = NONE, omit: str | None = None) -> H3Data:
    by = {(r["unit"], r["year"]): r for r in chain_rows}
    years = YEAR_SETS[year_set]
    units_all = sorted({r["unit"] for r in chain_rows})
    ou, oy, X, y, a, excluded = [], [], [], [], [], []
    for u in units_all:
        if u == omit:
            continue
        for t in years:
            c, o = by.get((u, t)), outcomes.get((u, t))
            if c is None or c["C"] is None:
                excluded.append((u, t, "C NA"))
                continue
            if not _valid_cohort(o):
                excluded.append((u, t, "cohort not valid"))
                continue
            row = [1.0, elogit(c["Q"], c["D"])]
            if len(years) > 1:
                row.append(1.0 if t == 2022 else 0.0)
            if adjust in (PRIVATE, PREV_PRIVATE):
                s = share.get((u, t))
                if s is None:
                    excluded.append((u, t, "private-sector share NA"))
                    continue
            if adjust in (PREV, PREV_PRIVATE):
                prev = outcomes.get((u, t - 1))
                if not _valid_cohort(prev):
                    excluded.append((u, t, "previous-year cohort not valid"))
                    continue
                row.append(prev["success"] / prev["cohort"])
            if adjust in (PRIVATE, PREV_PRIVATE):
                row.append(share[(u, t)])
            ou.append(u)
            oy.append(t)
            X.append(row)
            y.append(o[outcome] / o["cohort"])
            a.append(float(o["cohort"]))
    units = sorted(set(ou))
    arr = np.array(ou)
    rows_of = [np.flatnonzero(arr == u) for u in units]
    return H3Data(outcome, year_set, adjust, units, ou, oy, np.array(X), np.array(y),
                  np.array(a), rows_of, excluded)


def kish(weights_by_unit: list[np.ndarray]) -> float:
    K = np.array([float(np.sum(w)) for w in weights_by_unit])
    return float(K.sum() ** 2 / np.sum(K ** 2))


def bootstrap(d: H3Data, n_boot: int = N_DRAWS) -> dict:
    rng = np.random.default_rng(SEED)
    N = len(d.units)
    idx = rng.integers(0, N, size=(n_boot, N))
    b1 = np.full(n_boot, np.nan)
    for i in range(n_boot):
        rows = np.concatenate([d.rows_of[j] for j in idx[i]])
        try:
            b1[i] = irls(d.X[rows], d.y[rows], d.a[rows]).b1
        except Undefined:
            pass
    ok = b1[~np.isnan(b1)]
    lo, hi = np.percentile(ok, [2.5, 97.5], method="linear")
    return {"lo": float(lo), "hi": float(hi), "n_boot": n_boot,
            "n_discarded": int(n_boot - ok.size)}


def h3_entry(chain_rows, outcomes, share, outcome, year_set, adjust, omit=None) -> dict:
    d = h3_data(chain_rows, outcomes, share, outcome, year_set, adjust, omit)
    e = {"outcome": outcome, "year_set": year_set, "adjustment": adjust,
         "n_obs": len(d.y), "n_units": len(d.units),
         "main": (year_set == POOLED and adjust == NONE)}
    try:
        f = irls(d.X, d.y, d.a)
        se, lo, hi = f.wald()
        e.update(estimate=f.b1, phi=f.phi, wald_se=se, wald_lo=lo, wald_hi=hi,
                 iterations=f.iterations, status="estimated")
    except Undefined as ex:
        e.update(estimate=None, status=f"undefined ({ex})")
    return e


def h3(chain_rows: list[dict], outcomes: dict, share: dict, outcome: str,
       n_boot: int = N_DRAWS) -> dict:
    d = h3_data(chain_rows, outcomes, share, outcome)
    grid = [h3_entry(chain_rows, outcomes, share, outcome, ys, adj) for ys, adj in H3_GRID]
    main = dict(grid[0])
    main["kish"] = kish([d.a[r] for r in d.rows_of])
    main["units"] = d.units
    main["excluded"] = d.excluded
    if main["estimate"] is not None:
        main.update(bootstrap(d, n_boot))
    else:
        main.update(lo=None, hi=None, n_boot=0, n_discarded=None)
    res = {"main": main, "grid": grid, **_labelled(main, grid)}
    res["loo"] = _loo(lambda u: h3_entry(chain_rows, outcomes, share, outcome, POOLED, NONE,
                                         omit=u)["estimate"], d.units)
    return res


def loo_summary(name: str, loo: list[dict]) -> list[dict]:
    ok = [r for r in loo if r["estimate"] is not None]
    rows = [{"analysis": name, "omitted": r["omitted"], "estimate": r["estimate"],
             "summary": ""} for r in loo]
    if ok:
        lo = sorted(ok, key=lambda r: (r["estimate"], r["omitted"]))[0]
        hi = sorted(ok, key=lambda r: (-r["estimate"], r["omitted"]))[0]
        rows.append({"analysis": name, "omitted": lo["omitted"], "estimate": lo["estimate"],
                     "summary": "minimum"})
        rows.append({"analysis": name, "omitted": hi["omitted"], "estimate": hi["estimate"],
                     "summary": "maximum"})
    return rows
