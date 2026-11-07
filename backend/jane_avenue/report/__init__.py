"""Report generation. Owner: agent-9."""
from .generator import generate_report, key_figures
from .template import build_template_report, fmt_date, fmt_gbp_bn, fmt_pct, fmt_pp, is_forecast_withheld

__all__ = [
    "build_template_report",
    "fmt_date",
    "fmt_gbp_bn",
    "fmt_pct",
    "fmt_pp",
    "generate_report",
    "is_forecast_withheld",
    "key_figures",
]
