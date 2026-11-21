"""Checks on the text of the registered analysis plan: the values that must be copied
verbatim are present, the label rule is the diabetes study's, and no internal process
identifier appears in it."""
import re
from pathlib import Path

PLAN = (Path(__file__).resolve().parents[1] / "docs" / "analysis_plan.md").read_text(
    encoding="utf-8")

VERBATIM = [
    # label rule, copied from the diabetes study
    '"supported" only if the 95% interval excludes the null AND ≥80% of grid entries '
    'agree in sign',
    "Seed 20261123; numpy `default_rng`, reset per analysis; 10,000 draws.",
    "Reuse tbprio functions; never copy-modify them.",
    "`python -I`, LF line endings.",
    "A = bank details available ÷ D;",
    "P = paid at least once ÷ bank details available;",
    "C = paid at least once ÷ D.",
    "U = D − paid.",
    "U_acc = D − bank details available.",
    "U_pay = bank details available − paid.",
    "S_acc = D·max(0, A_bench − A);",
    "S_pay = D·A·max(0, P_bench − P).",
    "S_acc / (S_acc + S_pay) ≥ 2/3 with 95% posterior probability",
    "n_u = f_u·w_u + (1 − f_u)·m_u",
    "wt_u = n_u / n̄",
    "act now ≥ 0.80, probable ≥ 0.50, uncertain ≥ 0.20, otherwise lower",
    "U(2023) × ₹1,000 × 6 months",
    "× ₹6,000",
    "₹500 per month; 8 months",
    "1.06/(n−3)",
    "n_u × U(0.8, 1.2) independently per unit, 1,000 replicates",
    "99.8%",
    "paid at least once",
    "ecological association",
    "## 12. Deviations (dated)",
]

FORBIDDEN = [r"\bTask\s*\d", r"\bcontroller\b", r"\bRuling\s*P?\d", r"\bsubagent\b",
             r"\bSDD\b", r"\bBuilder\b"]


def test_fixed_values_and_label_rule_are_in_the_plan_verbatim():
    missing = [v for v in VERBATIM if v not in PLAN]
    assert missing == []


def test_no_internal_process_identifiers_in_the_plan():
    hits = [p for p in FORBIDDEN if re.search(p, PLAN, flags=re.IGNORECASE)]
    assert hits == []


def test_need_weight_is_only_named_as_undernourished_patients_in_a_negation():
    """The phrase may appear only to say what the weight is not."""
    allowed = ('never called "', "not a count of ", "not give the number of ", "no output column or sentence calls it that")
    for m in re.finditer(r"undernourished TB patients", PLAN, flags=re.IGNORECASE):
        before = PLAN[max(0, m.start() - 40):m.start()]
        assert any(before.endswith(a) for a in allowed), PLAN[m.start() - 60:m.end() + 20]
