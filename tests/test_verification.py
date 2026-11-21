"""Mutation tests of the verification suite (analysis plan section 10.3;
verification/MUTATIONS.md).

Each test breaks one thing in a temporary copy of the repository (never in the repository
itself) and shows that the check that owns it fails: a headline value, the plan above
section 12 (in a temporary clone), a label, an extracted cell, the need weight, a budget
rate, a class, a Monte Carlo summary, an unlogged deviation or post hoc label, a derived
count, and a file that a rerun does not reproduce.
"""
import ast
import csv
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from src.extract import itr_npy, itr_outcomes, itr_sector, readtable
from verification import (check_all, check_deviations, check_extraction_totals,
                          check_outputs, check_plan_order, check_rerun, check_rounding)

ROOT = Path(__file__).resolve().parents[1]


# ---- helpers -------------------------------------------------------------------------

@pytest.fixture(scope="module")
def committed_problems():
    return check_outputs.problems(ROOT)


@pytest.fixture
def root(tmp_path):
    """A copy of what the content checks read: outputs/, data/extracted/, the plan and the
    README."""
    r = tmp_path / "repo"
    shutil.copytree(ROOT / "outputs", r / "outputs")
    shutil.copytree(ROOT / "data" / "extracted", r / "data" / "extracted")
    (r / "docs").mkdir()
    shutil.copy2(ROOT / "docs" / "analysis_plan.md", r / "docs" / "analysis_plan.md")
    shutil.copy2(ROOT / "README.md", r / "README.md")
    return r


def edit_csv(path: Path, match: dict, column: str, fn) -> None:
    """Apply fn to ``column`` of every row matching ``match``; at least one must match."""
    with open(path, encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        header, rows = reader.fieldnames, list(reader)
    hits = [r for r in rows if all(r[k] == v for k, v in match.items())]
    assert hits, f"no row of {path.name} matches {match}"
    for r in hits:
        r[column] = fn(r[column])
    with open(path, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, header, lineterminator="\n")
        w.writeheader()
        w.writerows(rows)


def fails(root: Path, *needles: str) -> list[str]:
    bad, _ = check_outputs.problems(root)
    assert bad, "check_outputs passed on a mutated copy"
    for n in needles:
        assert any(n in b for b in bad), (n, bad)
    return bad


# ---- the checks pass on the repository ---------------------------------------------------

def test_check_outputs_is_standard_library_only():
    """Plan 10.3: an independent recompute; nothing of src/, no numpy, scipy or tbprio."""
    tree = ast.parse((ROOT / "verification" / "check_outputs.py").read_text(encoding="utf-8"))
    mods = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            mods |= {a.name.split(".")[0] for a in node.names}
        elif isinstance(node, ast.ImportFrom):
            assert node.level == 0, "relative import"
            mods.add(node.module.split(".")[0])
    assert mods and mods <= set(sys.stdlib_module_names), mods
    r = subprocess.run([sys.executable, "-I", "-c",
                        "import runpy, sys; sys.argv = ['x']; "
                        "runpy.run_path('verification/check_outputs.py', run_name='m'); "
                        "print(sorted(m for m in sys.modules if m.split('.')[0] in "
                        "('numpy', 'scipy', 'src', 'tbprio', 'nutpay')))"],
                       cwd=ROOT, capture_output=True, text=True)
    assert r.returncode == 0 and r.stdout.strip() == "[]", r.stdout + r.stderr


def test_check_outputs_passes_on_the_committed_outputs(committed_problems):
    bad, ok = committed_problems
    assert bad == []
    assert [line[:3] for line in ok] == ["(a)", "(b)", "(c)", "(d)", "(e)", "(f)", "(g)"]
    assert "U(2023) = 639965" in ok[0]
    assert "excluding Karnataka" in ok[3]
    assert "H3_success 'supported' (8/8)" in ok[6]


def test_check_deviations_passes():
    bad, ok = check_deviations.problems(ROOT)
    assert bad == []


def test_check_rounding_passes():
    bad, ok = check_rounding.problems(ROOT)
    assert bad == [] and ok


def test_own_irls_matches_the_main_slopes_to_1e_6():
    c = check_outputs.Checker(ROOT)
    c.load_chain()
    c.cohort = {}
    for r in c.outc:
        c.cohort.setdefault((r["unit"], int(r["cohort_year"])), {})[r["measure"]] = \
            check_outputs.integer(r["value"])
    with open(ROOT / "outputs" / "headline.csv", encoding="utf-8", newline="") as fh:
        head = {r["hypothesis"]: r for r in csv.DictReader(fh)}
    for o in check_outputs.OUTCOMES:
        f = c.h3_fit(o, check_outputs.POOLED, check_outputs.NONE)
        assert abs(f["beta"][1] - float(head[f"H3_{o}"]["estimate"])) < 1e-6


def test_exact_beta_functions():
    assert check_outputs.betainc(2.0, 3.0, 0.5) == pytest.approx(0.6875, abs=1e-14)
    assert check_outputs.beta_ppf(0.5, 1.0, 1.0) == pytest.approx(0.5, abs=1e-12)
    q = check_outputs.beta_ppf(0.975, 5000.5, 60000.5)
    assert check_outputs.betainc(5000.5, 60000.5, q) == pytest.approx(0.975, abs=1e-12)
    # E[max(0, t - Y)] and E[max(0, t - Y)^2] for Y ~ Uniform(0, 1): t^2/2 and t^3/3
    assert check_outputs.e_short(0.4, 1.0, 1.0) == pytest.approx(0.08, abs=1e-14)
    assert check_outputs.e_short(0.4, 1.0, 1.0, 2) == pytest.approx(0.4 ** 3 / 3, abs=1e-14)


def test_own_rank_statistics():
    x, y = [1, 2, 3, 4, 5], [2, 1, 4, 3, 5]
    assert check_outputs.spearman(x, y) == pytest.approx(0.8)
    assert check_outputs.kendall_b(x, y) == pytest.approx(0.6)
    assert check_outputs.kendall_b([1, 1, 2, 3], [1, 2, 3, 3]) == pytest.approx(
        4 / ((5 * 5) ** 0.5), abs=1e-12)
    lo, hi = check_outputs.fisher(0.5, 20)
    assert lo < 0.5 < hi


def test_label_rule():
    lab = check_outputs.label
    assert lab(0.1, 0.4, [1] * 8, 1) == ("supported", 8)
    assert lab(0.1, 0.4, [1] * 7 + [-1], 1) == ("supported", 7)        # 7 of 8
    assert lab(0.1, 0.4, [1] * 6 + [-1, None], 1) == ("not established", 6)
    assert lab(-0.1, 0.4, [1] * 8, 1) == ("not established", 8)       # interval spans 0
    assert lab(-0.4, -0.1, [-1] * 12, -1) == ("supported", 12)         # direction free


# ---- mutations: check_outputs -----------------------------------------------------------

def test_mutated_headline_value_fails(root):
    edit_csv(root / "outputs" / "headline.csv", {"hypothesis": "H1"}, "estimate",
             lambda v: repr(float(v) + 0.01))
    fails(root, "(e) H1 estimate", "(e) H1 main entry is the headline")


def test_mutated_h3_headline_fails(root):
    edit_csv(root / "outputs" / "headline.csv", {"hypothesis": "H3_success"}, "estimate",
             lambda v: repr(float(v) + 0.01))
    fails(root, "(f) H3_success headline estimate")


def test_mutated_interval_flips_the_label_check(root):
    """The label follows the printed interval: moving it across 0 must be seen."""
    edit_csv(root / "outputs" / "headline.csv", {"hypothesis": "H3_success"}, "lo",
             lambda v: "-0.01")
    fails(root, "(g) H3_success label")


def test_flipped_label_fails(root):
    edit_csv(root / "outputs" / "headline.csv", {"hypothesis": "H3_success"}, "label",
             lambda v: "not established")
    fails(root, "(g) H3_success label")


def test_flipped_label_in_spec_grid_fails(root):
    edit_csv(root / "outputs" / "spec_grid.csv", {"hypothesis": "H1"}, "label",
             lambda v: "supported")
    fails(root, "(g) H1 spec_grid label")


def test_spec_curve_sign_flip_fails(root):
    edit_csv(root / "outputs" / "spec_curve.csv",
             {"hypothesis": "H1", "weighting": "sex_weighted", "year": "2021"}, "sign",
             lambda v: "-1" if v == "1" else "1")
    fails(root, "(e) H1 {'weighting': 'sex_weighted', 'year': 2021} sign")


def test_altered_h3_entry_fails(root):
    edit_csv(root / "outputs" / "spec_curve.csv",
             {"hypothesis": "H3_success", "year_set": "2022",
              "adjustment": "previous-year success"}, "estimate",
             lambda v: repr(float(v) + 0.01))
    fails(root, "(f) H3_success 2022 / previous-year success estimate")


def test_changed_extracted_cell_fails_check_outputs(root):
    edit_csv(root / "data" / "extracted" / "npy_panel.csv",
             {"unit": "Bihar", "year": "2023", "measure": "paid"}, "value",
             lambda v: str(int(v) + 1))
    fails(root, "(a) Bihar 2023 Q", "(a) Bihar 2023 C")


def test_changed_extracted_cell_fails_check_extraction_totals():
    cells = check_extraction_totals._read("npy_cells.csv")
    assert readtable.unrecorded_gaps(check_extraction_totals.printed_totals(cells),
                                     itr_npy.RECORDED_GAPS) == []
    r = next(r for r in cells if r["printed_unit"] == "Bihar" and r["value"].isdigit())
    r["value"] = str(int(r["value"]) + 1)
    assert readtable.unrecorded_gaps(check_extraction_totals.printed_totals(cells),
                                     itr_npy.RECORDED_GAPS)


def test_changed_panel_cell_fails_the_coarsening_check():
    cells = check_extraction_totals._read("npy_cells.csv")
    panel = check_extraction_totals._read("npy_panel.csv")
    specs = {s.year: s for s in itr_npy.SPECS.values()}
    assert check_extraction_totals.coarsening(cells, panel, "year", specs, 330) == []
    r = next(r for r in panel if r["unit"] == "Bihar" and r["year"] == "2023"
             and r["measure"] == "paid")
    r["value"] = str(int(r["value"]) + 1)
    assert any("2023 paid" in b
               for b in check_extraction_totals.coarsening(cells, panel, "year", specs, 330))


def test_changed_outcome_and_sector_cells_fail_their_totals():
    for name, mod in (("outcomes_cells.csv", itr_outcomes), ("sector_cells.csv", itr_sector)):
        cells = check_extraction_totals._read(name)
        assert readtable.unrecorded_gaps(check_extraction_totals.printed_totals(cells),
                                         mod.RECORDED_GAPS) == []
        r = next(r for r in cells if r["printed_unit"] == "Bihar" and r["value"].isdigit())
        r["value"] = str(int(r["value"]) + 1)
        assert readtable.unrecorded_gaps(check_extraction_totals.printed_totals(cells),
                                         mod.RECORDED_GAPS)


def test_changed_nfhs_percentage_fails(root):
    edit_csv(root / "data" / "extracted" / "nfhs_bmi.csv", {"unit": "Kerala", "sex": "women"},
             "bmi_below_normal_pct", lambda v: f"{float(v) + 0.1:.1f}")
    fails(root, "(b) Kerala sex_weighted w_u", "(b) Kerala sex_weighted wt_u")


def test_altered_wt_u_fails(root):
    edit_csv(root / "outputs" / "need_weight.csv", {"unit": "Gujarat", "spec": "sex_weighted"},
             "wt_u_relative_need_weight", lambda v: repr(float(v) * 1.001))
    fails(root, "(b) Gujarat sex_weighted wt_u")


def test_altered_n_bar_fails(root):
    edit_csv(root / "outputs" / "need_weight.csv", {"unit": "Goa", "spec": "women"}, "n_bar",
             lambda v: repr(float(v) + 0.001))
    fails(root, "(b) Goa women n_bar")


def test_altered_budget_rate_fails(root):
    edit_csv(root / "outputs" / "budget.csv", {"item": "main: U(2023) x rate x months"},
             "rate_per_month", lambda v: "1100")
    fails(root, "(d) main: main rate_per_month")


def test_altered_budget_rate_and_cost_together_fail(root):
    """A rate changed with its cost kept consistent is still not the plan's Rs 1,000."""
    edit_csv(root / "outputs" / "budget.csv", {"item": "main: U(2023) x rate x months"},
             "rate_per_month", lambda v: "1100")
    edit_csv(root / "outputs" / "budget.csv", {"item": "main: U(2023) x rate x months"},
             "cost", lambda v: str(639965 * 1100 * 6))
    fails(root, "(d) main: main rate_per_month", "(d) main: main cost")


def test_altered_budget_count_and_benchmark_fail(root):
    edit_csv(root / "outputs" / "budget.csv", {"item": "U(2023), people not paid at least once"},
             "count", lambda v: str(int(v) + 1))
    edit_csv(root / "outputs" / "budget.csv",
             {"item": "benchmark scenario: increment over the current number paid at least "
                      "once", "spec": "p75"}, "C_bench", lambda v: repr(float(v) + 0.001))
    fails(root, "(d) U(2023) count", "(d) benchmark scenario: increment p75 C_bench")


def test_altered_unit_unpaid_count_fails(root):
    edit_csv(root / "outputs" / "chain.csv", {"unit": "Bihar", "year": "2023", "level": "unit"},
             "U", lambda v: str(int(v) + 1))
    fails(root, "(a) Bihar 2023 U")


def test_altered_national_value_fails(root):
    edit_csv(root / "outputs" / "chain.csv", {"level": "national", "year": "2022"}, "C_lo",
             lambda v: repr(float(v) - 0.001))
    fails(root, "(a) national 2022 C_lo")


def test_flipped_class_fails(root):
    edit_csv(root / "outputs" / "shortfall.csv",
             {"unit": "Bihar", "year": "2023", "spec": "p75"}, "class", lambda v: "payment-led")
    fails(root, "(c) Bihar 2023 p75 class from its printed shares")


def test_altered_shortfall_fails(root):
    edit_csv(root / "outputs" / "shortfall.csv",
             {"unit": "Bihar", "year": "2023", "spec": "p75"}, "S_acc",
             lambda v: repr(float(v) + 1.0))
    fails(root, "(c) Bihar 2023 p75 S_acc")


def test_monte_carlo_summaries_are_checked(root):
    """A draw-based value moved beyond its Monte Carlo tolerance fails."""
    edit_csv(root / "outputs" / "shortfall.csv",
             {"unit": "Bihar", "year": "2023", "spec": "p75"}, "S_acc_mean",
             lambda v: repr(float(v) * 1.05))
    edit_csv(root / "outputs" / "budget.csv", {"item": "U(2023), people not paid at least once"},
             "count_draw_mean", lambda v: repr(float(v) + 100.0))
    fails(root, "(c) Bihar 2023 p75 S_acc_mean", "(d) U(2023) draw mean")


def test_check_outputs_main_exits_1_on_a_mutation(root, capsys):
    edit_csv(root / "outputs" / "headline.csv", {"hypothesis": "H3_success"}, "label",
             lambda v: "not established")
    assert check_outputs.main(["--root", str(root)]) == 1
    assert "FAIL: (g) H3_success label" in capsys.readouterr().out


# ---- mutations: check_plan_order (temporary clone) ----------------------------------------

def test_edit_above_section12_fails_in_a_clone(tmp_path):
    clone = tmp_path / "clone"
    subprocess.run(["git", "clone", "-q", str(ROOT), str(clone)], check=True)
    assert check_plan_order.problems(clone) == []
    plan = clone / "docs" / "analysis_plan.md"
    text = plan.read_bytes().decode("utf-8")
    old = "10,000 draws"
    assert text.index(old) < text.index("## 12. Deviations (dated)")
    plan.write_bytes(text.replace(old, "5,000 draws", 1).encode("utf-8"))
    bad = check_plan_order.problems(clone)
    assert len(bad) == 1 and "uncommitted edit" in bad[0], bad
    subprocess.run(["git", "-C", str(clone), "-c", "user.name=m", "-c", "user.email=m@x",
                    "-c", "commit.gpgsign=false", "commit", "-qam",
                    "mutation: edit above section 12"], check=True)
    bad = check_plan_order.problems(clone)
    assert len(bad) == 1 and "above section 12 differs" in bad[0], bad
    assert check_plan_order.main(clone) == 1


def test_edit_below_section12_is_allowed_in_a_clone(tmp_path):
    clone = tmp_path / "clone"
    subprocess.run(["git", "clone", "-q", str(ROOT), str(clone)], check=True)
    plan = clone / "docs" / "analysis_plan.md"
    plan.write_bytes(plan.read_bytes() + b"\n### 2026-11-23. A later dated note\n\nText.\n")
    assert check_plan_order.problems(clone) == []


# ---- mutations: check_deviations --------------------------------------------------------

def _append_line(path: Path, line: str) -> None:
    with open(path, "a", encoding="utf-8", newline="") as f:
        f.write(line + "\n")


@pytest.mark.parametrize("line, ok", [
    ("H9,0.1,,,,,,,post hoc check", False),
    ("H9,0.1,,,,,,,exploratory (plan section 12, 2026-11-22)", False),  # not exploratory
    ("H9,0.1,,,,,,,see plan section 12, 2026-12-31", False),            # no such entry
    ("H9,0.1,,,,,,,a deviation from the plan", False),
    ("H9,0.1,,,,,,,a deviation (plan section 12, 2026-12-31)", False),
    ("H9,0.1,,,,,,,deviations are dated in plan section 12", True),
    ("H9,0.1,,,,,,,see plan section 12, 2026-11-22", True),
])
def test_unlogged_labels_fail(root, line, ok):
    _append_line(root / "outputs" / "headline.csv", line)
    bad, _ = check_deviations.problems(root)
    assert (bad == []) is ok, bad


def test_unlogged_label_in_readme_and_data_flags_fail(root):
    _append_line(root / "README.md", "A further deviation was made in data year 2021.")
    edit_csv(root / "data" / "extracted" / "npy_panel.csv",
             {"unit": "Bihar", "year": "2023", "measure": "paid"}, "flag",
             lambda v: v + ";post-hoc flag")
    bad, _ = check_deviations.problems(root)
    assert any(b.startswith("README.md line") for b in bad), bad
    assert any(b.startswith("data/extracted/npy_panel.csv line") for b in bad), bad


def test_undated_section12_entry_fails(root):
    _append_line(root / "docs" / "analysis_plan.md", "\n### soon. A post hoc analysis\n\nText.")
    bad, _ = check_deviations.problems(root)
    assert any("no valid ISO date" in b for b in bad), bad


def test_removed_section12_entry_fails(root):
    plan = root / "docs" / "analysis_plan.md"
    text = plan.read_text(encoding="utf-8")
    plan.write_text(text.replace("### 2026-11-22.", "### 2026-11-21.", 1), encoding="utf-8")
    bad, _ = check_deviations.problems(root)
    assert any("2026-11-22 is missing" in b for b in bad), bad


def test_post_hoc_line_covered_by_a_dated_post_hoc_entry_passes(root):
    _append_line(root / "docs" / "analysis_plan.md",
                 "\n### 2026-11-23. A post hoc analysis\n\nText.")
    _append_line(root / "outputs" / "headline.csv",
                 "H9,0.1,,,,,,,post hoc (plan section 12, 2026-11-23)")
    bad, _ = check_deviations.problems(root)
    assert bad == []


# ---- mutations: check_rounding ----------------------------------------------------------

def test_derived_count_flag_fails_check_rounding(root):
    edit_csv(root / "data" / "extracted" / "npy_panel.csv",
             {"unit": "Bihar", "year": "2023", "measure": "paid"}, "flag",
             lambda v: v + ";derived_from_percent")
    bad, _ = check_rounding.problems(root)
    assert any("derived from a percentage" in b for b in bad), bad


def test_value_not_the_printed_count_fails_check_rounding(root):
    edit_csv(root / "data" / "extracted" / "sector_cells.csv",
             {"printed_unit": "Bihar", "field": "private", "year": "2023"}, "value",
             lambda v: str(int(v) + 1))
    bad, _ = check_rounding.problems(root)
    assert any("not the count part" in b for b in bad), bad


def test_changed_rounding_result_fails_check_rounding(root):
    edit_csv(root / "outputs" / "rounding_check.csv", {"compared": "every class"}, "result",
             lambda v: "changed")
    bad, _ = check_rounding.problems(root)
    assert any("every class" in b for b in bad), bad


# ---- check_rerun and check_all ----------------------------------------------------------

def test_rerun_compares_every_file_byte_for_byte(tmp_path, monkeypatch):
    for d in ("outputs", "data/extracted"):
        (tmp_path / d).mkdir(parents=True)
    (tmp_path / "outputs" / "a.csv").write_bytes(b"x\n1\n")
    (tmp_path / "outputs" / "README.md").write_bytes(b"not generated\n")
    (tmp_path / "data" / "extracted" / "p.csv").write_bytes(b"p\n")
    made = {"a.csv": b"x\n1\n"}
    extracted = {"p.csv": b"p\n"}

    def fake(files):
        def run(root, tmp):
            tmp.mkdir(parents=True, exist_ok=True)
            for name, data in files.items():
                (tmp / name).write_bytes(data)
            return {name: tmp / name for name in files}
        return run

    monkeypatch.setattr(check_rerun, "rerun_analysis", fake(made))
    monkeypatch.setattr(check_rerun, "rerun_extraction", fake(extracted))
    monkeypatch.setattr(check_rerun, "extraction_inputs_present", lambda root: True)
    bad, notes = check_rerun.problems(tmp_path)
    assert bad == [] and len(notes) == 2 and all(n.startswith("OK") for n in notes)
    made["a.csv"] = b"x\n2\n"
    assert check_rerun.problems(tmp_path)[0] == [
        "outputs/a.csv differs from the analysis rerun"]
    del made["a.csv"]
    assert check_rerun.problems(tmp_path)[0] == [
        "outputs/a.csv is not reproduced by the analysis rerun"]
    made.update({"a.csv": b"x\n1\n", "c.csv": b"c\n"})
    assert check_rerun.problems(tmp_path)[0] == [
        "the analysis rerun produces c.csv, which is not in outputs/"]
    del made["c.csv"]
    extracted["p.csv"] = b"q\n"
    assert check_rerun.problems(tmp_path)[0] == [
        "data/extracted/p.csv differs from the extraction rerun"]
    monkeypatch.setattr(check_rerun, "extraction_inputs_present", lambda root: False)
    bad, notes = check_rerun.problems(tmp_path)
    assert bad == [] and notes[0].startswith("SKIPPED: extraction rerun")


def test_check_all_steps_and_manuscript_skips(tmp_path, monkeypatch):
    names = [n for n, _ in check_all.STEPS]
    assert names == ["pytest -q", "check_plan_order", "check_deviations",
                     "check_extraction_totals", "check_rounding", "check_outputs",
                     "check_rerun", "check_manuscript_numbers"]
    monkeypatch.setattr(check_all, "ROOT", tmp_path)
    for name in check_all.MANUSCRIPT_STEPS:
        assert check_all.skip_reason(name).startswith("SKIPPED")
    assert check_all.skip_reason("check_outputs") is None
    (tmp_path / "manuscript").mkdir()
    (tmp_path / "manuscript" / "manuscript.md").write_text("x", encoding="utf-8")
    assert check_all.skip_reason("check_manuscript_numbers") is None
