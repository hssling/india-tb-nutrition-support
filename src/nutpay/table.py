"""Deterministic CSV writing: UTF-8, LF, floats by repr, None as an empty cell, NaN as NA.

Adapted from hssling/india-tb-diabetes-gap v1.0.0 (MIT), src/dmgap/table.py.
"""
from __future__ import annotations

import csv
from pathlib import Path

import numpy as np


def fmt(v) -> str:
    if v is None:
        return ""
    if isinstance(v, (bool, np.bool_)):
        return "True" if v else "False"
    if isinstance(v, (float, np.floating)):
        v = float(v)
        if v != v:
            return "NA"
        return repr(v)
    if isinstance(v, (int, np.integer)):
        return str(int(v))
    if isinstance(v, (list, tuple)):
        return ";".join(fmt(x) for x in v)
    return str(v)


def write(path: Path, rows: list[dict], columns: list[str] | None = None) -> Path:
    """Write rows; columns default to the union of keys in first-seen order."""
    if columns is None:
        columns = []
        seen = set()
        for r in rows:
            for k in r:
                if k not in seen:
                    seen.add(k)
                    columns.append(k)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f, lineterminator="\n")
        w.writerow(columns)
        for r in rows:
            extra = set(r) - set(columns)
            if extra:
                raise ValueError(f"{path.name}: columns not declared: {sorted(extra)}")
            w.writerow([fmt(r.get(c)) for c in columns])
    return path
