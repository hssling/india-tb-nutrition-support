"""Perturbation of the need weight (analysis plan section 8.7).

A fresh numpy.random.default_rng(20261123); the multipliers in one call,
rng.uniform(0.8, 1.2, size=(1000, M)), M the number of units with non-NA n_u in
alphabetical order (column j is the j-th unit). In each replicate every unit's n_u is
multiplied by its multiplier, n_bar and wt_u are recomputed by the rule of section 4.3,
and the need-weighted P(top-5) and tier of the year are recomputed on the existing draws.
For each unit: the share of replicates in which its need-weighted tier equals its main
need-weighted tier.
"""
from __future__ import annotations

import numpy as np
from tbprio import priority as tbp

from . import SEED
from .need import relative
from .priority import DrawSet, p_top5

N_REP = 1000
LO, HI = 0.8, 1.2


def multipliers(m: int, n_rep: int = N_REP) -> np.ndarray:
    return np.random.default_rng(SEED).uniform(LO, HI, size=(n_rep, m))


def run(ds: DrawSet, n: dict[str, float | None], G: dict[str, int | None],
        n_rep: int = N_REP) -> list[dict]:
    units = [u for u in sorted(n) if n[u] is not None and G.get(u) is not None]
    mult = multipliers(len(units), n_rep)
    wt0, _ = relative(n, G)
    p0 = p_top5(ds, wt0)
    main = {u: tbp.tier(p, False) for u, p in p0.items()}
    same = {u: 0 for u in main}
    for i in range(n_rep):
        ni = {u: n[u] * float(mult[i, j]) for j, u in enumerate(units)}
        wt, _ = relative(ni, G)
        p = p_top5(ds, wt)
        for u in main:
            if tbp.tier(p[u], False) == main[u]:
                same[u] += 1
    out = []
    for u in units:
        row = {"unit": u, "year": ds.year, "spec": "need_weighted_sex_weighted",
               "main_tier": main.get(u), "main_p_top5": p0.get(u), "n_replicates": n_rep,
               "n_unchanged": same.get(u), "share_unchanged": None, "status": ""}
        if u in main:
            row["share_unchanged"] = same[u] / n_rep
            row["status"] = "tiered"
        else:
            row["status"] = "not tiered: U NA"
        out.append(row)
    return out
