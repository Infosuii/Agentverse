# Protocol

Reference for formats used by all seven agents. The rules in [AGENTS.md](../AGENTS.md) take precedence.

## Agent IDs

`agent-1` through `agent-7`. Nothing else. Use the ID exactly in labels, branch names, and `FROM` / `TO` fields.

## Labels

- Agent: `agent-1` … `agent-7`
- Status: `status:todo`, `status:in-progress`, `status:blocked`, `status:review`, `status:done`
- Other: `agent-inbox`, `agent-message`, `needs-coordination`

Each task Issue has exactly one agent label and one status label.

## Issue naming

- Inbox: `AGENT INBOX: agent-N` (permanent, labels `agent-inbox` and `agent-N`)
- Coordination: `COORDINATION: shared channel` (label `needs-coordination`)
- Task: `TASK: <short objective>` (label `agent-N` and a status label)

## Branch naming

- Identity: `agents/agent-N`
- Task: `agents/agent-N/issue-<number>`
- Setup: `setup/<topic>`

## Message format

Post as an Issue comment in the recipient's inbox, or in the coordination Issue for multi-agent topics:

```
AGENT MESSAGE
FROM: agent-1
TO: agent-4
TYPE: REQUEST / RESPONSE / UPDATE / BLOCKER / REVIEW
RELATED ISSUE: #42
MESSAGE:
[Message content]
ACTION REQUIRED:
[Specific request, or NONE]
```

- `RELATED ISSUE` may be replaced by `RELATED PR: #<number>` when the topic is a PR.
- Use exactly one `TYPE` per message.
- Start the comment with `AGENT MESSAGE` so inboxes are easy to filter.

## Message types

- `REQUEST`: asks the recipient to do something. Needs a `RESPONSE` or an update.
- `RESPONSE`: answers a request.
- `UPDATE`: progress without a required action.
- `BLOCKER`: work cannot continue. The Issue should be `status:blocked`.
- `REVIEW`: asks for review of a PR. The reviewer replies with a `RESPONSE`.

## Task states

`status:todo` → `status:in-progress` → `status:review` → `status:done`

`status:blocked` may be set from `status:in-progress`. Clear it once the blocker is resolved.

## PR rules

- Target `main`.
- Title starts with the Issue number, for example `#42: short summary`.
- Body includes `Closes #42`.
- Tests pass before the PR is requested for merge.
- One task per PR where practical.
- Reviewers are other agents, requested by a `REVIEW` message.
- Merge only after review. No auto-merge unless a human asks.

## Conflict resolution

1. Detect overlap by checking open PRs and task Issues before editing shared files.
2. Post a `BLOCKER` or `REQUEST` to the other agent, or the coordination Issue if more than two agents are involved.
3. Resolve conflicts only after agreement. Never overwrite another agent's commits.
4. Record the outcome in the coordination Issue.
