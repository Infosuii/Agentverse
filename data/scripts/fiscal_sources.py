"""Download and read the official sources behind the fiscal precedent library. No figure is typed in by hand.

Every rate, costing and outturn in the library is read from one of the files below. The only hand-kept facts are the
VAT standard-rate changes, because no official table of them exists, and `VAT_CHANGES` must quote each one exactly from
the House of Commons Library briefing or the OBR database: `build_fiscal_precedents.py` stops if a quote is not found.

Raw files go to data/raw/ (git-ignored); their SHA-256 is recorded in provenance.json.
"""
from __future__ import annotations

import hashlib
import csv
import re
import time
import zipfile
from datetime import date, datetime
from pathlib import Path
from xml.etree import ElementTree as ET

import httpx
import openpyxl
from bs4 import BeautifulSoup
from pypdf import PdfReader

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "raw"
UA = {"User-Agent": "JaneAvenue-data/0.1"}  # the client name fetch_official.py already uses
GOV = "https://www.gov.uk/government/statistics"
ASSETS = "https://assets.publishing.service.gov.uk/media"
ONS = "https://www.ons.gov.uk/economy/governmentpublicsectorandtaxes/publicsectorfinance/timeseries"

# source_id -> (title, landing or file url, publisher, publisher_type, raw file, download url)
SOURCES: dict[str, tuple[str, str, str, str, str, str]] = {
    "D-obr-policy-measures": (
        "OBR policy measures database", "https://obr.uk/data/", "Office for Budget Responsibility", "obr",
        "obr_policy_measures.xlsx", "https://obr.uk/download/policy-measures-database/"),
    "D-obr-databank-2026": (
        "OBR public finances databank, October 2026", "https://obr.uk/data/", "Office for Budget Responsibility", "obr",
        "obr_databank_oct_2026.xlsx", "https://obr.uk/download/public-finances-databank-october-2026-efo/"),
    "D-hmrc-table-a1": (
        "HMRC Table A.1: Income Tax personal allowances and reliefs",
        f"{GOV}/income-tax-personal-allowances-and-reliefs", "HMRC", "hmrc", "hmrc_table_a1.ods",
        f"{ASSETS}/6a54c97ba4890e65cce64db8/Table_a1_-_Income_Tax_-_personal_allowances_and_reliefs.ods"),
    "D-hmrc-table-a2": (
        "HMRC Table A.2: Rates of Income Tax", f"{GOV}/rates-of-income-statistics", "HMRC", "hmrc", "hmrc_table_a2.ods",
        f"{ASSETS}/6a54ca0b9e9c95844ae64d9a/Table_a2_-_Income_Tax_-_rates_and_allowances.ods"),
    "D-hmrc-table-a4": (
        "HMRC Table A.4: National Insurance contributions rates and allowances",
        f"{GOV}/main-features-of-national-insurance-contributions", "HMRC", "hmrc", "hmrc_table_a4.ods",
        f"{ASSETS}/6a54ca0fa4890e65cce64db9/Table_a4_-_National_Insurance_Contributions_-_rates_and_allowances.ods"),
    "D-hmrc-oil-duty-history": (
        "HMRC Hydrocarbon Oils Bulletin: historical duty rates",
        f"{GOV}/hydrocarbon-oils-bulletin/historical-hydrocarbon-oils-duty-rates--2", "HMRC", "hmrc",
        "hmrc_oil_duty_history.html", f"{GOV}/hydrocarbon-oils-bulletin/historical-hydrocarbon-oils-duty-rates--2"),
    "D-hmrc-alcohol-duty-history": (
        "HMRC Alcohol Bulletin: historic duty rates", f"{GOV}/alcohol-bulletin/alcohol-bulletin-historic-duty-rates",
        "HMRC", "hmrc", "hmrc_alcohol_duty_history.html", f"{GOV}/alcohol-bulletin/alcohol-bulletin-historic-duty-rates"),
    "D-hmrc-tobacco-duty-history": (
        "HMRC Tobacco Bulletin: historical duty rates", f"{GOV}/tobacco-bulletin/historical-tobacco-duty-rates",
        "HMRC", "hmrc", "hmrc_tobacco_duty_history.html", f"{GOV}/tobacco-bulletin/historical-tobacco-duty-rates"),
    "D-hmrc-ipt-history": (
        "HMRC Insurance Premium Tax Bulletin: historical rates",
        f"{GOV}/insurance-premium-tax-ipt-bulletin/historical-insurance-premium-tax-rates--2", "HMRC", "hmrc",
        "hmrc_ipt_history.html", f"{GOV}/insurance-premium-tax-ipt-bulletin/historical-insurance-premium-tax-rates--2"),
    "D-hmrc-apd-history": (
        "HMRC Air Passenger Duty Bulletin: historical rates", f"{GOV}/air-passenger-duty-bulletin/air-passenger-duty-rates",
        "HMRC", "hmrc", "hmrc_apd_history.html", f"{GOV}/air-passenger-duty-bulletin/air-passenger-duty-rates"),
    "D-hmrc-iht-thresholds": (
        "HMRC Inheritance Tax thresholds and interest rates",
        "https://www.gov.uk/government/publications/rates-and-allowances-inheritance-tax-thresholds-and-interest-rates/"
        "inheritance-tax-thresholds-and-interest-rates", "HMRC", "hmrc", "hmrc_iht_thresholds.html",
        "https://www.gov.uk/government/publications/rates-and-allowances-inheritance-tax-thresholds-and-interest-rates/"
        "inheritance-tax-thresholds-and-interest-rates"),
    "D-govuk-minimum-wage": (
        "National Minimum Wage and National Living Wage rates", "https://www.gov.uk/national-minimum-wage-rates",
        "HM Government", "other", "govuk_minimum_wage.html", "https://www.gov.uk/national-minimum-wage-rates"),
    "D-dwp-abstract-2025": (
        "Abstract of DWP benefit rate statistics 2025", f"{GOV}/abstract-of-dwp-benefit-rate-statistics-2025",
        "Department for Work and Pensions", "other", "dwp_abstract_2025.ods",
        f"{ASSETS}/697391a9276692606c0137af/data-tables-abstract-of-dwp-benefit-rate-statistics-2025.ods"),
    "D-dwp-expenditure-2026": (
        "DWP benefit expenditure and caseload tables, Spring Forecast 2026",
        "https://www.gov.uk/government/publications/benefit-expenditure-and-caseload-tables-2026",
        "Department for Work and Pensions", "other", "dwp_expenditure_2026.xlsx",
        f"{ASSETS}/69dcdc8c6b695d635c34dcc4/outturn-and-forecast-tables-spring-forecast-2026.xlsx"),
    "D-hmt-pesa-2026-ch4": (
        "HM Treasury Public Expenditure Statistical Analyses 2026, Chapter 4 tables",
        f"{GOV}/public-expenditure-statistical-analyses-2026", "HM Treasury", "hmt", "hmt_pesa_2026_ch4.xlsx",
        f"{ASSETS}/6a5772e09e63154454413700/PESA_2026_CP_Chapter_4_tables.xlsx"),
    **{sid: (title, f"{ONS}/{code}/pusf", "Office for National Statistics", "ons", name,
             f"https://www.ons.gov.uk/generator?format=csv&uri=/economy/governmentpublicsectorandtaxes/publicsectorfinance/timeseries/{code}/pusf")
       for sid, title, code, name in (
           ("D-ons-income-tax-cash", "ONS RURC: central government cash receipts, Income Tax", "rurc", "ons_income_tax_cash.csv"),
           ("D-ons-vat-cash", "ONS EYOO: central government cash receipts, VAT", "eyoo", "ons_vat_cash.csv"),
           ("D-ons-nics-cash", "ONS ABLP: central government cash receipts, social security contributions", "ablp", "ons_nics_cash.csv"),
           ("D-ons-fuel-duty", "ONS CUDG: central government receipts, fuel duty", "cudg", "ons_fuel_duty.csv"),
           ("D-ons-tobacco-duty", "ONS GTAO: central government receipts, tobacco duty", "gtao", "ons_tobacco_duty.csv"),
           ("D-ons-alcohol-duty", "ONS MF6V: central government receipts, alcohol duty", "mf6v", "ons_alcohol_duty.csv"))},
    "D-commons-vat-sn00701": (
        "House of Commons Library SN00701: VAT, the temporary cut in the standard rate",
        "https://commonslibrary.parliament.uk/research-briefings/sn00701/", "House of Commons Library", "parliament",
        "commons_sn00701.pdf", "https://researchbriefings.files.parliament.uk/documents/SN00701/SN00701.pdf"),
}


def fetch_all() -> dict[str, str]:
    """Download each source once into data/raw/ and return {raw file name: SHA-256}."""
    RAW.mkdir(parents=True, exist_ok=True)
    hashes: dict[str, str] = {}
    with httpx.Client(headers=UA, follow_redirects=True, timeout=120) as client:
        for _title, _page, _pub, _kind, name, url in SOURCES.values():
            path = RAW / name
            if not path.exists():
                if "ons.gov.uk" in url:
                    time.sleep(8)  # the ONS site rate-limits quick repeated requests
                response = client.get(url)
                response.raise_for_status()
                path.write_bytes(response.content)
            hashes[name] = hashlib.sha256(path.read_bytes()).hexdigest()
    return hashes


# ---- readers ---------------------------------------------------------------------------------------------------------

_T, _X, _O = ("{urn:oasis:names:tc:opendocument:xmlns:table:1.0}", "{urn:oasis:names:tc:opendocument:xmlns:text:1.0}",
              "{urn:oasis:names:tc:opendocument:xmlns:office:1.0}")


def read_ods(name: str) -> dict[str, list[list[str]]]:
    root = ET.fromstring(zipfile.ZipFile(RAW / name).read("content.xml"))
    out: dict[str, list[list[str]]] = {}
    for table in root.iter(_T + "table"):
        rows = []
        for row in table.iter(_T + "table-row"):
            cells: list[str] = []
            for cell in row:
                if not cell.tag.endswith("table-cell"):
                    continue
                repeat = min(int(cell.get(_T + "number-columns-repeated", "1")), 60)
                value = cell.get(_O + "value") or cell.get(_O + "date-value") or " ".join(
                    "".join(p.itertext()) for p in cell.findall(_X + "p"))
                cells += [value] * repeat
            if any(cells):
                rows.append(cells)
        out[table.get(_T + "name")] = rows
    return out


def html_tables(name: str) -> list[tuple[str, list[list[str]]]]:
    """Each table as (nearest preceding heading, rows of cell text)."""
    soup = BeautifulSoup((RAW / name).read_text(encoding="utf-8", errors="replace"), "html.parser")
    out = []
    for table in (soup.find("main") or soup).find_all("table"):
        heading = table.find_previous(["h2", "h3", "h4"])
        rows = [[re.sub(r"\s+", " ", c.get_text(" ", strip=True)) for c in r.find_all(["th", "td"])]
                for r in table.find_all("tr")]
        out.append((heading.get_text(" ", strip=True) if heading else "", rows))
    return out


def pdf_text(name: str) -> str:
    return re.sub(r"\s+", " ", " ".join(p.extract_text() or "" for p in PdfReader(RAW / name).pages))


def workbook(name: str, *, read_only: bool = True):
    return openpyxl.load_workbook(RAW / name, read_only=read_only, data_only=True)


def ons_fiscal_years(name: str) -> dict[str, float]:
    """A quarterly ONS series as April-to-March fiscal years in £bn; only years with all four quarters."""
    with (RAW / name).open(encoding="utf-8-sig") as handle:
        rows = list(csv.reader(handle))
    quarters = {r[0].replace(" ", ""): float(r[1]) for r in rows if re.fullmatch(r"\d{4} Q[1-4]", r[0]) and len(r) > 1 and r[1]}
    out: dict[str, float] = {}
    for year in range(1946, date.today().year):
        needed = (f"{year}Q2", f"{year}Q3", f"{year}Q4", f"{year + 1}Q1")
        if all(q in quarters for q in needed):
            out[f"{year}-{str(year + 1)[-2:]}"] = sum(quarters[q] for q in needed) / 1000.0
    return out


def number(text: object) -> float | None:
    """The leading number of a table cell ("25 (note 3)" -> 25, "£12,570" -> 12570), or None ("N/A", "No data")."""
    match = re.match(r"\s*£?\s*(-?\d[\d,]*(?:\.\d+)?(?:[eE]-?\d+)?)", str(text))
    return float(match.group(1).replace(",", "")) if match else None


def parse_date(text: str) -> date | None:
    text = re.sub(r"\s+", " ", str(text)).strip()
    for fmt, value in (("%Y-%m-%d", text[:10]), ("%d %B %Y", text), ("%d.%m.%y", text), ("%d %b %Y", text)):
        try:
            return datetime.strptime(value, fmt).date()
        except ValueError:
            continue
    return None
