# Adapted from hssling/india-tb-diabetes-gap v1.0.0 (MIT), verification/mutate_manuscript.py (itself
# adapted from hssling/india-tb-priority-tool and hssling/india-tb-acf-campaign); modified: the named
# mutations of this paper's Transactions of The Royal Society of Tropical Medicine and Hygiene set
# (numbers, the title page, superscript references and their placement, table cells, figure and
# graphical-abstract data, labels, signs, identifiers, wording, the abstract, keyword, legend and
# main-text limits, Word's counts, the AI disclosure, caveats, end sections, the layout, figures,
# display items, the cover letter and the file set), applied to copies inside the git-ignored
# manuscript folder; the number-token sweeps kept as --sweep.
"""Mutation test of the manuscript checks (check_manuscript_numbers and check_docx_tie).

Run as: python -I verification/mutate_manuscript.py [--manuscript-dir DIR] [--sweep]

The manuscript folder DIR (default manuscript/; git-ignored) is copied for every mutation into
DIR/_mutations/ (removed afterwards); the real files are never written. The TIFF files of
submission/ are hard-linked into each copy, and a mutation that changes one of them replaces the
link with a new file. Each named mutation (MUTATIONS) changes one thing in the copy, and both
checks run on it: check_manuscript_numbers.problems and check_docx_tie.problems. A mutation is
caught if either reports at least one problem. The unmutated copy must pass both, or nothing is
run.

The manuscript text a mutation edits (its anchor) quotes the manuscript, so it is not kept here: it
is read from "mutation_anchors" in the private DIR/section_phrases.json. A mutation whose anchor is
missing or not found counts as NOT APPLIED and fails the run.

--sweep also bumps the last digit of every number token (a) of manuscript.md outside the
References, which check_manuscript_numbers must catch, and (b) of the text of manuscript.docx,
tables and references included, which check_docx_tie must catch (the text tie, and the release
DOI against the DOI the build recorded).

Prints a table of the results; exits 1 if any mutation is not applied or not caught. Prints
"SKIPPED" and exits 0 when DIR/ or DIR/submission/ is absent.
"""
from __future__ import annotations

import json
import os
import re
import shutil
import sys
import tempfile
import zipfile
from pathlib import Path
from typing import Callable

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from verification import check_docx_tie as tie  # noqa: E402
from verification import check_manuscript_numbers as cmn  # noqa: E402

DOC = "word/document.xml"
SETTINGS = "word/settings.xml"
S = "submission/"
M, SUP, COV = (S + n for n in (tie.MANUSCRIPT, tie.SUPPLEMENT, tie.COVER_DOCX))
FIG1_TIF, FIG2_TIF, GA_TIF = S + tie.FIGURES[1], S + tie.FIGURES[2], S + tie.GA
NUMBER = re.compile(r"\d+(?:,\d{3}(?!\d))*(?:\.\d+)?")
WORK = "_mutations"
LINKED = (".tif",)
MS = cmn.MS_NAME
TP = cmn.TITLE_PAGE
TABLES_MD = "exhibits/tables.md"


class NotApplied(Exception):
    """The mutation's anchor was not found in the copy."""


# --------------------------------------------------------------------------------------
# Editing helpers (on the copy; a file is replaced, never written through a hard link)
# --------------------------------------------------------------------------------------
def replace_bytes(path: Path, data: bytes) -> None:
    tmp = path.with_name(path.name + ".new")
    tmp.write_bytes(data)
    path.unlink()
    tmp.replace(path)


def edit_text(path: Path, old: str, new: str) -> None:
    s = path.read_text(encoding="utf-8")
    if old not in s:
        raise NotApplied(f"{path.name}: {old!r} not found")
    replace_bytes(path, s.replace(old, new, 1).encode("utf-8"))


def rewrite_part(path: Path, part: str, fn: Callable[[str], str]) -> None:
    tmp = path.with_name(path.name + ".mut")
    with zipfile.ZipFile(path) as zi, zipfile.ZipFile(tmp, "w", zipfile.ZIP_DEFLATED) as zo:
        for item in zi.infolist():
            data = zi.read(item.filename)
            if item.filename == part:
                data = fn(data.decode("utf-8")).encode("utf-8")
            zo.writestr(item, data)
    path.unlink()
    tmp.replace(path)


def edit_docx(path: Path, old: str, new: str, part: str = DOC) -> None:
    def fn(xml: str) -> str:
        if old not in xml:
            raise NotApplied(f"{path.name}:{part}: {old!r} not found")
        return xml.replace(old, new, 1)
    rewrite_part(path, part, fn)


def edit_settings(path: Path, old: str, new: str) -> None:
    edit_docx(path, old, new, SETTINGS)


def bump(tok: str) -> str:
    return tok[:-1] + str((int(tok[-1]) + 1) % 10)


def bumped(s: str) -> str:
    m = NUMBER.search(s)
    if not m:
        raise NotApplied(f"no number in anchor {s!r}")
    return s[:m.start()] + bump(m.group()) + s[m.end():]


def flipped(s: str) -> str:
    m = NUMBER.search(s)
    if not m:
        raise NotApplied(f"no number in anchor {s!r}")
    if m.start() > 0 and s[m.start() - 1] == cmn.MINUS:
        return s[:m.start() - 1] + s[m.start():]
    return s[:m.start()] + cmn.MINUS + s[m.start():]


def anchor(d: Path, mid: str):
    try:
        a = cmn.load_phrase_file(d).get("mutation_anchors", {}).get(mid)
    except (OSError, ValueError) as e:
        raise NotApplied(f"{cmn.PHRASES}: {e}") from None
    if not a:
        raise NotApplied(f"no anchor for mutation {mid} in {cmn.PHRASES}")
    return a


def change(edit, rel: str, mid: str, how: Callable[[str], str]) -> Callable[[Path], None]:
    def fn(d: Path) -> None:
        a = anchor(d, mid)
        edit(d / rel, a, how(a))
    return fn


def insert(edit, rel: str, mid: str, extra: Callable[[Path], str], before: bool = False) -> Callable[[Path], None]:
    def fn(d: Path) -> None:
        a, x = anchor(d, mid), extra(d)
        edit(d / rel, a, x + a if before else a + x)
    return fn


def swap(edit, rel: str, mid: str) -> Callable[[Path], None]:
    """The anchor is a pair [old, new]."""
    def fn(d: Path) -> None:
        a = anchor(d, mid)
        if not (isinstance(a, list) and len(a) == 2):
            raise NotApplied(f"anchor of {mid} must be a pair [old, new]")
        edit(d / rel, a[0], a[1])
    return fn


def image(rel: str, size: tuple[int, int], dpi: int, mode: str = "RGB") -> Callable[[Path], None]:
    def fn(d: Path) -> None:
        try:
            from PIL import Image
        except ImportError:
            raise NotApplied("Pillow not installed") from None
        p = d / rel
        p.unlink()
        Image.new(mode, size, "white" if mode == "RGB" else 255).save(p, format="TIFF", dpi=(dpi, dpi))
    return fn


def greyscale_fig1(d: Path) -> None:
    from PIL import Image
    p = d / FIG1_TIF
    with Image.open(p) as im:
        g = im.convert("L")
    p.unlink()
    g.save(p, format="TIFF", compression="tiff_lzw", dpi=(tie.FIG_DPI, tie.FIG_DPI))


def other_figure(d: Path) -> None:
    replace_bytes(d / FIG1_TIF, (d / FIG2_TIF).read_bytes())


def edit_csv(rel: str, old: str, new: str) -> Callable[[Path], None]:
    def fn(d: Path) -> None:
        p = d / "exhibits" / rel
        s = p.read_text(encoding="utf-8")
        if old not in s:
            raise NotApplied(f"{rel}: {old!r} not found")
        replace_bytes(p, s.replace(old, new, 1).encode("utf-8"))
    return fn


def second_table(d: Path) -> None:
    """manuscript.docx: Table 1 duplicated (six display items)."""
    def fn(xml: str) -> str:
        i, j = xml.find("<w:tbl>"), xml.find("</w:tbl>")
        if i < 0 or j < 0:
            raise NotApplied("the manuscript has no table")
        t = xml[i:j + len("</w:tbl>")]
        return xml[:j + len("</w:tbl>")] + t + xml[j + len("</w:tbl>"):]
    rewrite_part(d / M, DOC, fn)


def no_line_numbers(d: Path) -> None:
    def fn(xml: str) -> str:
        new = re.sub(r"<w:lnNumType[^>]*/>", "", xml)
        if new == xml:
            raise NotApplied("no lnNumType in the manuscript")
        return new
    rewrite_part(d / M, DOC, fn)


def justified(d: Path) -> None:
    def fn(xml: str) -> str:
        i = xml.find("<w:pPr>")
        if i < 0:
            raise NotApplied("no paragraph properties in the manuscript")
        return xml[:i] + '<w:pPr><w:jc w:val="both"/>' + xml[i + len("<w:pPr>"):]
    rewrite_part(d / M, DOC, fn)


def stale_counts(d: Path) -> None:
    p = d / "word_counts_word.json"
    w = json.loads(p.read_text(encoding="utf-8"))
    w["abstract"] = tie.LIMITS["abstract"] + 1
    replace_bytes(p, (json.dumps(w, indent=1) + "\n").encode("utf-8"))


def long_main(d: Path) -> None:
    """manuscript.md Discussion: 1,000 words added (the main text over 3,500 words)."""
    a = anchor(d, "9b")
    edit_text(d / MS, a, a + " " + " ".join(["filler"] * 1000))


def long_legend(d: Path) -> None:
    """manuscript.md: the legend of Figure 1 made longer than 200 words."""
    a = anchor(d, "9d")
    edit_text(d / MS, a, a + " " + " ".join(["filler"] * 200))


def release_doi_bumped(d: Path) -> None:
    """manuscript.docx: the first release DOI (or placeholder) changed."""
    def fn(xml: str) -> str:
        m = re.search(r"10\.5281/zenodo\.(?!24411057)(\d+|X+)", xml)
        if not m:
            raise NotApplied("no release DOI in the manuscript")
        tok = m.group(1)
        new = bump(tok) if tok.isdigit() else "1234567"
        return xml[:m.start(1)] + new + xml[m.end(1):]
    rewrite_part(d / M, DOC, fn)


def extra_file(d: Path) -> None:
    (d / S / "notes.txt").write_text("x", encoding="utf-8")


def drop_file(d: Path) -> None:
    (d / COV).unlink()


# --------------------------------------------------------------------------------------
# The named mutations: (id, kind, what is changed, function of the copied folder)
# --------------------------------------------------------------------------------------
Mutation = tuple[str, str, str, Callable[[Path], None]]
MUTATIONS: list[Mutation] = [
    ("1a", "number, docx only", "manuscript.docx Results: the H1 value changed in its last digit", change(edit_docx, M, "1a", bumped)),
    ("1b", "number, docx only", "manuscript.docx title page: Word's abstract count increased by 1", change(edit_docx, M, "1b", bumped)),
    ("1c", "number, docx only", "Supplementary_data.docx Table S6: Bihar's unpaid count changed", change(edit_docx, SUP, "1c", bumped)),
    ("2a", "number, markdown only", "manuscript.md Results: the H2 value changed in its last digit", change(edit_text, MS, "2a", bumped)),
    ("2b", "number, markdown only", "manuscript.md Abstract: the payment-led count increased by 1", change(edit_text, MS, "2b", bumped)),
    ("2c", "number, markdown only", "manuscript.md Methods: the registration time changed", change(edit_text, MS, "2c", bumped)),
    ("2d", "number, markdown only", "manuscript.md Discussion: the effective number of clusters changed", change(edit_text, MS, "2d", bumped)),
    ("2e", "number, markdown only", "title_page_src.md: Word's abstract count changed", change(edit_text, TP, "2e", bumped)),
    ("3a", "title page, docx only", "manuscript.docx: the author's e-mail removed from the title page", swap(edit_docx, M, "3a")),
    ("3b", "title page, markdown", "title_page_src.md: a running title longer than 50 characters", swap(edit_text, TP, "3b")),
    ("3c", "title, markdown", "manuscript.md: the title claims 'first'", swap(edit_text, MS, "3c")),
    ("4a", "reference number, markdown", "manuscript.md Introduction: a citation number increased by 1", change(edit_text, MS, "4a", bumped)),
    ("4b", "reference number, docx only", "manuscript.docx References: entry 2 renumbered 3", swap(edit_docx, M, "4b")),
    ("4c", "reference placement, markdown", "manuscript.md Introduction: a citation placed before its comma", swap(edit_text, MS, "4c")),
    ("4d", "reference order, markdown", "manuscript.md Introduction: two first citations exchanged", swap(edit_text, MS, "4d")),
    ("5a", "table cell, docx only", "manuscript.docx Table 1: U_acc changed", change(edit_docx, M, "5a", bumped)),
    ("5b", "table cell, markdown only", "tables.md Table S6: an act-now unit moved to lower priority", swap(edit_text, TABLES_MD, "5b")),
    ("5c", "table cell, docx only", "Supplementary_data.docx Table S10: Punjab's z changed", change(edit_docx, SUP, "5c", bumped)),
    ("5d", "figure data, exhibits", "figure2_data.csv: an act-now unit set to lower priority",
     edit_csv("figure2_data.csv", ",act now,", ",lower priority,")),
    ("5e", "graphical-abstract data, exhibits", "graphical_abstract_data.csv: the act-now list changed",
     edit_csv("graphical_abstract_data.csv", "Bihar; Maharashtra", "Maharashtra")),
    ("6a", "label, markdown", "manuscript.md Results: H1 'not established' -> 'supported'", swap(edit_text, MS, "6a")),
    ("6b", "label, docx only", "manuscript.docx Results: H3 'supported' -> 'not established'", swap(edit_docx, M, "6b")),
    ("6c", "label, markdown", "manuscript.md Results: H3 called 'confirmed'", swap(edit_text, MS, "6c")),
    ("7a", "sign, markdown", "tables.md Table S10: Punjab's negative z made positive", change(edit_text, TABLES_MD, "7a", flipped)),
    ("7b", "sign, docx only", "Supplementary_data.docx Table S10: Punjab's negative z made positive", change(edit_docx, SUP, "7a", flipped)),
    ("8a", "internal identifier, markdown", "manuscript.md Methods: '(Task 99)' inserted",
     insert(edit_text, MS, "8a", lambda d: " (Task 99)")),
    ("8b", "internal identifier, docx only", "Supplementary_data.docx note: 'ITR2024' inserted",
     insert(edit_docx, SUP, "8b", lambda d: "ITR2024 ", before=True)),
    ("8c", "wording, markdown", "manuscript.md Results: 'paid at least once' written 'paid'", swap(edit_text, MS, "8c")),
    ("8d", "wording, markdown", "manuscript.md Results: a causal claim inserted",
     insert(edit_text, MS, "8d", lambda d: " Payment improved treatment success.")),
    ("8e", "wording, docx only", "manuscript.docx Results: ranking language inserted",
     insert(edit_docx, M, "8e", lambda d: " Uttar Pradesh ranked first.")),
    ("8f", "spelling, markdown", "manuscript.md Introduction: 'Programme' written 'Program'", swap(edit_text, MS, "8f")),
    ("8g", "wording, markdown", "manuscript.md Results: the need weight called a count of undernourished patients",
     insert(edit_text, MS, "8g", lambda d: " It counts undernourished TB patients.")),
    ("8h", "wording, markdown", "manuscript.md Discussion: an unhedged 'first' claim",
     insert(edit_text, MS, "8h", lambda d: " This is the first study of the payment chain.")),
    ("8i", "wording, markdown", "manuscript.md Results: H3 'supported' without 'ecological association'", swap(edit_text, MS, "8i")),
    ("9a", "abstract limit, markdown", "manuscript.md Abstract: twelve words added",
     insert(edit_text, MS, "9a", lambda d: " This sentence adds exactly twelve more words to the abstract for this test.")),
    ("9b", "main-text limit, markdown", "manuscript.md Discussion: 1,000 words added", long_main),
    ("9c", "Word's counts", "word_counts_word.json: the abstract count set over 200", stale_counts),
    ("9d", "legend limit, markdown", "manuscript.md: the legend of Figure 1 over 200 words", long_legend),
    ("9e", "keywords, markdown", "manuscript.md: keywords out of alphabetical order", swap(edit_text, MS, "9e")),
    ("9f", "alt text, markdown", "manuscript.md: the alt text of Figure 1 removed", swap(edit_text, MS, "9f")),
    ("10a", "AI disclosure, cover letter", "cover_letter.md: the AI disclosure changed", swap(edit_text, cmn.COVER, "10a")),
    ("10b", "caveat, markdown", "manuscript.md Results: the Punjab anomaly caveat removed", swap(edit_text, MS, "10b")),
    ("10c", "caveat, markdown", "manuscript.md Methods: the registry caveat removed", swap(edit_text, MS, "10c")),
    ("10d", "end section, markdown", "manuscript.md: 'Competing interests: None declared.' changed", swap(edit_text, MS, "10d")),
    ("11a", "figure, TIFF", "Figure_1.tif replaced by Figure 2", other_figure),
    ("11b", "figure, TIFF", "Figure_1.tif replaced by a 150 dpi image", image(FIG1_TIF, (300, 300), 150)),
    ("11c", "figure, TIFF", "Figure_1.tif converted to greyscale", greyscale_fig1),
    ("11d", "graphical abstract, TIFF", "graphical_abstract.tif replaced by a 2:1 image", image(GA_TIF, (2400, 1200), 300)),
    ("11e", "display items, docx only", "manuscript.docx: Table 1 duplicated (six display items)", second_table),
    ("11f", "layout, docx only", "manuscript.docx: line numbers removed", no_line_numbers),
    ("11g", "layout, docx only", "manuscript.docx: a paragraph justified", justified),
    ("11h", "layout, docx only", "manuscript.docx: automatic hyphenation switched on",
     lambda d: edit_settings(d / M, '<w:autoHyphenation w:val="false"/>', "<w:autoHyphenation/>")),
    ("12a", "file set", "an extra file in submission/", extra_file),
    ("12b", "file set", "cover_letter.docx removed", drop_file),
    ("12c", "cover letter, markdown", "cover_letter.md: a related manuscript removed", swap(edit_text, cmn.COVER, "12c")),
    ("13b", "release DOI, docx only", "manuscript.docx: the release DOI changed in its last digit",
     release_doi_bumped),
    ("13a", "builder text, docx only", "Supplementary_data.docx: the supplement's note changed", swap(edit_docx, SUP, "13a")),
]


# --------------------------------------------------------------------------------------
# Running the checks on a copy
# --------------------------------------------------------------------------------------
def copy_manuscript(src: Path, dst: Path) -> Path:
    """A copy of the folder, without the render output, the PNG previews and the mutation work
    folder; the TIFF files of submission/ are hard-linked."""
    def ignore(d: str, names: list[str]) -> set[str]:
        return {n for n in names if n in ("_render", "__pycache__", WORK) or n.endswith(".png")}

    def copy_fn(s: str, t: str) -> None:
        if s.endswith(LINKED) and "submission" in Path(s).parts:
            try:
                os.link(s, t)
                return
            except OSError:
                pass
        shutil.copy2(s, t)
    shutil.copytree(src, dst, ignore=ignore, copy_function=copy_fn)
    return dst


def cmn_problems(ms_dir: Path) -> list[str]:
    if not (ms_dir / cmn.PHRASES).exists():
        return [f"PHRASES: {cmn.PHRASES} missing"]
    return cmn.problems(ROOT, ms_dir)


def tie_problems(ms_dir: Path) -> list[str]:
    return tie.problems(ms_dir, ROOT)


def run_named(src: Path, mutations: list[Mutation] | None = None) -> list[dict]:
    mutations = MUTATIONS if mutations is None else mutations
    checks = {"check_manuscript_numbers": cmn_problems, "check_docx_tie": tie_problems}
    rows = []
    work = src / WORK
    shutil.rmtree(work, ignore_errors=True)
    work.mkdir()
    try:
        base = copy_manuscript(src, work / "base")
        for name, fn in checks.items():
            found = fn(base)
            if found:
                raise SystemExit(f"the unmutated copy fails {name}; fix that first:\n" + "\n".join(found[:5]))
        shutil.rmtree(base, ignore_errors=True)
        for mid, kind, what, fn in mutations:
            d = copy_manuscript(src, work / f"m{mid}")
            row = {"id": mid, "kind": kind, "what": what, "applied": True, "by": [], "first": ""}
            try:
                fn(d)
            except NotApplied as e:
                row.update(applied=False, first=str(e))
                rows.append(row)
                shutil.rmtree(d, ignore_errors=True)
                continue
            for name, check in checks.items():
                try:
                    found = check(d)
                except Exception as e:  # a check that crashes on the mutated copy has caught it
                    found = [f"{name} raised {type(e).__name__}: {e}"]
                if found:
                    row["by"].append(name)
                    row["first"] = row["first"] or found[0].splitlines()[0]
            rows.append(row)
            shutil.rmtree(d, ignore_errors=True)
    finally:
        shutil.rmtree(work, ignore_errors=True)
    return rows


# --------------------------------------------------------------------------------------
# Sweeps over every number token
# --------------------------------------------------------------------------------------
def md_token_spans(text: str) -> list[tuple[int, int]]:
    """Number tokens of the checked sections (the title and the '## ' sections but the References)."""
    spans, pos, state = [], 0, None
    for line in text.splitlines(keepends=True):
        take = False
        if state is None and line.startswith("# "):
            take, state = True, "front"
        elif line.startswith("## "):
            state = "refs" if line.strip() == "## References" else "body"
        elif state == "body":
            take = True
        if take:
            spans += [(pos + m.start(), pos + m.end()) for m in NUMBER.finditer(line)]
        pos += len(line)
    return spans


def sweep_md(ms: Path) -> tuple[int, int, list[str]]:
    text = (ms / cmn.MS_NAME).read_text(encoding="utf-8")
    gold, required = cmn.load_gold(ms), cmn.section_phrases(ms)
    caught, escaped = 0, []
    spans = md_token_spans(text)
    for a, b in spans:
        mutated = text[:a] + bump(text[a:b]) + text[b:]
        if cmn.problems(ROOT, ms, mutated, gold, required, exhibits=False):
            caught += 1
        else:
            escaped.append(f"...{text[max(0, a - 30):b + 10]}...".replace("\n", " "))
    return caught, len(spans), escaped


def sweep_docx(path: Path, want: list[str], doi: str | None = None) -> tuple[int, int, list[str]]:
    with zipfile.ZipFile(path) as z:
        xml = z.read(DOC).decode("utf-8")
    spans = []
    for m in re.finditer(r"<w:t(?: [^>]*)?>([^<]*)</w:t>", xml):
        spans += [(m.start(1) + t.start(), m.start(1) + t.end()) for t in NUMBER.finditer(m.group(1))]
    caught, escaped = 0, []
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td) / path.name
        for a, b in spans:
            shutil.copyfile(path, tmp)
            rewrite_part(tmp, DOC, lambda _x, a=a, b=b: xml[:a] + bump(xml[a:b]) + xml[b:])
            if tie.compare(path.name, tie.docx_units(tmp), want) or (doi and tie.wrong_dois(tmp, doi)):
                caught += 1
            else:
                escaped.append(xml[max(0, a - 40):b + 10])
    return caught, len(spans), escaped


def main(argv: list[str] | None = None, root: Path = ROOT) -> int:
    argv = sys.argv[1:] if argv is None else argv
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    ms, rest = cmn.manuscript_dir(root, argv)
    unknown = [a for a in rest if a != "--sweep"]
    if unknown:
        print(f"FAIL: unknown arguments {unknown}")
        return 1
    name = cmn.rel(ms, root)
    if not ms.is_dir() or not (ms / "submission").is_dir():
        print(f"SKIPPED: {name}/ or {name}/submission/ not present (kept private, not in this repository)")
        return 0
    rows = run_named(ms)
    bad = 0
    print("| # | Kind | Mutation | Caught by | First problem reported |")
    print("|---|------|----------|-----------|------------------------|")
    for r in rows:
        res = "NOT APPLIED" if not r["applied"] else (" and ".join(r["by"]) if r["by"] else "NOT CAUGHT")
        bad += res in ("NOT APPLIED", "NOT CAUGHT")
        print(f"| {r['id']} | {r['kind']} | {r['what']} | {res} | {r['first'].replace('|', '/')[:110]} |")
    print(f"named mutations: {len(rows) - bad} of {len(rows)} caught")
    if "--sweep" in rest:
        c, t, e = sweep_md(ms)
        print(f"sweep, manuscript.md number tokens (check_manuscript_numbers): caught {c} of {t}")
        for x in e:
            print("  UNCAUGHT", x)
        p = ms / M
        c2, t2, e2 = sweep_docx(p, tie.expected(ms, p.name), tie.release_doi(ms))
        print(f"sweep, {p.name} number tokens (check_docx_tie): caught {c2} of {t2}")
        for x in e2:
            print("  UNCAUGHT", x)
        bad += len(e) + len(e2)
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
