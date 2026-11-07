# GEMINI.md

This file is the Google Antigravity entry point for this repository. Antigravity agents in this build are `agent-7` to `agent-11`.

## Read first

Read [AGENTS.md](AGENTS.md) at the start of every session and follow it as the authoritative shared collaboration protocol. The message, label and branch formats are in [.agents/PROTOCOL.md](.agents/PROTOCOL.md).

After AGENTS.md, read:

1. [PROJECT.md](PROJECT.md), which covers the product, folder ownership and product rules.
2. The sections of [docs/MASTER_PROMPT.md](docs/MASTER_PROMPT.md) that your prompt names.

## Antigravity-specific notes

- **Identity.** Your prompt file in [docs/prompts/](docs/prompts/) gives your agent ID and workstream. To resume a session, see [.agents/STARTUP_PROMPT.md](.agents/STARTUP_PROMPT.md). Commit with `git -c user.name=<AGENT_ID>`.
- **GitHub.** Run every GitHub operation through the `gh` CLI in the terminal, so it follows the same protocol as the other tools.
- **Browser.** Use the built-in browser to verify UI work against the running app: backend on `:8000`, frontend on `:5173`, mock mode needs no API key.
- **Ownership.** Only edit paths you own (see PROJECT.md).
- **Secrets.** Never commit `.env`, API keys or anything under `.agents/local/`.
