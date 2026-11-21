"""The rounding check of analysis plan section 8.9, standard library only.

Run as: python -I verification/check_rounding.py [--root DIR]

The plan moves each count that is back-calculated from a printed percentage by half a unit
of the last printed digit, reruns, and requires every tier, class and label to stay the
same. This check shows that the rule has nothing to act on, and that outputs/rounding_check.csv
says so:

1. No file of data/extracted/ carries the flag ``derived_from_percent``.
2. In every extracted cell file (npy_cells.csv, outcomes_cells.csv, sector_cells.csv) every
   non-empty ``value`` is the count part of the cell as printed (the leading number of
   ``cell_printed``): no value was computed from a percentage.
3. outputs/rounding_check.csv names every comparison the plan lists (tiers, classes, the
   H1, H2 and H3 labels, the falling-coverage flags), each with "no derived counts" and the
   result "unchanged".

If a count were derived, the check fails: the rerun of section 8.9 must then be run and its
differences reported in section 12. Exit 1 on any failure.
"""
import argparse
import csv
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CELL_FILES = ("npy_cells.csv", "outcomes_cells.csv", "sector_cells.csv")
DERIVED = "derived_from_percent"
COMPARED = ("every tier", "every class", "every H1, H2 and H3 label",
            "the falling-coverage flags")
LEAD = re.compile(r"^\s*([\d,]+)")


def read(path: Path) -> list[dict]:
    with open(path, encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def problems(root: Path = ROOT) -> tuple[list[str], list[str]]:
    bad: list[str] = []
    ok: list[str] = []
    ex = root / "data" / "extracted"
    flagged = []
    for p in sorted(ex.glob("*.csv")):
        for r in read(p):
            if DERIVED in r.get("flag", ""):
                flagged.append(f"{p.name}: {r.get('unit') or r.get('printed_unit')}")
    bad += [f"a count derived from a percentage ({f}): run the rerun of plan 8.9" for f in
            flagged[:5]]
    n = 0
    for name in CELL_FILES:
        for r in read(ex / name):
            if r["value"] == "":
                continue
            m = LEAD.match(r["cell_printed"])
            n += 1
            if m is None or m.group(1).replace(",", "") != r["value"]:
                bad.append(f"{name}: {r['printed_unit']} {r['field']}: value {r['value']!r} "
                           f"is not the count part of the printed cell "
                           f"{r['cell_printed']!r}")
    rc = read(root / "outputs" / "rounding_check.csv")
    for c in COMPARED:
        rows = [r for r in rc if r["compared"].startswith(c)]
        if len(rows) != 1:
            bad.append(f"rounding_check.csv: {len(rows)} rows for {c!r}")
            continue
        if rows[0]["derived_counts"] != "no derived counts" or rows[0]["result"] != "unchanged":
            bad.append(f"rounding_check.csv: {c!r} is "
                       f"{rows[0]['derived_counts']!r} / {rows[0]['result']!r}")
    if len(rc) != len(COMPARED):
        bad.append(f"rounding_check.csv has {len(rc)} rows, expected {len(COMPARED)}")
    if not bad:
        ok.append(f"no derived counts: {n} extracted counts equal their printed count "
                  f"part; rounding_check.csv lists {len(COMPARED)} comparisons, all "
                  f"'no derived counts' and 'unchanged'")
    return bad, ok


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--root", default=str(ROOT), help="repository root (default: this one)")
    bad, ok = problems(Path(ap.parse_args(argv).root))
    for line in ok:
        print(f"OK: {line}")
    for b in bad:
        print(f"FAIL: {b}")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
