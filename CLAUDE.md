# CLAUDE.md

This file is the Claude Code entry point for this repository.

Read [AGENTS.md](AGENTS.md) at the start of every session and follow it as the authoritative shared collaboration protocol. The detailed message, label, and branch formats are in [.agents/PROTOCOL.md](.agents/PROTOCOL.md).

Claude Code-specific notes:

- Your agent ID is given by the startup prompt in [.agents/STARTUP_PROMPT.md](.agents/STARTUP_PROMPT.md). Use `git -c user.name=<AGENT_ID>` for commits.
- Use `gh` for all GitHub operations.
- Do not commit anything under `.agents/local/`.
