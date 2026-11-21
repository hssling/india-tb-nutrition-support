# Adapted from hssling/india-tb-diabetes-gap v1.0.0 (MIT), tests/test_manuscript_tools.py; modified:
# this paper's exhibits, catalogue, claims, wording and reference rules and its submission set.
"""Tests of the manuscript tooling: the exhibit builders, the submission build's guards and
the manuscript checks. None needs the private manuscript folder, pandoc or Microsoft Word."""
from __future__ import annotations

import re
from pathlib import Path

import pytest

from exhibits import formats, make_figures, make_graphical_abstract, make_tables
from tools import build_submission
from verification import check_docx_tie, check_manuscript_numbers as cmn, mutate_manuscript

ROOT = Path(__file__).resolve().parents[1]


# --------------------------------------------------------------------------------------
# Number formats
# --------------------------------------------------------------------------------------
def test_formats():
    assert formats.count("639964.6") == "639,965"
    assert formats.count(-1234.4) == "−1,234"
    assert formats.pct("0.74012") == "74.0%"
    assert formats.ratio("-0.3053") == "−0.31"
    assert formats.prob(1.0) == "1" and formats.prob(0.0) == "0"
    assert formats.prob(0.9983) == "0.998" and formats.prob(0.0004) == "<0.001"
    assert formats.people("639965", "638648.08", "641273.58") == "639,965 (638,648 to 641,274)"
    assert formats.inr_bn("3839790000") == "INR 3.84 billion"
    assert formats.and_list(["A", "B", "C"]) == "A, B and C" and formats.and_list([]) == "none"
    assert formats.day("2026-11-21T20:28:47Z") == "21 November 2026"


# --------------------------------------------------------------------------------------
# Exhibits: every cell built from outputs/
# --------------------------------------------------------------------------------------
def test_tables_build_from_outputs():
    tables = make_tables.build(ROOT)
    assert [t.label for t in tables] == ["Table 1"] + [f"Table S{k}" for k in range(1, 15)]
    for t in tables:
        assert t.rows and t.notes
        for r in t.rows:
            assert len(r) == len(t.header), t.label
            assert not any("|" in c for c in r)
    md = make_tables.render_md(tables)
    assert md == make_tables.render_md(make_tables.build(ROOT))  # deterministic
    h3 = next(r for r in tables[0].rows if r[0] == "H3, treatment success")
    assert h3[-1].startswith("supported")
    assert next(r for r in tables[0].rows if r[0] == "H1")[-1].startswith("not established")


def test_table_s6_tiers_match_priority_output():
    pr = [r for r in formats.read_csv(ROOT, "outputs/priority.csv")
          if r["spec"] == "unweighted" and r["year"] == "2023" and r["tier"] == "act now"]
    s6 = next(t for t in make_tables.build(ROOT) if t.label == "Table S6")
    act = sorted(r[0] for r in s6.rows if r[5].endswith("(act now)"))
    assert act == sorted(r["unit"] for r in pr)


def test_figure_and_graphical_abstract_data():
    for k, fn in make_figures.FIGURES.items():
        rows = fn(ROOT)
        assert rows, k
        assert make_figures.data_csv(rows) == make_figures.data_csv(fn(ROOT))
    assert len(make_figures.fig1_data(ROOT)) == 33
    assert {r["cohort_year"] for r in make_figures.fig4_data(ROOT)} == {"2021", "2022"}
    ga = {r["item"]: r["value"] for r in make_graphical_abstract.ga_data(ROOT)}
    assert ga["units"] == "32" and ga["act now, need-weighted"].count(";") == 4


# --------------------------------------------------------------------------------------
# The number check: catalogue, claims and rules
# --------------------------------------------------------------------------------------
def test_catalogue_and_claims_hold_on_outputs():
    cat = cmn.catalogue(ROOT)
    assert cat["nat.U"][0] == "639,965" and cat["H3.label"][0] == "supported"
    assert cat["H1.label"][0] == "not established" and cat["H3.adj"][0] == "0.03"
    assert cat["date.registration"][0] == "21 November 2026" and cat["reg.commit"][0] == "c1d2f04"
    assert cmn.claims(ROOT) == []


def test_wording_rules():
    ok = ("## Results\n\nC is paid at least once of eligible. The weight is not a count of undernourished TB "
          "patients. H3 is an ecological association. To the author's knowledge, this is the first analysis to do it.\n")
    assert cmn.wording_problems("x.md", ok) == []
    bad = ("## Results\n\nMost were paid. It counts undernourished TB patients. Coverage improved success. Bihar ranked "
           "first. This is the first study of it. The program was analyzed.\n")
    found = " ".join(cmn.wording_problems("x.md", bad))
    for what in ("paid at least once", "undernourished", "causal", "ranking", "'first'", "American"):
        assert what in found


def test_reference_rules():
    text = ("# T\n\n## Introduction\n\nA.^1,2^ B.^3^\n\n## References\n\n"
            "1. A B. T. J 2000;1:1–9. https://doi.org/10.1/a\n\n2. C D. T. J 2000;1:1–9. https://doi.org/10.1/b\n\n"
            "3. E F. T. Place: P; 2000. Available at: https://x.org/a.pdf [accessed 21 November 2026].\n")
    assert cmn.reference_problems(text) == []
    swapped = text.replace("A.^1,2^ B.^3^", "A.^1,3^ B.^2^")
    assert any("first citation" in p for p in cmn.reference_problems(swapped))
    misplaced = text.replace("B.^3^", "B^3^.")
    assert any("after punctuation" in p for p in cmn.reference_problems(misplaced))
    untruncated = text.replace("1–9. https://doi.org/10.1/a", "149–155. https://doi.org/10.1/a")
    assert any("truncated" in p for p in cmn.reference_problems(untruncated))


def test_length_and_structure_rules():
    body = ("# A pre-registered State-level analysis\n\n## Abstract\n\n**Background:** a.\n\n**Methods:** b.\n\n"
            "**Results:** c.\n\n**Conclusions:** d.\n\n**Keywords:** India, Tuberculosis\n\n## Introduction\n\nx\n\n"
            "## Materials and methods\n\nx\n\n## Results\n\nx\n\n## Discussion\n\n### Limitations\n\nx\n\n"
            "### Conclusions\n\nx\n\n## Authors' contributions\n\nx\n\n## Acknowledgements\n\nx\n\n## Funding\n\nNone.\n\n"
            "## Competing interests\n\nNone declared.\n\n## Ethical approval\n\nNot required.\n\n## Data availability\n\n"
            "x\n\n## References\n\n1. x\n\n## Figure legends\n\nx\n")
    assert cmn.length_problems(body) == []
    assert any("alphabetical" in p for p in cmn.length_problems(body.replace("India, Tuberculosis", "Tuberculosis, India")))
    assert any("abstract" in p for p in cmn.length_problems(body.replace("**Background:** a.", "**Background:** " + "w " * 200)))
    assert any("Limitations" in p for p in cmn.length_problems(body.replace("### Limitations", "### Caveats")))


# --------------------------------------------------------------------------------------
# Guards: no manuscript folder, unknown options, a submitted folder
# --------------------------------------------------------------------------------------
def test_checks_skip_without_the_private_folder(tmp_path, capsys):
    argv = ["--manuscript-dir", str(tmp_path / "absent")]
    assert cmn.main(ROOT, argv) == 0 and "SKIPPED" in capsys.readouterr().out
    assert check_docx_tie.main(ROOT, argv) == 0 and "SKIPPED" in capsys.readouterr().out
    assert mutate_manuscript.main(argv, ROOT) == 0 and "SKIPPED" in capsys.readouterr().out
    assert cmn.main(ROOT, argv + ["--bogus"]) == 1


def test_number_check_fails_when_phrases_are_missing(tmp_path, capsys):
    (tmp_path / cmn.MS_NAME).write_text("# T\n", encoding="utf-8")
    assert cmn.main(ROOT, ["--manuscript-dir", str(tmp_path)]) == 1
    assert "is missing" in capsys.readouterr().out


def test_build_rejects_unknown_options_and_bad_doi(tmp_path):
    with pytest.raises(SystemExit) as e:
        build_submission.main(["--manuscript-dir", str(tmp_path), "--bogus"])
    assert e.value.code == 2
    with pytest.raises(SystemExit) as e:
        build_submission.main(["--manuscript-dir", str(tmp_path), "--do", "10.5281/zenodo.1"])  # no abbreviations
    assert e.value.code == 2
    with pytest.raises(SystemExit) as e:
        build_submission.main(["--manuscript-dir", str(tmp_path), "--doi", "10.1000/xyz"])
    assert "--doi must look like" in str(e.value.code)


def test_build_refuses_a_submitted_folder(tmp_path):
    (tmp_path / "submission").mkdir()
    (tmp_path / "submission" / "SUBMITTED_2026-11-22.txt").write_text("sent", encoding="utf-8")
    with pytest.raises(SystemExit) as e:
        build_submission.main(["--manuscript-dir", str(tmp_path), "--no-word"])
    assert "refusing to write" in str(e.value.code)
    assert not (tmp_path / "submission" / check_docx_tie.MANUSCRIPT).exists()
    (tmp_path / "submission" / "SUBMITTED_2026-11-22.txt").unlink()
    (tmp_path / "SUBMITTED_note.md").write_text("sent", encoding="utf-8")
    with pytest.raises(SystemExit) as e:
        build_submission.main(["--manuscript-dir", str(tmp_path), "--no-word"])
    assert "refusing to write" in str(e.value.code)


def test_doi_placeholder_is_filled_everywhere():
    md = "x 10.5281/zenodo.XXXXXXX y https://doi.org/10.5281/zenodo.XXXXXXX"
    assert build_submission.with_doi(md, "10.5281/zenodo.123") == "x 10.5281/zenodo.123 y https://doi.org/10.5281/zenodo.123"
    assert build_submission.with_doi(md, None) == md


def test_reference_entries_stay_literal():
    md = "## References\n\n1. A. T [software]. Zenodo; 2026.\n\n12. B. Available at: u [accessed 1 May 2026].\n"
    out = build_submission.escape_refs(md)
    assert "1\\. A." in out and "12\\. B." in out and "\\[software\\]" in out


def test_docx_tie_normalisation_and_md_units():
    units = check_docx_tie.md_units("## Results\n\n**H1** was 0.02\n(95% CI).^3^\n\n| a | b |\n|---|---|\n| 1 | 2 |\n\n"
                                    "1. Ref one.\n2. Ref two.\n")
    assert units == ["Results", "H1 was 0.02 (95% CI).^3^", "a | b", "1 | 2", "1. Ref one.", "2. Ref two."]
    assert check_docx_tie.norm("doi 10.5281/zenodo.123") == check_docx_tie.norm("doi 10.5281/zenodo.XXXXXXX")
    assert check_docx_tie.norm("10.5281/zenodo.24411057") != check_docx_tie.norm("10.5281/zenodo.XXXXXXX")


def test_mutation_sweep_skips_references():
    text = "# Title 2023\n\n## Abstract\n\nA 92.5%.\n\n## References\n\n1. Y 12 (2000) 1.\n"
    toks = [text[a:b] for a, b in mutate_manuscript.md_token_spans(text)]
    assert toks == ["2023", "92.5"]
    assert len({m[0] for m in mutate_manuscript.MUTATIONS}) == len(mutate_manuscript.MUTATIONS)
    assert all(re.fullmatch(r"\d+[a-z]", m[0]) for m in mutate_manuscript.MUTATIONS)


def test_guidance_rule_uses_existing_outputs_only():
    assert make_tables.guidance("account-led", "lower priority", 0.5)[0].startswith("Account seeding")
    assert make_tables.guidance("payment-led", "act now", 0.7)[1].startswith("Priority for Ni-kshay Mitra")
    assert make_tables.guidance("mixed", "lower priority", 1.2)[1] == "Need weight above the mean"
    s14 = next(t for t in make_tables.build(ROOT) if t.label == "Table S14")
    cl = {r["unit"]: r["class"] or make_tables.DASH for r in formats.read_csv(ROOT, "outputs/chain_class.csv")
          if r["spec"] == "p75" and r["year"] == "2023"}
    assert {r[0]: r[1] for r in s14.rows} == cl
