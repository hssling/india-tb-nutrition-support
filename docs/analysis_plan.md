# Pre-registered analysis plan: who misses the TB nutrition payment, and where it matters most

**Date of this plan:** 22 November 2026
**Author:** Siddalingaiah H S, MD, Professor, Department of Community Medicine, Shridevi Institute of Medical Sciences and Research Hospital, Tumkur 572106, Karnataka, India. ORCID 0000-0002-4771-8285. hssling@yahoo.com. Single author.
**Repository:** https://github.com/hssling/india-tb-nutrition-support
**Status:** registered before any estimate was computed. The registration point (the commit SHA and the UTC time of the public push, taken from the GitHub API) is recorded in `docs/registration_event.json`. `verification/check_plan_order.py` checks that the text above §12 is byte-identical at every later commit, and that no file under `src/nutpay/` (the analysis package), `data/extracted/` or `outputs/` was committed before the registration commit. The registration record must name the full 40-character commit SHA and may never be re-pointed.
**Data inventory (structure only):** `docs/data_inventory.md`. This plan is self-contained: its rules are stated in full below, and the "Constraint" and "Fixed" paragraphs are the values that were fixed before any estimate.

**Conventions in this plan.**
- A paragraph marked **Constraint (verbatim)** states the study's global constraints, fixed before any estimate, word for word.
- A paragraph marked **Fixed (verbatim)** states the analysis values fixed before any estimate, word for word.
- A paragraph marked **Decision** records a rule settled from the structure-only inventory, before any estimate. Each is a general rule. None names a State on the basis of its values.
- **Precedence.** Decision overrides Fixed, which overrides Constraint, which overrides the earlier design notes: the more specific text governs where they differ. Every difference is settled in a paragraph marked **Resolution**, and all are listed in §1.4.
- A paragraph marked **Operational detail** fixes how a value is applied. These details were settled when this plan was written, before any estimate.
- "Edition" is the report; "data year" is the year its State tables are taken to describe (§3.2). "Unit" is a State or UT after coarsening (§3.5).
- **Notation.** For unit u and data year t: D the denominator of the chain (§3.3); B the number with bank details available; Q the number paid at least once. In every formula and column name, "paid" means paid at least once; in prose the full phrase is used. A = B/D, P = Q/B, C = Q/D, U = D − Q, U_acc = D − B, U_pay = B − Q. n_u is the NFHS-5 need share and wt_u the relative need weight (§4.3). The number of top places in a priority probability is always written out: P(top-5).
- Every percentile is `numpy.percentile(..., method="linear")`. "95% interval" means the 2.5th and 97.5th percentiles of 10,000 draws unless another method is named.

---

## 1. Background and scope

### 1.1 Purpose

Undernutrition is the largest attributable risk factor for TB in India, and it predicts death on treatment. India's Ni-kshay Poshan Yojana (NPY) pays every notified person with TB a monthly nutrition transfer by direct benefit transfer (DBT): ₹500 a month from April 2018, ₹1,000 a month from November 2024. A payment reaches a patient only after a chain of administrative steps: notification, bank details seeded in Ni-kshay, and payment. The India TB Reports print, by State, the number notified (or eligible), the number with bank details available, and the number paid at least once. In 2023 they also print the number with bank details validated.

The questions are: in each State and UT, how many people with TB were not paid at least once; at which step of the chain are they lost; and where do unpaid people coincide with higher adult undernutrition, so that closing the gap matters most? Secondarily, as an ecological question, do States with higher payment coverage have different treatment outcomes?

The users are the Central TB Division (CTD) and the State TB Cells that run DBT, district programme managers and ASHAs who seed bank accounts, and the Ni-kshay Mitra food-basket programme that decides where in-kind support goes. The framing is constructive and practice-guiding, not a critique.

### 1.2 Scope

- Published, aggregate, official data only (§3). No individual-level data.
- The unit is the State or UT after coarsening (§3.5). There is no district analysis.
- The headline year is data year 2023 (§6).
- Harm is counted in natural units: people with TB not paid at least once (§5.2). Counts are reported first, then per 100,000.
- **No timing component.** No State-wise data on the timing of payments (for example Parliament answers) have been supplied, and none is used. The study cannot say how late payments were.
- Out of scope: causal effects of the NPY; the effect of the 2024 doubling of the rate (no post-doubling State data are published); modelling the undernutrition of TB patients in absolute terms (no State data exist, so a relative weight is used, §4.3).


### 1.3 Wording

**Constraint (verbatim).**
- **Wording:**
  - no causal language;
  - tiers, not ranks;
  - "paid at least once", never "paid" or "fully paid" alone;
  - the need weight is relative and is never called "undernourished TB patients";
  - H3 is "ecological association".

**Operational detail.**
- Results describe programme data, not the performance or effort of any State's staff. No State is described as failing or to blame. Headline text uses tiers, never ranks.
- "Paid at least once" counts a patient who received any instalment. It does not show that the full entitlement was paid, so it understates the true payment gap (§10.4).
- The need weight is relative (§4.3). The need-weighted unpaid count says where an unpaid person is more likely to be undernourished. It is not a count of undernourished TB patients.
- H3 and every comparison of coverage with outcomes is an ecological association across units. No sentence uses "effect of", "improves", "reduces" or "leads to" for it.
- A unit's place is given as "act now", "probable priority", "uncertain" or "lower priority". The text never lists units by rank.

### 1.4 Precedence and the conflicts settled in this plan

| # | Topic | Earlier text | Later text that governs | Settled in |
|---|---|---|---|---|
| 1 | Reference year of a table | Fixed: a table whose year cannot be confirmed from its title or footnote is excluded | Decision: no NPY table prints its year; years are assigned from each edition's national DBT table, which prints the same India figure under a stated period | §3.2 |
| 2 | P in 2023 | Earlier design notes: "P = paid at least once / validated in 2023" | Fixed: P = paid at least once ÷ bank details available in every year; validation is a descriptive sub-step in 2023 only | §5.1 |
| 3 | Trend, main model | Earlier design notes: a 2023 indicator model "or" 2021–2022 only | Fixed: the main model is the 2021→2022 change; the indicator WLS is the sensitivity | §7 |
| 4 | The WLS indicator year | Fixed: tbprio's WLS "with a 2023 indicator" | tbprio's indicator year is fixed at 2021 in the package and cannot be moved; the 2023-indicator model is saturated and is computed from tbprio's own empirical logit | §7.3 |
| 5 | Seed | tbprio's package constant is 20261121 | Constraint: 20261123. tbprio's constant is not used | §10.1 |
| 6 | Outcome cohorts | Earlier design notes: cohorts "in ITR 2023 and ITR 2024" | Decision: the 2021 cohort is ITR 2023 Annexure 3.3, the 2022 cohort ITR 2024 Annexure 3.3; the 2020 cohort of TBAR 2022 is not used | §3.4 |
| 7 | H3 label | Earlier design notes: each association is labelled | Fixed: H3 is labelled, as a secondary ecological association | §8.6 |
| 8 | Previous-year success | Earlier design notes: used "only where it is published" | Settled here: available only for the 2022 cohort (the 2021 cohort is published; the 2020 cohort is not used) | §8.2 |
| 9 | Merging NFHS sheets | Fixed: silent | Settled here: the member rows' 2022 notified counts weight the NFHS items | §4.2 |
| 10 | "National number paid" in the benchmark scenario | Fixed: "the national number paid if every unit reached the benchmark C, × ₹6,000" | Settled here: both that figure and its increment over the current number are reported | §9 |

---

## 2. Questions and hypotheses

- **Q1. The payment chain.** For each unit and data year: what share of the denominator has bank details available (A), what share of those was paid at least once (P), and what share of the denominator was paid at least once (C)? (§5.1)
- **Q2. Where people are lost, and where to act.** How many people are not paid at least once (U), how many of them were lost before bank details (U_acc) and how many after (U_pay)? Is each unit's shortfall account-led, payment-led or mixed? In which units is the unpaid count, and the need-weighted unpaid count, largest, and how certain is each unit's tier? (§5.2–§6)
- **Q3. Trend.** Did coverage fall between 2021 and 2022? (§7)
- **Q4. Does payment follow need?** Across units, does 2023 coverage track the relative need weight (H1) or the private-sector share of notifications (H2)? (§8.1)
- **Q5. Ecological association with outcomes (secondary).** Across units, is coverage associated with the shares of DS-TB patients with treatment success, death and loss to follow-up (H3)? (§8.4)
- **Q6. Budget.** What would paying everyone not yet paid at least once cost, as an illustration at the current rate? (§9)

H1, H2 and H3 are the labelled estimates (§8.6). The chain, the unpaid counts, the classes, the tiers, the budget, the trend and the funnel are descriptive.

---

## 3. Data sources, data years and data rules

### 3.1 Files

All files are local copies, verified by SHA-256 against `data/source_manifest.csv` (seven sources: ITR 2019, ITR 2020, TBAR 2022, ITR 2023, ITR 2024 and the NFHS-5 Phase I and Phase II compendiums). They are kept in `data_raw/`, which is not committed and not redistributed.

**Constraint (verbatim).** `data_raw/` and `manuscript/` are never committed. Source digests go in `data/source_manifest.csv`. Ask the author before any new download.

Only the sources listed in §3.3 supply values. ITR 2019 and ITR 2020 print no State-wise NPY table (a text-layer search, `docs/data_inventory.md`) and are not used. ITR 2021 is a scan and is not used. A new source is added only with the author's approval, and the addition is logged in §12.

### 3.2 Data years

**Fixed (verbatim).** **Data years and sources.**

| Data year | NPY table | Denominator D |
|---|---|---|
| 2021 | TB Annual Report 2022, NPY State annexure | total notified |
| 2022 | ITR 2023, NPY State annexure | total notified |
| 2023 | ITR 2024, NPY State annexure | eligible beneficiaries |

- If a table's reference year cannot be confirmed from its title or footnote, the year is excluded and recorded.

**Decision (reference years).** No NPY State table prints its reference year (inventory §1). Data years 2021, 2022 and 2023 are assigned from each edition's national DBT table, which prints the same India "paid at least once" figure as the India row of the State table, under a stated period:
- TB Annual Report 2022, PDF p. 45 (printed 65–66), "National Figures", the DBT schemes table; the chapter text on PDF p. 11 says the scheme "continued its exemplary reach in 2021";
- ITR 2023, Table 8.1, PDF p. 115 (printed 88), the column headed `2022`;
- ITR 2024, Table 8.2, PDF p. 88 (printed 58), the column headed `Jan-Dec 2023`.

**Resolution.** This assignment is an assumption, stated as such: it rests on the match of one printed national figure with the India row of each State table. The fixed rule is read as satisfied by this match. No year is excluded under it. If extraction finds that the India row of a State table does not equal the printed figure of the national table, the year is excluded and recorded in §12.

### 3.3 Source tables and columns

PDF pages are the 1-based pages of the files in `data/source_manifest.csv`. Column headers are quoted as printed (`docs/data_inventory.md`). "Count part" means the count of a printed `count (%)` cell.

| Data year | NPY table, PDF page | D | B: bank details available | Q: paid at least once | Validated (2023 only) |
|---|---|---|---|---|---|
| 2021 | TBAR 2022 §9 "NIKSHAY POSHAN YOJANA", p. 143 | "TOTAL NOTIFICATION" | "BANK DETAILS AVAILABLE OF TOTAL NOTIFIED", count part | "BENEFICIARIES PAID AT LEAST ONE BENEFIT OF TOTAL NOTIFIED", count part | none |
| 2022 | ITR 2023 §9 "NI-KSHAY POSHAN YOJANA", pp. 323–324 | "TOTAL NOTIFICATION" | "BANK DETAILS AVAILABLE OF TOTAL NOTIFIED (%)", count part | "BENEFICIARIES PAID AT LEAST ONE BENEFIT OF TOTAL NOTIFIED (%)", count part | none |
| 2023 | ITR 2024 §9 "Nikshay Poshan Yojana", p. 309 | "Eligible beneficiaries" | "Bank details available of total eligible" | "Beneficiaries paid at least one benefit of total eligible beneficiaries" | "Bank details validated of total eligible" |

In every year the State rows are used, never the printed India row, except for the printed-total check (§3.6). TBAR 2022 and ITR 2023 print counts with their percentages; ITR 2024 prints counts only.

Other inputs:

| Input | Table, PDF pages |
|---|---|
| Treatment outcomes, 2021 cohort | ITR 2023 Annexure 3.3 "TREATMENT OUTCOME OF TB PATIENTS NOTIFIED IN 2021 (TOTAL)", pp. 251–252 |
| Treatment outcomes, 2022 cohort | ITR 2024 Annexure 3.3 "Treatment outcome of TB patients notified in 2022 (total)", pp. 222–223 |
| Private-sector share, 2021 | TBAR 2022 Annexure 1.2 "TB Case Notification", p. 89, the Public, Private and Total columns of "TB patients notified" |
| Private-sector share, 2022 | ITR 2023 Annexure 1.2 "TB CASE NOTIFICATION", pp. 213–214, the same columns |
| Private-sector share, 2023 | ITR 2024 Annexure 1.2 "TB case notification", pp. 187–188, the same columns |
| Notified by sex, 2022 (f_u) | ITR 2023 Annexure 1.6 "GENDER DISAGGREGATED DATA ON TOTAL TB NOTIFICATION, PAEDIATRIC TB NOTIFICATION AND TREATMENT INITIATION", pp. 221–222, "TB Cases Notified (Male, Female, Trans Gender)" |
| NFHS-5 items 86 and 87 | Phase I compendium (22 State and UT sheets) and Phase II compendium (India and 14 sheets): the page of each sheet listed in `docs/data_inventory.md` |

**Operational detail (the bases).** In TBAR 2022 and ITR 2023 the India "TOTAL NOTIFICATION" of the NPY table is the same printed number as the India total notified of Annexure 1.2. In ITR 2024 the India "Eligible beneficiaries" is a different printed number from the Annexure 1.2 total notified (inventory). The 2023 chain therefore uses the NPY table's own denominator, "eligible", and the private-sector share of 2023 is a share of Annexure 1.2 notifications. The mismatch is accepted and stated (§10.4).

### 3.4 Outcomes and cohorts (H3)

**Fixed (verbatim).** **Outcomes (H3).**
- DS-TB treatment-outcome cohort of patients notified in year t, paired with payment data year t, for t ∈ {2021, 2022}. The 2021 cohort is in ITR 2023 and the 2022 cohort in ITR 2024 (process reference omitted).
- Measures: treatment success, died, lost to follow-up, each ÷ cohort size.
- If the outcome rows are copied from tb_priority_tool/data/extracted, their provenance is kept and they are re-verified against the printed totals.

**Decision (outcome cohorts).** ITR 2023 Annexure 3.3 is the 2021 cohort; ITR 2024 Annexure 3.3 is the 2022 cohort. TBAR 2022 Annexure 3.3 (PDF p. 102) is titled "Treatment outcome of TB patients notified in 2020 (Total)", is the 2020 cohort, and is not used. The private-sector share is from the Annexure 1.2 Public, Private and Total columns of the edition matching the payment year (§3.3). No source prints the 2023 cohort, so H3 uses 2021 and 2022 only.

**Operational detail.**
- Cohort size is the column "TB patients Notified" (or "notified"). The success, died and lost-to-follow-up counts are the counts of the `n (%)` cells of "Success Rate", "Death Rate" and "Lost to follow up". The cohort year is stated in each title.
- The outcome rows are taken either by extraction from the pages above or by copying from `tb_priority_tool/data/extracted`. If copied, the provenance (source file, PDF page, table) is kept and every row is re-verified against the printed totals (§3.6). The choice is recorded in the extraction check and is not a deviation.
- The ITR 2024 table prints "Numerator is outcomes in DSTB patients initiated on treatment, and Denominator is total notified DSTB cases by current facility"; no such note was found for ITR 2023. The two cohorts may therefore differ in definition (§10.4).

### 3.5 Units

**Fixed (verbatim).** **Units.** 33 coarsened units, using the tb_priority_tool / tb_diabetes_gap crosswalk. Printed counts are summed across merged units.

**Operational detail.**
- In every data year, these printed rows are added to the named unit before any ratio is formed:
  - "Dadra and Nagar Haveli and Daman and Diu" (one row in all three NPY tables) → **Gujarat**;
  - Lakshadweep → **Kerala**;
  - Ladakh → **Jammu and Kashmir**.
- This gives 33 units in every data year (36 printed rows less the three merged). The canonical names, in `sorted()` order, are: Andaman and Nicobar Islands, Andhra Pradesh, Arunachal Pradesh, Assam, Bihar, Chandigarh, Chhattisgarh, Delhi, Goa, Gujarat, Haryana, Himachal Pradesh, Jammu and Kashmir, Jharkhand, Karnataka, Kerala, Madhya Pradesh, Maharashtra, Manipur, Meghalaya, Mizoram, Nagaland, Odisha, Puducherry, Punjab, Rajasthan, Sikkim, Tamil Nadu, Telangana, Tripura, Uttar Pradesh, Uttarakhand, West Bengal. They are the `UNITS` of tb_priority_tool's `src/extract/crosswalk.py`.
- Printed names, including capitalisation variants such as `CHANDIGARH`, and the NFHS sheet names (for example "NCT Delhi" → Delhi) are mapped by an explicit crosswalk. A name not in the crosswalk stops extraction with an error that names it.
- Merging sums every printed count over the member rows. A member row that is absent, blank or NA adds nothing; the merged unit carries a flag and is listed in `outputs/na_cells.csv`. A unit whose members are all NA is NA for that measure and year.
- Small UTs are reported only within the unit they join. This is a stated limitation.

### 3.6 Data rules

**Constraint (verbatim).**
- No imputation. NA cells are listed. Every value carries source_file, pdf_page and table_id. Printed totals are checked.
- No estimate before the registration commit is pushed. This covers rates, shares, unpaid counts, weights, tiers, correlations, regressions and budgets. A structure inventory (headers, pages, units, whether counts are printed) is allowed.

**Decision (impossible ratios).** Where a step ratio exceeds 1 (for example bank details above the denominator), that step's ratio and its split (A, U_acc, U_pay, shortfalls, class) are NA for that unit-year, and the cell is listed in `outputs/na_cells.csv`. C is kept if Q ≤ D. There is no imputation.

**Decision (dashes and NA cells).** Dashes and NA cells are NA, for any unit, at any step. Any 2023 national total (unpaid count, budget, scenario) is reported as "units with data", naming the units excluded. There is no carry-forward from an earlier year.

**Decision (editions not used).** ITR 2019 and ITR 2020 have no State-wise NPY table and are not used (§3.1).

**Operational detail.**
- **Printed totals.** For every table, the sum of the printed State rows (before coarsening) is compared with the printed India row, column by column. A difference is recorded with its size. It is not corrected, and the State values are used as printed.
- **Unit-year validity.** B > D makes A, U_acc, U_pay, shortfalls and class NA for that unit-year. Q > B makes P, U_pay, shortfalls and class NA (U_acc is kept if B ≤ D). Q > D makes C and U NA. D = 0 or B = 0 makes the ratio that uses it NA. An NA measure removes the unit-year only from the quantities that use it; a unit with the chain NA still enters the unpaid count if Q ≤ D.
- **Dashes in some cells of a row** do not make the row's other cells NA: each cell is read as printed.
- **Counts are used where printed.** Where a cell prints both a count and a percentage, the count is used. A count is back-calculated from a percentage only where no count is printed, as round-half-up(base × % ÷ 100), with the flag `derived_from_percent` and the rounding interval recorded. The inventory found no NPY, outcome or notification cell that needs this; the rounding check (§8.9) applies to any that does.
- A percentage printed above 100 is listed as an impossible cell at extraction, not before.

---

## 4. The need weight

### 4.1 NFHS-5 items

**Operational detail.**
- w_u (women) and m_u (men): the NFHS-5 **Total** column (not Urban, not Rural, not NFHS-4) of item 86 "Women whose Body Mass Index (BMI) is below normal (BMI <18.5 kg/m2)21 (%)" and item 87 "Men whose Body Mass Index (BMI) is below normal (BMI <18.5 kg/m2) (%)", in the section "Nutritional Status of Adults (age 15-49 years)" of each State and UT sheet. Footnote 21 reads "Excludes pregnant women and women with a birth in the preceding 2 months." The printed percentage is divided by 100.
- A Total cell printed in parentheses (25–49 unweighted cases) is used and flagged `nfhs_small_sample`; a starred cell (percentage not shown) is NA. Cells of this form found in other columns are not used.
- The India sheet is not used.
- The items cover ages 15–49. TB notifications include children and older adults. This is a limitation (§10.4).

### 4.2 Merging NFHS sheets

**Operational detail.** For a coarsened unit with member sheets j (Gujarat with the "Dadra & Nagar Haveli and Daman & Diu" sheet; Kerala with Lakshadweep; Jammu & Kashmir with Ladakh), the weight W_j of member j is its ITR 2023 Annexure 1.6 notified count (male + female + transgender; a member row with an NA cell has weight 0):
- w_u = Σ_j W_j·w_j ÷ Σ_j W_j and m_u = Σ_j W_j·m_j ÷ Σ_j W_j;
- if every member has weight 0, the unweighted mean of the member sheets is used and the flag `nfhs_merge_unweighted` is set.
- Every other unit has one sheet and takes its values unchanged.

### 4.3 The need weight

**Fixed (verbatim).** **Need weight.**
- n_u = f_u·w_u + (1 − f_u)·m_u, where:
  - w_u and m_u are NFHS-5 items 86 and 87: women and men aged 15–49 with BMI < 18.5 kg/m²;
  - f_u is the female share of the unit's notified TB patients in 2022 (ITR 2023 A1.6; transgender patients go with men, stated).
- Relative weight: wt_u = n_u / n̄, where n̄ is the mean of n_u across units, weighted by notifications.
- Need-weighted unpaid count = U·wt_u.
- Sensitivities: women only; men only; the simple average.

**Operational detail.**
- f_u = Female ÷ (Male + Female + Transgender), from ITR 2023 Annexure 1.6, summed over the unit's member rows. Transgender patients enter the denominator and are weighted with men.
- The 2022 f_u and the single NFHS-5 round give one n_u and one wt_u per unit, used for every data year.
- n̄ = Σ_u G_u·n_u ÷ Σ_u G_u over the units with non-NA n_u, where G_u is the unit's 2022 Annexure 1.6 notified count (male + female + transgender). Then wt_u = n_u / n̄, so the G-weighted mean of wt_u is 1.
- Sensitivity weights replace n_u by: w_u (women only); m_u (men only); (w_u + m_u)/2 (simple). Each recomputes n̄ and wt_u with the same rule.
- A unit with f_u, w_u or m_u NA has n_u and wt_u NA. It is excluded from every need-weighted quantity and from H1, and listed in `outputs/na_cells.csv`. There is no replacement value. The rule is the same for every unit; which units it excludes depends only on which cells the sources leave empty.
- The weight is relative. It does not give the number of undernourished TB patients, and no output column or sentence calls it that.

---

## 5. The chain, the unpaid count and the shortfall

### 5.1 The payment chain

**Fixed (verbatim).** **Chain.** In every year:
- A = bank details available ÷ D;
- P = paid at least once ÷ bank details available;
- C = paid at least once ÷ D.

In 2023 only, two descriptive sub-steps are added:
- V = bank details validated ÷ bank details available;
- paid ÷ validated.

**Operational detail.**
- The ratios use the validity rules of §3.6.
- 95% intervals of A, P, C, V and paid ÷ validated: the Jeffreys interval, the 2.5th and 97.5th percentiles of Beta(½ + x, ½ + n − x), by `scipy.stats.beta.ppf`.
- National values for each year (sums over the units with non-NA cells, with the number of units reported) are given for A, P and C with Wilson intervals (centre (x + z²/2)/(n + z²), half-width z·√(x(n − x)/n + z²/4)/(n + z²), z = 1.96).
- The two 2023 sub-steps are descriptive. They have no benchmark, tier, class or label. P is paid at least once ÷ bank details available in 2023 as in every other year, so that A and P mean the same in each year; the denominator of A in 2023 is "eligible", not "notified" (§3.3, §10.4).

### 5.2 Unpaid counts

**Fixed (verbatim).** **Unpaid.**
- U = D − paid.
- U_acc = D − bank details available.
- U_pay = bank details available − paid.

**Operational detail.**
- U = U_acc + U_pay when both are valid.
- Counts come first. Per 100,000 is the mean of the draws of the count ÷ D × 100,000. In 2023, D is the number of eligible beneficiaries, so the 2023 "per 100,000 notified" is per 100,000 eligible beneficiaries, and is labelled so.
- National totals are sums over the units with data, as in §3.6.

### 5.3 Draw sets

A **draw set** is defined by a data year. The draws do not depend on the benchmark percentile.

**Operational detail.**
- **Unpaid-rate draws (tiers).** For each data year, U^(d) comes from `tbprio.harm.estimate(rows, step, year, "p75", True, rng).rate_draws`, on its own fresh `numpy.random.default_rng(20261123)`. `rows` is the year's units in the panel format tbprio requires, as a loss-type step with numerator U and denominator D, over the units with non-NA U. Only `rate_draws` is used (the benchmark of its harm is not); U^(d) = D·rate^(d). tbprio fits the empirical-Bayes prior (`beta_binomial`) and draws the units in alphabetical order. Its edge cases map as follows: if ΣU = 0 (m = 0), tbprio returns zero draws and `no_harm`; every U^(d) is 0 and the year is reported as having no unpaid people. If tbprio raises because the shrinkage cannot be fitted (fewer than 2 units, or a pooled rate of 0 or 1, including a single unit with data), the call is repeated with shrinkage off (the Jeffreys prior `tbprio.shrink.JEFFREYS_BINOMIAL`) and the flag `prior_fallback_jeffreys` is set. The posterior means are `StepYear.post_mean`; Ĉ_u = 1 − post_mean_u.
- **Chain priors.** (α₁, β₁) = `tbprio.shrink.beta_binomial(B, D)` over the units with non-NA A; (α₂, β₂) = `tbprio.shrink.beta_binomial(Q, B)` over the units with non-NA P, with the same Jeffreys fallback and flag. Â_u = (α₁ + B_u)/(α₁ + β₁ + D_u); P̂_u = (α₂ + Q_u)/(α₂ + β₂ + B_u).
- **Chain draws (class rule).** A separate stream, `numpy.random.default_rng([20261123, 1])`, fresh for each data year. Units are processed in alphabetical order; for each unit, where the measure is non-NA: a^(d) = `rng.beta(α₁ + B, β₁ + D − B, size=10000)`, then p^(d) = `rng.beta(α₂ + Q, β₂ + B − Q, size=10000)`. The two streams are independent of each other.
- Each quantity is summarised by `tbprio.harm.summary` (mean, 2.5th and 97.5th percentiles).

### 5.4 Benchmark, shortfalls and class

**Fixed (verbatim).** **Benchmark.** The 75th percentile across units of the tbprio-shrunken A and of P (per year). Sensitivities: the 50th and 90th percentiles. Shortfalls:
- S_acc = D·max(0, A_bench − A);
- S_pay = D·A·max(0, P_bench − P).

**Fixed (verbatim).** **Class.**
- Account-led if S_acc / (S_acc + S_pay) ≥ 2/3 with 95% posterior probability.
- Payment-led if the payment share is ≥ 2/3 with 95% posterior probability.
- Otherwise mixed.
- "No shortfall" if S_acc + S_pay = 0 in more than 50% of draws.

**Operational detail.**
- Draws a^(d) and p^(d) are the chain draws of §5.3. A_bench = the 75th percentile, across the year's units with non-NA A, of Â_u. P_bench = the same for P̂_u. A higher A or P is better, so these are the 75th (main), 50th and 90th percentiles of performance. They are computed once per specification from the posterior means, not redrawn.
- By construction about a quarter of units lie above the benchmark. A shortfall is therefore a relative statement about the better quarter of units.
- Observed shortfalls S_acc and S_pay use the observed A and P (`point`). In draw d: S_acc^(d) = D·max(0, A_bench − a^(d)); S_pay^(d) = D·a^(d)·max(0, P_bench − p^(d)). Both are summarised by mean and 95% interval.
- Share S^(d) = S_acc^(d) ÷ (S_acc^(d) + S_pay^(d)); the payment share is 1 − S^(d). A draw with S_acc + S_pay = 0 has no share: it counts toward neither class share, but stays in the denominator of 10,000.
- Class, in this order, over units with both A and P non-NA:
  1. "no shortfall" if S_acc + S_pay = 0 in more than 50% of the 10,000 draws;
  2. "account-led" if the number of draws with S ≥ 2/3, divided by all 10,000 draws, is at least 0.95;
  3. "payment-led" if the number of draws with 1 − S ≥ 2/3, divided by all 10,000 draws, is at least 0.95;
  4. otherwise "mixed".
- Classes are computed for every data year; headline classes are for 2023. Sensitivities: the 50th and 90th percentile benchmarks.
- Output: `outputs/chain_class.csv`.

---

## 6. Priority tiers

**Fixed (verbatim).** **Tiers.**
- tbprio shrinkage and draws of the unpaid rate, applied to U and to U·wt_u. The weighted draws are the U draws × fixed wt_u.
- P(top-5) by the largest harm. Tiers: act now ≥ 0.80, probable ≥ 0.50, uncertain ≥ 0.20, otherwise lower.
- Absolute counts come first, then counts per 100,000 notified.
- Headline year 2023.

**Operational detail.**
- For each data year and each of the two harms (U; U·wt_u), over the units with a non-NA value: P(top-5) = `tbprio.priority.p_topk({unit: draws}, 5)`, with the units in alphabetical order. Weighted draws are U^(d)·wt_u with the fixed wt_u of §4.3; units with wt_u NA are excluded from the weighted harm and listed.
- Tier = `tbprio.priority.tier(P(top-5), False)`: "act now" P ≥ 0.80; "probable priority" 0.50 ≤ P < 0.80; "uncertain" 0.20 ≤ P < 0.50; "lower priority" P < 0.20. The rising argument is always False: this study has no "watch: rising" tier. The falling-coverage flag (§7) is reported alongside and never changes a tier.
- Draws are the unpaid-rate draws of §5.3. Headline tiers are for 2023. The unweighted and the need-weighted tiers are both reported; the need-weighted tiers use the sex-weighted n_u, with the sensitivity weights (women only, men only, simple) alongside.
- A 2023 unit with U NA is not tiered and is listed. The 2023 act-now set is "units with data" (§3.6).
- Output: `outputs/priority.csv` with a `spec` column.

---

## 7. Trend in coverage

### 7.1 Main change

**Fixed (verbatim).** **Trend.**
- Main: the change in C from 2021 to 2022 per unit and nationally, with a Wilson/Newcombe interval.
- Sensitivity: the tbprio empirical-logit WLS over 2021–2023 with a 2023 indicator for the denominator basis.
- A "falling coverage" flag is set when the 2021→2022 change interval lies wholly below 0.

**Operational detail.**
- For each unit with non-NA C in both 2021 and 2022, d_u = C₂₀₂₂ − C₂₀₂₁, with Newcombe's hybrid-score interval from the two Wilson intervals (l, u) of each C, where c = Q/D is the observed proportion: lower = d − √((c₂ − l₂)² + (u₁ − c₁)²), upper = d + √((u₂ − c₂)² + (c₁ − l₁)²), where 1 is 2021 and 2 is 2022 and z = 1.96.
- Nationally: C over the sums of Q and D across the units with non-NA C in both years (the number of units is reported), with the same interval.
- **Falling coverage**: the upper end of the interval < 0. The flag is descriptive and never changes a tier.
- Both years are on the "total notified" basis. 2023 is shown descriptively next to them and is on the "eligible" basis (§10.4).

### 7.2 Descriptive 2023

C₂₀₂₃ and its change from 2022 are listed with the Jeffreys intervals of each year, with the label "denominator basis changes between 2022 and 2023". No flag is set from the 2022→2023 change.

### 7.3 Sensitivity

**Resolution.** tbprio's indicator year is fixed at 2021 (`tbprio.trend.INDICATOR_YEAR`); it cannot be moved to 2023. A model L_t = β₀ + β₁(t − 2023) + γ·[t = 2023] over three points is saturated (no residual degrees of freedom): β₁ equals L₂₀₂₂ − L₂₀₂₁ and its variance is V₂₀₂₁ + V₂₀₂₂.

**Operational detail.**
- The sensitivity is computed from `tbprio.trend.transform` (the empirical logit L_t = log((Q + ½)/(D − Q + ½)) and its variance V_t = 1/(Q + ½) + 1/(D − Q + ½)). β₁ = L₂₀₂₂ − L₂₀₂₁, SE = √(V₂₀₂₁ + V₂₀₂₂), with φ = 1 because there are no residual degrees of freedom, and a 95% interval β₁ ± 1.96·SE. Its falling flag is "upper end < 0".
- Also reported: `tbprio.trend.fit(years, Q, D, indicator=False)` over 2021–2023 with φ = `tbprio.trend.pooled_phi` over the units' fits and the interval of `tbprio.trend.interval`, which does not separate the denominator basis. It is descriptive only.
- Each sensitivity's number of units whose falling flag differs from the main flag is reported. Output: `outputs/trend.csv`.

---

## 8. Headline estimates, funnel, grids and labels

### 8.1 H1, H2: Spearman correlations

**Fixed (verbatim).** **Headline estimates**

| | Estimate | Null | Interval | Label |
|---|---|---|---|---|
| H1 | Spearman ρ between C(2023) and n_u | 0 | Fisher-z with the Fieller–Hartley–Pearson variance 1.06/(n−3) | yes |
| H2 | Spearman ρ between C(2023) and the private-sector share of 2023 notifications | 0 | as for H1 | yes |
| H3 | Quasi-binomial IRLS of success (and, separately, died and LTFU) ÷ cohort on logit(C), with a year effect, pooled over 2021 and 2022; slope β | 0 | cluster bootstrap over units, 10,000 replicates; Kish effective clusters reported | yes (secondary; ecological) |

**Operational detail (H1, H2).**
- ρ = `tbprio.validate.spearman(x, y)` (the Pearson correlation of average ranks) over the units with both values non-NA; n is reported. Interval = `tbprio.validate.fisher_ci(ρ, n)`: tanh(atanh ρ ± 1.96·√(1.06/(n − 3))), none if n ≤ 3.
- H1: x = C(2023) and y = n_u (the sex-weighted need share of §4.3). A negative ρ means payment coverage is lower where adult underweight is higher, a statement about units only.
- H2: x = C(2023) and y = the private-sector share of 2023 notifications, private ÷ total of the printed Annexure 1.2 columns of ITR 2024 (§3.3), summed over merged units. H2 expects a negative sign (§11); the null is still 0.
- The two quantities of H2 are on different bases (eligible for C, notified for the share). This is stated with H2.
- H1 and H2 are associations across units. They say nothing about individual patients and are not causal.
- Output: `outputs/headline.csv`.

### 8.2 Grids

**Fixed (verbatim).** **Grids** (for the label's ≥80% sign agreement):
- **H1 (12 entries):** weighting {sex-weighted, women, men, simple} × year {2021, 2022, 2023}.
- **H2 (6 entries):** year {2021, 2022, 2023} × {Spearman, Kendall}.
- **H3 (8 entries):** year set {pooled, 2021, 2022} × adjustment {none, private-sector share} plus two models adjusting for previous-year success, only where it is published.

**Operational detail.**
- **H1 grid.** Each entry is ρ between C(t) and the weighting's n_u, for t in the year axis (2021, 2022 and 2023 coverage against the same n_u). The main entry is sex-weighted with 2023. The "women" weighting uses w_u, "men" m_u and "simple" (w_u + m_u)/2.
- **H2 grid.** Each entry is the correlation between C(t) and the private-sector share of the same year's edition (§3.3): 2021 from TBAR 2022, 2022 from ITR 2023, 2023 from ITR 2024. Kendall is Kendall's τ-b, `scipy.stats.kendalltau`. The main entry is Spearman with 2023. The 2022 entries, where both quantities are on the notified basis, are reported as a named sensitivity.
- **H3 grid.** Six entries are the year sets {pooled 2021 + 2022, 2021 alone, 2022 alone} × adjustment {none, private-sector share}. The two previous-year-success entries are year set {2022 alone} adjusted for the 2021 cohort's success share (alone) and adjusted for it together with the private-sector share. Previous-year success exists only for the 2022 cohort, because the 2021 cohort's predecessor is the 2020 cohort, which is not used (§3.4). This gives the eight entries.
- Each entry is a point estimate (ρ, τ or β). The interval is computed for the main entry only. An entry whose estimate is undefined has no sign and does not agree.
- Every entry is written to `outputs/spec_curve.csv`.

### 8.3 Funnel

**Fixed (verbatim).** **Funnel.**
- C(2023) against D. Multiplicative φ from 10%-winsorised z, the same as the diabetes study.
- 95% and 99.8% limits.
- Units below the 99.8% limit are flagged.

**Operational detail.**
- Over the units with non-NA C in 2023, c̄ = ΣQ ÷ ΣD (pooled coverage). z_u = (Q_u − D_u·c̄) ÷ √(D_u·c̄·(1 − c̄)).
- φ_f = `tbprio.district.winsorised_phi(z)`: each z is set to the 10th or 90th percentile where it lies outside them, and φ_f is the mean of the squared values. The limits are multiplied by `tbprio.district.widen(φ_f)`, √φ_f when φ_f > 1 and 1 otherwise.
- Limits on the z scale: ±1.96 (95%) and ±3.09 (99.8%), times the widening factor.
- A unit with z_u below the lower 99.8% limit is flagged "coverage well below the pooled level for its size". A unit above the upper limit is "well above" (descriptive). Positions between the 95% and 99.8% limits are reported. No State is described as failing.
- Output: `outputs/funnel.csv`. The funnel has no label.

### 8.4 H3: ecological association with outcomes

**Operational detail.**
- **Observations.** Unit-years (u, t) for t ∈ {2021, 2022} with non-NA C(t) and a valid cohort (cohort size > 0 and each of the three counts ≤ cohort size). A unit may contribute one or both years.
- **Outcomes.** Treatment success, died and lost to follow-up, each as a count out of the cohort size. Each outcome has its own model, grid and label.
- **Model.** Count_ut ~ quasi-binomial(cohort_ut, π_ut), logit(π_ut) = β₀ + β·logit(C_ut) + γ·[t = 2022] (pooled; no year term for a single year) + the adjustment terms of the grid. logit(C) is the empirical logit log((Q + ½)/(D − Q + ½)), so that C = 0 or 1 does not make it undefined. The private-sector share enters as a proportion (the Annexure 1.2 share of the same year); previous-year success enters as the 2021 cohort's success share.
- **Prior weights.** a_ut = cohort_ut.
- **IRLS** (numpy only). Start with μ = (a·y + ½)/(a + 1) and η = logit(μ). Repeat: working weights W = a·μ(1 − μ); working response z = η + (y − μ)/(μ(1 − μ)); β = (XᵀWX)⁻¹XᵀWz; η = Xβ; μ = expit(η). Stop when max |Δβ| < 10⁻¹⁰, after at most 100 iterations. Non-convergence, or a singular XᵀWX, is reported and the estimate is then undefined.
- **Pearson φ** = Σ a(y − μ)²/(μ(1 − μ)) ÷ (n_obs − n_par), reported with the fit, with the model-based Wald interval β ± 1.96·√(φ·(the diagonal element of (XᵀWX)⁻¹ for the slope on logit(C))) as a descriptive comparison. The Wald interval is not used for the label.
- **H3** = β of the main specification (pooled, no adjustment), per outcome. Null 0.
- **Interval: cluster bootstrap.** A fresh `numpy.random.default_rng(20261123)` for each outcome. The units with at least one observation are sorted alphabetically; with N_H3 of them, `rng.integers(0, N_H3, size=(10000, N_H3))`. Each drawn unit brings all its unit-years (a unit drawn twice enters twice), and the model is refitted. A draw whose fit is undefined is discarded, and the number discarded is reported. The 95% interval is the 2.5th and 97.5th percentiles of β over the retained draws, for the main specification only.
- **Kish effective clusters** (Σ_u K_u)² ÷ Σ_u K_u², with K_u = Σ_t a_ut (the unit's total prior weight), are reported with the interval.
- The model is ecological: β describes units, not patients, and strong programmes may have both high coverage and good outcomes. No causal reading is made.

### 8.5 Leave-one-out

**Fixed (verbatim).** **Leave-one-out:** each unit, for H1–H3 and for the 2023 act-now sets.

**Operational detail.**
- **H1 and H2.** The main ρ is recomputed with each unit left out. **H3.** The main β of each outcome is refitted with each unit (all its unit-years) left out. The minimum and maximum, with the unit whose omission gives each, are reported.
- **Act-now sets.** For each of the two harms (U; U·wt_u) in 2023, each unit is removed in turn and the whole chain is recomputed over the remaining units: the year's priors, n̄ and wt_u (for the weighted harm), a fresh draw set (seeds as in §5.3), P(top-5) and tiers. The number of remaining units whose act-now membership changes is reported, with the omitted unit that causes the most changes.
- Output: `outputs/leave_one_out.csv`.

### 8.6 Label rule

**Constraint (verbatim).** Label rule: "supported" only if the 95% interval excludes the null AND ≥80% of grid entries agree in sign.

**Operational detail.**
- The label applies to H1, H2 and H3 (H3 once for each of its three outcomes, each by its own grid; no correction for multiple outcomes is made and this is stated). The chain, the classes, the tiers, the budget, the trend, the funnel, leave-one-out and all sensitivities carry no label.
- Label = `tbprio.validate.label((lo, hi), 0, signs, main_sign)`, with signs = [`tbprio.validate.sign(v)` for each grid entry] and main_sign = `tbprio.validate.sign(main)`. The count of agreeing entries (`tbprio.validate.n_agree`) is reported.
- "Excludes the null": both ends of the interval strictly above 0, or both strictly below 0.
- "Agree in sign": an entry has the same strict sign as the main estimate. An entry equal to 0, or undefined, does not agree. The main entry counts as one of the entries. By the tbprio rule 5 × agree ≥ 4 × entries, "supported" needs at least 10 of 12 (H1), 5 of 6 (H2) and 7 of 8 (H3). Otherwise the label is "not established".
- A "supported" negative estimate is reported as such: the rule assumes no direction.

### 8.7 Perturbation of the need weight

**Fixed (verbatim).** **Perturbation:** n_u × U(0.8, 1.2) independently per unit, 1,000 replicates. Report, per unit, the share of replicates in which its need-weighted tier is unchanged.

**Operational detail.**
- A fresh `numpy.random.default_rng(20261123)`; the multipliers are drawn in one call, `rng.uniform(0.8, 1.2, size=(1000, M))`, with M the number of units with non-NA n_u, in alphabetical order, column j being the j-th unit.
- In each replicate every unit's n_u is multiplied by its multiplier, n̄ and wt_u are recomputed with the §4.3 rule, and the 2023 need-weighted P(top-5) and tier are recomputed on the existing 2023 draws (the draws do not depend on n_u).
- For each unit: the share of the 1,000 replicates in which its need-weighted tier equals its main need-weighted tier. Output: `outputs/perturbation.csv`.

### 8.8 NFHS limits

The NFHS-5 fact sheets print no confidence interval, so n_u has no sampling interval. The perturbation of §8.7 is the registered response. It is a limitation that the multipliers are independent across units and cannot represent a common error.

### 8.9 Rounding check

**Fixed (verbatim).** **Rounding check:**
- Where a count is back-calculated from a percentage, each such count is moved ±half a unit of the last printed digit.
- The rerun must keep every tier, every class and every H label unchanged. Otherwise a registered §12 note reports what changed.

**Operational detail.**
- For a count derived from a printed percentage x with last printed digit of size δ (δ = 0.1 for `x.x%`, δ = 1 for a whole-number percent), the interval of the count is base × (x − δ/2)/100 to base × (x + δ/2)/100. The analysis is rerun twice: with every derived count at the lower end and with every derived count at the upper end.
- Compared with the main run: every tier (U and U·wt_u, all years), every class, every H1, H2 and H3 label and the falling-coverage flags. A difference is written to `outputs/rounding_check.csv` and reported in §12.
- If no count is back-calculated (the expectation, §3.6), the check is written with "no derived counts" and its result is "unchanged" by construction.

---

## 9. Budget (illustrative)

**Fixed (verbatim).** **Budget (illustrative).**
- **Main:** U(2023) × ₹1,000 × 6 months.
- **Benchmark scenario:** the national number paid if every unit reached the benchmark C, × ₹6,000.
- **Ranges:** ₹500 per month; 8 months.
- Stated: "paid at least once" understates the true payment gap.

**Operational detail.**
- U(2023) is the sum over the units with data (§3.6), with the units excluded named. Its 95% interval is the interval of Σ_u U^(d) over the 2023 draws of §5.3.
- **Main:** U(2023) × ₹1,000 × 6 months.
- **Ranges** (a grid, not a forecast): rate ∈ {₹500, ₹1,000} per month × months ∈ {6, 8}. The ₹500 rate was the rate when the data were collected; ₹1,000 applies from November 2024.
- **Benchmark scenario.** C_bench = the 75th percentile, across the units with non-NA U in 2023, of Ĉ_u (§5.3); sensitivities at the 50th and 90th percentiles. The national number paid at least once in the scenario = Σ_u D_u·max(C_u, C_bench); its cost = that number × ₹6,000. The increment over the current number, Σ_u D_u·max(0, C_bench − C_u), and its cost at ₹6,000 are reported alongside, and both are labelled.
- Each figure is "an illustration, not a forecast". It counts people not paid at least once and does not count instalments owed to people who were paid at least once, so it understates the gap.
- Output: `outputs/budget.csv`.

---

## 10. Computation, outputs, verification and limitations

### 10.1 Computation

**Constraint (verbatim).**
- `python -I`, LF line endings.
- Seed 20261123; numpy `default_rng`, reset per analysis; 10,000 draws.
- Reuse tbprio functions; never copy-modify them.

**Operational detail.**
- Python 3.14 with numpy 2.3.5 and scipy 1.16.3; tbprio 1.0.1, pinned in `pyproject.toml`. At the start of every analysis run, the installed tbprio must report version 1.0.1 or the run stops.
- "Reset per analysis" means a new `numpy.random.default_rng(20261123)` at the start of each draw stream (§5.3; the chain stream is seeded `[20261123, 1]`), each H3 bootstrap (§8.4), each leave-one-out refit of the act-now sets (§8.5) and the perturbation (§8.7). tbprio's own seed constant (20261121) is not used.
- Reruns with the same inputs must give byte-identical outputs. This is checked.
- The analysis package is `src/nutpay/`. New code covers the chain, the draw sets, the shortfall and class rules, the IRLS and the budget. The tbprio functions used are imported and never copied: `shrink.beta_binomial`, `shrink.JEFFREYS_BINOMIAL`, `harm.estimate`, `harm.summary`, `priority.p_topk`, `priority.tier`, `trend.transform`, `trend.fit`, `trend.pooled_phi`, `trend.interval`, `validate.spearman`, `validate.fisher_ci`, `validate.label`, `validate.sign`, `validate.n_agree`, `district.winsorised_phi`, `district.widen`.

### 10.2 Outputs

- Extracted data: `data/extracted/npy_panel.csv` (unit, year, measure, value, source_file, pdf_page, table_id, flag), the outcome cohorts, the Annexure 1.2 notifications, the Annexure 1.6 sex counts and the NFHS-5 items, each with provenance.
- Analysis outputs, each with a `spec` column where it carries sensitivities: `outputs/chain_class.csv`, `outputs/priority.csv`, `outputs/trend.csv`, `outputs/funnel.csv`, `outputs/headline.csv`, `outputs/spec_curve.csv`, `outputs/leave_one_out.csv`, `outputs/perturbation.csv`, `outputs/rounding_check.csv`, `outputs/budget.csv`, `outputs/na_cells.csv`.

### 10.3 Verification

- `verification/check_plan_order.py` checks the registration order: no file under `src/nutpay/`, `data/extracted/` or `outputs/` before the registration commit, over the full history with merges included; the registration record naming a full 40-character SHA and never re-pointed; and the text above §12 unchanged at every later commit on the ancestry path and in the working tree. Before `docs/registration_event.json` exists it fails with "NOT REGISTERED YET".
- Further checks, run after registration: the extracted tables against their printed totals; a byte-for-byte rerun of `outputs/`; an independent standard-library recompute of the chain, the shortfalls, the need weight, the Spearman correlations with their Fisher intervals and the label; and mutation tests showing that each check fails when its target is altered.
- Every deviation from this plan is dated and explained in §12.

### 10.4 Known limitations stated in advance

- **"Paid at least once".** The tables count people who received at least one instalment. A person paid once but not for the later months is counted as paid. Coverage is therefore overstated, and the unpaid count and the budget understate the true gap.
- **No timing data.** The tables give no date of payment and no instalment count. The study cannot say how late payments were.
- **The 2023 denominator changes.** TBAR 2022 and ITR 2023 use "total notified"; ITR 2024 uses "eligible beneficiaries", and its India figure is a different printed number from the Annexure 1.2 total notified. Coverage in 2023 is not strictly comparable with 2021–2022, and the private-sector share of 2023 notifications (Annexure 1.2) is on another basis than C(2023). The 2021→2022 change is the main trend because both years share a basis.
- **NFHS-5 and the need weight.** Items 86 and 87 cover women and men aged 15–49, while TB notifications include children and older adults. NFHS-5 fieldwork was in 2019–21 and gives one round for all years. The weight is relative: it says where an unpaid person is more likely to be undernourished, not how many are. It is not a count of undernourished TB patients. f_u is from 2022 for every year. The NFHS-5 fact sheets print no confidence interval.
- **H3 is an ecological association.** It compares units, with about 33 units and two cohorts, and strong programmes may do well on both coverage and outcomes. It is not a causal estimate. The 2022 cohort table (ITR 2024) prints a note on its definition that the 2021 cohort table does not; the cohorts may differ in definition. With about 33 units, the percentile cluster bootstrap may give too-narrow intervals. The previous-year-success adjustment exists only for the 2022 cohort.
- **The reference years are inferred.** No NPY table prints its year. Each is assigned from a national table of the same edition that prints the same India figure under a stated period (§3.2). The assumption could be wrong for a table.
- **NA exclusions.** A unit whose cells are dashes or NA, or whose ratios are impossible, is excluded from the quantities that need them and listed (§3.6). 2023 national totals are for "units with data", not for all of India, and units are never carried forward from earlier years. The excluded units are named in the outputs, whichever they turn out to be.
- **Previously seen data.** Some of the data, and the direction of some results, had been seen (§11). H1 and H2 are not blind to the 2023 State coverage.
- **Coarsening.** Small UTs are reported only within the unit they join.
- **Benchmarks are relative.** About a quarter of units lie above the 75th percentile benchmark by construction. A shortfall is relative to the better quarter of units, not to a standard.
- **Recording.** A low coverage may reflect recording, definitions or patients not eligible for payment, not only failure to pay. Reporting artefacts (bank details above the denominator, paid above bank details) are set to NA.
- **P(top-5) near 0 or 1.** With thousands of patients per unit, sampling noise is small, so P(top-5) will mostly be close to 0 or 1. The tiers express little uncertainty beyond sampling. The larger uncertainty from n_u is shown only through the perturbation.

---

## 11. What had been seen before registration

**Constraint (verbatim).** No estimate before the registration commit is pushed. This covers rates, shares, unpaid counts, weights, tiers, correlations, regressions and budgets. A structure inventory (headers, pages, units, whether counts are printed) is allowed.

**No estimate of any kind had been computed** in this repository or for this study: no rate, share, unpaid count, weight, tier, correlation, regression or budget, for any unit or year. No State value had been extracted in this repository. The following had been seen:

1. **NPY table structures** (structure scan, 22 November 2026): headers, pages, units, printed India rows, and whether counts are printed (`docs/data_inventory.md`). The printed India rows were quoted verbatim as structure. Nothing was calculated from them.
2. **Rendered table pages.** While the inventory was being built, rendered table pages were viewed to verify headers. State values were therefore seen, but were not recorded or computed.
3. **The 2023 NPY State coverage**, which the author's State TB Score study extracted and analysed as its indicator 5.
4. **The 2022 NPY table**, which that study examined for its denominator but did not use.
5. **The DS-TB outcome tables**, extracted by the author's priority-tool study. State outcome values were therefore seen, not paired with payment data.
6. **National NPY coverage of about 62–66%**, from the literature and news.
7. **Jeyashree et al. 2024** (BMC Public Health, doi 10.1186/s12889-024-17777-7): patients notified in the private sector more often went unpaid. This is why H2 expects a negative sign.
8. **NFHS-5 State underweight shares.** These are widely published and had probably been seen by the author. The inventory located the item labels and wrote no value.
9. **Companion repositories (public, hssling/india-tb-diabetes-gap and hssling/india-tb-priority-tool).**
   - The author's diabetes–TB study extracted the ITR 2023 Annexure 1.6 notified counts by sex for each unit and published them, and published the female share f by unit. That f is this study's f_u under the identical definition (female ÷ male + female + transgender, summed over merged units), and the same counts are the notification weights G_u for n̄ and the NFHS merge weights of §4.2. f_u was therefore computed and published before this plan, in that study.
   - The author's priority-tool study extracted the Annexure 1.2 total notified for TBAR 2022, ITR 2023 and ITR 2024, which are the totals behind the H2 private-sector share. The shares themselves had not been formed.
10. **Nothing else.** No other values from these tables had been computed by the author, and no file of `src/nutpay/`, `data/extracted/` or `outputs/` existed before the registration commit.

---

## 12. Deviations (dated)

No deviation has been recorded.
