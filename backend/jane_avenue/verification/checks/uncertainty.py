"""Uncertainty check UNC-001 (MASTER_PROMPT 9.7, rule 6). Owner: agent-5.

Monte Carlo bands are assumption-driven ranges. They may be called "prediction intervals" only when the backtest
calibrated them (`interval_kind="empirical_prediction_interval"` with an `empirical_interval` and its note).
"""
from __future__ import annotations

import re

from ...contracts import Analysis
from ._base import Outcome, check

_PREDICTION_INTERVAL = re.compile(r"prediction\s+intervals?", re.I)
_NEGATION = re.compile(r"\b(?:not|no|never|rather\s+than|instead\s+of|unlike)\b|n't\b", re.I)


def claims_prediction_interval(text: str) -> bool:
    """True if `text` calls something a prediction interval without negating it ("not ... prediction intervals")."""
    for m in _PREDICTION_INTERVAL.finditer(text or ""):
        before = text[max(0, m.start() - 40):m.start()]
        if not _NEGATION.search(before):
            return True
    return False


@check("UNC-001", "uncertainty", "error", "rule", "Uncertainty bands are labelled honestly")
def unc_001(analysis: Analysis) -> Outcome:
    sim = analysis.simulation
    if sim is None or sim.monte_carlo is None:
        return Outcome("skipped", "No Monte Carlo results to check.")
    mc = sim.monte_carlo
    if mc.interval_kind == "empirical_prediction_interval":
        missing = [name for name, ok in (("empirical_interval", bool(mc.empirical_interval)),
                                         ("empirical_calibration_note", bool(mc.empirical_calibration_note)))
                   if not ok]
        if missing:
            return Outcome("issue", "The bands are labelled empirical prediction intervals but have no "
                                    f"{' or '.join(missing)}, so nothing shows they were calibrated.",
                           ["monte_carlo.interval_kind"])
        return Outcome("pass", "Empirical prediction intervals carry a backtest calibration note.")

    texts = {"monte_carlo.interval_note": mc.interval_note}
    texts.update({f"simulation.warning.{i}": w for i, w in enumerate(sim.warnings)})
    for s in sim.scenarios:
        texts[f"{s.scenario.name}.description"] = s.scenario.description
        texts.update({f"{s.scenario.name}.{m.metric}.note": m.note for m in s.result.metrics})
    mislabelled = [key for key, text in texts.items() if claims_prediction_interval(text)]
    if mislabelled:
        return Outcome("issue", "Assumption-driven ranges are described as prediction intervals in "
                                f"{', '.join(mislabelled[:5])}; they are not calibrated by the backtest.",
                       mislabelled)
    if not mc.interval_note.strip():
        return Outcome("issue", "The Monte Carlo bands have no interval note explaining that they are "
                                "assumption-driven ranges.", ["monte_carlo.interval_note"])
    return Outcome("pass", "Monte Carlo bands are labelled as assumption-driven ranges, not prediction intervals.")
