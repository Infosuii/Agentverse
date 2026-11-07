# Curated data and historical precedents (agent-6)

Install the backend requirements (including `openpyxl`), then run
`python data/scripts/build_all.py`. Use `--offline` to rebuild only from already
fetched releases. Downloads stay in ignored `data/raw/`; small curated CSVs,
metadata, and the URL/hash manifest `data/curated/provenance.json` are committed.
`DATASET_VERSION` hashes the concatenated curated CSV bytes in filename order.
Tests use committed data only and never fetch URLs or call Gemini.

Every dataset is built by `data/scripts/build_all.py`; fetches are in
`fetch_official.py`. `policy_events.py` documents the manual announcement-date
transcriptions below. Numeric rates, receipts, macro series, asset values and
costings are extracted from downloaded official releases, not the seed prompt.
UK government/ONS/OBR data use Open Government Licence v3.0; parliamentary
speech material uses the Open Parliament Licence. See each linked publisher's
terms; facts and dates are transcribed without copying speeches.

## ct_main_rate_history

HMRC Table A.6, financial-year rows 1982–2016; the stale 2017 forward row showing
20% is excluded. HMRC's 2026 historical background verifies the 19% reduction on
1 April 2017 and the unified-rate period through March 2023. HMRC's April 2026
rates table supplies 2022–2026. Unified years use the main rate in the small-
profits column; this does not imply a separate small-profits regime. Starting-
rate bands and ring-fence rates are excluded. Provenance: D-hmrc-history,
D-hmrc-background, D-hmrc-rates. No manual rate transcription.

## ct_policy_changes

All 16 implemented changes are differences between consecutive verified HMRC
rows. A separately labelled CT-MAIN-2020-REVERSED records the announced 17%
proposal, not an implemented rate. Its observed outcomes are deliberately empty.
Dates are effective 1 April financial years; announcement dates can come later
for retrospective measures. All announcement dates below are documented manual
transcriptions of the linked official speech/event dates, regenerated from
`policy_events.EVENTS`:

| Effective financial year(s) | Announced | Fiscal event/source location |
|---|---|---|
| 1983, 1984, 1985, 1986 | 1984-03-13 | D-budget1984, corporation-tax/capital-allowances passage: phased reform, 1983 retrospective |
| 1990, 1991 | 1991-03-19 | D-budget1991, corporation-tax passage: 1990 retrospective |
| 1997 | 1997-07-02 | D-budget1997, corporation-tax and dividend-credit passage, retrospective |
| 1999 | 1998-03-17 | D-budget1998, corporation-tax and ACT/instalments passage |
| 2008 | 2007-03-21 | D-budget2007, business-tax/capital-allowances passage |
| 2011 | 2011-03-23 | D-budget2011, measures announced today |
| 2012, 2013 | 2012-03-21 | D-budget2012, Table 2.1 row 7 and executive summary |
| 2014 | 2012-12-05 | D-autumn2012, business measures, further cut to 21% |
| 2015 | 2013-03-20 | D-budget2013, corporation-tax unification passage |
| 2017 | 2015-07-08 | D-budget2015, corporate-tax package |
| 2020 (reversed proposal) | 2016-03-16 | D-reversal2020, background on Budget 2016 announcement; retained at 19% in Budget 2020 |
| 2023 | 2021-03-03 | D-budget2021, corporate-tax passage and Table 2.1 row 22 |

The five Hansard speech downloads return HTTP 403 in the direct downloader.
Their dates and passages were checked through web search's copies of the same
primary URLs. Fetch failure is retained in provenance.json; manual source rows
remain reproducible from policy_events.py. A browser-downloaded archival copy
can be placed under the named raw filename. No missing value is invented.
Full-expensing comparability is independently sourced to D-full_expensing.

## ct_receipts

ONS N445 is central-government CT **gross of tax credits**, NSA quarterly £m.
Sum Q2/Q3/Q4/Q1 and divide by 1000. The outturn panel runs 1982–83 through
2025–26. Percentage GDP divides by fiscal nominal GDP from OBR databank
`Aggregates (£bn)` AE. Supplementary onshore figures come from OBR `Receipts
(£bn)` U, available from 1999–2000, and include Bank Surcharge/EGL. They have a
different perimeter from N445: do not subtract them to infer offshore receipts.
Missing early onshore observations are blank. Provenance: D-ons-ct-receipts,
D-obr-databank. Baseline revenue uses OBR onshore, never gross N445.

## obr_baseline

OBR EFO October 2026: six rows 2025–26 through 2030–31. Onshore receipts:
databank `Receipts (£bn)` U; nominal GDP: `Aggregates (£bn)` AE. Current main
and small-profits rates come from the latest verified history row.

OBR detailed economy Table 1.1 F (NPEL) is **real** investment. The nominal
investment projection is explicitly derived, not an official OBR nominal BI
series. As agreed with agents 11 and 3 in coordination #8, anchor at the latest
complete ONS NPEK current-price fiscal sum (£m/1000), then use:

`BI_nominal_t = NPEK_base * (NPEL_t / NPEL_base) * (GDPdeflator_t / GDPdeflator_base)`

The deflator is OBR economy Table 1.7 V. The GDP deflator proxies the investment
deflator: this is a documented modelling assumption, not a verified identity.
The anchor year is recorded in the metadata notes. The sourced transformation
has no unverified placeholder inputs; source IDs include D-ons-investment,
D-obr-efo, D-obr-databank. After the official horizon, each component grows at
its own final two-year ratio; `extrapolated_from` records the last official year.
Those extensions are model extrapolations, not official forecasts.

## macro_annual

Fiscal years 1982–83 through 2025–26. ABMI real GDP, CAER seasonally adjusted
PNFC gross operating surplus, CPI annual inflation D7G7, unemployment MGSX,
ONS NPEK current-price business investment, OBR nominal GDP and BoE IUMABEDR.
Quarterly flows sum Q2–Q1 and £m convert to £bn. Inflation/unemployment average
four quarterly observations; Bank Rate averages the 12 monthly-average rates
April–March. Real GDP growth compares consecutive fiscal sums. Missing early
CPI and investment observations remain blank, never interpolated. Only outturn
periods enter the panel; latest forecast data do not enter precedent macro
comparisons. The context for a change is its previous fiscal year.

## business_investment_by_asset

ONS CP SA quarterly series, calendar-year sums 1997–2025, £m/1000:
plant_machinery = EDRB transport + EDWH ICT/other machinery;
structures = EDYP other buildings/structures, excluding dwellings;
intangibles = EDYS intellectual property products. Shares divide by the sum of
the three groups; 2025 sums reconcile to NPEK. Source: D-ons-investment.
`load_series("business_investment_by_asset")` returns the latest year's shares
as fractions with the year in the title and asset names in `point.period`.

## ct_costings

Original HMT tables, sign positive = Exchequer revenue; £m divide by 1000:
Budget 2021 Table 2.1 row 22; Summer Budget 2015 Table 2.1 row 9; Budget 2012
Table 2.1 row 7, printed page 50/PDF page 51. The 2012 costing covers a joint
2012–14 package and is referenced by both the 2012 and 2013 changes: **do not
sum these duplicate package references**. The 2015 costing includes the planned
2020 cut later reversed. Tables do not establish behavioural inclusion, so that
field is null. Coverage: implemented 2012, 2013, 2017, 2023 changes. Earlier
isolated costings are absent rather than guessed or zero-filled. The OBR policy-
measures workbook is downloaded for further investigation; its extrapolated
policy effects are deliberately not relabelled as original announced costings.

Observed receipts/GDP, real GDP growth and nominal investment are attached for
t−1, t, t+1 and t+2 where observed. Future or unavailable outcomes remain absent.
These are observations, not estimates of the policy's causal effect.

## sources and registry

All eight frozen annual evaluation series are supported. `list_sources()` also
loads agent-3's literature_sources.csv if present. Every committed CSV has a
DatasetMeta sibling; source references resolve. There are no placeholders in
these curated datasets. Incomplete historical coverage and explicit modelling
assumptions are documented above; absence is never represented by a fabricated
zero. Baseline sources and costings sources remain separate evidence classes.

Precedent scoring uses direction .30, magnitude .25, rate level .15, macro .20,
recency .10; macro scales use the available annual history. Missing macro data
renormalises remaining weights and adds a comparability note. Full-expensing,
phased-package, reversed-proposal and pre-change recession caveats are surfaced.

## Source URLs

- D-hmrc-history: [HMRC Table A.6: Rates of Corporation Tax](https://www.gov.uk/government/uploads/system/uploads/attachment_data/file/257049/table-a6.pdf)
- D-hmrc-rates: [Corporation Tax rates and allowances](https://www.gov.uk/government/publications/rates-and-allowances-corporation-tax/rates-and-allowances-corporation-tax)
- D-hmrc-background: [Corporation Tax statistics 2026: background](https://www.gov.uk/government/statistics/corporation-tax-statistics-2026/background-and-guidance-to-interpreting-corporation-tax-statistics-2026)
- D-obr-databank: [Public finances databank October 2026](https://obr.uk/download/public-finances-databank-october-2026-efo/)
- D-obr-efo: [October 2026 EFO detailed forecast tables](https://obr.uk/download/october-2026-economic-and-fiscal-outlook-detailed-forecast-tables-zip-file/)
- D-obr-measures: [Policy measures database March 2026](https://obr.uk/download/policy-measures-database/)
- D-ons-investment: [Business investment time series](https://www.ons.gov.uk/file?uri=/economy/grossdomesticproductgdp/datasets/businessinvestment/current/cxnv.csv)
- D-ons-real-gdp: [Real GDP ABMI, quarterly national accounts](https://www.ons.gov.uk/generator?format=csv&uri=/economy/grossdomesticproductgdp/timeseries/abmi/qna)
- D-ons-pnfc: [PNFC gross operating surplus CAER](https://www.ons.gov.uk/generator?format=csv&uri=/economy/grossdomesticproductgdp/timeseries/caer/ukea)
- D-ons-cpi: [CPI annual inflation D7G7](https://www.ons.gov.uk/generator?format=csv&uri=/economy/inflationandpriceindices/timeseries/d7g7/mm23)
- D-ons-ct-receipts: [Central government Corporation Tax gross of tax credits N445](https://www.ons.gov.uk/generator?format=csv&uri=/economy/governmentpublicsectorandtaxes/publicsectorfinance/timeseries/n445/pusf)
- D-ons-unemployment: [Unemployment rate MGSX](https://www.ons.gov.uk/generator?format=csv&uri=/employmentandlabourmarket/peoplenotinwork/unemployment/timeseries/mgsx/lms)
- D-boe-bank-rate: [Monthly average official Bank Rate IUMABEDR](https://www.bankofengland.co.uk/boeapps/database/fromshowcolumns.asp?CSVF=TT&DAT=ALL&FNY=Y&Filter=N&FromSeries=1&SeriesCodes=IUMABEDR%2CIUMTLMV%2CIUMBV34&ToSeries=50&Travel=NIxAZxSUx&UsingCodes=Y&html.x=66&html.y=26)
- D-budget1984: [Budget speech 13 March 1984: corporation tax and capital allowances](https://hansard.parliament.uk/Commons/1984-03-13/debates/6cf4b7c6-4a55-429a-a8a9-e7617b155785/CommonsChamber)
- D-budget1991: [Budget speech 19 March 1991: corporation tax](https://hansard.parliament.uk/commons/1991-03-19/debates/37cfce8d-a615-420f-a132-917ccf219ef4/CommonsChamber)
- D-budget1997: [Budget speech 2 July 1997: corporation tax](https://hansard.parliament.uk/Commons/1997-07-02/debates/25efc1ce-0352-4c6a-b353-def04ca4c618/CommonsChamber)
- D-budget1998: [Budget speech 17 March 1998: corporation tax and ACT](https://hansard.parliament.uk/commons/1998-03-17/debates/b52b11d8-562f-4016-b28b-110f2f11b404/CommonsChamber)
- D-budget2007: [Budget speech 21 March 2007: business tax reform](https://hansard.parliament.uk/Commons/2007-03-21/debates/d71fcb9d-858f-4a83-a532-3c88bb72b8be/CommonsChamber)
- D-budget2011: [2011 Budget: Britain open for business, 23 March 2011](https://www.gov.uk/government/news/2011-budget-britain-open-for-business)
- D-budget2012: [Budget 2012, 21 March: Table 2.1 corporation tax package](https://assets.publishing.service.gov.uk/media/5a7c923ced915d6969f45d0b/1853.pdf)
- D-autumn2012: [Autumn Statement 2012 overview, 5 December](https://www.gov.uk/government/news/autumn-statement-2012-an-overview)
- D-budget2013: [Budget speech 20 March 2013: corporation tax unification](https://www.gov.uk/government/speeches/budget-2013-chancellors-statement)
- D-budget2015: [Summer Budget 8 July 2015: corporation tax package](https://www.gov.uk/government/publications/summer-budget-2015/summer-budget-2015)
- D-budget2021: [Budget 3 March 2021: Table 2.1 row 22](https://www.gov.uk/government/publications/budget-2021-documents/budget-2021-html)
- D-reversal2020: [HMRC March 2020: reversal of 2016-announced 17 percent rate](https://www.gov.uk/government/publications/changes-to-corporation-tax-rates-from-1-april-2020/corporation-tax-main-rate-at-19-in-2020-and-charge-and-main-rate-for-2021)
- D-full_expensing: [HMRC 15 March 2023: introduction of full expensing](https://www.gov.uk/government/publications/capital-allowances-full-expensing/capital-allowances-full-expensing-for-companies-investing-in-plant-and-machinery-from-1-april-2023-until-31-march-2026)
