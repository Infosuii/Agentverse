from data.alerts import make_alerts
from data.loaders import load_alert_labels, load_transactions


def test_splits_are_disjoint_and_time_ordered():
    tr, va, te = (load_transactions(s) for s in ("train", "val", "test"))
    assert tr and va and te
    ids = [{t.txn_id for t in x} for x in (tr, va, te)]
    assert not (ids[0] & ids[1]) and not (ids[1] & ids[2]) and not (ids[0] & ids[2])
    assert max(t.timestamp for t in tr) <= min(t.timestamp for t in va)
    assert max(t.timestamp for t in va) <= min(t.timestamp for t in te)


def test_transactions_carry_no_labels():
    t = load_transactions("train")[0]
    assert not hasattr(t, "is_illicit")


def test_alerts_have_labels_and_arrival_order():
    txns = load_transactions("val")
    alerts = make_alerts(txns)
    labels = load_alert_labels("val")
    assert alerts and set(labels) == {a.alert_id for a in alerts}
    assert [a.created_at for a in alerts] == sorted(a.created_at for a in alerts)
