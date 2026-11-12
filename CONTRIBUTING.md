# Contributing to Jane Avenue

Thanks for your interest. Jane Avenue is a prototype, but it holds itself to a high bar: **every number must be traceable, and nothing is invented**. This guide covers how to set up, check and submit a change.

> AI agents working on this repository follow [AGENTS.md](AGENTS.md) and [PROJECT.md](PROJECT.md) instead. Those files set out the ownership, branch and review rules.

## Set up

```bash
git clone https://github.com/Infosuii/Jane-Avenue.git && cd Jane-Avenue
cp .env.example .env
JANE_MODE=mock ./scripts/dev.sh        # Windows: $env:JANE_MODE = "mock"; .\scripts\dev.ps1
```

This needs Python 3.13 and Node.js 22+. `mock` mode needs no API key and is fully deterministic.

## Before you open a pull request

Run the same checks CI runs:

```bash
./scripts/check.sh                      # Windows: .\scripts\check.ps1
```

This runs `ruff`, `pytest -m "not live"`, `tsc`, `eslint`, `vitest`, `vite build` and the OpenAPI drift check. If you change a contract in `backend/jane_avenue/contracts/`, regenerate the API types in the same PR:

```bash
python backend/scripts/export_openapi.py && cd frontend && npm run gen:api
```

## Product rules (non-negotiable)

- **Gemini never produces forecast numbers.** Numbers come from `engine/` and `simulation/` only.
- **No invented sources.** Sources come from search grounding, fetched URLs or curated datasets, and quotes are verified in code.
- **Every number is labelled**: observed outcome, official costing, model scenario, assumption or AI interpretation.
- **Decline when unsure.** Out-of-scope requests or failed blocking checks must set `forecast_withheld`.
- **Tests never call live APIs**, and CI has no secrets.
- **Never commit** `.env`, keys, raw downloads (`data/raw/`) or files over 5 MB.

The full list is in [docs/MASTER_PROMPT.md](docs/MASTER_PROMPT.md), section 3.

## Branches and commits

- `main` is protected by convention: changes arrive through pull requests only.
- Name branches after their purpose, for example `fix/parser-negative-rate` or `docs/readme`.
- Keep pull requests focused, and say what you tested in the description.
