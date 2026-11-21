"""The full analysis of the registered plan (docs/analysis_plan.md, sections 4-10).

Run from the repository root:  python -I src/run_all.py  [--out DIR]

Writes the outputs of plan section 10.2 to outputs/ (or DIR): chain.csv, need_weight.csv,
shortfall.csv, chain_class.csv, priority.csv, budget.csv, trend.csv, funnel.csv,
headline.csv, spec_curve.csv, spec_grid.csv, leave_one_out.csv, perturbation.csv,
rounding_check.csv, na_cells.csv. Reruns with the same inputs give byte-identical files.
"""
from __future__ import annotations

import argparse
import csv
import math
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if __package__ in (None, ""):
    sys.path.insert(0, str(ROOT))

import numpy as np  # noqa: E402
from tbprio import harm as tbharm  # noqa: E402

from src.extract import crosswalk  # noqa: E402
from src.nutpay import (CHAIN_STREAM, HEADLINE_YEAR, N_DRAWS, SEED, YEARS,  # noqa: E402
                        budget, chain, check_tbprio, funnel, need, perturb, priority,
                        shortfall, table, trend, validate)

OUT = ROOT / "outputs"
EXTRACTED = ROOT / "data" / "extracted"
SEX = need.SEX_WEIGHTED
BENCH_SPECS = {"p75": 75.0, "p50": 50.0, "p90": 90.0}
DERIVED = "derived_from_percent"
COST_NOTE = (budget.NOTE + "; cost_lo and cost_hi: descriptive addition; the plan names "
             "only the interval of U")
OUTCOME_LABEL = {"success": "treatment success", "died": "died",
                 "ltfu": "lost to follow-up"}


def need_spec(w: str) -> str:
    return f"need_weighted_{w}"


def n_required(n: int) -> int:
    """The smallest number of agreeing entries with 5 x agree >= 4 x entries."""
    return math.ceil(4 * n / 5)


def _rows(path: Path) -> list[dict]:
    with open(path, encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


class Analysis:
    def __init__(self):
        self.version = check_tbprio()
        self.npy = chain.load()
        self.chain = chain.compute(self.npy)
        self.by = {(r["unit"], r["year"]): r for r in self.chain}
        if sorted({r["unit"] for r in self.chain}) != sorted(crosswalk.UNITS):
            raise ValueError("the NPY panel does not hold the 33 units")
        nf, sx = need.load_nfhs(), need.load_sex()
        self.items = need.merge_nfhs(nf, sx)
        if sorted(self.items) != sorted(crosswalk.UNITS):
            raise ValueError("NFHS-5 sheets do not cover the 33 units")
        self.f = need.female_share(sx)
        self.G = need.notified(sx)
        self.n = {w: need.n_share(self.items, self.f, w) for w in need.WEIGHTINGS}
        self.wt, self.nbar = {}, {}
        for w in need.WEIGHTINGS:
            self.wt[w], self.nbar[w] = need.relative(self.n[w], self.G)
        self.outcomes = validate.load_outcomes()
        self.sector = validate.load_sector()
        self.share = validate.private_share(self.sector)
        # unpaid-rate draw sets: a fresh rng(20261123) per data year (plan 5.3)
        self.ds = {t: priority.draw_set(self.chain, t, np.random.default_rng(SEED))
                   for t in YEARS}
        self.trend_rows, self.falling = trend.run(self.chain)

    # ---- chain.csv ------------------------------------------------------------------
    def chain_table(self) -> list[dict]:
        out = []
        for r in self.chain:
            out.append({
                "level": "unit", "unit": r["unit"], "year": r["year"],
                "denominator_basis": r["denominator_basis"], "D_denominator": r["D"],
                "B_bank_available": r["B"], "Q_paid_at_least_once": r["Q"],
                "bank_validated": r["Vd"],
                "A": r["A"], "A_lo": r["A_lo"], "A_hi": r["A_hi"],
                "P": r["P"], "P_lo": r["P_lo"], "P_hi": r["P_hi"],
                "C": r["C"], "C_lo": r["C_lo"], "C_hi": r["C_hi"],
                "V": r["V"], "V_lo": r["V_lo"], "V_hi": r["V_hi"],
                "paid_over_validated": r["PV"], "paid_over_validated_lo": r["PV_lo"],
                "paid_over_validated_hi": r["PV_hi"],
                "U": r["U"], "U_acc": r["U_acc"], "U_pay": r["U_pay"],
                "interval": "Jeffreys", "na_steps": r["na_steps"],
                "note": "", "flag": r["flag"], "source_file": r["source_file"],
                "pdf_page": r["pdf_page"], "table_id": r["table_id"]})
        for t in YEARS:
            nat = {x["step"]: x for x in chain.national(self.chain, t)}
            rows = [r for r in self.chain if r["year"] == t]
            row = {"level": "national", "unit": "units with data", "year": t,
                   "denominator_basis": rows[0]["denominator_basis"], "interval": "Wilson"}
            notes = []
            for s in ("A", "P", "C"):
                x = nat[s]
                row.update({s: x["value"], f"{s}_lo": x["lo"], f"{s}_hi": x["hi"]})
                row[f"n_units_{s}"] = x["n_units"]
                if x["units_excluded"]:
                    notes.append(f"{s} excludes {', '.join(x['units_excluded'])}")
            for k in ("U", "U_acc", "U_pay"):
                use = [r for r in rows if r[k] is not None]
                row[k] = sum(r[k] for r in use)
                row[f"n_units_{k}"] = len(use)
                miss = [r["unit"] for r in rows if r[k] is None]
                if miss:
                    notes.append(f"{k} excludes {', '.join(miss)}")
            row["note"] = "; ".join(notes)
            out.append(row)
        return out

    CHAIN_COLS = ["level", "unit", "year", "denominator_basis", "D_denominator",
                  "B_bank_available", "Q_paid_at_least_once", "bank_validated", "A", "A_lo",
                  "A_hi", "P", "P_lo", "P_hi", "C", "C_lo", "C_hi", "V", "V_lo", "V_hi",
                  "paid_over_validated", "paid_over_validated_lo", "paid_over_validated_hi",
                  "U", "U_acc", "U_pay", "interval", "n_units_A", "n_units_P",
                  "n_units_C", "n_units_U", "n_units_U_acc", "n_units_U_pay", "na_steps",
                  "note", "flag", "source_file", "pdf_page", "table_id"]

    # ---- need_weight.csv ------------------------------------------------------------
    def need_table(self) -> list[dict]:
        out = []
        for w in need.WEIGHTINGS:
            for u in crosswalk.UNITS:
                it = self.items[u]
                out.append({"unit": u, "spec": w, "w_u_women": it["women"],
                            "m_u_men": it["men"], "f_u_female_share_2022": self.f[u],
                            "G_u_notified_2022": self.G[u], "n_u": self.n[w][u],
                            "n_bar": self.nbar[w], "wt_u_relative_need_weight": self.wt[w][u],
                            "nfhs_sheets": it["members"], "flag": it["flags"],
                            "note": "relative weight; not a count of TB patients"})
        return out

    # ---- shortfall.csv, chain_class.csv --------------------------------------------
    def shortfalls(self) -> list[dict]:
        out = []
        for t in YEARS:
            for spec, pct in BENCH_SPECS.items():
                out += shortfall.compute(self.chain, t, pct,
                                         np.random.default_rng(list(CHAIN_STREAM)))
        return out

    @staticmethod
    def classes(sf: list[dict]) -> list[dict]:
        return [{"unit": r["unit"], "year": r["year"], "spec": r["spec"], "class": r["class"],
                 "p_zero": r["p_zero"], "p_acc_ge_2_3": r["p_acc_ge_2_3"],
                 "p_pay_ge_2_3": r["p_pay_ge_2_3"], "S_acc": r["S_acc"], "S_pay": r["S_pay"],
                 "status": r["status"]} for r in sf]

    # ---- priority.csv ---------------------------------------------------------------
    def priority_table(self) -> list[dict]:
        out = []
        for t in YEARS:
            ds = self.ds[t]
            out += priority.tiers(ds, None, priority.UNWEIGHTED, self.falling,
                                  list(crosswalk.UNITS))
            for w in need.WEIGHTINGS:
                out += priority.tiers(ds, self.wt[w], need_spec(w), self.falling,
                                      list(crosswalk.UNITS))
        return out

    # ---- budget.csv -----------------------------------------------------------------
    def budget_table(self) -> list[dict]:
        ds = self.ds[HEADLINE_YEAR]
        bench = {s: budget.c_bench(ds.C_hat, p) for s, p in BENCH_SPECS.items()}
        tot = budget.total_draws(ds.U_draws)
        m, lo, hi = tbharm.summary(tot)
        out = []
        main = budget.compute(self.chain, bench, budget.RATE_MAIN, budget.MONTHS_MAIN)
        common = {"year": HEADLINE_YEAR, "units_with_data": len(main["units_with_data"]),
                  "units_excluded": main["units_excluded"], "note": budget.NOTE}
        out.append(common | {"item": "U(2023), people not paid at least once", "spec": "",
                             "count": main["U_total"], "count_draw_mean": m, "count_lo": lo,
                             "count_hi": hi})
        out.append(common | {"item": "main: U(2023) x rate x months", "spec": "main",
                             "rate_per_month": budget.RATE_MAIN,
                             "months": budget.MONTHS_MAIN, "count": main["U_total"],
                             "count_lo": lo, "count_hi": hi, "cost": main["cost"],
                             "cost_lo": lo * budget.RATE_MAIN * budget.MONTHS_MAIN,
                             "cost_hi": hi * budget.RATE_MAIN * budget.MONTHS_MAIN,
                             "note": COST_NOTE})
        for rate in budget.RATES:
            for months in budget.MONTHS:
                b = budget.compute(self.chain, {}, rate, months)
                out.append(common | {"item": "range: U(2023) x rate x months",
                                     "spec": f"rate {rate}, {months} months",
                                     "rate_per_month": rate, "months": months,
                                     "count": b["U_total"], "count_lo": lo, "count_hi": hi,
                                     "cost": b["cost"], "cost_lo": lo * rate * months,
                                     "cost_hi": hi * rate * months, "note": COST_NOTE})
        for spec in BENCH_SPECS:
            sc = main["scenarios"][spec]
            base = common | {"spec": spec, "C_bench": sc["C_bench"],
                             "current_number_paid_at_least_once": sc["current_number_paid"],
                             "rate_per_month": None, "months": None}
            out.append(base | {"item": "benchmark scenario: national number paid at least "
                                       "once if every unit reached C_bench",
                               "count": sc["number_paid"],
                               "cost": sc["cost_number_paid"], "cost_basis": "x Rs 6,000"})
            out.append(base | {"item": "benchmark scenario: increment over the current "
                                       "number paid at least once",
                               "count": sc["increment"], "cost": sc["cost_increment"],
                               "cost_basis": "x Rs 6,000"})
        return out

    BUDGET_COLS = ["item", "spec", "year", "rate_per_month", "months", "count",
                   "count_draw_mean", "count_lo", "count_hi", "cost", "cost_lo", "cost_hi",
                   "cost_basis", "C_bench", "current_number_paid_at_least_once",
                   "units_with_data", "units_excluded", "note"]

    # ---- headline, grids, leave-one-out --------------------------------------------
    def hypotheses(self) -> dict:
        res = {"H1": validate.h1(self.chain, self.n), "H2": validate.h2(self.chain, self.share)}
        for o in validate.OUTCOME_NAMES:
            res[f"H3_{o}"] = validate.h3(self.chain, self.outcomes, self.share, o)
        return res

    @staticmethod
    def headline(res: dict) -> list[dict]:
        out = []
        for h, r in res.items():
            m = r["main"]
            row = {"hypothesis": h, "estimate": m["estimate"], "null": 0.0, "lo": m["lo"],
                   "hi": m["hi"], "label": r["label"], "n_entries": r["n_entries"],
                   "n_agree": r["n_agree"], "n_required": n_required(r["n_entries"]),
                   "main_sign": r["main_sign"]}
            if h == "H1":
                row.update(quantity="Spearman rho, C(2023) and n_u (sex-weighted)",
                           interval_method="Fisher z, variance 1.06/(n - 3)", n=m["n"],
                           note="association across units; not causal")
            elif h == "H2":
                row.update(quantity="Spearman rho, C(2023) and the private-sector share of "
                                    "2023 notifications",
                           interval_method="Fisher z, variance 1.06/(n - 3)", n=m["n"],
                           note="association across units; not causal; C(2023) is on the "
                                "eligible basis and the share on the notified basis")
            else:
                row.update(quantity=f"slope on logit(C), quasi-binomial, "
                                    f"{OUTCOME_LABEL[m['outcome']]} share "
                                    "of the cohort, pooled 2021+2022 with a year term",
                           interval_method="cluster bootstrap over units, 10,000 replicates",
                           n=m["n_units"], n_obs=m["n_obs"], kish_effective_clusters=m["kish"],
                           n_boot=m["n_boot"], n_boot_discarded=m["n_discarded"],
                           phi=m.get("phi"), wald_lo=m.get("wald_lo"), wald_hi=m.get("wald_hi"),
                           note=validate.H3_NOTE + "; secondary; no correction for three "
                                "outcomes")
            out.append(row)
        return out

    HEADLINE_COLS = ["hypothesis", "quantity", "estimate", "null", "lo", "hi",
                     "interval_method", "n", "n_obs", "label", "n_entries", "n_agree",
                     "n_required", "main_sign", "kish_effective_clusters", "n_boot",
                     "n_boot_discarded", "phi", "wald_lo", "wald_hi", "note"]

    @staticmethod
    def spec_curve(res: dict) -> list[dict]:
        out = []
        for h, r in res.items():
            for i, e in enumerate(r["grid"], 1):
                out.append({"hypothesis": h, "entry": i, "main": e["main"],
                            "weighting": e.get("weighting"), "year": e.get("year"),
                            "method": e.get("method",
                                            "quasi-binomial IRLS" if h.startswith("H3") else None),
                            "year_set": e.get("year_set"), "adjustment": e.get("adjustment"),
                            "estimate": e["estimate"], "sign": e["sign"],
                            "agrees_with_main": e["agrees"], "n": e.get("n", e.get("n_units")),
                            "n_obs": e.get("n_obs"), "phi": e.get("phi"),
                            "wald_lo": e.get("wald_lo"), "wald_hi": e.get("wald_hi"),
                            "status": e.get("status", "estimated" if e["estimate"] is not None
                                            else "undefined")})
        return out

    @staticmethod
    def spec_grid(res: dict) -> list[dict]:
        axes = {"H1": "weighting {sex-weighted, women, men, simple} x year {2021, 2022, 2023}",
                "H2": "year {2021, 2022, 2023} x {Spearman, Kendall tau-b}"}
        out = []
        for h, r in res.items():
            m = r["main"]
            excl = (m["lo"] is not None and m["hi"] is not None
                    and ((m["lo"] > 0 and m["hi"] > 0) or (m["lo"] < 0 and m["hi"] < 0)))
            out.append({"hypothesis": h,
                        "grid": axes.get(h, "year set {pooled, 2021, 2022} x adjustment "
                                            "{none, private-sector share}, plus 2022 with "
                                            "previous-year success (alone; with the "
                                            "private-sector share)"),
                        "n_entries": r["n_entries"], "n_agree": r["n_agree"],
                        "n_required": n_required(r["n_entries"]),
                        "share_agree": r["n_agree"] / r["n_entries"],
                        "main_sign": r["main_sign"], "interval_excludes_null": excl,
                        "label": r["label"]})
        return out

    def leave_one_out(self, res: dict) -> list[dict]:
        out = []
        for h, r in res.items():
            out += validate.loo_summary(h, r["loo"])
        t = HEADLINE_YEAR
        main_u = priority.act_now(priority.tiers(self.ds[t], None))
        main_w = priority.act_now(priority.tiers(self.ds[t], self.wt[SEX]))

        def weights_for(omit):
            return need.relative({u: v for u, v in self.n[SEX].items() if u != omit},
                                 self.G)[0]

        rows = priority.leave_one_out(self.chain, t, list(crosswalk.UNITS), weights_for,
                                      main_u, main_w)
        for r in rows:
            out.append({"analysis": r["analysis"] + f", harm {r['harm']}",
                        "omitted": r["omitted"], "estimate": None,
                        "n_changed": r["n_changed"], "changed_units": r["changed_units"],
                        "act_now_without": r["act_now_without"], "summary": ""})
        for harm, main in (("U", main_u), ("U_wt_sex_weighted", main_w)):
            hr = [r for r in rows if r["harm"] == harm]
            mx = max(r["n_changed"] for r in hr)
            top = [r["omitted"] for r in hr if r["n_changed"] == mx]
            out.append({"analysis": f"act-now set {t}, harm {harm}", "omitted": top,
                        "estimate": None, "n_changed": mx, "changed_units": None,
                        "act_now_without": sorted(main),
                        "summary": "most changes (omitted unit); act_now_without lists the "
                                   "main act-now set"})
        return out

    LOO_COLS = ["analysis", "omitted", "estimate", "n_changed", "changed_units",
                "act_now_without", "summary"]

    # ---- rounding_check.csv ---------------------------------------------------------
    @staticmethod
    def rounding_check() -> list[dict]:
        derived = []
        for name in ("npy_panel.csv", "outcomes_panel.csv", "sector_panel.csv",
                     "tb_sex_2022.csv"):
            for r in _rows(EXTRACTED / name):
                if DERIVED in r.get("flag", ""):
                    derived.append(f"{name}: {r.get('unit')} {r.get('measure', '')}")
        if derived:
            raise RuntimeError("counts derived from a printed percentage were found; the "
                               "rounding rerun of plan section 8.9 must be run: "
                               + "; ".join(derived))
        compared = ("every tier (U and U wt_u, all years)", "every class",
                    "every H1, H2 and H3 label", "the falling-coverage flags")
        return [{"check": "rounding check (plan section 8.9)", "compared": c,
                 "derived_counts": "no derived counts", "result": "unchanged",
                 "note": "no count is back-calculated from a percentage, so the rerun is "
                         "unchanged by construction"} for c in compared]

    # ---- na_cells.csv ---------------------------------------------------------------
    def na_cells(self, res: dict, pri: list[dict]) -> list[dict]:
        out = []

        def add(source, unit, year, measure, reason):
            out.append({"source": source, "unit": unit, "year": year, "measure": measure,
                        "reason": reason})

        for r in chain.na_listing(self.npy):
            add("npy_panel.csv (plan 3.6 rule)", r["unit"], r["year"], f"step {r['step']}",
                r["reason"])
        for r in self.chain:
            na = r["na"]
            for k, steps in (("U", ("C",)), ("U_acc", ("A",)), ("U_pay", ("A", "P")),
                             ("shortfalls and class", ("A", "P"))):
                if k in r and r[k] is not None:
                    continue    # the count is valid (U = 0 for D = Q = 0 with C NA)
                why = [f"{s} NA ({na[s]})" for s in steps if s in na]
                if why:
                    add("chain (plan 3.6)", r["unit"], r["year"], k,
                        "NA because " + ", ".join(why))
            if "PV" in na:
                add("chain (plan 3.6, 5.1)", r["unit"], r["year"],
                    "paid at least once / bank details validated (descriptive)",
                    f"NA: {na['PV']}")
        for name, ycol in (("npy_panel.csv", "year"), ("sector_panel.csv", "year"),
                           ("outcomes_panel.csv", "cohort_year")):
            for r in _rows(EXTRACTED / name):
                fl = [f for f in r["flag"].split(";")
                      if f.startswith(("member_missing", "na_printed", "NA:"))]
                if r["value"] == "" or fl:
                    add(name, r["unit"], int(r[ycol]), r["measure"],
                        ("value NA; " if r["value"] == "" else "merged unit with a member "
                         "cell NA (adds nothing); ") + ";".join(fl))
        for u in crosswalk.UNITS:
            for f in self.items[u]["flags"]:
                add("nfhs_bmi.csv (plan 4.1-4.2)", u, None, "w_u/m_u", f)
            if self.n[SEX][u] is None:
                add("need weight (plan 4.3)", u, None, "n_u, wt_u",
                    "f_u, w_u or m_u NA: excluded from need-weighted quantities and H1")
        for t in YEARS:
            ds = self.ds[t]
            if ds.absent:
                add("priority (plan 5.3)", None, t, "tiers", "no usable unit: no tiers")
            if ds.flag:
                add("priority (plan 5.3)", None, t, "unpaid-rate prior", ds.flag)
            for u in ds.excluded:
                add("priority (plan 6)", u, t, "tiers (U and U wt_u)",
                    "not tiered: " + ds.excluded_reason[u])
        for r in pri:
            if r["status"] == "not tiered: wt_u NA":
                add("priority (plan 6)", r["unit"], r["year"], f"tier, {r['spec']}",
                    r["status"])
        for r in [x for x in self.chain if x["year"] == HEADLINE_YEAR and x["U"] is None]:
            add("2023 national totals (plan 3.6, 9)", r["unit"], HEADLINE_YEAR,
                "unpaid count, budget, scenario", "excluded: reported as units with data")
        for r in [x for x in self.chain if x["year"] == HEADLINE_YEAR and x["C"] is None]:
            add("funnel (plan 8.3)", r["unit"], HEADLINE_YEAR, "funnel", "C NA")
        for h in ("H1", "H2"):
            used = set(res[h]["main"]["units"])
            for u in crosswalk.UNITS:
                if u not in used:
                    add(f"{h} (plan 8.1)", u, HEADLINE_YEAR, "main estimate",
                        "excluded: a value is NA")
        for o in validate.OUTCOME_NAMES:
            for u, t, why in res[f"H3_{o}"]["main"]["excluded"]:
                add(f"H3 {o} (plan 8.4)", u, t, "observation", why)
        return out

    # ---- run ------------------------------------------------------------------------
    def run(self, out_dir: Path) -> list[Path]:
        out_dir.mkdir(parents=True, exist_ok=True)
        paths = []
        w = lambda name, rows, cols=None: paths.append(  # noqa: E731
            table.write(out_dir / name, rows, cols))
        w("chain.csv", self.chain_table(), self.CHAIN_COLS)
        w("need_weight.csv", self.need_table())
        sf = self.shortfalls()
        w("shortfall.csv", sf)
        w("chain_class.csv", self.classes(sf))
        pri = self.priority_table()
        w("priority.csv", pri)
        w("budget.csv", self.budget_table(), self.BUDGET_COLS)
        w("trend.csv", self.trend_rows, trend.COLUMNS)
        w("funnel.csv", funnel.compute(self.chain, HEADLINE_YEAR))
        res = self.hypotheses()
        w("headline.csv", self.headline(res), self.HEADLINE_COLS)
        w("spec_curve.csv", self.spec_curve(res))
        w("spec_grid.csv", self.spec_grid(res))
        w("leave_one_out.csv", self.leave_one_out(res), self.LOO_COLS)
        w("perturbation.csv", perturb.run(self.ds[HEADLINE_YEAR], self.n[SEX], self.G))
        w("rounding_check.csv", self.rounding_check())
        w("na_cells.csv", self.na_cells(res, pri))
        self.res = res
        return paths


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Run the registered analysis.")
    ap.add_argument("--out", type=Path, default=OUT, help="output directory")
    args = ap.parse_args(argv)
    a = Analysis()
    for p in a.run(args.out):
        print(f"wrote {p.name}")
    print(f"tbprio {a.version}; seed {SEED}; {N_DRAWS} draws")
    return 0


if __name__ == "__main__":
    sys.exit(main())
