# Adapted from hssling/india-tb-diabetes-gap v1.0.0 (MIT), verification/check_all.py.
# Changes: the steps of this repository (analysis plan section 10.3); the manuscript steps
# (check_manuscript_numbers and check_docx_tie) are skipped until manuscript/manuscript.md exists
# (the manuscript is private and git-ignored).
"""Run the whole verification (analysis plan section 10.3).

Run as: python -I verification/check_all.py   (steps run from the repository root)

Steps, each a `python -I ...` subprocess:
1. pytest -q
2. check_plan_order          registration order; the plan text above section 12 unchanged
3. check_deviations          every deviation / post hoc / exploratory label has a dated entry
4. check_extraction_totals   extracted tables against their printed totals; coarsening
5. check_rounding            no count is derived from a percentage (plan 8.9)
6. check_outputs             independent standard-library recompute
7. check_rerun               byte-for-byte rerun of the extraction and of outputs/
8. check_manuscript_numbers  }  SKIP until manuscript/manuscript.md exists (the manuscript is
9. check_docx_tie            }  private and git-ignored)

Each step prints PASS, FAIL or SKIP. A step that exits 0 and prints only lines beginning
"SKIPPED" counts as skipped; one that also prints other lines passes, with the number of
skipped parts noted (check_rerun without data_raw/). Prints "N/N checks passed (k skipped)";
exits 1 on any FAIL.
"""
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PY = [sys.executable, "-I"]
MANUSCRIPT_DIR = "manuscript"
MANUSCRIPT = Path(MANUSCRIPT_DIR) / "manuscript.md"

STEPS = [
    ("pytest -q", PY + ["-m", "pytest", "-q", "-p", "no:cacheprovider"]),
    ("check_plan_order", PY + ["verification/check_plan_order.py"]),
    ("check_deviations", PY + ["verification/check_deviations.py"]),
    ("check_extraction_totals", PY + ["verification/check_extraction_totals.py"]),
    ("check_rounding", PY + ["verification/check_rounding.py"]),
    ("check_outputs", PY + ["verification/check_outputs.py"]),
    ("check_rerun", PY + ["verification/check_rerun.py"]),
    ("check_manuscript_numbers", PY + ["verification/check_manuscript_numbers.py",
                                       "--manuscript-dir", MANUSCRIPT_DIR]),
    ("check_docx_tie", PY + ["verification/check_docx_tie.py", "--manuscript-dir", MANUSCRIPT_DIR]),
]
MANUSCRIPT_STEPS = ("check_manuscript_numbers", "check_docx_tie")


def run(cmd: list[str]) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True, encoding="utf-8",
                          errors="replace")


def tail(text: str, n: int = 15) -> str:
    return "\n".join("    " + ln for ln in text.strip().splitlines()[-n:])


def skip_reason(name: str) -> str | None:
    """Why a manuscript step is skipped, or None when it must run."""
    if name in MANUSCRIPT_STEPS and not (ROOT / MANUSCRIPT).exists():
        return f"SKIPPED: {MANUSCRIPT.as_posix()} does not exist"
    return None


def main() -> int:
    tally = {"passed": 0, "failed": 0, "skipped": 0}
    for name, cmd in STEPS:
        why = skip_reason(name)
        if why is not None:
            tally["skipped"] += 1
            print(f"[SKIP] {name}: {why}", flush=True)
            continue
        if cmd[2].endswith(".py") and not (ROOT / cmd[2]).exists():
            tally["failed"] += 1
            print(f"[FAIL] {name}: {cmd[2]} does not exist", flush=True)
            continue
        r = run(cmd)
        out = r.stdout + r.stderr
        lines = [ln for ln in out.strip().splitlines() if ln.strip()]
        if r.returncode != 0:
            tally["failed"] += 1
            print(f"[FAIL] {name}\n{tail(out)}", flush=True)
        elif lines and all(ln.startswith("SKIPPED") for ln in lines):
            tally["skipped"] += 1
            print(f"[SKIP] {name}\n{tail(out)}", flush=True)
        else:
            tally["passed"] += 1
            part = sum(ln.startswith("SKIPPED") for ln in lines)
            note = f" ({part} part(s) skipped: see the step's output)" if part else ""
            print(f"[PASS] {name}: {lines[-1] if lines else ''}{note}", flush=True)
    total = tally["passed"] + tally["failed"]
    note = f" ({tally['skipped']} skipped)" if tally["skipped"] else ""
    print(f"\n{tally['passed']}/{total} checks passed{note}")
    return 1 if tally["failed"] else 0


if __name__ == "__main__":
    sys.exit(main())
