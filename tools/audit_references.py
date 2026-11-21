# Adapted from hssling/india-tb-diabetes-gap v1.0.0 (MIT), tools/audit_references.py (itself adapted
# from hssling/india-tb-priority-tool and hssling/india-tb-acf-campaign); modified: Oxford SCIMED
# references ("Authors. Title. Journal Year;Vol:pages. https://doi.org/..."), with articles in press,
# the released [software] and the study's own [dataset] (Zenodo, a DataCite DOI that Crossref does
# not hold), web sources with "[accessed D Month YYYY]" verified against data/source_manifest.csv,
# and the programme facts the text cites from the reports checked on their pages.
"""Verify every reference of the manuscript and write <manuscript folder>/reference_audit.md.

Run as: python -I tools/audit_references.py [--manuscript-dir DIR]   (default: manuscript)

- A reference with a Crossref DOI: the DOI is resolved through the Crossref REST API
  (https://api.crossref.org/works/<doi>; read-only; a generic User-Agent and no e-mail). It
  passes if (1) Crossref's title (markup removed) occurs in the entry, compared without case,
  punctuation or spaces; (2) the cited year is Crossref's issued, print or online year; (3) the
  cited journal is a valid abbreviation of Crossref's container title (each word, in order, a
  letter-subsequence of a title word with the same first letter) or of its short title; (4) the
  cited volume and first page (or article number) equal Crossref's where Crossref gives them; an
  article in press has neither; (5) every family name Crossref lists among the first six authors
  occurs in the entry (for an "et al." entry, among the first three).
- A Zenodo DOI (10.5281/zenodo.*) is a DataCite DOI and is not looked up: the [dataset] entry may
  hold the release placeholder; the [software] entry must name its version.
- A reference without a DOI: its URL must be the upstream address of a file in
  data/source_manifest.csv, whose SHA-256 is re-verified when data_raw/ holds the file; the facts
  the manuscript cites from that report (FACTS) are found on their pages. An official web page
  without a local copy must be listed in WEB_PAGES with what was read on it.
Nothing is downloaded except Crossref's JSON records. Refuses to write into a folder (or its
submission/) holding a SUBMITTED_* file. Exit 1 if any reference fails.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import html
import json
import re
import sys
import time
import unicodedata
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
UA = "reference-audit/1.0"
MS_NAME = "manuscript.md"
# Official web pages cited without a local copy: read online (read only, nothing downloaded) on the
# accessed date, with what was found on them.
WEB_PAGES = {
    "https://tbcindia.mohfw.gov.in/press-release-link-on-pib-4/":
        "official Central TB Division page reproducing the press release of 7 December 2024, read online (not "
        "downloaded); it states that the Ni-kshay Poshan amount was increased from Rs 500 to Rs 1000 per month "
        "for all TB patients; it gives no effective date. The release of 7 October 2024 on pib.gov.in did not open",
}
# Facts the text cites from a report: (file name, 1-based PDF page, phrase found on the page).
FACTS = {
    "ITR2023.pdf": [(113, "launched the NPY scheme in April 2018"), (114, "Rs 500 per month"),
                    (114, "within 15 days of treatment initiation"), (26, "bank account of a blood relative")],
    "ITR2024.pdf": [(28, "Pradhan Mantri TB Mukt Bharat Abhiyaan in September 2022"), (28, "Ni-kshay Mitras"),
                    (309, "Nikshay Poshan Yojana")],
    "TBAnnaulReport2022.pdf": [(143, "BENEFICIARIES PAID AT LEAST ONE BENEFIT")],
}


def norm(s: str) -> str:
    s = html.unescape(s).replace("’", "").replace("'", "")
    s = re.sub("[‐-―]", "-", s)
    s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9]+", " ", s).strip()


def compact(s: str) -> str:
    return norm(re.sub(r"<[^>]+>", "", s)).replace(" ", "")


def crossref(doi: str) -> dict:
    req = urllib.request.Request("https://api.crossref.org/works/" + urllib.parse.quote(doi),
                                 headers={"User-Agent": UA})
    for attempt in range(4):
        try:
            with urllib.request.urlopen(req, timeout=60) as r:
                return json.load(r)["message"]
        except urllib.error.HTTPError as e:
            if e.code != 429 or attempt == 3:
                raise
            time.sleep(5 * (attempt + 1))
    raise RuntimeError("unreachable")


def years(m: dict) -> set[int]:
    out = set()
    for k in ("issued", "published-print", "published-online", "published"):
        dp = (m.get(k) or {}).get("date-parts") or [[None]]
        if dp[0] and dp[0][0]:
            out.add(int(dp[0][0]))
    return out


def subseq(a: str, w: str) -> bool:
    it = iter(w)
    return a[:1] == w[:1] and all(ch in it for ch in a)


def abbrev_ok(abbr: str, full: str) -> bool:
    words = norm(full).split()
    i = 0
    for a in norm(abbr).split():
        while i < len(words) and not subseq(a, words[i]):
            i += 1
        if i == len(words):
            return False
        i += 1
    return True


SOURCE = re.compile(r" (?P<year>\d{4});(?P<vol>\d+):(?P<pages>[^.\s]+)\. https://doi\.org/")
PRESS = re.compile(r" (?P<year>\d{4})\. https://doi\.org/")


def journal_of(entry: str, m: re.Match) -> str:
    """The text between the last '. ' before the year and the year: the journal abbreviation."""
    return entry[:m.start()].rsplit(". ", 1)[-1].strip()


def cited(ms_dir: Path) -> dict[int, str]:
    ms = (ms_dir / MS_NAME).read_text(encoding="utf-8")
    refs = ms.split("\n## References", 1)[1].split("\n## ", 1)[0]
    return {int(m.group(1)): m.group(2) for m in re.finditer(r"(?m)^(\d+)\. (.+)$", refs)}


def doi_check(n: int, entry: str, doi: str) -> tuple[str, bool]:
    m = crossref(doi)
    title = (m.get("title") or [""])[0]
    journal = (m.get("container-title") or [""])[0]
    short = m.get("short-container-title") or []
    t_ok = compact(title) in compact(entry)
    e = SOURCE.search(entry)
    press = e is None
    if press:
        e = PRESS.search(entry)
    cj = journal_of(entry, e) if e else ""
    y_ok = bool(e) and int(e.group("year")) in years(m)
    j_ok = bool(e) and (norm(cj) == norm(journal) or abbrev_ok(cj, journal) or any(abbrev_ok(cj, s) for s in short))
    if e and not press:
        first = e.group("pages").split("–")[0]
        cr_first = (m.get("page") or "").split("-")[0] or (m.get("article-number") or "")
        v_ok = (not m.get("volume") or e.group("vol") == m["volume"]) and (not cr_first or first == cr_first)
    else:
        v_ok = bool(e) and not m.get("volume") and not m.get("page")  # in press: neither yet
    authors = entry.split(". ", 1)[0]
    k = 3 if authors.endswith("et al") else 6
    fams = [a.get("family", "") for a in (m.get("author") or [])[:k] if a.get("family")]
    a_ok = all(norm(f) in norm(authors) for f in fams)
    ok = t_ok and y_ok and j_ok and v_ok and a_ok
    meta = "; ".join(x for x in [html.unescape(journal), "/".join(str(y) for y in sorted(years(m))),
                                 f"vol {m['volume']}" if m.get("volume") else "no volume (in press)",
                                 f"pp {m['page']}" if m.get("page") else "",
                                 f"art {m['article-number']}" if m.get("article-number") else "",
                                 f"authors {', '.join(fams)}" if fams else "group or no personal author"] if x)
    flags = (f"title {'yes' if t_ok else 'NO'}, year {'yes' if y_ok else 'NO'}, journal '{cj}' "
             f"{'yes' if j_ok else 'NO'}, volume/page {'yes' if v_ok else 'NO'}, authors {'yes' if a_ok else 'NO'}")
    clean = re.sub(r"\s+", " ", re.sub(r"<[^>]+>", "", html.unescape(title))).strip()
    return f"| {n} | {doi} | {clean} | {meta} | {flags} | {'yes' if ok else 'NO'} |", ok


def zenodo_check(n: int, entry: str, doi: str) -> tuple[str, bool]:
    if "[dataset]" in entry:
        ok = "XXXXXXX" in doi or doi.split(".")[-1].isdigit()
        state = "release placeholder (filled with --doi at release)" if "XXXXXXX" in doi else "Zenodo version DOI"
        return f"| {n} | {doi} | [dataset] the study's repository | {state}; DataCite, not looked up | — | {'yes' if ok else 'NO'} |", ok
    ok = bool(re.search(r"version \d+\.\d+\.\d+", entry)) and doi.split(".")[-1].isdigit() and "[software]" in entry
    name = entry.split(". ", 2)[1]
    return (f"| {n} | {doi} | [software] {name} | Zenodo version DOI of released software (DataCite, not looked up; "
            f"only Crossref metadata may be downloaded); version named: {'yes' if ok else 'NO'} | — | "
            f"{'yes' if ok else 'NO'} |"), ok


def sha(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def facts_state(path: Path) -> str:
    want = FACTS.get(path.name, [])
    if not want or not path.exists():
        return ""
    try:
        import fitz  # PyMuPDF, used only to read the cited pages
    except ImportError:
        return "; facts not re-read (PyMuPDF absent)"
    doc = fitz.open(str(path))
    found = sum(phrase in " ".join(doc[p - 1].get_text().split()) for p, phrase in want)
    return f"; cited facts found on their pages: {found} of {len(want)}"


def non_doi_check(n: int, entry: str, root: Path) -> tuple[str, bool]:
    with open(root / "data" / "source_manifest.csv", newline="", encoding="utf-8") as f:
        man = list(csv.DictReader(f))
    url = re.search(r"Available at: (https?://\S+) \[accessed (\d{1,2} \w+ \d{4})\]\.$", entry)
    if not url:
        return f"| {n} | none | {entry[:70]} | no DOI, no URL with an [accessed ...] date | — | NO |", False
    hit = [r for r in man if ("upstream " + url.group(1)) in r["origin"]]
    if not hit and url.group(1) in WEB_PAGES:
        return (f"| {n} | none | {url.group(1)} | {WEB_PAGES[url.group(1)]}; accessed {url.group(2)} | — | yes |"), True
    if not hit:
        return f"| {n} | none | {entry[:70]} | URL not in data/source_manifest.csv | — | NO |", False
    states = []
    ok = True
    for r in hit:
        p = root / r["path"]
        st = ("SHA-256 verified" if p.exists() and sha(p) == r["sha256"] else
              "SHA-256 DIFFERS" if p.exists() else "local copy absent (digest not re-verified)")
        fs = facts_state(p)
        ok = ok and "DIFFERS" not in st and not re.search(r"found on their pages: (\d+) of (?!\1\b)", fs)
        states.append(f"{Path(r['path']).name}: {st}{fs}")
    return (f"| {n} | none | {'; '.join(Path(r['path']).name for r in hit)} | upstream URL in data/source_manifest.csv; "
            f"{'; '.join(states)}; accessed {url.group(2)} | — | {'yes' if ok else 'NO'} |"), ok


def submitted_markers(ms_dir: Path) -> list[Path]:
    """SUBMITTED_* files in the folder or its submission/ (a frozen, submitted set)."""
    out = []
    for d in (ms_dir, ms_dir / "submission"):
        if d.is_dir():
            out += [p for p in d.iterdir() if p.is_file() and p.name.startswith("SUBMITTED_")]
    return out


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0], allow_abbrev=False)
    ap.add_argument("--manuscript-dir", default="manuscript")
    a = ap.parse_args(argv)
    ms_dir = Path(a.manuscript_dir)
    ms_dir = ms_dir if ms_dir.is_absolute() else ROOT / ms_dir
    frozen = submitted_markers(ms_dir)
    if frozen:
        raise SystemExit(f"refusing to write: {', '.join(p.name for p in frozen)} marks {ms_dir} as submitted; "
                         f"put post-submission changes in a new folder (for example a _v2 folder)")
    rows, bad = [], 0
    for n, entry in sorted(cited(ms_dir).items()):
        d = re.search(r"https://doi\.org/(\S+?)\.?$", entry)
        if d and d.group(1).startswith("10.5281/zenodo."):
            line, ok = zenodo_check(n, entry, d.group(1))
        elif d:
            line, ok = doi_check(n, entry, d.group(1))
            time.sleep(1)
        else:
            line, ok = non_doi_check(n, entry, ROOT)
        rows.append(line)
        bad += not ok
    out = ["# Reference audit", "",
           "Written by tools/audit_references.py. DOIs resolved through the Crossref REST API "
           "(api.crossref.org/works/<doi>; generic User-Agent, no e-mail); Zenodo (DataCite) DOIs not looked up; "
           "web sources checked against data/source_manifest.csv, with the facts cited from them found on their "
           "pages. Nothing else was downloaded.", "",
           "| Ref | DOI | Crossref title (or source) | Crossref metadata (or verification) | Checks | Pass |",
           "|---|---|---|---|---|---|", *rows, "", f"Problems: {bad}."]
    (ms_dir / "reference_audit.md").write_text("\n".join(out) + "\n", encoding="utf-8", newline="\n")
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    for r in rows:
        if r.endswith("| NO |"):
            print(r)
    print(f"{len(rows)} references audited; {bad} problem(s); wrote {(ms_dir / 'reference_audit.md').as_posix()}")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
