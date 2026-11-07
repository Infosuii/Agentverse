"""Regenerate curated CSVs from downloaded official releases, never from seeds."""
import json
import re
import zipfile

import openpyxl
import pandas as pd
from bs4 import BeautifulSoup
from fetch_official import ROOT, URLS, fetch
from pypdf import PdfReader

OUT = ROOT / 'curated'
RAW = ROOT / 'raw'
VINTAGE = 'OBR EFO October 2026'
SOURCES = {
    'D-hmrc-history': ('HMRC Table A.6: Rates of Corporation Tax', 'hmrc_history.pdf', 'HMRC', 'hmrc'),
    'D-hmrc-rates': ('Corporation Tax rates and allowances', 'hmrc_rates.html', 'HMRC', 'hmrc'),
    'D-hmrc-background': ('Corporation Tax statistics 2026: background', 'hmrc_background.html', 'HMRC', 'hmrc'),
    'D-obr-databank': ('Public finances databank October 2026', 'obr_databank.xlsx', 'OBR', 'obr'),
    'D-obr-efo': ('October 2026 EFO detailed forecast tables', 'obr_oct_tables.zip', 'OBR', 'obr'),
    'D-obr-measures': ('Policy measures database March 2026', 'obr_measures.xlsx', 'OBR', 'obr'),
    'D-ons-investment': ('Business investment time series', 'ons_investment.csv', 'ONS', 'ons'),
}


def fy(year):
    return f'{year}-{str(year + 1)[-2:]}'


def write(name, rows, source, notes, *, placeholder=False, vintage=VINTAGE):
    OUT.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(rows).to_csv(OUT / f'{name}.csv', index=False, lineterminator='\n')
    title, raw, publisher, _ = SOURCES[source]
    manifest = json.loads((RAW / 'manifest.json').read_text())
    meta = dict(dataset_id=name, title=name.replace('_', ' ').title(), description=title,
                publisher=publisher, source_url=URLS[raw], licence='Open Government Licence v3.0',
                retrieved_at=manifest[raw]['retrieved_at'], vintage=vintage,
                file=f'curated/{name}.csv', source_id=source, is_placeholder=placeholder,
                notes=notes + '\nRaw SHA256: ' + manifest[raw]['sha256'])
    (OUT / f'{name}.meta.json').write_text(json.dumps(meta, indent=2) + '\n', encoding='utf-8')


def annual(sheet, column):
    return {r[1]: float(r[column]) for r in sheet.values
            if isinstance(r[1], str) and re.fullmatch(r'1?2?\d{3}-\d{2}', r[1])
            and isinstance(r[column], (float, int))}


def build_rates():
    rows = []
    text = '\n'.join(p.extract_text() for p in PdfReader(RAW / 'hmrc_history.pdf').pages)
    for line in text.splitlines():
        fields = line.split()
        if len(fields) == 11 and fields[0].isdigit() and 1982 <= int(fields[0]) <= 2016:
            year = int(fields[0])
            rows.append(dict(financial_year=year, fiscal_year=fy(year), main_rate_pct=float(fields[9]),
                             small_profits_rate_pct=float(fields[5]) if fields[5] != '-' else float(fields[9]),
                             marginal_relief=fields[8], notes='HMRC Table A.6, financial-year row.',
                             source_id='D-hmrc-history'))
    # Table A.6's stale future row for 2017 is deliberately NOT used.
    background = BeautifulSoup((RAW / 'hmrc_background.html').read_text(encoding='utf-8'), 'html.parser').get_text(' ', strip=True)
    if not re.search(r'1 April 2017\s+Single unified rate reduced from 20% to 19%', background):
        raise ValueError('HMRC 2017 rate verification text changed')
    table = BeautifulSoup((RAW / 'hmrc_rates.html').read_text(encoding='utf-8'), 'html.parser').find('table')
    parsed = [[cell.get_text(' ', strip=True) for cell in tr.find_all(['td', 'th'])] for tr in table.find_all('tr')]
    current = pd.DataFrame(parsed[1:], columns=parsed[0])
    for year in range(2017, 2027):
        if year <= 2021:
            rate, small, source = 19, 19, 'D-hmrc-background'
        else:
            col = next(c for c in current.columns if str(c) == str(year))
            values = current[col].astype(str).str.replace(' ', '')
            rate = float(values.iloc[1 if year >= 2023 else 2].replace('%', ''))
            small, source = 19, 'D-hmrc-rates'
        rows.append(dict(financial_year=year, fiscal_year=fy(year), main_rate_pct=rate,
                         small_profits_rate_pct=small, marginal_relief='3/200' if year >= 2023 else '-',
                         notes='Unified rate until 2023; non-ring-fence profits only.', source_id=source))
    assert len(rows) == 45
    write('ct_main_rate_history', rows, 'D-hmrc-history',
          'Table A.6 rows 1982–2016; 2017–2021 from HMRC 2026 Historical Background; 2022–2026 from HMRC current rates table. Starting-rate bands are not represented.', vintage='HMRC August 2017 / April 2026')
    changes = []
    for old, new in zip(rows, rows[1:], strict=False):
        if old['main_rate_pct'] == new['main_rate_pct']:
            continue
        y = new['financial_year']
        changes.append(dict(change_id=f'CT-MAIN-{y}', policy_type='corporation_tax_main_rate',
                            announced_date='', fiscal_event='', effective_date=f'{y}-04-01',
                            old_rate_pct=old['main_rate_pct'], new_rate_pct=new['main_rate_pct'],
                            other_measures='phased capital-allowance reform' if 1983 <= y <= 1986 else
                            ('small profits rate and marginal relief; full expensing' if y == 2023 else ''),
                            reversed=False, notes='Rate and effective financial year verified. Announcement event/date transcription pending.',
                            source_ids='; '.join(dict.fromkeys([old['source_id'], new['source_id']]))))
    write('ct_policy_changes', changes, 'D-hmrc-history',
          'Every implemented seed rate verified against history. Announcement dates/events remain missing; no date inferred from effective year. Reversed proposals are not implemented rate changes.', vintage='HMRC history through 2026')


def build_fiscal():
    w = openpyxl.load_workbook(RAW / 'obr_databank.xlsx', data_only=True)
    receipts = next(s for s in w if s.title.startswith('Receipts ('))
    gdp = annual(next(s for s in w if s.title.startswith('Aggregates (') and 'bn' in s.title), 30)
    rows = []
    for r in receipts.values:
        if isinstance(r[1], str) and re.fullmatch(r'\d{4}-\d{2}', r[1]) and isinstance(r[20], (int, float)):
            # Columns U/V are explicitly onshore (incl bank surcharge/EGL) and offshore.
            total = r[20] + r[21]
            rows.append(dict(fiscal_year=r[1], ct_receipts_gbp_bn=total,
                             ct_receipts_pct_gdp=100 * total / gdp[r[1]],
                             onshore_ct_receipts_gbp_bn=r[20], source_id='D-obr-databank'))
    observed = [r for r in rows if r['fiscal_year'] <= '2025-26']
    write('ct_receipts', observed, 'D-obr-databank',
          'Receipts (£bn) U+V; onshore U includes Bank Surcharge and EGL. GDP denominator: Aggregates (£bn) AE (financial-year GDP). Only outturn fiscal years through 2025-26; forecasts excluded.')
    with zipfile.ZipFile(RAW / 'obr_oct_tables.zip') as z:
        z.extractall(RAW / 'oct_tables')
    econ = openpyxl.load_workbook(next((RAW / 'oct_tables').glob('*economy*')), data_only=True)
    # OBR provides chain-linked-volume BI, not nominal BI. Keep this gap explicit.
    real_bi = annual(econ['1.1'], 5)
    baseline = [dict(vintage=VINTAGE, fiscal_year=r['fiscal_year'], ct_receipts_gbp_bn=r['onshore_ct_receipts_gbp_bn'],
                     nominal_gdp_gbp_bn=gdp[r['fiscal_year']], business_investment_gbp_bn=real_bi[r['fiscal_year']],
                     source_id='D-obr-efo') for r in rows if '2025-26' <= r['fiscal_year'] <= '2030-31']
    write('obr_baseline', baseline, 'D-obr-efo',
          'CT: databank Receipts U (onshore); nominal GDP: Aggregates AE. BI: economy Table 1.1 F, CHAIN-LINKED VOLUMES, NOT NOMINAL: placeholder remains until a nominal forecast is sourced. Current rates from rate history. Do not clear placeholder on these inputs.', placeholder=True)


def build():
    fetch()
    build_rates()
    build_fiscal()
    sources = [dict(source_id=sid, title=title, url=URLS[raw], publisher=pub,
                    publisher_type=kind, published_date='', reliability_tier=1)
               for sid, (title, raw, pub, kind) in SOURCES.items()]
    write('sources', sources, 'D-hmrc-rates', 'Source URLs were fetched by fetch_official.py; raw hashes are in each metadata file.', vintage='2026-11-07')


if __name__ == '__main__':
    build()
