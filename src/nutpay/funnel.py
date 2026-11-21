"""The funnel of C(2023) against D (analysis plan section 8.3).

Over the units with non-NA C in the year: c_bar = sum Q / sum D, z_u = (Q_u - D_u c_bar) /
sqrt(D_u c_bar (1 - c_bar)); phi_f = tbprio.district.winsorised_phi(z); the limits +/-1.96
(95%) and +/-3.09 (99.8%) are multiplied by tbprio.district.widen(phi_f). A unit below the
lower 99.8% limit is flagged; positions between the 95% and 99.8% limits are reported. The
funnel has no label.
"""
from __future__ import annotations

import math

from tbprio import district as tbd

Z95, Z998 = 1.96, 3.09
FLAG_LOW = "coverage well below the pooled level for its size"
FLAG_HIGH = "coverage well above the pooled level for its size (descriptive)"


def compute(chain_rows: list[dict], year: int = 2023) -> list[dict]:
    rows = sorted((r for r in chain_rows if r["year"] == year and r["C"] is not None),
                  key=lambda r: r["unit"])
    cbar = sum(r["Q"] for r in rows) / sum(r["D"] for r in rows)
    z = [(r["Q"] - r["D"] * cbar) / math.sqrt(r["D"] * cbar * (1.0 - cbar)) for r in rows]
    phi = tbd.winsorised_phi(z)
    wf = tbd.widen(phi)
    l95, l998 = Z95 * wf, Z998 * wf
    out = []
    for r, zu in zip(rows, z):
        if zu < -l998:
            pos, flag = "below the 99.8% limit", FLAG_LOW
        elif zu < -l95:
            pos, flag = "between the 95% and 99.8% limits (below)", ""
        elif zu > l998:
            pos, flag = "above the 99.8% limit", FLAG_HIGH
        elif zu > l95:
            pos, flag = "between the 95% and 99.8% limits (above)", ""
        else:
            pos, flag = "within the 95% limits", ""
        out.append({"unit": r["unit"], "year": year, "Q": r["Q"], "D": r["D"], "C": r["C"],
                    "c_bar": cbar, "z": zu, "phi_f": phi, "widen": wf, "lower_95": -l95,
                    "upper_95": l95, "lower_998": -l998, "upper_998": l998,
                    "position": pos, "flag": flag})
    return out
