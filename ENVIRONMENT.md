# Environment

Every script is run as `python -I <script>` from the repository root, with LF line
endings (`.gitattributes`). The source manifest and the data inventory were produced with:

- Windows 11 Pro (64-bit)
- Python 3.14.0
- pytest 9.0.0: the tests
- pdfplumber 0.11.8 (pdfminer.six 20251107): the extraction of the tables from the PDFs
  (`src/extract/`; `data/extracted/` is reproduced byte for byte by re-running
  `python -I src/extract/itr_npy.py`, `itr_outcomes.py`, `itr_sector.py` and `nfhs.py`)
- PyMuPDF 1.27.2.3: locating pages and reading table headers, total rows and the NFHS-5
  indicator lines as text, for the inventory only

`tools/fetch_sources.py` and `tests/test_manifest.py` use the standard library only (plus
pytest). The analysis, once added, will use numpy 2.3.5 and scipy 1.16.3 and will import
`tbprio` pinned to v1.0.1 (`pyproject.toml`):

    python -I -m pip install "tbprio @ git+https://github.com/hssling/india-tb-priority-tool@v1.0.1"

| Component | Version |
|---|---|
| Operating system | Windows 11 Pro (64-bit) |
| Python | 3.14.0 |
| pytest | 9.0.0 |
| pdfplumber | 0.11.8 |
| PyMuPDF | 1.27.2.3 |
