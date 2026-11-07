# TASK: Data pipeline and evaluation (agent-1)

**Owner:** agent-1. **Paths:** data/, evaluation/, tests/data/, tests/evaluation/. Read PROJECT.md first.

## Objective
Replace the synthetic-sample stubs with real labelled data and an honest evaluation on unseen data.
This stream carries most of the 25% "testing on unseen data" score.

## Requirements
1. Download scripts for the chosen datasets (organisers' finance kit first; then PaySim, IBM AML transactions, or Elliptic) into `data/raw/` (git-ignored). Convert to `Transaction`. Add each dataset, its source and its licence to `data/README.md`.
2. Keep the **time-based** split (60/20/20) and freeze it: save the test transaction IDs and a hash of them.
3. Keep `make_alerts` as the rules-engine benchmark; tune its rules on train/val only.
4. `evaluation/`: recall and precision at analyst capacity, PR-AUC, analyst minutes saved, cost of missed cases, each with a bootstrap 95% CI. Compare arrival order, rules engine, model alone, full system. Add an adapter for the organisers' hidden test mode.
5. Write `evaluation/results.md` with the final table for the deck, including any benchmark missed.

## Completion criteria
- `python -m pytest` passes; `python pipeline.py --split test` runs on real data.
- `data_is_synthetic` in the evaluation output reflects the dataset actually used.
