"""Download pinned official releases; raw responses are never committed."""
import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from policy_events import DOCUMENTS

ROOT = Path(__file__).resolve().parents[1]
URLS = {
    'hmrc_rates.html': 'https://www.gov.uk/government/publications/rates-and-allowances-corporation-tax/rates-and-allowances-corporation-tax',
    'hmrc_history.pdf': 'https://www.gov.uk/government/uploads/system/uploads/attachment_data/file/257049/table-a6.pdf',
    'obr_databank.xlsx': 'https://obr.uk/download/public-finances-databank-october-2026-efo/',
    'obr_measures.xlsx': 'https://obr.uk/download/policy-measures-database/',
    'obr_oct_tables.zip': 'https://obr.uk/download/october-2026-economic-and-fiscal-outlook-detailed-forecast-tables-zip-file/',
    'hmrc_background.html': 'https://www.gov.uk/government/statistics/corporation-tax-statistics-2026/background-and-guidance-to-interpreting-corporation-tax-statistics-2026',
    'ons_investment.csv': 'https://www.ons.gov.uk/file?uri=/economy/grossdomesticproductgdp/datasets/businessinvestment/current/cxnv.csv',
    'ons_real_gdp.csv': 'https://www.ons.gov.uk/generator?format=csv&uri=/economy/grossdomesticproductgdp/timeseries/abmi/qna',
    'ons_pnfc.csv': 'https://www.ons.gov.uk/generator?format=csv&uri=/economy/grossdomesticproductgdp/timeseries/caer/ukea',
    'ons_cpi.csv': 'https://www.ons.gov.uk/generator?format=csv&uri=/economy/inflationandpriceindices/timeseries/d7g7/mm23',
    'ons_ct_receipts.csv': 'https://www.ons.gov.uk/generator?format=csv&uri=/economy/governmentpublicsectorandtaxes/publicsectorfinance/timeseries/n445/pusf',
    'ons_unemployment.csv': 'https://www.ons.gov.uk/generator?format=csv&uri=/employmentandlabourmarket/peoplenotinwork/unemployment/timeseries/mgsx/lms',
    'boe_rate.html': 'https://www.bankofengland.co.uk/boeapps/database/fromshowcolumns.asp?CSVF=TT&DAT=ALL&FNY=Y&Filter=N&FromSeries=1&SeriesCodes=IUMABEDR%2CIUMTLMV%2CIUMBV34&ToSeries=50&Travel=NIxAZxSUx&UsingCodes=Y&html.x=66&html.y=26',
}
URLS.update({name: info[0] for name, info in DOCUMENTS.items()})


def fetch():
    raw = ROOT / 'raw'
    raw.mkdir(parents=True, exist_ok=True)
    manifest = {}
    old = json.loads((raw / 'manifest.json').read_text()) if (raw / 'manifest.json').exists() else {}
    for name, url in URLS.items():
        path = raw / name
        if not path.exists():
            try:
                with urlopen(Request(url, headers={'User-Agent': 'JaneAvenue-data/0.1'}), timeout=90) as response:
                    path.write_bytes(response.read())
            except HTTPError as exc:
                if name in DOCUMENTS and exc.code == 403:
                    # Dates are documented manual transcriptions, not parsed numeric datasets.
                    manifest[name] = {'url': url, 'sha256': None, 'retrieved_at': None,
                                      'notes': 'Download denied (403); documented manual transcription in policy_events.py and DATA.md.'}
                    print(name, '403: manual transcription source')
                    continue
                raise
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        retrieved = old.get(name, {}).get('retrieved_at') if old.get(name, {}).get('sha256') == digest else None
        manifest[name] = {'url': url, 'sha256': digest, 'retrieved_at': retrieved or datetime.now(UTC).date().isoformat()}
        print(name, path.stat().st_size)
    (raw / 'manifest.json').write_text(json.dumps(manifest, indent=2), encoding='utf-8')


if __name__ == '__main__':
    fetch()

