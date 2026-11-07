# Curated data (agent-6)

Run `python -m pip install -r backend/requirements-dev.txt openpyxl lxml`, then
`python data/scripts/build_all.py`. Fetches go to ignored `data/raw/`; builds
are offline once cached. Commit only curated CSVs, sibling metadata and scripts.
Each metadata file records the exact release URL, table and raw SHA-256.
Sources are UK public-sector releases under Open Government Licence v3.0.

## ct_main_rate_history

HMRC Table A.6, *Rates of Corporation Tax*, financial-year rows 1982–2016.
The PDF's stale forward row for 2017 says 20: it is excluded. HMRC's 2026
*Background and guidance* historical timeline verifies the reduction to 19
on 1 April 2017 and the unified-rate period through March 2023. HMRC's
*Rates and allowances* April 2026 edition supplies 2022–2026. Extracted by
`build_all.build_rates`; no rates are taken from the master prompt seed list.
Unified years use the main rate in the small-profits column; this does not
mean a separate small-profits regime existed then. Starting-rate bands and
ring-fence profits are outside this dataset.

## ct_policy_changes

Differences between consecutive verified HMRC history rows, effective 1 April
of the named financial year. All 16 implemented seed changes reconcile to
the rate history. Announcement dates and fiscal events still require source
transcription; missing dates are empty, not guessed from effective dates.
The historical retroactive changes must not be interpreted as having been
announced in the financial year in which they took effect. The reversed 2020
17% proposal is not yet included. Confounding-measure notes need expansion.

## ct_receipts

OBR Public finances databank October 2026, `Receipts (£bn)` columns U and V:
onshore (including Bank Surcharge and Electricity Generator Levy) and offshore.
Total is U+V; percentage GDP divides by financial-year nominal GDP in
`Aggregates (£bn)` column AE. Forecast rows are excluded: the committed
outturn panel is 1999–2000 through 2025–26. These are aggregate receipts,
not an isolated effect of the main rate. Offsets around effective dates are
observations, not causal estimates. Older observations remain M2 work.

## obr_baseline

October 2026 OBR databank provides onshore receipts and nominal GDP;
October detailed economy Table 1.1 column F provides business investment
in **chain-linked volumes, not nominal pounds**. Six official rows cover
2025–26 to 2030–31. This price-basis mismatch is unresolved: metadata and
`BaselineProjection.is_placeholder` deliberately remain true. Quantitative
forecasts must remain subject to DATA-001. Do not present this investment
series as verified nominal investment. Registry notes carry this caveat.
Beyond 2030–31, each component extends at its own final two-year growth
ratio; `extrapolated_from` identifies the last official year. Extended values
are model extrapolations, never official forecasts.

## sources

Fetched HMRC, OBR and ONS source URLs. IDs begin `D-`. The registry also reads
agent-3's `literature_sources.csv` when present. `DATASET_VERSION` is the first
12 hexadecimal characters of SHA-256 over all curated CSV bytes in filename
order. No raw data or API keys are needed at runtime or by tests.

## Pending M2 datasets

`ct_costings`, `macro_annual`, `business_investment_by_asset` and complete
announcement/precedent provenance are not yet curated. Fetch inputs include
OBR Policy measures database (March 2026), and the ONS business investment
time-series CSV. Do not substitute the OBR database's extrapolated policy
effects for original announced costings. Asset-share series will use asset
names as `TimeSeriesPoint.period`, fractions as values and the latest year
in the title; the underlying CSV retains its actual year.
