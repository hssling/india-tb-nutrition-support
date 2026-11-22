# Mutation record

<!-- Adapted from hssling/india-tb-diabetes-gap v1.0.0 (MIT), verification/MUTATIONS.md; modified: this repository's checks and mutations -->

Each check was shown to fail on a deliberate break (analysis plan section 10.3). All breaks
were made in a scratch clone (`git clone <repo> <scratch>`), never in this repository or
its history; the clone was restored (`git checkout -- .`, and `git reset --hard HEAD~1` after
the committed plan edit) between runs. Run on 22 November 2026 against commit 9a019f1. The
same breaks are also exercised by `tests/test_verification.py` on temporary copies.

| # | Check | Break | Result |
|---|-------|-------|--------|
| 1 | check_outputs | headline value: `headline.csv` H1 estimate + 0.01 | caught (FAIL, exit 1) |
| 2 | check_plan_order | `docs/analysis_plan.md` "10,000 draws" to "5,000 draws", above section 12; first uncommitted, then committed | caught both times (FAIL, exit 1) |
| 3 | check_outputs | label flipped: `headline.csv` H3_success "supported" to "not established" | caught (FAIL, exit 1) |
| 4 | check_outputs, check_extraction_totals | extracted cell: `npy_panel.csv` Bihar 2023 paid + 1 | caught by both (FAIL, exit 1) |
| 5 | check_outputs | `need_weight.csv` Gujarat sex-weighted wt_u x 1.001 | caught (FAIL, exit 1) |
| 6 | check_outputs | budget rate: `budget.csv` main row rate 1,000 to 1,100 with its cost recomputed to match | caught (FAIL, exit 1) |
| 7 | check_deviations | a README line "A further deviation was made in data year 2021." | caught (FAIL, exit 1) |
| 8 | check_rerun | one byte of `outputs/trend.csv` ("estimated" to "Estimated") | caught (FAIL, exit 1) |
| 9 | check_rounding | `npy_panel.csv` Bihar 2023 paid flagged `derived_from_percent` | caught (FAIL, exit 1) |

## Printed results

```
# 1. outputs/headline.csv, H1 estimate + 0.01
FAIL: (e) H1 estimate: printed '0.02906158357771261' but recomputed 0.01906158357771261
FAIL: (e) H1 main entry is the headline: printed '0.01906158357771261' but expected '0.02906158357771261'

# 2. docs/analysis_plan.md above section 12 (uncommitted, then committed)
FAIL: the working-tree docs/analysis_plan.md above section 12 differs from its content at the registration commit c1d2f04 (an uncommitted edit)
FAIL: commit 9621396: docs/analysis_plan.md above section 12 differs from its content at the registration commit c1d2f04

# 3. outputs/headline.csv, H3_success label
FAIL: (g) H3_success label: printed 'not established' but expected 'supported'

# 4. data/extracted/npy_panel.csv, Bihar 2023 paid + 1
FAIL: (a) Bihar 2023 Q: printed 113895 but expected 113896     (check_outputs; more lines follow for C and the national figures)
FAIL: npy_panel.csv: 2023 paid: panel sum 1875511 != printed rows 1875510     (check_extraction_totals)

# 5. outputs/need_weight.csv, Gujarat sex_weighted wt_u x 1.001
FAIL: (b) Gujarat sex_weighted wt_u: printed '1.288089169070372' but recomputed 1.2868023667036685

# 6. outputs/budget.csv, main rate 1100 and cost 4,223,769,000
FAIL: (d) main: main rate_per_month: printed 1100 but expected 1000
FAIL: (d) main: main cost: printed 4223769000 but expected 3839790000

# 7. README.md
FAIL: README.md line 285: labelled 'deviation' but names no dated plan 12 entry that carries that label

# 8. outputs/trend.csv, one byte
FAIL: outputs/trend.csv differs from the analysis rerun

# 9. data/extracted/npy_panel.csv, derived_from_percent flag
FAIL: a count derived from a percentage (npy_panel.csv: Bihar): run the rerun of plan 8.9
```

Every command exited 1. The scratch clone had `data_raw/` copied in, so check_rerun also
ran the extraction rerun (reproduced byte for byte before mutation 8).

## Manuscript checks

`verification/mutate_manuscript.py` breaks one thing at a time in a copy of the private
manuscript folder and runs `check_manuscript_numbers` and `check_docx_tie` on the copy (the
anchors it edits quote the manuscript, so they are kept in the private folder). Run on
22 November 2026: 61 of 61 named mutations caught. They cover numbers changed in the
Markdown only or in the submission files only (text, title page, Table 1 and supplementary
cells), the title page (e-mail, running title, a "first" claim), superscript references
(number, order, placement, a renumbered entry), table cells and signs, figure and
graphical-abstract data, labels, internal identifiers, wording ("paid" alone, causal language,
ranking language, the need weight as a count of undernourished patients, an unhedged "first",
H3 "supported" without "ecological association"), British spelling, the abstract, keyword,
legend and main-text limits, Word's counts, missing alt text, the AI disclosure, caveats, the
end sections, the figures (another figure, a 150 dpi image, greyscale, a graphical abstract that
is not 5:2), a second table, the layout (line numbers removed, justified text, automatic
hyphenation), the release DOI, thousands written with commas, the supplementary methods text, Table 1
removed from its own file or copied into the manuscript, the cover letter and the file set.

With `--sweep`, the last digit of every number token was bumped in turn: 374 of 374 tokens of
the manuscript's Markdown were caught by `check_manuscript_numbers`, and 639 of 639 tokens of
the manuscript's .docx (tables and references included, the release DOI filled in) by
`check_docx_tie`.
