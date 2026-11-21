"""Tests of verification/check_plan_order.py on synthetic temporary git repositories
(never the real repository), adapted from hssling/india-tb-diabetes-gap
tests/test_plan_order.py (MIT): the guarded paths are src/nutpay/, data/extracted/ and
outputs/, and the registration record must name a full 40-character SHA."""
import json
import subprocess

import pytest

from verification import check_plan_order

PLAN = "# Plan\n\nBefore.\n\n## 12. Deviations (dated)\n"


def git(repo, *args):
    subprocess.run(["git", "-C", str(repo), "-c", "user.name=t", "-c", "user.email=t@t",
                    "-c", "commit.gpgsign=false", "-c", "core.autocrlf=false", *args],
                   check=True, capture_output=True)


def commit(repo, files, msg):
    for rel, text in files.items():
        p = repo / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(text.encode("utf-8"))
        git(repo, "add", rel)
    git(repo, "commit", "-m", msg)
    return subprocess.run(["git", "-C", str(repo), "rev-parse", "HEAD"], check=True,
                          capture_output=True, text=True).stdout.strip()


def event(sha):
    return json.dumps({"registered_commit": sha, "pushed_at": "2026-11-22T00:00:00Z"})


@pytest.fixture
def repo(tmp_path):
    git(tmp_path, "init", "-q")
    return tmp_path


def test_guarded_paths_are_nutpay_extracted_outputs_and_run_all_with_no_allow_list():
    assert check_plan_order.GUARDED == ("outputs", "data/extracted", "src/nutpay", "src/run_all.py")
    assert check_plan_order.ALLOWED == ()


def test_clean_history_passes_and_section12_edit_is_allowed(repo, capsys):
    reg = commit(repo, {"docs/analysis_plan.md": PLAN}, "plan")
    commit(repo, {"docs/registration_event.json": event(reg)}, "registration event")
    commit(repo, {"docs/analysis_plan.md": PLAN + "\n**23 November 2026.** A deviation.\n"},
           "deviation")
    commit(repo, {"src/nutpay/gaps.py": "x = 1\n", "outputs/gaps.csv": "a\n"}, "estimates")
    assert check_plan_order.problems(repo, reg) == []
    assert check_plan_order.main(repo) == 0
    assert capsys.readouterr().out.startswith("OK:")


def test_missing_registration_event_is_not_registered_yet(repo, capsys):
    commit(repo, {"docs/analysis_plan.md": PLAN}, "plan")
    assert check_plan_order.main(repo) == 1
    out = capsys.readouterr().out
    assert out.startswith("FAIL: NOT REGISTERED YET")
    assert "docs/registration_event.json does not exist" in out


def test_missing_registration_event_fails_even_with_an_otherwise_clean_history(repo, capsys):
    """A missing record never switches the check off, whatever else is in the history."""
    commit(repo, {"docs/analysis_plan.md": PLAN}, "plan")
    commit(repo, {"src/extract/itr_npy.py": "x = 1\n"}, "extraction code")
    assert check_plan_order.main(repo) == 1
    assert "NOT REGISTERED YET" in capsys.readouterr().out


def test_registration_event_without_commit_fails(repo, capsys):
    commit(repo, {"docs/analysis_plan.md": PLAN,
                  "docs/registration_event.json": json.dumps({"pushed_at": "x"})}, "plan")
    assert check_plan_order.main(repo) == 1
    assert "names no registration commit" in capsys.readouterr().out


def test_registration_event_that_is_not_json_fails(repo, capsys):
    commit(repo, {"docs/analysis_plan.md": PLAN,
                  "docs/registration_event.json": "not json\n"}, "plan")
    assert check_plan_order.main(repo) == 1
    assert "is not valid JSON" in capsys.readouterr().out


@pytest.mark.parametrize("named", ["abc1234", "ABCDEF" + "0" * 34, "0" * 39, "0" * 41,
                                   "HEAD", "g" * 40])
def test_registration_record_must_name_a_full_lowercase_sha(repo, capsys, named):
    commit(repo, {"docs/analysis_plan.md": PLAN,
                  "docs/registration_event.json": json.dumps({"registered_commit": named})},
           "plan")
    assert check_plan_order.main(repo) == 1
    assert "not a full 40-character hexadecimal commit SHA" in capsys.readouterr().out


def test_abbreviated_sha_in_an_earlier_record_is_flagged(repo):
    """The anchor comparison is exact: an earlier committed record that named the same
    commit by an abbreviation does not count as naming it."""
    reg = commit(repo, {"docs/analysis_plan.md": PLAN}, "plan")
    commit(repo, {"docs/registration_event.json": event(reg[:7])}, "short record")
    commit(repo, {"docs/registration_event.json": event(reg)}, "full record")
    bad = check_plan_order.problems(repo, reg)
    assert len(bad) == 1 and "the anchor must never move" in bad[0]


def test_full_sha_record_passes_main(repo, capsys):
    reg = commit(repo, {"docs/analysis_plan.md": PLAN}, "plan")
    commit(repo, {"docs/registration_event.json": event(reg)}, "registration event")
    assert len(reg) == 40
    assert check_plan_order.main(repo) == 0
    assert capsys.readouterr().out.startswith("OK:")


def test_unknown_registration_commit_fails(repo, capsys):
    commit(repo, {"docs/analysis_plan.md": PLAN,
                  "docs/registration_event.json": event("0" * 40)}, "plan")
    assert check_plan_order.main(repo) == 1
    assert "does not exist" in capsys.readouterr().out


def test_output_committed_before_registration_is_flagged(repo, capsys):
    commit(repo, {"outputs/headline.csv": "a\n"}, "output first")
    reg = commit(repo, {"docs/analysis_plan.md": PLAN}, "plan")
    commit(repo, {"docs/registration_event.json": event(reg)}, "registration event")
    bad = check_plan_order.problems(repo, reg)
    assert len(bad) == 1 and "not a descendant" in bad[0]
    assert check_plan_order.main(repo) == 1
    assert capsys.readouterr().out.startswith("FAIL: commit")


@pytest.mark.parametrize("module", ["__init__", "chain", "unpaid", "tiers", "trend",
                                    "validate"])
def test_nutpay_module_before_registration_is_flagged(repo, module):
    commit(repo, {f"src/nutpay/{module}.py": "x = 1\n"}, "module first")
    reg = commit(repo, {"docs/analysis_plan.md": PLAN}, "plan")
    bad = check_plan_order.problems(repo, reg)
    assert len(bad) == 1 and "src/nutpay/" in bad[0]


def test_nutpay_module_in_registration_commit_is_flagged(repo):
    reg = commit(repo, {"docs/analysis_plan.md": PLAN, "src/nutpay/gaps.py": "x\n"},
                 "plan+code")
    assert len(check_plan_order.problems(repo, reg)) == 1


def test_extraction_code_before_registration_passes(repo):
    """Extraction code, the source manifest and the verification scripts may precede
    registration; only src/nutpay/, src/run_all.py, data/extracted/ and outputs/ are guarded."""
    commit(repo, {"src/extract/itr_npy.py": "y = 1\n", "data/source_manifest.csv": "p\n",
                  "verification/check_plan_order.py": "z = 1\n"}, "extraction code first")
    reg = commit(repo, {"docs/analysis_plan.md": PLAN}, "plan")
    assert check_plan_order.problems(repo, reg) == []


def test_run_all_before_registration_is_flagged(repo):
    commit(repo, {"src/run_all.py": "w = 1\n"}, "analysis driver first")
    reg = commit(repo, {"docs/analysis_plan.md": PLAN}, "plan")
    bad = check_plan_order.problems(repo, reg)
    assert len(bad) == 1 and "src/run_all.py" in bad[0]


@pytest.mark.parametrize("name", ["npy_panel.csv", "nfhs_bmi.csv", "outcomes_cohorts.csv"])
def test_extracted_data_before_registration_is_flagged(repo, name):
    commit(repo, {f"data/extracted/{name}": "u\n"}, "extracted data first")
    reg = commit(repo, {"docs/analysis_plan.md": PLAN}, "plan")
    bad = check_plan_order.problems(repo, reg)
    assert len(bad) == 1 and "data/extracted/" in bad[0] and "not a descendant" in bad[0]


def test_extracted_data_after_registration_passes(repo):
    reg = commit(repo, {"docs/analysis_plan.md": PLAN}, "plan")
    commit(repo, {"docs/registration_event.json": event(reg)}, "registration event")
    commit(repo, {"data/extracted/npy_panel.csv": "u\n"}, "extraction")
    assert check_plan_order.problems(repo, reg) == []


def test_similarly_named_paths_are_not_guarded(repo):
    """A pathspec matches a directory, not a name prefix: src/nutpay_notes.md and
    outputs_old.txt are outside the guarded directories."""
    commit(repo, {"src/nutpay_notes.md": "n\n", "outputs_old.txt": "o\n",
                  "data/extracted_notes.txt": "e\n"}, "near misses")
    reg = commit(repo, {"docs/analysis_plan.md": PLAN}, "plan")
    assert check_plan_order.problems(repo, reg) == []


def test_allow_listed_module_before_registration_passes(repo):
    commit(repo, {"src/nutpay/panel.py": "x = 1\n"}, "loader first")
    reg = commit(repo, {"docs/analysis_plan.md": PLAN}, "plan")
    assert check_plan_order.problems(repo, reg, allowed=("src/nutpay/panel.py",)) == []


def test_allow_list_does_not_cover_a_second_module_in_the_same_commit(repo):
    commit(repo, {"src/nutpay/panel.py": "x\n", "src/nutpay/validate.py": "y\n"}, "two")
    reg = commit(repo, {"docs/analysis_plan.md": PLAN}, "plan")
    assert len(check_plan_order.problems(repo, reg, allowed=("src/nutpay/panel.py",))) == 1


def test_renamed_nutpay_module_before_registration_is_flagged(repo):
    commit(repo, {"src/scratch.py": "x = 1\n"}, "scratch")
    git(repo, "mv", "src/scratch.py", "src/nutpay_tmp.py")
    git(repo, "commit", "-q", "-m", "rename outside")
    (repo / "src" / "nutpay").mkdir()
    git(repo, "mv", "src/nutpay_tmp.py", "src/nutpay/gaps.py")
    git(repo, "commit", "-q", "-m", "rename into nutpay")
    reg = commit(repo, {"docs/analysis_plan.md": PLAN}, "plan")
    assert len(check_plan_order.problems(repo, reg)) == 1


def test_deleted_output_before_registration_is_still_flagged(repo):
    """An output committed and then deleted before registration is found in the history."""
    commit(repo, {"outputs/gaps.csv": "a\n"}, "output")
    git(repo, "rm", "-q", "outputs/gaps.csv")
    git(repo, "commit", "-q", "-m", "delete output")
    reg = commit(repo, {"docs/analysis_plan.md": PLAN}, "plan")
    assert len(check_plan_order.problems(repo, reg)) == 2


def test_moved_registration_anchor_is_flagged(repo, capsys):
    """The anchor is pinned: a later commit may not re-point the registration record."""
    reg = commit(repo, {"docs/analysis_plan.md": PLAN}, "plan")
    commit(repo, {"docs/registration_event.json": event(reg)}, "registration event")
    commit(repo, {"docs/analysis_plan.md": PLAN.replace("Before.", "Changed.")}, "edit")
    later = commit(repo, {"outputs/x.csv": "a\n"}, "output")
    commit(repo, {"docs/registration_event.json": event(later)}, "move the anchor")
    assert check_plan_order.main(repo) == 1
    assert "the anchor must never move" in capsys.readouterr().out


def test_anchor_moved_and_moved_back_is_flagged(repo):
    """Every committed version of the record is checked, not only the current one."""
    reg = commit(repo, {"docs/analysis_plan.md": PLAN}, "plan")
    commit(repo, {"docs/registration_event.json": event(reg)}, "registration event")
    later = commit(repo, {"README.md": "r\n"}, "readme")
    commit(repo, {"docs/registration_event.json": event(later)}, "move the anchor")
    commit(repo, {"docs/registration_event.json": event(reg)}, "move it back")
    bad = check_plan_order.problems(repo, reg)
    assert len(bad) == 1 and "the anchor must never move" in bad[0]


def test_deleted_then_restored_registration_event_is_flagged(repo):
    reg = commit(repo, {"docs/analysis_plan.md": PLAN}, "plan")
    commit(repo, {"docs/registration_event.json": event(reg)}, "registration event")
    git(repo, "rm", "-q", "docs/registration_event.json")
    git(repo, "commit", "-q", "-m", "delete event")
    commit(repo, {"docs/registration_event.json": event(reg)}, "restore event")
    bad = check_plan_order.problems(repo, reg)
    assert len(bad) == 1 and "names no commit" in bad[0]


def test_old_plan_on_a_branch_merged_after_registration_is_not_a_later_commit(repo):
    """--ancestry-path: a side commit made before registration, merged after it, is not
    one of the commits whose plan text must equal the registered text."""
    commit(repo, {"README.md": "r\n"}, "root")
    git(repo, "checkout", "-q", "-b", "side")
    commit(repo, {"docs/analysis_plan.md": PLAN.replace("Before.", "Draft.")}, "draft plan")
    git(repo, "checkout", "-q", "-")
    reg = commit(repo, {"docs/analysis_plan.md": PLAN}, "plan")
    git(repo, "merge", "-q", "-s", "ours", "side", "-m", "merge, keeping our tree")
    assert check_plan_order.problems(repo, reg) == []


def test_later_commits_use_the_ancestry_path(repo):
    commit(repo, {"README.md": "r\n"}, "root")
    git(repo, "checkout", "-q", "-b", "side")
    side = commit(repo, {"notes.txt": "n\n"}, "side work before registration")
    git(repo, "checkout", "-q", "-")
    reg = commit(repo, {"docs/analysis_plan.md": PLAN}, "plan")
    git(repo, "merge", "-q", "--no-ff", "side", "-m", "merge side")
    later = check_plan_order.later_commits(repo, reg)
    assert side not in later and len(later) == 1


def test_output_on_a_merged_side_branch_is_found_over_the_full_history(repo):
    """History simplification would hide a side-branch commit whose change a merge drops."""
    commit(repo, {"README.md": "r\n"}, "root")
    git(repo, "checkout", "-q", "-b", "side")
    side = commit(repo, {"outputs/headline.csv": "a\n"}, "output on a side branch")
    git(repo, "checkout", "-q", "-")
    git(repo, "merge", "-q", "-s", "ours", "side", "-m", "merge, keeping our tree")
    reg = commit(repo, {"docs/analysis_plan.md": PLAN}, "plan")
    bad = check_plan_order.problems(repo, reg)
    assert any(b.startswith(f"commit {side[:7]} ") for b in bad)
    assert all("not a descendant" in b for b in bad)


def test_output_introduced_by_a_merge_commit_itself_is_flagged(repo):
    """An evil merge (--diff-merges=separate): neither parent has the guarded file; the
    merge commit adds it."""
    commit(repo, {"README.md": "r\n"}, "root")
    git(repo, "checkout", "-q", "-b", "side")
    commit(repo, {"notes.txt": "n\n"}, "side work")
    git(repo, "checkout", "-q", "-")
    commit(repo, {"other.txt": "o\n"}, "main work")
    git(repo, "merge", "-q", "--no-commit", "--no-ff", "side")
    out = repo / "src" / "nutpay"
    out.mkdir(parents=True, exist_ok=True)
    (out / "gaps.py").write_text("x = 1\n", encoding="utf-8")
    git(repo, "add", "src/nutpay/gaps.py")
    git(repo, "commit", "-q", "-m", "merge that adds an estimation module")
    merge = subprocess.run(["git", "-C", str(repo), "rev-parse", "HEAD"], check=True,
                           capture_output=True, text=True).stdout.strip()
    reg = commit(repo, {"docs/analysis_plan.md": PLAN}, "plan")
    bad = check_plan_order.problems(repo, reg)
    assert any(b.startswith(f"commit {merge[:7]} ") for b in bad)


def test_edit_above_section12_is_flagged(repo, capsys):
    reg = commit(repo, {"docs/analysis_plan.md": PLAN}, "plan")
    commit(repo, {"docs/registration_event.json": event(reg)}, "registration event")
    commit(repo, {"docs/analysis_plan.md": PLAN.replace("Before.", "Changed.")}, "edit")
    bad = check_plan_order.problems(repo, reg)
    assert len(bad) == 1 and "above section 12" in bad[0]
    assert check_plan_order.main(repo) == 1
    assert "above section 12 differs" in capsys.readouterr().out


def test_reverted_edit_above_section12_is_still_flagged(repo):
    reg = commit(repo, {"docs/analysis_plan.md": PLAN}, "plan")
    commit(repo, {"docs/analysis_plan.md": PLAN.replace("Before.", "Changed.")}, "edit")
    commit(repo, {"docs/analysis_plan.md": PLAN}, "revert")
    bad = check_plan_order.problems(repo, reg)
    assert len(bad) == 1 and "above section 12" in bad[0]


def test_uncommitted_edit_above_section12_is_flagged(repo):
    reg = commit(repo, {"docs/analysis_plan.md": PLAN}, "plan")
    commit(repo, {"docs/registration_event.json": event(reg)}, "registration event")
    assert check_plan_order.problems(repo, reg) == []
    (repo / "docs" / "analysis_plan.md").write_bytes(
        PLAN.replace("Before.", "Changed.").encode("utf-8"))
    bad = check_plan_order.problems(repo, reg)
    assert len(bad) == 1 and "uncommitted edit" in bad[0]
    # An uncommitted edit below the heading (a new §12 entry being drafted) is allowed.
    (repo / "docs" / "analysis_plan.md").write_bytes((PLAN + "\nnew entry\n").encode("utf-8"))
    assert check_plan_order.problems(repo, reg) == []


def test_line_ending_change_above_section12_is_flagged(repo):
    """Byte identity, not line identity: a CRLF conversion of the frozen text fails."""
    reg = commit(repo, {"docs/analysis_plan.md": PLAN}, "plan")
    commit(repo, {"docs/analysis_plan.md": PLAN.replace("Before.\n", "Before.\r\n")}, "crlf")
    assert len(check_plan_order.problems(repo, reg)) == 1


def test_removed_or_duplicated_section12_heading_is_flagged(repo):
    reg = commit(repo, {"docs/analysis_plan.md": PLAN}, "plan")
    commit(repo, {"docs/analysis_plan.md": PLAN + "\n## 12. Deviations (dated)\n"}, "dup")
    bad = check_plan_order.problems(repo, reg)
    assert len(bad) == 1 and "cannot be read" in bad[0]


def test_registration_not_ancestor_is_flagged(repo):
    reg = commit(repo, {"docs/analysis_plan.md": PLAN}, "plan")
    git(repo, "checkout", "-q", "--orphan", "other")
    commit(repo, {"docs/analysis_plan.md": PLAN}, "unrelated history")
    bad = check_plan_order.problems(repo, reg)
    assert len(bad) == 1 and "not an ancestor" in bad[0]


def test_plan_order_skips_without_git(tmp_path, capsys):
    """A release archive has no .git: the history check is skipped, not failed."""
    assert check_plan_order.main(tmp_path) == 0
    assert capsys.readouterr().out.startswith("SKIPPED: not a git checkout")


def test_real_plan_has_exactly_one_section12_heading_and_lf_endings():
    """The plan in this repository carries the heading the check looks for, once, with
    nothing after it until deviations are recorded."""
    data = (check_plan_order.ROOT / check_plan_order.PLAN).read_bytes()
    assert b"\r" not in data
    assert [ln for ln in data.split(b"\n") if ln == check_plan_order.HEADING] == \
        [check_plan_order.HEADING]


def test_registration_record_with_a_utf8_bom_is_read(repo, capsys):
    reg = commit(repo, {"docs/analysis_plan.md": PLAN}, "plan")
    p = repo / "docs" / "registration_event.json"
    p.write_bytes("\ufeff".encode("utf-8") + event(reg).encode("utf-8"))
    git(repo, "add", "docs/registration_event.json")
    git(repo, "commit", "-m", "event with BOM")
    assert check_plan_order.main(repo) == 0
    assert capsys.readouterr().out.startswith("OK:")
