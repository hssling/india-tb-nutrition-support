# Adapted from hssling/india-tb-diabetes-gap v1.0.0 (MIT), verification/check_rerun.py.
# Changes: this repository's extraction modules (itr_npy, itr_outcomes, itr_sector, nfhs) and
# record file (total_checks.csv).
"""Rerun the extraction and the analysis into a temporary folder and compare the results with
data/extracted/ and outputs/ byte for byte (analysis plan sections 10.1 and 10.3). Nothing in
the repository is written.

Run as: python -I verification/check_rerun.py [--root DIR]

1. Extraction (needs data_raw/, which is not distributed; without it this part prints
   SKIPPED): the write_all of src/extract/itr_npy.py, itr_outcomes.py and itr_sector.py,
   src/extract/nfhs.py (nfhs_bmi.csv), and the printed-total record total_checks.csv built
   by check_extraction_totals from the rerun cells. Every file of data/extracted/ must be
   reproduced.
2. Analysis: python -I src/run_all.py --out <tmp>. Every file of outputs/ except README.md
   must be reproduced.

A reproduced file missing from the repository, a committed file not reproduced, or a byte
difference is a failure. Exit 1 on any failure.
"""
import argparse
import csv
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
NOT_GENERATED = {"README.md"}


def _write_dicts(path: Path, rows: list[dict]) -> None:
    """The writer of the printed-total record (csv.DictWriter, LF, the first row's keys)."""
    with open(path, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]), lineterminator="\n")
        w.writeheader()
        w.writerows(rows)


def _read(path: Path) -> list[dict]:
    with open(path, encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def extraction_inputs_present(root: Path) -> bool:
    sys.path.insert(0, str(root))
    from src.extract import itr_npy, itr_outcomes, itr_sector, nfhs  # noqa: PLC0415
    need = {s.source_file for m in (itr_npy, itr_outcomes, itr_sector)
            for s in m.SPECS.values()} | {nfhs.PHASE1, nfhs.PHASE2}
    return all((root / f).is_file() for f in need)


def rerun_extraction(root: Path, tmp: Path) -> dict[str, Path]:
    """Rerun the extraction from the PDFs into ``tmp``; file name -> path."""
    sys.path.insert(0, str(root))
    from src.extract import annex, itr_npy, itr_outcomes, itr_sector, nfhs  # noqa: PLC0415
    from verification import check_extraction_totals as cet  # noqa: PLC0415

    tmp.mkdir(parents=True, exist_ok=True)
    made: dict[str, Path] = {}
    for mod in (itr_npy, itr_outcomes, itr_sector):
        made.update({p.name: p for p in mod.write_all(mod.read_all(), tmp).values()})
    annex.write_csv(tmp / nfhs.NFHS_CSV.name, nfhs.COLS, nfhs.build(nfhs.read_all()))
    made[nfhs.NFHS_CSV.name] = tmp / nfhs.NFHS_CSV.name
    checks: list[dict] = []
    for cells_name, _panel, _year, _mod, _n in cet.GROUPS:
        checks += cet.printed_totals(_read(made[cells_name]))
    checks += cet.sex_totals(_read(made["tb_sex_2022.csv"]))
    _write_dicts(tmp / "total_checks.csv", checks)
    made["total_checks.csv"] = tmp / "total_checks.csv"
    return made


def rerun_analysis(root: Path, tmp: Path) -> dict[str, Path]:
    """Run src/run_all.py from ``root`` into ``tmp``; file name -> path."""
    tmp.mkdir(parents=True, exist_ok=True)
    r = subprocess.run([sys.executable, "-I", "src/run_all.py", "--out", str(tmp)], cwd=root,
                       capture_output=True, text=True, encoding="utf-8", errors="replace")
    if r.returncode != 0:
        raise RuntimeError(f"src/run_all.py exited {r.returncode}: {r.stderr.strip()[-500:]}")
    return {p.name: p for p in sorted(tmp.iterdir()) if p.is_file()}


def compare(committed: Path, rel: str, made: dict[str, Path], label: str,
            not_generated: set[str] = frozenset()) -> tuple[list[str], int]:
    """Byte comparison of the committed folder ``rel`` with a rerun; (failures, files
    compared)."""
    names = {p.name for p in committed.iterdir() if p.is_file()} - set(not_generated)
    bad = [f"{rel}/{n} is not reproduced by the {label} rerun"
           for n in sorted(names - set(made))]
    for n in sorted(made):
        if n not in names:
            bad.append(f"the {label} rerun produces {n}, which is not in {rel}/")
        elif made[n].read_bytes() != (committed / n).read_bytes():
            bad.append(f"{rel}/{n} differs from the {label} rerun")
    return bad, len(names)


def problems(root: Path = ROOT) -> tuple[list[str], list[str]]:
    """(failures, notes): notes are OK or SKIPPED lines."""
    bad, notes = [], []
    with tempfile.TemporaryDirectory() as t:
        tmp = Path(t)
        if extraction_inputs_present(root):
            b, n = compare(root / "data" / "extracted", "data/extracted",
                           rerun_extraction(root, tmp / "extracted"), "extraction")
            bad += b
            if not b:
                notes.append(f"OK: all {n} files of data/extracted/ are reproduced byte for "
                             f"byte by the extraction rerun")
        else:
            notes.append("SKIPPED: extraction rerun (data_raw/ is not distributed; run "
                         "python -I tools/fetch_sources.py to restore it)")
        b, n = compare(root / "outputs", "outputs", rerun_analysis(root, tmp / "outputs"),
                       "analysis", NOT_GENERATED)
        bad += b
        if not b:
            notes.append(f"OK: all {n} files of outputs/ (README.md aside) are reproduced "
                         f"byte for byte by python -I src/run_all.py")
    return bad, notes


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--root", default=str(ROOT), help="repository root (default: this one)")
    root = Path(ap.parse_args(argv).root).resolve()
    try:
        bad, notes = problems(root)
    except Exception as e:  # noqa: BLE001  any error is a failed check
        bad, notes = [f"{type(e).__name__}: {e}"], []
    for n in notes:
        print(n)
    for b in bad:
        print(f"FAIL: {b}")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
