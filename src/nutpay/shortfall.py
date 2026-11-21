"""Chain priors and draws, the benchmark, the shortfalls and the class rule (analysis plan
sections 5.3-5.4).

Priors: (alpha1, beta1) = tbprio.shrink.beta_binomial(B, D) over the units with non-NA A;
(alpha2, beta2) = tbprio.shrink.beta_binomial(Q, B) over the units with non-NA P. If the
prior cannot be fitted (fewer than 2 units, or a pooled rate of 0 or 1) the Jeffreys prior
tbprio.shrink.JEFFREYS_BINOMIAL is used and the flag ``prior_fallback_jeffreys`` is set.
Posterior means A_hat = (alpha1 + B)/(alpha1 + beta1 + D), P_hat = (alpha2 + Q)/(alpha2 +
beta2 + B).

Draws: the caller passes a fresh numpy.random.default_rng([20261123, 1]) for each data
year. Units in alphabetical order; for each unit, where the measure is non-NA,
a = rng.beta(alpha1 + B, beta1 + D - B, size=10000), then p = rng.beta(alpha2 + Q,
beta2 + B - Q, size=10000).

Benchmark: A_bench and P_bench are the pct-th percentiles (numpy linear) of A_hat and
P_hat across the year's units with the measure non-NA (75 main; 50 and 90 sensitivities).

Shortfalls: S_acc = D max(0, A_bench - A), S_pay = D A max(0, P_bench - P), observed with
the observed A and P and in each draw with a and p. Class over units with A and P non-NA,
in this order: "no shortfall" if S_acc + S_pay = 0 in more than 50% of the draws;
"account-led" if the draws with S_acc/(S_acc + S_pay) >= 2/3, divided by all draws, is at
least 0.95; "payment-led" likewise for the payment share; otherwise "mixed". A draw with
no shortfall has no share and stays in the denominator.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
from tbprio import harm as tbharm
from tbprio import shrink

from . import N_DRAWS

PCTS = (75.0, 50.0, 90.0)          # main first
TWO_THIRDS = 2.0 / 3.0
PROB = 0.95
FALLBACK = "prior_fallback_jeffreys"
NO_SHORTFALL, ACCOUNT, PAYMENT, MIXED = "no shortfall", "account-led", "payment-led", "mixed"


def spec_name(pct: float) -> str:
    return f"p{int(pct)}"


def prior(x, n) -> tuple[float, float, str]:
    """(alpha, beta, flag): tbprio's empirical-Bayes prior, or Jeffreys with the flag."""
    try:
        a, b = shrink.beta_binomial(np.asarray(x, dtype=float), np.asarray(n, dtype=float))
        return a, b, ""
    except ValueError as e:
        if not str(e).startswith("beta_binomial"):
            raise
        a, b = shrink.JEFFREYS_BINOMIAL
        return a, b, FALLBACK


@dataclass
class ChainDraws:
    year: int
    alpha1: float
    beta1: float
    flag1: str
    alpha2: float
    beta2: float
    flag2: str
    A_hat: dict[str, float]
    P_hat: dict[str, float]
    a: dict[str, np.ndarray] = field(repr=False)
    p: dict[str, np.ndarray] = field(repr=False)


def _year_rows(chain_rows: list[dict], year: int) -> list[dict]:
    return sorted((r for r in chain_rows if r["year"] == year), key=lambda r: r["unit"])


def draws(chain_rows: list[dict], year: int, rng: np.random.Generator,
          n_draws: int = N_DRAWS) -> ChainDraws:
    rows = _year_rows(chain_rows, year)
    ra = [r for r in rows if r["A"] is not None]
    rp = [r for r in rows if r["P"] is not None]
    a1, b1, f1 = prior([r["B"] for r in ra], [r["D"] for r in ra])
    a2, b2, f2 = prior([r["Q"] for r in rp], [r["B"] for r in rp])
    A_hat = {r["unit"]: (a1 + r["B"]) / (a1 + b1 + r["D"]) for r in ra}
    P_hat = {r["unit"]: (a2 + r["Q"]) / (a2 + b2 + r["B"]) for r in rp}
    ad: dict[str, np.ndarray] = {}
    pd: dict[str, np.ndarray] = {}
    for r in rows:   # alphabetical
        u = r["unit"]
        if r["A"] is not None:
            ad[u] = rng.beta(a1 + r["B"], b1 + r["D"] - r["B"], size=n_draws)
        if r["P"] is not None:
            pd[u] = rng.beta(a2 + r["Q"], b2 + r["B"] - r["Q"], size=n_draws)
    return ChainDraws(year, a1, b1, f1, a2, b2, f2, A_hat, P_hat, ad, pd)


def benchmarks(cd: ChainDraws, pct: float) -> tuple[float | None, float | None]:
    def q(vals):
        return (float(np.percentile(np.array(vals), pct, method="linear"))
                if vals else None)
    return q(list(cd.A_hat.values())), q(list(cd.P_hat.values()))


def shortfall_draws(cd: ChainDraws, chain_rows: list[dict], year: int, pct: float
                    ) -> tuple[dict[str, np.ndarray], dict[str, np.ndarray]]:
    """S_acc and S_pay draws for the units with A and P non-NA."""
    a_b, p_b = benchmarks(cd, pct)
    sa, sp = {}, {}
    for r in _year_rows(chain_rows, year):
        u = r["unit"]
        if u in cd.a and u in cd.p:
            a, p = cd.a[u], cd.p[u]
            sa[u] = r["D"] * np.maximum(0.0, a_b - a)
            sp[u] = r["D"] * a * np.maximum(0.0, p_b - p)
    return sa, sp


def classify(s_acc: np.ndarray, s_pay: np.ndarray) -> dict:
    """The class rule of section 5.4 on one unit's draws."""
    s_acc = np.asarray(s_acc, dtype=float)
    s_pay = np.asarray(s_pay, dtype=float)
    n = s_acc.size
    tot = s_acc + s_pay
    pos = tot > 0
    share = np.zeros(n)
    np.divide(s_acc, tot, out=share, where=pos)
    p_zero = float(np.count_nonzero(~pos)) / n
    p_acc = float(np.count_nonzero(pos & (share >= TWO_THIRDS))) / n
    p_pay = float(np.count_nonzero(pos & ((1.0 - share) >= TWO_THIRDS))) / n
    if np.count_nonzero(~pos) * 2 > n:
        cls = NO_SHORTFALL
    elif p_acc >= PROB:
        cls = ACCOUNT
    elif p_pay >= PROB:
        cls = PAYMENT
    else:
        cls = MIXED
    return {"class": cls, "p_zero": p_zero, "p_acc_ge_2_3": p_acc, "p_pay_ge_2_3": p_pay}


def compute(chain_rows: list[dict], year: int, pct: float, rng: np.random.Generator
            ) -> list[dict]:
    """Every unit of the year under the pct-th percentile benchmark: the posterior means,
    the benchmarks, the observed shortfalls and their draws (mean and 95% interval), and
    the class with its posterior shares. ``rng`` is the year's fresh chain stream."""
    cd = draws(chain_rows, year, rng)
    a_b, p_b = benchmarks(cd, pct)
    sa, sp = shortfall_draws(cd, chain_rows, year, pct)
    out = []
    for r in _year_rows(chain_rows, year):
        u = r["unit"]
        row = {"unit": u, "year": year, "spec": spec_name(pct), "D": r["D"], "A": r["A"],
               "P": r["P"], "A_hat": cd.A_hat.get(u), "P_hat": cd.P_hat.get(u),
               "A_bench": a_b, "P_bench": p_b, "S_acc": None, "S_pay": None,
               "S_acc_mean": None, "S_acc_lo": None, "S_acc_hi": None,
               "S_pay_mean": None, "S_pay_lo": None, "S_pay_hi": None,
               "account_share_observed": None, "p_zero": None, "p_acc_ge_2_3": None,
               "p_pay_ge_2_3": None, "class": None, "status": "",
               "prior_A": cd.flag1 or "empirical Bayes", "prior_P": cd.flag2 or "empirical Bayes",
               "alpha1": cd.alpha1, "beta1": cd.beta1, "alpha2": cd.alpha2, "beta2": cd.beta2}
        if u in sa:
            s_acc = r["D"] * max(0.0, a_b - r["A"])
            s_pay = r["D"] * r["A"] * max(0.0, p_b - r["P"])
            row["S_acc"], row["S_pay"] = s_acc, s_pay
            if s_acc + s_pay > 0:
                row["account_share_observed"] = s_acc / (s_acc + s_pay)
            row["S_acc_mean"], row["S_acc_lo"], row["S_acc_hi"] = tbharm.summary(sa[u])
            row["S_pay_mean"], row["S_pay_lo"], row["S_pay_hi"] = tbharm.summary(sp[u])
            row.update(classify(sa[u], sp[u]))
            row["status"] = "classified"
        else:
            miss = [s for s in ("A", "P") if r[s] is None]
            row["status"] = "NA: " + ", ".join(miss) + " not available (no class)"
        out.append(row)
    return out
