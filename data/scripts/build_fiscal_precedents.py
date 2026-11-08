"""Build the precedent library for every fiscal policy other than corporation tax. Corporation tax data is untouched.

Outputs under data/curated/ (each with a .meta.json):
- fiscal_topics.csv: one row per policy the product can analyse; `query_pattern` maps free text to a topic.
- fiscal_policy_changes.csv: the historical changes. `kind` says what a row is:
    rate_series: an implemented change, from an official table of rates (HMRC, DWP, GOV.UK);
    announced_measure: a measure announced at a fiscal event, from the OBR policy measures database;
    fiscal_event: the net tax, spending and borrowing effect of a whole fiscal event, from the same database.
- fiscal_costings.csv: the original Treasury scorecard costing of a change, by fiscal year. Years the OBR extrapolated
  with nominal GDP are shaded in its workbook and are left out.
- fiscal_outturns.csv: observed receipts, spending or borrowing by fiscal year, outturn years only.

Run from the repo root:  backend/.venv/Scripts/python data/scripts/build_fiscal_precedents.py
OBR and House of Commons Library files cannot be fetched by script: save them by hand under the names in
fiscal_sources.SOURCES in data/raw/. The build stops if a figure cannot be traced to its source.
"""
from __future__ import annotations

import csv
import hashlib
import json
import re
import warnings
from collections import defaultdict
from dataclasses import dataclass
from datetime import date
from pathlib import Path

import fiscal_sources as fs

warnings.simplefilter("ignore")  # openpyxl warns about page headers in the official workbooks
OUT = Path(__file__).resolve().parents[1] / "curated"
TODAY = date.today()
OBR, DATABANK, A1, A2, A4 = ("D-obr-policy-measures", "D-obr-databank-2026", "D-hmrc-table-a1", "D-hmrc-table-a2",
                             "D-hmrc-table-a4")
ABSTRACT, DWP, PESA, VAT_NOTE = "D-dwp-abstract-2025", "D-dwp-expenditure-2026", "D-hmt-pesa-2026-ch4", "D-commons-vat-sn00701"
LAST_OUTTURN = "2025-26"  # the databank's forecast starts at 2026-27 (its own note)
EXTRAPOLATED_FILL = "FFE1E9EE"  # the OBR workbook's "extended beyond the scorecard" shading


@dataclass(frozen=True)
class Topic:
    key: str
    label: str
    kind: str                # measure | other
    area: str                # tax | spending | overall
    query: str               # regex over the lower-cased request; ignored for measures, which the parser identifies
    heads: tuple[str, ...]   # OBR tax or spending heads, compared case-insensitively
    pattern: str = ""        # regex on the OBR measure description
    exclude: str = ""
    outturn: str = ""
    # +1 if a higher value of the policy raises revenue, -1 if it costs money (allowances, benefits)
    value_sign: int = 1
    any_head: bool = False   # match `pattern` in every head rather than within `heads`


T = Topic
IT, NIC, CGT, IHT = ("income tax",), ("nics",), ("capital gains tax",), ("inheritance tax",)
WELFARE = ("welfare inside cap", "welfare outside cap", "social security benefits")
TOPICS: tuple[Topic, ...] = (
    T("income_tax_basic_rate", "Income Tax basic rate", "measure", "tax", "", IT, r"basic rate|\bbasic\b.*\brate", r"relief", "income_tax"),
    T("income_tax_higher_rate", "Income Tax higher rate", "measure", "tax", "", IT, r"higher rate", r"relief|allowance", "income_tax"),
    T("income_tax_additional_rate", "Income Tax additional rate", "measure", "tax", "", IT, r"additional rate|\b50p\b|\b45p\b", r"relief", "income_tax"),
    T("income_tax_personal_allowance", "Income Tax Personal Allowance", "measure", "tax", "", IT,
      r"personal allowance|\bPA\b|increase (?:in|of) (?:married and single )?allowances?", r"blind|married couple|age allowance|age.related|older people", "income_tax", -1),
    T("nics_employee_main_rate", "Class 1 employee National Insurance", "measure", "tax", "", NIC, r"employee|primary (?:rate|threshold)|main rate", r"employer|share scheme|share option", "nics"),
    T("nics_employer_rate", "Class 1 employer National Insurance", "measure", "tax", "", NIC, r"employer|secondary", "", "nics"),
    T("nics_class4_main_rate", "Class 4 self-employed National Insurance", "measure", "tax", "", NIC, r"class 4|self.?employ", "", "nics"),
    T("cgt_lower_rate", "Capital Gains Tax lower rate", "measure", "tax", "", CGT, r"\brates?\b", r"relief", "cgt"),
    T("cgt_higher_rate", "Capital Gains Tax higher rate", "measure", "tax", "", CGT, r"\brates?\b", r"relief", "cgt"),
    T("inheritance_tax_rate", "Inheritance Tax", "measure", "tax", "", IHT, r"\brates?\b|threshold|nil.rate|band", "", "iht"),
    T("vat_standard_rate", "VAT standard rate", "measure", "tax", "", ("vat",),
      r"VAT rate|standard rate|main rate|unification of rates", r"flat rate|applying the standard|zero", "vat"),
    T("vat_reduced_rate", "VAT reduced rate", "measure", "tax", "", ("vat",), r"reduced rate|lower rate|\b5%", "", "vat"),
    T("ipt_standard_rate", "Insurance Premium Tax", "measure", "tax", "", ("insurance premium tax",), "", "", "ipt"),
    T("fuel_duty", "Fuel duty", "measure", "tax", "", ("fuel duty",), "", "", "fuel"),
    T("alcohol_duty", "Alcohol duties", "measure", "tax", "", ("alcohol duty",), "", "", "alcohol"),
    T("tobacco_duty", "Tobacco duties", "measure", "tax", "", ("tobacco duty",), "", "", "tobacco"),
    T("child_benefit", "Child Benefit", "measure", "spending", r"child benefit", (), r"child benefit", "", "child_benefit", -1, True),
    # Named policies with no forecast model. Order matters: the first matching query wins.
    T("devolved_income_tax", "Scottish and Welsh income tax", "other", "tax",
      r"(?:scot|wales|welsh|holyrood|senedd).*income tax|income tax.*(?:scot|wales|welsh)", IT, r"(?:scottish|welsh)\b.*income tax|income tax.*(?:scottish|welsh)\b", "", "income_tax"),
    T("council_tax", "Council Tax", "other", "tax", r"council[\s-]+tax", ("council tax", "high-value council tax surcharge"), "", "", "council_tax"),
    T("business_rates", "Business rates", "other", "tax", r"business[\s-]+rates", ("business rates",)),
    T("stamp_duty", "Stamp duty", "other", "tax", r"stamp[\s-]+duty|\bsdlt\b", ("stamp duty",), "", "", "stamp"),
    T("wealth_tax", "Wealth tax", "other", "tax", r"wealth[\s-]+tax", (), r"wealth tax|net wealth", "", "", 1, True),
    T("carbon_tax", "Carbon pricing", "other", "tax", r"carbon[\s-]+(?:tax|price|border)|climate change levy",
      ("climate change levy", "emissions trading scheme", "cbam"), "", "", "carbon"),
    T("digital_services_tax", "Digital services tax", "other", "tax", r"digital[\s-]+services[\s-]+tax", ("digital services tax",)),
    T("bank_levy", "Bank levy and surcharge", "other", "tax", r"bank[\s-]+(?:levy|surcharge)", ("bank levy", "bank surcharge"), "", "", "bank_levy"),
    T("energy_profits_levy", "Windfall taxes and the Energy Profits Levy", "other", "tax", r"windfall[\s-]+tax|energy[\s-]+profits[\s-]+levy",
      ("energy profits levy", "electricity generators levy"), "", "", "epl"),
    T("apprenticeship_levy", "Apprenticeship levy", "other", "tax", r"apprenticeship[\s-]+levy", ("apprenticeship levy",)),
    T("air_passenger_duty", "Air Passenger Duty", "other", "tax", r"air[\s-]+passenger[\s-]+duty|\bapd\b", ("air passenger duty",), "", "", "apd"),
    T("vehicle_excise_duty", "Vehicle Excise Duty", "other", "tax", r"vehicle[\s-]+excise[\s-]+duty|road[\s-]+tax|\bved\b", ("vehicle excise duty",), "", "", "ved"),
    T("landfill_tax", "Landfill Tax", "other", "tax", r"landfill[\s-]+tax", ("landfill tax",)),
    T("soft_drinks_levy", "Soft Drinks Industry Levy", "other", "tax", r"sugar[\s-]+tax|soft[\s-]+drinks", ("soft drinks levy",)),
    T("land_value_tax", "Land value tax", "other", "tax", r"land[\s-]+value[\s-]+tax", (), r"land value tax", "", "", 1, True),
    T("dividend_tax", "Dividend taxation", "other", "tax", r"dividend[\s-]+tax", IT, r"dividend", "", "income_tax"),
    T("plastic_packaging_tax", "Plastic Packaging Tax", "other", "tax", r"plastic[\s-]+packaging", ("plastic packaging tax",)),
    T("gambling_duty", "Gambling duties", "other", "tax", r"gambling|betting|gaming", ("betting", "statutory gaming levy")),
    T("tariffs", "Customs duties and tariffs", "other", "tax", r"tariffs?|customs", ("customs duty",)),
    T("tax_credits", "Tax credits", "other", "spending", r"tax[\s-]+credits?", ("tax credits",), "", "", "tax_credits", -1),
    T("universal_credit", "Universal Credit", "other", "spending", r"universal[\s-]+credit", (), r"universal credit", "", "universal_credit", -1, True),
    T("pension_credit", "Pension Credit", "other", "spending", r"pension[\s-]+credit", (), r"pension credit", "", "pension_credit", -1, True),
    T("state_pension", "State Pension and the triple lock", "other", "spending", r"state[\s-]+pension|triple[\s-]+lock", (),
      r"state pension|triple lock", "", "state_pension", -1, True),
    T("housing_benefit", "Housing Benefit", "other", "spending", r"housing[\s-]+benefit", (), r"housing benefit|local housing allowance|social rent", "", "housing_benefit", -1, True),
    T("winter_fuel", "Winter Fuel Payment", "other", "spending", r"winter[\s-]+fuel", (), r"winter fuel", "", "winter_fuel", -1, True),
    T("benefit_uprating", "Benefit cap, freeze and uprating", "other", "spending", r"benefits?[\s-]+(?:cap|freeze|uprating)", (),
      r"benefit cap|benefits? freeze|up-?rat|CPI indexation", "", "welfare", -1, True),
    T("pip", "Personal Independence Payment", "other", "spending", r"\bpip\b|personal[\s-]+independence", (), r"personal independence|\bPIP\b|disability living", "", "disability", -1, True),
    T("jobseekers_allowance", "Jobseeker's Allowance", "other", "spending", r"jobseeker", (), r"jobseeker|\bJSA\b", "", "unemployment", -1, True),
    T("carers_allowance", "Carer's Allowance", "other", "spending", r"carer", (), r"carer", "", "carers", -1, True),
    T("disability_benefits", "Disability benefits", "other", "spending", r"disability", (), r"disab|incapacity|employment and support", "", "disability", -1, True),
    T("welfare", "Welfare spending", "other", "spending", r"welfare|\bbenefits?\b", WELFARE, "", "", "welfare", -1),
    T("minimum_wage", "National Minimum and Living Wage", "other", "spending", r"(?:minimum|living)[\s-]+wage", (), r"^(?:national )?(?:minimum|living) wage", "", "", 1, True),
    T("public_sector_pay", "Public sector pay", "other", "spending", r"public[\s-]+sector[\s-]+pay", (), r"public sector pay|pay award|pay freeze", "", "", -1, True),
    T("nhs", "NHS and health spending", "other", "spending", r"\bnhs\b|health", (), r"\bNHS\b|health and social care|health service", r"levy", "health", -1, True),
    T("defence", "Defence spending", "other", "spending", r"defen[cs]e", (), r"defen[cs]e|armed forces", r"flood|export finance", "defence", -1, True),
    T("education", "Schools and education spending", "other", "spending", r"school|education", (), r"school|education|pupil premium|tuition", "", "education", -1, True),
    T("public_spending", "Public spending", "other", "spending", r"spending|funding|public[\s-]+investment", ("psce in rdel", "psgi in cdel"),
      r"spending review|spending round|capital spending|spending assumption|spending decisions|special reserve", "", "tme", -1),
    T("overall_fiscal", "Overall tax, spending and borrowing", "other", "overall", r".", (), "", "", "borrowing"),
)
BY_KEY = {t.key: t for t in TOPICS}


# ---- rate histories -------------------------------------------------------------------------------------------------

@dataclass
class Rate:
    effective: date
    value: float | None


@dataclass
class Series:
    key: str
    series: str
    unit: str
    source_id: str
    points: list[Rate]
    note: str


def _fy_date(text: str) -> date | None:
    """Tax-year tables: "1992 to 1993" -> 6 April 1992."""
    m = re.match(r"\s*(\d{4}) to \d{4}", text)
    return date(int(m.group(1)), 4, 6) if m else None


TAX_YEAR_NOTE = ("From the HMRC annual table: the date shown is the start of the tax year (6 April), and a change made "
                 "part-way through a year may not appear.")


def _income_tax() -> list[Series]:
    rows = fs.read_ods("hmrc_table_a2.ods")["TA2_Rates_of_IT"]
    head = next(r for r in rows if r[0].strip() == "Financial Years")
    if [c for c in head[1:11:2]] and not all("Band" in c for c in head[1:11:2]):
        raise SystemExit("HMRC Table A.2 layout changed")
    out = []
    for key, col in (("income_tax_basic_rate", 6), ("income_tax_higher_rate", 8), ("income_tax_additional_rate", 10)):
        points = [Rate(d, fs.number(r[col])) for r in rows if (d := _fy_date(r[0]))]
        out.append(Series(key, BY_KEY[key].label, "%", A2, points, TAX_YEAR_NOTE))
    allowances = fs.read_ods("hmrc_table_a1.ods")["TA1_IT_PA_and_Reliefs"]
    if "Personal" not in next(r for r in allowances if r[0].strip().startswith("Financial year"))[1]:
        raise SystemExit("HMRC Table A.1 layout changed")
    out.append(Series("income_tax_personal_allowance", "Personal Allowance (non-aged)", "£", A1,
                      [Rate(d, fs.number(r[1])) for r in allowances if (d := _fy_date(r[0]))], TAX_YEAR_NOTE))
    return out


def _nics() -> list[Series]:
    rows = fs.read_ods("hmrc_table_a4.ods")["TA4_NICS_MAIN_FEATURES"]
    years = next(r for r in rows if r[0].strip() == "NICS Class")
    wanted = (("nics_employee_main_rate", "Primary (employee) main contribution rate"),
              ("nics_employer_rate", "Secondary (employer) contribution rate"),
              ("nics_class4_main_rate", "Main contribution rate (LPL to UPL)"))
    out = []
    for key, label in wanted:
        row = next(r for r in rows if r[1].strip().startswith(label))
        points = []
        for year, cell in zip(years[2:], row[2:], strict=False):
            d, value = _fy_date(year), fs.number(cell)
            if d and value is not None:
                points.append(Rate(d, round(value * 100, 4) if value < 1 else value))
        out.append(Series(key, BY_KEY[key].label, "%", A4, points, TAX_YEAR_NOTE))
    return out


def _date_table(name: str, column: str, *, heading: str = "") -> list[Rate]:
    points = []
    for found, rows in fs.html_tables(name):
        if heading and heading not in found:
            continue
        head = rows[0]
        if column not in head:
            continue
        i = head.index(column)
        for r in rows[1:]:
            if len(r) > i and (d := fs.parse_date(r[0])):
                points.append(Rate(d, fs.number(r[i])))
    return points


def _petrol() -> list[Rate]:
    """The main petrol rate: ultra-low-sulphur petrol while that column exists (it was then the standard rate), else unleaded."""
    points = []
    for _h, rows in fs.html_tables("hmrc_oil_duty_history.html"):
        head = rows[0]
        if "Unleaded petrol" not in head:
            continue
        unleaded = head.index("Unleaded petrol")
        ulsp = head.index("Ultra low sulphur petrol") if "Ultra low sulphur petrol" in head else None
        for r in rows[1:]:
            if not (d := fs.parse_date(r[0])):
                continue
            value = fs.number(r[ulsp]) if ulsp is not None and len(r) > ulsp else None
            points.append(Rate(d, value if value is not None else fs.number(r[unleaded])))
    return points


def _duties() -> list[Series]:
    petrol = _petrol()
    spirits = (_date_table("hmrc_alcohol_duty_history.html", "Spirits", heading="Historic Alcohol Duty rates on spirits")
               + _date_table("hmrc_alcohol_duty_history.html", "Stronger than 22%", heading="Historic Alcohol Duty rates on spirits")
               + _date_table("hmrc_alcohol_duty_history.html", "Stronger than 22%", heading="Current Alcohol Duty Rates on spirits"))
    beer_band = "Over 3.4%, up to and including 8.4%"
    beer_col = next(c for _h, rows in fs.html_tables("hmrc_alcohol_duty_history.html")
                    if "Beer" in rows[0] for c in ["Beer"])
    beer = (_date_table("hmrc_alcohol_duty_history.html", beer_col, heading="Historic Alcohol Duty rates on beer")
            + _band_table("Historic Alcohol Duty rates on beer", beer_band)
            + _band_table("Current Alcohol Duty rates on beer", beer_band))
    return [
        Series("fuel_duty", "Petrol", "p/litre", "D-hmrc-oil-duty-history", petrol,
               "HMRC's main petrol duty rate: ultra-low-sulphur petrol while that rate existed, otherwise unleaded."),
        Series("alcohol_duty", "Spirits", "£/litre of pure alcohol", "D-hmrc-alcohol-duty-history", spirits,
               "Duty on spirits. From August 2023 this is the rate for drinks stronger than 22%."),
        Series("alcohol_duty", "Beer", "£/litre of pure alcohol", "D-hmrc-alcohol-duty-history", beer,
               "General beer duty. From August 2023 this is the rate for beer over 3.4% and up to 8.4%, non-draught."),
        Series("tobacco_duty", "Cigarettes (specific duty)", "£/1,000 sticks", "D-hmrc-tobacco-duty-history",
               _date_table("hmrc_tobacco_duty_history.html", "Specific £ per 1,000 sticks"), "The specific element of cigarette duty."),
        Series("ipt_standard_rate", "Standard rate", "%", "D-hmrc-ipt-history",
               _date_table("hmrc_ipt_history.html", "Standard rate (%)"), ""),
    ]


def _band_table(heading: str, band: str) -> list[Rate]:
    points = []
    for found, rows in fs.html_tables("hmrc_alcohol_duty_history.html"):
        if heading in found and any(band in c for c in rows[0]):
            i = next(n for n, c in enumerate(rows[0]) if band in c)
            points += [Rate(d, fs.number(r[i])) for r in rows[1:] if (d := fs.parse_date(r[0]))]
    return points


def _apd() -> list[Series]:
    points: list[Rate] = []
    for _h, rows in fs.html_tables("hmrc_apd_history.html"):
        head = rows[0]
        col = next((i for i, c in enumerate(head) if re.match(r"(Domestic Standard rate|Band A Standard rate|EEA Destinations Standard|Lower rate)", c)), None)
        if col is None:
            continue
        points += [Rate(d, fs.number(r[col])) for r in rows[1:] if len(r) > col and (d := fs.parse_date(r[0]))]
    return [Series("air_passenger_duty", "Shortest-distance standard rate", "£/passenger", "D-hmrc-apd-history", points,
                   "HMRC's lowest-distance standard-class rate; the band definitions changed in 2001, 2009 and 2023.")]


def _iht() -> list[Series]:
    for _h, rows in fs.html_tables("hmrc_iht_thresholds.html"):
        if rows[0][:3] == ["From", "To", "Threshold (nil rate band)"]:
            points = [Rate(d, fs.number(r[2])) for r in rows[1:] if (d := fs.parse_date(r[0]))]
            return [Series("inheritance_tax_rate", "Nil-rate band (threshold)", "£", "D-hmrc-iht-thresholds", points,
                           "A change in the tax-free threshold, not in the 40% rate.")]
    raise SystemExit("IHT threshold table not found")


def _minimum_wage() -> list[Series]:
    points = []
    months = {"April": 4, "October": 10}
    for _h, rows in fs.html_tables("govuk_minimum_wage.html"):
        if not rows[0][1:2] or "and over" not in rows[0][1]:
            continue
        for r in rows[1:]:
            m = re.match(r"(April|October) (\d{4})", r[0])
            if m:
                points.append(Rate(date(int(m.group(2)), months[m.group(1)], 1), fs.number(r[1])))
    return [Series("minimum_wage", "National Living Wage (top age band)", "£/hour", "D-govuk-minimum-wage", points,
                   "The rate for the oldest age band shown by GOV.UK; that band's starting age has fallen over time.")]


def _benefit(sheet: str, table: str, key: str, series: str, unit: str) -> Series:
    rows = fs.read_ods("dwp_abstract_2025.ods")[sheet]
    start = next(i for i, r in enumerate(rows) if r[0].startswith(table + ":") and i > 4)
    points = []
    for r in rows[start + 2:]:
        if r[0].startswith("Table "):
            break
        if d := fs.parse_date(r[0]):
            points.append(Rate(d, fs.number(r[1])))
    return Series(key, series, unit, ABSTRACT, points, "DWP's up-rating history, in cash terms at each date.")


def _benefits() -> list[Series]:
    return [_benefit("Child_Benefit", "Table 39", "child_benefit", "One-child family", "£/week"),
            _benefit("Basic_State_Pension", "Table 6", "state_pension", "Basic State Pension (single)", "£/week"),
            _benefit("New_State_Pension", "Table 8", "state_pension", "New State Pension (full rate)", "£/week"),
            _benefit("Pension_Credit", "Table 9", "pension_credit", "Standard minimum guarantee (single)", "£/week"),
            _benefit("Universal_Credit", "Table 16", "universal_credit", "Standard allowance (single, 25 or over)", "£/month"),
            _benefit("JSA_and_UB", "Table 19", "jobseekers_allowance", "Unemployment Benefit / JSA (contributory)", "£/week")]


# VAT: no official table exists. Each row is (effective date, old, new, note, source, exact quote the source must contain).
VAT_CHANGES = (
    (date(1974, 7, 1), 10.0, 8.0, "The source gives the month only, so the day shown is the 1st.", VAT_NOTE,
     "reduce the standard rate of VAT from 10 per cent to 8 per cent"),
    (date(1979, 6, 1), 8.0, 15.0, "The source gives the month only, so the day shown is the 1st.", VAT_NOTE,
     "The standard rate was maintained at 8% until June 1979, when it was increased to 15%."),
    (date(2008, 12, 1), 17.5, 15.0, "A temporary cut as part of the 2008 fiscal stimulus.", VAT_NOTE,
     "will reduce the standard rate of VAT from 17.5 per cent to 15 per cent from 1 December 2008"),
    (date(2010, 1, 1), 15.0, 17.5, "The planned end of the temporary cut.", VAT_NOTE,
     "The rate will remain at 15 per cent until 1 January 2010 when it will revert to 17.5 per"),
    (date(2011, 1, 4), 17.5, 20.0, "", VAT_NOTE, "the standard rate would be increased to 20% from 4 January 2011"),
)
# Budget 1991 raised the rate to 17.5%: the OBR row gives the new rate and its first costed year, and the old rate is the
# 15% set in 1979, which held until then. The date is the start of that fiscal year.
VAT_1991 = (date(1991, 4, 1), 15.0, 17.5, "Budget 1991", "VAT rate increase to 17.5%")


def _verify_vat() -> None:
    text = fs.pdf_text("commons_sn00701.pdf")
    for _d, _o, _n, _note, _sid, quote in VAT_CHANGES:
        if quote not in text:
            raise SystemExit(f"VAT quote not found in the Commons Library briefing: {quote!r}")


# ---- OBR policy measures --------------------------------------------------------------------------------------------

@dataclass
class ObrRow:
    event: str
    description: str
    head: str
    costed: dict[str, float]  # fiscal year -> £m, scorecard years only


def _load_obr(sheet: str) -> list[ObrRow]:
    ws = fs.workbook("obr_policy_measures.xlsx", read_only=False)[sheet]
    rows = list(ws.iter_rows())
    header = [c.value for c in rows[2]]
    if header[1:4] != ["Event", "Measure description", "Tax head" if sheet.startswith("Tax") else "Spending head"]:
        raise SystemExit(f"OBR {sheet} layout changed: {header[:5]}")
    out = []
    for row in rows[3:]:
        event, description, head = row[1].value, row[2].value, row[3].value
        if not event or not description:
            continue
        costed = {}
        for year, cell in zip(header[4:], row[4:], strict=False):
            if not year or not isinstance(cell.value, int | float):
                continue
            extended = cell.fill.fill_type and cell.fill.fgColor.type == "rgb" and cell.fill.fgColor.rgb == EXTRAPOLATED_FILL
            if not extended:
                costed[str(year)] = float(cell.value)
        out.append(ObrRow(str(event).strip(), " ".join(str(description).split()), str(head or "").strip().lower(), costed))
    return out


def _borrowing_summary() -> dict[str, dict[str, dict[str, float]]]:
    """{event: {"Tax"|"Spend"|"Borrowing": {fiscal year: £m}}}, scorecard years only."""
    ws = fs.workbook("obr_policy_measures.xlsx", read_only=False)["Borrowing Summary"]
    rows = list(ws.iter_rows())
    header = [c.value for c in rows[2]]
    out: dict[str, dict[str, dict[str, float]]] = {}
    event = ""
    for row in rows[3:]:
        event = str(row[1].value).strip() if row[1].value else event
        category = row[2].value
        if category not in ("Tax", "Spend", "Borrowing"):
            continue
        values = {}
        for year, cell in zip(header[3:], row[3:], strict=False):
            if year and isinstance(cell.value, int | float) and not (
                    cell.fill.fill_type and cell.fill.fgColor.type == "rgb" and cell.fill.fgColor.rgb == EXTRAPOLATED_FILL):
                values[str(year)] = float(cell.value)
        out.setdefault(event, {})[str(category)] = values
    return out


def _event_year(event: str) -> int | None:
    m = re.search(r"\b((?:19|20)\d\d)\b", event)
    return int(m.group(1)) if m else None


# A measure can touch several heads ("Stamp Duty ..." has a small effect on capital gains tax). A row filed under one head
# but named after another tax belongs to that other tax.
_NAMED_TAXES = (("income_tax", r"income tax|dividend|property income|savings income"), ("nics", r"national insurance|\bnics?\b"), ("cgt", r"capital gains|\bcgt\b"),
                ("iht", r"inheritance tax"), ("vat", r"\bvat\b"), ("stamp", r"stamp duty|\bsdlt\b"), ("fuel", r"fuel dut"),
                ("alcohol", r"alcohol|beer|cider|wine|spirits dut"), ("tobacco", r"tobacco"), ("ct", r"corporation tax"),
                ("ved", r"vehicle excise|\bved\b"), ("ipt", r"insurance premium"), ("apd", r"air passenger"),
                ("business_rates", r"business rates"), ("soft_drinks", r"soft drinks"), ("company_car", r"van benefit|company car"))
_TOPIC_FAMILY = {"dividend_tax": "income_tax", "devolved_income_tax": "income_tax", "stamp_duty": "stamp"}


def _named_other_tax(topic: Topic, description: str) -> bool:
    family = _TOPIC_FAMILY.get(topic.key, topic.outturn)
    prefix = description.split(":", 1)[0].lower() if ":" in description else ""
    return any(name != family and re.search(pattern, prefix) for name, pattern in _NAMED_TAXES)


def _topic_rows(topic: Topic, rows: list[ObrRow]) -> dict[tuple[str, str], ObrRow]:
    """Rows for a topic, merged across heads by (event, description) so one measure appears once."""
    found: dict[tuple[str, str], ObrRow] = {}
    pattern = re.compile(topic.pattern, re.I) if topic.pattern else None
    exclude = re.compile(topic.exclude, re.I) if topic.exclude else None
    for r in rows:
        if not topic.any_head and r.head not in topic.heads:
            continue
        if pattern and not pattern.search(r.description) or exclude and exclude.search(r.description):
            continue
        if not any(abs(v) > 0 for v in r.costed.values()) or _named_other_tax(topic, r.description):
            continue
        k = (r.event, r.description)
        if k in found:
            merged = dict(found[k].costed)
            for y, v in r.costed.items():
                merged[y] = merged.get(y, 0.0) + v
            found[k] = ObrRow(r.event, r.description, found[k].head, merged)
        else:
            found[k] = ObrRow(r.event, r.description, r.head, dict(r.costed))
    return {k: r for k, r in found.items() if any(abs(v) > 0 for v in r.costed.values())}  # offsetting heads can net to zero


def _first_year(row: ObrRow) -> str:
    return min(y for y, v in row.costed.items() if abs(v) > 0)


def _sign(row: ObrRow) -> int:
    v = row.costed[_first_year(row)]
    return (v > 0) - (v < 0)


_FROM_TO = re.compile(r"from\s+(\d+(?:\.\d+)?)\s*%\s+to\s+(\d+(?:\.\d+)?)\s*%", re.I)


def _clean(text: str) -> str:
    return text.replace(";", ",")


def _others(row: ObrRow, rows: list[ObrRow]) -> str:
    """Up to three of the largest other measures on the same tax head at the same event."""
    same = [r for r in rows if r.event == row.event and r.head == row.head and r.description != row.description and r.costed]
    same.sort(key=lambda r: -max((abs(v) for v in r.costed.values()), default=0))
    return "; ".join(_clean(r.description) for r in same[:3])


# ---- outturns --------------------------------------------------------------------------------------------------------

def _databank() -> tuple[dict[str, dict[str, float]], dict[str, float]]:
    wb = fs.workbook("obr_databank_oct_2026.xlsx")
    receipts = list(next(ws for ws in wb.worksheets if ws.title.startswith("Receipts")).iter_rows(values_only=True))
    head = [str(c or "") for c in receipts[3]]

    def col(prefix: str) -> int:
        return next(i for i, h in enumerate(head) if h.startswith(prefix))

    groups = {"vat": ["VAT (net"], "fuel": ["Fuel duties"], "stamp": ["Stamp duty land tax", "Stamp taxes on shares"],
              "tobacco": ["Tobacco duties"], "alcohol": ["Alcohol duties"], "ved": ["Vehicle excise duties"],
              "apd": ["Air passenger duty"], "ipt": ["Insurance premium tax"], "carbon": ["Climate change levy"],
              "income_tax": ["Pay as you", "Self assessed", "Other income tax"], "cgt": ["Capital gains tax"],
              "epl": ["Energy profits levy"], "bank_levy": ["Bank levy"], "iht": ["Inheritance tax"],
              "nics": ["National insurance"], "council_tax": ["Council tax"]}
    series: dict[str, dict[str, float]] = defaultdict(dict)
    for r in receipts[5:]:
        fy = str(r[1] or "")
        if not re.fullmatch(r"\d{4}-\d{2}", fy) or fy > LAST_OUTTURN:
            continue
        for key, prefixes in groups.items():
            values = [r[col(p)] for p in prefixes]
            if all(isinstance(v, int | float) for v in values) and sum(values) != 0:  # zero means the tax did not exist yet
                series[key][fy] = sum(values)
    aggregates = list(next(ws for ws in wb.worksheets if ws.title.startswith("Aggregates") and "bn" in ws.title).iter_rows(values_only=True))
    labels = [str(c or "") for c in aggregates[3]]
    tme, psnb = labels.index("Total managed expenditure"), labels.index("Public sector net borrowing")
    gdp = next(i for i, h in enumerate(labels) if h.startswith("Nominal GDP"))
    gdp_values: dict[str, float] = {}
    for r in aggregates:
        fy = str(r[1] or "")
        if re.fullmatch(r"\d{4}-\d{2}", fy) and fy <= LAST_OUTTURN:
            if isinstance(r[tme], int | float):
                series["tme"][fy] = r[tme]
            if isinstance(r[psnb], int | float):
                series["borrowing"][fy] = r[psnb]
            if isinstance(r[gdp], int | float):
                gdp_values[fy] = r[gdp]
    return dict(series), gdp_values


def _dwp() -> dict[str, dict[str, float]]:
    wb = fs.workbook("dwp_expenditure_2026.xlsx")
    wanted = {"state_pension": ("State Pension", "Total"), "pension_credit": ("Pension Credit", "Total Pension Credit"),
              "housing_benefit": ("Housing benefits", "Total"), "carers": ("Carers Allowance", "Total"),
              "disability": ("Disability benefits", "Total"), "unemployment": ("Unemployment benefits", "Total"),
              "universal_credit": ("Universal Credit and equivalent", "Total UC and equivalents"),
              "child_benefit": ("Non-DWP Welfare", "Child Benefit, One Parent Benefit"),
              "tax_credits": ("Non-DWP Welfare", "Personal tax credits"),
              "winter_fuel": ("Table 1a", "Winter Fuel Payments")}
    out: dict[str, dict[str, float]] = {}
    for key, (sheet, label) in wanted.items():
        rows = list(wb[sheet].iter_rows(values_only=True))
        years_at = next(i for i, r in enumerate(rows) if any(str(c or "") == "1948/49" for c in r))
        years, status = rows[years_at], rows[years_at + 1]
        row = next(r for r in rows[years_at + 2:] if str(r[1] or "").strip().startswith(label))
        series = {}
        for y, st, v in zip(years, status, row, strict=False):
            m = re.fullmatch(r"(\d{4})/(\d{2})", str(y or ""))
            if m and st == "Outturn" and isinstance(v, int | float) and v != 0:
                series[f"{m.group(1)}-{m.group(2)}"] = v / 1000.0
        if not series:
            raise SystemExit(f"No outturn for {key} in DWP sheet {sheet}")
        out[key] = series
    return out


def _pesa() -> dict[str, dict[str, float]]:
    rows = list(fs.workbook("hmt_pesa_2026_ch4.xlsx")["4_2"].iter_rows(values_only=True))
    years_at = next(i for i, r in enumerate(rows) if "2003-04" in [str(c) for c in r])
    years = rows[years_at]
    out: dict[str, dict[str, float]] = {}
    for key, label in (("defence", "2. Defence"), ("health", "7. Health"), ("education", "9. Education")):
        row = next(r for r in rows if str(r[0] or "").startswith(label))
        out[key] = {str(y): float(v) for y, v in zip(years, row, strict=False)
                    if re.fullmatch(r"\d{4}-\d{2}", str(y or "")) and isinstance(v, int | float)}
    return out


# ---- assemble --------------------------------------------------------------------------------------------------------

def _implemented_changes(series: Series) -> list[tuple[date, float | None, float]]:
    """Consecutive distinct values, oldest first. Future dates are left out."""
    best: dict[date, Rate] = {}
    for p in series.points:
        if p.effective <= TODAY:
            best[p.effective] = p
    ordered = [best[d] for d in sorted(best) if best[d].value is not None]
    out: list[tuple[date, float | None, float]] = []
    for i, point in enumerate(ordered):
        old = ordered[i - 1].value if i else None
        if i and old != point.value:
            out.append((point.effective, old, point.value))  # type: ignore[arg-type]
    return out


# Benefit and wage rates change by annual up-rating, which is not itemised as one measure, so nothing is linked to them.
NO_COSTING_LINK = {"child_benefit", "state_pension", "pension_credit", "universal_credit", "jobseekers_allowance", "minimum_wage",
                   "inheritance_tax_rate"}
_LATE_YEAR_EVENT = re.compile(r"autumn|pre-budget|\bpbr\b|#2|spending review", re.I)


# Plain-named Budgets held in the autumn; every other plain "Budget YYYY" was a spring Budget.
_AUTUMN_BUDGET_YEARS = {1994, 1995, 1996, 2018}
DUTY_TOPICS = {"fuel_duty", "alcohol_duty", "tobacco_duty"}
_DUTY_RATE_MEASURE = re.compile(r"dut(?:y|ies)|\brates?\b|revalor|escalator|increase|freeze", re.I)
_DUTY_OTHER_MEASURE = re.compile(r"scheme|relief|drawback|small brewer|draught|compliance|fraud|strategy|minimum excise|stamp|"
                                 r"rebate|enforcement|red diesel|biofuel|road fuel gas|\bleaded petrol|minor oils", re.I)
MIN_LINKED_COSTING_GBP_M = 20.0  # smaller rows are side measures, not the costing of a headline rate change


def _other_product(series: str, description: str) -> bool:
    """A measure named after another product does not cost this duty series ("Increase in beer duty" and spirits)."""
    text = description.lower()
    if series == "Spirits":
        return bool(re.search(r"beer|cider|wine", text)) and "spirit" not in text and "alcohol" not in text
    if series == "Beer":
        return bool(re.search(r"spirit|cider|wine", text)) and "beer" not in text and "alcohol" not in text
    if series.startswith("Cigarettes"):
        return "hand" in text and "cigarette" not in text
    return False


def _event_can_precede(event: str, effective: date, *, duty: bool) -> bool:
    """Whether the fiscal event, known only by name, was held before the change. Duty changes usually start on Budget day."""
    year = _event_year(event)
    late = bool(_LATE_YEAR_EVENT.search(event)) or year in _AUTUMN_BUDGET_YEARS
    if year == effective.year:
        return late == (effective.month >= 10) or (not late and effective.month < 10)
    if year == effective.year - 1:
        if duty:  # a duty change usually starts on Budget day, so only a late-year event can precede one early next year
            return late and effective.month < 4
        return late if effective.month < 4 else True
    return False


def _attach(topic: Topic, series: str, rows: dict[tuple[str, str], ObrRow], effective: date, old: float | None, new: float
            ) -> ObrRow | None:
    """The one OBR measure that costs this change, or None if it cannot be identified with certainty."""
    if topic.key in NO_COSTING_LINK:
        return None
    duty = topic.key in DUTY_TOPICS
    start = effective.year if effective.month >= 4 else effective.year - 1
    allowed_years = {f"{start}-{str(start + 1)[-2:]}"}
    if effective.month < 4:  # a Budget-day change in March is first costed in the fiscal year that starts next
        allowed_years.add(f"{start + 1}-{str(start + 2)[-2:]}")
    expected = ((new > (old or 0)) - (new < (old or 0))) * topic.value_sign
    found = []
    for row in rows.values():
        if not _event_can_precede(row.event, effective, duty=duty) or _first_year(row) not in allowed_years or _sign(row) != expected:
            continue
        if max(abs(v) for v in row.costed.values()) < MIN_LINKED_COSTING_GBP_M:
            continue
        if duty and (not _DUTY_RATE_MEASURE.search(row.description) or _DUTY_OTHER_MEASURE.search(row.description)
                     or _other_product(series, row.description)):
            continue
        found.append(row)
    return found[0] if len(found) == 1 else None


def _fy_of(row_year: str) -> date:
    return date(int(row_year[:4]), 4, 1)


def main() -> None:
    hashes = fs.fetch_all()
    _verify_vat()
    tax, spend = _load_obr("Tax Measures"), _load_obr("Spending Measures")
    all_rows = tax + spend
    summary = _borrowing_summary()
    outturns, gdp = _databank()
    outturns.update(_dwp())
    outturns.update(_pesa())
    # One unbroken ONS series per tax where it goes further back than the databank's 1999-00 start.
    for key, name in (("income_tax", "ons_income_tax_cash.csv"), ("vat", "ons_vat_cash.csv"), ("nics", "ons_nics_cash.csv"),
                      ("fuel", "ons_fuel_duty.csv"), ("tobacco", "ons_tobacco_duty.csv"), ("alcohol", "ons_alcohol_duty.csv")):
        outturns[key] = {fy: v for fy, v in fs.ons_fiscal_years(name).items() if fy <= LAST_OUTTURN}
    outturns.setdefault("welfare", {})
    wb = fs.workbook("dwp_expenditure_2026.xlsx")
    rows = list(wb["UK welfare "].iter_rows(values_only=True))
    years_at = next(i for i, r in enumerate(rows) if any(re.fullmatch(r"\d{4}/\d{2}", str(c or "")) for c in r))
    total = next(r for r in rows[years_at + 1:] if str(r[1] or "").strip() == "Total")  # this sheet is already in £bn
    status_row = next(r for r in rows if "Outturn" in [str(c) for c in r])
    for y, st, v in zip(rows[years_at], status_row, total, strict=False):
        m = re.fullmatch(r"(\d{4})/(\d{2})", str(y or ""))
        if m and st == "Outturn" and isinstance(v, int | float) and v:
            outturns["welfare"][f"{m.group(1)}-{m.group(2)}"] = v

    series_list = _income_tax() + _nics() + _duties() + _apd() + _iht() + _minimum_wage() + _benefits()
    changes: list[dict] = []
    costings: list[dict] = []
    counts: dict[str, dict[str, int]] = {t.key: {"rate_series": 0, "announced_measure": 0, "fiscal_event": 0} for t in TOPICS}
    used: dict[str, set[tuple[str, str]]] = defaultdict(set)
    linked: dict[str, set[tuple[str, str, str]]] = defaultdict(set)

    def add_costing(change_id: str, row: ObrRow) -> None:
        for fy in sorted(row.costed):
            costings.append({"change_id": change_id, "costing_body": "HMT", "fiscal_event": row.event, "fiscal_year": fy,
                             "value_gbp_bn": round(row.costed[fy] / 1000.0, 6), "includes_behavioural": "", "source_id": OBR})

    def add_rate(topic: Topic, label: str, unit: str, source: str, effective: date, old: float | None, new: float,
                 note: str, topic_rows: dict[tuple[str, str], ObrRow]) -> None:
        slug = re.sub(r"[^a-z0-9]+", "-", label.lower()).strip("-")
        cid = f"{topic.key}-{slug}-{effective.isoformat()}".upper().replace("_", "-")
        row = _attach(topic, label, topic_rows, effective, old, new)
        if row is not None and (label, row.event, row.description) in linked[topic.key]:
            row = None  # one measure costs one change in a series: a later step of the same package is not costed again
        if row is not None:
            linked[topic.key].add((label, row.event, row.description))
            used[topic.key].add((row.event, row.description))
            add_costing(cid, row)
        changes.append({"change_id": cid, "policy_key": topic.key, "series": label, "kind": "rate_series", "value_unit": unit,
                        "announced_date": "", "fiscal_event": row.event if row else "", "effective_date": effective.isoformat(),
                        "old_value": "" if old is None else old, "new_value": new,
                        "other_measures": _others(row, all_rows) if row else "", "reversed": False, "notes": note,
                        "source_ids": "; ".join(dict.fromkeys([source] + ([OBR] if row else [])))})
        counts[topic.key]["rate_series"] += 1

    topic_rows = {t.key: _topic_rows(t, all_rows) for t in TOPICS}
    implemented: dict[str, set[tuple[float | None, float]]] = defaultdict(set)
    for s in series_list:
        topic = BY_KEY[s.key]
        for effective, old, new in _implemented_changes(s):
            add_rate(topic, s.series, s.unit, s.source_id, effective, old, new, s.note, topic_rows[s.key])
            implemented[s.key].add((old, new))

    vat = BY_KEY["vat_standard_rate"]
    for effective, old, new, note, sid, _quote in VAT_CHANGES:
        add_rate(vat, "Standard rate", "%", sid, effective, old, new, note, topic_rows[vat.key])
    effective, old, new, event, description = VAT_1991
    row_1991 = topic_rows[vat.key].get((event, description))
    if row_1991 is None:
        raise SystemExit("The OBR row for the 1991 VAT rise was not found")
    add_rate(vat, "Standard rate", "%", OBR, effective, old, new,
             "The OBR measure gives the new rate. The 15% old rate was set in 1979 and the date is the start of the first "
             "costed fiscal year.", topic_rows[vat.key])

    for topic in TOPICS:
        if topic.key == "overall_fiscal":
            continue
        for k, row in sorted(topic_rows[topic.key].items(), key=lambda kv: kv[0]):
            if k in used[topic.key]:
                continue
            m = _FROM_TO.search(row.description)
            first = _first_year(row)
            digest = re.sub(r"[^A-Z0-9]+", "-", f"{row.event}-{row.description[:40]}".upper()).strip("-")
            unique = hashlib.sha256(f"{row.event}|{row.description}".encode()).hexdigest()[:8].upper()
            cid = f"OBR-{topic.key.upper().replace('_', '-')}-{digest}-{unique}"
            note = ("Announced at this fiscal event. The OBR database records the original costing; it does not show whether "
                    "the measure was later changed or reversed. The date shown is the start of the first costed fiscal year, "
                    "not the legal start date.")
            reverse = False
            checked = "income_tax_basic_rate" if topic.key == "devolved_income_tax" else topic.key
            if m and checked in implemented and (float(m.group(1)), float(m.group(2))) not in implemented[checked]:
                reverse = True
                note += " The official rate table shows no such change, so it did not take effect."
            changes.append({"change_id": cid, "policy_key": topic.key, "series": row.description, "kind": "announced_measure",
                            "value_unit": "%" if m else "", "announced_date": "", "fiscal_event": row.event,
                            "effective_date": _fy_of(first).isoformat(), "old_value": m.group(1) if m else "",
                            "new_value": m.group(2) if m else "", "other_measures": _others(row, all_rows), "reversed": reverse,
                            "notes": note, "source_ids": OBR})
            add_costing(cid, row)
            counts[topic.key]["announced_measure"] += 1

    overall = BY_KEY["overall_fiscal"]
    for event, parts in summary.items():
        if "Borrowing" not in parts or not any(abs(v) > 0 for v in parts["Borrowing"].values()):
            continue
        row = ObrRow(event, f"Net effect of all measures at {event}", "", parts["Borrowing"])
        first = _first_year(row)
        tax_part, spend_part = parts.get("Tax", {}), parts.get("Spend", {})
        cid = f"OBR-OVERALL-{re.sub(r'[^A-Z0-9]+', '-', event.upper()).strip('-')}"
        note = (f"The combined direct effect of every measure at {event}. In its first costed year ({first}) tax measures "
                f"contributed £{tax_part.get(first, 0) / 1000:.2f}bn and spending measures £{spend_part.get(first, 0) / 1000:.2f}bn "
                "to the Exchequer. A positive number reduces borrowing.")
        changes.append({"change_id": cid, "policy_key": overall.key, "series": row.description, "kind": "fiscal_event",
                        "value_unit": "", "announced_date": "", "fiscal_event": event, "effective_date": _fy_of(first).isoformat(),
                        "old_value": "", "new_value": "", "other_measures": "", "reversed": False, "notes": note, "source_ids": OBR})
        add_costing(cid, row)
        counts[overall.key]["fiscal_event"] += 1

    # outturn rows
    outturn_meta = {
        "income_tax": ("Income Tax receipts (cash)", "receipts", "D-ons-income-tax-cash"),
        "nics": ("National Insurance receipts (cash)", "receipts", "D-ons-nics-cash"),
        "cgt": ("Capital Gains Tax receipts", "receipts", DATABANK), "iht": ("Inheritance Tax receipts", "receipts", DATABANK),
        "vat": ("VAT receipts (cash)", "receipts", "D-ons-vat-cash"), "ipt": ("Insurance Premium Tax receipts", "receipts", DATABANK),
        "fuel": ("Fuel duty receipts", "receipts", "D-ons-fuel-duty"), "alcohol": ("Alcohol duty receipts", "receipts", "D-ons-alcohol-duty"),
        "tobacco": ("Tobacco duty receipts", "receipts", "D-ons-tobacco-duty"), "stamp": ("Stamp duty receipts (land and shares)", "receipts", DATABANK),
        "ved": ("Vehicle Excise Duty receipts", "receipts", DATABANK), "apd": ("Air Passenger Duty receipts", "receipts", DATABANK),
        "carbon": ("Climate change levy and carbon price floor receipts", "receipts", DATABANK), "epl": ("Energy Profits Levy receipts", "receipts", DATABANK),
        "bank_levy": ("Bank levy receipts", "receipts", DATABANK), "council_tax": ("Council Tax receipts", "receipts", DATABANK),
        "tme": ("Total managed expenditure", "spending", DATABANK), "borrowing": ("Public sector net borrowing", "borrowing", DATABANK),
        "state_pension": ("State Pension spending", "spending", DWP), "pension_credit": ("Pension Credit spending", "spending", DWP),
        "housing_benefit": ("Housing benefit spending", "spending", DWP), "carers": ("Carer's Allowance spending", "spending", DWP),
        "disability": ("Disability benefit spending", "spending", DWP), "unemployment": ("Unemployment benefit spending", "spending", DWP),
        "universal_credit": ("Universal Credit and equivalents spending", "spending", DWP), "child_benefit": ("Child Benefit spending", "spending", DWP),
        "tax_credits": ("Personal tax credits spending", "spending", DWP), "winter_fuel": ("Winter Fuel Payments spending", "spending", DWP),
        "welfare": ("UK welfare spending", "spending", DWP), "defence": ("Defence spending", "spending", PESA),
        "health": ("Health spending", "spending", PESA), "education": ("Education spending", "spending", PESA),
    }
    outturn_rows = [{"outturn_id": key, "label": outturn_meta[key][0], "kind": outturn_meta[key][1], "fiscal_year": fy,
                     "value_gbp_bn": round(value, 6), "pct_gdp": round(100 * value / gdp[fy], 6) if gdp.get(fy) else "",
                     "source_id": outturn_meta[key][2]}
                    for key in sorted(outturns) for fy, value in sorted(outturns[key].items())]

    topics_out = [{"policy_key": t.key, "label": t.label, "kind": t.kind, "area": t.area, "value_sign": t.value_sign,
                   "query_pattern": t.query, "outturn_id": t.outturn,
                   "rate_series": counts[t.key]["rate_series"], "announced_measures": counts[t.key]["announced_measure"],
                   "fiscal_events": counts[t.key]["fiscal_event"]} for t in TOPICS]

    def write(name: str, rows_out: list[dict]) -> None:
        with (OUT / f"{name}.csv").open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=list(rows_out[0]), lineterminator="\n")
            writer.writeheader()
            writer.writerows(rows_out)

    write("fiscal_topics", topics_out)
    write("fiscal_policy_changes", sorted(changes, key=lambda c: (c["policy_key"], c["effective_date"], c["change_id"])))
    write("fiscal_costings", costings)
    write("fiscal_outturns", outturn_rows)

    descriptions = {
        "fiscal_topics": ("Fiscal policy topics", "Every policy the product can analyse, with counts of its precedents.",
                          "Curated topic list. The counts are computed by the build, so zero means no measure was found."),
        "fiscal_policy_changes": ("Fiscal policy changes", "Historical UK tax, benefit and spending changes other than corporation tax.",
                                  "rate_series rows are implemented changes from official rate tables. announced_measure rows come from the "
                                  "OBR policy measures database and may later have been changed. VAT standard-rate rows are verified by exact "
                                  "quote from House of Commons Library SN00701; the old rate of the 1991 rise is the rate set in 1979."),
        "fiscal_costings": ("Fiscal policy costings", "Original Treasury scorecard costings, positive means revenue gained.",
                            "Copied from the OBR policy measures database, £m / 1000. Years the OBR extrapolated with nominal GDP are excluded. "
                            "A costing is linked to a rate change only when exactly one measure matches its event, first year and sign. "
                            "Whether a costing includes behaviour is not stated, so it is blank, not guessed."),
        "fiscal_outturns": ("Fiscal outturns", "Observed receipts, spending and borrowing by fiscal year.",
                            f"Outturn only, to {LAST_OUTTURN}. ONS cash series start in 1967-68 for Income Tax, 1973-74 for VAT and 1978-79 for NICs; "
                            "fuel, alcohol and tobacco ONS series start in 1997-98; other OBR databank receipts start in 1999-00; "
                            "PESA function spending starts in 2003-04. "
                            "Observed totals include every cause, not only the policy they sit beside."),
    }
    obr_meta = fs.SOURCES[OBR]
    for name, (title, description, notes) in descriptions.items():
        meta = {"dataset_id": name, "title": title, "description": description, "publisher": "OBR, HMRC, DWP, HM Treasury",
                "source_url": obr_meta[1], "licence": "Open Government Licence v3.0", "retrieved_at": TODAY.isoformat(),
                "vintage": "Sources current at build date", "file": f"curated/{name}.csv", "source_id": OBR, "is_placeholder": False,
                "notes": notes}
        (OUT / f"{name}.meta.json").write_text(json.dumps(meta, indent=2) + "\n", encoding="utf-8")

    path = OUT / "sources.csv"
    with path.open(encoding="utf-8", newline="") as handle:
        existing = list(csv.DictReader(handle))
        fields = list(existing[0])
    known = {r["source_id"] for r in existing}
    for sid, (title, url, publisher, kind, _name, _download) in fs.SOURCES.items():
        if sid not in known:
            existing.append(dict(source_id=sid, title=title, url=url, publisher=publisher, publisher_type=kind, published_date="",
                                 reliability_tier=1))
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        writer.writerows(existing)

    prov_path = OUT / "provenance.json"
    provenance = json.loads(prov_path.read_text(encoding="utf-8"))
    for _title, url, _publisher, _kind, name, download in fs.SOURCES.values():
        provenance[name] = {"url": download or url, "sha256": hashes[name], "retrieved_at": TODAY.isoformat()}
    prov_path.write_text(json.dumps(provenance, indent=2) + "\n", encoding="utf-8")

    print(f"{len(changes)} changes, {len(costings)} costings, {len(outturn_rows)} outturn rows")
    for t in topics_out:
        print(f"{t['policy_key']:32} rate={t['rate_series']:3} announced={t['announced_measures']:4} events={t['fiscal_events']:3} outturn={t['outturn_id']}")


if __name__ == "__main__":
    main()
