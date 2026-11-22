# Adapted from hssling/india-tb-diabetes-gap v1.0.0 (MIT), verification/check_docx_tie.py (itself
# adapted from hssling/india-tb-priority-tool and hssling/india-tb-acf-campaign); modified: the
# Transactions of The Royal Society of Tropical Medicine and Hygiene set of this paper (one .docx
# holding the title page, abstract, text, references, Table 1 and the figure legends; separate
# TIFF figures; the supplementary data; the cover letter; the graphical abstract), Word's counts
# against the 200-word abstract and the 3,500-word main text, the layout (double spacing, line
# numbers, no justification, no automatic hyphenation), the figures re-rendered from the exhibits
# and checked for resolution, colour and Arial, and the graphical abstract's 5:2 shape.
"""Tie the submission files to their Markdown sources and check the journal's limits.

Run as: python -I verification/check_docx_tie.py [--manuscript-dir DIR]

The manuscript folder is DIR (default manuscript/; git-ignored). The files in <folder>/submission/
(built by tools/build_submission.py) are what the journal receives; the Markdown files in <folder>/
are what check_manuscript_numbers.py verifies. Reading the .docx files needs only zipfile and
ElementTree; the figure checks use PyMuPDF and Pillow.

1. Text tie. Each .docx's units (paragraphs outside tables; table rows as their cells joined by
   " | ") equal, in order, the units of its Markdown source(s): headings, paragraphs, list items,
   table rows and reference entries, normalised the same way on both sides (emphasis markers and
   escapes removed, superscripts written ^...^ and subscripts ~...~, whitespace collapsed, the Zenodo DOI read as one
   token). Every file of the set is present and no other file is in submission/ (except a
   SUBMITTED_* record and the _render folder).
2. Title page. The manuscript's first page gives a running title of at most 50 characters and
   quotes Word's counts.
3. Internal identifiers and wording (check_manuscript_numbers.BANNED and WORDING) do not occur in
   the manuscript (before the References) or the supplementary data.
4. Word's counts. <folder>/word_counts_word.json (Word's ComputeStatistics on the manuscript,
   written by the build) belongs to the current manuscript.md; the abstract is at most 200 words
   and the main text (Introduction to Discussion) at most 3,500.
5. Display items: the manuscript holds one table per cited table and, with the figures, at most
   five display items.
6. Layout: the manuscript has continuous line numbers; every paragraph style is double spaced in
   the manuscript; no paragraph is justified; automatic hyphenation is off.
7. The release DOI: every one in the .docx files equals the DOI the build recorded in
   <folder>/release_doi.txt (or the placeholder when the build had no --doi).
8. Figures: each Figure_k.tif equals the TIFF rendered now from exhibits/figurek.pdf (colour, at
   least 300 dpi), and the PDF's text is set in Arial; graphical_abstract.tif equals its rendering,
   is 5:2 landscape, at least 127 x 50 mm and 300 to 600 dpi.

Prints "SKIPPED" and exits 0 when <folder>/ or <folder>/submission/ is absent. Exit 1 on any problem.
"""
from __future__ import annotations

import difflib
import hashlib
import io
import json
import re
import sys
import zipfile
from functools import lru_cache
from pathlib import Path
from xml.etree import ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from verification import check_manuscript_numbers as cmn  # noqa: E402
from exhibits.formats import count  # noqa: E402

W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
# The release DOI: the placeholder in the Markdown, the DOI that --doi fills in the .docx. Zenodo DOIs
# cited as themselves (the released tbprio software) are compared digit for digit.
CITED_ZENODO = ("24411057",)
DOI = re.compile(r"10\.5281/zenodo\.(?:X{3,}|(?!(?:" + "|".join(CITED_ZENODO) + r")\b)\d+)")
LIMITS = {"abstract": 200, "main_text": 3500}
FIG_DPI, GA_DPI = 600, 300
MIN_DPI = 300
GA_MIN_MM = (127.0, 50.0)
MAX_DISPLAY = 5
MS = cmn.MS_NAME
TP = cmn.TITLE_PAGE
MANUSCRIPT = "manuscript.docx"
SUPPLEMENT = "Supplementary data.docx"  # the journal: the file name contains "Supplementary data"
TABLE1 = "Table_1.docx"                 # the journal: tables as separate, editable Word files
COVER_DOCX = "cover_letter.docx"
SUPP_TEXT = cmn.SUPP_TEXT
FIGURES = {k: f"Figure_{k}.tif" for k in range(1, 5)}
GA = "graphical_abstract.tif"
# The paragraph the build adds to the supplementary data (tools/build_submission.py imports it).
SUPP_NOTE = ("Tables S1 to S15 are cited in the manuscript in this order, after the methods below. Every cell is generated from the study's "
             "committed outputs; units are listed alphabetically (tiers, not ranks).")

SPEC: dict[str, list[tuple]] = {
    MANUSCRIPT: [
        ("first", MS, "# "),
        ("md", TP, "# Title page", None, "drop-first"),
        ("md", MS, "## Abstract", "## Figure legends"),
        ("md", MS, "## Figure legends", None),
    ],
    TABLE1: [("md", "exhibits/tables.md", "## Table 1.", "## Table S1.")],
    SUPPLEMENT: [
        ("builder", "Supplementary data"),
        ("first", MS, "# "),
        ("builder", SUPP_NOTE),
        ("md", SUPP_TEXT, None, None),
        ("md", "exhibits/tables.md", "## Table S1.", None),
    ],
    COVER_DOCX: [("md", cmn.COVER, "# Cover letter", None, "drop-first")],
}
CHECKED_WORDING = (MANUSCRIPT, SUPPLEMENT, TABLE1)
SUBMITTED = re.compile(r"SUBMITTED_.*")


def all_files() -> set[str]:
    return set(SPEC) | set(FIGURES.values()) | {GA}


# --------------------------------------------------------------------------------------
# Normalisation (the same for both sides)
# --------------------------------------------------------------------------------------
def norm(s: str) -> str:
    s = s.replace("**", "").replace("*", "")
    s = re.sub(r"\\(?=[^\w\s])", "", s)
    s = s.replace("^^", "")
    s = s.replace("\u00a0", " ")
    s = DOI.sub("10.5281/zenodo.<DOI>", s)
    return re.sub(r"\s+", " ", s).strip()


def md_slice(text: str, start: str | None, end: str | None) -> str:
    lines = text.splitlines()
    i = 0 if start is None else next(k for k, ln in enumerate(lines) if ln.startswith(start))
    j = len(lines) if end is None else next(k for k, ln in enumerate(lines) if k > i and ln.startswith(end))
    return "\n".join(lines[i:j])


def row_unit(cells) -> str:
    cells = list(cells)
    while len(cells) > 1 and not cells[-1]:
        cells.pop()
    return " | ".join(cells)


def md_units(text: str) -> list[str]:
    """Headings, paragraphs, list items, reference entries and table rows of a Markdown text, normalised."""
    units: list[str] = []
    para: list[str] = []

    def flush() -> None:
        if para:
            units.append(norm(" ".join(para)))
            para.clear()

    for ln in text.splitlines():
        s = ln.strip()
        if not s:
            flush()
        elif s.startswith("#"):
            flush()
            units.append(norm(s.lstrip("#")))
        elif s.startswith("|"):
            flush()
            body = s[1:-1] if s.endswith("|") else s[1:]
            cells = body.split("|")
            if all(re.fullmatch(r"\s*:?-{3,}:?\s*", c) for c in cells):
                continue
            units.append(row_unit(norm(c) for c in cells))
        elif re.match(r"[-*+] ", s):
            flush()
            para.append(s[2:])
        elif re.match(r"\d+\. ", s):
            flush()
            para.append(s)
        else:
            para.append(s)
    flush()
    return [u for u in units if u]


# --------------------------------------------------------------------------------------
# .docx units and layout
# --------------------------------------------------------------------------------------
def para_text(p: ET.Element) -> str:
    parts = []
    for r in p.iter(f"{W}r"):
        va = r.find(f"{W}rPr/{W}vertAlign")
        sup = va is not None and va.get(f"{W}val") == "superscript"
        sub = va is not None and va.get(f"{W}val") == "subscript"
        txt = "".join((t.text or "") if t.tag == f"{W}t" else " " for t in r if t.tag in (f"{W}t", f"{W}tab", f"{W}br"))
        parts.append(f"^{txt}^" if sup and txt.strip() else f"~{txt}~" if sub and txt.strip() else txt)
    return "".join(parts)


def part(path: Path, name: str) -> ET.Element | None:
    with zipfile.ZipFile(path) as z:
        return ET.fromstring(z.read(name)) if name in z.namelist() else None


def docx_units(path: Path) -> list[str]:
    body = part(path, "word/document.xml").find(f"{W}body")
    units: list[str] = []
    for el in body:
        if el.tag == f"{W}p":
            u = norm(para_text(el))
            if u:
                units.append(u)
        elif el.tag == f"{W}tbl":
            for tr in el.iter(f"{W}tr"):
                cells = [" ".join(para_text(p) for p in tc.iter(f"{W}p")) for tc in tr.findall(f"{W}tc")]
                units.append(row_unit(norm(c) for c in cells))
    return units


def docx_tables(path: Path) -> int:
    body = part(path, "word/document.xml").find(f"{W}body")
    return sum(1 for el in body if el.tag == f"{W}tbl")


def docx_all_text(path: Path) -> str:
    out = []
    with zipfile.ZipFile(path) as z:
        for name in z.namelist():
            if name.endswith((".xml", ".rels")):
                raw = z.read(name).decode("utf-8", errors="replace")
                out += [re.sub(r"<[^>]+>", "", raw), raw]
    return "\n".join(out)


def layout_problems(path: Path) -> list[str]:
    """Line numbers, double spacing, no justification, no automatic hyphenation."""
    out = []
    doc = part(path, "word/document.xml")
    if doc.find(f".//{W}sectPr/{W}lnNumType") is None:
        out.append(f"LAYOUT: {path.name} has no line numbers")
    for jc in list(doc.iter(f"{W}jc")) + list(part(path, "word/styles.xml").iter(f"{W}jc")):
        if jc.get(f"{W}val") in ("both", "distribute"):
            out.append(f"LAYOUT: {path.name} has justified text")
            break
    st = part(path, "word/styles.xml")
    styles = {s.get(f"{W}styleId"): s for s in st.findall(f"{W}style") if s.get(f"{W}type") == "paragraph"}

    def line(sid: str | None, depth: int = 0) -> str | None:
        s = styles.get(sid)
        if s is None or depth > 20:
            return None
        sp = s.find(f"{W}pPr/{W}spacing")
        if sp is not None and sp.get(f"{W}line"):
            return sp.get(f"{W}line")
        base = s.find(f"{W}basedOn")
        return line(base.get(f"{W}val"), depth + 1) if base is not None else None

    used = {ps.get(f"{W}val") for ps in doc.iter(f"{W}pStyle")} | {"Normal"}
    for sid in sorted(used - {"TableTitle", "TableNote", None}):
        if sid in styles and line(sid) != "480":
            out.append(f"LAYOUT: style {sid} used in {path.name} is not double spaced")
    se = part(path, "word/settings.xml")
    ah = se.find(f"{W}autoHyphenation") if se is not None else None
    if ah is not None and ah.get(f"{W}val", "true") not in ("false", "0", "off"):
        out.append(f"LAYOUT: {path.name} has automatic hyphenation on")
    return out


# --------------------------------------------------------------------------------------
# Expected units
# --------------------------------------------------------------------------------------
def expected(ms_dir: Path, name: str) -> list[str]:
    out: list[str] = []
    for p in SPEC[name]:
        if p[0] == "builder":
            out.append(norm(p[1]))
        elif p[0] == "first":
            text = (ms_dir / p[1]).read_text(encoding="utf-8")
            out.append(norm(text.splitlines()[0].lstrip("#")))
        else:
            text = (ms_dir / p[1]).read_text(encoding="utf-8")
            units = md_units(md_slice(text, p[2], p[3]))
            if len(p) > 4 and p[4] == "drop-first":
                units = units[1:]
            out += units
    return out


def compare(name: str, got: list[str], want: list[str], limit: int = 6) -> list[str]:
    if got == want:
        return []
    out = []
    sm = difflib.SequenceMatcher(None, want, got, autojunk=False)
    for tag, i1, i2, j1, j2 in sm.get_opcodes():
        if tag == "equal":
            continue
        md = " // ".join(want[i1:i2])[:300] or "(nothing)"
        dx = " // ".join(got[j1:j2])[:300] or "(nothing)"
        out.append(f"TIE {name}: {tag} at markdown unit {i1 + 1}, docx unit {j1 + 1}:\n    markdown: {md}\n    docx:     {dx}")
        if len(out) >= limit:
            out.append(f"TIE {name}: further differences not listed")
            break
    return out


# --------------------------------------------------------------------------------------
# Title page, wording, word counts and display items
# --------------------------------------------------------------------------------------
def front(units: list[str]) -> list[str]:
    return units[:units.index("Abstract")] if "Abstract" in units else units


def title_page_problems(units: list[str], ms_dir: Path) -> list[str]:
    head = front(units)
    out = []
    rt = next((u.split(":", 1)[1].strip() for u in head if u.startswith("Running title:")), "")
    if not rt or len(rt) > cmn.LIMITS["running_title"]:
        out.append(f"TITLE PAGE: the manuscript's running title is missing or longer than {cmn.LIMITS['running_title']} characters")
    flat = " ".join(head)
    for what, pat in (("e-mail", r"[\w.+-]+@[\w-]+\.[\w.]+"), ("ORCID", r"\d{4}-\d{4}-\d{4}-\d{3}[\dX]")):
        if not re.search(pat, flat):
            out.append(f"TITLE PAGE: the manuscript's first page has no {what}")
    title = norm((ms_dir / MS).read_text(encoding="utf-8").splitlines()[0].lstrip("#"))
    if not head or head[0] != title:
        out.append("TITLE PAGE: the manuscript does not open with its title")
    return out


def wording_problems(name: str, units: list[str]) -> list[str]:
    text = "\n".join(units)
    if name == MANUSCRIPT:
        text = text.split("\nReferences\n", 1)[0]
    out = []
    for pat, what in cmn.BANNED + cmn.WORDING:
        for m in re.finditer(pat, text, re.I if (pat, what) in cmn.WORDING else 0):
            out.append(f"WORDING in {name}: {what}: {m.group()!r}")
    return out


def word_count_problems(ms_dir: Path, units: list[str]) -> list[str]:
    p = ms_dir / "word_counts_word.json"
    if not p.exists():
        return ["WORDS: word_counts_word.json missing (build with Word: python -I tools/build_submission.py)"]
    w = json.loads(p.read_text(encoding="utf-8"))
    out = []
    md5 = hashlib.md5((ms_dir / MS).read_text(encoding="utf-8").encode("utf-8")).hexdigest()
    if w.get("source_md5") != md5:
        out.append("WORDS: word_counts_word.json is stale (manuscript.md changed): rebuild")
    for k, lim in LIMITS.items():
        if w[k] > lim:
            out.append(f"WORDS: Word counts {w[k]} words in the {k}, over the limit of {lim}")
    own = sum(cmn.words(u) for u in abstract_of(units))
    if own > LIMITS["abstract"]:
        out.append(f"WORDS: the abstract of the manuscript has {own} words, over the limit of {LIMITS['abstract']}")
    flat = " ".join(front(units))
    for want in (f"abstract {count(w['abstract'])} words", f"main text (Introduction to Discussion, headings "
                 f"excluded) {count(w['main_text'])} words"):
        if want not in flat:
            out.append(f"WORDS: the title page does not quote Word's count {want!r}")
    return out


def abstract_of(units: list[str]) -> list[str]:
    try:
        i = units.index("Abstract")
    except ValueError:
        return ["(no Abstract heading)"] * 999
    out = []
    for u in units[i + 1:]:
        if u.startswith("Keywords:"):
            break
        out.append(u)
    return out


def display_problems(path: Path, table1: Path | None = None) -> list[str]:
    """No table in the manuscript itself; Table 1 alone in its own file; with the figures, at most five."""
    out = []
    n_ms = docx_tables(path)
    if n_ms:
        out.append(f"DISPLAY: the manuscript holds {n_ms} table(s); tables go in separate files")
    n_tab = docx_tables(table1) if table1 is not None and table1.exists() else 0
    if n_tab != len(cmn.TABLES):
        out.append(f"DISPLAY: {TABLE1} holds {n_tab} tables, the text cites {len(cmn.TABLES)}")
    if n_tab + n_ms + len(FIGURES) > MAX_DISPLAY:
        out.append(f"DISPLAY: {n_tab + n_ms} tables and {len(FIGURES)} figures, more than {MAX_DISPLAY} display items")
    return out

def render_tiff_bytes(pdf: Path, dpi: int) -> bytes:
    """The TIFF of the PDF's first page: RGB colour, LZW, at dpi (deterministic)."""
    return _render(hashlib.md5(pdf.read_bytes()).hexdigest(), str(pdf), dpi)


@lru_cache(maxsize=16)
def _render(_digest: str, pdf: str, dpi: int) -> bytes:
    import fitz  # PyMuPDF
    from PIL import Image
    Image.MAX_IMAGE_PIXELS = None
    page = fitz.open(pdf)[0]
    pix = page.get_pixmap(dpi=dpi, alpha=False, colorspace=fitz.csRGB)
    im = Image.frombytes("RGB", (pix.width, pix.height), pix.samples)
    buf = io.BytesIO()
    im.save(buf, format="TIFF", compression="tiff_lzw", dpi=(dpi, dpi))
    return buf.getvalue()


@lru_cache(maxsize=32)
def pixel_digest(tiff: bytes) -> str:
    """The MD5 of a TIFF's decoded pixels, mode, size and resolution (LZW streams of the same pixels
    may differ byte for byte between runs, so the pixels are compared)."""
    from PIL import Image
    Image.MAX_IMAGE_PIXELS = None
    with Image.open(io.BytesIO(tiff)) as im:
        h = hashlib.md5(im.tobytes())
        h.update(f"{im.mode} {im.size} {im.info.get('dpi')}".encode())
        return h.hexdigest()


def pdf_fonts(pdf: Path) -> set[str]:
    import fitz
    return {f[3] for f in fitz.open(str(pdf))[0].get_fonts()}


def tiff_info(path: Path):
    from PIL import Image
    Image.MAX_IMAGE_PIXELS = None
    with Image.open(path) as im:
        return im.info.get("dpi", (0, 0)), im.size, im.mode


def figure_problems(ms_dir: Path) -> list[str]:
    sub, ex = ms_dir / "submission", ms_dir / "exhibits"
    out = []
    items = [(k, tif, ex / f"figure{k}.pdf", FIG_DPI) for k, tif in FIGURES.items()]
    items.append(("GA", GA, ex / "graphical_abstract.pdf", GA_DPI))
    for k, tif, pdf, dpi in items:
        if not (sub / tif).exists() or not pdf.exists():
            continue
        if pixel_digest((sub / tif).read_bytes()) != pixel_digest(render_tiff_bytes(pdf, dpi)):
            out.append(f"FIGURES: {tif} differs from the rendering of exhibits/{pdf.name} (rebuild)")
        if not any("Arial" in f for f in pdf_fonts(pdf)) or any("Arial" not in f for f in pdf_fonts(pdf)):
            out.append(f"FIGURES: exhibits/{pdf.name} is not set in Arial only ({sorted(pdf_fonts(pdf))})")
        (dx, dy), (wpx, hpx), mode = tiff_info(sub / tif)
        if min(float(dx), float(dy)) < MIN_DPI:
            out.append(f"FIGURES: {tif} is {dx} dpi, below {MIN_DPI}")
        if mode != "RGB":
            out.append(f"FIGURES: {tif} is {mode}, not RGB colour")
        if k == "GA":
            if wpx * 2 != hpx * 5:
                out.append(f"FIGURES: {tif} is {wpx} x {hpx} pixels, not 5:2")
            w_mm, h_mm = wpx / float(dx) * 25.4, hpx / float(dy) * 25.4
            if w_mm < GA_MIN_MM[0] or h_mm < GA_MIN_MM[1]:
                out.append(f"FIGURES: {tif} is {w_mm:.0f} x {h_mm:.0f} mm, below {GA_MIN_MM[0]:.0f} x {GA_MIN_MM[1]:.0f} mm")
            if not 300 <= float(dx) <= 600:
                out.append(f"FIGURES: {tif} is {dx} dpi, outside 300 to 600")
    return out


def problems(ms_dir: Path | None = None, root: Path = ROOT) -> list[str]:
    ms_dir = ms_dir or root / cmn.DEFAULT_MS_DIR
    sub = ms_dir / "submission"
    out: list[str] = []
    units_of: dict[str, list[str]] = {}
    out += [f"EXTRA: {p.name} is not part of the submission set" for p in sorted(sub.iterdir())
            if p.is_file() and p.name not in all_files() and not SUBMITTED.fullmatch(p.name)]
    for name in SPEC:
        path = sub / name
        if not path.exists():
            out.append(f"MISSING: {name}")
            continue
        got = docx_units(path)
        units_of[name] = got
        out += compare(name, got, expected(ms_dir, name))
        if name in CHECKED_WORDING:
            out += wording_problems(name, got)
    for name in list(FIGURES.values()) + [GA]:
        if not (sub / name).exists():
            out.append(f"MISSING: {name}")
    if MANUSCRIPT in units_of:
        out += title_page_problems(units_of[MANUSCRIPT], ms_dir)
        out += word_count_problems(ms_dir, units_of[MANUSCRIPT])
        out += display_problems(sub / MANUSCRIPT, sub / TABLE1)
        out += layout_problems(sub / MANUSCRIPT)
    out += figure_problems(ms_dir)
    out += doi_problems(ms_dir)
    return out


RELEASE_DOI = "release_doi.txt"  # written by the build when --doi is given


def doi_problems(ms_dir: Path) -> list[str]:
    """The release DOI is read as one token by the text tie, so it is checked here: every release DOI
    in the .docx files equals the DOI recorded by the build (release_doi.txt), or every one is the
    placeholder when no DOI was given."""
    want = release_doi(ms_dir)
    out = []
    for name in SPEC:
        p = ms_dir / "submission" / name
        if p.exists():
            out += [f"DOI: {name} holds {d}, the build recorded {want}" for d in wrong_dois(p, want)]
    return out


def release_doi(ms_dir: Path) -> str:
    rec = ms_dir / RELEASE_DOI
    return rec.read_text(encoding="utf-8").strip() if rec.exists() else "10.5281/zenodo.XXXXXXX"


def wrong_dois(path: Path, want: str) -> list[str]:
    """Release DOIs in one .docx that differ from `want`."""
    text = " ".join(" ".join(para_text(e) for e in part(path, "word/document.xml").iter(f"{W}p")).split())
    return [m.group() for m in DOI.finditer(text) if m.group() != want]


def notes(ms_dir: Path) -> list[str]:
    p = ms_dir / "submission" / MANUSCRIPT
    if p.exists() and "zenodo.XXXXXXX" in docx_all_text(p):
        return [f"note: {MANUSCRIPT} still holds the Zenodo DOI placeholder (rebuild with --doi at release)"]
    return []


def main(root: Path = ROOT, argv: list[str] | None = None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    ms_dir, rest = cmn.manuscript_dir(root, argv)
    if rest:
        print(f"FAIL: unknown arguments {rest}")
        return 1
    name = cmn.rel(ms_dir, root)
    if not ms_dir.is_dir() or not (ms_dir / "submission").is_dir():
        print(f"SKIPPED: {name}/ or {name}/submission/ not present (kept private, not in this repository)")
        return 0
    found = problems(ms_dir, root)
    for ln in found:
        print(ln)
    for ln in notes(ms_dir):
        print(ln)
    n_units = sum(len(docx_units(ms_dir / "submission" / n)) for n in SPEC if (ms_dir / "submission" / n).exists())
    print(f"docx tie: {len(all_files())} files; {len(SPEC)} .docx, {n_units} paragraphs and table rows tied to the "
          f"Markdown; title page, abstract and main-text limits; layout; at most {MAX_DISPLAY} display items; "
          f"figures and graphical abstract re-rendered from the exhibits; {len(found)} problem(s)")
    return 1 if found else 0


if __name__ == "__main__":
    sys.exit(main())
