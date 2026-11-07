# Agent collaboration system

Eleven general-purpose agents (`agent-1` to `agent-11`) coordinate on this repository through GitHub only. They run on several tools, and every tool follows the same protocol:

- five Claude Code sessions
- one Codex CLI session
- five Antigravity sessions

There is no orchestrator, no background server, and no GitHub Action that runs a model.

## Architecture

- **GitHub Issues are the message bus and the task board.**
  - Eleven permanent inbox Issues, one per agent. See [INBOXES.md](INBOXES.md).
  - The coordination Issue (#8) handles multi-agent topics, and the contracts Issue (#20) handles interface changes.
  - Task Issues carry the objective, the milestone and status labels, and the completion criteria. Each agent creates its own task Issues from its prompt.
- **Branches isolate work.** `main` is the integration branch. Each agent has an identity branch and creates a separate task branch for each Issue.
- **Pull Requests propose changes to `main` and link to task Issues.** Reviews are PR comments (`REVIEW: APPROVED by agent-X`), because every agent shares one GitHub account.
- **Local state is limited to the last processed inbox comment ID.** It lives in `.agents/local/`, which is git-ignored.

## How each tool finds the rules

| Tool | Entry file | Then reads |
|---|---|---|
| Claude Code | [../CLAUDE.md](../CLAUDE.md) | AGENTS.md, PROJECT.md |
| Codex CLI | [../AGENTS.md](../AGENTS.md) (native) | PROJECT.md |
| Antigravity | [../GEMINI.md](../GEMINI.md) and AGENTS.md | PROJECT.md |

## Usage

1. Clone the repository on any laptop. Install `git`, `gh` (authenticated to the owning account), Python 3.13 and Node 22.
2. Open the tool for that agent (see the table in [PROTOCOL.md](PROTOCOL.md)).
3. Paste the agent's prompt file from [../docs/prompts/](../docs/prompts/) into the session.

To resume a session later, use [STARTUP_PROMPT.md](STARTUP_PROMPT.md).

## Files

- [../AGENTS.md](../AGENTS.md): shared protocol (authoritative)
- [../PROJECT.md](../PROJECT.md): product, folder ownership, reviewers, product rules
- [../docs/MASTER_PROMPT.md](../docs/MASTER_PROMPT.md): full build specification
- [../docs/prompts/](../docs/prompts/): one prompt per agent
- [PROTOCOL.md](PROTOCOL.md): message, label, branch and PR formats
- [INBOXES.md](INBOXES.md): inbox and coordination Issue numbers
- [STARTUP_PROMPT.md](STARTUP_PROMPT.md): starting and resuming sessions
- `.agents/local/`: device-specific state (never committed)
