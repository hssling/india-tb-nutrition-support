# Adapted from hssling/india-tb-diabetes-gap v1.0.0 (MIT), exhibits/make_figures.py (itself adapted
# from hssling/india-tb-priority-tool and hssling/india-tb-acf-campaign); modified: the four figures
# of this paper (the 2023 payment chain by unit with its benchmarks, the unpaid counts split by
# step with the tiers, coverage against the need share with the funnel, and coverage against
# treatment success), drawn from outputs/ in Arial, with a colour-blind-safe palette and text labels.
"""Draw the manuscript's figures from outputs/ into <manuscript folder>/exhibits/.

Run as: python -I exhibits/make_figures.py [--manuscript-dir DIR]   (default: manuscript)

Writes figure1.pdf ... figure4.pdf (vector, Arial; the build renders each to a 600 dpi colour
TIFF), a PNG preview of each (figureN.png, 200 dpi, for reading the layout only) and
figureN_data.csv, the values each figure plots, read by the figN_data() functions (the number
check regenerates them and requires the CSVs to be identical). Figure 4 plots the treatment
success share of each cohort, read from the committed extraction (data/extracted/
outcomes_panel.csv); every other value is read from outputs/. Needs matplotlib (3.10.7). The
PDFs carry no creation date, so a rerun gives the same bytes on the same platform.

Figure 1  the payment chain by unit, 2023: A (bank details available), P (paid at least once of
          those with bank details) and C (paid at least once of eligible), with Jeffreys
          intervals, the 75th-percentile benchmarks and the national value; marker by class
Figure 2  people not paid at least once by unit, 2023, split into those lost before bank
          details (U_acc) and after (U_pay), with the need-weighted count and the tiers; variable names
          are set as subscripts with matplotlib mathtext in Arial
Figure 3  (A) C (2023) against the need share n_u (H1); (B) the overdispersed funnel of C
          against the number of eligible beneficiaries
Figure 4  treatment success share of the 2021 and 2022 DS-TB cohorts against C of the same
          year (H3, an ecological association)
"""
from __future__ import annotations

import argparse
import csv
import io
import math
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from exhibits.formats import (MAIN_YEAR, national, num, one, pct, ratio, read_csv, rng,  # noqa: E402
                              unit_rows)

DEFAULT_MS_DIR = "manuscript"
WIDTH = 6.85  # inches: a full-page figure width (174 mm)
FONT = "Arial"
BLUE, ORANGE, DARK, GREY, LIGHT = "#0072B2", "#D55E00", "#000000", "#7f7f7f", "#c8c8c8"
SKY = "#56B4E9"
CLASS_STYLE = {"account-led": ("o", BLUE, True), "payment-led": ("s", ORANGE, True), "mixed": ("D", DARK, True),
               "no shortfall": ("o", GREY, False)}
ANOMALY = "Punjab"


# --------------------------------------------------------------------------------------
# The data of each figure
# --------------------------------------------------------------------------------------
def fig1_data(root: Path) -> list[dict]:
    cl = {r["unit"]: r["class"] for r in read_csv(root, "outputs/chain_class.csv")
          if r["year"] == MAIN_YEAR and r["spec"] == "p75"}
    sf = [r for r in read_csv(root, "outputs/shortfall.csv") if r["year"] == MAIN_YEAR and r["spec"] == "p75" and r["A_bench"]]
    cb = one(read_csv(root, "outputs/budget.csv"), "C_bench p75", spec="p75",
             item="benchmark scenario: increment over the current number paid at least once")["C_bench"]
    ch = read_csv(root, "outputs/chain.csv")
    n = national(ch, MAIN_YEAR)
    rows = []
    for r in sorted(unit_rows(ch, MAIN_YEAR), key=lambda r: r["unit"]):
        rows.append({"unit": r["unit"], "A": r["A"], "A_lo": r["A_lo"], "A_hi": r["A_hi"], "P": r["P"], "P_lo": r["P_lo"],
                     "P_hi": r["P_hi"], "C": r["C"], "C_lo": r["C_lo"], "C_hi": r["C_hi"], "class": cl.get(r["unit"], ""),
                     "A_bench": sf[0]["A_bench"], "P_bench": sf[0]["P_bench"], "C_bench": cb,
                     "A_national": n["A"], "P_national": n["P"], "C_national": n["C"]})
    return rows


def fig2_data(root: Path) -> list[dict]:
    pr = {(r["unit"], r["spec"]): r for r in read_csv(root, "outputs/priority.csv") if r["year"] == MAIN_YEAR}
    rows = []
    for r in sorted(unit_rows(read_csv(root, "outputs/chain.csv"), MAIN_YEAR), key=lambda r: r["unit"]):
        a, b = pr[(r["unit"], "unweighted")], pr[(r["unit"], "need_weighted_sex_weighted")]
        rows.append({"unit": r["unit"], "U": r["U"], "U_acc": r["U_acc"], "U_pay": r["U_pay"], "tier": a["tier"],
                     "wt_u": b["wt_u"], "U_wt": b["harm_observed"], "tier_need_weighted": b["tier"]})
    return rows


def fig3_data(root: Path) -> list[dict]:
    nw = {r["unit"]: r for r in read_csv(root, "outputs/need_weight.csv") if r["spec"] == "sex_weighted"}
    fu = {r["unit"]: r for r in read_csv(root, "outputs/funnel.csv")}
    h1 = one(read_csv(root, "outputs/headline.csv"), "H1", hypothesis="H1")
    rows = []
    for r in sorted(unit_rows(read_csv(root, "outputs/chain.csv"), MAIN_YEAR), key=lambda r: r["unit"]):
        f = fu.get(r["unit"])
        if f is None:
            continue
        rows.append({"unit": r["unit"], "C": r["C"], "n_u": nw[r["unit"]]["n_u"], "D": f["D"], "c_bar": f["c_bar"],
                     "widen": f["widen"], "z": f["z"], "position": f["position"], "flag": f["flag"],
                     "H1": h1["estimate"], "H1_lo": h1["lo"], "H1_hi": h1["hi"], "H1_label": h1["label"]})
    return rows


def fig4_data(root: Path) -> list[dict]:
    oc: dict[tuple[str, str], dict[str, int]] = {}
    for r in read_csv(root, "data/extracted/outcomes_panel.csv"):
        oc.setdefault((r["unit"], r["cohort_year"]), {})[r["measure"]] = int(r["value"])
    hl = one(read_csv(root, "outputs/headline.csv"), "H3 success", hypothesis="H3_success")
    adj = one(read_csv(root, "outputs/spec_curve.csv"), "H3 success entry 7", hypothesis="H3_success", entry="7")
    rows = []
    for r in sorted(unit_rows(read_csv(root, "outputs/chain.csv")), key=lambda r: (r["year"], r["unit"])):
        if r["year"] not in ("2021", "2022") or not r["C"]:
            continue
        o = oc[(r["unit"], r["year"])]
        rows.append({"cohort_year": r["year"], "unit": r["unit"], "C": r["C"], "cohort": o["cohort"], "success": o["success"],
                     "success_share": repr(o["success"] / o["cohort"]), "H3": hl["estimate"], "H3_lo": hl["lo"],
                     "H3_hi": hl["hi"], "H3_label": hl["label"], "H3_adjusted_previous_year": adj["estimate"]})
    return rows


FIGURES = {1: fig1_data, 2: fig2_data, 3: fig3_data, 4: fig4_data}


def data_csv(rows: list[dict]) -> bytes:
    buf = io.StringIO()
    w = csv.DictWriter(buf, fieldnames=list(rows[0]), lineterminator="\n")
    w.writeheader()
    w.writerows(rows)
    return buf.getvalue().encode("utf-8")


# --------------------------------------------------------------------------------------
# Drawing
# --------------------------------------------------------------------------------------
def setup():
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    plt.rcParams.update({
        "font.family": FONT, "font.size": 7.5, "axes.titlesize": 8, "axes.labelsize": 7.5,
        "xtick.labelsize": 7, "ytick.labelsize": 7, "legend.fontsize": 7, "axes.linewidth": 0.6,
        "xtick.major.width": 0.5, "ytick.major.width": 0.5, "pdf.fonttype": 42, "svg.hashsalt": "nutpay",
        "axes.spines.top": False, "axes.spines.right": False,
        "mathtext.fontset": "custom", "mathtext.rm": FONT, "mathtext.it": f"{FONT}:italic",
        "mathtext.bf": f"{FONT}:bold", "mathtext.default": "regular",
    })
    return plt


def legend_handles(classes: list[str]):
    from matplotlib.lines import Line2D
    out = []
    for c in classes:
        m, col, filled = CLASS_STYLE[c]
        out.append(Line2D([], [], marker=m, ls="", ms=4.2, mfc=col if filled else "white", mec=col, mew=0.8))
    return out


def draw1(rows: list[dict], plt):
    units = [r["unit"] for r in rows]
    fig, axes = plt.subplots(1, 3, figsize=(WIDTH, 6.3), sharey=True)
    panels = [("A", "A  Bank details available (A)\nof eligible beneficiaries"),
              ("P", "B  Paid at least once (P)\nof those with bank details"),
              ("C", "C  Paid at least once (C)\nof eligible beneficiaries")]
    for ax, (k, title) in zip(axes, panels):
        for i, r in enumerate(rows):
            if not r[k]:
                ax.annotate("no 2023 data", (2, i), va="center", fontsize=6.3, color=GREY)
                continue
            v, lo, hi = (100 * float(r[x]) for x in (k, f"{k}_lo", f"{k}_hi"))
            m, col, filled = CLASS_STYLE[r["class"]]
            ax.plot([lo, hi], [i, i], color=col, lw=0.9, solid_capstyle="butt")
            ax.plot(v, i, marker=m, ms=3.6, mfc=col if filled else "white", mec=col, mew=0.8, ls="")
            if r["unit"] == ANOMALY and k in ("P", "C"):
                ax.annotate("as printed", (v, i), xytext=(5, 0), textcoords="offset points", va="center", fontsize=6.3)
        bench = 100 * float(rows[0][f"{k}_bench"])
        nat = 100 * float(rows[0][f"{k}_national"])
        ax.axvline(bench, color=BLUE, ls="--", lw=0.9, zorder=0)
        ax.axvline(nat, color=GREY, ls=":", lw=0.9, zorder=0)
        ax.set_xlim(0, 100)
        ax.set_xticks([0, 25, 50, 75, 100])
        ax.set_title(title, loc="left", fontweight="bold", fontsize=7.4)
        ax.set_xlabel("Per cent, 2023")
        ax.grid(axis="y", color="#eeeeee", lw=0.5)
        ax.set_axisbelow(True)
    axes[0].set_ylim(len(units) - 0.4, -0.6)
    axes[0].set_yticks(range(len(units)))
    axes[0].set_yticklabels(units)
    from matplotlib.lines import Line2D
    classes = ["account-led", "payment-led", "mixed", "no shortfall"]
    h = legend_handles(classes) + [Line2D([], [], color=BLUE, ls="--", lw=0.9), Line2D([], [], color=GREY, ls=":", lw=0.9)]
    fig.legend(h, classes + ["75th-percentile benchmark", "national value (units with data)"], loc="lower center", ncol=6,
               frameon=False, fontsize=6.6, handletextpad=0.3, columnspacing=1.0)
    fig.subplots_adjust(left=0.235, right=0.985, top=0.93, bottom=0.11, wspace=0.1)
    return fig


def draw2(rows: list[dict], plt):
    units = [r["unit"] for r in rows]
    fig, ax = plt.subplots(figsize=(WIDTH, 6.3))
    xmax = max(max(float(r["U"]), float(r["U_wt"])) for r in rows if r["U"]) / 1000
    for i, r in enumerate(rows):
        if not r["U"]:
            ax.annotate("no 2023 data", (1, i), va="center", fontsize=6.3, color=GREY)
            continue
        acc, pay = float(r["U_acc"]) / 1000, float(r["U_pay"]) / 1000
        ax.barh(i, acc, height=0.68, color=SKY, edgecolor="none")
        ax.barh(i, pay, left=acc, height=0.68, color=ORANGE, edgecolor="none")
        ax.plot(float(r["U_wt"]) / 1000, i, marker="D", ms=3.4, mfc="white", mec=DARK, mew=0.8, ls="")
        end = max(acc + pay, float(r["U_wt"]) / 1000)
        if r["tier"] == "act now":
            note = "act now" if r["tier_need_weighted"] == "act now" else "act now (unpaid count)"
            if r["unit"] == ANOMALY:
                note += "; printed value"
            ax.annotate(note, (end, i), xytext=(4, 0), textcoords="offset points", va="center", fontsize=6.5,
                        fontweight="bold")
    ax.set_ylim(len(units) - 0.4, -0.6)
    ax.set_yticks(range(len(units)))
    ax.set_yticklabels(units)
    ax.set_xlim(0, xmax * 1.22)
    ax.set_xlabel("People not paid at least once, 2023 (thousands)")
    ax.grid(axis="x", color="#eeeeee", lw=0.5)
    ax.set_axisbelow(True)
    from matplotlib.lines import Line2D
    from matplotlib.patches import Patch
    h = [Patch(color=SKY), Patch(color=ORANGE), Line2D([], [], marker="D", ls="", ms=3.4, mfc="white", mec=DARK, mew=0.8)]
    ax.legend(h, ["lost before bank details ($U_{acc}$)", "lost after bank details ($U_{pay}$)",
                  "need-weighted count (U × relative need weight)"], loc="center right", frameon=False)
    fig.subplots_adjust(left=0.235, right=0.985, top=0.985, bottom=0.07)
    return fig


def draw3(rows: list[dict], plt):
    fig, (a, b) = plt.subplots(1, 2, figsize=(WIDTH, 3.2))
    h = rows[0]
    for r in rows:
        x, y = 100 * float(r["n_u"]), 100 * float(r["C"])
        flagged = bool(r["flag"])
        a.plot(x, y, marker="o", ms=3.6, mfc=DARK if flagged else "white", mec=DARK, mew=0.7, ls="")
        if flagged:
            a.annotate(r["unit"] + (" (as printed)" if r["unit"] == ANOMALY else ""), (x, y), xytext=(4, 0),
                       textcoords="offset points", va="center", fontsize=6.5)
    a.set_xlabel("Need share $n_u$: adults aged 15–49 with BMI <18.5 kg/m² (%)")
    a.set_ylabel("C: paid at least once of eligible, 2023 (%)")
    a.set_ylim(0, 100)
    a.set_title("A  Coverage and need (H1)", loc="left", fontweight="bold")
    a.text(0.97, 0.3, f"Spearman ρ {ratio(h['H1'])} (95% CI {rng(ratio(h['H1_lo']), ratio(h['H1_hi']))}); {h['H1_label']}",
           transform=a.transAxes, fontsize=6.5, ha="right")
    cbar, widen = float(h["c_bar"]), float(h["widen"])
    ds = [float(r["D"]) for r in rows]
    x0, x1 = min(ds) / 1.5, max(ds) * 1.5
    grid = [x0 * (x1 / x0) ** (k / 200) for k in range(201)]
    for z, ls in ((1.96, ":"), (3.09, "-")):
        for sgn in (-1, 1):
            ys = [100 * min(1, max(0, cbar + sgn * z * widen * math.sqrt(cbar * (1 - cbar) / d))) for d in grid]
            b.plot(grid, ys, color=BLUE, ls=ls, lw=0.9)
    b.axhline(100 * cbar, color=GREY, lw=0.7)
    for r in rows:
        below = r["position"] == "below the 99.8% limit"
        b.plot(float(r["D"]), 100 * float(r["C"]), marker="o", ms=3.6, mfc=DARK if below else "white", mec=DARK, mew=0.7,
               ls="")
        if below:
            b.annotate(r["unit"], (float(r["D"]), 100 * float(r["C"])), xytext=(5, 0), textcoords="offset points",
                       ha="left", va="center", fontsize=6.5)
    b.set_xscale("log")
    b.set_xlim(x0, x1)
    b.set_ylim(0, 100)
    b.set_xlabel("Eligible beneficiaries, 2023 (log scale)")
    b.set_title("B  Funnel, widened for overdispersion", loc="left", fontweight="bold")
    from matplotlib.lines import Line2D
    b.legend([Line2D([], [], color=BLUE, lw=0.9), Line2D([], [], color=BLUE, ls=":", lw=0.9),
              Line2D([], [], color=GREY, lw=0.7)], ["99.8% limits", "95% limits", f"pooled coverage {pct(cbar)}"],
             loc="lower left", bbox_to_anchor=(0.0, 0.28), frameon=False)
    fig.subplots_adjust(left=0.08, right=0.985, top=0.9, bottom=0.15, wspace=0.25)
    return fig


def draw4(rows: list[dict], plt):
    fig, axes = plt.subplots(1, 2, figsize=(WIDTH, 3.0), sharey=True)
    h = rows[0]
    for ax, y in zip(axes, ("2021", "2022")):
        rs = [r for r in rows if r["cohort_year"] == y]
        for r in rs:
            ax.plot(100 * float(r["C"]), 100 * float(r["success_share"]), marker="o" if y == "2021" else "^", ms=3.8,
                    mfc="white", mec=BLUE if y == "2021" else ORANGE, mew=0.8, ls="")
        ax.set_xlim(0, 100)
        ax.set_xlabel(f"C: paid at least once of notified, {y} (%)")
        ax.set_title(f"{'A' if y == '2021' else 'B'}  {y} cohort", loc="left", fontweight="bold")
        ax.grid(color="#eeeeee", lw=0.5)
        ax.set_axisbelow(True)
    axes[0].set_ylabel("Treatment success, DS-TB cohort (%)")
    lo = min(100 * float(r["success_share"]) for r in rows)
    axes[0].set_ylim(math.floor(lo / 10) * 10, 100)
    fig.text(0.08, 0.02, f"Pooled slope on logit(C) {ratio(h['H3'])} (95% CI {rng(ratio(h['H3_lo']), ratio(h['H3_hi']))}), "
             f"{h['H3_label']}; adjusted for the previous year's success (2022 cohort) "
             f"{ratio(h['H3_adjusted_previous_year'])}.\nAn ecological association across units, not a causal estimate.",
             fontsize=6.6, va="bottom")
    fig.subplots_adjust(left=0.08, right=0.985, top=0.9, bottom=0.24, wspace=0.08)
    return fig


DRAW = {1: draw1, 2: draw2, 3: draw3, 4: draw4}


def write(ms_dir: Path, root: Path = ROOT, png: bool = True) -> list[str]:
    plt = setup()
    ex = ms_dir / "exhibits"
    ex.mkdir(parents=True, exist_ok=True)
    out = []
    for k, fn in FIGURES.items():
        rows = fn(root)
        (ex / f"figure{k}_data.csv").write_bytes(data_csv(rows))
        fig = DRAW[k](rows, plt)
        fig.savefig(ex / f"figure{k}.pdf", metadata={"CreationDate": None, "Creator": None, "Producer": None})
        if png:
            fig.savefig(ex / f"figure{k}.png", dpi=200)
        plt.close(fig)
        out.append(f"figure{k}.pdf: {len(rows)} data rows")
    return out


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0], allow_abbrev=False)
    ap.add_argument("--manuscript-dir", default=DEFAULT_MS_DIR)
    a = ap.parse_args(argv)
    d = Path(a.manuscript_dir)
    d = d if d.is_absolute() else ROOT / d
    for ln in write(d):
        print(ln)
    return 0


if __name__ == "__main__":
    sys.exit(main())
