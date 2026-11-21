"""nutpay: the analysis of the TB nutrition-support study (registered analysis plan,
docs/analysis_plan.md, sections 4-10).

Modules: chain (A, P, C, V, the unpaid counts and the national values, sections 3.6, 5.1,
5.2), need (the NFHS-5 merge and the relative need weight, sections 4.2-4.3), shortfall
(the chain priors and draws, the shortfalls and the class rule, sections 5.3-5.4), priority
(the unpaid-rate draws, P(top-5) and tiers, sections 5.3, 6, 8.5), budget (section 9),
trend (section 7), funnel (section 8.3), validate (H1-H3, the grids, the label and
leave-one-out, sections 8.1-8.6), perturb (section 8.7), table (CSV writing). The run is
src/run_all.py.

tbprio 1.0.1 is imported and called, never copied or modified (section 10.1). Every run
starts with check_tbprio(), which stops unless the installed tbprio is version 1.0.1 and
its source files are byte-identical to tag v1.0.1.
"""
from __future__ import annotations

import hashlib
import importlib.metadata
from pathlib import Path

TBPRIO_VERSION = "1.0.1"
SEED = 20261123
CHAIN_STREAM = (SEED, 1)
N_DRAWS = 10_000
YEARS = (2021, 2022, 2023)
HEADLINE_YEAR = 2023

# SHA-256 of src/tbprio/* at tag v1.0.1 of hssling/india-tb-priority-tool
# (DOI 10.5281/zenodo.24411057), from `git show v1.0.1:src/tbprio/<file> | sha256sum`.
TBPRIO_V101 = {
    "__init__.py": "4067d1c97393be078a199753d5c9402a56337eb5b07cfe88273448d15f871d22",
    "__main__.py": "4fdbd07dc7384b8ada292817a8b9f1692a381c539579db5fb3fb544eb966493f",
    "district.py": "815e10f7ab9529b93a1a3a574269bf84a5db1623438bbd90a5dcbfaffd429f93",
    "harm.py": "3e60565c319f7b38553d39bb25055cefa57ddfdf9348197879ea33f8c637f0a1",
    "panel.py": "235d992b123e8ea50eedeba13346d6c44bca6104ee130a940154dad079b17d84",
    "priority.py": "f5557a434394729ad748bb0fa5b25a9fe01e052cb0df6d4cc5f4e8318162f116",
    "report.py": "f1ff4cdf80a0593e055494ecdd1b1363a5ba6b7923bc815d21d49738773396be",
    "schema.py": "39688c1cb76ec47cdac6a745074c756ebdedff74353f13bbbf860d28acd13df8",
    "shrink.py": "b95859662e7855020319cfad398b97f32d38c5c33d0b4243ceeff75f5e5c4f4b",
    "state.py": "1b7ec61f514ebb518841bf7c18d5ef3479516ae8d3785ee7ab1584c48fad5c57",
    "table.py": "0a99d43157a84186b76ece3e12272e723886a41bc20b6442ea533ef85570b97c",
    "trend.py": "5fc582f329ac11f066419f162da3e5eb432e3319b042e548cbc6bede962870a8",
    "validate.py": "3f35042dbad52cf2996495f68e54a838535def51be4150276a4a0af37026bef0",
}


def check_tbprio() -> str:
    """Stop unless the installed tbprio reports version 1.0.1 and its source files match
    tag v1.0.1 byte for byte (plan section 10.1)."""
    import tbprio

    v = importlib.metadata.version("tbprio")
    if v != TBPRIO_VERSION:
        raise RuntimeError(f"tbprio {v} is installed; the plan pins {TBPRIO_VERSION}")
    src = Path(tbprio.__file__).resolve().parent
    files = sorted(p.name for p in src.glob("*.py"))
    if files != sorted(TBPRIO_V101):
        raise RuntimeError(f"tbprio source files {files} differ from tag v1.0.1")
    for name, digest in TBPRIO_V101.items():
        got = hashlib.sha256((src / name).read_bytes()).hexdigest()
        if got != digest:
            raise RuntimeError(f"tbprio {name} differs from tag v1.0.1 ({got})")
    return v
