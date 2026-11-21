"""Verify the source documents in data_raw/ against their SHA-256 digests and write the manifest.

Run as: python -I tools/fetch_sources.py   (stdlib only; from the repository root)

No file is downloaded. Outside the author's workspace, download each source from its upstream
URL (listed below and in data/source_manifest.csv), save it at the listed path under data_raw/,
and run this script: it verifies the files already in place. A file that is missing is copied
from a sibling folder only if that folder exists. The India TB Reports are copied from the sibling
repository ../tb_priority_tool/data_raw/india_tb_report/, which holds them as
downloaded from tbcindia.mohfw.gov.in; the pinned digests below are those in that
repository's manifest (../tb_priority_tool/data/source_manifest.csv), and when that
manifest is present each pinned digest is also checked against it.

The two NFHS-5 fact-sheet compendiums are copied from the sibling repository
../tb_diabetes_gap/data_raw/nfhs5/; their pinned digests are those in
../tb_diabetes_gap/data/source_manifest.csv, checked the same way when present.

Every file is checked against its pinned digest before the manifest
data/source_manifest.csv (columns path, origin, bytes, sha256) is written. A
mismatch is an error and the manifest is not written.
"""
from __future__ import annotations

import csv
import hashlib
import os
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SIBLINGS = ROOT.parent
SIBLING_MANIFESTS = [SIBLINGS / "tb_priority_tool" / "data" / "source_manifest.csv",
                     SIBLINGS / "tb_diabetes_gap" / "data" / "source_manifest.csv"]
MANIFEST = ROOT / "data" / "source_manifest.csv"
FIELDS = ["path", "origin", "bytes", "sha256"]
CHUNK = 1 << 20

NFHS_ORIGIN = ("https://dhsprogram.com/pubs/pdf/OF43/{name} (NFHS-5 India and State fact sheet "
               "compendium, {phase})")

# (path in this repo, sibling copy relative to the parent folder (None only for
#  author-supplied files), upstream origin, pinned sha256)
SOURCES: list[tuple[str, str | None, str, str]] = [
    ("data_raw/india_tb_report/India-TB-Report-2019.pdf",
     "tb_priority_tool/data_raw/india_tb_report/India-TB-Report-2019.pdf",
     "https://tbcindia.mohfw.gov.in/wp-content/uploads/2023/05/India-TB-Report-2019.pdf",
     "87e546751372ba157cb9eba1620173d54aad0fb99abc1b99f4302e9a2005c03b"),
    ("data_raw/india_tb_report/ITR2020.pdf",
     "tb_priority_tool/data_raw/india_tb_report/ITR2020.pdf",
     "https://tbcindia.mohfw.gov.in/wp-content/uploads/2023/05/India-TB-Report-2020.pdf",
     "63b9408015dae510858e0eef2711e809d398bfe3149dd21c94390b258c007e7e"),
    ("data_raw/india_tb_report/TBAnnaulReport2022.pdf",
     "tb_priority_tool/data_raw/india_tb_report/TBAnnaulReport2022.pdf",
     "https://tbcindia.mohfw.gov.in/wp-content/uploads/2023/05/TBAnnaulReport2022.pdf",
     "dc9ff4a88a28eb87232770d0956fe92b2b266b15e5794f879a7335b7c083418b"),
    ("data_raw/india_tb_report/ITR2023.pdf",
     "tb_priority_tool/data_raw/india_tb_report/ITR2023.pdf",
     "https://tbcindia.mohfw.gov.in/wp-content/uploads/2023/05/5646719104TB_AR_2023_04-04-2023_LRP_final.pdf",
     "0817ac3a1e7a03273438073d4e685f88aa93507ad115ec5c6588edfddc8f0b7b"),
    ("data_raw/india_tb_report/ITR2024.pdf",
     "tb_priority_tool/data_raw/india_tb_report/ITR2024.pdf",
     "https://tbcindia.mohfw.gov.in/wp-content/uploads/2024/10/TB-Report_for-Web_08_10-2024-1.pdf",
     "e37f9f406153b5e9a19726538c3f4d09dc4c470281c34fe511adaa56a0e22765"),
    ("data_raw/nfhs5/NFHS-5_India_and_State_Factsheet_Compendium_Phase-I.pdf",
     "tb_diabetes_gap/data_raw/nfhs5/NFHS-5_India_and_State_Factsheet_Compendium_Phase-I.pdf",
     NFHS_ORIGIN.format(name="NFHS-5_India_and_State_Factsheet_Compendium_Phase-I.pdf", phase="Phase I"),
     "5bcc2a37b13ffc0203d736803f72aece88b4beb0bc168d1f069e110178ab2bd7"),
    ("data_raw/nfhs5/NFHS-5_India_and_State_Factsheet_Compendium_Phase-II.pdf",
     "tb_diabetes_gap/data_raw/nfhs5/NFHS-5_India_and_State_Factsheet_Compendium_Phase-II.pdf",
     NFHS_ORIGIN.format(name="NFHS-5_India_and_State_Factsheet_Compendium_Phase-II.pdf", phase="Phase II"),
     "3e8ee12bb4a59e9ec2e7bebc736b2252d61e9ed98ce322717debe11dd73c52b7"),
]


def sha256_of(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(CHUNK), b""):
            h.update(block)
    return h.hexdigest()


def sibling_digests() -> dict[str, str]:
    """sha256 by sibling path (relative to the parent folder), from the sibling
    repositories' manifests; empty if none is present."""
    out: dict[str, str] = {}
    for manifest in SIBLING_MANIFESTS:
        if not manifest.is_file():
            continue
        repo = manifest.parents[1].name
        with open(manifest, newline="", encoding="utf-8") as f:
            out.update({f"{repo}/" + r["path"]: r["sha256"] for r in csv.DictReader(f)})
    return out


def check_pins(recorded: dict[str, str]) -> None:
    """Each pinned digest of a sibling copy must equal the sibling manifest's."""
    if not recorded:
        print("sibling manifests absent; using pinned digests")
        return
    for _path, sibling, _upstream, pinned in SOURCES:
        if sibling is None or not recorded:
            continue
        if sibling not in recorded:
            raise ValueError(f"not in the sibling manifest: {sibling}")
        if recorded[sibling] != pinned:
            raise ValueError(f"pinned digest differs from the sibling manifest: {sibling}")


def bring(path: str, sibling: str | None, pinned: str, upstream: str = "") -> str:
    """Copy (if missing) and verify one source; return a status line.
    Raises ValueError on a digest mismatch, FileNotFoundError if absent."""
    dest = ROOT / path
    how = "verified"
    if not dest.is_file():
        if sibling is None:
            raise FileNotFoundError(f"author-supplied file missing: {path}")
        src = SIBLINGS / sibling
        if not src.is_file():
            raise FileNotFoundError(f"sibling copy missing: {src}; download {upstream.split(' (')[0]} "
                                    f"and save it as {path}, then rerun")
        dest.parent.mkdir(parents=True, exist_ok=True)
        part = dest.with_name(dest.name + ".part")
        try:
            shutil.copyfile(src, part)
            if sha256_of(part) != pinned:
                raise ValueError(f"SHA-256 mismatch in copy of {src}")
            os.replace(part, dest)
        finally:
            part.unlink(missing_ok=True)
        how = f"copied from ../{sibling}"
    actual = sha256_of(dest)
    if actual != pinned:
        raise ValueError(f"SHA-256 mismatch for {path}: expected {pinned}, got {actual}")
    return f"{how}: {path}"


def origin_of(sibling: str | None, upstream: str) -> str:
    if sibling is None:
        return upstream
    return f"local copy of ../{sibling}; upstream {upstream}"


def main() -> int:
    try:
        check_pins(sibling_digests())
    except ValueError as e:
        print(f"FAILED: {e}; manifest not written", file=sys.stderr)
        return 1
    rows, failed = [], 0
    for path, sibling, upstream, pinned in SOURCES:
        try:
            print(bring(path, sibling, pinned, upstream))
        except (ValueError, OSError) as e:
            failed += 1
            print(f"FAILED {path}: {e}", file=sys.stderr)
            continue
        rows.append({"path": path, "origin": origin_of(sibling, upstream),
                     "bytes": str((ROOT / path).stat().st_size), "sha256": pinned})
    if failed:
        print(f"{failed} of {len(SOURCES)} sources failed; manifest not written", file=sys.stderr)
        return 1
    MANIFEST.parent.mkdir(parents=True, exist_ok=True)
    tmp = MANIFEST.with_name(MANIFEST.name + ".tmp")
    with open(tmp, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS, lineterminator="\n")
        w.writeheader()
        w.writerows(rows)
    os.replace(tmp, MANIFEST)
    print(f"{len(rows)} of {len(SOURCES)} sources verified; wrote {MANIFEST.relative_to(ROOT).as_posix()}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
