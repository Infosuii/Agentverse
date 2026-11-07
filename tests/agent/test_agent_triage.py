from agent.triage import triage
from controls.validator import validate
from data.alerts import make_alerts
from data.loaders import load_transactions
from risk.score import score


def test_template_note_passes_validator():
    txns = load_transactions("val")
    alerts = make_alerts(txns)
    for a, s in zip(alerts, score(alerts, txns)):
        rec = triage(a, s, txns)
        assert rec.alert_id == a.alert_id
        assert validate(rec, s, a, txns) == []
