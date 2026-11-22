# Adapted from hssling/india-tb-diabetes-gap v1.0.0 (MIT), verification/check_manuscript_numbers.py
# (itself adapted from hssling/india-tb-priority-tool and hssling/india-tb-acf-campaign); modified:
# the catalogue of this paper (the payment chain, the unpaid counts, classes and tiers, the trend,
# the funnel, H1-H3, the leave-one-out and perturbation results and the budget from outputs/;
# registration and plan constants from docs/), the Transactions of The Royal Society of Tropical
# Medicine and Hygiene format (a structured abstract of at most 200 words with Background, Methods,
# Results and Conclusions; at most six alphabetical keywords; a main text of at most 3,500 words;
# at most 30 Oxford-style superscript references; at most five display items; figure legends with
# alt text) and this paper's wording rules ("paid at least once"; tiers, not ranks; a relative need
# weight; H3 an ecological association; no causal language).
"""Check every number in the manuscript against the committed outputs.

Run as: python -I verification/check_manuscript_numbers.py [--manuscript-dir DIR] [--regenerate]

The manuscript folder (default manuscript/; git-ignored, kept private, not in this repository)
holds manuscript.md (title, abstract, text, end sections, references and figure legends),
title_page_src.md, cover_letter.md, section_phrases.json, number_skeleton.json and exhibits/. A
relative DIR is taken from the repository root. When the folder or its manuscript.md is absent
this prints "SKIPPED: ..." and exits 0 (a fresh clone); check_all then counts the step as
skipped. If manuscript.md is present without section_phrases.json (or the reverse) the check
FAILS.

Checks (each section's text with its whitespace collapsed; the References are excluded from 1-3):

1. Section phrases. section_phrases.json lists, for each section ("Title", "Abstract", the "## "
   headings), phrases with {label} placeholders. Each label is a catalogue value (catalogue():
   from outputs/, docs/registration_event.json and the registered plan, formatted by
   exhibits/formats.py). Every filled phrase must occur whole in its own section.
2. Every number is accounted for: by a phrase placeholder or a FIXED pattern (exhibit names,
   hypothesis names, years, catalogue dates, superscript citations, plan sections). A token with
   no label is UNACCOUNTED.
3. The golden skeleton (number_skeleton.json): each section's ordered tokens and labels of the
   reviewed text. Regenerate only after review: ... --regenerate
4. Claims stated in words (claims()), re-tested on the outputs.
5. Exhibits: Table 1 and Figures 1-4 cited in order, at most five display items, a legend with
   an "Alt text:" line for each figure and at most 200 words in each legend; Tables S1-S14 exist
   and are first cited in order. exhibits/tables.md, each figureN_data.csv and
   graphical_abstract_data.csv equal what the exhibit scripts produce now.
6. References (Oxford SCIMED): superscript ^n^, ^n,m^, ^n–m^ placed after punctuation; every
   number in range; every reference cited; numbered in order of first citation; at most 30; each
   with a DOI or an "[accessed D Month YYYY]" date.
7. Lengths: a structured abstract (Background, Methods, Results, Conclusions) of at most 200
   words, without citations; at most 6 keywords, capitalised and in alphabetical order; the main
   text (Introduction to Discussion, headings excluded) at most 3,500 words; the Discussion holds
   a Limitations and a closing Conclusions subsection; the end sections in the journal's order.
8. Title page and wording: the title names the study type and claims no "first"; the title page
   gives a running title of at most 50 characters, the author, the affiliation, the e-mail and the
   ORCID; the AI disclosure is the same in the Acknowledgements and the cover letter; no internal
   identifiers; British spelling; "paid at least once", never "paid" alone; tiers, not ranks; the
   need weight never a count of undernourished patients; no causal language; "first" only in the
   hedged sentence. Private caveats (section_phrases.json "caveats") occur whole. The cover letter
   names every related manuscript listed in section_phrases.json "cover_letter".

Exit 1 on any problem.
"""
from __future__ import annotations

import argparse
import json
from datetime import datetime, timedelta
import re
import sys
from functools import lru_cache
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from exhibits.formats import (MAIN_YEAR, MINUS, MONTHS, NBSP, and_list, count, day, inr_bn, national,  # noqa: E402
                              num, one, pct, pct_n, people, pp, ratio, read_csv, rng, share_ci, small,
                              unit_rows)

DEFAULT_MS_DIR = "manuscript"
MS_NAME = "manuscript.md"
PHRASES = "section_phrases.json"
SKELETON = "number_skeleton.json"
TITLE_PAGE = "title_page_src.md"
COVER = "cover_letter.md"
SUPP_TEXT = "supplementary_text.md"  # the methods text of the supplementary data (checked like the manuscript)
SUPP_PREFIX = "Supplementary: "
LIMITS = {"abstract": 200, "main": 3500, "references": 30, "display_items": 5, "keywords": 6, "running_title": 50,
          "legend": 200}
MAIN_SECTIONS = ("Introduction", "Materials and methods", "Results", "Discussion")
ABSTRACT_PARTS = ("Background", "Methods", "Results", "Conclusions")
END_SECTIONS = ("Authors' contributions", "Acknowledgements", "Funding", "Competing interests", "Ethical approval",
                "Data availability")
AI_SENTENCE = ("The author used Claude (Anthropic) to assist with coding, analysis and drafting. The author reviewed and "
               "edited all content and takes full responsibility for the article.")
STUDY_TYPE = re.compile(r"\ban analysis of published\b", re.I)


# --------------------------------------------------------------------------------------
# The plan and the registration
# --------------------------------------------------------------------------------------
def plan_text(root: Path) -> str:
    return (root / "docs" / "analysis_plan.md").read_text(encoding="utf-8")


def plan_has(root: Path, s: str, where: str) -> str:
    """s, after confirming the registered plan states it (so the constant is the plan's)."""
    if s not in re.sub(r"\s+", " ", plan_text(root)):
        raise ValueError(f"the plan ({where}) does not state {s!r}")
    return s


# --------------------------------------------------------------------------------------
# Catalogue: label -> (text as printed, source)
# --------------------------------------------------------------------------------------
def catalogue(root: Path) -> dict[str, tuple[str, str]]:
    c: dict[str, tuple[str, str]] = {}

    def put(label: str, text: str, source: str) -> None:
        if label in c:
            raise ValueError(f"duplicate catalogue label {label}")
        c[label] = (text, source)

    # ---- registration and plan constants -------------------------------------------------
    reg = json.loads((root / "docs" / "registration_event.json").read_text(encoding="utf-8"))
    put("date.registration", day(reg["pushed_at"]), "docs/registration_event.json: pushed_at")
    put("reg.time", reg["pushed_at"][11:19] + " UTC", "docs/registration_event.json: pushed_at")
    put("reg.commit", reg["registered_commit"][:7], "docs/registration_event.json: registered_commit")
    ist = datetime.fromisoformat(reg["pushed_at"].replace("Z", "+00:00")) + timedelta(hours=5, minutes=30)
    put("reg.ist", f"{ist:%H:%M} India Standard Time on {ist.day} {MONTHS[ist.month - 1]}",
        "docs/registration_event.json: pushed_at in India Standard Time (UTC+5:30)")
    plan_has(root, "10,000", "§5.3, §10.1")
    put("plan.draws", count(10000), "docs/analysis_plan.md §5.3, §10.1 (10,000)")
    for lab, s in (("t80", "0.80"), ("t50", "0.50"), ("t20", "0.20")):
        put(f"plan.{lab}", plan_has(root, s, "§6"), "docs/analysis_plan.md §6 tiers")
    put("plan.p95", plan_has(root, "0.95", "§5.4"), "docs/analysis_plan.md §5.4 (class probability)")
    put("plan.two3", plan_has(root, "2/3", "§5.4"), "docs/analysis_plan.md §5.4 (class share)")
    for lab, s in (("p75", "75th"), ("p50", "50th"), ("p90", "90th")):
        put(f"plan.{lab}", plan_has(root, s, "§5.4"), "docs/analysis_plan.md §5.4 benchmarks")
    put("plan.agree", plan_has(root, "≥80%", "§8.2, §8.6").lstrip("≥"), "docs/analysis_plan.md §8.6 label rule")
    plan_has(root, "H1 (12 entries)", "§8.2")
    plan_has(root, "H2 (6 entries)", "§8.2")
    plan_has(root, "H3 (8 entries)", "§8.2")
    put("plan.grid", "12 entries for H1, 6 for H2 and 8 for each H3 outcome", "docs/analysis_plan.md §8.2 grids")
    put("plan.z998", plan_has(root, "99.8%", "§8.3"), "docs/analysis_plan.md §8.3 funnel")
    plan_has(root, "1,000 replicates", "§8.7")
    put("plan.replicates", f"{count(1000)} replicates", "docs/analysis_plan.md §8.7 perturbation (1,000 replicates)")
    put("plan.n1000", count(1000), "docs/analysis_plan.md §8.7 (1,000 replicates)")
    plan_has(root, "U(0.8, 1.2)", "§8.7")
    put("plan.pert", "between 0.8 and 1.2", "docs/analysis_plan.md §8.7 (U(0.8, 1.2))")
    put("plan.age", plan_has(root, "15–49", "§4.1"), "docs/analysis_plan.md §4.1, §4.3")
    plan_has(root, "18.5 kg/m²", "§4.3")
    put("plan.bmi", "18.5 kg/m²", "docs/analysis_plan.md §4.3")
    plan_has(root, "₹500 a month from April 2018, ₹1,000 a month from November 2024", "§1.1")
    put("plan.inr500", "INR 500", "docs/analysis_plan.md §1.1, §9 (₹500)")
    put("plan.n500", "500", "docs/analysis_plan.md §1.1 (₹500)")
    put("plan.inr1000", f"INR {count(1000)}", "docs/analysis_plan.md §1.1, §9 (₹1,000)")
    plan_has(root, "₹6,000", "§9")
    put("plan.inr6000", f"INR {count(6000)}", "docs/analysis_plan.md §9 (₹6,000)")
    plan_has(root, "× 6 months", "§9")
    plan_has(root, "8 months", "§9")
    put("plan.m6", "6 months", "docs/analysis_plan.md §9 (main)")
    put("plan.m68", "from 6 to 8 months", "docs/analysis_plan.md §9 (range)")
    put("plan.m6w", "six months", "docs/analysis_plan.md §9 (main, in words)")
    put("plan.wins", plan_has(root, "10%-winsorised", "§8.3").split("-")[0], "docs/analysis_plan.md §8.3 funnel")
    put("lit.jey761", "76.1%", "literature: Jeyashree et al. 2024 (ref 9), abstract via Crossref: 76.1% received at least one "
        "instalment in 2022")
    put("lit.jey91", "91 days", "literature: Jeyashree et al. 2024 (ref 9), abstract via Crossref: median 91 days to the first "
        "instalment in 2022")
    put("lit.asha15", "15 days", "literature: India TB Report 2023, PDF p. 114 (ASHA incentive for seeding within 15 days)")

    # ---- the national chain (outputs/chain.csv) ------------------------------------------
    ch = read_csv(root, "outputs/chain.csv")
    n23 = national(ch, MAIN_YEAR)
    put("units", count(len(unit_rows(ch, MAIN_YEAR))), "outputs/chain.csv: units, 2023 rows")
    put("units.data", count(n23["n_units_C"]), "outputs/chain.csv: national 2023 n_units_C")
    put("nat.C", pct(n23["C"]), "outputs/chain.csv: national 2023 C")
    put("nat.C.ci", share_ci(n23["C"], n23["C_lo"], n23["C_hi"]), "outputs/chain.csv: national 2023 C, C_lo, C_hi")
    for y in ("2021", "2022"):
        put(f"nat.C.{y}", pct(national(ch, y)["C"]), f"outputs/chain.csv: national {y} C")
    put("nat.A", pct(n23["A"]), "outputs/chain.csv: national 2023 A")
    put("nat.P", pct(n23["P"]), "outputs/chain.csv: national 2023 P")
    put("nat.Uacc", count(n23["U_acc"]), "outputs/chain.csv: national 2023 U_acc")
    put("nat.Upay", count(n23["U_pay"]), "outputs/chain.csv: national 2023 U_pay")
    bu = read_csv(root, "outputs/budget.csv")
    u = one(bu, "U 2023", item="U(2023), people not paid at least once")
    if count(u["count"]) != count(n23["U"]):
        raise ValueError("budget.csv U(2023) differs from chain.csv national U")
    put("nat.U", count(u["count"]), "outputs/budget.csv: U(2023) count (= chain.csv national U)")
    put("nat.U.ci", people(u["count"], u["count_lo"], u["count_hi"]), "outputs/budget.csv: U(2023) count, count_lo, count_hi")

    # ---- units, 2023 -----------------------------------------------------------------------
    st = sorted((r for r in unit_rows(ch, MAIN_YEAR) if r["C"]), key=lambda r: float(r["C"]))
    put("c.min", f"{st[0]['unit']}, at {pct(st[0]['C'])}", "outputs/chain.csv: 2023 lowest C")
    put("c.range2", f"{pct(st[1]['C'])} ({st[1]['unit']}) to {pct(st[-1]['C'])} ({st[-1]['unit']})",
        "outputs/chain.csv: 2023 second-lowest and highest C")
    pb = one(unit_rows(ch, MAIN_YEAR), "Punjab 2023", unit="Punjab")
    put("pb.Q", count(pb["Q_paid_at_least_once"]), "outputs/chain.csv: Punjab 2023 Q")
    put("pb.D", count(pb["D_denominator"]), "outputs/chain.csv: Punjab 2023 D")
    put("pb.B", count(pb["B_bank_available"]), "outputs/chain.csv: Punjab 2023 B")
    pr = {r["unit"]: r for r in read_csv(root, "outputs/priority.csv") if r["year"] == MAIN_YEAR and r["spec"] == "unweighted"}
    for y in ("2021", "2022"):
        r = one(unit_rows(ch, y), f"Punjab {y}", unit="Punjab")
        put(f"pb.C.{y}", pct(r["C"]), f"outputs/chain.csv: Punjab {y} C")
    put("pb.per100k", count(pr["Punjab"]["harm_per_100000"]), "outputs/priority.csv: Punjab 2023 unweighted harm_per_100000")
    sf = [r for r in read_csv(root, "outputs/shortfall.csv") if r["year"] == MAIN_YEAR and r["spec"] == "p75" and r["A_bench"]]
    put("bench.A", pct(sf[0]["A_bench"]), "outputs/shortfall.csv: 2023 p75 A_bench")
    put("bench.P", pct(sf[0]["P_bench"]), "outputs/shortfall.csv: 2023 p75 P_bench")
    cl = [r["class"] for r in read_csv(root, "outputs/chain_class.csv") if r["year"] == MAIN_YEAR and r["spec"] == "p75" and r["class"]]
    for lab, k in (("class.pay", "payment-led"), ("class.acc", "account-led"), ("class.mixed", "mixed"),
                   ("class.none", "no shortfall")):
        put(lab, count(cl.count(k)), f"outputs/chain_class.csv: 2023 p75 {k}")
    act = sorted(u for u, r in pr.items() if r["tier"] == "act now")
    put("act.U", and_list(act), "outputs/priority.csv: 2023 unweighted act now")
    usum = sum(float(pr[u]["U_observed"]) for u in act)
    tot = sum(float(r["U_observed"]) for r in pr.values() if r["U_observed"])
    put("act.share", f"{count(usum)} of the {count(tot)} ({pct(usum / tot)})", "outputs/priority.csv: 2023 act-now U sum / total")
    pt = read_csv(root, "outputs/perturbation.csv")
    tiered = [r for r in pt if r["share_unchanged"]]
    put("pert.all", f"{count(sum(float(r['share_unchanged']) == 1.0 for r in tiered))} of {count(len(tiered))}",
        "outputs/perturbation.csv: units with share_unchanged = 1")
    for u, lab in (("Punjab", "pert.pb"), ("Rajasthan", "pert.rj")):
        put(lab, pct(one(tiered, u, unit=u)["share_unchanged"]), f"outputs/perturbation.csv: {u} share_unchanged")
    lo = min(tiered, key=lambda r: float(r["share_unchanged"]))
    put("pert.min", f"{lo['unit']} kept it in {pct(lo['share_unchanged'])}", "outputs/perturbation.csv: lowest share_unchanged")

    # ---- trend ------------------------------------------------------------------------------
    tr = read_csv(root, "outputs/trend.csv")
    tn = one(tr, "national trend", level="national", spec="main_newcombe_2021_2022")
    put("trend", f"{pp(tn['estimate'])} ({rng(num(100 * float(tn['lo']), 1), num(100 * float(tn['hi']), 1))})",
        "outputs/trend.csv: national main change, lo, hi (x100)")
    fall = one(tr, "falling", level="summary", spec="main_newcombe_2021_2022")
    n_tr = sum(r["level"] == "unit" and r["spec"] == "main_newcombe_2021_2022" and r["estimate"] != "" for r in tr)
    put("trend.falling", f"{count(fall['estimate'])} of {count(n_tr)}", "outputs/trend.csv: units with falling coverage")

    # ---- headline estimates -------------------------------------------------------------------
    hl = {r["hypothesis"]: r for r in read_csv(root, "outputs/headline.csv")}
    for h, key in (("H1", "H1"), ("H2", "H2"), ("H3", "H3_success"), ("H3d", "H3_died"), ("H3l", "H3_ltfu")):
        r = hl[key]
        put(f"{h}.value", ratio(r["estimate"]), f"outputs/headline.csv: {key} estimate")
        put(f"{h}.ci", rng(ratio(r["lo"]), ratio(r["hi"])), f"outputs/headline.csv: {key} lo, hi")
        put(f"{h}.label", r["label"], f"outputs/headline.csv: {key} label")
        put(f"{h}.agree", f"{count(r['n_agree'])} of {count(r['n_entries'])}", f"outputs/headline.csv: {key} n_agree, n_entries")
    put("H2.entries", count(hl["H2"]["n_entries"]), "outputs/headline.csv: H2 n_entries")
    put("H3.nobs", count(hl["H3_success"]["n_obs"]), "outputs/headline.csv: H3_success n_obs")
    put("H3.kish", num(hl["H3_success"]["kish_effective_clusters"], 1), "outputs/headline.csv: H3_success kish_effective_clusters")
    put("H3.kish0", count(hl["H3_success"]["kish_effective_clusters"]), "outputs/headline.csv: H3_success Kish (whole number)")
    sc = read_csv(root, "outputs/spec_curve.csv")
    e7 = one(sc, "H3 entry 7", hypothesis="H3_success", entry="7")
    e8 = one(sc, "H3 entry 8", hypothesis="H3_success", entry="8")
    put("H3.adj", ratio(e7["estimate"]), "outputs/spec_curve.csv: H3_success entry 7 estimate")
    put("H3.adj.wald", rng(ratio(e7["wald_lo"]), ratio(e7["wald_hi"])), "outputs/spec_curve.csv: H3_success entry 7 wald_lo, wald_hi")
    put("H3.adj2", ratio(e8["estimate"]), "outputs/spec_curve.csv: H3_success entry 8 estimate")

    # ---- funnel ---------------------------------------------------------------------------------
    fu = read_csv(root, "outputs/funnel.csv")
    put("fun.cbar", pct(fu[0]["c_bar"]), "outputs/funnel.csv: c_bar")
    put("fun.phi", count(fu[0]["phi_f"]), "outputs/funnel.csv: phi_f")
    bh = one(fu, "Bihar", unit="Bihar")
    put("fun.bihar", f"Bihar ({pct(bh['C'])})", "outputs/funnel.csv: Bihar C")

    # ---- leave-one-out ---------------------------------------------------------------------------
    lo1 = read_csv(root, "outputs/leave_one_out.csv")
    wp = {h: one(lo1, f"{h} Punjab", analysis=h, omitted="Punjab")["estimate"] for h in ("H1", "H2", "H3_success")}
    put("loo.punjab", f"H1 was {ratio(wp['H1'])}, H2 {ratio(wp['H2'])} and H3 for success {ratio(wp['H3_success'])}",
        "outputs/leave_one_out.csv: H1, H2, H3_success without Punjab")
    for h, lab in (("H1", "loo.H1"), ("H3_success", "loo.H3")):
        mn = one(lo1, f"{h} min", analysis=h, summary="minimum")["estimate"]
        mx = one(lo1, f"{h} max", analysis=h, summary="maximum")["estimate"]
        put(lab, rng(ratio(mn), ratio(mx)), f"outputs/leave_one_out.csv: {h} minimum and maximum")

    # ---- budget ----------------------------------------------------------------------------------
    main = one(bu, "main", spec="main")
    put("bud.main", inr_bn(main["cost"]), "outputs/budget.csv: main cost")
    r1 = one(bu, "range 500x6", spec="rate 500, 6 months")
    r2 = one(bu, "range 1000x8", spec="rate 1000, 8 months")
    put("bud.range", f"{inr_bn(r1['cost'])} to {inr_bn(r2['cost'])}", "outputs/budget.csv: range minimum and maximum cost")
    inc = one(bu, "increment p75", spec="p75", item="benchmark scenario: increment over the current number paid at least once")
    put("bud.cbench", pct(inc["C_bench"]), "outputs/budget.csv: p75 C_bench")
    put("bud.inc", count(inc["count"]), "outputs/budget.csv: p75 increment count")
    put("bud.inc.cost", inr_bn(inc["cost"]), "outputs/budget.csv: p75 increment cost")
    strengthen_catalogue(root, put)
    return c


def strengthen_catalogue(root: Path, put) -> None:
    """Values of the strengthened text: n/N forms, spelled-out small counts, the validated split and the
    class totals in people (computed by the exhibit code from outputs/), and the size of the counts."""
    from exhibits import make_tables as mt
    ch = read_csv(root, "outputs/chain.csv")
    n23 = national(ch, MAIN_YEAR)
    vs = mt.validated_split(root)
    src_vs = "exhibits/make_tables.py validated_split() from outputs/chain.csv (Table S4 national row)"
    put("nat.C.n", pct_n(vs["Q"], vs["D"]), src_vs)
    put("nat.A.n", pct_n(vs["B"], vs["D"]), src_vs)
    put("vs.V.n", pct_n(vs["Vd"], vs["B"]), src_vs)
    put("vs.PV.n", pct_n(vs["Q"], vs["Vd"]), src_vs)
    put("vs.V", pct(vs["V"]), src_vs)
    put("vs.PV", pct(vs["PV"]), src_vs)
    for y in ("2021", "2022"):
        us = [r for r in unit_rows(ch, y) if r["C"]]
        q, d = (sum(int(r[k]) for r in us) for k in ("Q_paid_at_least_once", "D_denominator"))
        if pct(q / d) != pct(national(ch, y)["C"]):
            raise ValueError(f"{y}: summed C differs from the national C")
        put(f"nat.C.{y}.n", pct_n(q, d), f"outputs/chain.csv: {y} unit rows summed (= national C)")
    st = {r["unit"]: r for r in unit_rows(ch, MAIN_YEAR)}

    def unit_n(u, num="Q_paid_at_least_once", den="D_denominator", year=MAIN_YEAR):
        r = one(unit_rows(ch, year), f"{u} {year}", unit=u)
        return pct_n(r[num], r[den])
    srt = sorted((r for r in st.values() if r["C"]), key=lambda r: float(r["C"]))
    lo, hi = srt[1], srt[-1]
    put("c.range2.n", f"{pct_n(lo['Q_paid_at_least_once'], lo['D_denominator'])[:-1]}; {lo['unit']}) to "
        f"{pct_n(hi['Q_paid_at_least_once'], hi['D_denominator'])[:-1]}; {hi['unit']})",
        "outputs/chain.csv: 2023 second-lowest and highest C with Q/D")
    put("c.range.round", f"about {pct(lo['C'], 0)} to {pct(hi['C'], 0)}", "outputs/chain.csv: 2023 C range, whole per cent")
    put("pb.C.n", unit_n("Punjab"), "outputs/chain.csv: Punjab 2023 Q/D")
    put("pb.C.2021.n", unit_n("Punjab", year="2021"), "outputs/chain.csv: Punjab 2021 Q/D")
    put("pb.C.2022.n", unit_n("Punjab", year="2022"), "outputs/chain.csv: Punjab 2022 Q/D")
    up = st["Uttar Pradesh"]
    put("up.U", count(up["U"]), "outputs/chain.csv: Uttar Pradesh 2023 U")
    put("up.C.n", unit_n("Uttar Pradesh"), "outputs/chain.csv: Uttar Pradesh 2023 Q/D")
    put("tg.V.n", unit_n("Telangana", "bank_validated", "B_bank_available"), "outputs/chain.csv: Telangana 2023 V")
    put("tg.PV.n", unit_n("Telangana", "Q_paid_at_least_once", "bank_validated"), "outputs/chain.csv: Telangana 2023 Q/validated")
    put("ap.PV.n", unit_n("Andhra Pradesh", "Q_paid_at_least_once", "bank_validated"),
        "outputs/chain.csv: Andhra Pradesh 2023 Q/validated")
    tr = read_csv(root, "outputs/trend.csv")
    fall = one(tr, "falling", level="summary", spec="main_newcombe_2021_2022")
    n_tr = sum(r["level"] == "unit" and r["spec"] == "main_newcombe_2021_2022" and r["estimate"] != "" for r in tr)
    put("trend.falling.w", f"{small(fall['estimate'])} of {count(n_tr)}", "outputs/trend.csv: units with falling coverage")
    put("falling.n.w", small(fall["estimate"]), "outputs/trend.csv: number of units with falling coverage")
    xp = {k: v for k, v in (("all", mt.class_people(root)), ("noPb", mt.class_people(root, ("Punjab",))))}
    src_cp = "exhibits/make_tables.py class_people() from outputs/shortfall.csv and outputs/chain.csv (Table S8)"
    put("noPb.split", f"{count(xp['noPb']['all']['U_acc'])} and {count(xp['noPb']['all']['U_pay'])}", src_cp)
    cl = xp["all"]
    put("cls.w", f"{small(cl['account-led']['units'])} units were account-led, {small(cl['payment-led']['units'])} "
        f"payment-led and {small(cl['mixed']['units'])} mixed, and {small(cl['no shortfall']['units'])} had no shortfall",
        "outputs/chain_class.csv via class_people(): units by class")
    put("cls.people", f"{count(cl['account-led']['U'])}, {count(cl['payment-led']['U'])}, {count(cl['mixed']['U'])} and "
        f"{count(cl['no shortfall']['U'])}", src_cp)
    put("cls.acc.U", count(cl["account-led"]["U"]), src_cp)
    put("cls.pay.U", count(cl["payment-led"]["U"]), src_cp)
    put("cls.mixed.U", count(cl["mixed"]["U"]), src_cp)
    put("cls.acc.w", small(cl["account-led"]["units"]), src_cp)
    put("cls.pay.n", count(cl["payment-led"]["units"]), src_cp)
    put("S.all", f"{count(cl['all']['S_acc'])} people before bank details and {count(cl['all']['S_pay'])} after", src_cp)
    put("S.noPb", f"{count(xp['noPb']['all']['S_acc'])} and {count(xp['noPb']['all']['S_pay'])} without Punjab", src_cp)
    sf = {r["unit"]: r for r in read_csv(root, "outputs/shortfall.csv") if r["year"] == MAIN_YEAR and r["spec"] == "p75"}
    put("sf.examples", f"Maharashtra ({count(sf['Maharashtra']['S_acc'])}) and Delhi ({count(sf['Delhi']['S_acc'])}); "
        f"among payment-led units outside Punjab, the largest payment shortfalls were in Telangana "
        f"({count(sf['Telangana']['S_pay'])}) and Andhra Pradesh ({count(sf['Andhra Pradesh']['S_pay'])})",
        "outputs/shortfall.csv: 2023 p75 S_acc and S_pay of the named units")
    pr = {r["unit"]: r for r in read_csv(root, "outputs/priority.csv") if r["year"] == MAIN_YEAR and r["spec"] == "unweighted"}
    act = [u for u, r in pr.items() if r["tier"] == "act now"]
    usum = sum(float(pr[u]["U_observed"]) for u in act)
    tot = sum(float(r["U_observed"]) for r in pr.values() if r["U_observed"])
    put("act.share.n", pct_n(usum, tot), "outputs/priority.csv: 2023 act-now U sum / total")
    us = [float(r["U_observed"]) for r in pr.values() if r["U_observed"]]
    put("fold.U", f"about {count(round(max(us) / min(us), -2))}-fold between units ({count(min(us))} to {count(max(us))})",
        "outputs/priority.csv: 2023 U, max/min rounded to the hundred")
    nw = [float(r["wt_u_relative_need_weight"]) for r in read_csv(root, "outputs/need_weight.csv") if r["spec"] == "sex_weighted"]
    put("fold.wt", f"about {small(round(max(nw) / min(nw)))}-fold ({ratio(min(nw))} to {ratio(max(nw))})",
        "outputs/need_weight.csv: sex-weighted wt_u, max/min")
    pt = {r["unit"]: r for r in read_csv(root, "outputs/perturbation.csv")}
    put("pert.n", f"{count(pt['Punjab']['n_unchanged'])} and {count(pt['Rajasthan']['n_unchanged'])} of "
        f"{count(pt['Punjab']['n_replicates'])}", "outputs/perturbation.csv: Punjab and Rajasthan n_unchanged")
    put("rate.examples", f"Manipur ({count(pr['Manipur']['harm_per_100000'])}) and Telangana "
        f"({count(pr['Telangana']['harm_per_100000'])}) had more unpaid people than any act-now unit except Punjab "
        f"({count(pr['Punjab']['harm_per_100000'])} as printed)", "outputs/priority.csv: 2023 harm_per_100000")
    ka = one(unit_rows(ch, "2022"), "Karnataka 2022", unit="Karnataka")
    put("ka.U2022", count(ka["U"]), "outputs/chain.csv: Karnataka 2022 U")
    put("act.min", count(min(usum for usum in (float(pr[u]["U_observed"]) for u in act))),
        "outputs/priority.csv: smallest 2023 act-now U")
    put("pay.share.n", pct_n(n23["U"], vs["Q"]), "outputs/chain.csv: national 2023 U / summed Q")
    put("H2.entries.n", count(one(read_csv(root, "outputs/headline.csv"), "H2", hypothesis="H2")["n_entries"]),
        "outputs/headline.csv: H2 n_entries")
    hl = {r["hypothesis"]: r for r in read_csv(root, "outputs/headline.csv")}
    put("H3.kish.s", num(hl["H3_success"]["kish_effective_clusters"], 1), "outputs/headline.csv: H3_success Kish")
    fu = read_csv(root, "outputs/funnel.csv")
    put("fun.limits", f"{num(fu[0]['widen'], 1)}; 95% limits ±{num(fu[0]['upper_95'], 1)} and 99.8% limits "
        f"±{num(fu[0]['upper_998'], 1)}", "outputs/funnel.csv: widen, upper_95, upper_998")


@lru_cache(maxsize=4)
def catalogue_cached(root: Path) -> dict[str, tuple[str, str]]:
    return catalogue(root)


# --------------------------------------------------------------------------------------
# Claims stated in words, re-tested on the outputs
# --------------------------------------------------------------------------------------
def claims(root: Path) -> list[str]:
    out: list[str] = []

    def need(ok: bool, msg: str) -> None:
        if not ok:
            out.append(f"CLAIM fails: {msg}")

    hl = {x["hypothesis"]: x for x in read_csv(root, "outputs/headline.csv")}
    need(hl["H1"]["label"] == "not established" and hl["H2"]["label"] == "not established", "H1 and H2 are not established")
    need(hl["H3_success"]["label"] == "supported", "H3 for treatment success is supported")
    need(hl["H3_died"]["label"] == "not established" and hl["H3_ltfu"]["label"] == "not established",
         "H3 for death and loss to follow-up is not established")
    sc = read_csv(root, "outputs/spec_curve.csv")
    need(all(float(r["estimate"]) < 0 for r in sc if r["hypothesis"] == "H2"), "all H2 grid entries are negative")
    e1 = float(one(sc, "e1", hypothesis="H3_success", entry="1")["estimate"])
    e7 = float(one(sc, "e7", hypothesis="H3_success", entry="7")["estimate"])
    need(e1 > 0.15 and 0 < e7 < 0.05, "H3 for success attenuates to about 0.03 when adjusted for previous-year success")
    pri = [r for r in read_csv(root, "outputs/priority.csv") if r["year"] == MAIN_YEAR]
    un = {r["unit"]: r for r in pri if r["spec"] == "unweighted"}
    nw = {r["unit"]: r for r in pri if r["spec"] == "need_weighted_sex_weighted"}
    five = {"Bihar", "Maharashtra", "Punjab", "Rajasthan", "Uttar Pradesh"}
    need({u for u, r in un.items() if r["tier"] == "act now"} == five, "the unweighted act-now tier holds the five units named")
    need({u for u, r in nw.items() if r["tier"] == "act now"} == five, "the need-weighted act-now tier holds the same five units")
    need(all(r["tier"] in ("act now", "lower priority") for r in un.values() if r["tier"]),
         "every other unit with data is lower priority")
    need(all(float(r["p_top5"]) < 0.01 or float(r["p_top5"]) > 0.99 for r in pri if r["p_top5"] and r["spec"] == "unweighted"),
         "P(top-5) is near 0 or 1")
    usum = sum(float(un[u]["U_observed"]) for u in five)
    need(usum / sum(float(r["U_observed"]) for r in un.values() if r["U_observed"]) > 0.5,
         "the five act-now units hold most of the people not paid at least once")
    ch = read_csv(root, "outputs/chain.csv")
    n23 = national(ch, MAIN_YEAR)
    need(int(n23["U_pay"]) > int(n23["U_acc"]), "more people were lost after bank details than before (2023)")
    us = [r for r in unit_rows(ch, MAIN_YEAR) if r["U_pay"]]
    need(sum(int(r["U_pay"]) > int(r["U_acc"]) for r in us) > len(us) / 2,
         "in most units more people were lost after bank details than before (Figure 2 alt text)")
    need(0.70 <= float(n23["C"]) <= 0.80, "about three-quarters were paid at least once in 2023")
    need(float(national(ch, "2022")["C"]) > float(national(ch, "2021")["C"]), "coverage rose from 2021 to 2022")
    st = {r["unit"]: r for r in unit_rows(ch, MAIN_YEAR)}
    need(not st["Karnataka"]["C"] and not st["Karnataka"]["D_denominator"], "Karnataka has no 2023 denominator")
    need(min((r for r in st.values() if r["C"]), key=lambda r: float(r["C"]))["unit"] == "Punjab", "Punjab has the lowest 2023 C")
    cl = {r["unit"]: r["class"] for r in read_csv(root, "outputs/chain_class.csv") if r["year"] == MAIN_YEAR and r["spec"] == "p75"}
    for u, k in (("Maharashtra", "account-led"), ("Delhi", "account-led"), ("Gujarat", "account-led"),
                 ("Telangana", "payment-led"), ("Andhra Pradesh", "payment-led"), ("Tamil Nadu", "payment-led"),
                 ("Bihar", "mixed"), ("Rajasthan", "mixed"), ("Uttar Pradesh", "mixed")):
        need(cl[u] == k, f"{u} is {k} in 2023")
    for u in ("Chhattisgarh", "Jharkhand", "Madhya Pradesh"):
        need(float(nw[u]["wt_u"]) > 1, f"{u} has a need weight above the mean")
    for spec, out_u in (("need_weighted_women", "Punjab"), ("need_weighted_men", "Rajasthan")):
        got = {r["unit"] for r in pri if r["spec"] == spec and r["tier"] == "act now"}
        need(got == (five - {out_u}) | {"Madhya Pradesh"}, f"the {spec} act-now set has Madhya Pradesh in place of {out_u}")
    need(all(float(national(ch, y)["C"]) > float(one(unit_rows(ch, y), "pb", unit="Punjab")["C"]) > 0.10
             for y in ("2021", "2022")), "Punjab's coverage was low in 2021 and 2022 but far above its 2023 value")
    fu = read_csv(root, "outputs/funnel.csv")
    need({r["unit"] for r in fu if r["position"] == "below the 99.8% limit"} == {"Bihar", "Punjab"},
         "Bihar and Punjab are the units below the 99.8% limit")
    lo = read_csv(root, "outputs/leave_one_out.csv")
    a = one(lo, "U without Punjab", analysis="act-now set 2023, harm U", omitted="Punjab")
    b = one(lo, "U_wt without Punjab", analysis="act-now set 2023, harm U_wt_sex_weighted", omitted="Punjab")
    need(a["changed_units"] == "Telangana", "without Punjab, Telangana enters the act-now set for the unpaid count")
    need(b["changed_units"] == "Madhya Pradesh", "without Punjab, Madhya Pradesh enters the need-weighted act-now set")
    # ---- claims of the strengthened text
    from exhibits import make_tables as mt
    for spec in ("unweighted", "need_weighted_sex_weighted", "need_weighted_women", "need_weighted_men",
                 "need_weighted_simple"):
        got = {r["unit"] for r in pri if r["spec"] == spec and r["tier"] == "act now"}
        need({"Bihar", "Maharashtra", "Uttar Pradesh"} <= got, f"Bihar, Maharashtra and Uttar Pradesh act now under {spec}")
    top5 = sorted(un, key=lambda u: -float(un[u]["U_observed"] or -1))[:5]
    need(set(top5) == five, "the act-now set equals the five largest unpaid counts")
    vs = mt.validated_split(root)
    need(vs["Vd"] - vs["Q"] > vs["B"] - vs["Vd"], "more people were lost after validation than at it (2023)")
    upr = st["Uttar Pradesh"]
    need(max((r for r in st.values() if r["U"]), key=lambda r: int(r["U"]))["unit"] == "Uttar Pradesh"
         and float(upr["C"]) > float(n23["C"]), "Uttar Pradesh has the most unpaid people and above-national coverage")
    falling = sorted(r["unit"] for r in read_csv(root, "outputs/trend.csv") if r["level"] == "unit"
                     and r["spec"] == "main_newcombe_2021_2022" and r["falling_coverage"] == "True")
    need(falling == ["Andaman and Nicobar Islands", "Andhra Pradesh", "Goa", "Gujarat", "Himachal Pradesh",
                     "Madhya Pradesh", "Odisha", "Tamil Nadu", "Uttarakhand"], "the nine units with falling coverage named")
    sf = {r["unit"]: r for r in read_csv(root, "outputs/shortfall.csv") if r["year"] == MAIN_YEAR and r["spec"] == "p75"}
    acc = sorted((u for u in sf if cl.get(u) == "account-led"), key=lambda u: -float(sf[u]["S_acc"]))
    pay = sorted((u for u in sf if cl.get(u) == "payment-led" and u != "Punjab"), key=lambda u: -float(sf[u]["S_pay"]))
    need(acc[:2] == ["Maharashtra", "Delhi"], "Maharashtra and Delhi have the largest account shortfalls of account-led units")
    need(pay[:2] == ["Telangana", "Andhra Pradesh"],
         "Telangana and Andhra Pradesh have the largest payment shortfalls of payment-led units outside Punjab")
    rate = {u: float(r["harm_per_100000"]) for u, r in un.items() if r["harm_per_100000"]}
    need(all(rate[x] > rate[u] for x in ("Manipur", "Telangana") for u in five - {"Punjab"}) and
         all(rate["Punjab"] > rate[x] for x in ("Manipur", "Telangana")),
         "Manipur and Telangana have higher rates than every act-now unit except Punjab")
    ka = one(unit_rows(ch, "2022"), "Karnataka 2022", unit="Karnataka")
    need(int(ka["U"]) < min(float(un[u]["U_observed"]) for u in five), "Karnataka's 2022 count is below the act-now counts")
    need(all(r["agrees_with_main"] == "True" for r in sc if r["hypothesis"] == "H3_success" and r["entry"] in ("7", "8")),
         "the two adjusted H3 success entries agree in sign")
    nac = read_csv(root, "outputs/na_cells.csv")
    need(any(r["unit"] == "Himachal Pradesh" and r["year"] == "2021" and "bank_available_exceeds_denominator" in r["reason"]
             for r in nac) and any(r["unit"] == "Meghalaya" and r["year"] == "2023" and "paid_exceeds_bank_validated"
                                   in r["reason"] for r in nac), "the two data-quality flags are in na_cells.csv")
    env = (root / "ENVIRONMENT.md").read_text(encoding="utf-8")
    need(all(x in env for x in ("| Python | 3.14.0 |", "| numpy | 2.3.5 |", "| scipy | 1.16.3 |", "| tbprio | 1.0.1 |")),
         "the software versions stated are those of ENVIRONMENT.md")
    nd = read_csv(root, "data/extracted/npy_national_check.csv")
    need(all(r["equal"] == "True" for r in nd), "each NPY table's India paid-at-least-once figure equals the national DBT table")
    tc = [r for r in read_csv(root, "data/extracted/total_checks.csv") if r["table_key"] == "ITR2024_NPY"]
    need(all(r["difference"] == "0" for r in tc), "Punjab's 2023 row is consistent with the printed India total")
    return out


# --------------------------------------------------------------------------------------
# Section phrases (private; read at run time from <folder>/section_phrases.json)
# --------------------------------------------------------------------------------------
def load_phrase_file(ms_dir: Path) -> dict:
    d = json.loads((ms_dir / PHRASES).read_text(encoding="utf-8"))
    secs = d.get("sections") if isinstance(d, dict) else None
    if not isinstance(secs, dict) or not secs or not all(
            isinstance(k, str) and isinstance(v, list) and all(isinstance(x, str) for x in v) for k, v in secs.items()):
        raise ValueError(f"{PHRASES}: 'sections' must map section names to lists of phrases")
    return d


def section_phrases(ms_dir: Path) -> dict[str, list[str]]:
    return load_phrase_file(ms_dir)["sections"]


# --------------------------------------------------------------------------------------
# Fixed (non-result) number patterns
# --------------------------------------------------------------------------------------
SUPPLEMENT = [f"S{k}" for k in range(1, 16)]
TABLES = [1]
FIGURES = [1, 2, 3, 4]
FIXED: list[tuple[str, str]] = [
    ("reference", r"\^\d+(?:[,–]\d+)*\^"),
    ("exhibit", r"\bTables? S\d{1,2}(?:(?:,| and| to|–) ?S\d{1,2})*\b"),
    ("exhibit", r"\b(?:Table|Figure)s? [1-4][AB]?(?:(?:,| and| to) [1-4][AB]?)*\b"),
    ("name", r"\b[H][1-3]\b|\bNFHS-5\b|\bP\(top-5\)"),
    ("ci_level", r"\b95%"),
    ("plan_section", r"\bplan section 1[12]\b"),
    ("formula", r"\(1 − \*f\*~u~\)|\bbelow 0\b|\bexcluding 0\b|\bnear 0 or 1\b|\bper 100\u00a0000\b|\b1 or near 0\b"),
    ("formula", r"1\.06/\(n − 3\)"),
    ("software", r"\bPython 3\.14\b|\bNumPy 2\.3\.5\b|\bSciPy 1\.16\.3\b|\btbprio 1\.0\.1\b"),
    ("date", r"\b\d{1,2} (?:" + "|".join(MONTHS) + r") 20\d\d\b"),
    ("years", r"\b20(?:1[7-9]|2[0-6])–(?:20)?(?:1[7-9]|2[0-6])\b"),
    ("year", r"(?<![\d.,])20(?:1[7-9]|2[0-6])(?![\d]|[.,]\d)"),
    ("doi", r"10\.5281/zenodo\.(?:\d+|X+)"),
]
NUMBER = re.compile(r"\d+(?:\u00a0\d{3}(?!\d))*(?:\.\d+)?")


def sections(text: str) -> dict[str, str]:
    """Heading -> whitespace-collapsed text: the title ("Title") and every '## ' section (its
    '### ' subsections included) but the References."""
    out: dict[str, list[str]] = {}
    cur = None
    for ln in text.splitlines():
        if ln.startswith("# ") and not out:
            out["Title"] = [ln[2:]]
            cur = None
        elif ln.startswith("## "):
            cur = ln[3:].strip()
            out[cur] = []
        elif cur is not None:
            out[cur].append(ln)
    # whitespace collapsed, but a no-break space (the thousands separator) is kept
    return {k: re.sub(r"[ \t\r\n]+", " ", "\n".join(v)).strip() for k, v in out.items() if k != "References"}


def fill(template: str, cat: dict) -> tuple[str, list[tuple[int, int, str]]]:
    out, spans, pos = "", [], 0
    for m in re.finditer(r"\{([^}]+)\}", template):
        out += template[pos:m.start()]
        val = cat[m.group(1)][0]
        spans.append((len(out), len(out) + len(val), m.group(1)))
        out += val
        pos = m.end()
    return out + template[pos:], spans


def _occurrences(body: str, phrase: str) -> list[int]:
    before = r"(?<![\d.,−-])" if re.match(r"[\d−-]", phrase) else ""
    after = r"(?![\d]|[.,]\d)" if re.search(r"\d$", phrase) else ""
    pat = re.compile(before + re.escape(phrase) + after)
    return [m.start() for m in pat.finditer(body)]


def assign(name: str, body: str, cat: dict, required: list[str]) -> tuple[list[dict], list[str]]:
    """Label every number token of one section; return (skeleton entries, problems)."""
    probs: list[str] = []
    labels: dict[int, tuple[str, str]] = {}
    toks = [(m.start(), m.end(), m.group()) for m in NUMBER.finditer(body)]
    for tpl in required:
        try:
            phrase, spans = fill(tpl, cat)
        except KeyError as e:
            probs.append(f"PHRASES in {name}: unknown label {e}")
            continue
        occ = _occurrences(body, phrase)
        if not occ:
            probs.append(f"MISSING in {name}: {phrase!r}")
            continue
        for at in occ:
            for s, e, _ in toks:
                for ps, pe, lab in spans:
                    if at + ps <= s and e <= at + pe and s not in labels:
                        labels[s] = (lab, cat[lab][1])
    dates = {v[0]: k for k, v in cat.items() if k.startswith("date.")}
    for kind, pat in FIXED:
        for m in re.finditer(pat, body):
            for s, e, _ in toks:
                if m.start() <= s and e <= m.end() and s not in labels:
                    if kind == "date":
                        lab = dates.get(m.group())
                        if lab is None:
                            probs.append(f"DATE in {name} is not a catalogue date: {m.group()!r}")
                            continue
                        labels[s] = (lab, cat[lab][1])
                    else:
                        labels[s] = (f"fixed:{kind}", f"fixed {kind}: {m.group()}")
    entries = []
    for s, e, t in toks:
        if s not in labels:
            probs.append(f"UNACCOUNTED number in {name}: {t!r} in ...{body[max(0, s - 40):e + 20]}...")
            entries.append({"token": t, "label": "UNACCOUNTED", "source": ""})
        else:
            entries.append({"token": t, "label": labels[s][0], "source": labels[s][1]})
    return entries, probs


def all_sections(text: str, supp: str | None) -> dict[str, str]:
    """The manuscript's sections and, prefixed, the '## ' sections of the supplementary methods text."""
    secs = sections(text)
    if supp is not None:
        secs.update({SUPP_PREFIX + k: v for k, v in sections("# Supplementary data\n" + supp).items() if k != "Title"})
    return secs


def skeleton(text: str, root: Path, required: dict[str, list[str]],
             supp: str | None = None) -> tuple[dict[str, list[dict]], list[str]]:
    cat = catalogue_cached(root)
    secs = all_sections(text, supp)
    out, probs = {}, []
    for name in required:
        if name not in secs:
            probs.append(f"MISSING section {name!r}")
    for name, body in secs.items():
        entries, p = assign(name, body, cat, required.get(name, []))
        out[name] = entries
        probs += p
    return out, probs


def skeleton_problems(now: dict, gold: dict | None, root: Path) -> list[str]:
    if gold is None:
        return [f"{SKELETON} missing: after review run python -I verification/check_manuscript_numbers.py --regenerate"]
    cat = catalogue_cached(root)
    out = []
    for name in sorted(set(now) | set(gold)):
        a = [(x["token"], x["label"]) for x in gold.get(name, [])]
        b = [(x["token"], x["label"]) for x in now.get(name, [])]
        if a != b:
            k = next((i for i, (x, y) in enumerate(zip(a, b)) if x != y), min(len(a), len(b)))
            out.append(f"SKELETON {name}: entry {k + 1} is {b[k] if k < len(b) else '(none)'}, golden has "
                       f"{a[k] if k < len(a) else '(none)'} ({len(b)} tokens now, {len(a)} golden)")
        for x in gold.get(name, []):
            lab = x["label"]
            if lab.startswith("fixed:"):
                continue
            if lab not in cat:
                out.append(f"SKELETON {name}: golden label {lab} is not in the catalogue")
            elif x["token"] not in NUMBER.findall(cat[lab][0]):
                out.append(f"SKELETON {name}: golden token {x['token']!r} is no longer in {lab} = {cat[lab][0]!r}")
    return out


# --------------------------------------------------------------------------------------
# Exhibits: citations, legends, display items, and the regenerated tables and figure data
# --------------------------------------------------------------------------------------
def legends(text: str) -> dict[int, str]:
    """Figure k -> its legend paragraph (from '**Figure k.**') with its alt-text paragraph."""
    part = text.split("\n## Figure legends", 1)
    if len(part) != 2:
        return {}
    out: dict[int, str] = {}
    cur = None
    for para in re.split(r"\n\s*\n", part[1]):
        m = re.match(r"\*\*Figure (\d)\.\*\*", para.strip())
        if m:
            cur = int(m.group(1))
            out[cur] = para.strip()
        elif cur is not None and para.strip():
            out[cur] += "\n\n" + para.strip()
    return out


def exhibit_problems(text: str) -> list[str]:
    secs = sections(text)
    body = " ".join(v for k, v in secs.items() if k not in ("Title", "Abstract", "Figure legends"))
    out = []
    for kind, want, pat in (("Table", TABLES, r"\bTables? ((?:[1-9](?:, | and | to )?)+)\b"),
                            ("Figure", FIGURES, r"\bFigures? ((?:[1-9][AB]?(?:, | and | to )?)+)")):
        seen = []
        for m in re.finditer(pat, body):
            seen += [int(n) for n in re.findall(r"[1-9]", m.group(1))]
        first = list(dict.fromkeys(seen))
        if sorted(first) != want:
            out.append(f"EXHIBITS: {kind}s cited {first}, expected each of {want}")
        elif first != want:
            out.append(f"EXHIBITS: first citations of {kind}s out of order: {first}")
    if len(TABLES) + len(FIGURES) > LIMITS["display_items"]:
        out.append(f"EXHIBITS: {len(TABLES) + len(FIGURES)} display items, more than {LIMITS['display_items']}")
    sup: list[str] = []
    for m in re.finditer(r"\bTables? (S\d{1,2}(?:(?:,| and| to|–) ?S\d{1,2})*)", body):
        parts = re.findall(r"S(\d{1,2})", m.group(1))
        if re.search(r"(?: to|–) ?S", m.group(1)) and len(parts) == 2:
            parts = [str(k) for k in range(int(parts[0]), int(parts[1]) + 1)]
        for p in parts:
            s = f"S{p}"
            if s not in SUPPLEMENT:
                out.append(f"EXHIBITS: supplementary {s} does not exist")
            else:
                sup.append(s)
    first = list(dict.fromkeys(sup))
    if first != [s for s in SUPPLEMENT if s in first]:
        out.append(f"EXHIBITS: supplementary tables first cited out of order: {first}")
    never = [s for s in SUPPLEMENT if s not in first]
    if never:
        out.append(f"EXHIBITS: supplementary tables never cited: {never}")
    lg = legends(text)
    for n in FIGURES:
        if n not in lg:
            out.append(f"EXHIBITS: no legend for Figure {n}")
            continue
        paras = lg[n].split("\n\n")
        if not any(p.startswith("Alt text: ") for p in paras[1:]):
            out.append(f"EXHIBITS: the legend of Figure {n} has no 'Alt text:' line under it")
        w = words(paras[0])
        if w > LIMITS["legend"]:
            out.append(f"EXHIBITS: the legend of Figure {n} has {w} words (limit {LIMITS['legend']})")
    return out


def regenerated_problems(ms_dir: Path, root: Path) -> list[str]:
    """tables.md and the figure and graphical-abstract data equal what the exhibit scripts
    produce from outputs/ now."""
    from exhibits import make_figures, make_graphical_abstract, make_tables
    out = []
    ex = ms_dir / "exhibits"
    p = ex / "tables.md"
    if not p.exists():
        return ["EXHIBITS: exhibits/tables.md missing (python -I exhibits/make_tables.py)"]
    if p.read_text(encoding="utf-8") != make_tables.render_md(make_tables.build(root)):
        out.append("EXHIBITS: exhibits/tables.md differs from the tables regenerated from outputs/")
    for k, fn in make_figures.FIGURES.items():
        q = ex / f"figure{k}_data.csv"
        if not q.exists() or q.read_bytes() != make_figures.data_csv(fn(root)):
            out.append(f"EXHIBITS: exhibits/figure{k}_data.csv differs from the data regenerated from outputs/")
    q = ex / "graphical_abstract_data.csv"
    if not q.exists() or q.read_bytes() != make_figures.data_csv(make_graphical_abstract.ga_data(root)):
        out.append("EXHIBITS: exhibits/graphical_abstract_data.csv differs from the data regenerated from outputs/")
    return out


# --------------------------------------------------------------------------------------
# References: Oxford SCIMED, superscript numbers
# --------------------------------------------------------------------------------------
CITE = re.compile(r"\^(\d+(?:[,–]\d+)*)\^")


def ref_list(text: str) -> list[tuple[int, str]]:
    part = text.split("\n## References", 1)
    if len(part) != 2:
        return []
    body = part[1].split("\n## ", 1)[0]
    return [(int(m.group(1)), m.group(2)) for m in re.finditer(r"(?m)^(\d+)\. (.+)$", body)]


def citations(text: str) -> list[int]:
    body = text.split("\n## References", 1)[0]
    order: list[int] = []
    for m in CITE.finditer(body):
        for part in m.group(1).split(","):
            a, _, b = part.partition("–")
            order += list(range(int(a), int(b or a) + 1))
    return order


def reference_problems(text: str) -> list[str]:
    refs = ref_list(text)
    if not refs:
        return ["REFERENCES: no '## References' section with entries 'n. ...'"]
    n = len(refs)
    out = []
    if n > LIMITS["references"]:
        out.append(f"REFERENCES: {n} references, more than {LIMITS['references']}")
    if [k for k, _ in refs] != list(range(1, n + 1)):
        out.append("REFERENCES: list not numbered 1..n")
    order = citations(text)
    for k in sorted(set(order)):
        if not 1 <= k <= n:
            out.append(f"REFERENCES: citation {k} outside 1..{n}")
    first = list(dict.fromkeys(order))
    if first != sorted(first):
        out.append(f"REFERENCES: not numbered in order of first citation: {first}")
    never = sorted(set(range(1, n + 1)) - set(order))
    if never:
        out.append(f"REFERENCES: never cited: {never}")
    body = text.split("\n## References", 1)[0]
    for m in CITE.finditer(body):
        if body[m.start() - 1] not in ".,;:?!":
            out.append(f"REFERENCES: citation ^{m.group(1)}^ not placed after punctuation: ...{body[max(0, m.start() - 40):m.end()]}")
    if re.search(r"\[\d+(?:[,–]\d+)*\]", body):
        out.append("REFERENCES: a bracketed citation [n] in the text (the journal uses superscripts)")
    for k, e in refs:
        if "https://doi.org/" not in e and not re.search(r"\[accessed \d{1,2} \w+ \d{4}\]\.?$", e):
            out.append(f"REFERENCES: {k} has neither a DOI nor an [accessed ...] date")
        auth = e.split(". ", 1)[0]
        if auth.endswith(", et al") and len(auth.removesuffix(", et al").split(", ")) != 3:
            out.append(f"REFERENCES: {k} does not list exactly three authors before et al.")
        if "et al" not in auth and auth.count(",") >= 4 and not re.search(r"Institute|Division|ICF", auth):
            out.append(f"REFERENCES: {k} lists more than four authors without et al.")
        pg = re.search(r" \d{4};\d+:e?(\d+)–(\d+)\.", e)
        if pg and len(pg.group(2)) == len(pg.group(1)) > 1 and pg.group(2)[0] == pg.group(1)[0]:
            out.append(f"REFERENCES: {k} page range not truncated (Oxford style: 177–81)")
        if ("[dataset]" in e or "[software]" in e) and "doi.org/10.5281/zenodo." not in e:
            out.append(f"REFERENCES: {k} is a data or software reference without its Zenodo DOI")
    return out


# --------------------------------------------------------------------------------------
# Lengths: abstract, keywords, main text, structure
# --------------------------------------------------------------------------------------
def words(s: str) -> int:
    """Words as Word counts them (a no-break space separates words, as in Word)."""
    return len(re.findall(r"\S+", re.sub(r"[*_#|]", " ", re.sub(r"\^[^^]*\^", "", s))))


def main_text(text: str) -> str:
    """Introduction to Discussion, '### ' headings excluded (the journal's 3,500-word count)."""
    out, keep = [], False
    for ln in text.splitlines():
        if ln.startswith("## "):
            keep = ln[3:].strip() in MAIN_SECTIONS
            continue
        if keep and not ln.startswith("#"):
            out.append(ln)
    return "\n".join(out)


def length_problems(text: str) -> list[str]:
    out = []
    secs = sections(text)
    ab = secs.get("Abstract", "")
    kw = re.search(r"\*\*Keywords:\*\* (.+)$", ab)
    abstract = ab[:kw.start()].strip() if kw else ab
    if words(abstract) > LIMITS["abstract"]:
        out.append(f"LENGTH: abstract {words(abstract)} words, limit {LIMITS['abstract']}")
    heads = re.findall(r"\*\*(\w+):\*\*", abstract)
    if heads != list(ABSTRACT_PARTS):
        out.append(f"LENGTH: abstract headings {heads}, expected {list(ABSTRACT_PARTS)}")
    if CITE.search(abstract) or re.search(r"\[\d", abstract):
        out.append("LENGTH: the abstract cites a reference")
    if not kw:
        out.append("LENGTH: no '**Keywords:**' line at the end of the Abstract")
    else:
        k = [x.strip() for x in kw.group(1).split(",") if x.strip()]
        if not 1 <= len(k) <= LIMITS["keywords"]:
            out.append(f"LENGTH: {len(k)} keywords (1 to {LIMITS['keywords']} allowed)")
        if k != sorted(k, key=str.lower):
            out.append(f"LENGTH: keywords not in alphabetical order: {k}")
        if any(not x[0].isupper() for x in k):
            out.append("LENGTH: keywords not capitalised")
    names = list(secs)
    for name in MAIN_SECTIONS:
        if name not in secs:
            out.append(f"LENGTH: no '## {name}' section")
    m = words(main_text(text))
    if m > LIMITS["main"]:
        out.append(f"LENGTH: main text {m} words (Introduction to Discussion, headings excluded), limit {LIMITS['main']}")
    disc = text.split("\n## Discussion", 1)[-1].split("\n## ", 1)[0]
    subs = re.findall(r"(?m)^### (.+)$", disc)
    if "Limitations" not in subs or not subs or subs[-1] != "Conclusions":
        out.append(f"STRUCTURE: the Discussion needs a Limitations subsection and a closing Conclusions ({subs})")
    ends = [n for n in names if n in END_SECTIONS]
    if ends != list(END_SECTIONS):
        out.append(f"STRUCTURE: end sections {ends}, expected {list(END_SECTIONS)} in this order")
    tail = names[names.index(END_SECTIONS[-1]) + 1:] if END_SECTIONS[-1] in names else []
    if tail != ["Figure legends"]:
        out.append(f"STRUCTURE: after Data availability expected References and Figure legends, found {tail}")
    for name, want in (("Funding", "None."), ("Competing interests", "None declared."),
                       ("Ethical approval", "Not required.")):
        if not secs.get(name, "").startswith(want):
            out.append(f"STRUCTURE: '{name}' does not start {want!r}")
    return out


# --------------------------------------------------------------------------------------
# Title page, wording and labels
# --------------------------------------------------------------------------------------
BANNED = [
    (r"\bTask \d|\bfix round\b|\bcontroller\b|\bimplementer\b|\bdispatch|\bsubagent\b", "drafting-process language"),
    (r"\bITR ?20\d\d\b|\bTBAR\b|\bA1\.\d|\bA3\.\d", "a shorthand source identifier"),
    (r"§", "a section sign (write 'plan section 12')"),
    (r"\b(?:outputs|data|verification|exhibits|src|docs)/\S+|\.py\b|\.csv\b", "a file path"),
    (r"\bp_top5\b|\bneed_weighted\w*|\bharm_\w+|\bsex_weighted\b|\b[ACP]_bench\b|\bU_wt\b|\bshare_unchanged\b",
     "an internal variable name"),
]
WORDING = [
    (r"\bpaid\b(?! at least once)", "write 'paid at least once', never 'paid' alone"),
    (r"\bfully paid\b", "never 'fully paid'"),
    (r"(?<!not a count of )\bundernourished (?:TB )?patients\b", "the need weight is never a count of undernourished patients"),
    (r"\bcaus(?:ed|es|ing)\b|\bled to\b|\bleads? to\b|\bresult(?:ed|s)? in\b|\beffect of\b|\bimpact of\b"
     r"|\bimprov(?:es|ed)\b|\breduc(?:es|ed)\b|\bbecause of the (?:payment|programme)\b", "causal language"),
    (r"\branked\b|\brank(?:s|ed)? (?:first|highest|lowest)\b|\btop-ranked\b|\bnumber one\b|\bworst\b"
     r"|\bbest[- ]performing\b|\bfailing\b|\bto blame\b|\bpoorly performing\b|\bfollowed by\b", "ranking or blaming language"),
    (r"(?<!knowledge, this is )\bthe first (?:study|analysis|paper)\b", "'first' only in the hedged sentence"),
]
AMERICAN = [r"\banalyz", r"(?<!age-)\bstandardiz", r"(?<!World Health )\borganiz", r"\bprogram\b(?! Planning)",
            r"\bprograms\b", r"\bcolor", r"\bcenters?\b", r"\bbehavior", r"\bmodeling\b", r"\blabeled\b", r"\bminimiz",
            r"\bprioritiz", r"\brecogniz", r"\butiliz", r"\bcategoriz", r"\bhospitaliz", r"\bemphasiz", r"\bfavor",
            r"\bjudgment", r"\bgeneraliz", r"\bdiarrhea", r"\banemia", r"\bpediatric"]


def wording_problems(name: str, text: str) -> list[str]:
    out = []
    body = text.split("\n## References", 1)[0]
    if name == "exhibits/tables.md":
        body = "\n".join(ln for ln in body.splitlines() if not ln.startswith("# Tables (generated"))
    for pat, what in BANNED + WORDING:
        for m in re.finditer(pat, body, re.I if (pat, what) in WORDING else 0):
            out.append(f"WORDING in {name}: {what}: {m.group()!r}")
    for pat in AMERICAN:
        for m in re.finditer(pat, body, re.I):
            out.append(f"SPELLING in {name}: American form {m.group()!r}")
    return out


def label_problems(text: str, root: Path) -> list[str]:
    """No label stronger than the registered ones; H3 'supported' only as an ecological association."""
    out = []
    body = text.split("\n## References", 1)[0]
    for m in re.finditer(r"\b(H[1-3])\b[^\n.]{0,200}?\b(confirmed|validated|proven|(?<!not )established|significant)\b", body):
        out.append(f"LABEL: {m.group(1)} written as {m.group(2)!r} in ...{m.group()[-80:]}...")
    flat = re.sub(r"\s+", " ", body)
    for m in re.finditer(r"[^.;]*\bH3\b[^.;]*\bsupported\b[^.;]*[.;]", flat):
        near = flat[m.start():m.end() + 200]
        if "ecological association" not in near:
            out.append(f"LABEL: H3 'supported' without 'ecological association' nearby: {m.group()[:120]!r}")
    return out


def front_line(text: str, key: str) -> str | None:
    hits = [ln for ln in text.splitlines() if ln.startswith(key)]
    return hits[0] if len(hits) == 1 else None


def title_page_problems(text: str, title_page: str) -> list[str]:
    out = []
    title = text.splitlines()[0][2:].strip() if text.startswith("# ") else ""
    if not title:
        out.append("TITLE: manuscript.md does not start with its '# ' title")
    if not STUDY_TYPE.search(title):
        out.append("TITLE: the title does not state the study type (a pre-registered ... analysis)")
    if re.search(r"\bfirst\b", title, re.I):
        out.append("TITLE: the title claims 'first'")
    rt = (front_line(title_page, "**Running title:**") or "").split(":**", 1)[-1].strip()
    if not rt or len(rt) > LIMITS["running_title"]:
        out.append(f"TITLE PAGE: running title missing or longer than {LIMITS['running_title']} characters: {rt!r}")
    for key in ("**Author:**", "**Corresponding author:**"):
        if front_line(title_page, key) is None:
            out.append(f"TITLE PAGE: no {key.strip('*:')} line")
    if not re.search(r"Department of Community Medicine, Shridevi Institute", title_page):
        out.append("TITLE PAGE: no affiliation")
    if not re.search(r"[\w.+-]+@[\w-]+\.[\w.]+", title_page):
        out.append("TITLE PAGE: no e-mail address")
    if not re.search(r"\d{4}-\d{4}-\d{4}-\d{3}[\dX]", title_page):
        out.append("TITLE PAGE: no ORCID")
    return out


def declaration_problems(text: str, cover: str | None) -> list[str]:
    out = []
    ack = sections(text).get("Acknowledgements", "")
    if AI_SENTENCE not in ack:
        out.append("DECLARATION: the AI disclosure is missing from the Acknowledgements")
    if cover is not None and AI_SENTENCE not in re.sub(r"\s+", " ", cover):
        out.append("DECLARATION: the AI disclosure in the cover letter differs from the Acknowledgements")
    if "10.5281/zenodo.XXXXXXX" not in sections(text).get("Data availability", "") and not re.search(
            r"10\.5281/zenodo\.\d+", sections(text).get("Data availability", "")):
        out.append("DECLARATION: Data availability lacks the Zenodo DOI (or its placeholder)")
    return out


def cover_problems(cover: str | None, required: list[str]) -> list[str]:
    if cover is None:
        return [f"MISSING: {COVER}"]
    return [f"COVER LETTER: does not name the related manuscript {r!r}" for r in required if r not in cover]


def caveat_problems(text: str, caveats: dict[str, list[str]], supp: str | None = None) -> list[str]:
    secs = all_sections(text, supp)
    return [f"CAVEAT missing in {name}: {c!r}" for name, cs in caveats.items() for c in cs
            if c not in secs.get(name, "")]


# --------------------------------------------------------------------------------------
# Driver
# --------------------------------------------------------------------------------------
def manuscript_dir(root: Path, argv: list[str]) -> tuple[Path, list[str]]:
    ap = argparse.ArgumentParser(add_help=False, allow_abbrev=False)
    ap.add_argument("--manuscript-dir", default=DEFAULT_MS_DIR)
    a, rest = ap.parse_known_args(argv)
    d = Path(a.manuscript_dir)
    return (d if d.is_absolute() else root / d), rest


def rel(p: Path, root: Path) -> str:
    try:
        return p.relative_to(root).as_posix()
    except ValueError:
        return p.as_posix()


def load_gold(ms_dir: Path) -> dict | None:
    p = ms_dir / SKELETON
    return json.loads(p.read_text(encoding="utf-8"))["sections"] if p.exists() else None


def read_opt(ms_dir: Path, name: str) -> str | None:
    p = ms_dir / name
    return p.read_text(encoding="utf-8") if p.exists() else None


def problems(root: Path, ms_dir: Path, text: str | None = None, gold: dict | None = None,
             required: dict | None = None, exhibits: bool = True) -> list[str]:
    """Every problem of the manuscript folder (the arguments override what is read from it;
    exhibits=False skips regenerating the tables and figure data, for the mutation sweep)."""
    text = text if text is not None else (ms_dir / MS_NAME).read_text(encoding="utf-8")
    gold = gold if gold is not None else load_gold(ms_dir)
    required = required if required is not None else section_phrases(ms_dir)
    if not required:
        return [f"PHRASES: no section phrases ({PHRASES} missing or empty)"]
    pf = load_phrase_file(ms_dir)
    supp = read_opt(ms_dir, SUPP_TEXT)
    if supp is None:
        return [f"MISSING: {SUPP_TEXT}"]
    now, out = skeleton(text, root, required, supp)
    out += skeleton_problems(now, gold, root)
    out += claims(root)
    out += exhibit_problems(text)
    if exhibits:
        out += regenerated_problems(ms_dir, root)
    caveats = pf.get("caveats", {})
    if not caveats:
        out.append(f"CAVEAT: no caveats listed in {PHRASES}")
    out += caveat_problems(text, caveats, supp)
    out += reference_problems(text)
    out += length_problems(text)
    out += label_problems(text, root)
    out += wording_problems(MS_NAME, text)
    out += wording_problems(SUPP_TEXT, supp)
    tables = read_opt(ms_dir, "exhibits/tables.md")
    if tables is not None:
        out += wording_problems("exhibits/tables.md", tables)
    tp = read_opt(ms_dir, TITLE_PAGE)
    if tp is None:
        out.append(f"MISSING: {TITLE_PAGE}")
    else:
        out += wording_problems(TITLE_PAGE, tp)
        out += title_page_problems(text, tp)
    cover = read_opt(ms_dir, COVER)
    out += declaration_problems(text, cover)
    out += cover_problems(cover, pf.get("cover_letter", []))
    if cover is not None:
        out += [p for p in wording_problems(COVER, cover) if "file path" not in p]
    if not pf.get("cover_letter"):
        out.append(f"COVER LETTER: no related manuscripts listed in {PHRASES} 'cover_letter'")
    return out


def golden(text: str, root: Path, required: dict, supp: str | None = None) -> dict:
    now, probs = skeleton(text, root, required, supp)
    if probs:
        raise SystemExit("cannot regenerate the skeleton while phrases or numbers fail:\n" + "\n".join(probs))
    return {"about": "Golden numeric skeleton of manuscript.md: for each section, every number token in reading order "
                     "with the catalogue label that accounts for it and its source. Written by "
                     "verification/check_manuscript_numbers.py --regenerate after review.",
            "sections": now}


def main(root: Path = ROOT, argv: list[str] | None = None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    ms_dir, rest = manuscript_dir(root, argv)
    unknown = [a for a in rest if a != "--regenerate"]
    if unknown:
        print(f"FAIL: unknown arguments {unknown}")
        return 1
    name = rel(ms_dir, root)
    if not ms_dir.is_dir():
        print(f"SKIPPED: {name}/ not present (kept private, not in this repository)")
        return 0
    ms, ph = ms_dir / MS_NAME, ms_dir / PHRASES
    if not ms.exists() and not ph.exists():
        print(f"SKIPPED: {name}/{MS_NAME} not present (kept private, not in this repository)")
        return 0
    if not ms.exists() or not ph.exists():
        have, lack = (MS_NAME, PHRASES) if ms.exists() else (PHRASES, MS_NAME)
        print(f"FAIL: {name}/{have} is present but {name}/{lack} is missing")
        return 1
    try:
        required = section_phrases(ms_dir)
    except ValueError as e:
        print(f"FAIL: {name}/{PHRASES} cannot be read: {e}")
        return 1
    text = ms.read_text(encoding="utf-8")
    if "--regenerate" in rest:
        g = golden(text, root, required, read_opt(ms_dir, SUPP_TEXT))
        (ms_dir / SKELETON).write_text(json.dumps(g, indent=1, ensure_ascii=False) + "\n", encoding="utf-8",
                                       newline="\n")
        print(f"wrote {name}/{SKELETON}: {sum(len(v) for v in g['sections'].values())} number tokens")
        return 0
    found = problems(root, ms_dir, text, required=required)
    for ln in found:
        print(ln)
    gold = load_gold(ms_dir) or {}
    n_tok = sum(len(v) for v in gold.values())
    n_traced = sum(1 for v in gold.values() for x in v if not x["label"].startswith("fixed:"))
    print(f"{n_tok} number tokens ({n_traced} traced to a source file, {n_tok - n_traced} fixed labels), "
          f"{sum(len(v) for v in required.values())} section phrases, {len(catalogue_cached(root))} catalogue "
          f"values, {len(ref_list(text))} references; tables, figure and graphical-abstract data regenerated from "
          f"outputs/; {len(found)} problem(s)")
    return 1 if found else 0


if __name__ == "__main__":
    sys.exit(main())
