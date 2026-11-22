# Adapted from hssling/india-tb-diabetes-gap v1.0.0 (MIT), exhibits/formats.py (itself adapted
# from hssling/india-tb-priority-tool and hssling/india-tb-acf-campaign); modified: the formats
# of this paper (shares, coefficients, people, rupee amounts in billions), shared by
# exhibits/make_tables.py, exhibits/make_figures.py, exhibits/make_graphical_abstract.py and
# verification/check_manuscript_numbers.py.
"""Number formats of the manuscript and its exhibits: the only place they are fixed.

Every number printed in the tables, the figure labels and the text goes through one of these
functions, so the number check (verification/check_manuscript_numbers.py) and the exhibits
always agree on how a value from outputs/ is written.
"""
from __future__ import annotations

import csv
from datetime import date
from pathlib import Path

MINUS = "−"  # a negative number is written with the minus sign U+2212
TO = " to "        # every interval: "0.02 to 0.35"
MONTHS = ("January February March April May June July August September October November "
          "December").split()
TIERS = ["act now", "probable priority", "uncertain", "lower priority"]
CLASSES = ["account-led", "payment-led", "mixed", "no shortfall"]
YEARS = ["2021", "2022", "2023"]
MAIN_YEAR = "2023"
NATIONAL = "units with data"


def num(x: float | str, dp: int) -> str:
    """x with dp decimals; a negative value with the minus sign."""
    s = f"{float(x):.{dp}f}"
    if s.startswith("-") and float(s) == 0:
        s = s[1:]
    return MINUS + s[1:] if s.startswith("-") else s


NBSP = "\u00a0"  # the journal's thousands separator: "10 000", never "10,000"


def count(x: float | str) -> str:
    """A whole number in the journal's style: a no-break space between thousands from five digits
    up ("639 965"), none in a four-digit number ("2796"); x is rounded half to even."""
    v = round(float(x))
    s = str(abs(v)) if abs(v) < 10000 else f"{abs(v):,}".replace(",", NBSP)
    return (MINUS + s) if v < 0 else s


SMALL = "zero one two three four five six seven eight nine".split()


def small(x: float | str) -> str:
    """A count in words from one to nine (the journal spells these out in text), else count()."""
    v = round(float(x))
    return SMALL[v] if 0 < v < 10 else count(v)


def pct_n(n: float | str, d: float | str) -> str:
    """A percentage with its numerator and denominator: "74.0% (1 822 585/2 462 550)"; one
    decimal when the denominator is above 100, a whole number otherwise."""
    n, d = float(n), float(d)
    return f"{pct(n / d, 1 if d > 100 else 0)} ({count(n)}/{count(d)})"


def rng(lo: str, hi: str) -> str:
    return f"{lo}{TO}{hi}"


def pct(x: float | str, dp: int = 1) -> str:
    """A share as a percentage: 0.74012 -> "74.0%"."""
    return num(100 * float(x), dp) + "%"


def pp(x: float | str, dp: int = 1) -> str:
    """A difference of shares in percentage points: 0.0404 -> "4.0 percentage points"."""
    return num(100 * float(x), dp) + " percentage points"


def ratio(x: float | str, dp: int = 2) -> str:
    """A coefficient (rho, beta, a weight): two decimals by default."""
    return num(x, dp)


def prob(x: float | str) -> str:
    """A probability: two decimals; 1 and 0 written in full only when exact."""
    v = float(x)
    if v == 1.0:
        return "1"
    if v == 0.0:
        return "0"
    s = num(v, 2)
    if s == "1.00":
        return num(v, 3) if num(v, 3) != "1.000" else ">0.999"
    if s == "0.00":
        return num(v, 3) if num(v, 3) != "0.000" else "<0.001"
    return s


def people(mean: str | float, lo: str | float, hi: str | float) -> str:
    """A count of people with its interval: "639,965 (638,648 to 641,274)"."""
    return f"{count(mean)} ({rng(count(lo), count(hi))})"


def share_ci(x: str, lo: str, hi: str, dp: int = 1) -> str:
    """A share with its interval: "74.0% (74.0% to 74.1%)"."""
    return f"{pct(x, dp)} ({rng(pct(lo, dp), pct(hi, dp))})"


def ratio_ci(x: str, lo: str, hi: str, dp: int = 2) -> str:
    return f"{ratio(x, dp)} ({rng(ratio(lo, dp), ratio(hi, dp))})"


def inr_bn(x: float | str, dp: int = 2) -> str:
    """Rupees in billions: 3839790000 -> "INR 3.84 billion"."""
    return f"INR {num(float(x) / 1e9, dp)} billion"


def day(iso: str) -> str:
    """'2026-11-21' -> '21 November 2026'."""
    d = date.fromisoformat(iso[:10])
    return f"{d.day} {MONTHS[d.month - 1]} {d.year}"


def and_list(items: list[str]) -> str:
    """'A, B and C' (no item: 'none')."""
    items = list(items)
    if not items:
        return "none"
    return items[0] if len(items) == 1 else ", ".join(items[:-1]) + " and " + items[-1]


def read_csv(root: Path, rel: str) -> list[dict]:
    with open(root / rel, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def one(rows: list[dict], what: str, **kv) -> dict:
    hits = [r for r in rows if all(r[k] == v for k, v in kv.items())]
    if len(hits) != 1:
        raise ValueError(f"{what}: {len(hits)} rows match {kv}")
    return hits[0]


def unit_rows(rows: list[dict], year: str | None = None) -> list[dict]:
    """chain.csv rows of the 33 units (the national rows left out), optionally of one year."""
    return [r for r in rows if r.get("level") == "unit" and (year is None or r["year"] == year)]


def national(rows: list[dict], year: str) -> dict:
    return one(rows, f"national {year}", level="national", year=year)


# Variable names written in italics with a subscript in the manuscript and its tables (Pandoc's
# *...* and ~...~ syntax);
# file names and URLs are never touched (a name preceded by "/", "." or a word character is left).
SUBSCRIPTS = {"wt_u": "*wt*~u~", "n_u": "*n*~u~", "f_u": "*f*~u~", "w_u": "*w*~u~", "m_u": "*m*~u~",
              "U_acc": "*U*~acc~", "U_pay": "*U*~pay~", "S_acc": "*S*~acc~", "S_pay": "*S*~pay~"}


def subscripts(text: str) -> str:
    """Write the variable names of SUBSCRIPTS as italic Pandoc subscripts: "U_acc" -> "*U*~acc~"."""
    import re
    for a, b in SUBSCRIPTS.items():
        text = re.sub(r"(?<![\w/.~])" + re.escape(a) + r"\b", b, text)
    return text
