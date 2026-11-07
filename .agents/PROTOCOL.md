# Protocol

This is the reference for the formats all eleven agents use. Where this file and [AGENTS.md](../AGENTS.md) disagree, AGENTS.md wins.

## Agent IDs

Agent IDs are `agent-1` through `agent-11`, and nothing else. Use the ID exactly as written in labels, branch names, and `FROM` / `TO` fields.

| Agent | Recommended tool | Inbox | Workstream prompt |
|---|---|---|---|
| agent-1 | Claude Code | #1 | `docs/prompts/agent-01-backend-platform.md` |
| agent-2 | Claude Code | #2 | `docs/prompts/agent-02-gemini-research.md` |
| agent-3 | Claude Code | #3 | `docs/prompts/agent-03-econometric-engine.md` |
| agent-4 | Claude Code | #4 | `docs/prompts/agent-04-simulation-uncertainty.md` |
| agent-5 | Claude Code | #5 | `docs/prompts/agent-05-policy-verification.md` |
| agent-6 | Codex | #6 | `docs/prompts/agent-06-data-precedents.md` |
| agent-7 | Antigravity | #7 | `docs/prompts/agent-07-frontend-foundation.md` |
| agent-8 | Antigravity | #16 | `docs/prompts/agent-08-scenarios-charts.md` |
| agent-9 | Antigravity | #17 | `docs/prompts/agent-09-precedents-verification-report.md` |
| agent-10 | Antigravity | #18 | `docs/prompts/agent-10-evaluation-ml.md` |
| agent-11 | Antigravity | #19 | `docs/prompts/agent-11-integration-qa-demo.md` |

## Labels

| Group | Labels |
|---|---|
| Agent | `agent-1` … `agent-11` |
| Status | `status:todo`, `status:in-progress`, `status:blocked`, `status:review`, `status:done` |
| Milestone | `M1` (vertical slice), `M2` (feature complete and hardening) |
| Other | `agent-inbox`, `agent-message`, `needs-coordination`, `contract-change`, `integration` |

Each task Issue has exactly one agent label, one status label and one milestone label.

## Issue naming

| Issue type | Title format | Labels and notes |
|---|---|---|
| Inbox | `AGENT INBOX: agent-N` | Permanent. Labels `agent-inbox` and `agent-N`. |
| Coordination | `COORDINATION: shared channel` (#8) | Label `needs-coordination`. |
| Contracts | `CONTRACTS: shared interface changes` (#20) | Label `contract-change`. |
| Task | `TASK: [agent-N][M1] <short objective>` | Labels `agent-N`, a status label, and `M1` or `M2`. |
| Integration bug | `BUG: <symptom>` | Labels `integration` and the owner's `agent-N`. |

## Branch naming

| Branch type | Format |
|---|---|
| Identity | `agents/agent-N` |
| Task | `agents/agent-N/issue-<number>` |
| Setup | `setup/<topic>` |

## Message format

Post the message as an Issue comment, either in the recipient's inbox or in the coordination Issue for multi-agent topics:

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
- To address several agents in #8, write `TO: agent-3, agent-4` or `TO: all`.

## Message types

| Type | Meaning |
|---|---|
| `REQUEST` | Asks the recipient to do something. Needs a `RESPONSE` or an update. |
| `RESPONSE` | Answers a request. |
| `UPDATE` | Progress report with no required action. |
| `BLOCKER` | Work cannot continue. The Issue should be `status:blocked`. |
| `REVIEW` | Asks for review of a PR. The reviewer replies with a PR comment (see the PR rules below) and a `RESPONSE`. |

## Useful `gh` commands

```
# inbox comments newer than an ID (replace 16 with your inbox number)
gh api repos/Infosuii/Agentverse/issues/16/comments --paginate --jq '.[] | select(.id > LAST_ID) | {id, created_at, body}'
# your open tasks
gh issue list -R Infosuii/Agentverse --label agent-8 --state open
# post a message from a file
gh issue comment 4 -R Infosuii/Agentverse --body-file msg.txt
# change status
gh issue edit 42 -R Infosuii/Agentverse --remove-label status:todo --add-label status:in-progress
# review verdict on a PR
gh pr comment 57 -R Infosuii/Agentverse --body "REVIEW: APPROVED by agent-3"
```

## Task states

`status:todo` → `status:in-progress` → `status:review` → `status:done`

`status:blocked` may be set from `status:in-progress`. Clear it once the blocker is resolved.

## PR rules

- Target `main`.
- Start the title with the Issue number, for example `#42: short summary`.
- Include `Closes #42` in the body.
- Tests must pass before the PR is requested for merge.
- Keep to one task per PR where practical, and under about 400 changed lines.
- Reviewers are other agents, asked through a `REVIEW` message to the assigned reviewer (`PROJECT.md`).
- The verdict is a PR comment, `REVIEW: APPROVED by agent-X` or `REVIEW: CHANGES REQUESTED by agent-X`, because the shared account cannot use GitHub approvals.
- `contract-change` PRs need two agent approvals, or one if the change is additive and optional only.
- Merge only after review, using `gh pr merge <n> --squash --delete-branch`. No auto-merge unless a human asks.

## Conflict resolution

1. Detect overlap by checking open PRs and task Issues before editing shared files.
2. Post a `BLOCKER` or `REQUEST` to the other agent, or to the coordination Issue if more than two agents are involved.
3. Resolve conflicts only after agreement. Never overwrite another agent's commits.
4. Record the outcome in the coordination Issue.
