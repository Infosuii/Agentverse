# TASK: Integration, analyst app and deck (agent-5)

**Owner:** agent-5. **Paths:** pipeline.py, app/, README.md, PROJECT.md, docs/, .github/, tests/test_pipeline.py, requirements.txt. Read PROJECT.md first.

## Objective
Keep the pipeline running end to end as other streams land, build the analyst UI, and prepare the submission.
This stream carries the 20% "relevance and impact" score and owns the deck evidence.

## Requirements
1. After each merged PR, run `python -m pytest` and `python pipeline.py --split val`; report breakages in Issue #8.
2. Streamlit app: ranked alert queue; trace view (raw transactions, features and score, case note, policy decision, human decision); approve/override buttons that write to the audit log; live-control button; on-screen failure scenario (uncertain novel pattern routed to the analyst).
3. README: how to run, data sources and licences, synthetic labels, limitations, "paper only".
4. Deck outline in `docs/deck.md`: problem, who it helps, data, evaluation vs benchmark (from `evaluation/results.md`), limits and controls, key statistics.
5. Before submission: repo public, demo works, rough demo recording as backup.

## Completion criteria
- Fresh clone -> install -> `python -m pytest` -> `streamlit run app/streamlit_app.py` works on Windows.
