"""Build the curated HMRC ready-reckoner and tax-measure datasets from official downloads, never from seeds.

Outputs (all under data/curated/):
- hmrc_ready_reckoner.csv (+ .meta.json): every row of HMRC "Direct effects of illustrative tax changes" (June 2025),
  verbatim labels, one row per (section, label, fiscal year), £m as published ("Neg" = negligible, stored as 0 and
  flagged).
- tax_measures.csv (+ .meta.json): the modelling layer. Each measure names the ready-reckoner rows that cost it, the unit
  of change, the sign convention of those rows, a hard scope limit and the current rate, which is verified by an exact
  quote in the live gov.uk page (the script fails if a quote is not found: no number is ever typed in by hand).
- sources.csv: the new source rows are appended once.

Run from the repo root:  backend/.venv/Scripts/python data/scripts/build_tax_measures.py
Raw downloads go to data/raw/ (git-ignored); their SHA-256 is recorded in the metadata and in provenance.json.
"""
from __future__ import annotations

import csv
import hashlib
import json
import re
import sys
import unicodedata
import zipfile
from datetime import date
from pathlib import Path
from xml.etree import ElementTree as ET

import httpx
from bs4 import BeautifulSoup

ROOT = Path(__file__).resolve().parents[1]
RAW, OUT = ROOT / "raw", ROOT / "curated"
UA = {"User-Agent": "JaneAvenue/0.1 (research prototype)"}
TODAY = date.today().isoformat()

RR_ID = "D-hmrc-ready-reckoner-2025"
RR_URL = "https://www.gov.uk/government/statistics/direct-effects-of-illustrative-tax-changes"
RR_ODS = "https://assets.publishing.service.gov.uk/media/68552862b46781eacfd71d71/June_2025_TRR_ODS__1_.ods"
RR_FILE = "hmrc_ready_reckoner_june_2025.ods"
RR_YEARS = ("2026-27", "2027-28", "2028-29")

# source_id -> (title, url, publisher, publisher_type, raw file)
SOURCES: dict[str, tuple[str, str, str, str, str]] = {
    RR_ID: ("Direct effects of illustrative tax changes (June 2025)", RR_URL, "HMRC", "hmrc", RR_FILE),
    "D-govuk-income-tax-rates": ("Income Tax rates and Personal Allowances", "https://www.gov.uk/income-tax-rates",
                                 "HMRC", "hmrc", "govuk_income_tax_rates.html"),
    "D-govuk-ni-rates": ("National Insurance rates and category letters",
                         "https://www.gov.uk/national-insurance-rates-letters", "HMRC", "hmrc", "govuk_ni_rates.html"),
    "D-govuk-ni-self-employed": ("Self-employed National Insurance rates",
                                 "https://www.gov.uk/self-employed-national-insurance-rates", "HMRC", "hmrc",
                                 "govuk_ni_self_employed.html"),
    "D-govuk-vat-rates": ("VAT rates", "https://www.gov.uk/vat-rates", "HMRC", "hmrc", "govuk_vat_rates.html"),
    "D-govuk-cgt-rates": ("Capital Gains Tax: what you pay", "https://www.gov.uk/capital-gains-tax/rates", "HMRC",
                          "hmrc", "govuk_cgt_rates.html"),
    "D-govuk-inheritance-tax": ("Inheritance Tax", "https://www.gov.uk/inheritance-tax", "HMRC", "hmrc",
                                "govuk_inheritance_tax.html"),
    "D-govuk-ipt": ("Insurance Premium Tax", "https://www.gov.uk/guidance/insurance-premium-tax", "HMRC", "hmrc",
                    "govuk_ipt.html"),
    "D-hmrc-fuel-duty": ("Excise duty hydrocarbon oils rates",
                         "https://www.gov.uk/government/publications/rates-and-allowances-excise-duty-hydrocarbon-oils/"
                         "excise-duty-hydrocarbon-oils-rates", "HMRC", "hmrc", "hmrc_fuel_duty.html"),
    "D-govuk-child-benefit": ("Child Benefit: what you'll get", "https://www.gov.uk/child-benefit/what-youll-get",
                              "HMRC", "hmrc", "govuk_child_benefit.html"),
}

S_IT, S_PA, S_NIC = "Income Tax rates", "Income Tax allowances and reliefs", "National Insurance contributions rates"
S_CB, S_CGT, S_IHT = "Child Benefit", "Capital Gains Tax", "Inheritance tax"
S_DUTY, S_VAT, S_IPT = "1% change in various duties", "VAT", "Insurance premium tax"


def _pts(*pairs: tuple[float, list[tuple[str, str]]]) -> str:
    """'size=section::label+section::label;size=...'"""
    return ";".join(f"{size:g}=" + "+".join(f"{s}::{lab}" for s, lab in rows) for size, rows in pairs)


def _cgt(which: str) -> str:
    return _pts(*[(n, [(S_CGT, f"Increase {which} Capital Gains Tax rate by {n} percentage point{'s' if n > 1 else ''}")])
                  for n in (1, 5, 10)])


# measure_id, label, tax, policy_area, unit, current (value, unit, source_id, [quotes]) or None,
# points_up, sign_up, points_down ('' = mirror the increase), sign_down, max_change
MEASURES = [
    ("income_tax_basic_rate", "Income Tax basic rate", "income_tax", "tax", "pp",
     (20, "%", "D-govuk-income-tax-rates", ["Basic rate £12,571 to £50,270 20%"]),
     _pts((1, [(S_IT, "Change basic rate by 1p")])), 1, "", 0, 5),
    ("income_tax_higher_rate", "Income Tax higher rate", "income_tax", "tax", "pp",
     (40, "%", "D-govuk-income-tax-rates", ["Higher rate £50,271 to £125,140 40%"]),
     _pts((1, [(S_IT, "Change higher rate by 1p")])), 1, "", 0, 5),
    ("income_tax_additional_rate", "Income Tax additional rate", "income_tax", "tax", "pp",
     (45, "%", "D-govuk-income-tax-rates", ["Additional rate over £125,140 45%"]),
     _pts((1, [(S_IT, "Increase additional rate by 1p (yield)")])), 1,
     _pts((1, [(S_IT, "Decrease additional rate by 1p (cost)")])), -1, 5),
    ("income_tax_personal_allowance", "Income Tax Personal Allowance", "income_tax", "tax", "gbp",
     (12570, "£", "D-govuk-income-tax-rates", ["The standard Personal Allowance is £12,570"]),
     _pts((100, [(S_PA, "Change personal allowance by £100")]),
          (1257, [(S_PA, "Change personal allowance by 10%")])), -1, "", 0, 2514),
    ("nics_employee_main_rate", "Class 1 employee National Insurance main rate", "national_insurance", "tax", "pp",
     (8, "%", "D-govuk-ni-rates", ["from 6 April 2026 to 5 April 2027",
                                   "Over £967 a week (£4,189 a month) A 0% 8% 2%"]),
     _pts((1, [(S_NIC, "Change Class 1 employee main rate by 1 percentage point")])), 1, "", 0, 5),
    ("nics_employer_rate", "Class 1 employer National Insurance rate", "national_insurance", "tax", "pp",
     (15, "%", "D-govuk-ni-rates", ["how much employers pay towards employees’ National Insurance from 6 April 2026 to "
                                    "5 April 2027", "A 15% 15% 15%"]),
     _pts((1, [(S_NIC, "Change Class 1 employer rate by 1 percentage point")])), 1, "", 0, 5),
    ("nics_class4_main_rate", "Class 4 self-employed National Insurance main rate", "national_insurance", "tax", "pp",
     (6, "%", "D-govuk-ni-self-employed", ["6% on profits over £12,570 up to £50,270"]),
     _pts((1, [(S_NIC, "Change Class 4 main rate by 1 percentage point")])), 1, "", 0, 5),
    ("cgt_lower_rate", "Capital Gains Tax lower rate", "capital_gains_tax", "tax", "pp",
     (18, "%", "D-govuk-cgt-rates", ["you’ll pay 18% on your gains made from 6 April 2026"]),
     _cgt("lower"), 1, "", 0, 10),
    ("cgt_higher_rate", "Capital Gains Tax higher rate", "capital_gains_tax", "tax", "pp",
     (24, "%", "D-govuk-cgt-rates", ["you’ll pay 24% on gains made from 6 April 2026"]),
     _cgt("higher"), 1, "", 0, 10),
    ("inheritance_tax_rate", "Inheritance Tax standard rate", "inheritance_tax", "tax", "pp",
     (40, "%", "D-govuk-inheritance-tax", ["The standard Inheritance Tax rate is 40%."]),
     _pts((1, [(S_IHT, "Increase standard rate for estates left on death by 1 percentage point")])), 1, "", 0, 10),
    ("vat_standard_rate", "VAT standard rate", "vat", "tax", "pp",
     (20, "%", "D-govuk-vat-rates", ["Standard rate 20%"]),
     _pts((1, [(S_VAT, "Change standard rate by 1 percentage point")])), 1, "", 0, 5),
    ("vat_reduced_rate", "VAT reduced rate", "vat", "tax", "pp",
     (5, "%", "D-govuk-vat-rates", ["Reduced rate 5%"]),
     _pts((1, [(S_VAT, "Change reduced rate by 1 percentage point")])), 1, "", 0, 5),
    ("ipt_standard_rate", "Insurance Premium Tax standard rate", "insurance_premium_tax", "tax", "pp",
     (12, "%", "D-govuk-ipt", ["a standard rate 12%"]),
     _pts((1, [(S_IPT, "Change standard rate by 1 percentage point")])), 1, "", 0, 5),
    ("fuel_duty", "Fuel duty (petrol and diesel)", "fuel_duty", "tax", "pct_of_rate",
     (52.95, "p/litre", "D-hmrc-fuel-duty", ["Unleaded petrol 0.5295", "Heavy oil (diesel) 0.5295"]),
     _pts((1, [(S_DUTY, "Petrol"), (S_DUTY, "Diesel")])), 1, "", 0, 20),
    ("alcohol_duty", "Alcohol duties (beer, cider, wine and spirits)", "alcohol_duty", "tax", "pct_of_rate", None,
     _pts((1, [(S_DUTY, "Beer and cider duties"), (S_DUTY, "Wine and other fermented product duties"),
               (S_DUTY, "Spirits duties")])), 1, "", 0, 20),
    ("tobacco_duty", "Tobacco duties", "tobacco_duty", "tax", "pct_of_rate", None,
     _pts((1, [(S_DUTY, "Tobacco Duties")])), 1, "", 0, 20),
    ("child_benefit", "Child Benefit weekly rates (eldest and additional children)", "child_benefit", "spending",
     "gbp_per_week", (27.05, "£/week (eldest child)", "D-govuk-child-benefit", ["Eldest or only child £27.05",
                                                                               "£17.90 per child"]),
     _pts((1, [(S_CB, "Increase first child rate by £1 per week (cost)"),
               (S_CB, "Increase subsequent child rate by £1 per week (cost)")])), -1,
     _pts((1, [(S_CB, "Decrease first child rate by £1 per week (yield)"),
               (S_CB, "Decrease subsequent child rate by £1 per week (yield)")])), 1, 10),
]


def _norm(text: str) -> str:
    return re.sub(r"\s+", " ", unicodedata.normalize("NFKC", text)).strip()


def _download(url: str, name: str) -> bytes:
    path = RAW / name
    if not path.exists():
        RAW.mkdir(parents=True, exist_ok=True)
        resp = httpx.get(url, headers=UA, follow_redirects=True, timeout=30)
        resp.raise_for_status()
        path.write_bytes(resp.content)
    return path.read_bytes()


def _ods_rows(data: bytes) -> list[list[str]]:
    t = "{urn:oasis:names:tc:opendocument:xmlns:table:1.0}"
    p = "{urn:oasis:names:tc:opendocument:xmlns:text:1.0}p"
    root = ET.fromstring(zipfile.ZipFile(__import__("io").BytesIO(data)).read("content.xml"))
    rows: list[list[str]] = []
    for row in root.iter(t + "table-row"):
        cells: list[str] = []
        for cell in row.iter(t + "table-cell"):
            text = " ".join("".join(x.itertext()) for x in cell.findall(p)).strip()
            cells += [text] * min(int(cell.get(t + "number-columns-repeated", "1")), 10)
        while cells and not cells[-1]:
            cells.pop()
        if cells:
            rows.append(cells)
    return rows


def ready_reckoner(data: bytes) -> list[dict]:
    rows = _ods_rows(data)
    header = next(r for r in rows if r[0] == "Column1")
    years = [re.search(r"(\d{4}) to (\d{4})", h).group(1) for h in header[1:4]]  # type: ignore[union-attr]
    expected = tuple(f"{y}-{str(int(y) + 1)[-2:]}" for y in years)
    if expected != RR_YEARS:
        sys.exit(f"Unexpected ready-reckoner years {expected}")
    out, section = [], ""
    for r in rows[rows.index(header) + 1:]:
        if len(r) == 1:
            if r[0].startswith(("For detailed", "End of worksheet")):
                continue
            section = r[0]
            continue
        label = _norm(r[0])
        for fy, raw in zip(RR_YEARS, r[1:4], strict=True):
            neg = raw.strip().lower() == "neg"
            value = 0.0 if neg else float(raw.replace(",", ""))
            out.append({"section": section, "label": label, "fiscal_year": fy, "value_gbp_m": value,
                        "is_negligible": neg, "source_id": RR_ID})
    return out


def _page_text(source_id: str) -> str:
    _, url, *_rest, name = SOURCES[source_id]
    html = _download(url, name)
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup(["script", "style", "nav"]):
        tag.decompose()
    return _norm(soup.get_text(" "))


def measures(rr: list[dict]) -> list[dict]:
    labels = {(r["section"], r["label"]) for r in rr}
    out = []
    for (mid, label, tax, area, unit, current, up, sign_up, down, sign_down, max_change) in MEASURES:
        for spec in (up, down):
            for point in filter(None, spec.split(";")):
                for ref in point.split("=", 1)[1].split("+"):
                    section, row = ref.split("::", 1)
                    if (section, _norm(row)) not in labels:
                        sys.exit(f"{mid}: ready-reckoner row not found: {ref}")
        row = {"measure_id": mid, "label": label, "tax": tax, "policy_area": area, "unit": unit,
               "current_value": "", "current_unit": "", "current_quote": "", "points_up": up, "sign_up": sign_up,
               "points_down": down, "sign_down": sign_down, "max_change": max_change, "source_ids": RR_ID}
        if current is not None:
            value, cunit, sid, quotes = current
            text = _page_text(sid)
            for q in quotes:
                if _norm(q) not in text:
                    sys.exit(f"{mid}: quote not found in {SOURCES[sid][1]}: {q!r}")
            row.update(current_value=value, current_unit=cunit, current_quote=" || ".join(quotes),
                       source_ids=f"{RR_ID};{sid}")
        out.append(row)
    return out


def _write_csv(name: str, rows: list[dict]) -> bytes:
    path = OUT / f"{name}.csv"
    with path.open("w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0]), lineterminator="\n")
        w.writeheader()
        w.writerows(rows)
    return path.read_bytes()


def _meta(name: str, title: str, description: str, source_id: str, url: str, notes: str) -> None:
    meta = {"dataset_id": name, "title": title, "description": description, "publisher": "HMRC", "source_url": url,
            "licence": "Open Government Licence v3.0", "retrieved_at": TODAY, "vintage": "June 2025 (Spring Statement 2025)",
            "file": f"curated/{name}.csv", "source_id": source_id, "is_placeholder": False, "notes": notes}
    (OUT / f"{name}.meta.json").write_text(json.dumps(meta, indent=2) + "\n", encoding="utf-8")


def main() -> None:
    ods = _download(RR_ODS, RR_FILE)
    rr = ready_reckoner(ods)
    ms = measures(rr)
    _write_csv("hmrc_ready_reckoner", rr)
    _write_csv("tax_measures", ms)
    sha = hashlib.sha256(ods).hexdigest()
    _meta("hmrc_ready_reckoner", "HMRC ready reckoner: direct effects of illustrative tax changes",
          "Every row of HMRC's June 2025 'Direct effects of illustrative tax changes' table, £m by fiscal year.",
          RR_ID, RR_URL,
          "Verbatim labels and values from the ODS table (Spring Statement 2025 basis). 'Neg' (negligible: above zero "
          "but rounding to zero) is stored as 0 with is_negligible=True. HMRC: direct effects of small illustrative "
          "changes, including some behavioural responses but no wider macroeconomic effects; larger changes need not "
          f"scale linearly. Sign conventions differ by row (see tax_measures.csv).\nRaw SHA256: {sha}")
    raw_hashes = {SOURCES[s][4]: hashlib.sha256((RAW / SOURCES[s][4]).read_bytes()).hexdigest()
                  for s in SOURCES if (RAW / SOURCES[s][4]).exists()}
    _meta("tax_measures", "Modelled tax and benefit measures",
          "Measures modelled from the HMRC ready reckoner: rows used, unit of change, sign convention, scope limit and "
          "the current rate verified by an exact quote on gov.uk.", RR_ID, RR_URL,
          "points_up/points_down list 'size=section::label(+...)' ready-reckoner rows (values summed) costed for a change "
          "of that size; sign_up/sign_down turn those £m into Exchequer revenue (+ = more revenue); an empty "
          "points_down mirrors the increase. max_change is the scope gate's hard limit in the measure's unit. "
          "current_value was verified on " + TODAY + " by the quotes in current_quote.\nRaw SHA256: "
          + "; ".join(f"{k}={v}" for k, v in sorted(raw_hashes.items())))
    # sources.csv: append missing rows
    path = OUT / "sources.csv"
    existing = list(csv.DictReader(path.open(encoding="utf-8")))
    have = {r["source_id"] for r in existing}
    with path.open("a", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(existing[0]), lineterminator="\n")
        for sid, (title, url, pub, ptype, _name) in SOURCES.items():
            if sid not in have:
                w.writerow({"source_id": sid, "title": title, "url": url, "publisher": pub, "publisher_type": ptype,
                            "published_date": "2025-06-24" if sid == RR_ID else "", "reliability_tier": 1})
    prov_path = OUT / "provenance.json"
    prov = json.loads(prov_path.read_text(encoding="utf-8"))
    for sid, (_t, url, _p, _pt, name) in SOURCES.items():
        if name in raw_hashes:
            prov[name] = {"url": RR_ODS if sid == RR_ID else url, "sha256": raw_hashes[name], "retrieved_at": TODAY}
    prov_path.write_text(json.dumps(prov, indent=2) + "\n", encoding="utf-8")
    print(f"{len(rr)} ready-reckoner values, {len(ms)} measures written")


if __name__ == "__main__":
    main()
