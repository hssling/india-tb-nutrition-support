"""Analysis tests (analysis plan sections 4-10).

The shortfall floor and "no shortfall" class (test_shortfall_floor_zero_and_no_shortfall_class),
the tbprio version and source pin (test_tbprio_pinned_version), the label, class, need-weight, budget and rerun tests, the
NFHS-5 merge of plan section 4.2, the single NA rule of plan section 3.6 (consumed from
src.extract.itr_npy, never re-implemented), and unit tests of the intervals, the IRLS, the
draw streams and the tbprio calls.
"""
import csv
import hashlib
import importlib.metadata
import math
import subprocess
import sys
from pathlib import Path

import numpy as np
import pytest
import tbprio
from scipy.stats import beta as beta_dist
from tbprio import harm as tbharm
from tbprio import shrink

from src.extract import crosswalk, itr_npy
from src.nutpay import (SEED, budget, chain, check_tbprio, funnel, need, perturb, priority,
                        shortfall, trend, validate)

ROOT = Path(__file__).resolve().parents[1]
OUTPUTS = ROOT / "outputs"
EXTRACTED = ROOT / "data" / "extracted"

# SHA-256 of src/tbprio/* at tag v1.0.1 of hssling/india-tb-priority-tool, recorded with
# `git show v1.0.1:src/tbprio/<file> | sha256sum` in the local checkout (22 Nov 2026).
TBPRIO_V101 = {
    "__init__.py": "4067d1c97393be078a199753d5c9402a56337eb5b07cfe88273448d15f871d22",
    "__main__.py": "4fdbd07dc7384b8ada292817a8b9f1692a381c539579db5fb3fb544eb966493f",
    "district.py": "815e10f7ab9529b93a1a3a574269bf84a5db1623438bbd90a5dcbfaffd429f93",
    "harm.py": "3e60565c319f7b38553d39bb25055cefa57ddfdf9348197879ea33f8c637f0a1",
    "panel.py": "235d992b123e8ea50eedeba13346d6c44bca6104ee130a940154dad079b17d84",
    "priority.py": "f5557a434394729ad748bb0fa5b25a9fe01e052cb0df6d4cc5f4e8318162f116",
    "report.py": "f1ff4cdf80a0593e055494ecdd1b1363a5ba6b7923bc815d21d49738773396be",
    "schema.py": "39688c1cb76ec47cdac6a745074c756ebdedff74353f13bbbf860d28acd13df8",
    "shrink.py": "b95859662e7855020319cfad398b97f32d38c5c33d0b4243ceeff75f5e5c4f4b",
    "state.py": "1b7ec61f514ebb518841bf7c18d5ef3479516ae8d3785ee7ab1584c48fad5c57",
    "table.py": "0a99d43157a84186b76ece3e12272e723886a41bc20b6442ea533ef85570b97c",
    "trend.py": "5fc582f329ac11f066419f162da3e5eb432e3319b042e548cbc6bede962870a8",
    "validate.py": "3f35042dbad52cf2996495f68e54a838535def51be4150276a4a0af37026bef0",
}


def _read(name: str) -> list[dict]:
    with open(EXTRACTED / name, encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def npy_rows(cells: dict) -> list[dict]:
    """Rows in the npy_panel.csv format from {(unit, year): (D, B, Q[, validated])};
    None is an empty (NA) cell."""
    out = []
    for (unit, year), vals in sorted(cells.items()):
        names = ["denominator", "bank_available", "paid"]
        if len(vals) == 4:
            names = ["denominator", "bank_available", "paid", "bank_validated"]
        for m, v in zip(names, vals):
            out.append({"unit": unit, "year": str(year), "measure": m,
                        "value": "" if v is None else str(v),
                        "denominator_basis": "eligible" if year == 2023 else "notified",
                        "source_file": "synthetic.pdf", "pdf_page": "1",
                        "table_id": "synthetic", "flag": ""})
    return out


UNITS10 = [f"Unit {c}" for c in "ABCDEFGHIJ"]


# ---- tbprio pinned to v1.0.1 ----------------------------------------------------------

def test_tbprio_pinned_version():
    assert importlib.metadata.version("tbprio") == "1.0.1"
    assert check_tbprio() == "1.0.1"
    src = Path(tbprio.__file__).resolve().parent
    files = sorted(p.name for p in src.glob("*.py"))
    assert files == sorted(TBPRIO_V101)
    for name, digest in TBPRIO_V101.items():
        assert hashlib.sha256((src / name).read_bytes()).hexdigest() == digest, name


def test_check_tbprio_stops_on_a_changed_file(monkeypatch):
    import src.nutpay as nutpay
    bad = dict(nutpay.TBPRIO_V101)
    bad["harm.py"] = "0" * 64
    monkeypatch.setattr(nutpay, "TBPRIO_V101", bad)
    with pytest.raises(RuntimeError, match="harm.py"):
        nutpay.check_tbprio()


# ---- a unit above the benchmark on both steps -----------------------------------------

def _floor_rows():
    cells = {}
    for i, u in enumerate(UNITS10):
        if i == 0:
            cells[(u, 2023)] = (20000, 19990, 19985)        # A = 0.9995, P = 0.99975
        else:
            d = 1000 + 100 * i
            b = int(d * (0.78 + 0.01 * i))
            cells[(u, 2023)] = (d, b, int(b * (0.80 + 0.01 * i)))
    return chain.compute(npy_rows(cells))


def test_shortfall_floor_zero_and_no_shortfall_class():
    rows = _floor_rows()
    for pct in shortfall.PCTS:
        out = shortfall.compute(rows, 2023, pct, np.random.default_rng([SEED, 1]))
        top = next(r for r in out if r["unit"] == UNITS10[0])
        assert top["S_acc"] == 0.0 and top["S_pay"] == 0.0
        assert top["class"] == "no shortfall"
        for r in out:
            assert r["S_acc"] >= 0.0 and r["S_pay"] >= 0.0
            assert r["S_acc_lo"] >= 0.0 and r["S_pay_lo"] >= 0.0
    # per draw: never negative
    cd = shortfall.draws(rows, 2023, np.random.default_rng([SEED, 1]))
    sa, sp = shortfall.shortfall_draws(cd, rows, 2023, 75.0)
    for u in sa:
        assert np.all(sa[u] >= 0.0) and np.all(sp[u] >= 0.0), u
    # budget: the unit above the benchmark adds 0 to the scenario increment
    c_top = next(r for r in rows if r["unit"] == UNITS10[0])["C"]
    res = budget.compute(rows, {"p75": c_top - 0.05}, 1000, 6)
    assert res["scenarios"]["p75"]["increment_by_unit"][UNITS10[0]] == 0.0
    assert all(v >= 0.0 for v in res["scenarios"]["p75"]["increment_by_unit"].values())


# ---- label (plan section 8.6) ---------------------------------------------------------

def test_label_rule():
    S, N = "supported", "not established"
    # H1: 12 entries; 10 agree is enough, 9 is not
    assert validate.label(0.5, (0.2, 0.7), [1] * 10 + [-1, 0]) == S
    assert validate.label(0.5, (0.2, 0.7), [1] * 9 + [-1, 0, None]) == N
    # H2: 5 of 6; H3: 7 of 8
    assert validate.label(-0.4, (-0.6, -0.1), [-1] * 5 + [1]) == S
    assert validate.label(-0.4, (-0.6, -0.1), [-1] * 4 + [1, 1]) == N
    assert validate.label(0.1, (0.01, 0.2), [1] * 7 + [None]) == S
    assert validate.label(0.1, (0.01, 0.2), [1] * 6 + [None, 0]) == N
    # the interval must exclude the null strictly
    assert validate.label(0.5, (0.0, 0.7), [1] * 12) == N
    assert validate.label(0.5, (-0.1, 0.7), [1] * 12) == N
    assert validate.label(0.5, (None, None), [1] * 12) == N
    # an undefined main estimate is never supported
    assert validate.label(None, (0.2, 0.7), [1] * 12) == N
    # 0 or undefined entries do not agree
    assert validate.label(0.5, (0.2, 0.7), [1] * 9 + [0, 0, 0]) == N


# ---- class rule (plan section 5.4) ----------------------------------------------------

def test_class_rule_two_thirds():
    n = 10_000
    # share exactly 2/3 counts as account-led (>= 2/3)
    c = shortfall.classify(np.full(n, 2.0), np.full(n, 1.0))
    assert c["class"] == "account-led"
    assert c["p_acc_ge_2_3"] == 1.0
    # just below 2/3 is not
    c = shortfall.classify(np.full(n, 1.99), np.full(n, 1.0))
    assert c["class"] == "mixed"
    # payment share exactly 2/3
    c = shortfall.classify(np.full(n, 1.0), np.full(n, 2.0))
    assert c["class"] == "payment-led"
    # the denominator is all 10,000 draws: 9,400 account-led draws and 600 with no
    # shortfall give 0.94 < 0.95 (mixed), although every draw with a share is account-led
    sa = np.r_[np.full(9400, 5.0), np.zeros(600)]
    sp = np.r_[np.zeros(9400), np.zeros(600)]
    c = shortfall.classify(sa, sp)
    assert c["p_zero"] == 0.06 and c["p_acc_ge_2_3"] == 0.94
    assert c["class"] == "mixed"
    sa = np.r_[np.full(9500, 5.0), np.zeros(500)]
    assert shortfall.classify(sa, np.zeros(n))["class"] == "account-led"
    # "no shortfall" needs more than 50% of draws with S_acc + S_pay = 0, checked first
    sa = np.r_[np.full(5000, 5.0), np.zeros(5000)]
    assert shortfall.classify(sa, np.zeros(n))["class"] == "mixed"
    sa = np.r_[np.full(4999, 5.0), np.zeros(5001)]
    assert shortfall.classify(sa, np.zeros(n))["class"] == "no shortfall"


# ---- need weight (plan sections 4.2-4.3) ----------------------------------------------

def test_need_weight_mean_one():
    nf, sx = _read("nfhs_bmi.csv"), _read("tb_sex_2022.csv")
    G = need.notified(sx)
    for w in need.WEIGHTINGS:
        wt = need.weights(nf, sx, G, w)
        units = [u for u in crosswalk.UNITS if wt[u] is not None]
        assert len(units) == 33
        mean = sum(G[u] * wt[u] for u in units) / sum(G[u] for u in units)
        assert mean == pytest.approx(1.0, abs=1e-12)
    # synthetic: two units
    n = {"X": 0.2, "Y": 0.1, "Z": None}
    G = {"X": 100, "Y": 300, "Z": 50}
    wt, nbar = need.relative(n, G)
    assert nbar == pytest.approx((100 * 0.2 + 300 * 0.1) / 400)
    assert wt["Z"] is None
    assert (100 * wt["X"] + 300 * wt["Y"]) / 400 == pytest.approx(1.0)


def _nfhs(unit, w, m):
    flag = "" if crosswalk.coarsen(unit) == unit else f"merge_into:{crosswalk.coarsen(unit)}"
    return [{"unit": unit, "sex": s, "bmi_below_normal_pct": v, "source_file": "f.pdf",
             "pdf_page": "1", "flag": flag} for s, v in (("women", w), ("men", m))]


def _sex(printed, unit, m, f, t):
    return {"printed_name": printed, "printed_unit": printed, "unit": unit, "male": m,
            "female": f, "transgender": t, "source_file": "f.pdf", "pdf_page": "1",
            "table_id": "Annexure 1.6", "flag": ""}


def test_nfhs_merge_weighted_by_notified_counts():
    nf = _nfhs("Kerala", "20.0", "10.0") + _nfhs("Lakshadweep", "40.0", "30.0")
    sx = [_sex("Kerala", "Kerala", "200", "100", "0"),
          _sex("Lakshadweep", "Kerala", "60", "39", "1")]
    items = need.merge_nfhs(nf, sx)
    # W = 300 and 100
    assert items["Kerala"]["women"] == pytest.approx((300 * 0.20 + 100 * 0.40) / 400)
    assert items["Kerala"]["men"] == pytest.approx((300 * 0.10 + 100 * 0.30) / 400)
    assert "nfhs_merge_unweighted" not in items["Kerala"]["flags"]
    # a member with an NA cell has weight 0
    sx2 = [_sex("Kerala", "Kerala", "200", "100", "0"),
           _sex("Lakshadweep", "Kerala", "", "39", "1")]
    items = need.merge_nfhs(nf, sx2)
    assert items["Kerala"]["women"] == pytest.approx(0.20)
    # every member weight 0: the unweighted mean, flagged
    sx3 = [_sex("Kerala", "Kerala", "", "100", "0"),
           _sex("Lakshadweep", "Kerala", "60", "", "1")]
    items = need.merge_nfhs(nf, sx3)
    assert items["Kerala"]["women"] == pytest.approx(0.30)
    assert items["Kerala"]["men"] == pytest.approx(0.20)
    assert "nfhs_merge_unweighted" in items["Kerala"]["flags"]
    # a one-sheet unit keeps its value unchanged
    items = need.merge_nfhs(_nfhs("Goa", "12.5", "7.5"), [_sex("Goa", "Goa", "1", "1", "0")])
    assert items["Goa"]["women"] == 0.125 and items["Goa"]["men"] == 0.075


def test_nfhs_merge_on_the_extracted_files():
    nf, sx = _read("nfhs_bmi.csv"), _read("tb_sex_2022.csv")
    items = need.merge_nfhs(nf, sx)
    assert sorted(items) == sorted(crosswalk.UNITS)
    pct = {(r["unit"], r["sex"]): float(r["bmi_below_normal_pct"]) / 100 for r in nf}
    W = {r["printed_unit"]: int(r["male"]) + int(r["female"]) + int(r["transgender"])
         for r in sx}
    for unit, member in (("Gujarat", "Dadra and Nagar Haveli and Daman and Diu"),
                         ("Kerala", "Lakshadweep"), ("Jammu and Kashmir", "Ladakh")):
        for s in ("women", "men"):
            want = ((W[unit] * pct[(unit, s)] + W[member] * pct[(member, s)])
                    / (W[unit] + W[member]))
            assert items[unit][s] == pytest.approx(want, abs=1e-15)
    assert items["Goa"]["women"] == pct[("Goa", "women")]
    # f_u: female over all three, transgender with men
    f = need.female_share(sx)
    assert f["Kerala"] == pytest.approx((8289 + 9) / (15235 + 8289 + 5 + 13 + 9 + 0))


# ---- the single NA rule (plan section 3.6) --------------------------------------------

def test_chain_consumes_the_extraction_na_rule(monkeypatch):
    calls = []
    real = itr_npy.chain_na

    def spy(*a, **k):
        calls.append(a)
        out = real(*a, **k)
        if a[:3] == (1000, 900, 700):
            out = dict(out, A="sentinel_reason")
        return out

    monkeypatch.setattr(itr_npy, "chain_na", spy)
    rows = chain.compute(npy_rows({("Goa", 2022): (1000, 900, 700)}))
    assert calls, "chain.compute must call itr_npy.chain_na"
    r = rows[0]
    assert r["A"] is None and r["U_acc"] is None and r["U_pay"] is None
    assert r["na"]["A"] == "sentinel_reason"
    assert r["C"] == 0.7 and r["U"] == 300
    # chain.py has no rule of its own: with chain_na silenced, an impossible chain
    # (bank details above the denominator) is not set to NA by anything else
    monkeypatch.setattr(itr_npy, "chain_na", lambda *a, **k: {})
    r = chain.compute(npy_rows({("Goa", 2021): (1000, 1020, 700)}))[0]
    assert r["A"] == 1.02 and r["U_acc"] == -20


def test_chain_validity_rules():
    rows = chain.compute(npy_rows({
        ("A1", 2021): (1000, 1020, 700),    # B > D: A, U_acc, U_pay NA; C kept
        ("A2", 2021): (1000, 600, 700),     # Q > B: P, U_pay NA; U_acc kept
        ("A3", 2021): (1000, 900, 1100),    # Q > D: C and U NA (and P)
        ("A4", 2023): (None, None, 500, None),  # dashes
        ("A5", 2023): (1000, 900, 800, 750),    # paid above validated
    }))
    r = {x["unit"]: x for x in rows}
    assert r["A1"]["A"] is None and r["A1"]["U_acc"] is None and r["A1"]["U_pay"] is None
    assert r["A1"]["C"] == 0.7 and r["A1"]["U"] == 300 and r["A1"]["P"] == 700 / 1020
    assert r["A2"]["P"] is None and r["A2"]["U_pay"] is None and r["A2"]["U_acc"] == 400
    assert r["A3"]["C"] is None and r["A3"]["U"] is None
    assert r["A4"]["U"] is None and r["A4"]["A"] is None
    assert r["A5"]["V"] == 750 / 900 and r["A5"]["PV"] is None
    assert r["A5"]["na"]["PV"] == "paid_exceeds_bank_validated"
    # U = U_acc + U_pay when both are valid
    ok = chain.compute(npy_rows({("A6", 2022): (1000, 900, 700)}))[0]
    assert ok["U"] == ok["U_acc"] + ok["U_pay"] == 300


def test_zero_denominator_keeps_u_when_q_not_above_d():
    # plan 3.6: a unit with the chain NA still enters the unpaid count if Q <= D
    rows = chain.compute(npy_rows({
        ("Goa", 2023): (0, 0, 0),           # D = Q = 0: C NA, U = 0
        ("Bihar", 2023): (0, 0, 5),         # D = 0 < Q: U NA
        ("Assam", 2023): (1000, 800, 600),
        ("Delhi", 2023): (2000, 1900, 1500),
    }))
    r = {x["unit"]: x for x in rows}
    assert r["Goa"]["C"] is None and r["Goa"]["U"] == 0
    assert r["Bihar"]["C"] is None and r["Bihar"]["U"] is None
    res = budget.compute(rows, {"p75": 0.9}, 1000, 6)
    assert res["U_total"] == 400 + 500
    assert res["units_with_data"] == ["Assam", "Delhi", "Goa"]
    assert res["units_excluded"] == ["Bihar"]
    assert res["scenarios"]["p75"]["number_paid"] == pytest.approx(900 + 1800)
    # the D = 0 unit has no rate: it is left out of the draws and not tiered
    ds = priority.draw_set(rows, 2023, np.random.default_rng(SEED))
    assert ds.units == ["Assam", "Delhi"]
    assert ds.excluded_reason == {"Bihar": "U NA", "Goa": "D = 0 (U = 0; rate undefined)"}
    t = {x["unit"]: x for x in priority.tiers(ds, None, all_units=["Assam", "Delhi", "Goa"])}
    assert t["Goa"]["status"] == "not tiered: D = 0 (U = 0; rate undefined)"


def test_na_cells_do_not_list_u_na_for_a_zero_zero_unit(monkeypatch):
    """A D = Q = 0 unit has C NA but U = 0: na_cells.csv lists a U-NA line only where U is
    None (a unit whose D is missing keeps its line)."""
    sys.path.insert(0, str(ROOT))
    import src.run_all as run_all

    rows = chain.load()
    for r in rows:      # Goa 2022: D = B = Q = 0
        if r["unit"] == "Goa" and r["year"] == "2022":
            r["value"] = "0"
    monkeypatch.setattr(chain, "load", lambda *a, **k: rows)
    a = run_all.Analysis()
    goa = next(r for r in a.chain if r["unit"] == "Goa" and r["year"] == 2022)
    assert goa["C"] is None and goa["U"] == 0
    res = {"H1": {"main": {"units": []}}, "H2": {"main": {"units": []}}}
    res.update({f"H3_{o}": {"main": {"excluded": []}} for o in validate.OUTCOME_NAMES})
    out = a.na_cells(res, [])
    mine = [r for r in out if r["unit"] == "Goa" and r["year"] == 2022 and r["measure"] == "U"]
    assert mine == []
    kar = [r for r in out if r["unit"] == "Karnataka" and r["year"] == 2023
           and r["measure"] == "U"]
    assert len(kar) == 1 and kar[0]["reason"].startswith("NA because C NA")


def test_nfhs_merge_raises_on_an_unmatched_sheet():
    nf = _nfhs("Kerala", "20.0", "10.0") + _nfhs("Lakshadweep", "40.0", "30.0")
    sx = [_sex("Kerala", "Kerala", "200", "100", "0")]   # no Lakshadweep row
    with pytest.raises(KeyError, match="Lakshadweep"):
        need.merge_nfhs(nf, sx)


def test_chain_on_the_extracted_panel():
    rows = chain.compute(chain.load())
    assert len(rows) == 99
    by = {(r["unit"], r["year"]): r for r in rows}
    hp = by[("Himachal Pradesh", 2021)]
    assert hp["A"] is None and hp["U_acc"] is None and hp["C"] is not None
    ka = by[("Karnataka", 2023)]
    assert ka["U"] is None and ka["C"] is None
    # the NA listing is the extraction's own
    assert chain.na_listing(chain.load()) == itr_npy.na_cells(chain.load())


def test_jeffreys_and_wilson():
    lo, hi = chain.jeffreys(30, 100)
    assert lo == pytest.approx(beta_dist.ppf(0.025, 30.5, 70.5))
    assert hi == pytest.approx(beta_dist.ppf(0.975, 30.5, 70.5))
    lo, hi = chain.wilson(30, 100)
    z = 1.96
    c = (30 + z * z / 2) / (100 + z * z)
    h = z * math.sqrt(30 * 70 / 100 + z * z / 4) / (100 + z * z)
    assert (lo, hi) == (pytest.approx(c - h), pytest.approx(c + h))


# ---- draws --------------------------------------------------------------------------

def _draw_rows():
    cells = {}
    for i, u in enumerate(UNITS10):
        d = 2000 + 300 * i
        b = int(d * (0.70 + 0.02 * i))
        cells[(u, 2023)] = (d, b, int(b * (0.60 + 0.03 * i)))
    return chain.compute(npy_rows(cells))


def test_unpaid_draws_are_tbprio_rate_draws():
    rows = _draw_rows()
    ds = priority.draw_set(rows, 2023, np.random.default_rng(SEED))
    tb_rows = [{"unit": r["unit"], "year": 2023, "step": "unpaid", "numerator": r["U"],
                "denominator": r["D"], "na": False} for r in rows]
    sy = tbharm.estimate(tb_rows, "unpaid", 2023, "p75", True, np.random.default_rng(SEED))
    for u in UNITS10:
        d = next(r["D"] for r in rows if r["unit"] == u)
        assert np.array_equal(ds.U_draws[u], d * sy.rate_draws[u])
        assert ds.C_hat[u] == 1.0 - sy.post_mean[u]
    assert ds.flag == ""


def test_unpaid_draws_fallback_and_no_harm():
    one = chain.compute(npy_rows({("Goa", 2023): (1000, 900, 700)}))
    ds = priority.draw_set(one, 2023, np.random.default_rng(SEED))
    assert ds.flag == "prior_fallback_jeffreys"
    assert (ds.alpha, ds.beta) == shrink.JEFFREYS_BINOMIAL
    none = chain.compute(npy_rows({("Goa", 2023): (1000, 1000, 1000),
                                   ("Bihar", 2023): (500, 500, 500)}))
    ds = priority.draw_set(none, 2023, np.random.default_rng(SEED))
    assert ds.no_harm and all(np.all(v == 0) for v in ds.U_draws.values())
    empty = chain.compute(npy_rows({("Goa", 2023): (None, 900, 700)}))
    ds = priority.draw_set(empty, 2023, np.random.default_rng(SEED))
    assert ds.absent and ds.units == []


def test_chain_stream_order():
    rows = _draw_rows()
    cd = shortfall.draws(rows, 2023, np.random.default_rng([SEED, 1]))
    rng = np.random.default_rng([SEED, 1])
    for u in UNITS10:   # alphabetical; a then p for each unit
        r = next(x for x in rows if x["unit"] == u)
        a = rng.beta(cd.alpha1 + r["B"], cd.beta1 + r["D"] - r["B"], size=10_000)
        p = rng.beta(cd.alpha2 + r["Q"], cd.beta2 + r["B"] - r["Q"], size=10_000)
        assert np.array_equal(cd.a[u], a) and np.array_equal(cd.p[u], p)
    a1, b1 = shrink.beta_binomial(np.array([r["B"] for r in rows], float),
                                  np.array([r["D"] for r in rows], float))
    assert (cd.alpha1, cd.beta1) == (a1, b1)


def test_tiers_use_tbprio_p_topk():
    rows = _draw_rows()
    out = priority.run(rows, None, 2023, np.random.default_rng(SEED))
    assert {r["tier"] for r in out} <= {"act now", "probable priority", "uncertain",
                                        "lower priority"}
    wt = {u: 1.0 + 0.1 * i for i, u in enumerate(UNITS10)}
    outw = priority.run(rows, wt, 2023, np.random.default_rng(SEED))
    ds = priority.draw_set(rows, 2023, np.random.default_rng(SEED))
    p = tbprio.priority.p_topk({u: ds.U_draws[u] * wt[u] for u in UNITS10}, 5)
    for r in outw:
        assert r["p_top5"] == p[r["unit"]]
        assert r["tier"] == tbprio.priority.tier(p[r["unit"]], False)


# ---- budget (plan section 9) ----------------------------------------------------------

def test_budget_arithmetic():
    rows = chain.compute(npy_rows({
        ("Goa", 2023): (1000, 800, 600, 700),
        ("Bihar", 2023): (2000, 1800, 1500, 1700),
        ("Karnataka", 2023): (None, None, 500, None),
    }))
    res = budget.compute(rows, {"p75": 0.7}, 1000, 6)
    assert res["U_total"] == 900
    assert res["units_with_data"] == ["Bihar", "Goa"]
    assert res["units_excluded"] == ["Karnataka"]
    assert res["cost"] == 900 * 1000 * 6
    assert budget.compute(rows, {}, 500, 8)["cost"] == 900 * 500 * 8 == 3_600_000
    sc = res["scenarios"]["p75"]
    assert sc["number_paid"] == pytest.approx(1000 * 0.7 + 2000 * 0.75)
    assert sc["increment"] == pytest.approx(1000 * 0.1)
    assert sc["cost_number_paid"] == pytest.approx(2200 * 6000)
    assert sc["cost_increment"] == pytest.approx(100 * 6000)
    assert sc["current_number_paid"] == 2100


# ---- trend (plan section 7) -----------------------------------------------------------

def test_newcombe_difference():
    x1, n1, x2, n2 = 600, 1000, 550, 1000
    d, lo, hi = trend.newcombe(x1, n1, x2, n2)
    l1, u1 = chain.wilson(x1, n1)
    l2, u2 = chain.wilson(x2, n2)
    c1, c2 = 0.6, 0.55
    assert d == pytest.approx(-0.05)
    assert lo == pytest.approx(d - math.sqrt((c2 - l2) ** 2 + (u1 - c1) ** 2))
    assert hi == pytest.approx(d + math.sqrt((u2 - c2) ** 2 + (c1 - l1) ** 2))


def test_saturated_sensitivity():
    b, se, lo, hi = trend.saturated(600, 1000, 550, 1000)
    L = lambda q, d: math.log((q + 0.5) / (d - q + 0.5))   # noqa: E731
    V = lambda q, d: 1 / (q + 0.5) + 1 / (d - q + 0.5)     # noqa: E731
    assert b == pytest.approx(L(550, 1000) - L(600, 1000))
    assert se == pytest.approx(math.sqrt(V(600, 1000) + V(550, 1000)))
    assert hi == pytest.approx(b + 1.96 * se)


# ---- H3 IRLS (plan section 8.4) -------------------------------------------------------

def test_irls_two_group_logit():
    # two groups: the slope on a 0/1 covariate is the log odds ratio
    X = np.array([[1.0, 0.0], [1.0, 1.0]])
    y = np.array([0.2, 0.5])
    a = np.array([100.0, 200.0])
    f = validate.irls(X, y, a)
    assert f.b1 == pytest.approx(math.log(1.0) - math.log(0.25), abs=1e-9)
    with pytest.raises(validate.Undefined):
        validate.irls(np.array([[1.0, 1.0], [1.0, 1.0]]), y, a)


def test_kish():
    assert validate.kish([np.array([10.0, 10.0]), np.array([20.0])]) == pytest.approx(2.0)
    assert validate.kish([np.array([10.0]), np.array([30.0])]) == pytest.approx(1.6)


def test_spearman_fisher_from_tbprio():
    x = [1, 2, 3, 4, 5, 6, 7]
    y = [2, 1, 4, 3, 7, 5, 6]
    e = validate.correlation(x, y, "spearman")
    assert e == tbprio.validate.spearman(x, y)
    from scipy.stats import kendalltau
    assert validate.correlation(x, y, "kendall") == kendalltau(x, y).statistic


# ---- funnel and perturbation ----------------------------------------------------------

def test_funnel_limits():
    rows = _draw_rows()
    out = funnel.compute(rows, 2023)
    from tbprio import district
    z = [r["z"] for r in out]
    phi = district.winsorised_phi(z)
    assert out[0]["phi_f"] == phi
    assert out[0]["upper_998"] == pytest.approx(3.09 * district.widen(phi))
    for r in out:
        assert (r["flag"] != "") == (r["z"] < r["lower_998"] or r["z"] > r["upper_998"])


def test_perturbation_draws_and_shares():
    rows = _draw_rows()
    ds = priority.draw_set(rows, 2023, np.random.default_rng(SEED))
    n = {u: 0.1 + 0.01 * i for i, u in enumerate(UNITS10)}
    G = {u: 1000 for u in UNITS10}
    out = perturb.run(ds, n, G, n_rep=20)
    assert [r["unit"] for r in out] == UNITS10
    assert all(0.0 <= r["share_unchanged"] <= 1.0 for r in out)
    mult = np.random.default_rng(SEED).uniform(0.8, 1.2, size=(20, 10))
    assert np.array_equal(perturb.multipliers(10, 20), mult)


# ---- the outputs ----------------------------------------------------------------------

def test_outputs_have_no_causal_or_rank_wording():
    banned = ("effect of", "improves", "reduces", "leads to", "rank", "undernourished",
              "fully paid", "impact")
    for p in sorted(OUTPUTS.glob("*.csv")):
        text = p.read_text(encoding="utf-8").lower()
        for b in banned:
            assert b not in text, (p.name, b)


def test_outputs_byte_identical_on_rerun(tmp_path):
    r = subprocess.run([sys.executable, "-I", str(ROOT / "src" / "run_all.py"), "--out",
                        str(tmp_path)], cwd=ROOT, capture_output=True, text=True,
                       timeout=3600)
    assert r.returncode == 0, r.stderr
    committed = sorted(p.name for p in OUTPUTS.glob("*.csv"))
    rerun = sorted(p.name for p in tmp_path.glob("*.csv"))
    assert committed == rerun
    for name in committed:
        assert (OUTPUTS / name).read_bytes() == (tmp_path / name).read_bytes(), name
