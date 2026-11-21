"""Extraction: the three pinned Review Focus tests, the printed-total and coarsening
checks, and the structure of the extracted files.

No PDF is needed except for the byte-identical rerun (skipped when data_raw/ is absent):
the rules are tested on synthetic cells, and the committed extracts in data/extracted/
are checked directly.
"""
import csv
from pathlib import Path

import pytest

from src.extract import annex, crosswalk, itr_npy, itr_outcomes, itr_sector, nfhs, readtable
from verification import check_extraction_totals as cet

ROOT = Path(__file__).resolve().parents[1]
EXTRACTED = ROOT / "data" / "extracted"
SIBLING_SEX = ROOT.parent / "tb_diabetes_gap" / "data" / "extracted" / "tb_sex_2022.csv"
SIBLING_CELLS = ROOT.parent / "tb_priority_tool" / "data" / "extracted" / "state_cells.csv"


def _read(name: str) -> list[dict]:
    with open(EXTRACTED / name, encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


# ---- synthetic NPY tables -----------------------------------------------------------

DEFAULT = {"denominator": 1000, "bank_available": 900, "bank_validated": 850, "paid": 700}


def _fake() -> tuple[dict, dict]:
    tables, vals = {}, {}
    for spec in itr_npy.SPECS.values():
        units = list(crosswalk.PRINTED[spec.year]) + [crosswalk.NATIONAL]
        tables[spec.key] = readtable.Table(spec, {}, {u: spec.pages[0] for u in units}, {})
        for u in units:
            for f in spec.fields:
                vals[(spec.key, u, f.name)] = readtable.CellValue(DEFAULT[f.name], [])
    return tables, vals


def _panel(tables, vals) -> dict[tuple[str, int, str], dict]:
    return {(r["unit"], r["year"], r["measure"]): r for r in itr_npy.panel_rows(tables, vals)}


# ---- Review Focus 1: impossible chains ----------------------------------------------

def test_impossible_chain_becomes_na():
    # The rule (plan section 3.6), one step at a time: A = B/D, P = Q/B, C = Q/D.
    assert itr_npy.chain_na(100, 120, 50) == {"A": "bank_available_exceeds_denominator"}
    assert itr_npy.chain_na(100, 50, 60) == {"P": "paid_exceeds_bank_available"}
    # Q above both B and D: P and C are both NA.
    assert itr_npy.chain_na(100, 50, 120) == {"P": "paid_exceeds_bank_available",
                                              "C": "paid_exceeds_denominator"}
    # C is kept when Q <= D, even when B exceeds D (only A is NA).
    assert itr_npy.chain_na(100, 130, 90) == {"A": "bank_available_exceeds_denominator"}
    assert itr_npy.chain_na(100, 100, 100) == {}
    assert itr_npy.chain_na(0, 0, 0) == {"A": "denominator_zero", "P": "bank_available_zero",
                                         "C": "denominator_zero"}
    assert itr_npy.chain_na(None, 10, 5) == {"A": "input_missing", "C": "input_missing"}
    assert itr_npy.chain_na(100, 90, 80, v=95) == {"V": "bank_validated_exceeds_bank_available"}

    # In the panel the printed counts are kept, never turned into NA or changed; the
    # row that carries the numerator is flagged so that the analysis applies the rule.
    tables, vals = _fake()
    vals[("TBAR2022_NPY", "Bihar", "bank_available")] = readtable.CellValue(1500, [])
    vals[("ITR2023_NPY", "Assam", "paid")] = readtable.CellValue(950, [])
    vals[("ITR2024_NPY", "Goa", "bank_validated")] = readtable.CellValue(901, [])
    p = _panel(tables, vals)
    b = p[("Bihar", 2021, "bank_available")]
    assert b["value"] == 1500
    assert "impossible_chain:A:bank_available_exceeds_denominator" in b["flag"].split(";")
    assert "impossible_chain" not in p[("Bihar", 2021, "paid")]["flag"]
    a = p[("Assam", 2022, "paid")]
    assert a["value"] == 950 and a["flag"].split(";") == [
        "impossible_chain:P:paid_exceeds_bank_available"]  # Q <= D: C stays valid
    assert "impossible_chain:V:bank_validated_exceeds_bank_available" in \
        p[("Goa", 2023, "bank_validated")]["flag"]
    flagged = sorted(k for k, r in p.items() if "impossible_chain" in r["flag"])
    assert flagged == [("Assam", 2022, "paid"), ("Bihar", 2021, "bank_available"),
                       ("Goa", 2023, "bank_validated")]
    # na_cells lists the NA steps from the panel alone (a missing input is listed too).
    rows = itr_npy.na_cells([dict(r, value="" if r["value"] is None else r["value"])
                             for r in p.values()])
    assert {(r["unit"], r["year"], r["step"]) for r in rows} == {
        ("Bihar", 2021, "A"), ("Assam", 2022, "P"), ("Goa", 2023, "V")}


def test_a_blank_cell_is_na_not_zero_and_not_imputed():
    tables, vals = _fake()
    for f in ("denominator", "bank_available", "bank_validated"):
        vals[("ITR2024_NPY", "Karnataka", f)] = readtable.CellValue(None, ["na_printed:-"])
    p = _panel(tables, vals)
    r = p[("Karnataka", 2023, "denominator")]
    assert r["value"] is None
    assert {"member_missing:Karnataka", "na_printed:-", "NA:all_members_missing"} <= \
        set(r["flag"].split(";"))
    assert p[("Karnataka", 2023, "paid")]["value"] == 700  # a dash elsewhere does not spread
    # With the chain inputs missing the steps are NA by input_missing, never by a guess.
    rows = itr_npy.na_cells([dict(r, value="" if r["value"] is None else r["value"])
                             for r in p.values()])
    ka = {r["step"]: r["reason"] for r in rows if r["unit"] == "Karnataka"}
    assert ka == {"A": "input_missing", "P": "input_missing", "C": "input_missing",
                  "V": "input_missing"}


def test_member_missing_adds_nothing_and_is_flagged():
    tables, vals = _fake()
    vals[("ITR2023_NPY", "Ladakh", "paid")] = readtable.CellValue(None, ["na_printed:-"])
    vals[("ITR2023_NPY", "Jammu and Kashmir", "paid")] = readtable.CellValue(70, [])
    r = _panel(tables, vals)[("Jammu and Kashmir", 2022, "paid")]
    assert r["value"] == 70
    flags = r["flag"].split(";")
    assert "member_missing:Ladakh" in flags
    assert "merged:Jammu and Kashmir+Ladakh" in flags
    for u in ("Jammu and Kashmir", "Ladakh"):
        vals[("ITR2023_NPY", u, "paid")] = readtable.CellValue(None, [])
    r = _panel(tables, vals)[("Jammu and Kashmir", 2022, "paid")]
    assert r["value"] is None and "NA:all_members_missing" in r["flag"]


def test_real_panel_flags_match_the_rule():
    rows = _read("npy_panel.csv")
    by: dict[tuple[str, int], dict[str, dict]] = {}
    for r in rows:
        by.setdefault((r["unit"], int(r["year"])), {})[r["measure"]] = r
    n_flagged = 0
    for (unit, year), ms in by.items():
        v = {m: (None if r["value"] == "" else int(r["value"])) for m, r in ms.items()}
        na = itr_npy.chain_na(v["denominator"], v["bank_available"], v["paid"],
                              v.get("bank_validated"), with_validated=year == 2023)
        want = sorted((itr_npy.FLAG_ROW[s], f"impossible_chain:{s}:{why}")
                      for s, why in na.items() if why != "input_missing")
        got = sorted((m, f) for m, r in ms.items() for f in r["flag"].split(";")
                     if f.startswith("impossible_chain"))
        assert got == want, (unit, year)
        n_flagged += len(got)
    assert n_flagged >= 1  # Himachal Pradesh 2021, bank details above the denominator
    # No value was changed or blanked by the rule: only printed dashes are empty.
    assert {(r["unit"], r["year"], r["measure"]) for r in rows if r["value"] == ""} == {
        ("Karnataka", "2023", m) for m in ("denominator", "bank_available", "bank_validated")}


# ---- Review Focus 2: percent-only cells ---------------------------------------------

def test_percent_only_cell_derivation_flagged():
    # A printed count is used, not its percentage.
    assert readtable.cell_count(annex.Cell("511", "(96)", "511 (96)"), 534, "x") == (511, [])
    # A percent-only cell: round-half-up(base x % / 100), flagged with its range.
    v, flags = readtable.cell_count(annex.Cell(None, "(52%)", "(52%)"), 606, "x")
    assert v == 315  # 606 x 0.52 = 315.12
    assert flags == ["derived_from_percent:(52%)_of_606_range_313-318"]
    assert readtable.derive_from_percent(202, "(25%)") == (51, 50, 51)  # 50.5 rounds half up
    # A whole-number percent without a % sign, as ITR 2023 prints it.
    assert readtable.derive_from_percent(534, "(96)") == (513, 510, 515)
    with pytest.raises(ValueError, match="no count"):
        readtable.derive_from_percent(10, "(25%)")  # no whole count of 10 prints as 25%
    assert readtable.derive_from_percent(1000, "(91.5)") == (915, 915, 915)
    # No base: an error, not a guess.
    with pytest.raises(ValueError, match="no base"):
        readtable.cell_count(annex.Cell(None, "(52%)", "(52%)"), None, "x")
    # Blank markers are not percentages.
    assert readtable.cell_count(annex.Cell(None, "(NA)", "(NA)"), 606, "x") == (None, [])
    assert readtable.cell_count(annex.Cell(None, None, "-"), 606, "x") == (None, [])
    assert readtable.cell_count(None, 606, "x") == (None, [])

    # Through cell_values: the base is the same row's denominator; the flag reaches the
    # unit's panel row, and the cell enters the rounding check through its interval.
    tables, _ = _fake()
    spec = itr_npy.SPECS[2022]
    t = tables[spec.key]
    for u in list(crosswalk.PRINTED[2022]) + [crosswalk.NATIONAL]:
        t.cells[u] = [annex.Cell("1000", None, "1000"), annex.Cell("900", "(90)", "900 (90)"),
                      annex.Cell("700", "(70)", "700 (70)")]
    t.cells["Goa"] = [annex.Cell("1000", None, "1000"), annex.Cell(None, "(91.5)", "(91.5)"),
                      annex.Cell("700", "(70)", "700 (70)")]
    only = {spec.key: t}
    vals = readtable.cell_values(only)
    cv = vals[(spec.key, "Goa", "bank_available")]
    assert cv.value == 915 and cv.flags == ["derived_from_percent:(91.5)_of_1000_range_915-915"]
    assert vals[(spec.key, "Goa", "paid")].flags == []
    # Derived cells are not mistaken for a printed count in the panel.
    tables2, vals2 = _fake()
    vals2[(spec.key, "Goa", "bank_available")] = cv
    r = _panel(tables2, vals2)[("Goa", 2022, "bank_available")]
    assert r["value"] == 915 and "derived_from_percent" in r["flag"]
    # A percentage printed above 100 is flagged at extraction; the printed count is kept.
    t.cells["Delhi"] = [annex.Cell("1000", None, "1000"), annex.Cell("1014", "(101.4%)", "x"),
                        annex.Cell("700", "(70)", "700 (70)")]
    vals = readtable.cell_values(only)
    assert vals[(spec.key, "Delhi", "bank_available")].value == 1014
    assert vals[(spec.key, "Delhi", "bank_available")].flags == ["percent_above_100:(101.4%)"]
    assert readtable.impossible_cells(vals) == [
        (spec.key, "Delhi", "bank_available", "percent_above_100:(101.4%)")]


def test_no_real_cell_needed_derivation():
    # The inventory found no NPY, outcome or notification cell that prints only a percentage.
    for n in ("npy_panel.csv", "outcomes_panel.csv", "sector_panel.csv",
              "npy_cells.csv", "outcomes_cells.csv", "sector_cells.csv"):
        assert not any("derived_from_percent" in r["flag"] for r in _read(n)), n


def test_real_percent_above_100_cells_are_listed():
    cells = _read("npy_cells.csv")
    listed = {(r["table_key"], r["printed_unit"], r["field"]) for r in cells
              if "percent_above_100" in r["flag"]}
    assert listed == {("TBAR2022_NPY", "Himachal Pradesh", "bank_available"),
                      ("TBAR2022_NPY", crosswalk.DNHDD, "bank_available")}
    # The Annexure 1.2 percentage is the achievement against a target: not an impossible cell.
    assert not any("percent_above_100" in r["flag"] for r in _read("sector_cells.csv"))


# ---- Review Focus 3: unit-name drift --------------------------------------------------

def test_unmatched_unit_raises():
    # An unmatched printed name stops extraction with an error that names it.
    with pytest.raises(KeyError, match="Atlantis"):
        crosswalk.printed_unit("Atlantis", 2022)
    with pytest.raises(KeyError, match="Atlantis"):
        crosswalk.unit_name("Atlantis", 2023)
    with pytest.raises(KeyError, match="Atlantis"):
        crosswalk.nfhs_printed_unit("Atlantis")
    # Capitalisation and "&"/"and" drift are matched by the explicit crosswalk ...
    for raw in ("Andaman & Nicobar Islands", "Andaman and Nicobar Islands",
                "Andaman And Nicobar Islands", "ANDAMAN & NICOBAR ISLANDS"):
        assert crosswalk.unit_name(raw, 2022) == "Andaman and Nicobar Islands"
    assert crosswalk.unit_name("CHANDIGARH", 2021) == "Chandigarh"
    assert crosswalk.unit_name("Jammu & Kashmir", 2023) == "Jammu and Kashmir"
    # ... and the merged rows go to their unit in every data year.
    for year in itr_npy.YEARS:
        assert crosswalk.unit_name("Dadra And Nagar Haveli And Daman And Diu", year) == "Gujarat"
        assert crosswalk.unit_name("Lakshadweep", year) == "Kerala"
        assert crosswalk.unit_name("Ladakh", year) == "Jammu and Kashmir"
    # The pre-merger rows are not printed rows of these editions.
    with pytest.raises(KeyError, match="Daman and Diu"):
        crosswalk.unit_name("Daman and Diu", 2022)
    # A year without a crosswalk raises too.
    with pytest.raises(KeyError, match="2030"):
        crosswalk.printed_unit("Kerala", 2030)
    # The 33 coarsened units, in sorted order, are those of the plan.
    assert list(crosswalk.UNITS) == sorted(crosswalk.UNITS) and len(crosswalk.UNITS) == 33
    # Real printed names: each table prints the 36 rows of its year and the India row.
    for n in ("npy_cells.csv", "outcomes_cells.csv", "sector_cells.csv"):
        for r in _read(n):
            if r["printed_unit"] != "India":
                assert crosswalk.unit_name(r["printed_name"], int(r.get("year") or
                                                                   r["cohort_year"])) == r["unit"]


def test_nfhs_unmatched_sheet_and_build():
    sheets = [name for _, _, name in nfhs.SHEETS]
    assert len(sheets) == 36
    with pytest.raises(KeyError, match="Daman & Diu only"):
        crosswalk.match_nfhs(sheets + ["Daman & Diu only"])
    with pytest.raises(ValueError, match="Ladakh"):
        crosswalk.match_nfhs([s for s in sheets if s != "Ladakh"])
    with pytest.raises(ValueError, match="two NFHS-5 sheets"):
        crosswalk.match_nfhs(sheets + ["Delhi"])
    m = crosswalk.match_nfhs(sheets)
    assert m["NCT Delhi"] == "Delhi"
    assert m["Dadra & Nagar Haveli and Daman & Diu"] == crosswalk.DNHDD
    assert set(m.values()) == set(crosswalk.PRINTED[2022])
    cells = {(f, p, name): {"women": "10.0", "men": "11.0"} for f, p, name in nfhs.SHEETS}
    assert len(nfhs.build(cells)) == 72
    bad = dict(cells)
    bad[(nfhs.PHASE1, 999, "Atlantis")] = {"women": "1.0", "men": "1.0"}
    del bad[(nfhs.PHASE1, 85, "Ladakh")]
    with pytest.raises(KeyError, match="Atlantis"):
        nfhs.build(bad)


def test_nfhs_cell_flags():
    assert nfhs.parse_total("13.0") == ("13.0", [])
    assert nfhs.parse_total("(17.2)") == ("17.2", ["nfhs_small_sample"])
    assert nfhs.parse_total("*") == (None, ["nfhs_suppressed"])
    with pytest.raises(ValueError):
        nfhs.parse_total("na")


# ---- printed totals and coarsening ----------------------------------------------------

@pytest.mark.parametrize("cells,mod", [("npy_cells.csv", itr_npy),
                                       ("outcomes_cells.csv", itr_outcomes),
                                       ("sector_cells.csv", itr_sector)])
def test_printed_totals_match_or_are_recorded(cells, mod):
    checks = cet.printed_totals(_read(cells))
    assert len(checks) == sum(len(s.fields) for s in mod.SPECS.values())
    assert readtable.unrecorded_gaps(checks, mod.RECORDED_GAPS) == []
    gaps = {(c["table_key"], c["field"]) for c in checks if c["difference"] != 0}
    assert gaps == set(mod.RECORDED_GAPS)


def test_printed_sex_totals_match():
    assert all(c["difference"] == 0 for c in cet.sex_totals(_read("tb_sex_2022.csv")))


def test_unrecorded_gap_fails():
    checks = cet.printed_totals(_read("npy_cells.csv"))
    c = next(c for c in checks if c["table_key"] == "ITR2024_NPY" and c["field"] == "paid")
    c["state_sum"] += 1
    c["difference"] += 1
    bad = readtable.unrecorded_gaps(checks, itr_npy.RECORDED_GAPS)
    assert any("ITR2024_NPY paid" in b for b in bad)
    # A recorded gap that is no longer found also fails.
    ok = cet.printed_totals(_read("npy_cells.csv"))
    assert readtable.unrecorded_gaps(ok, {("ITR2024_NPY", "paid"): (1, 2)})


@pytest.mark.parametrize("cells,panel,col,mod,n", [(g[0], g[1], g[2], g[3], g[4])
                                                   for g in cet.GROUPS])
def test_coarsening_preserves_totals(cells, panel, col, mod, n):
    assert cet.coarsening(_read(cells), _read(panel), col,
                          {s.year: s for s in mod.SPECS.values()}, n) == []


def test_the_india_paid_figure_equals_the_national_table():
    rows = _read("npy_national_check.csv")
    assert [int(r["year"]) for r in rows] == [2021, 2022, 2023]
    assert all(r["equal"] == "True" for r in rows)
    assert cet.national_table(rows) == []
    assert {r["printed_national_paid"] for r in rows} == {"1326306", "1601896", "1875510"}


def test_the_national_check_detects_a_mismatch():
    tables, vals = _fake()
    # The fake India row prints 700 in every year, so every year fails the check.
    out = itr_npy.national_check(tables, vals, lambda f, p: "national 1326306 1601896 1875510")
    assert [r["equal"] for r in out] == [False, False, False]


def test_tb_sex_equals_the_diabetes_study_extraction():
    """tb_sex_2022.csv is re-extracted from ITR 2023 A1.6 here (not copied); its values
    equal those of the diabetes study's file."""
    if not SIBLING_SEX.is_file():
        pytest.skip("../tb_diabetes_gap/data/extracted/tb_sex_2022.csv not present")
    mine = _read("tb_sex_2022.csv")
    with open(SIBLING_SEX, encoding="utf-8", newline="") as f:
        theirs = list(csv.DictReader(f))
    assert len(mine) == len(theirs) == 37
    assert list(mine[0]) == list(theirs[0]) == itr_sector.SEX_COLS
    assert mine == theirs


def test_outcomes_and_notified_match_the_priority_tool():
    """The priority tool (v1.0.1) extracted the ITR 2023 and ITR 2024 outcome cohorts and
    deaths and losses to follow-up, and the Annexure 1.2 total notified, from the same
    PDFs; this repository re-extracted them independently."""
    if not SIBLING_CELLS.is_file():
        pytest.skip("../tb_priority_tool/data/extracted/state_cells.csv not present")
    mine = {}
    for n in ("outcomes_cells.csv", "sector_cells.csv"):
        for r in _read(n):
            mine[(r["table_key"], r["printed_unit"], r["field"])] = r["value"]
    rename = {"cohort_notified": "cohort", "notified": "total"}
    n = 0
    with open(SIBLING_CELLS, encoding="utf-8", newline="") as f:
        for r in csv.DictReader(f):
            if r["table_key"] not in ("ITR2023_A3.3", "ITR2024_A3.3", "TBAR2022_A1.2",
                                      "ITR2023_A1.2", "ITR2024_A1.2"):
                continue
            field = rename.get(r["field"], r["field"])
            k = (r["table_key"], r["printed_unit"], field)
            if k in mine and field in ("cohort", "died", "ltfu", "total"):
                assert mine[k] == r["value"], k
                n += 1
    assert n == 37 * 3 * 2 + 37 * 3


# ---- structure ------------------------------------------------------------------------

def test_npy_panel_structure():
    rows = _read("npy_panel.csv")
    assert list(rows[0]) == ["unit", "year", "measure", "value", "denominator_basis",
                             "source_file", "pdf_page", "table_id", "flag"]
    keys = {(r["unit"], int(r["year"]), r["measure"]) for r in rows}
    assert len(rows) == len(keys) == 33 * (3 + 3 + 4)
    assert {r["unit"] for r in rows} == set(crosswalk.UNITS)
    assert {int(r["year"]) for r in rows} == {2021, 2022, 2023}
    assert {r["measure"] for r in rows} <= set(itr_npy.MEASURES)
    # the validated column exists in 2023 only
    assert {int(r["year"]) for r in rows if r["measure"] == "bank_validated"} == {2023}
    # the basis: "notified" in 2021 and 2022, "eligible" in 2023
    assert {(int(r["year"]), r["denominator_basis"]) for r in rows} == {
        (2021, "notified"), (2022, "notified"), (2023, "eligible")}
    assert all(r["source_file"] and r["pdf_page"] and r["table_id"] for r in rows)
    # every value is a printed count: empty only where the source prints a dash
    assert all(r["value"] != "" or "NA:all_members_missing" in r["flag"] for r in rows)


def test_outcomes_panel_structure():
    rows = _read("outcomes_panel.csv")
    assert list(rows[0]) == ["unit", "cohort_year", "measure", "value", "source_file",
                             "pdf_page", "table_id", "flag"]
    assert len(rows) == 33 * 2 * 4
    assert {int(r["cohort_year"]) for r in rows} == {2021, 2022}
    assert {r["measure"] for r in rows} == set(itr_outcomes.MEASURES)
    assert all(r["value"] != "" and r["source_file"] and r["pdf_page"] and r["table_id"]
               for r in rows)
    sources = {(int(r["cohort_year"]), r["source_file"].rsplit("/", 1)[1]) for r in rows}
    assert sources == {(2021, "ITR2023.pdf"), (2022, "ITR2024.pdf")}
    assert not any("impossible_outcome" in r["flag"] for r in rows)


def test_sector_panel_structure():
    rows = _read("sector_panel.csv")
    assert list(rows[0]) == ["unit", "year", "measure", "value", "source_file", "pdf_page",
                             "table_id", "flag"]
    assert len(rows) == 33 * 3 * 3
    assert {r["measure"] for r in rows} == {"public", "private", "total"}
    assert all(r["table_id"] == "Annexure 1.2" and r["pdf_page"] and r["source_file"]
               for r in rows)
    # Lakshadweep's private cell (printed NA in 2021 and 2023) is NA, flagged on Kerala
    na = {(r["unit"], int(r["year"])) for r in rows
          if "member_missing:Lakshadweep" in r["flag"]}
    assert na == {("Kerala", 2021), ("Kerala", 2023)}
    assert {r["measure"] for r in rows if "member_missing:" in r["flag"]} == {"private"}


def test_nfhs_structure():
    rows = _read("nfhs_bmi.csv")
    assert list(rows[0]) == ["unit", "sex", "bmi_below_normal_pct", "source_file", "pdf_page",
                             "flag"]
    assert len(rows) == 72
    assert {(r["source_file"], r["pdf_page"]) for r in rows} == \
        {(f, str(p)) for f, p, _ in nfhs.SHEETS}
    assert {r["unit"] for r in rows} == set(crosswalk.PRINTED[2022])
    assert {r["sex"] for r in rows} == {"women", "men"}
    assert all(r["bmi_below_normal_pct"] != "" for r in rows)  # no Total cell is starred
    merge = {r["unit"] for r in rows if "merge_into:" in r["flag"]}
    assert merge == {crosswalk.DNHDD, "Lakshadweep", "Ladakh"}


def test_sex_structure():
    rows = _read("tb_sex_2022.csv")
    assert len(rows) == 37
    assert {r["printed_unit"] for r in rows} == set(crosswalk.PRINTED[2022]) | {"India"}


def test_cells_have_provenance():
    for n, mod in (("npy_cells.csv", itr_npy), ("outcomes_cells.csv", itr_outcomes),
                   ("sector_cells.csv", itr_sector)):
        rows = _read(n)
        assert len(rows) == 37 * sum(len(s.fields) for s in mod.SPECS.values())
        assert all(r["pdf_page"] and r["table_id"] and r["cell_printed"] for r in rows)
        assert all(r["source_file"] == next(s.source_file for s in mod.SPECS.values()
                                            if s.key == r["table_key"]) for r in rows)


def test_no_analysis_quantity_is_extracted():
    # Extraction only: no ratio, share, unpaid count, weight or tier column anywhere.
    banned = ("ratio", "rate", "share", "unpaid", "weight", "tier", "pct")
    for n in ("npy_panel.csv", "outcomes_panel.csv", "sector_panel.csv"):
        header = list(_read(n)[0])
        assert not [h for h in header if any(b in h for b in banned)], n


def test_extraction_rerun_is_byte_identical(tmp_path):
    """Rerunning the extraction from the PDFs reproduces the committed files."""
    needed = [s.source_file for m in (itr_npy, itr_outcomes, itr_sector)
              for s in m.SPECS.values()] + [itr_sector.SEX_SPEC.source_file]
    if not all((ROOT / f).is_file() for f in needed):
        pytest.skip("data_raw/ is not distributed; run python -I tools/fetch_sources.py")
    paths = {}
    paths.update(itr_npy.write_all(itr_npy.read_all(), tmp_path))
    paths.update({"o_" + k: p for k, p in
                  itr_outcomes.write_all(itr_outcomes.read_all(), tmp_path).items()})
    paths.update({"s_" + k: p for k, p in
                  itr_sector.write_all(itr_sector.read_all(), tmp_path).items()})
    for p in paths.values():
        assert p.read_bytes() == (EXTRACTED / p.name).read_bytes(), p.name
    nfhs_rows = nfhs.build(nfhs.read_all())
    annex.write_csv(tmp_path / "nfhs_bmi.csv", nfhs.COLS, nfhs_rows)
    assert (tmp_path / "nfhs_bmi.csv").read_bytes() == (EXTRACTED / "nfhs_bmi.csv").read_bytes()
