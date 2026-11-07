# CLAUDE.md

This file is the Claude Code entry point for this repository.

Read [AGENTS.md](AGENTS.md) at the start of every session and follow it as the authoritative shared collaboration protocol. The message, label and branch formats are in [.agents/PROTOCOL.md](.agents/PROTOCOL.md).

After AGENTS.md, read [PROJECT.md](PROJECT.md), which covers the product, folder ownership and product rules. Then read the sections of [docs/MASTER_PROMPT.md](docs/MASTER_PROMPT.md) that your prompt names.

Claude Code-specific notes:

- Your agent ID and workstream are given by your prompt file in [docs/prompts/](docs/prompts/). If you are resuming a session, see [.agents/STARTUP_PROMPT.md](.agents/STARTUP_PROMPT.md). Use `git -c user.name=<AGENT_ID>` for commits.
- Use `gh` for all GitHub operations.
- If the `gemini-api-dev` skill is available, use it before writing Gemini calls. Otherwise, fetch the documentation URLs listed in MASTER_PROMPT rule 12.
- Do not commit anything under `.agents/local/`.
