# Adapted from hssling/india-tb-diabetes-gap v1.0.0 (MIT), verification/check_deviations.py
# (itself adapted from hssling/india-tb-priority-tool and hssling/india-state-tb-score).
# Changes: the entries of section 12 here are dated headings ("### 2026-11-22. <title>"),
# so an entry is named by its ISO date; the files scanned are this repository's outputs/,
# README.md and data/extracted/.
"""Check that every deviation, post hoc or exploratory label, and every reference to a
section 12 entry, in the outputs, the README and the extracted data is covered by a dated
entry of section 12 of docs/analysis_plan.md (plan sections 10.3 and 12).

Run as: python -I verification/check_deviations.py [--root DIR]

Files scanned: every file under outputs/ (outputs/README.md included), README.md and
data/extracted/*.csv.

1. Every section 12 entry is a heading "### <YYYY-MM-DD>. <title>"; an entry without a valid
   date is a failure. Entries are named by their date (a second entry of the same day is
   "<date>#2").
2. A reference to a specific entry ("section 12, 2026-11-22", "plan 12 (2026-11-22)",
   "§12 2026-11-22") must name an entry that exists.
3. A line labelled "post hoc" or "exploratory" must name, in the same line, an entry whose
   text carries the same label.
4. A line labelled "deviation" must name, in the same line, an entry whose text says
   "deviation", or point to section 12 as a whole ("§12", "section 12", "plan 12" with no
   date) when it is a general pointer (no "post hoc" or "exploratory" label).

Nothing is edited; a label without a covering entry is a failure.
"""
import argparse
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PLAN = Path("docs") / "analysis_plan.md"
HEADING = "## 12. Deviations (dated)"
# Entries logged so far (by date); extend this set when a new dated entry is added.
REQUIRED_ENTRIES = {"2026-11-22"}
ENTRY = re.compile(r"^###\s+(\S+?)\.?\s+(.*)$")
DATE = re.compile(r"^(20\d\d)-(0[1-9]|1[0-2])-(0[1-9]|[12]\d|3[01])$")
# A reference to one entry: "section 12 ... 2026-11-22" (also §12, plan 12, plan_12).
REF = re.compile(r"(?:§\s?|section\s|plan[\s_])12[\s,:(]+(\d{4}-\d{2}-\d{2})", re.I)
# A pointer to the section as a whole (no entry date).
WHOLE = re.compile(r"(?:§\s?|section\s|plan[\s_])12(?![.\d])", re.I)
LABELS = {"post hoc": re.compile(r"post[\s-]hoc", re.I),
          "exploratory": re.compile(r"exploratory", re.I),
          "deviation": re.compile(r"deviation", re.I)}


def entries(plan: str) -> tuple[dict[str, str], list[str]]:
    """(entry date -> its text, problems) for the entries of section 12."""
    lines = plan.splitlines()
    starts = [i for i, ln in enumerate(lines) if ln.strip() == HEADING]
    if len(starts) != 1:
        return {}, [f"{PLAN.as_posix()}: expected one {HEADING!r} heading, found "
                    f"{len(starts)}"]
    out: dict[str, list[str]] = {}
    bad: list[str] = []
    current = None
    for ln in lines[starts[0] + 1:]:
        if ln.startswith("## "):
            break
        m = ENTRY.match(ln)
        if m:
            date = m.group(1)
            if not DATE.match(date):
                bad.append(f"a plan 12 entry has no valid ISO date in its heading "
                           f"(found {date!r})")
                date = f"undated:{ln.strip()[:40]}"
            current, k = date, 2
            while current in out:
                current, k = f"{date}#{k}", k + 1
            out[current] = [ln]
        elif current is not None:
            out[current].append(ln)
        elif ln.strip():
            bad.append(f"text in plan 12 before its first dated entry: {ln.strip()[:60]!r}")
    return {k: "\n".join(v) for k, v in out.items()}, bad


def files(root: Path) -> list[Path]:
    fs = [f for f in sorted((root / "outputs").rglob("*")) if f.is_file()]
    fs += [root / "README.md"] if (root / "README.md").exists() else []
    fs += sorted((root / "data" / "extracted").glob("*.csv"))
    return fs


def problems(root: Path = ROOT) -> tuple[list[str], list[str]]:
    """(failures, descriptions of covered files)."""
    plan = (root / PLAN).read_text(encoding="utf-8")
    ent, bad = entries(plan)
    # The dated entries are append-only: once logged, an entry may never disappear.
    for d in sorted(REQUIRED_ENTRIES - set(ent)):
        bad.append(f"the plan 12 entry of {d} is missing (dated entries are never removed)")
    ok: list[str] = []
    for f in files(root):
        rel = f.relative_to(root).as_posix()
        text = f.read_text(encoding="utf-8", errors="replace")
        n_cov = 0
        unlogged: list[str] = []
        for k, ln in enumerate(text.splitlines(), start=1):
            refs = set(REF.findall(ln))
            labels = [name for name, rx in LABELS.items() if rx.search(ln)]
            if not refs and not labels and not WHOLE.search(ln):
                continue
            missing = sorted(r for r in refs if r not in ent)
            if missing:
                unlogged.append(f"line {k}: names the plan 12 entry of "
                                f"{', '.join(missing)}, which does not exist")
                continue
            for name in labels:
                if any(LABELS[name].search(ent[r]) for r in refs):
                    continue
                if name == "deviation" and WHOLE.search(ln) and not (
                        {"post hoc", "exploratory"} & set(labels)):
                    continue
                unlogged.append(f"line {k}: labelled {name!r} but names no dated plan 12 "
                                f"entry that carries that label")
            n_cov += 1
        if unlogged:
            bad += [f"{rel} {u}" for u in unlogged[:5]]
            if len(unlogged) > 5:
                bad.append(f"{rel}: {len(unlogged) - 5} more such line(s)")
        elif n_cov:
            ok.append(f"{rel} ({n_cov} line(s))")
    return bad, ok


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--root", default=str(ROOT), help="repository root (default: this one)")
    root = Path(ap.parse_args(argv).root)
    try:
        bad, ok = problems(root)
    except Exception as e:  # noqa: BLE001  any error is a failed check
        bad, ok = [f"{type(e).__name__}: {e}"], []
    if bad:
        for b in bad:
            print(f"FAIL: {b}")
        return 1
    ent, _ = entries((root / PLAN).read_text(encoding="utf-8"))
    print(f"OK: {len(ent)} dated plan 12 entr{'y' if len(ent) == 1 else 'ies'}; labelled or "
          f"referring lines in {len(ok)} file(s) are covered: {'; '.join(ok) or 'none'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
