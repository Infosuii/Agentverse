"""Analyst UI (STUB, owner: agent-5). Run:  streamlit run app/streamlit_app.py

To build: ranked queue, trace view, approve/override buttons that write to the
audit log, live-control button, on-screen failure scenario.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import streamlit as st  # noqa: E402

from controls import audit  # noqa: E402
from pipeline import run_detailed  # noqa: E402

st.set_page_config(page_title="Trusted Triage", layout="wide")
st.title("Trusted Triage: alert queue (synthetic data)")

split = st.sidebar.selectbox("Split", ["val", "test"])
out = run_detailed(split)
rows = sorted(
    zip(out["alerts"], out["scores"], out["recommendations"], out["decisions"]),
    key=lambda r: -r[1].probability,
)
st.caption(f"{len(rows)} alerts, ranked by model probability. Audit chain valid: {audit.verify_chain()}")

for alert, s, rec, d in rows[:50]:
    with st.expander(f"{alert.alert_id} | p={s.probability} | {d.final_action}"):
        st.write("**Trigger:**", alert.trigger)
        st.write("**Score:**", s.model_dump())
        st.write("**Case note:**", rec.case_note)
        st.write("**Policy:**", d.model_dump())
        c1, c2 = st.columns(2)
        if c1.button("Approve", key=f"ok-{alert.alert_id}"):
            audit.log("human", alert.alert_id, {"decision": "approve", "final_action": d.final_action})
            st.success("Logged")
        if c2.button("Override", key=f"no-{alert.alert_id}"):
            audit.log("human", alert.alert_id, {"decision": "override", "final_action": d.final_action})
            st.warning("Logged")
