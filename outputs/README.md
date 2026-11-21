# outputs/: notes for readers and for the verification

Written by `python -I src/run_all.py` (plan section 10.2). Reruns are byte-identical
(`verification/check_rerun.py`); this README is the only file not generated. Floats are
written in full precision. An empty cell is "not applicable"; the text `NA` is a value that
could not be computed. Every file that carries sensitivities has a `spec` column. Units are
the 33 coarsened States and UTs of plan section 3.5; the three data years are 2021 (TB
Annual Report 2022), 2022 (India TB Report 2023) and 2023 (India TB Report 2024).

## Wording

- "Paid" always means **paid at least once** (the person received any instalment). It does
  not show that the full entitlement was paid, so it understates the true payment gap.
- The **need weight** `wt_u` is relative (mean 1, weighted by 2022 notifications). It says
  where an unpaid person is more likely to be underweight (adult BMI below 18.5 kg/m2,
  NFHS-5, ages 15-49). It is not a count of undernourished TB patients.
- Places are **tiers**, never ranks: "act now" (P(top-5) at least 0.80), "probable priority"
  (at least 0.50), "uncertain" (at least 0.20), "lower priority".
- H3 is an **ecological association** across units. No output is a causal estimate.
- In 2023 the denominator is eligible beneficiaries; in 2021 and 2022 it is notified.
  2023 national figures are for the **units with data** (Karnataka is excluded: its 2023
  row prints dashes), never carried forward from an earlier year.
- The budget figures are "an illustration, not a forecast". They count people not paid at
  least once and not instalments owed to people paid at least once, so they understate the
  gap.

## Files and columns

### chain.csv (plan sections 3.6, 5.1, 5.2)

One row per unit-year (99 rows, `level` = `unit`) and one national row per year
(`level` = `national`, `unit` = `units with data`).

- `level`, `unit`, `year`, `denominator_basis` (`notified` or `eligible`).
- `D_denominator`, `B_bank_available`, `Q_paid_at_least_once`, `bank_validated` (2023
  only): the printed counts, summed over merged rows.
- `A` = B / D, `P` = Q / B, `C` = Q / D, each with `_lo` and `_hi` (Jeffreys 95% interval
  for units; Wilson for the national row). `V` = validated / B and `paid_over_validated`
  = Q / validated, 2023 only and descriptive (with `_lo`, `_hi`).
- `U` = D - Q, `U_acc` = D - B (lost before bank details), `U_pay` = B - Q (lost after bank
  details). A ratio above 1 makes that step, its split and its class NA; C and U are kept
  when Q <= D (plan section 3.6).
- `interval` (Jeffreys or Wilson); `n_units`, `n_units_A`, `n_units_P`, `n_units_C`,
  `n_units_U`, `n_units_U_acc`, `n_units_U_pay` (national rows: units used);
  `na_steps` (the NA steps with their reason), `note` (units excluded from a national
  value), `flag` (extraction flags), `source_file`, `pdf_page`, `table_id`.

### need_weight.csv (plan section 4)

One row per unit and weighting (`spec`: `sex_weighted`, `women`, `men`, `simple`).

- `w_u_women`, `m_u_men`: NFHS-5 Total column, items 86 and 87, divided by 100 (merged
  sheets weighted by the 2022 notified counts).
- `f_u_female_share_2022`, `G_u_notified_2022`: the female share and the count notified
  in 2022 (male + female + transgender; transgender patients are weighted with men).
- `n_u` (under the weighting), `n_bar` (the G-weighted mean of n_u), `wt_u_relative_need_weight`
  = n_u / n_bar.
- `nfhs_sheets` (the sheets merged), `flag`, `note`.

### shortfall.csv and chain_class.csv (plan sections 5.3, 5.4)

One row per unit, year and benchmark (`spec`: `p75` main, `p50`, `p90`).

- `D`, `A`, `P`; `A_hat`, `P_hat`: empirical-Bayes posterior means; `A_bench`, `P_bench`:
  the percentile (75th, 50th or 90th) of A_hat and P_hat across the year's units.
- `S_acc` = D max(0, A_bench - A) and `S_pay` = D A max(0, P_bench - P): observed
  shortfalls, in people. `S_acc_mean`, `S_acc_lo`, `S_acc_hi`, `S_pay_mean`, `S_pay_lo`,
  `S_pay_hi`: mean and 95% interval over 10,000 chain draws. `account_share_observed` =
  S_acc / (S_acc + S_pay).
- `p_zero`: share of draws with no shortfall; `p_acc_ge_2_3`, `p_pay_ge_2_3`: share of
  draws in which the account (payment) share of the shortfall is at least 2/3.
- `class`: `no shortfall` (p_zero above 0.5), `account-led` (p_acc_ge_2_3 at least 0.95),
  `payment-led` (p_pay_ge_2_3 at least 0.95), otherwise `mixed`. Empty where A or P is NA.
  A class is relative to the better quarter of units; it is not a standard.
- `status`; `prior_A`, `prior_P` (`empirical Bayes` or the Jeffreys fallback); `alpha1`,
  `beta1`, `alpha2`, `beta2`: the beta priors of A and of P.
- chain_class.csv repeats unit, year, spec, class, p_zero, p_acc_ge_2_3, p_pay_ge_2_3,
  S_acc, S_pay and status.

### priority.csv (plan section 6)

One row per unit, year and harm (`spec`: `unweighted`; `need_weighted_sex_weighted`,
`need_weighted_women`, `need_weighted_men`, `need_weighted_simple`).

- Counts first: `D`, `U_observed` (people not paid at least once), `wt_u` (need-weighted
  specs), `harm_observed` (U, or U x wt_u), `harm_mean`, `harm_lo`, `harm_hi` (posterior
  draws), then `harm_per_100000` and `per_100000_basis` (per 100,000 notified, or per
  100,000 eligible beneficiaries in 2023).
- `unpaid_rate_post_mean`, `C_hat` = 1 - that mean.
- `p_top5`: probability that the unit is among the five with the largest harm; `tier`.
- `falling_coverage_2021_2022` (descriptive; never changes a tier), `prior`,
  `no_unpaid_people_in_year`, `status` (a unit with U NA is not tiered).

### trend.csv (plan section 7)

- `spec`: `main_newcombe_2021_2022` (the change in C from 2021 to 2022 with a Newcombe
  interval; `estimate`, `lo`, `hi`), `sensitivity_saturated_logit` (the empirical-logit
  change with `se`), `sensitivity_wls_no_indicator_2021_2023` (descriptive; does not
  separate the denominator basis; `phi`) and `descriptive_2022_2023` (2023 shown next to
  2022 with its Jeffreys intervals; the denominator basis changes; no flag is set).
- `level` (`unit`, `national`, `summary`), `unit`, `C_2021`, `C_2022`, `C_2023`,
  `falling_coverage` (the 2021-2022 interval lies wholly below 0), `status`, `note`,
  `C_2022_lo`, `C_2022_hi`, `C_2023_lo`, `C_2023_hi`, `n_compared`.
- `summary` rows count the units with falling coverage and the units whose flag differs
  from the main flag in each sensitivity.

### funnel.csv (plan section 8.3)

C(2023) against D. `Q`, `D`, `C`, `c_bar` (pooled coverage), `z`, `phi_f` (winsorised
overdispersion), `widen`, `lower_95`, `upper_95`, `lower_998`, `upper_998` (limits on the z
scale), `position` and `flag` ("coverage well below the pooled level for its size" below
the 99.8% limit). Descriptive; no label.

### headline.csv (plan sections 8.1, 8.4, 8.6)

One row per labelled estimate: `H1` (Spearman rho, C(2023) and n_u), `H2` (Spearman rho,
C(2023) and the private-sector share of 2023 notifications), `H3_success`, `H3_died`,
`H3_ltfu` (quasi-binomial slope on logit(C), 2021 and 2022 cohorts pooled).

- `hypothesis`, `quantity`, `estimate`, `null` (0), `lo`, `hi`, `interval_method`
  (Fisher z with variance 1.06/(n - 3), or cluster bootstrap over units), `n` (units),
  `n_obs` (H3 unit-years).
- `label` (`supported` only if the interval excludes the null and at least 80% of grid
  entries share the main sign; otherwise `not established`), `n_entries`, `n_agree`,
  `n_required`, `main_sign`.
- H3 only: `kish_effective_clusters`, `n_boot`, `n_boot_discarded`, `phi` (Pearson),
  `wald_lo`, `wald_hi` (model-based interval; descriptive, not used for the label).
- `note`.

### spec_curve.csv and spec_grid.csv (plan section 8.2)

- spec_curve.csv: one row per grid entry (H1 12, H2 6, each H3 outcome 8). `hypothesis`,
  `entry`, `main`, `weighting` (H1), `year` (H1, H2), `method` (`spearman`, `kendall` or
  `quasi-binomial IRLS`), `year_set` and `adjustment` (H3: pooled, 2021 or 2022 with none,
  the private-sector share, previous-year success, or both), `estimate`, `sign`,
  `agrees_with_main`, `n`, `n_obs`, `phi`, `wald_lo`, `wald_hi` (H3), `status`.
  Previous-year success exists only for the 2022 cohort.
- spec_grid.csv: one row per hypothesis. `grid`, `n_entries`, `n_agree`, `n_required`,
  `share_agree`, `main_sign`, `interval_excludes_null`, `label`.

### leave_one_out.csv (plan section 8.5)

- `analysis`: `H1`, `H2`, `H3_success`, `H3_died`, `H3_ltfu` (the main estimate with each
  unit left out: `omitted`, `estimate`; `summary` marks the `minimum` and `maximum`) and
  `act-now set 2023, harm U` / `harm U_wt_sex_weighted` (each unit removed in turn and the
  whole chain recomputed: `n_changed` remaining units whose act-now membership changes,
  `changed_units`, `act_now_without`; the closing row names the omitted unit with the most
  changes).

### perturbation.csv (plan section 8.7)

Need weight n_u multiplied by U(0.8, 1.2) per unit, 1,000 replicates. `unit`, `year`
(2023), `spec`, `main_tier`, `main_p_top5`, `n_replicates`, `n_unchanged`,
`share_unchanged` (share of replicates with the same need-weighted tier), `status`.

### budget.csv (plan section 9)

All for 2023, over the units with data. `item`, `spec`, `year`, `rate_per_month` (Rs),
`months`, `count` (people), `count_draw_mean`, `count_lo`, `count_hi` (95% interval of the
sum of the unpaid draws), `cost` (Rs), `cost_lo`, `cost_hi` (a descriptive addition: the
interval of the count times rate times months), `cost_basis`, `C_bench`,
`current_number_paid_at_least_once`, `units_with_data`, `units_excluded`, `note`.

- Rows: U(2023); the main figure (U x Rs 1,000 x 6 months); the range grid (Rs 500 and
  Rs 1,000 a month; 6 and 8 months); and, for the 75th, 50th and 90th percentile benchmark
  C_bench, the national number paid at least once if every unit reached C_bench (x
  Rs 6,000) and its increment over the current number.

### rounding_check.csv (plan section 8.9)

Four rows (tiers, classes, the H1, H2 and H3 labels, the falling-coverage flags), each
"no derived counts" and "unchanged": no count is back-calculated from a printed percentage.
`verification/check_rounding.py` checks this.

### na_cells.csv (plan section 3.6)

Every NA cell and exclusion, with `source`, `unit`, `year`, `measure` and `reason`.
Nothing is imputed.
