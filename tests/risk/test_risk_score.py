from data.alerts import make_alerts
from data.loaders import load_transactions
from risk.score import score


def test_scores_are_valid_and_aligned():
    txns = load_transactions("val")
    alerts = make_alerts(txns)
    scores = score(alerts, txns)
    assert [s.alert_id for s in scores] == [a.alert_id for a in alerts]
    for s in scores:
        assert 0 <= s.interval_low <= s.probability <= s.interval_high <= 1
        assert s.top_factors
