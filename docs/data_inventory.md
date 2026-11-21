# Data inventory (structure only, no estimates)

Written 22 Nov 2026, before the analysis plan is registered. This file records
what the sources print: the tables, their pages, the verbatim column headers, the
reference year each table states, the units covered, the printed India total rows,
and whether counts or only percentages are printed. No rate, share, sum, difference
or other value has been computed from any cell. No State value is written here.
Printed India total rows are quoted verbatim as structure only. NFHS-5 indicator
labels are quoted; no NFHS-5 value is written.

The study has no timing component: no Parliament answers with State-wise timing of
payments have been supplied, and none are used.

## Conventions

- **Edition to data year** (the notification year of the patients the edition
  reports, unless a table says otherwise): TB Annual Report 2022
  (`TBAnnaulReport2022.pdf`, cited as TBAR 2022) to 2021; ITR 2023 to 2022;
  ITR 2024 to 2023. This is the mapping used in the author's earlier State
  analyses; where a table prints its own year, the printed year is recorded below.
- **Pages:** "PDF p." is the 1-based page of the file listed in
  `data/source_manifest.csv`; "printed" is the page number printed on that page.
  TBAR 2022 is laid out as two-page spreads, so one PDF page carries two printed
  pages.
- **Headers** are verbatim (PyMuPDF text blocks, checked by eye against rendered
  pages). Cell line breaks are shown as spaces, and `|` separates columns. Print
  errors are kept and marked [sic].
- **"37 rows"** means one row per State/UT as printed (36, with Dadra and Nagar
  Haveli and Daman and Diu merged and Ladakh separate), plus the India row.
- **How the pages were read:** PyMuPDF 1.27.2.3 for text, headers and total rows;
  pages rendered to images and read by eye for titles, footnotes and layout. Cells
  were classified by form only (a bare count, "count (percent)", a dash, NA). Their
  values were not recorded.

## 1. Ni-kshay Poshan Yojana (NPY) State tables

| Edition | Section heading as printed | PDF p. (printed) | Rows | Counts printed? |
|---|---|---|---|---|
| TBAR 2022 | `9 NIKSHAY POSHAN YOJANA` | 143 (261-262) | 37 | Yes, in all data columns; the two derived columns are `count (x.x%)` |
| ITR 2023 | `9. NI-KSHAY POSHAN YOJANA` | 323-324 (293-294) | 37 (36 States/UTs over 2 pages, then India) | Yes, in all data columns; the two derived columns are `count (xx)`, a whole-number percent with no % sign |
| ITR 2024 | `9. Nikshay Poshan Yojana` | 309 (278) | 37 | Yes, counts only; no percent is printed in any column |

All three headings are printed above the table.

**Headers (verbatim):**

- TBAR 2022: `STATES | TOTAL NOTIFICATION | BANK DETAILS AVAILABLE OF TOTAL NOTIFIED | BENEFICIARIES PAID AT LEAST ONE BENEFIT OF TOTAL NOTIFIED`.
  Cells: a bare count, then `count (x.x%)` twice.
- ITR 2023: `State/UTs/UTs [sic] | TOTAL NOTIFICATION | BANK DETAILS AVAILABLE OF TOTAL NOTIFIED (%) | BENEFICIARIES PAID AT LEAST ONE BENEFIT OF TOTAL NOTIFIED (%)`.
  The header is repeated on the second page. Cells: a bare count, then `count (xx)` twice.
  On the rendered page each unit is one row with its three cells. The text layer
  lists the names and cells as separate blocks, which is the "interleaved" layout.
- ITR 2024: `States/UTs | Eligible beneficiaries | Bank details available of total eligible | Bank details validated of total eligible | Beneficiaries paid at least one benefit of total eligible beneficiaries`.
  Cells: bare counts in all four columns.

**Printed India rows (quoted verbatim):**

- TBAR 2022: `INDIA | 2135830 | 1804668 (84.5%) | 1326306 (62.1%)`
- ITR 2023: `India | 2422121 | 2064038 (85) | 1601896 (66)`
- ITR 2024: `INDIA | 2462550 | 2177229 | 2052652 | 1875510`

**Reference (notification) year.** None of the three tables states a year in its
heading, header or footnote. The nearest text is the running head of the page
(`INDIA TB REPORT 2022`, `INDIA TB REPORT 2023`, `India TB Report 2024`), which
names the edition, not the data year. Recorded as "not stated" for each table. Other
printed national tables carry the same "paid" figure as the India row of the State
table, and they do state a period:

- TBAR 2022, PDF p. 45 (printed 65-66), "National Figures": "The following table
  provided the status of DBT Schemes", columns `Scheme | Beneficiaries Paid in No's |
  Amount Paid (in lacs)`, NPY row `13,26,306 | 28,544`. The table has no year column;
  the chapter text on PDF p. 11 says the scheme "continued its exemplary reach in 2021".
- ITR 2023, Table 8.1, PDF p. 115 (printed 88), columns `Beneficiaries Paid in No's
  (2018-2022 | 2022)` and `Amount Paid (in lacs) (2018-2022 | 2022)`, NPY row
  `7096402 | 1601896 | 208976 | 39605`.
- ITR 2024, Table 8.2, PDF p. 88 (printed 58), columns `No. of beneficiaries paid
  (Apr 2018 to Dec 2023 | Jan-Dec 2023)` and `Amount paid (in crores) (Apr 2018 to
  Dec 2023 | Jan-Dec 2023)`, NPY row `1,00,37,873 | 18,75,510 | 2,781 | 440`.

In each edition, the India "paid at least one benefit" figure of the State table is the
same printed number as the single-year figure here (2021 context, 2022, Jan-Dec 2023).
This is a comparison of printed numbers, not a calculation. The registered analysis
plan will state which year each table is taken to represent.

**Structure notes (no values):**

- The bases differ. TBAR 2022 and ITR 2023 print "TOTAL NOTIFICATION" with the
  denominator "TOTAL NOTIFIED"; ITR 2024 prints "Eligible beneficiaries" with the
  denominator "total eligible". In TBAR 2022 and ITR 2023, the India "TOTAL
  NOTIFICATION" figure is the same printed number as the India total notified in
  Annexure 1.2 of the same edition (section 3). In ITR 2024, the India "Eligible
  beneficiaries" figure is a different printed number from the Annexure 1.2 total
  notified (`2552257 (92.4)`).
- ITR 2024 prints a dash in the first three data columns of the Karnataka row
  (eligible, bank details available, bank details validated); its "paid at least one
  benefit" cell has a count. These three dashes are NA cells for extraction. No other
  dash or NA appears in the three NPY tables.
- TBAR 2022 prints two cells with a percent above 100, both in the "bank details
  available" column (the Dadra and Nagar Haveli and Daman and Diu row and the Himachal
  Pradesh row). The counts are printed with them. ITR 2023 and ITR 2024 print no percent
  above 100.
- Lakshadweep, Ladakh and the merged Dadra and Nagar Haveli and Daman and Diu row are
  printed in all three tables.
- TBAR 2022 prints Chandigarh in capitals (`CHANDIGARH`), which matters for name matching.

**ITR 2019 and ITR 2020: no State-wise NPY table.** `India-TB-Report-2019.pdf` and
`ITR2020.pdf` were searched by keyword (poshan, NPY, DBT, bank details, paid), and by
the presence of State names with those words on one page. No page holds a State-wise
NPY table. They print national figures only:

- ITR 2019, PDF p. 84 (period line printed as `Period: 01.04.2019-28.02.2019` [sic]):
  a national table `No. of transactions | Amount (in Rs.)` with an NPY row, source "DBT-04
  Report, PFMS".
- ITR 2020, PDF p. 99: `Total Beneficiary | Total Amount Paid (Rs.)` for "01 Jan 2019
  to 31st Dec 2019 (Source: PFMS)", with a national NPY row.
- ITR 2019, PDF p. 148, lists "% of Eligible beneficiaries paid under Nikshay Poshan
  Yojana" as a State performance indicator, and ITR 2020, PDF p. 152, has a district
  dashboard template with "No. of public sector patients who have received atleast 1
  NPY payment". No State values of either are printed in these editions.

The search used the text layer; a scanned table without a text layer would not have been
found. The NPY series therefore has three State-level time points (2021, 2022, 2023).

## 2. DS-TB treatment-outcome State tables (Annexure 3.3)

The 2021 and 2022 notification cohorts are printed by ITR 2023 and ITR 2024.
TBAR 2022 Annexure 3.3 (PDF p. 102) is titled "Treatment outcome of TB patients
notified in 2020 (Total)", so it is the 2020 cohort and is not used.

| Edition | Title as printed | PDF p. (printed) | Rows | Counts printed? |
|---|---|---|---|---|
| ITR 2023 | `3.3 TREATMENT OUTCOME OF TB PATIENTS NOTIFIED IN 2021 (TOTAL)` | 251-252 (221-222) | 37 | Yes: "TB patients Notified" is a bare count; the others are `n (%)` |
| ITR 2024 | `3.3. Treatment outcome of TB patients notified in 2022 (total)` | 222-223 (191-192) | 37 | Yes, as for ITR 2023 |

**Headers (verbatim):**

- ITR 2023: `State | TB patients Notified | Cure Rate, n (%) | Success Rate, n (%) | Death Rate, n (%) | Lost to follow up, n (%) | Treatment Failure Rate, n (%) | Regimen Change, n (%) | Not evaluated, n (%)`.
- ITR 2024: `States/UTs | TB patients notified | Cure rate, n(%) | Success rate, n(%) | Death rate, n(%) | Lost to follow up, n(%) | Treatment failure rate, n(%) | Regimen change, n(%) | Not evaluated, n(%)`.
  Printed under the table: `Note: Numerator is outcomes in DSTB patients initiated on treatment, and Denominator is total notified DSTB cases by current facility.`
  No such note was found in the text of the ITR 2023 pages.

The cohort size is the column "TB patients Notified" / "TB patients notified". The
success, died and lost-to-follow-up counts are the "n" of the `n (%)` cells in the
"Success Rate", "Death Rate" and "Lost to follow up" columns. The cohort year is stated
in each title (2021 and 2022).

**Printed India rows (quoted verbatim):**

- ITR 2023: `India | 2082444 | 579038 (27.8) | 1779602 (85.5) | 88060 (4.2) | 54127 (2.6) | 11308 (0.5) | 30147 (1.4) | 21155 (1)`
- ITR 2024: `INDIA | 2360036 | 681021 (28.9) | 2066386 (87.6) | 85231 (3.6) | 48604 (2.1) | 11691 (0.5) | 32937 (1.4) | 9221 (0.4)`

No source in the study prints the 2023 cohort.

## 3. Notification by sector (public, private) by State: Annexure 1.2

| Data year | Edition | Title as printed | PDF p. (printed) | Rows |
|---|---|---|---|---|
| 2021 | TBAR 2022 | `1.2 TB Case Notification` | 89 (153-154) | 37 |
| 2022 | ITR 2023 | `1.2 TB CASE NOTIFICATION` | 213-214 (183-184) | 37 |
| 2023 | ITR 2024 | `1.2. TB case notification` | 187-188 (156-157) | 37 |

**Headers (verbatim):**

- TBAR 2022: `State/UT | Target TB patients expected to be notified (Public | Private | Total) | TB patients notified (Achievement against target %) (Public | Private | Total) | TB case notification rate (Public | Private | Total)`.
- ITR 2023: `State/UT | Target TB patients expected to be notified (Public | Private | Total) | TB patients notified, n (% achievement against target) (Public | Private | Total) | TB case notification rate (per 1,00,000) (Public | Private | Total)`.
- ITR 2024: `States/UTs | Target of TB patients expected to be notified (Public | Private | Total) | TB patients notified, n(% of achievement against target) (Public | Private | Total) | TB case notification rate (per lakh population) (Public | Private | Total)`.

Counts are printed for the public, private and total notified columns, as
`count (percent)` cells. TBAR 2022 and ITR 2024 print the footnote that notification "is
based on notification by diagnosing PHI". TBAR 2022 and ITR 2024 print an `NA` cell in the
Lakshadweep row (text order); ITR 2023 prints `0 (NA)` for Lakshadweep, at the top of its
second page.

**Printed India rows (quoted verbatim):**

- TBAR 2022: `INDIA | 1952750 | 1041580 | 2994330 | 1446701 (74%) | 689129 (66%) | 2135830 (71%) | 104 | 49 | 153`
- ITR 2023: `India | 1828260 | 951740 | 2780000 | 1688427 (92.4) | 733694 (77.1) | 2422121 (87.1) | 120 | 52.1 | 172.1`
- ITR 2024: `INDIA | 1825705 | 937127 | 2762832 | 1707878 (93.5) | 844379 (90.1) | 2552257 (92.4) | 119.7 | 59.2 | 178.8`

## 4. Notified TB by sex: Annexure 1.6, ITR 2023

- **Title as printed:** `1.6 GENDER DISAGGREGATED DATA ON TOTAL TB NOTIFICATION, PAEDIATRIC TB NOTIFICATION AND TREATMENT INITIATION`.
- **PDF pp. 221-222 (printed 191-192).** 37 rows.
- **Header (verbatim):** `State | TB Cases Notified (Male | Female | Trans Gender) | Paediatric TB Cases Notified, n (% of total notified) (Male | Female | Trans Gender) | Total TB Cases initiated on treatment, n (% of total notified) (Male | Female | Trans Gender)`.
- **Printed India row (start, quoted):** `India | 1472190 | 948455 | 1021 | ...`
- **Counts** are printed in the three "TB Cases Notified" columns. `NA` and `0 (NA)` cells
  appear in rows around Andaman and Nicobar Islands, Dadra and Nagar Haveli and Daman
  and Diu, Ladakh, Lakshadweep, Mizoram, Nagaland, Puducherry and Tripura. This is read
  from the text order only; extraction will list the exact cells.
- **Reference year:** the table states no year. It is Annexure 1.6 of ITR 2023 (data year
  2022 by the edition mapping above).

## 5. NFHS-5 body-mass-index items 86 and 87

Both compendiums are the NFHS-5 India and State fact sheet compendiums. Each State or UT
has a six-page sheet headed `<name> - Key Indicators`, with columns `Urban | Rural | Total`
under `NFHS-5 (2019-20)` and `Total` under `NFHS-4 (2015-16)`. Items 86 and 87 are on the
same page of each sheet, under the section heading `Nutritional Status of Adults (age
15-49 years)`, so the items cover ages 15-49 as printed. Item labels (verbatim):

- `86. Women whose Body Mass Index (BMI) is below normal (BMI <18.5 kg/m2)21 (%)`
- `87. Men whose Body Mass Index (BMI) is below normal (BMI <18.5 kg/m2) (%)`

Footnote 21 (verbatim): `Excludes pregnant women and women with a birth in the
preceding 2 months.` Item 87 carries no footnote number. The sheet legend prints
`( ) Based on 25-49 unweighted cases`.

UT sheets are named in the same form as the States (`Andaman & Nicobar Islands`,
`Dadra & Nagar Haveli and Daman & Diu`, `Lakshadweep`, `Ladakh`, `Chandigarh`, `NCT Delhi`,
`Puducherry`, `Jammu & Kashmir`). Delhi is `NCT Delhi`, and Ladakh has its own sheet. The
Phase II file also holds the `India - Key Indicators` sheet.

**Phase I** (`NFHS-5_India_and_State_Factsheet_Compendium_Phase-I.pdf`, 142 pages; 22
sheets; PDF page of items 86 and 87): Andaman & Nicobar Islands 13; Andhra Pradesh 19;
Assam 25; Bihar 31; Dadra & Nagar Haveli and Daman & Diu 37; Goa 43; Gujarat 49;
Himachal Pradesh 55; Jammu & Kashmir 61; Karnataka 67; Kerala 73; Lakshadweep 79; Ladakh
85; Maharashtra 91; Meghalaya 97; Manipur 103; Mizoram 109; Nagaland 115; Sikkim 121;
Telangana 127; Tripura 133; West Bengal 139.

**Phase II** (`NFHS-5_India_and_State_Factsheet_Compendium_Phase-II.pdf`, 96 pages; India
and 14 State/UT sheets): India 9; Arunachal Pradesh 15; Chhattisgarh 21; Haryana 27;
Jharkhand 33; Madhya Pradesh 39; Odisha 45; Punjab 51; Rajasthan 57; Tamil Nadu 63; Uttar
Pradesh 69; Uttarakhand 75; Chandigarh 81; NCT Delhi 87; Puducherry 93.

Together the two files give 36 States and UTs. Cells in the four columns of items 86 and
87 that are not plain one-decimal numbers (structure only): Lakshadweep item 87, Rural
cell in parentheses; NCT Delhi item 87, Rural cell in parentheses; Chandigarh items 86
and 87, Rural cell printed as `*` (the legend for `*` was not located in the page text).

## Findings that bear on the plan

1. The NPY tables do not state their reference year; it is inferred from the edition and
   from the same figure in a national table that states a period (section 1).
2. ITR 2024 changes the NPY base from "total notified" to "eligible beneficiaries", and
   its India figure for that base is a different printed number from the Annexure 1.2
   total notified. It prints counts only, and it prints dashes in three Karnataka cells.
3. ITR 2023 prints the NPY percentages as whole numbers; TBAR 2022 prints one decimal.
   Both print the counts with them.
4. The outcome tables for the 2021 and 2022 cohorts are in ITR 2023 and ITR 2024; no
   source gives the 2023 cohort.
5. ITR 2019 and ITR 2020 hold no State-wise NPY table.
