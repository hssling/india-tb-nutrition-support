"""The relative need weight (analysis plan sections 4.1-4.3).

- w_u, m_u: NFHS-5 items 86 and 87 (Total column), the printed percentage / 100
  (data/extracted/nfhs_bmi.csv). A starred cell is NA.
- Merge (section 4.2): a coarsened unit with member sheets j takes
  w_u = sum_j W_j w_j / sum_j W_j (and the same for m_u), W_j the member's ITR 2023
  Annexure 1.6 notified count (male + female + transgender; a member row with an NA cell
  has weight 0). If every member has weight 0, the unweighted mean of the member sheets
  is used and the flag ``nfhs_merge_unweighted`` is set. A unit with one sheet takes its
  values unchanged.
- f_u = Female / (Male + Female + Transgender), summed over the unit's member rows
  (transgender patients are weighted with men).
- n_u = f_u w_u + (1 - f_u) m_u ("sex_weighted"); sensitivities: w_u ("women"), m_u
  ("men"), (w_u + m_u)/2 ("simple").
- n_bar = sum_u G_u n_u / sum_u G_u over the units with non-NA n_u, G_u the unit's 2022
  Annexure 1.6 notified count; wt_u = n_u / n_bar, so the G-weighted mean of wt_u is 1.
- A unit with f_u, w_u or m_u NA has n_u and wt_u NA under every weighting.

The weight is relative: it says where an unpaid person is more likely to be underweight.
It is not a count of TB patients with undernutrition.
"""
from __future__ import annotations

import csv
from pathlib import Path

from src.extract import crosswalk

ROOT = Path(__file__).resolve().parents[2]
NFHS = ROOT / "data" / "extracted" / "nfhs_bmi.csv"
SEX = ROOT / "data" / "extracted" / "tb_sex_2022.csv"

SEX_WEIGHTED, WOMEN, MEN, SIMPLE = "sex_weighted", "women", "men", "simple"
WEIGHTINGS = (SEX_WEIGHTED, WOMEN, MEN, SIMPLE)


def _load(path: Path) -> list[dict]:
    with open(path, encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def load_nfhs(path: Path = NFHS) -> list[dict]:
    return _load(path)


def load_sex(path: Path = SEX) -> list[dict]:
    return _load(path)


def _int(v) -> int | None:
    return None if v in (None, "") else int(v)


def _counts(row: dict) -> tuple[int | None, int | None, int | None]:
    return _int(row["male"]), _int(row["female"]), _int(row["transgender"])


def state_rows(sex_rows: list[dict]) -> list[dict]:
    """The State/UT rows (the printed India row, flagged ``national_row``, is not used)."""
    return [r for r in sex_rows if r["unit"] and "national_row" not in r["flag"].split(";")]


def member_weight(row: dict) -> int:
    """W_j: male + female + transgender of a member row; 0 when any cell is NA."""
    m, f, t = _counts(row)
    if m is None or f is None or t is None:
        return 0
    return m + f + t


def notified(sex_rows: list[dict]) -> dict[str, int | None]:
    """G_u: the 2022 Annexure 1.6 notified count of each unit, summed over its member
    rows; a member row with an NA cell adds nothing; a unit whose rows are all NA is NA."""
    out: dict[str, int | None] = {u: None for u in crosswalk.UNITS}
    for r in state_rows(sex_rows):
        m, f, t = _counts(r)
        if m is None or f is None or t is None:
            continue
        out[r["unit"]] = (out[r["unit"]] or 0) + m + f + t
    return out


def female_share(sex_rows: list[dict]) -> dict[str, float | None]:
    """f_u = Female / (Male + Female + Transgender), summed over the member rows."""
    fem: dict[str, int] = {}
    tot: dict[str, int] = {}
    for r in state_rows(sex_rows):
        m, f, t = _counts(r)
        if m is None or f is None or t is None:
            continue
        fem[r["unit"]] = fem.get(r["unit"], 0) + f
        tot[r["unit"]] = tot.get(r["unit"], 0) + m + f + t
    return {u: (fem[u] / tot[u] if tot.get(u) else None) for u in crosswalk.UNITS}


def _pct(v: str) -> float | None:
    return None if v in (None, "") else float(v) / 100.0


def merge_nfhs(nfhs_rows: list[dict], sex_rows: list[dict]) -> dict[str, dict]:
    """unit -> {"women": w_u, "men": m_u, "flags": [...], "members": [...]} (section 4.2).

    A member sheet whose cell is NA adds nothing to that item (as a merged count does,
    section 3.5) and the unit is flagged; a unit whose member cells are all NA is NA."""
    W = {r["printed_unit"]: member_weight(r) for r in state_rows(sex_rows)}
    sheets: dict[str, dict[str, dict]] = {}
    for r in nfhs_rows:
        printed = r["unit"]
        unit = crosswalk.coarsen(printed)
        flags = [f for f in r["flag"].split(";") if f]
        mi = [f.split(":", 1)[1] for f in flags if f.startswith("merge_into:")]
        if mi and mi != [unit]:
            raise ValueError(f"NFHS-5 sheet {printed!r}: merge flag {mi} is not {unit!r}")
        if unit != printed and not mi:
            raise ValueError(f"NFHS-5 sheet {printed!r} joins {unit!r} without a merge flag")
        sheets.setdefault(unit, {}).setdefault(printed, {})[r["sex"]] = r
    out: dict[str, dict] = {}
    for unit in [u for u in crosswalk.UNITS if u in sheets]:
        members = sorted(sheets[unit], key=lambda p: (p != unit, p))
        res = {"members": members, "flags": []}
        for sex in ("women", "men"):
            vals = []
            for j in members:
                row = sheets[unit][j][sex]
                for f in row["flag"].split(";"):
                    if f in ("nfhs_small_sample", "nfhs_suppressed"):
                        res["flags"].append(f"{f}:{sex}@{j}")
                v = _pct(row["bmi_below_normal_pct"])
                if v is None:
                    if len(members) > 1:
                        res["flags"].append(f"nfhs_member_na:{sex}@{j}")
                    continue
                vals.append((j, v))
            if not vals:
                res[sex] = None
            elif len(members) == 1:
                res[sex] = vals[0][1]
            else:
                wsum = sum(W.get(j, 0) for j, _ in vals)
                if wsum > 0:
                    res[sex] = sum(W.get(j, 0) * v for j, v in vals) / wsum
                else:
                    res[sex] = sum(v for _, v in vals) / len(vals)
                    if "nfhs_merge_unweighted" not in res["flags"]:
                        res["flags"].append("nfhs_merge_unweighted")
        out[unit] = res
    return out


def n_share(items: dict[str, dict], f: dict[str, float | None],
            weighting: str = SEX_WEIGHTED) -> dict[str, float | None]:
    """n_u under one weighting; NA when f_u, w_u or m_u is NA."""
    if weighting not in WEIGHTINGS:
        raise ValueError(f"unknown weighting {weighting!r}")
    out: dict[str, float | None] = {}
    for u in [u for u in crosswalk.UNITS if u in items]:
        w, m, fu = items[u]["women"], items[u]["men"], f.get(u)
        if w is None or m is None or fu is None:
            out[u] = None
        elif weighting == SEX_WEIGHTED:
            out[u] = fu * w + (1.0 - fu) * m
        elif weighting == WOMEN:
            out[u] = w
        elif weighting == MEN:
            out[u] = m
        else:
            out[u] = (w + m) / 2.0
    return out


def relative(n: dict[str, float | None], G: dict[str, int | None]
             ) -> tuple[dict[str, float | None], float]:
    """(wt_u, n_bar): n_bar the G-weighted mean of n_u over the units with non-NA n_u
    (and G_u), wt_u = n_u / n_bar."""
    use = [u for u in n if n[u] is not None and G.get(u) is not None]
    nbar = sum(G[u] * n[u] for u in use) / sum(G[u] for u in use)
    return {u: (n[u] / nbar if u in use else None) for u in n}, nbar


def weights(nfhs_rows: list[dict], sex_rows: list[dict], notified: dict[str, int | None],
            weighting: str = SEX_WEIGHTED) -> dict[str, float | None]:
    """wt_u under one weighting; ``notified`` is G_u (see notified())."""
    n = n_share(merge_nfhs(nfhs_rows, sex_rows), female_share(sex_rows), weighting)
    return relative(n, notified)[0]
