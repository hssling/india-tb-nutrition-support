# Who misses the TB nutrition payment, and where it matters most

Code, extracted data, outputs and a pre-registered analysis plan for a State-level
analysis of the payment chain of India's Ni-kshay Poshan Yojana (NPY), the monthly
direct benefit transfer for nutrition support to notified people with TB. It uses only
published, aggregate, official data: the NPY State tables of the TB Annual Report 2022
and the India TB Reports 2023 and 2024, the matching State treatment-outcome and
notification tables, and the NFHS-5 (2019-21) State and UT fact sheets.

The framing is practice-guiding, for the Central TB Division and the State TB Cells. It is
not a league table: results are given as tiers, not ranks, and they describe programme
data, not the performance or effort of any State's staff. All associations reported here
are observational and ecological; none is a causal estimate.

## Status

Registration stage. The source manifest (`data/source_manifest.csv`), a structure-only
inventory of the source tables (`docs/data_inventory.md`) and the analysis plan
(`docs/analysis_plan.md`) are in place. The plan is registered by its first public push,
recorded in `docs/registration_event.json`, before any estimate is computed.

## Reproducing the source copies

The source PDFs are not redistributed (`data_raw/` is not committed). `tools/fetch_sources.py`
copies them from the author's earlier repositories and checks each against its SHA-256
digest (standard library only):

    python -I tools/fetch_sources.py
    python -I -m pytest -q

## Licences

Code: MIT (`LICENSE`). Derived data: CC BY 4.0 (`LICENSE-DATA`). The source reports remain
the property of their publishers.

## Author

Siddalingaiah H S (ORCID 0000-0002-4771-8285), Department of Community Medicine,
Shridevi Institute of Medical Sciences and Research Hospital, Tumkur 572106, Karnataka,
India. hssling@yahoo.com
