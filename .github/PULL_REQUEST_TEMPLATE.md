## What this changes

<!-- One or two sentences. Link the issue: Closes #… -->

## How it was tested

- [ ] `./scripts/check.sh` (or `.\scripts\check.ps1`) passes locally
- [ ] Golden path still approved: `python backend/scripts/smoke.py --mode mock --expect-approved`
- [ ] If a contract changed: OpenAPI exported and `npm run gen:api` re-run

## Product rules

- [ ] No forecast number comes from Gemini
- [ ] Every new number is labelled and traceable to a calculation, quote or dataset row
- [ ] No `.env`, keys, raw downloads or files over 5 MB
