# Adapted from hssling/india-tb-diabetes-gap v1.0.0 (MIT), verification/check_outputs.py
# (the incomplete Beta function, the Beta quantile, the Spearman and Fisher formulas, the
# own IRLS and the label rule are written out again there from the plan). Changes: this
# study's quantities (chain, need weight, shortfall classes, budget, H1-H3).
"""Independent recompute of the registered results with the standard library only (analysis
plan section 10.3). Nothing of src/ is imported, nor numpy, scipy or tbprio: every formula
below is written out again from docs/analysis_plan.md.

Run as: python -I verification/check_outputs.py [--root DIR]

Inputs: data/extracted/ (npy_panel, nfhs_bmi, tb_sex_2022, outcomes_panel, sector_panel)
and the committed files of outputs/.

Tolerances.
- Deterministic values: relative 1e-9 (REL). Exact Beta quantiles (Jeffreys intervals,
  printed by scipy.stats.beta.ppf): relative 1e-7. The own IRLS slopes: absolute 1e-6;
  phi and the Wald interval: relative 1e-6.
- Where the plan uses Monte Carlo (10,000 draws), the printed value is compared with its
  exact expectation, written from the regularised incomplete Beta function: a mean within
  MC_SE = 5 Monte Carlo standard errors; a share of draws P within 5 sqrt(P(1 - P)/10,000)
  + 0.001; a percentile within Q_TOL posterior standard deviations of the exact quantile.

(a) The chain (plan 3.6, 5.1, 5.2), 33 units x 3 data years: A, P, C, V and paid/validated
    with their Jeffreys intervals, U, U_acc, U_pay, NA steps; the national A, P, C (Wilson)
    and the national unpaid counts, with the number of units.
(b) The need weight (plan 4.2-4.3): w_u, m_u, f_u, G_u, n_u, n-bar and wt_u for the four
    weightings; the G-weighted mean of wt_u is 1.
(c) The shortfalls and classes (plan 5.3-5.4), all years and the three benchmarks: the
    chain priors, A_hat, P_hat, the benchmarks, the observed S_acc and S_pay, their
    exact expectations and the exact 95% limits of S_acc, the exact P(no shortfall), and
    a separate Monte Carlo (this file's own draws from random.betavariate) of the class
    shares; the printed class must follow the rule and agree with the own draws, except
    where it lies within the Monte Carlo tolerance of a threshold ("borderline", named).
(d) The budget (plan 9), 2023: U(2023) and its exact mean and spread, the cost of the main
    figure and of the four ranges, C-hat (the unpaid-rate posterior), C_bench at the 75th,
    50th and 90th percentiles, the benchmark scenarios.
(e) H1 and H2 (plan 8.1-8.2): every entry of the grids, the estimate with its Fisher-z
    interval, n, the label.
(f) H3 (plan 8.4): all 24 entries (3 outcomes x 8) by this file's own IRLS, with phi, the
    Wald interval, n_obs, n_units and the Kish effective clusters.
(g) The label rule (plan 8.6) from the own signs and the printed intervals; spec_grid.csv.

NOT re-derived here: the H3 bootstrap interval, P(top-5) and the tiers, the trend, the
funnel, leave-one-out and the perturbation; check_rerun.py reproduces them byte for byte.

Exit 1 on any failed comparison.
"""
import argparse
import csv
import math
import random
import statistics
import sys
import zlib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
YEARS = (2021, 2022, 2023)
YEAR = 2023
N_DRAWS = 10_000
REL = 1e-9
REL_Q = 1e-7
TOL_B = 1e-6
REL_FIT = 1e-6
MC_SE = 5.0
Q_TOL = 0.2
Z = 1.96
FIELLER = 1.06
JEFFREYS = (0.5, 0.5)
OWN_DRAWS = 4000
PCTS = {"p75": 75.0, "p50": 50.0, "p90": 90.0}
WEIGHTINGS = ("sex_weighted", "women", "men", "simple")
RATE_MAIN, MONTHS_MAIN, RATES, MONTHS, TOTAL = 1000, 6, (500, 1000), (6, 8), 6000
SUPPORTED, NOT_ESTABLISHED = "supported", "not established"
NO_SHORTFALL, ACCOUNT, PAYMENT, MIXED = "no shortfall", "account-led", "payment-led", "mixed"
POOLED = "pooled 2021+2022"
NONE, PRIVATE, PREV, PREV_PRIVATE = ("none", "private-sector share",
                                     "previous-year success",
                                     "previous-year success + private-sector share")
H3_GRID = [(POOLED, NONE), (POOLED, PRIVATE), ("2021", NONE), ("2021", PRIVATE),
           ("2022", NONE), ("2022", PRIVATE), ("2022", PREV), ("2022", PREV_PRIVATE)]
YEAR_SETS = {POOLED: (2021, 2022), "2021": (2021,), "2022": (2022,)}
OUTCOMES = ("success", "died", "ltfu")


# ------------------------------------------------------------------ input

def read(path: Path) -> list[dict]:
    with open(path, encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def flt(s):
    return None if s is None or s.strip() in ("", "NA") else float(s)


def integer(s):
    return None if s is None or s.strip() in ("", "NA") else int(s)


# ------------------------------------------------------------------ arithmetic

def close(a, b, rel=REL) -> bool:
    if a is None or b is None:
        return a is None and b is None
    return math.isclose(a, b, rel_tol=rel, abs_tol=rel * 1e-3)


def percentile(values, q: float) -> float:
    """Linear interpolation between order statistics (numpy's "linear" method)."""
    s = sorted(values)
    h = (len(s) - 1) * q / 100.0
    lo = math.floor(h)
    hi = min(lo + 1, len(s) - 1)
    return s[lo] + (s[hi] - s[lo]) * (h - lo)


def mom_beta(x: list, n: list) -> tuple[float, float]:
    """The beta-binomial method-of-moments prior (plan 5.3: tbprio's rule, written out
    again): m = sum x / sum n; s2 the unweighted variance of x/n (divisor U - 1);
    tau2 = s2 - m(1 - m) mean(1/n); S = m(1 - m)/tau2 - 1 bounded to [1, 1e6] (1e6 when
    tau2 <= 0). Raises when U < 2 or the pooled rate is 0 or 1."""
    U = len(x)
    if U < 2:
        raise ValueError("fewer than 2 units")
    m = math.fsum(x) / math.fsum(n)
    if not 0.0 < m < 1.0:
        raise ValueError(f"pooled rate {m}")
    s2 = math.fsum((xi / ni - m) ** 2 for xi, ni in zip(x, n)) / (U - 1)
    tau2 = s2 - m * (1.0 - m) * math.fsum(1.0 / ni for ni in n) / U
    S = 1e6 if tau2 <= 0 else min(max(m * (1.0 - m) / tau2 - 1.0, 1.0), 1e6)
    return m * S, (1.0 - m) * S


def prior_or_jeffreys(x, n) -> tuple[float, float]:
    try:
        return mom_beta(x, n)
    except ValueError:
        return JEFFREYS  # plan 5.3: the Jeffreys prior


def _betacf(a: float, b: float, x: float) -> float:
    """Continued fraction of the incomplete Beta function (modified Lentz)."""
    tiny, eps = 1e-300, 1e-15
    qab, qap, qam = a + b, a + 1.0, a - 1.0
    c, d = 1.0, 1.0 - qab * x / qap
    d = 1.0 / (d if abs(d) > tiny else tiny)
    h = d
    for m in range(1, 1_000_000):
        m2 = 2 * m
        aa = m * (b - m) * x / ((qam + m2) * (a + m2))
        d = 1.0 + aa * d
        d = 1.0 / (d if abs(d) > tiny else tiny)
        c = 1.0 + aa / c
        c = c if abs(c) > tiny else tiny
        h *= d * c
        aa = -(a + m) * (qab + m) * x / ((a + m2) * (qap + m2))
        d = 1.0 + aa * d
        d = 1.0 / (d if abs(d) > tiny else tiny)
        c = 1.0 + aa / c
        c = c if abs(c) > tiny else tiny
        de = d * c
        h *= de
        if abs(de - 1.0) < eps:
            return h
    raise ArithmeticError("incomplete Beta: no convergence")


def betainc(a: float, b: float, x: float) -> float:
    """The regularised incomplete Beta function I_x(a, b) = P(Beta(a, b) <= x)."""
    if x <= 0.0:
        return 0.0
    if x >= 1.0:
        return 1.0
    front = math.exp(math.lgamma(a + b) - math.lgamma(a) - math.lgamma(b)
                     + a * math.log(x) + b * math.log1p(-x))
    if x < (a + 1.0) / (a + b + 2.0):
        return front * _betacf(a, b, x) / a
    return 1.0 - front * _betacf(b, a, 1.0 - x) / b


def beta_mean_sd(a: float, b: float) -> tuple[float, float]:
    s = a + b
    return a / s, math.sqrt(a * b / (s * s * (s + 1.0)))


def beta_ppf(q: float, a: float, b: float) -> float:
    """The q-quantile of Beta(a, b): safeguarded Newton on betainc."""
    mean, sd = beta_mean_sd(a, b)
    x = min(max(mean + statistics.NormalDist().inv_cdf(q) * sd, 1e-12), 1.0 - 1e-12)
    lo, hi = 0.0, 1.0
    lbeta = math.lgamma(a) + math.lgamma(b) - math.lgamma(a + b)
    for _ in range(400):
        F = betainc(a, b, x)
        if F < q:
            lo = x
        else:
            hi = x
        dens = math.exp((a - 1.0) * math.log(x) + (b - 1.0) * math.log1p(-x) - lbeta)
        xn = x - (F - q) / dens if dens > 0 else (lo + hi) / 2.0
        if not lo < xn < hi:
            xn = (lo + hi) / 2.0
        if abs(xn - x) <= 1e-15 * x or hi - lo <= 1e-16:
            return xn
        x = xn
    raise ArithmeticError("Beta quantile: no convergence")


def jeffreys_interval(x: int, n: int) -> tuple[float, float]:
    a, b = 0.5 + x, 0.5 + n - x
    return beta_ppf(0.025, a, b), beta_ppf(0.975, a, b)


def wilson(x: int, n: int) -> tuple[float, float, float]:
    centre = (x + Z * Z / 2.0) / (n + Z * Z)
    half = Z * math.sqrt(x * (n - x) / n + Z * Z / 4.0) / (n + Z * Z)
    return x / n, centre - half, centre + half


def e_short(t: float, a: float, b: float, k: int = 1) -> float:
    """E[max(0, t - Y)^k], Y ~ Beta(a, b), k = 1 or 2, by the incomplete Beta function."""
    s = a + b
    f0 = betainc(a, b, t)
    f1 = betainc(a + 1.0, b, t)
    if k == 1:
        return t * f0 - a / s * f1
    f2 = betainc(a + 2.0, b, t)
    return t * t * f0 - 2.0 * t * a / s * f1 + a * (a + 1.0) / (s * (s + 1.0)) * f2


def avg_ranks(values: list) -> list[float]:
    order = sorted(range(len(values)), key=lambda i: values[i])
    ranks = [0.0] * len(values)
    i = 0
    while i < len(order):
        j = i
        while j + 1 < len(order) and values[order[j + 1]] == values[order[i]]:
            j += 1
        for k in range(i, j + 1):
            ranks[order[k]] = (i + j) / 2 + 1
        i = j + 1
    return ranks


def pearson(a: list, b: list):
    n = len(a)
    if n < 2:
        return None
    ma, mb = math.fsum(a) / n, math.fsum(b) / n
    sab = math.fsum((x - ma) * (y - mb) for x, y in zip(a, b))
    saa = math.fsum((x - ma) ** 2 for x in a)
    sbb = math.fsum((y - mb) ** 2 for y in b)
    if saa <= 0 or sbb <= 0:
        return None
    return sab / math.sqrt(saa * sbb)


def spearman(x: list, y: list):
    return pearson(avg_ranks(x), avg_ranks(y))


def kendall_b(x: list, y: list):
    """Kendall's tau-b (ties in either variable)."""
    n = len(x)
    conc = disc = tx = ty = 0
    for i in range(n):
        for j in range(i + 1, n):
            dx, dy = x[i] - x[j], y[i] - y[j]
            if dx == 0 and dy == 0:
                continue
            if dx == 0:
                tx += 1
            elif dy == 0:
                ty += 1
            elif (dx > 0) == (dy > 0):
                conc += 1
            else:
                disc += 1
    den = math.sqrt((conc + disc + tx) * (conc + disc + ty))
    return None if den == 0 else (conc - disc) / den


def fisher(rho, n):
    """Fisher z with the Fieller-Hartley-Pearson variance 1.06/(n - 3); none if n <= 3."""
    if rho is None or n <= 3:
        return None, None
    if abs(rho) >= 1:
        return rho, rho
    z, se = math.atanh(rho), math.sqrt(FIELLER / (n - 3))
    return math.tanh(z - Z * se), math.tanh(z + Z * se)


def sign(v):
    if v is None or v != v:
        return None
    return (v > 0) - (v < 0)


def label(lo, hi, signs, main_sign) -> tuple[str, int]:
    """Plan 8.6: "supported" only if the 95% interval excludes the null (0) AND at least
    80% of the grid entries have the main estimate's strict sign (5 agree >= 4 entries)."""
    agree = sum(1 for s in signs if main_sign in (1, -1) and s == main_sign)
    if lo is None or hi is None or not ((lo > 0 and hi > 0) or (lo < 0 and hi < 0)):
        return NOT_ESTABLISHED, agree
    if main_sign not in (1, -1):
        return NOT_ESTABLISHED, agree
    return (SUPPORTED if 5 * agree >= 4 * len(signs) else NOT_ESTABLISHED), agree


# ------------------------------------------------------------------ the IRLS of plan 8.4

def solve(M: list[list[float]], r: list[float]) -> list[float]:
    """Gaussian elimination with partial pivoting; raises on a singular matrix."""
    n = len(r)
    A = [row[:] + [r[i]] for i, row in enumerate(M)]
    scale = max(abs(v) for row in M for v in row) or 1.0
    for c in range(n):
        p = max(range(c, n), key=lambda i: abs(A[i][c]))
        if abs(A[p][c]) <= 1e-13 * scale:
            raise ArithmeticError("singular X'WX")
        A[c], A[p] = A[p], A[c]
        for i in range(c + 1, n):
            f = A[i][c] / A[c][c]
            for j in range(c, n + 1):
                A[i][j] -= f * A[c][j]
    x = [0.0] * n
    for i in range(n - 1, -1, -1):
        x[i] = (A[i][n] - sum(A[i][j] * x[j] for j in range(i + 1, n))) / A[i][i]
    return x


def xtwx(X, w):
    p = len(X[0])
    return [[math.fsum(w[k] * X[k][i] * X[k][j] for k in range(len(X))) for j in range(p)]
            for i in range(p)]


def irls(X: list, y: list, a: list) -> dict:
    """Plan 8.4: start mu = (a y + 1/2)/(a + 1), eta = logit(mu); W = a mu(1 - mu);
    z = eta + (y - mu)/(mu(1 - mu)); beta = (X'WX)^-1 X'Wz; stop when max |delta beta| <
    1e-10 (at most 100 iterations). Pearson phi = sum a (y - mu)^2/(mu(1 - mu)) /
    (n_obs - n_par); Wald SE of the slope sqrt(phi [(X'WX)^-1]_11)."""
    n, p = len(y), len(X[0])
    mu = [(ai * yi + 0.5) / (ai + 1.0) for ai, yi in zip(a, y)]
    eta = [math.log(m / (1.0 - m)) for m in mu]
    old = None
    for it in range(1, 101):
        v = [m * (1.0 - m) for m in mu]
        w = [ai * vi for ai, vi in zip(a, v)]
        z = [e + (yi - m) / vi for e, yi, m, vi in zip(eta, y, mu, v)]
        r = [math.fsum(w[k] * X[k][i] * z[k] for k in range(n)) for i in range(p)]
        beta = solve(xtwx(X, w), r)
        eta = [math.fsum(xi * bi for xi, bi in zip(X[k], beta)) for k in range(n)]
        mu = [1.0 / (1.0 + math.exp(-e)) for e in eta]
        if old is not None and max(abs(b - o) for b, o in zip(beta, old)) < 1e-10:
            v = [m * (1.0 - m) for m in mu]
            M = xtwx(X, [ai * vi for ai, vi in zip(a, v)])
            cov11 = solve(M, [1.0 if i == 1 else 0.0 for i in range(p)])[1]
            phi = math.fsum(ai * (yi - m) ** 2 / vi
                            for ai, yi, m, vi in zip(a, y, mu, v)) / (n - p)
            se = math.sqrt(phi * cov11)
            return {"beta": beta, "phi": phi, "se": se, "lo": beta[1] - Z * se,
                    "hi": beta[1] + Z * se}
        old = beta
    raise ArithmeticError("non-convergence")


# ------------------------------------------------------------------ the recompute

def chain_na(D, B, Q, Vd, has_v) -> dict:
    """Plan 3.6: a step ratio is NA when an input is missing, its denominator is 0, or its
    numerator exceeds its denominator."""
    out = {}
    steps = [("A", B, D), ("P", Q, B), ("C", Q, D)]
    if has_v:
        steps += [("V", Vd, B), ("PV", Q, Vd)]
    for s, num, den in steps:
        if num is None or den is None:
            out[s] = "missing"
        elif den == 0:
            out[s] = "zero"
        elif num > den:
            out[s] = "exceeds"
    return out


class Checker:
    def __init__(self, root: Path):
        self.root = root
        self.bad: list[str] = []
        self.ok: list[str] = []
        ex = root / "data" / "extracted"
        self.npy = read(ex / "npy_panel.csv")
        self.nfhs = read(ex / "nfhs_bmi.csv")
        self.sex = read(ex / "tb_sex_2022.csv")
        self.outc = read(ex / "outcomes_panel.csv")
        self.sector = read(ex / "sector_panel.csv")
        self.files = {p.stem: read(p) for p in sorted((root / "outputs").glob("*.csv"))}
        self.units = sorted({r["unit"] for r in self.npy})

    # -- helpers --------------------------------------------------------------------

    def same(self, what: str, printed, expected):
        if printed != expected:
            self.bad.append(f"{what}: printed {printed!r} but expected {expected!r}")

    def near(self, what: str, printed, expected, tol, rel=False):
        p = flt(printed) if isinstance(printed, str) else printed
        if p is None or expected is None:
            if not (p is None and expected is None):
                self.bad.append(f"{what}: printed {printed!r} but expected {expected!r}")
            return
        d = abs(p - expected)
        if d > (tol * max(abs(expected), 1e-300) if rel else tol):
            self.bad.append(f"{what}: printed {p!r} but the exact expectation is "
                            f"{expected!r} (tolerance {tol}{' relative' if rel else ''})")

    def val(self, what: str, printed, expected, rel=REL):
        p = flt(printed) if isinstance(printed, str) else printed
        if not close(p, expected, rel):
            self.bad.append(f"{what}: printed {printed!r} but recomputed {expected!r}")

    def one(self, name: str, **where) -> dict:
        rows = [r for r in self.files[name] if all(r.get(k) == v for k, v in where.items())]
        if len(rows) != 1:
            raise KeyError(f"{name}.csv: {len(rows)} rows match {where}")
        return rows[0]

    # -- inputs ---------------------------------------------------------------------

    def load_chain(self):
        cells: dict = {}
        for r in self.npy:
            cells.setdefault((r["unit"], int(r["year"])), {})[r["measure"]] = \
                integer(r["value"])
        self.cells = cells
        self.chain = {}
        for (u, t), m in cells.items():
            D, B, Q = m.get("denominator"), m.get("bank_available"), m.get("paid")
            has_v = "bank_validated" in m
            Vd = m.get("bank_validated")
            na = chain_na(D, B, Q, Vd, has_v)
            c = {"D": D, "B": B, "Q": Q, "Vd": Vd, "has_v": has_v, "na": na}
            for s, (num, den) in {"A": (B, D), "P": (Q, B), "C": (Q, D), "V": (Vd, B),
                                  "PV": (Q, Vd)}.items():
                c[s] = None if (s in na or (s in ("V", "PV") and not has_v)) \
                    else num / den
                c[s + "_x"], c[s + "_n"] = num, den
            c["U"] = D - Q if (D is not None and Q is not None and Q <= D) else None
            c["U_acc"] = None if "A" in na else D - B
            c["U_pay"] = None if ("A" in na or "P" in na) else B - Q
            self.chain[(u, t)] = c
        if len(self.chain) != 99 or len(self.units) != 33:
            raise ValueError(f"npy_panel.csv holds {len(self.chain)} unit-years")

    def need(self):
        """Plan 4.2-4.3: unit -> w, m, f, G; n_u and wt_u per weighting."""
        sheets: dict = {}
        for r in self.nfhs:
            flags = r["flag"].split(";")
            tgt = next((f.split(":", 1)[1] for f in flags if f.startswith("merge_into:")),
                       r["unit"])
            sheets.setdefault(tgt, {}).setdefault(r["unit"], {})[r["sex"]] = \
                flt(r["bmi_below_normal_pct"])
        W, fem, tot = {}, {}, {}
        for r in self.sex:
            if r["unit"] == "":
                continue            # the printed India row
            m, f, t = integer(r["male"]), integer(r["female"]), integer(r["transgender"])
            if None in (m, f, t):
                continue
            W[r["printed_unit"]] = m + f + t
            fem[r["unit"]] = fem.get(r["unit"], 0) + f
            tot[r["unit"]] = tot.get(r["unit"], 0) + m + f + t
        self.G = {u: tot.get(u) for u in self.units}
        self.f = {u: fem[u] / tot[u] if tot.get(u) else None for u in self.units}
        self.w, self.m = {}, {}
        for u in self.units:
            for key, store in (("women", self.w), ("men", self.m)):
                vals = [(j, s[key] / 100.0) for j, s in sheets[u].items()
                        if s.get(key) is not None]
                if not vals:
                    store[u] = None
                elif len(sheets[u]) == 1:
                    store[u] = vals[0][1]
                else:
                    ws = sum(W[j] for j, _ in vals)
                    store[u] = (sum(W[j] * v for j, v in vals) / ws if ws > 0
                                else sum(v for _, v in vals) / len(vals))
        self.n, self.wt, self.nbar = {}, {}, {}
        for wg in WEIGHTINGS:
            n = {}
            for u in self.units:
                w, m, f = self.w[u], self.m[u], self.f[u]
                if w is None or m is None or f is None:
                    n[u] = None
                else:
                    n[u] = {"sex_weighted": f * w + (1.0 - f) * m, "women": w, "men": m,
                            "simple": (w + m) / 2.0}[wg]
            use = [u for u in self.units if n[u] is not None and self.G[u] is not None]
            nbar = sum(self.G[u] * n[u] for u in use) / sum(self.G[u] for u in use)
            self.n[wg] = n
            self.nbar[wg] = nbar
            self.wt[wg] = {u: (n[u] / nbar if u in use else None) for u in self.units}

    def years_rows(self, t):
        return [(u, self.chain[(u, t)]) for u in self.units]

    # -- (a) the chain ----------------------------------------------------------------

    def check_chain(self):
        n0 = len(self.bad)
        rows = {(r["unit"], int(r["year"])): r for r in self.files["chain"]
                if r["level"] == "unit"}
        self.same("(a) chain.csv unit rows", len(rows), 99)
        for (u, t), c in self.chain.items():
            r = rows[(u, t)]
            w = f"(a) {u} {t}"
            self.same(f"{w} D", integer(r["D_denominator"]), c["D"])
            self.same(f"{w} B", integer(r["B_bank_available"]), c["B"])
            self.same(f"{w} Q", integer(r["Q_paid_at_least_once"]), c["Q"])
            self.same(f"{w} validated", integer(r["bank_validated"]),
                      c["Vd"] if c["has_v"] else None)
            cols = {"A": "A", "P": "P", "C": "C", "V": "V", "PV": "paid_over_validated"}
            for s, col in cols.items():
                self.val(f"{w} {col}", r[col], c[s])
                if c[s] is None:
                    lo = hi = None
                else:
                    lo, hi = jeffreys_interval(c[s + "_x"], c[s + "_n"])
                self.val(f"{w} {col}_lo", r[col + "_lo"], lo, REL_Q)
                self.val(f"{w} {col}_hi", r[col + "_hi"], hi, REL_Q)
            for k in ("U", "U_acc", "U_pay"):
                self.same(f"{w} {k}", integer(r[k]), c[k])
            if c["U"] is not None and c["U_acc"] is not None and c["U_pay"] is not None:
                self.same(f"{w} U = U_acc + U_pay", c["U"], c["U_acc"] + c["U_pay"])
            self.same(f"{w} NA steps", sorted(x.split(":")[0] for x in
                                              r["na_steps"].split(";") if x),
                      sorted(c["na"]))
        nat = {int(r["year"]): r for r in self.files["chain"] if r["level"] == "national"}
        for t in YEARS:
            r, rows_t = nat[t], [c for _, c in self.years_rows(t)]
            for s in ("A", "P", "C"):
                use = [c for c in rows_t if c[s] is not None]
                x, n = sum(c[s + "_x"] for c in use), sum(c[s + "_n"] for c in use)
                v, lo, hi = wilson(x, n)
                w = f"(a) national {t} {s}"
                self.val(w, r[s], v)
                self.val(w + "_lo", r[s + "_lo"], lo)
                self.val(w + "_hi", r[s + "_hi"], hi)
                self.same(w + " n_units", integer(r[f"n_units_{s}"]), len(use))
            for k in ("U", "U_acc", "U_pay"):
                use = [c for c in rows_t if c[k] is not None]
                self.same(f"(a) national {t} {k}", integer(r[k]), sum(c[k] for c in use))
                self.same(f"(a) national {t} {k} n_units", integer(r[f"n_units_{k}"]),
                          len(use))
        if len(self.bad) == n0:
            n3 = sum(self.chain[(u, 2023)]["U"] or 0 for u in self.units)
            self.ok.append(f"(a) chain: 99 unit-years (A, P, C, V, paid/validated with "
                           f"Jeffreys intervals, U, U_acc, U_pay, NA steps) and the "
                           f"national A, P, C (Wilson) and unpaid counts; U(2023) = {n3}")

    # -- (b) the need weight -------------------------------------------------------------

    def check_need(self):
        n0 = len(self.bad)
        self.need()
        rows = {(r["unit"], r["spec"]): r for r in self.files["need_weight"]}
        self.same("(b) need_weight.csv rows", len(rows), 4 * 33)
        for wg in WEIGHTINGS:
            for u in self.units:
                r = rows[(u, wg)]
                w = f"(b) {u} {wg}"
                self.val(w + " w_u", r["w_u_women"], self.w[u])
                self.val(w + " m_u", r["m_u_men"], self.m[u])
                self.val(w + " f_u", r["f_u_female_share_2022"], self.f[u])
                self.same(w + " G_u", integer(r["G_u_notified_2022"]), self.G[u])
                self.val(w + " n_u", r["n_u"], self.n[wg][u])
                self.val(w + " n_bar", r["n_bar"], self.nbar[wg])
                self.val(w + " wt_u", r["wt_u_relative_need_weight"], self.wt[wg][u])
            use = [u for u in self.units if self.wt[wg][u] is not None]
            mean = (sum(self.G[u] * self.wt[wg][u] for u in use)
                    / sum(self.G[u] for u in use))
            self.val(f"(b) {wg}: the G-weighted mean of wt_u", mean, 1.0, 1e-12)
        if len(self.bad) == n0:
            self.ok.append(f"(b) need weight: w_u, m_u, f_u, G_u, n_u, n-bar and wt_u for "
                           f"4 weightings x 33 units; n-bar (sex-weighted) "
                           f"{self.nbar['sex_weighted']:.6f}")

    # -- (c) the shortfalls and the classes -------------------------------------------------

    def own_draws(self, key, a_par, p_par):
        """Own Monte Carlo draws (random.betavariate), fixed by the parameters."""
        cache = self.__dict__.setdefault("_draws", {})
        if key not in cache:
            rng = random.Random(zlib.crc32(repr(key).encode()))
            cache[key] = ([rng.betavariate(*a_par) for _ in range(OWN_DRAWS)],
                          [rng.betavariate(*p_par) for _ in range(OWN_DRAWS)])
        return cache[key]

    def class_from(self, p_zero, p_acc, p_pay) -> str:
        if p_zero > 0.5:
            return NO_SHORTFALL
        if p_acc >= 0.95:
            return ACCOUNT
        if p_pay >= 0.95:
            return PAYMENT
        return MIXED

    def check_shortfall(self):
        n0 = len(self.bad)
        sf = {(r["unit"], int(r["year"]), r["spec"]): r for r in self.files["shortfall"]}
        self.same("(c) shortfall.csv rows", len(sf), 3 * 99)
        cls = {(r["unit"], int(r["year"]), r["spec"]): r for r in self.files["chain_class"]}
        borderline, n_cls = [], 0
        for t in YEARS:
            rows = self.years_rows(t)
            ra = [c for _, c in rows if c["A"] is not None]
            rp = [c for _, c in rows if c["P"] is not None]
            a1, b1 = prior_or_jeffreys([c["B"] for c in ra], [c["D"] for c in ra])
            a2, b2 = prior_or_jeffreys([c["Q"] for c in rp], [c["B"] for c in rp])
            A_hat = {u: (a1 + c["B"]) / (a1 + b1 + c["D"]) for u, c in rows
                     if c["A"] is not None}
            P_hat = {u: (a2 + c["Q"]) / (a2 + b2 + c["B"]) for u, c in rows
                     if c["P"] is not None}
            for spec, pct in PCTS.items():
                Ab, Pb = (percentile(list(A_hat.values()), pct),
                          percentile(list(P_hat.values()), pct))
                for u, c in rows:
                    r, w = sf[(u, t, spec)], f"(c) {u} {t} {spec}"
                    for col, v in (("alpha1", a1), ("beta1", b1), ("alpha2", a2),
                                   ("beta2", b2), ("A_bench", Ab), ("P_bench", Pb)):
                        self.val(f"{w} {col}", r[col], v)
                    self.val(f"{w} A_hat", r["A_hat"], A_hat.get(u))
                    self.val(f"{w} P_hat", r["P_hat"], P_hat.get(u))
                    self.same(f"{w} D", integer(r["D"]), c["D"])
                    self.val(f"{w} A", r["A"], c["A"])
                    self.val(f"{w} P", r["P"], c["P"])
                    if c["A"] is None or c["P"] is None:
                        self.same(f"{w} class (A or P NA: none)", r["class"], "")
                        self.same(f"{w} S_acc (A or P NA)", flt(r["S_acc"]), None)
                        continue
                    n_cls += 1
                    s_acc = c["D"] * max(0.0, Ab - c["A"])
                    s_pay = c["D"] * c["A"] * max(0.0, Pb - c["P"])
                    self.val(f"{w} S_acc", r["S_acc"], s_acc)
                    self.val(f"{w} S_pay", r["S_pay"], s_pay)
                    self.val(f"{w} account_share_observed", r["account_share_observed"],
                             s_acc / (s_acc + s_pay) if s_acc + s_pay > 0 else None)
                    ap, bp = a1 + c["B"], b1 + c["D"] - c["B"]
                    pp, qp = a2 + c["Q"], b2 + c["B"] - c["Q"]
                    # exact expectations of the Monte Carlo summaries
                    ma, sa = beta_mean_sd(ap, bp)
                    mp, sp = beta_mean_sd(pp, qp)
                    e_acc = c["D"] * e_short(Ab, ap, bp)
                    sd_acc = c["D"] * math.sqrt(max(0.0, e_short(Ab, ap, bp, 2)
                                                    - e_short(Ab, ap, bp) ** 2))
                    h1, h2 = e_short(Pb, pp, qp), e_short(Pb, pp, qp, 2)
                    e_pay = c["D"] * ma * h1
                    ea2 = sa * sa + ma * ma
                    sd_pay = c["D"] * math.sqrt(max(0.0, ea2 * h2 - (ma * h1) ** 2))
                    self.near(f"{w} S_acc_mean", r["S_acc_mean"], e_acc,
                              MC_SE * sd_acc / 100.0 + 1e-6)
                    self.near(f"{w} S_pay_mean", r["S_pay_mean"], e_pay,
                              MC_SE * sd_pay / 100.0 + 1e-6)
                    # S_acc is a decreasing function of a: its percentiles are exact
                    lo = c["D"] * max(0.0, Ab - beta_ppf(0.975, ap, bp))
                    hi = c["D"] * max(0.0, Ab - beta_ppf(0.025, ap, bp))
                    tol = c["D"] * Q_TOL * sa + 1e-6
                    self.near(f"{w} S_acc_lo", r["S_acc_lo"], lo, tol)
                    self.near(f"{w} S_acc_hi", r["S_acc_hi"], hi, tol)
                    # exact P(S_acc + S_pay = 0) = P(a >= A_bench) P(p >= P_bench)
                    pz = (1.0 - betainc(ap, bp, Ab)) * (1.0 - betainc(pp, qp, Pb))
                    pz_p = flt(r["p_zero"])
                    self.near(f"{w} p_zero", pz_p, pz,
                              MC_SE * math.sqrt(pz * (1.0 - pz) / N_DRAWS) + 0.001)
                    # the printed class follows the printed shares
                    pa, pb = flt(r["p_acc_ge_2_3"]), flt(r["p_pay_ge_2_3"])
                    self.same(f"{w} class from its printed shares",
                              r["class"], self.class_from(pz_p, pa, pb))
                    cc = cls[(u, t, spec)]
                    for col in ("class", "p_zero", "p_acc_ge_2_3", "p_pay_ge_2_3", "S_acc",
                                "S_pay", "status"):
                        self.same(f"{w} chain_class.csv {col}", cc[col], r[col])
                    # own Monte Carlo of the class shares
                    da, dp = self.own_draws((u, t, ap, bp, pp, qp), (ap, bp), (pp, qp))
                    z = pa_n = pp_n = 0
                    for a_, p_ in zip(da, dp):
                        sacc = c["D"] * max(0.0, Ab - a_)
                        spay = c["D"] * a_ * max(0.0, Pb - p_)
                        tot = sacc + spay
                        if tot <= 0:
                            z += 1
                            continue
                        sh = sacc / tot
                        pa_n += sh >= 2.0 / 3.0
                        pp_n += (1.0 - sh) >= 2.0 / 3.0
                    mc = (z / OWN_DRAWS, pa_n / OWN_DRAWS, pp_n / OWN_DRAWS)
                    tols = []
                    for name, printed, own in zip(("p_zero", "p_acc", "p_pay"),
                                                  (pz_p, pa, pb), mc):
                        pc = min(max(printed, 0.001), 0.999)
                        tl = 5 * math.sqrt(pc * (1 - pc) * (1 / OWN_DRAWS + 1 / N_DRAWS)) \
                            + 0.003
                        tols.append(tl)
                        if abs(printed - own) > tl:
                            self.bad.append(f"{w} {name}: printed {printed} but the own "
                                            f"Monte Carlo gives {own} (tolerance {tl:.4f})")
                    own_cls = self.class_from(*mc)
                    if own_cls != r["class"]:
                        th = ((pz_p, 0.5, tols[0]) if NO_SHORTFALL in (own_cls, r["class"])
                              else (pa if ACCOUNT in (own_cls, r["class"]) else pb, 0.95,
                                    tols[1]))
                        if abs(th[0] - th[1]) <= th[2] + 0.02:
                            borderline.append(f"{u} {t} {spec}")
                        else:
                            self.bad.append(f"{w} class: printed {r['class']!r} but the own "
                                            f"draws give {own_cls!r} (p {mc})")
        if len(self.bad) == n0:
            self.ok.append(f"(c) shortfalls: priors, A_hat, P_hat, benchmarks, observed "
                           f"S_acc and S_pay, exact expectations and class shares for "
                           f"{n_cls} classified unit-year-benchmarks"
                           + (f"; borderline (either class accepted): "
                              f"{'; '.join(borderline)}" if borderline else ""))

    # -- (d) the budget --------------------------------------------------------------------

    def check_budget(self):
        n0 = len(self.bad)
        t = YEAR
        rows = self.years_rows(t)
        use = [(u, c) for u, c in rows if c["U"] is not None]
        draws = [(u, c) for u, c in use if c["C"] is not None]   # D > 0: a rate exists
        x, n = [c["U"] for _, c in draws], [c["D"] for _, c in draws]
        alpha, beta = prior_or_jeffreys(x, n)
        post = {u: (alpha + c["U"]) / (alpha + beta + c["D"]) for u, c in draws}
        C_hat = {u: 1.0 - v for u, v in post.items()}
        U_total = sum(c["U"] for _, c in use)
        mean = sum(c["D"] * post[u] for u, c in draws)
        var = 0.0
        for u, c in draws:
            _, sd = beta_mean_sd(alpha + c["U"], beta + c["D"] - c["U"])
            var += (c["D"] * sd) ** 2
        sd_tot = math.sqrt(var)
        excl = [u for u, c in rows if c["U"] is None]
        b = self.files["budget"]

        def pick(prefix, spec=""):
            rs = [r for r in b if r["item"].startswith(prefix) and r["spec"] == spec]
            if len(rs) != 1:
                raise KeyError(f"budget.csv: {len(rs)} rows for {prefix!r} {spec!r}")
            return rs[0]

        def common(r, w):
            self.same(f"{w} year", integer(r["year"]), t)
            self.same(f"{w} units_with_data", integer(r["units_with_data"]), len(use))
            self.same(f"{w} units_excluded", r["units_excluded"].split(";") if
                      r["units_excluded"] else [], excl)

        r = pick("U(2023), people not paid")
        common(r, "(d) U(2023)")
        self.same("(d) U(2023) count", integer(r["count"]), U_total)
        self.near("(d) U(2023) draw mean", r["count_draw_mean"], mean,
                  MC_SE * sd_tot / 100.0 + 1e-6)
        lo_e, hi_e = mean - Z * sd_tot, mean + Z * sd_tot
        self.near("(d) U(2023) count_lo", r["count_lo"], lo_e, Q_TOL * sd_tot)
        self.near("(d) U(2023) count_hi", r["count_hi"], hi_e, Q_TOL * sd_tot)
        grid = [("main: ", "main", RATE_MAIN, MONTHS_MAIN)] + [
            ("range: ", f"rate {rate}, {m} months", rate, m) for rate in RATES
            for m in MONTHS]
        for prefix, spec, rate, months in grid:
            r = pick(prefix, spec)
            w = f"(d) {prefix}{spec}"
            common(r, w)
            self.same(f"{w} rate_per_month", integer(r["rate_per_month"]), rate)
            self.same(f"{w} months", integer(r["months"]), months)
            self.same(f"{w} count", integer(r["count"]), U_total)
            self.same(f"{w} cost", integer(r["cost"]), U_total * rate * months)
            self.val(f"{w} cost_lo", r["cost_lo"], flt(r["count_lo"]) * rate * months)
            self.val(f"{w} cost_hi", r["cost_hi"], flt(r["count_hi"]) * rate * months)
        current = sum(c["Q"] for _, c in use)
        benches = {}
        for spec, pct in PCTS.items():
            cb = percentile([C_hat[u] for u in sorted(C_hat)], pct)
            benches[spec] = cb
            number = sum(c["D"] * max(c["Q"] / c["D"], cb) for _, c in draws)
            inc = sum(c["D"] * max(0.0, cb - c["Q"] / c["D"]) for _, c in draws)
            for prefix, count in (("benchmark scenario: national number", number),
                                  ("benchmark scenario: increment", inc)):
                r = pick(prefix, spec)
                w = f"(d) {prefix} {spec}"
                common(r, w)
                self.val(w + " C_bench", r["C_bench"], cb)
                self.same(w + " current number", integer(r["current_number_paid_at_least_once"]),
                          current)
                self.val(w + " count", r["count"], count)
                self.val(w + " cost", r["cost"], count * TOTAL)
                self.same(w + " cost basis", r["cost_basis"], "x Rs 6,000")
        if len(self.bad) == n0:
            self.ok.append(f"(d) budget {t}: U = {U_total} over {len(use)} units "
                           f"(excluding {', '.join(excl) or 'none'}), main cost "
                           f"{U_total * RATE_MAIN * MONTHS_MAIN}; ranges; C_bench "
                           f"p75 {benches['p75']:.6f}")

    # -- (e) H1 and H2 -------------------------------------------------------------------

    def coverage(self, t):
        return {u: self.chain[(u, t)]["C"] for u in self.units}

    def share(self, t):
        v = {}
        for r in self.sector:
            if int(r["year"]) == t:
                v.setdefault(r["unit"], {})[r["measure"]] = integer(r["value"])
        return {u: (m["private"] / m["total"] if m.get("private") is not None
                    and m.get("total") else None) for u, m in v.items()}

    @staticmethod
    def corr(x: dict, y: dict, method="spearman", omit=None):
        us = sorted(u for u in x if u in y and x[u] is not None and y[u] is not None
                    and u != omit)
        xs, ys = [x[u] for u in us], [y[u] for u in us]
        return (spearman(xs, ys) if method == "spearman" else kendall_b(xs, ys)), len(us)

    def grid_check(self, h, entries, w_main):
        """entries: list of (spec_curve filter, estimate, n); returns the signs."""
        sc = self.files["spec_curve"]
        signs = []
        for where, est, n in entries:
            rs = [r for r in sc if r["hypothesis"] == h
                  and all(r[k] == str(v) for k, v in where.items())]
            if len(rs) != 1:
                raise KeyError(f"spec_curve.csv: {len(rs)} rows for {h} {where}")
            r, w = rs[0], f"(e) {h} {where}"
            self.val(w + " estimate", r["estimate"], est)
            self.same(w + " n", integer(r["n"]), n)
            self.same(w + " sign", integer(r["sign"]), sign(est))
            signs.append(sign(est))
        mains = [r for r in sc if r["hypothesis"] == h and r["main"] == "True"]
        self.same(f"(e) {h} one main entry", len(mains), 1)
        return signs

    def check_h12(self):
        n0 = len(self.bad)
        C = {t: self.coverage(t) for t in YEARS}
        specs = {}
        h1_entries = []
        for wg in WEIGHTINGS:
            for t in YEARS:
                est, n = self.corr(C[t], self.n[wg])
                h1_entries.append(({"weighting": wg, "year": t}, est, n))
        h2_entries = []
        for t in YEARS:
            for m in ("spearman", "kendall"):
                est, n = self.corr(C[t], self.share(t), m)
                h2_entries.append(({"year": t, "method": m}, est, n))
        for h, ents, main_where in (("H1", h1_entries, {"weighting": "sex_weighted",
                                                        "year": 2023}),
                                    ("H2", h2_entries, {"year": 2023, "method": "spearman"})):
            signs = self.grid_check(h, ents, main_where)
            main = next(e for w, e, n in ents if w == main_where)
            n = next(n for w, e, n in ents if w == main_where)
            lo, hi = fisher(main, n)
            r = self.one("headline", hypothesis=h)
            self.val(f"(e) {h} estimate", r["estimate"], main)
            self.val(f"(e) {h} lo", r["lo"], lo)
            self.val(f"(e) {h} hi", r["hi"], hi)
            self.same(f"(e) {h} n", integer(r["n"]), n)
            self.same(f"(e) {h} null", flt(r["null"]), 0.0)
            mr = [x for x in self.files["spec_curve"] if x["hypothesis"] == h
                  and x["main"] == "True"][0]
            self.same(f"(e) {h} main entry is the headline", mr["estimate"], r["estimate"])
            specs[h] = (signs, sign(main), lo, hi, r)
        self.h12 = specs
        if len(self.bad) == n0:
            r1, r2 = specs["H1"][4], specs["H2"][4]
            self.ok.append(f"(e) H1 rho {float(r1['estimate']):.4f} (n {r1['n']}) and H2 rho "
                           f"{float(r2['estimate']):.4f} (n {r2['n']}): 12 + 6 grid entries "
                           f"and the Fisher-z intervals")

    # -- (f) H3 ---------------------------------------------------------------------------

    def valid_cohort(self, u, t):
        o = self.cohort.get((u, t))
        if not o:
            return False
        n = o.get("cohort")
        return n is not None and n > 0 and all(o.get(k) is not None and o[k] <= n
                                               for k in OUTCOMES)

    def h3_fit(self, outcome, year_set, adjust):
        years = YEAR_SETS[year_set]
        sector = {t: self.share(t) for t in years}
        X, y, a, ou = [], [], [], []
        for u in self.units:
            for t in years:
                c = self.chain[(u, t)]
                if c["C"] is None or not self.valid_cohort(u, t):
                    continue
                row = [1.0, math.log((c["Q"] + 0.5) / (c["D"] - c["Q"] + 0.5))]
                if len(years) > 1:
                    row.append(1.0 if t == 2022 else 0.0)
                if adjust in (PREV, PREV_PRIVATE):
                    if not self.valid_cohort(u, t - 1):
                        continue
                    pv = self.cohort[(u, t - 1)]
                    row.append(pv["success"] / pv["cohort"])
                if adjust in (PRIVATE, PREV_PRIVATE):
                    s = sector[t].get(u)
                    if s is None:
                        continue
                    row.append(s)
                o = self.cohort[(u, t)]
                X.append(row)
                y.append(o[outcome] / o["cohort"])
                a.append(float(o["cohort"]))
                ou.append(u)
        fit = irls(X, y, a)
        K: dict = {}
        for u, ai in zip(ou, a):
            K[u] = K.get(u, 0.0) + ai
        fit.update(n_obs=len(y), n_units=len(K),
                   kish=math.fsum(K.values()) ** 2 / math.fsum(v * v for v in K.values()))
        return fit

    def check_h3(self):
        n0 = len(self.bad)
        self.cohort = {}
        for r in self.outc:
            self.cohort.setdefault((r["unit"], int(r["cohort_year"])), {})[r["measure"]] = \
                integer(r["value"])
        sc = self.files["spec_curve"]
        summary = []
        for o in OUTCOMES:
            h = f"H3_{o}"
            signs, ents = [], []
            for i, (ys, adj) in enumerate(H3_GRID, 1):
                f = self.h3_fit(o, ys, adj)
                rs = [r for r in sc if r["hypothesis"] == h and r["year_set"] == ys
                      and r["adjustment"] == adj]
                if len(rs) != 1:
                    raise KeyError(f"spec_curve.csv: {len(rs)} rows for {h} {ys} {adj}")
                r, w = rs[0], f"(f) {h} {ys} / {adj}"
                self.same(w + " entry number", integer(r["entry"]), i)
                self.near(w + " estimate", r["estimate"], f["beta"][1], TOL_B)
                self.near(w + " phi", r["phi"], f["phi"], REL_FIT, rel=True)
                self.near(w + " wald_lo", r["wald_lo"], f["lo"], REL_FIT, rel=True)
                self.near(w + " wald_hi", r["wald_hi"], f["hi"], REL_FIT, rel=True)
                self.same(w + " n_obs", integer(r["n_obs"]), f["n_obs"])
                self.same(w + " n_units", integer(r["n"]), f["n_units"])
                self.same(w + " sign", integer(r["sign"]), sign(f["beta"][1]))
                signs.append(sign(f["beta"][1]))
                ents.append(f)
            main = ents[0]
            ms = sign(main["beta"][1])
            for r, s in zip([x for x in sc if x["hypothesis"] == h], signs):
                self.same(f"(f) {h} entry {r['entry']} agrees_with_main",
                          r["agrees_with_main"], str(s is not None and s == ms and ms in
                                                     (1, -1)))
            r = self.one("headline", hypothesis=h)
            self.near(f"(f) {h} headline estimate", r["estimate"], main["beta"][1], TOL_B)
            self.near(f"(f) {h} headline phi", r["phi"], main["phi"], REL_FIT, rel=True)
            self.near(f"(f) {h} headline wald_lo", r["wald_lo"], main["lo"], REL_FIT,
                      rel=True)
            self.near(f"(f) {h} headline wald_hi", r["wald_hi"], main["hi"], REL_FIT,
                      rel=True)
            self.near(f"(f) {h} Kish effective clusters", r["kish_effective_clusters"],
                      main["kish"], REL_FIT, rel=True)
            self.same(f"(f) {h} n_obs", integer(r["n_obs"]), main["n_obs"])
            self.same(f"(f) {h} n (units)", integer(r["n"]), main["n_units"])
            self.same(f"(f) {h} null", flt(r["null"]), 0.0)
            self.h3 = getattr(self, "h3", {})
            self.h3[o] = (signs, ms, flt(r["lo"]), flt(r["hi"]), r)
            summary.append(f"{o} {main['beta'][1]:.4f}")
        if len(self.bad) == n0:
            self.ok.append(f"(f) H3: 24 entries by the own IRLS (slope, phi, Wald interval, "
                           f"n_obs, n_units), Kish clusters; main slopes: "
                           f"{'; '.join(summary)}")

    # -- (g) the label ---------------------------------------------------------------------

    def check_labels(self):
        n0 = len(self.bad)
        out = []
        both = {**self.h12, **{f"H3_{o}": v for o, v in self.h3.items()}}
        for h, (signs, ms, lo, hi, r) in both.items():
            lo_p, hi_p = flt(r["lo"]), flt(r["hi"])
            lab, agree = label(lo_p, hi_p, signs, ms)
            self.same(f"(g) {h} label", r["label"], lab)
            self.same(f"(g) {h} n_agree", integer(r["n_agree"]), agree)
            self.same(f"(g) {h} n_entries", integer(r["n_entries"]), len(signs))
            self.same(f"(g) {h} n_required", integer(r["n_required"]),
                      -(-4 * len(signs) // 5))
            self.same(f"(g) {h} main_sign", integer(r["main_sign"]), ms)
            g = self.one("spec_grid", hypothesis=h)
            excl = (lo_p is not None and hi_p is not None
                    and ((lo_p > 0 and hi_p > 0) or (lo_p < 0 and hi_p < 0)))
            self.same(f"(g) {h} spec_grid label", g["label"], lab)
            self.same(f"(g) {h} spec_grid n_agree", integer(g["n_agree"]), agree)
            self.same(f"(g) {h} spec_grid n_entries", integer(g["n_entries"]), len(signs))
            self.same(f"(g) {h} spec_grid interval_excludes_null",
                      g["interval_excludes_null"], str(excl))
            self.same(f"(g) {h} spec_grid main_sign", integer(g["main_sign"]), ms)
            self.val(f"(g) {h} spec_grid share_agree", g["share_agree"],
                     agree / len(signs))
            out.append(f"{h} {lab!r} ({agree}/{len(signs)})")
        if len(self.bad) == n0:
            self.ok.append("(g) labels: " + "; ".join(out))

    def run(self):
        try:
            self.load_chain()
        except (KeyError, ValueError, ArithmeticError, TypeError) as e:
            self.bad.append(f"load_chain: {type(e).__name__}: {e}")
            return self.bad, self.ok
        steps = [self.check_chain, self.check_need, self.check_shortfall,
                 self.check_budget, self.check_h12, self.check_h3, self.check_labels]
        for step in steps:
            try:
                step()
            except (KeyError, ValueError, ArithmeticError, StopIteration, TypeError,
                    AttributeError, IndexError, ZeroDivisionError) as e:
                self.bad.append(f"{step.__name__}: {type(e).__name__}: {e}")
                if step in (self.check_need, self.check_h12, self.check_h3):
                    break      # later steps need its results
        return self.bad, self.ok


def problems(root: Path = ROOT) -> tuple[list[str], list[str]]:
    """(failures, one summary line per passed part)."""
    try:
        return Checker(root).run()
    except (OSError, KeyError, ValueError) as e:
        return [f"{type(e).__name__}: {e}"], []


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--root", default=str(ROOT), help="repository root (default: this one)")
    bad, ok = problems(Path(ap.parse_args(argv).root))
    for line in ok:
        print(line)
    if bad:
        for b in bad:
            print(f"FAIL: {b}")
        return 1
    print(f"OK: the standard-library recompute matches outputs/ ({len(ok)} parts)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
