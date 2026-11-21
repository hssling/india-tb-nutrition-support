# Who misses the TB nutrition payment, and where it matters most

Code, extracted data, outputs and a pre-registered analysis plan for a State-level
analysis of the payment chain of India's Ni-kshay Poshan Yojana (NPY), the monthly
direct benefit transfer for nutrition support to notified people with TB. For each State
or UT it counts the people with TB who were not paid at least once, shows at which step
of the chain (bank details, then payment) they are lost, and asks where unpaid people
coincide with higher adult undernutrition, so that closing the gap matters most. It uses
only published, aggregate, official data: the NPY State tables of the TB Annual Report 2022
and the India TB Reports 2023 and 2024, the matching State treatment-outcome and
notification tables, and the NFHS-5 (2019-21) State and UT fact sheets.

The framing is practice-guiding, for the Central TB Division and the State TB Cells. It is
not a league table: results are given as tiers, not ranks, and they describe programme
data, not the performance or effort of any State's staff. All associations reported here
are observational and ecological; none is a causal estimate. A low coverage may reflect
recording, definitions or people not eligible for payment, and not only a failure to pay.

## The question

The analysis plan, [`docs/analysis_plan.md`](docs/analysis_plan.md), asks (its section 2):

- **Q1. The payment chain.** For each unit and data year: what share of the denominator
  has bank details available (A), what share of those was paid at least once (P), and what
  share of the denominator was paid at least once (C)?
- **Q2. Where people are lost, and where to act.** How many people were not paid at least
  once (U), how many of them were lost before bank details (U_acc) and how many after
  (U_pay)? Is each unit's shortfall account-led, payment-led or mixed? Where is the unpaid
  count, and the need-weighted unpaid count, largest, and how certain is each unit's tier?
- **Q3. Trend.** Did coverage fall between 2021 and 2022?
- **Q4. Does payment follow need?** Across units, does 2023 coverage go with the relative
  need weight (H1) or with the private-sector share of notifications (H2)?
- **Q5. Ecological association with outcomes (secondary).** Across units, is coverage
  associated with the shares of DS-TB patients with treatment success, death and loss to
  follow-up (H3)?
- **Q6. Budget.** What would paying everyone not yet paid at least once cost, as an
  illustration at the current rate?

"Paid at least once" counts a person who received any instalment. It does not show that
the full entitlement was paid, so it understates the true payment gap. The data give no
timing of payments.

## Registration

The plan was committed and pushed to this public repository before any estimate was
computed: commit `c1d2f04` (c1d2f04f1867ac75b322b1bbf031ff63a42bb486), first public push
`pushed_at` 2026-11-21T20:28:47Z (22 November 2026, 01:58 India Standard Time), from the
GitHub API ([`docs/registration_event.json`](docs/registration_event.json)). The text
above section 12 of the plan is frozen: `verification/check_plan_order.py` checks that it
is byte-identical at every later commit and in the working tree, and that no analysis
module, extracted value or output was committed before the registration commit.

### Changes after registration (plan section 12)

Section 12 of the plan holds one dated entry, 2026-11-22: an implementation note on two
edge rules the plan does not state (an NA NFHS-5 cell in a merged unit; an NA covariate in
an adjusted H3 entry). Neither applies to the data used, so neither changes a reported
number. `verification/check_deviations.py` (plan section 12) checks that every labelled
line and every reference to a dated entry in the outputs, this README and the extracted
data names an entry that exists.

### What had been seen before registration

Plan section 11 lists it. No estimate of any kind had been computed: no rate, share,
unpaid count, weight, tier, correlation, regression or budget. What had been seen: the
structure of the NPY tables (headers, pages, units, printed India rows); rendered table
pages, so some State values were seen but not recorded or computed; the 2023 NPY State
coverage and the 2022 NPY table, extracted by the author's State TB Score study; the DS-TB
outcome tables, extracted by the author's priority-tool study; the national NPY coverage
of about 62-66% from the literature; Jeyashree et al. 2024, in which patients notified in
the private sector more often went unpaid (so H2 expects a negative sign); the widely
published NFHS-5 State underweight shares; and the female share of notified patients and
the Annexure 1.2 notified totals, which companion studies had already published. H1 and H2
are therefore not blind to the 2023 State coverage.

## Key results

Data year 2023 is the headline year. Karnataka is excluded from the 2023 totals: its 2023
row prints dashes for the denominator, bank details available and bank details validated.
The 2023 figures are for the 32 units with data, never for all of India, and nothing is
carried forward from an earlier year. The 2023 denominator is eligible beneficiaries, not
notified (plan section 10.4), so 2023 coverage is not strictly comparable with 2021-2022.
Counts come first.

### The chain, national, sums over the units with data

| Data year | Denominator | Paid at least once | Not paid at least once (U) | Lost before bank details (U_acc) | Lost after bank details (U_pay) | C, paid at least once of the denominator |
|---|---|---|---|---|---|---|
| 2021 (notified, 33 units) | 2,135,830 | 1,326,306 | 809,524 | 331,440 (32 units) | 477,755 (32 units) | 62.1% (62.0 to 62.2) |
| 2022 (notified, 33 units) | 2,422,121 | 1,601,896 | 820,225 | 358,083 | 462,142 | 66.1% (66.1 to 66.2) |
| 2023 (eligible, 32 units) | 2,462,550 | 1,822,585 | 639,965 | 285,321 | 354,644 | 74.0% (74.0 to 74.1) |

Wilson 95% intervals. In 2021, U_acc and U_pay exclude Himachal Pradesh, whose bank details
exceed its denominator. A (bank details available of the denominator) was 84.4%, 85.2% and
88.4% in 2021, 2022 and 2023, and P (paid at least once of those with bank details) was
73.5%, 77.6% and 83.7%.

- **People not paid at least once in 2023: 639,965** (95% interval from the draws, 638,648
  to 641,274): 285,321 lost before bank details and 354,644 after bank details.
- **Trend.** C rose from 62.1% to 66.1% between 2021 and 2022 (+4.0 percentage points;
  Newcombe 95% interval 3.9 to 4.1). In 9 of 33 units the interval lies wholly below
  zero, which sets the "falling coverage" flag: Andaman and Nicobar Islands, Andhra
  Pradesh, Goa, Gujarat, Himachal Pradesh, Madhya Pradesh, Odisha, Tamil Nadu and
  Uttarakhand. The flag is descriptive and never changes a tier.

### Tiers, 2023

Tiers come from the probability that a unit is among the five with the largest harm,
P(top-5): "act now" at 0.80 or more, "probable priority" at 0.50 or more, "uncertain" at
0.20 or more, otherwise "lower priority". These are tiers, not ranks; units are listed
alphabetically.

- **Act now, by the number of people not paid at least once** (`priority.csv`): Bihar
  (74,684 of 188,579 eligible), Maharashtra (67,918 of 225,255), Punjab (53,028 of
  55,824), Rajasthan (44,159 of 163,204) and Uttar Pradesh (138,153 of 643,208). Every
  other unit with data is "lower priority"; Karnataka is not tiered. Per 100,000 eligible
  beneficiaries the same five units have 39,601 (Bihar), 30,151 (Maharashtra), 94,985
  (Punjab), 27,058 (Rajasthan) and 21,479 (Uttar Pradesh).
- **Need-weighted.** The relative need weight, wt_u, rescales a unit's unpaid count by how
  its adult underweight (BMI below 18.5 kg/m2, NFHS-5 items 86 and 87, women and men aged
  15-49, combined by the sex mix of the unit's notified patients) compares with the
  notification-weighted mean, which is 1. It is a relative weight. It says where an unpaid
  person is more likely to be underweight; it is not a count of undernourished TB patients.
  The need-weighted "act now" tier holds the same five units.
- **How certain.** With thousands of people per unit, P(top-5) is near 0 or 1, so the
  tiers express sampling uncertainty only. The larger uncertainty is in the need weight
  (NFHS-5 prints no interval). When each unit's weight is multiplied by a random factor
  between 0.8 and 1.2 (1,000 replicates), the need-weighted tier is unchanged in 100% of
  replicates for every unit except Gujarat (87%), Madhya Pradesh (47%), Punjab (57%),
  Rajasthan (71%) and Telangana (94%).
- **Funnel.** Against the pooled coverage of 74.0% and each unit's size, Bihar (60.4%
  paid at least once) and Punjab lie below the 99.8% limit ("coverage well below the
  pooled level for its size"). This describes programme data and may reflect recording or
  definitions.
- **Punjab 2023, as printed.** India TB Report 2024 (PDF p. 309, printed p. 278) prints
  2,796 paid at least once out of 55,824 eligible beneficiaries (5.0%; 6.1% of the people
  with bank details available). The value is consistent with the printed India total of
  1,875,510 paid at least once. It is probably a source reporting anomaly, to be verified
  with the programme, and should not be read as programme performance. Punjab's "act now"
  tier and its 94,985 per 100,000 eligible beneficiaries rest on this printed value. The
  leave-one-out output (`leave_one_out.csv`, the without-Punjab rows) shows its influence
  on the associations: without Punjab, H1 is -0.008467741935483872 (main
  0.01906158357771261), H2 -0.3407258064516129 (main -0.3053519061583578), H3 success
  0.17973282935525503 (main 0.1778386247214988), H3 died 0.1131492205385424 (main
  0.09278393179827536) and H3 lost to follow-up -0.20697304365191618 (main
  -0.19636082000595786). Without Punjab the 2023 "act now" set changes by one unit for the
  unpaid count (Telangana enters) and by one unit for the need-weighted count (Madhya
  Pradesh enters).

### Where people are lost, 2023

Classed against the 75th-percentile benchmark of the shrunken A and P across units
(`chain_class.csv`): 13 units are payment-led, 8 account-led, 8 mixed and 3 have no
shortfall; Karnataka is not classified. By construction about a quarter of units lie above
the benchmark, so a class is a relative statement about the better quarter of units, not a
standard. The 50th and 90th percentile benchmarks are in the same file.

### Associations across units (ecological; not causal)

| | Estimate | 95% interval | Label |
|---|---|---|---|
| H1 | Spearman rho between C(2023) and the sex-weighted need share n_u: 0.019 (n = 32) | -0.341 to 0.375 (Fisher z) | not established (8 of 12 grid entries share its sign) |
| H2 | Spearman rho between C(2023) and the private-sector share of 2023 notifications: -0.305 (n = 32) | -0.598 to 0.059 (Fisher z) | not established (6 of 6 grid entries negative; the interval includes 0) |
| H3, treatment success | Slope on logit(C): 0.178, quasi-binomial, 2021 and 2022 cohorts pooled, 33 units, 66 unit-years | 0.024 to 0.348 (cluster bootstrap over units, 10,000 replicates) | supported (interval excludes 0; 8 of 8 entries positive) |
| H3, died | 0.093 | -0.030 to 0.208 | not established |
| H3, lost to follow-up | -0.196 | -0.583 to 0.140 | not established (6 of 8 entries negative) |

- **H1 and H2** compare units. C(2023) is on the eligible basis, the private-sector share
  on the notified basis. Neither is established under the registered rule.
- **H3 is an ecological association.** Units with higher coverage had a higher share of
  treatment success in these two cohorts; the data cannot say why, and strong programmes may
  do well on both coverage and outcomes. **When adjusted for the previous year's success
  share (the 2022 cohort only), the success association attenuates to about 0.03**
  (descriptive Wald interval -0.05 to 0.11; `spec_curve.csv`, entry 7), and to 0.01 when the
  private-sector share is added. H3 is secondary, there is no correction for three
  outcomes, and the Kish effective number of clusters is 11.3, so the bootstrap interval
  may be too narrow. The two cohorts may differ in definition (plan section 10.4).
- Leaving out one unit at a time, H1 ranges from -0.051 (without Madhya Pradesh) to 0.093
  (without Bihar), and H3 success from 0.100 (without Delhi) to 0.230 (without Madhya
  Pradesh) (`leave_one_out.csv`).

### Budget (an illustration, not a forecast)

2023, units with data (Karnataka excluded). The main figure, 639,965 people not paid at
least once x Rs 1,000 a month x 6 months, is **Rs 3,839,790,000** (about Rs 3.84 billion),
within a range of Rs 1.92 billion (Rs 500, 6 months) to Rs 5.12 billion (Rs 1,000, 8
months). If every unit reached the 75th-percentile coverage (81.9%), the number paid at
least once would be 2,026,830 against 1,822,585 now, an increment of 204,245 people
(Rs 1.23 billion at Rs 6,000 each); the 50th and 90th percentile sensitivities give
133,268 and 242,897. The figures count people not paid at least once and not instalments
owed to people already paid at least once, so they understate the gap.

### NA cells

Listed in `outputs/na_cells.csv`; there is no imputation. Himachal Pradesh 2021: bank
details above the denominator, so A, U_acc, U_pay and the class are NA (C and U are kept).
Karnataka 2023: dashes, so every 2023 measure and the tier are NA. Meghalaya 2023: paid
exceeds bank details validated, so the descriptive paid over validated step is NA. Kerala
2021 and 2023: the private-sector count of the merged Lakshadweep row is NA and adds
nothing.

## Reproduction

Python 3.14 on any platform; versions in [`ENVIRONMENT.md`](ENVIRONMENT.md). Every script
is run as `python -I <script>` from the repository root, with LF line endings. Seed
20261123, numpy `default_rng` reset per analysis, 10,000 draws.

```sh
python -I -m pip install numpy==2.3.5 scipy==1.16.3 pdfplumber==0.11.8 pytest==9.0.0
python -I -m pip install "tbprio @ git+https://github.com/hssling/india-tb-priority-tool@v1.0.1"

# The source PDFs (not distributed): copy them into data_raw/ and verify their digests
python -I tools/fetch_sources.py

# Extraction (data/extracted/), optional: the extracts are committed
python -I src/extract/itr_npy.py
python -I src/extract/itr_outcomes.py
python -I src/extract/itr_sector.py
python -I src/extract/nfhs.py

# Analysis (outputs/*.csv; byte-identical on rerun)
python -I src/run_all.py

# The whole verification: PASS / FAIL / SKIP per step
python -I verification/check_all.py
```

`check_all` runs pytest, `check_plan_order`, `check_deviations` (plan section 12),
`check_extraction_totals`, `check_rounding` (plan section 8.9: no count is derived from a
percentage, so the rounding rerun has nothing to move), `check_outputs` (an independent
recompute with the Python standard library only: the chain, the need weight, the
shortfalls and class shares, the budget, H1 to H3 by its own IRLS, and the labels) and
`check_rerun` (the extraction and the analysis rerun and compared byte for byte). The two
manuscript checks, `check_manuscript_numbers` (every number of the manuscript traced to
`outputs/`, the journal's limits and the wording rules) and `check_docx_tie` (the submission
files tied to their sources), are skipped in a clone, because the manuscript is kept private.
Each check was shown to fail on a deliberate break:
[`verification/MUTATIONS.md`](verification/MUTATIONS.md).
Without `data_raw/`, the extraction rerun is skipped and everything else runs on the
committed extracts.

## Data sources

The source documents are Government of India publications. They are not redistributed
here; `data/source_manifest.csv` records each file's origin, size and SHA-256 digest.

- TB Annual Report 2022, India TB Report 2023 and India TB Report 2024 (Central TB
  Division, Ministry of Health and Family Welfare; tbcindia.mohfw.gov.in): the NPY State
  annexures (data years 2021, 2022 and 2023), the Annexure 1.2 notifications by sector,
  the Annexure 3.3 DS-TB treatment outcomes (cohorts 2021 and 2022) and the Annexure 1.6
  notifications by sex (2022). India TB Report 2019 and 2020 print no State-wise NPY table
  and are not used.
- National Family Health Survey (NFHS-5), 2019-21, India and State/UT fact sheet
  compendiums, Phases I and II (Ministry of Health and Family Welfare and the
  International Institute for Population Sciences), obtained from dhsprogram.com
  (pubs/pdf/OF43): items 86 and 87, the Total column.

The extracted values (`data/extracted/`) carry their source file, PDF page and table on
every row; printed totals are checked.

## Limitations

- **"Paid at least once"** overstates coverage; the unpaid count and the budget understate
  the gap. There are no timing data.
- **The 2023 denominator changes** to eligible beneficiaries, and the 2023 private-sector
  share is on the notified basis. The 2021 to 2022 change is the main trend because both
  years share a basis. The reference years are inferred from each edition's national table.
- **NFHS-5 and the need weight.** Items 86 and 87 cover ages 15-49 and one survey round;
  TB notifications include children and older adults. NFHS-5 fact sheets print no interval.
- **H3 is an ecological association** across about 33 units and two cohorts, not a causal
  estimate.
- **Benchmarks are relative.** About a quarter of units lie above the 75th percentile by
  construction.
- **State level only.** Small UTs are reported within the unit they join (Dadra and Nagar
  Haveli and Daman and Diu with Gujarat, Lakshadweep with Kerala, Ladakh with Jammu and
  Kashmir).
- **Recording.** Reporting artefacts are set to NA and listed; a low coverage may reflect
  recording or definitions. Punjab's 2023 row (2,796 paid at least once of 55,824 eligible)
  is probably a source reporting anomaly, to be verified with the programme; its tier rests
  on the printed value.

## Repository layout

- `docs/analysis_plan.md`: the registered plan (dated changes in its section 12);
  `docs/registration_event.json`; `docs/data_inventory.md` (structure only, before
  registration).
- `data/source_manifest.csv`; `data/extracted/`: the extracted panels with provenance, the
  NFHS-5 items, the sex counts and the extraction checks.
- `src/extract/`: the extraction; `src/nutpay/` and `src/run_all.py`: the analysis, which
  imports the author's TB priority tool package `tbprio` pinned to v1.0.1.
- `outputs/`: the results (columns in [`outputs/README.md`](outputs/README.md));
  `verification/`: the checks; `tests/`.
- `exhibits/`: the manuscript's tables, figures and graphical abstract, built from `outputs/`
  only; `tools/build_submission.py`, `tools/audit_references.py`, `tools/word_count_word.ps1` and
  `tools/render_check.ps1`: the submission build and its checks (they need the private
  manuscript folder).

## Citation and licences

Cite as in [`CITATION.cff`](CITATION.cff). Author: Siddalingaiah H S (ORCID
[0000-0002-4771-8285](https://orcid.org/0000-0002-4771-8285)), Department of Community
Medicine, Shridevi Institute of Medical Sciences and Research Hospital, Tumkur 572106,
Karnataka, India (hssling@yahoo.com).

Code (`src/`, `tools/`, `tests/`, `verification/`): MIT ([`LICENSE`](LICENSE)). Derived
data (`data/`, `outputs/`): CC BY 4.0 ([`LICENSE-DATA`](LICENSE-DATA)). The source
publications remain the property of their publishers and should also be cited.
