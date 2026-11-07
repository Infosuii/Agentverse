# Agent collaboration system

Seven general-purpose agents (`agent-1` to `agent-7`) coordinate on this repository through GitHub only. Claude Code and Codex CLI sessions on any laptop follow the same protocol. There is no orchestrator, no background server, and no GitHub Action that runs a model.

## Architecture

- **GitHub Issues** are the message bus and task board.
  - Seven permanent inbox Issues, one per agent. See [INBOXES.md](INBOXES.md).
  - One coordination Issue for multi-agent topics.
  - Task Issues carry the objective, requirements, and status labels.
- **Branches** isolate work. `main` is the integration branch. Each agent has an identity branch and creates a task branch per Issue.
- **Pull Requests** propose changes to `main` and link to task Issues.
- **Local state** is limited to the last processed inbox comment ID, in `.agents/local/`, which is git-ignored.

## Usage

1. Choose an agent number for the session, for example `3`.
2. Open a Claude Code or Codex CLI session in a clone of this repository on any laptop.
3. Paste [STARTUP_PROMPT.md](STARTUP_PROMPT.md) and replace `AGENT_ID` with `agent-3`.
4. The agent reads [AGENTS.md](../AGENTS.md), checks its inbox and assigned work, and resumes or claims a task.

Assigning work: create a task Issue with the agent's label and `status:todo`, or post a `REQUEST` in that agent's inbox.

## Requirements

- `git` and `gh` installed and authenticated to the account that owns this repository.
- Push access to this repository.

## Files

- [../AGENTS.md](../AGENTS.md): shared protocol (authoritative)
- [../CLAUDE.md](../CLAUDE.md): Claude Code entry point
- [PROTOCOL.md](PROTOCOL.md): message, label, branch, and PR formats
- [INBOXES.md](INBOXES.md): inbox and coordination Issue numbers
- [STARTUP_PROMPT.md](STARTUP_PROMPT.md): reusable startup prompt
- `.agents/local/`: device-specific state, not committed
