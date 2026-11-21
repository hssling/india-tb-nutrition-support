"""Extract the NFHS-5 body-mass-index items 86 and 87 (analysis plan section 4.1).

Adapted from hssling/india-tb-diabetes-gap (MIT), src/extract/nfhs.py at tag v1.0.0
(DOI 10.5281/zenodo.24425259): the page reading, the sheet table and the cell parser are
the same pattern, applied to items 86 and 87 instead of lines 101 and 104.

Run: python -I src/extract/nfhs.py   (from the repository root)

Reads, from each of the 36 State and UT fact sheets (22 sheets in Phase I; 14 in Phase II;
the India sheet is not used, plan section 4.1), the NFHS-5 Total column of item 86
"Women whose Body Mass Index (BMI) is below normal (BMI <18.5 kg/m2)21 (%)" and item 87
"Men whose Body Mass Index (BMI) is below normal (BMI <18.5 kg/m2) (%)", at the pages
listed in docs/data_inventory.md. Writes data/extracted/nfhs_bmi.csv:

    unit, sex, bmi_below_normal_pct, source_file, pdf_page, flag

- ``unit`` is the printed TB row the sheet matches (crosswalk.match_nfhs; one
  "Dadra and Nagar Haveli and Daman and Diu" sheet, a Ladakh sheet). One row per
  sheet and sex; the sheets are not merged here. The merge of plan section 4.2 (a
  notification-weighted mean over the member sheets) belongs to the analysis; a
  member sheet carries ``merge_into:<unit>``.
- ``bmi_below_normal_pct`` is the Total cell as printed (a percentage, not divided
  by 100). A cell in parentheses (25-49 unweighted cases) is used and flagged
  ``nfhs_small_sample``; a starred cell is NA (empty) and flagged ``nfhs_suppressed``.
  Urban, Rural and NFHS-4 cells are read only to place the Total column and are not
  kept.

Each page is checked for its "<name> - Key Indicators" heading, the section "Nutritional
Status of Adults (age 15-49 years)", the wording of items 86 and 87 and footnote 21.
Values are placed by word position: the words of the item's row (each goes to the nearer
of the two item numbers), within the column of the "Total" heading under "NFHS-5".
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if __package__ in (None, ""):
    sys.path.insert(0, str(ROOT))

from src.extract import annex, crosswalk  # noqa: E402

EXTRACTED = ROOT / "data" / "extracted"
NFHS_CSV = EXTRACTED / "nfhs_bmi.csv"
COLS = ["unit", "sex", "bmi_below_normal_pct", "source_file", "pdf_page", "flag"]

PHASE1 = "data_raw/nfhs5/NFHS-5_India_and_State_Factsheet_Compendium_Phase-I.pdf"
PHASE2 = "data_raw/nfhs5/NFHS-5_India_and_State_Factsheet_Compendium_Phase-II.pdf"

# (file, PDF page of items 86 and 87, sheet name as printed in the page heading);
# docs/data_inventory.md, section 5.
SHEETS: tuple[tuple[str, int, str], ...] = (
    (PHASE1, 13, "Andaman & Nicobar Islands"),
    (PHASE1, 19, "Andhra Pradesh"),
    (PHASE1, 25, "Assam"),
    (PHASE1, 31, "Bihar"),
    (PHASE1, 37, "Dadra & Nagar Haveli and Daman & Diu"),
    (PHASE1, 43, "Goa"),
    (PHASE1, 49, "Gujarat"),
    (PHASE1, 55, "Himachal Pradesh"),
    (PHASE1, 61, "Jammu & Kashmir"),
    (PHASE1, 67, "Karnataka"),
    (PHASE1, 73, "Kerala"),
    (PHASE1, 79, "Lakshadweep"),
    (PHASE1, 85, "Ladakh"),
    (PHASE1, 91, "Maharashtra"),
    (PHASE1, 97, "Meghalaya"),
    (PHASE1, 103, "Manipur"),
    (PHASE1, 109, "Mizoram"),
    (PHASE1, 115, "Nagaland"),
    (PHASE1, 121, "Sikkim"),
    (PHASE1, 127, "Telangana"),
    (PHASE1, 133, "Tripura"),
    (PHASE1, 139, "West Bengal"),
    (PHASE2, 15, "Arunachal Pradesh"),
    (PHASE2, 21, "Chhattisgarh"),
    (PHASE2, 27, "Haryana"),
    (PHASE2, 33, "Jharkhand"),
    (PHASE2, 39, "Madhya Pradesh"),
    (PHASE2, 45, "Odisha"),
    (PHASE2, 51, "Punjab"),
    (PHASE2, 57, "Rajasthan"),
    (PHASE2, 63, "Tamil Nadu"),
    (PHASE2, 69, "Uttar Pradesh"),
    (PHASE2, 75, "Uttarakhand"),
    (PHASE2, 81, "Chandigarh"),
    (PHASE2, 87, "NCT Delhi"),
    (PHASE2, 93, "Puducherry"),
)
ITEMS = {"women": "86.", "men": "87."}
# The start of each item's wording; the rest of the label wraps differently by sheet.
LABEL_START = {
    "86.": "86. Women whose Body Mass Index (BMI) is below normal (BMI <18.5",
    "87.": "87. Men whose Body Mass Index (BMI) is below normal (BMI <18.5",
}
SECTION = "Nutritional Status of Adults (age 15-49 years)"
FOOTNOTE = "21Excludes pregnant women and women with a birth in the preceding 2 months."

_VALUE = re.compile(r"^(?:\d+(?:\.\d+)?|\(\d+(?:\.\d+)?\)|\*|na)$")


def _squash(s: str) -> str:
    return "".join(s.split()).casefold()


def parse_total(text: str) -> tuple[str | None, list[str]]:
    """(percentage as printed or None, flags) of one NFHS-5 Total cell."""
    t = text.strip()
    if re.fullmatch(r"\d+(?:\.\d+)?", t):
        return t, []
    m = re.fullmatch(r"\((\d+(?:\.\d+)?)\)", t)
    if m:
        return m.group(1), ["nfhs_small_sample"]
    if t == "*":
        return None, ["nfhs_suppressed"]
    raise ValueError(f"not an NFHS-5 percentage cell: {text!r}")


def read_sheet(words: list[dict], heading: str) -> dict[str, str]:
    """{'women': Total cell, 'men': Total cell} (as printed) from one page's words
    (pdfplumber extract_words). Raises ValueError if the page is not the expected one
    or a cell cannot be placed."""
    lines: dict[int, list[dict]] = {}
    for w in sorted(words, key=lambda w: (round(w["top"]), w["x0"])):
        lines.setdefault(round(w["top"]), []).append(w)
    texts = [" ".join(w["text"] for w in ws) for _, ws in sorted(lines.items())]
    first = texts[0] if texts else ""
    if _squash(first) != _squash(f"{heading} - Key Indicators"):
        raise ValueError(f"page heading {first!r} is not {heading!r} - Key Indicators")
    page = _squash(" ".join(texts))
    for need in (SECTION, FOOTNOTE):
        if _squash(need) not in page:
            raise ValueError(f"{heading}: {need!r} not on the page")
    head = [w for w in words if w["top"] < 100 and w["text"] in ("Urban", "Rural", "Total")]
    head.sort(key=lambda w: w["x0"])
    if [w["text"] for w in head] != ["Urban", "Rural", "Total", "Total"]:
        raise ValueError(f"{heading}: column headings {[w['text'] for w in head]}")
    cols = {"urban": head[0], "rural": head[1], "total": head[2], "nfhs4": head[3]}

    def col_of(w: dict) -> str | None:
        xc = (w["x0"] + w["x1"]) / 2
        best = min(cols, key=lambda k: abs(xc - (cols[k]["x0"] + cols[k]["x1"]) / 2))
        c = cols[best]
        return best if c["x0"] - 12 <= xc <= c["x1"] + 12 else None

    def top_of(label: str) -> float:
        hits = [w["top"] for w in words if w["text"] == label and w["x0"] < 45]
        if len(hits) != 1:
            raise ValueError(f"{heading}: item {label} found {len(hits)} times")
        return hits[0]

    t86, t87, t88 = top_of("86."), top_of("87."), top_of("88.")
    if not t86 < t87 < t88:
        raise ValueError(f"{heading}: items 86, 87, 88 are not in order")
    tops = {"86.": t86, "87.": t87}
    # The value cells of an item sit on the item number's line or within a few points
    # of it (item 87's wrapped label is set between them); each goes to the nearer
    # item number.
    vals = [w for w in words if w["x0"] >= 400 and t86 - 4 <= w["top"] < t88 - 4]
    placed: dict[str, dict[str, str]] = {"86.": {}, "87.": {}}
    for w in vals:
        if not _VALUE.match(w["text"]):
            raise ValueError(f"{heading}: items 86-87: unexpected token {w['text']!r}")
        item = min(tops, key=lambda k: abs(w["top"] - tops[k]))
        k = col_of(w)
        if k is None or k in placed[item]:
            raise ValueError(f"{heading}: item {item} cannot place {w['text']!r}")
        placed[item][k] = w["text"]
    out: dict[str, str] = {}
    for sex, num in ITEMS.items():
        if set(placed[num]) != set(cols):
            raise ValueError(f"{heading}: item {num} cells {placed[num]}")
        out[sex] = placed[num]["total"]
        lo, hi = tops[num] - 2, (t87 - 2 if num == "86." else t88 - 2)
        band = [w for w in words if w["x0"] < 400 and lo <= w["top"] < hi]
        label = _squash("".join(w["text"] for w in
                                sorted(band, key=lambda w: (round(w["top"]), w["x0"]))))
        if _squash(LABEL_START[num]) not in label:
            raise ValueError(f"{heading}: item {num} reads {label!r}")
    return out


def read_all() -> dict[tuple[str, int, str], dict[str, str]]:
    import pdfplumber

    out: dict[tuple[str, int, str], dict[str, str]] = {}
    for f in (PHASE1, PHASE2):
        with pdfplumber.open(ROOT / f) as pdf:
            for sf, p, name in SHEETS:
                if sf != f:
                    continue
                pg = pdf.pages[p - 1]
                words = [{k: w[k] for k in ("text", "x0", "x1", "top")}
                         for w in pg.extract_words()]
                pg.flush_cache()
                pg.close()
                try:
                    out[(sf, p, name)] = read_sheet(words, name)
                except ValueError as e:
                    raise ValueError(f"{f} PDF p. {p}: {e}") from None
    return out


def build(cells_by_sheet: dict[tuple[str, int, str], dict[str, str]]) -> list[dict]:
    if len(cells_by_sheet) != 36:
        raise ValueError(f"{len(cells_by_sheet)} NFHS-5 sheets read, expected 36")
    match = crosswalk.match_nfhs([name for _, _, name in cells_by_sheet])
    rows = []
    for (f, p, name), vals in cells_by_sheet.items():
        unit = match[name]
        for sex in ("women", "men"):
            pct, flags = parse_total(vals[sex])
            if crosswalk.coarsen(unit) != unit:
                flags.append(f"merge_into:{crosswalk.coarsen(unit)}")
            if _squash(name) != _squash(unit):
                flags.append(f"sheet_name:{name}")
            rows.append({"unit": unit, "sex": sex, "bmi_below_normal_pct": pct,
                         "source_file": f, "pdf_page": p, "flag": ";".join(flags)})
    rows.sort(key=lambda r: (r["unit"], r["sex"] != "women"))
    return rows


def main() -> int:
    rows = build(read_all())
    annex.write_csv(NFHS_CSV, COLS, rows)
    print(f"wrote {NFHS_CSV.relative_to(ROOT).as_posix()}: {len(rows)} rows")
    return 0


if __name__ == "__main__":
    sys.exit(main())
