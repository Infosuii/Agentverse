# Agent prompts

This folder has one self-contained prompt per agent. Open the right tool in a clone of `Infosuii/Agentverse` and paste the whole file in as the first message. Every prompt includes the startup protocol, the mission, owned paths, interfaces, the M1 and M2 tasks, the decisions already made, the reviewer, and the definition of done.

The master specification is [../MASTER_PROMPT.md](../MASTER_PROMPT.md). Every prompt points to the sections of it that the agent needs.

| # | Tool | Prompt | Workstream |
|---|---|---|---|
| 1 | Claude Code | [agent-01-backend-platform.md](agent-01-backend-platform.md) | Backend skeleton, contracts, API, orchestrator, store |
| 2 | Claude Code | [agent-02-gemini-research.md](agent-02-gemini-research.md) | Gemini gateway and autonomous research agent |
| 3 | Claude Code | [agent-03-econometric-engine.md](agent-03-econometric-engine.md) | Econometric engine and sourced parameter registry |
| 4 | Claude Code | [agent-04-simulation-uncertainty.md](agent-04-simulation-uncertainty.md) | Scenarios, Monte Carlo, tornado, interval semantics |
| 5 | Claude Code | [agent-05-policy-verification.md](agent-05-policy-verification.md) | Policy parser, scope gate, verification catalogue |
| 6 | Codex | [agent-06-data-precedents.md](agent-06-data-precedents.md) | Curated official data, provenance, precedent matching |
| 7 | Antigravity | [agent-07-frontend-foundation.md](agent-07-frontend-foundation.md) | Frontend scaffold, entry flow, live research view |
| 8 | Antigravity | [agent-08-scenarios-charts.md](agent-08-scenarios-charts.md) | Chart library, scenario explorer, calculation inspector |
| 9 | Antigravity | [agent-09-precedents-verification-report.md](agent-09-precedents-verification-report.md) | Precedents and verification views, report generator |
| 10 | Antigravity | [agent-10-evaluation-ml.md](agent-10-evaluation-ml.md) | Backtest, ML experiment, research and verifier evaluation |
| 11 | Antigravity | [agent-11-integration-qa-demo.md](agent-11-integration-qa-demo.md) | CI, end-to-end QA, demo, release |

## Start order

1. Merge the setup PR that adds these files. Agents read their prompts from `main`.
2. Start **agent-1**, **agent-7** and **agent-11** first. They build the skeleton, the scaffold and CI, which everyone else plugs into during the first hour.
3. Start the other eight immediately afterwards. They code against the contracts in MASTER_PROMPT Appendix A and Appendix B on their own branches, then rebase once the skeleton lands.
4. Put a `GEMINI_API_KEY` in your local `backend/.env` on the laptops running agents 2, 5, 9 and 10 for live work. Everything else runs in mock mode.
