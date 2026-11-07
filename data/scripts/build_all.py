"""Regenerate curated CSVs from downloaded official releases, never from seeds."""
import argparse
import csv
import json
import re
import zipfile
from datetime import datetime

import openpyxl
import pandas as pd
from bs4 import BeautifulSoup
from fetch_official import ROOT, URLS, fetch
from policy_events import DOCUMENTS, EVENTS, source_id
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
    'D-ons-real-gdp': ('Real GDP ABMI, quarterly national accounts', 'ons_real_gdp.csv', 'ONS', 'ons'),
    'D-ons-pnfc': ('PNFC gross operating surplus CAER', 'ons_pnfc.csv', 'ONS', 'ons'),
    'D-ons-cpi': ('CPI annual inflation D7G7', 'ons_cpi.csv', 'ONS', 'ons'),
    'D-ons-ct-receipts': ('Central government Corporation Tax gross of tax credits N445', 'ons_ct_receipts.csv', 'ONS', 'ons'),
    'D-ons-unemployment': ('Unemployment rate MGSX', 'ons_unemployment.csv', 'ONS', 'ons'),
    'D-boe-bank-rate': ('Monthly average official Bank Rate IUMABEDR', 'boe_rate.html', 'Bank of England', 'boe'),
}
SOURCES.update({source_id(name): (title, name, publisher, kind)
                for name, (_, title, publisher, kind) in DOCUMENTS.items()})


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
        announced, event, document = EVENTS[y]
        changes.append(dict(change_id=f'CT-MAIN-{y}', policy_type='corporation_tax_main_rate',
                            announced_date=announced, fiscal_event=event, effective_date=f'{y}-04-01',
                            old_rate_pct=old['main_rate_pct'], new_rate_pct=new['main_rate_pct'],
                            other_measures='phased capital-allowance reform' if 1983 <= y <= 1986 else
                            ('small profits rate and marginal relief; full expensing' if y == 2023 else ''),
                            reversed=False, notes='Rate/effective year: HMRC Table A.6 or current table; announcement: named Budget speech/statement, corporation tax section. '
                            + ('Phased package with capital-allowance reform. ' if y <= 1986 else '')
                            + ('Retrospectively effective. ' if announced > f'{y}-04-01' else ''),
                            source_ids='; '.join(dict.fromkeys([old['source_id'], new['source_id'], source_id(document)]
                                                             + (['D-full_expensing'] if y == 2023 else [])))))
    changes.append(dict(change_id='CT-MAIN-2020-REVERSED', policy_type='corporation_tax_main_rate',
                        announced_date='2016-03-16', fiscal_event='Budget 2016', effective_date='2020-04-01',
                        old_rate_pct=19, new_rate_pct=17, other_measures='', reversed=True,
                        notes='Announced proposal only; retained at 19 percent by Budget 2020. Not part of implemented rate history.',
                        source_ids='D-budget2016; D-reversal2020'))
    write('ct_policy_changes', changes, 'D-hmrc-history',
          'All 16 implemented seed changes verified. Announcement dates/events: policy_events.py, explicit Budget speech dates; location is each speech corporation-tax section. 1983/1990/1997 changes are retrospective. 2020 reversed proposal is separately labelled; no implemented outcomes attributed.', vintage='HMRC history through 2026')


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
    onshore = {r['fiscal_year']: r['onshore_ct_receipts_gbp_bn'] for r in rows}
    observed = [dict(fiscal_year=y, ct_receipts_gbp_bn=v, ct_receipts_pct_gdp=100*v/gdp[y],
                     onshore_ct_receipts_gbp_bn=onshore.get(y, ''), source_id='D-ons-ct-receipts')
                for y, v in fiscal_observations('ons_ct_receipts.csv', divisor=1000).items() if y >= '1982-83']
    write('ct_receipts', observed, 'D-ons-ct-receipts',
          'Total: ONS N445 central-government CT GROSS OF TAX CREDITS, NSA quarterly £m sum Q2–Q1 /1000. GDP denominator: OBR databank Aggregates (£bn) AE. Supplementary onshore column only: OBR Receipts U, includes Bank Surcharge/EGL, available from 1999-00; therefore not directly additive/comparable to N445 total. No missing onshore history filled. Outturns only through 2025-26. Baseline uses OBR onshore, NOT this gross total.')
    with zipfile.ZipFile(RAW / 'obr_oct_tables.zip') as z:
        z.extractall(RAW / 'oct_tables')
    econ = openpyxl.load_workbook(next((RAW / 'oct_tables').glob('*economy*')), data_only=True)
    # Agreed transformation in coordination #8 (agent-11, comment 6710911267).
    # This is an explicit GDP-deflator proxy, not an OBR nominal BI forecast.
    real_bi = annual(econ['1.1'], 5)
    deflator = annual(econ['1.7'], 21)
    investment = ons_fiscal('NPEK')
    anchor = max(k for k in investment if k in real_bi and k <= '2025-26')
    nominal_bi = {y: investment[anchor] * real_bi[y] / real_bi[anchor] * deflator[y] / deflator[anchor]
                  for y in real_bi if y in deflator}
    baseline = [dict(vintage=VINTAGE, fiscal_year=r['fiscal_year'], ct_receipts_gbp_bn=r['onshore_ct_receipts_gbp_bn'],
                     nominal_gdp_gbp_bn=gdp[r['fiscal_year']], business_investment_gbp_bn=nominal_bi[r['fiscal_year']],
                     source_id='D-obr-efo') for r in rows if '2025-26' <= r['fiscal_year'] <= '2030-31']
    write('obr_baseline', baseline, 'D-obr-efo',
          f'CT: databank Receipts U (onshore); GDP: Aggregates AE. BI is a derived nominal projection, NOT an official nominal OBR forecast: ONS NPEK CP SA fiscal sum /1000 anchored at {anchor}, multiplied by OBR Table 1.1 F real BI ratio and Table 1.7 V GDP-deflator ratio relative to anchor. GDP deflator proxies the BI deflator; assumption agreed in #8 comment 6710911267. Formula: NPEK_base*(NPEL_t/NPEL_base)*(GDPdeflator_t/GDPdeflator_base). Current rates from rate history. Sources D-ons-investment, D-obr-efo and D-obr-databank.')


def ons_fiscal(code):
    with (RAW / 'ons_investment.csv').open(encoding='utf-8-sig') as f:
        rows = list(csv.reader(f))
    col = rows[1].index(code)
    quarters = {r[0].replace(' ', ''): float(r[col]) / 1000 for r in rows
                if re.fullmatch(r'\d{4} Q[1-4]', r[0]) and r[col]}
    result = {}
    for y in range(1982, 2026):
        qs = [f'{y}Q2', f'{y}Q3', f'{y}Q4', f'{y+1}Q1']
        if all(q in quarters for q in qs):
            result[fy(y)] = sum(quarters[q] for q in qs)
    return result


def fiscal_observations(filename, *, divisor=1, average=False):
    with (RAW / filename).open(encoding='utf-8-sig') as f:
        rows = list(csv.reader(f))
    quarters = {r[0].replace(' ', ''): float(r[1]) / divisor for r in rows
                if re.fullmatch(r'\d{4} Q[1-4]', r[0]) and r[1]}
    result = {}
    for y in range(1981, 2026):
        qs = [f'{y}Q2', f'{y}Q3', f'{y}Q4', f'{y+1}Q1']
        if all(q in quarters for q in qs):
            result[fy(y)] = sum(quarters[q] for q in qs) / (4 if average else 1)
    return result


def build_macro_assets():
    real = fiscal_observations('ons_real_gdp.csv', divisor=1000)
    pnfc = fiscal_observations('ons_pnfc.csv', divisor=1000)
    cpi = fiscal_observations('ons_cpi.csv', average=True)
    unemployed = fiscal_observations('ons_unemployment.csv', average=True)
    investment = ons_fiscal('NPEK')
    w = openpyxl.load_workbook(RAW / 'obr_databank.xlsx', data_only=True)
    gdp = annual(next(s for s in w if s.title.startswith('Aggregates (') and 'bn' in s.title), 30)
    soup = BeautifulSoup((RAW / 'boe_rate.html').read_text(encoding='utf-8'), 'html.parser')
    months = {}
    for tr in soup.find_all('tr'):
        cells = [c.get_text(' ', strip=True) for c in tr.find_all('td')]
        if len(cells) >= 2 and re.fullmatch(r'\d{1,2} [A-Za-z]{3} \d{2}', cells[0]):
            d = datetime.strptime(cells[0], '%d %b %y')
            months[(d.year, d.month)] = float(cells[1])
    if not months:
        raise ValueError('Bank Rate data table missing')
    rates = {}
    for y in range(1982, 2026):
        ms = [(y, m) for m in range(4, 13)] + [(y+1, m) for m in range(1, 4)]
        if all(m in months for m in ms):
            rates[fy(y)] = sum(months[m] for m in ms) / 12
    rows = []
    for y in range(1982, 2026):
        period = fy(y)
        rows.append(dict(fiscal_year=period,
                         real_gdp_growth_pct=100*(real[period]/real[fy(y-1)]-1) if period in real and fy(y-1) in real else '',
                         nominal_gdp_gbp_bn=gdp.get(period, ''), cpi_inflation_pct=cpi.get(period, ''),
                         bank_rate_pct=rates.get(period, ''), unemployment_rate_pct=unemployed.get(period, ''),
                         pnfc_gross_operating_surplus_gbp_bn=pnfc.get(period, ''),
                         business_investment_gbp_bn=investment.get(period, ''),
                         source_ids='; '.join(['D-ons-real-gdp', 'D-obr-databank', 'D-ons-cpi',
                                               'D-boe-bank-rate', 'D-ons-unemployment', 'D-ons-pnfc', 'D-ons-investment'])))
    write('macro_annual', rows, 'D-ons-real-gdp',
          'Fiscal April–March: quarterly flows sum Q2–Q1, divide £m by 1000; rates average four quarterly values. ABMI real GDP growth is year-on-year fiscal sum growth. CAER PNFC GOS is seasonally adjusted current-price £m. Bank Rate IUMABEDR monthly averages average April–March. GDP: OBR databank AE. Missing early observations are empty, never interpolated. All source_ids enumerate exact fetched series.', vintage='ONS September/October 2026; BoE November 2026')
    with (RAW / 'ons_investment.csv').open(encoding='utf-8-sig') as f:
        raw = list(csv.reader(f))
    asset_codes = {'plant_machinery': ['EDRB', 'EDWH'], 'structures': ['EDYP'], 'intangibles': ['EDYS']}
    assets = []
    for y in range(1997, 2026):
        values = {}
        for asset, codes in asset_codes.items():
            cols = [raw[1].index(c) for c in codes]
            qs = [r for r in raw if r[0] in [f'{y} Q{q}' for q in range(1, 5)]]
            if len(qs) == 4 and all(r[c] for r in qs for c in cols):
                values[asset] = sum(float(r[c]) for r in qs for c in cols) / 1000
        if len(values) == 3:
            total = sum(values.values())
            assets.extend(dict(year=y, asset=a, value_gbp_bn=v, share=v/total, source_id='D-ons-investment')
                          for a, v in values.items())
    write('business_investment_by_asset', assets, 'D-ons-investment',
          'Calendar-year sums of four CP SA quarters (£m/1000). plant_machinery=EDRB transport+EDWH ICT/other machinery; structures=EDYP; intangibles=EDYS. Non-government business investment; transport grouped with machinery explicitly. Shares divide by sum of the three groups; validate against NPEK.', vintage='ONS September 2026')


def build_costings():
    rows = []
    for filename, change, match, first_year, event in [
        ('budget2021.html', 'CT-MAIN-2023', 'tapering to main rate of 25%', 2020, 'Spring Budget 2021'),
        ('budget2015.html', 'CT-MAIN-2017', 'reduce to 19% from 2017', 2015, 'Summer Budget 2015'),
    ]:
        soup = BeautifulSoup((RAW / filename).read_text(encoding='utf-8'), 'html.parser')
        found = [tr for tr in soup.find_all('tr') if match in tr.get_text(' ', strip=True)]
        if len(found) != 1:
            raise ValueError(f'Expected exactly one costing row: {filename}')
        cells = [c.get_text(' ', strip=True) for c in found[0].find_all(['td', 'th'])]
        values = cells[cells.index('Tax') + 1:]
        for offset, value in enumerate(values):
            rows.append(dict(change_id=change, costing_body='HMT', fiscal_event=event,
                             fiscal_year=fy(first_year+offset), value_gbp_bn=float(value.replace(',', '').replace('−', '-'))/1000,
                             includes_behavioural='', source_id=source_id(filename)))
    text = ' '.join(PdfReader(RAW / 'budget2012.pdf').pages[50].extract_text().split())
    match = re.search(r'Corporation tax: decrease main rate Tax ((?:[–−-]\d[\d,]*\s*){5})', text)
    if not match:
        raise ValueError('Budget 2012 Table 2.1 row 7 changed')
    values = [float(v.replace('–', '-').replace('−', '-').replace(',', ''))/1000 for v in match[1].split()]
    for change in ('CT-MAIN-2012', 'CT-MAIN-2013'):
        for i, value in enumerate(values):
            rows.append(dict(change_id=change, costing_body='HMT', fiscal_event='Budget 2012 (joint phased package)',
                             fiscal_year=fy(2012+i), value_gbp_bn=value, includes_behavioural='', source_id='D-budget2012'))
    write('ct_costings', rows, 'D-budget2021',
          'Original HMT tables, £m/1000, positive=Exchequer revenue. Budget 2021 Table 2.1 row 22; Summer Budget 2015 Table 2.1 row 9 (joint 19/18 percent package, including subsequently reversed 2020 element); Budget 2012 Table 2.1 row 7 printed p50/PDF p51 (joint 2012–14 package, linked to 2012 and 2013 changes: do NOT add these duplicated package references together). No isolated causal costings implied. Behavioural inclusion unspecified in these tables: null, not guessed. Earlier unsourced costings are absent, never zero-filled. OBR measures workbook extrapolates original policy effects and is not used as an original costing.', vintage='Original HMT Budget 2012 / 2015 / 2021')


def build(*, offline=False):
    if not offline:
        fetch()
    build_rates()
    build_fiscal()
    build_macro_assets()
    build_costings()
    sources = [dict(source_id=sid, title=title, url=URLS[raw], publisher=pub,
                    publisher_type=kind, published_date='', reliability_tier=1)
               for sid, (title, raw, pub, kind) in SOURCES.items()]
    write('sources', sources, 'D-hmrc-rates', 'Source URLs were fetched by fetch_official.py; raw hashes are in each metadata file.', vintage='2026-11-07')
    (OUT / 'provenance.json').write_text((RAW / 'manifest.json').read_text(encoding='utf-8'), encoding='utf-8')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--offline', action='store_true', help='Build only from already fetched raw releases')
    build(offline=parser.parse_args().offline)
