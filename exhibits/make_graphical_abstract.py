# Adapted from hssling/india-tb-diabetes-gap v1.0.0 (MIT), exhibits/make_graphical_abstract.py;
# modified: drawn from outputs/ only for this paper (the 2023 national payment chain, where people
# are lost, the act-now units and the illustrative budget), at the journal's 5:2 landscape shape in
# a sans-serif font of 12 to 16 pt, with no caption.
"""Draw the graphical abstract from outputs/ into <manuscript folder>/exhibits/.

Run as: python -I exhibits/make_graphical_abstract.py [--manuscript-dir DIR]   (default: manuscript)

Writes graphical_abstract.pdf (vector, Arial), graphical_abstract.png (preview) and
graphical_abstract_data.csv (every value it prints, read from outputs/; the number check
regenerates the CSV). The page is 10 x 4 inches (254 x 101.6 mm, 5:2 landscape), so the build's
300 dpi TIFF is 3000 x 1200 pixels, above the journal's minimum of 127 x 50 mm; the text is
Arial at 12 to 16 pt at that size.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from exhibits.formats import MAIN_YEAR, count, inr_bn, national, one, pct, read_csv  # noqa: E402
from exhibits.make_figures import BLUE, DARK, GREY, ORANGE, data_csv, setup  # noqa: E402

DEFAULT_MS_DIR = "manuscript"
SIZE = (10.0, 4.0)  # inches: 5:2 landscape


def ga_data(root: Path) -> list[dict]:
    """(item, value) rows: every value the graphical abstract prints."""
    n = national(read_csv(root, "outputs/chain.csv"), MAIN_YEAR)
    rows = [{"item": "units", "value": n["n_units_C"]}, {"item": "A", "value": n["A"]}, {"item": "P", "value": n["P"]},
            {"item": "C", "value": n["C"]}, {"item": "U", "value": n["U"]}, {"item": "U_acc", "value": n["U_acc"]},
            {"item": "U_pay", "value": n["U_pay"]}]
    cl = [r["class"] for r in read_csv(root, "outputs/chain_class.csv")
          if r["year"] == MAIN_YEAR and r["spec"] == "p75" and r["class"]]
    for c in ("payment-led", "account-led", "mixed"):
        rows.append({"item": f"class {c}", "value": str(cl.count(c))})
    pr = [r for r in read_csv(root, "outputs/priority.csv") if r["year"] == MAIN_YEAR and r["spec"] == "need_weighted_sex_weighted"]
    rows.append({"item": "act now, need-weighted", "value": "; ".join(sorted(r["unit"] for r in pr if r["tier"] == "act now"))})
    rows.append({"item": "budget", "value": one(read_csv(root, "outputs/budget.csv"), "main", spec="main")["cost"]})
    return rows


def draw(rows: list[dict], plt):
    v = {r["item"]: r["value"] for r in rows}
    fig = plt.figure(figsize=SIZE)
    fig.text(0.02, 0.91, f"Who misses India's TB nutrition payment? States and UTs, {MAIN_YEAR}", fontsize=16,
             fontweight="bold", va="center")
    # Panel 1: the national chain
    fig.text(0.02, 0.76, "The payment chain", fontsize=14, fontweight="bold", va="center")
    steps = [("Bank details available", float(v["A"]), BLUE), ("Paid at least once", float(v["C"]), BLUE)]
    for i, (lab, share, col) in enumerate(steps):
        y = 0.62 - i * 0.2
        fig.text(0.02, y, lab, fontsize=12, va="center")
        ax = fig.add_axes((0.02, y - 0.12, 0.3, 0.07))
        ax.barh(0, 1.0, height=1, color="#e6eef7", edgecolor="none")
        ax.barh(0, share, height=1, color=col, edgecolor="none")
        ax.text(0.02, 0, pct(share), fontsize=13, fontweight="bold", va="center", color="white")
        ax.set_xlim(0, 1)
        ax.set_ylim(-0.5, 0.5)
        ax.axis("off")
    fig.text(0.02, 0.13, f"of eligible beneficiaries, {v['units']} units with data", fontsize=12, color=GREY, va="center")
    # Panel 2: where they are lost
    fig.text(0.37, 0.76, "Not paid at least once", fontsize=14, fontweight="bold", va="center")
    fig.text(0.37, 0.61, count(v["U"]), fontsize=16, fontweight="bold", color=ORANGE, va="center")
    fig.text(0.37, 0.48, f"{count(v['U_acc'])} before bank details", fontsize=12, va="center", color=DARK)
    fig.text(0.37, 0.39, f"{count(v['U_pay'])} after bank details", fontsize=12, va="center", color=DARK)
    fig.text(0.37, 0.26, f"{v['class payment-led']} units payment-led, {v['class account-led']} account-led,\n"
             f"{v['class mixed']} mixed", fontsize=12, va="center", color=DARK, linespacing=1.2)
    # Panel 3: act now
    fig.text(0.69, 0.76, "Act now (tiers, not ranks)", fontsize=14, fontweight="bold", va="center")
    names = v["act now, need-weighted"].split("; ")
    fig.text(0.69, 0.66, "\n".join(names), fontsize=12, va="top", linespacing=1.25)
    fig.text(0.69, 0.22, "Punjab's 2023 row: a probable\nreporting anomaly, to be verified", fontsize=12, color=GREY,
             va="center", linespacing=1.2)
    fig.text(0.02, 0.04, f"Cost of paying them all: about {inr_bn(v['budget'])} (INR 1,000 a month for 6 months; "
             "illustrative)", fontsize=12, color=GREY, va="center")
    return fig


def write(ms_dir: Path, root: Path = ROOT) -> str:
    plt = setup()
    ex = ms_dir / "exhibits"
    ex.mkdir(parents=True, exist_ok=True)
    rows = ga_data(root)
    (ex / "graphical_abstract_data.csv").write_bytes(data_csv(rows))
    fig = draw(rows, plt)
    fig.savefig(ex / "graphical_abstract.pdf", metadata={"CreationDate": None, "Creator": None, "Producer": None})
    fig.savefig(ex / "graphical_abstract.png", dpi=100)
    plt.close(fig)
    return f"graphical_abstract.pdf: {len(rows)} values"


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0], allow_abbrev=False)
    ap.add_argument("--manuscript-dir", default=DEFAULT_MS_DIR)
    a = ap.parse_args(argv)
    d = Path(a.manuscript_dir)
    print(write(d if d.is_absolute() else ROOT / d))
    return 0


if __name__ == "__main__":
    sys.exit(main())
