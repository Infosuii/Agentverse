"""Download pinned official releases; raw responses are never committed."""
import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
URLS = {
    'hmrc_rates.html': 'https://www.gov.uk/government/publications/rates-and-allowances-corporation-tax/rates-and-allowances-corporation-tax',
    'hmrc_history.pdf': 'https://www.gov.uk/government/uploads/system/uploads/attachment_data/file/257049/table-a6.pdf',
    'obr_databank.xlsx': 'https://obr.uk/download/public-finances-databank-october-2026-efo/',
    'obr_measures.xlsx': 'https://obr.uk/download/policy-measures-database/',
    'obr_oct_tables.zip': 'https://obr.uk/download/october-2026-economic-and-fiscal-outlook-detailed-forecast-tables-zip-file/',
    'hmrc_background.html': 'https://www.gov.uk/government/statistics/corporation-tax-statistics-2026/background-and-guidance-to-interpreting-corporation-tax-statistics-2026',
    'ons_investment.csv': 'https://www.ons.gov.uk/file?uri=/economy/grossdomesticproductgdp/datasets/businessinvestment/current/cxnv.csv',
}


def fetch():
    raw = ROOT / 'raw'
    raw.mkdir(parents=True, exist_ok=True)
    manifest = {}
    old = json.loads((raw / 'manifest.json').read_text()) if (raw / 'manifest.json').exists() else {}
    for name, url in URLS.items():
        path = raw / name
        if not path.exists():
            with urlopen(Request(url, headers={'User-Agent': 'JaneAvenue-data/0.1'}), timeout=90) as response:
                path.write_bytes(response.read())
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        retrieved = old.get(name, {}).get('retrieved_at') if old.get(name, {}).get('sha256') == digest else None
        manifest[name] = {'url': url, 'sha256': digest, 'retrieved_at': retrieved or datetime.now(UTC).date().isoformat()}
        print(name, path.stat().st_size)
    (raw / 'manifest.json').write_text(json.dumps(manifest, indent=2), encoding='utf-8')


if __name__ == '__main__':
    fetch()
