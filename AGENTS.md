# AGENTS.md

The authoritative collaboration protocol for all seven agents (`agent-1` to `agent-7`). It applies to Claude Code and OpenAI Codex CLI alike. Detailed formats are in [.agents/PROTOCOL.md](.agents/PROTOCOL.md). Inbox Issue numbers are in [.agents/INBOXES.md](.agents/INBOXES.md).

There is no orchestrator. Agents coordinate by reading and writing GitHub Issues, comments and Pull Requests, using `gh`.

## 1. Identity

- You are exactly one agent: `agent-1` through `agent-7`. Your ID is given by the startup prompt (`AGENT_ID`).
- All agents are general-purpose. Do not assume a specialist role.
- Every agent shares one GitHub account. Identity comes from **labels, branch names, and the `FROM:` line** in messages, not from the GitHub assignee field.
- Set your git author for every commit: `git -c user.name=<AGENT_ID> commit ...`.

## 2. Branches

| Purpose | Name | Rule |
|---|---|---|
| Integration | `main` | Never commit or push directly. Changes arrive through PRs. |
| Identity | `agents/<AGENT_ID>` | Persistent. Owned by that agent only. Do not use it for task work. |
| Task work | `agents/<AGENT_ID>/issue-<N>` | Created from fresh `origin/main` for each task Issue `#N`. |
| Setup | `setup/*` | Infrastructure changes only, reviewed by a PR. |

- Do not modify another agent's branch without explicit agreement recorded in the coordination Issue.
- Never force-push, reset shared branches, or delete a branch that someone else may use.

## 3. Startup procedure

1. Identify yourself: confirm `AGENT_ID`.
2. `git fetch --all --prune`.
3. Read this file and [.agents/PROTOCOL.md](.agents/PROTOCOL.md).
4. Run the inbox check (see section 4) and the task check (see section 4).
5. Resume your claimed task, or claim the next `status:todo` task assigned to you.
6. Note the time of your last check for later comparison.

## 4. Checking GitHub

Check when: at session start, about every 3–5 minutes during active work at safe interruption points, after each meaningful milestone, before starting a task, before opening or updating a PR, and before ending the session.

Each check reads:

1. **Inbox:** new comments on your inbox Issue after your last processed comment ID.
2. **Assigned work:** open Issues labelled with your `agent-N` label.
3. **Active task Issues and PRs:** new comments and label changes.
4. **Coordination Issue:** new comments since your last check.

The last processed comment ID is stored locally in `.agents/local/<AGENT_ID>.last-comment-id`. This folder is git-ignored. Never commit it.

Do not busy-loop. Checks happen between steps of your work, not in a tight loop. If no work is available, report idle and stop normally.

## 5. Task claiming and completion

- A task is an Issue with your `agent-N` label, `status:todo`, a clear objective, requirements, relevant files, and completion criteria.
- **Claim** by commenting `CLAIM: agent-N` on the Issue and changing its status label to `status:in-progress`.
- If two claims appear, the **earliest** claim comment wins. The other agent withdraws and posts a note on the Issue.
- Before starting, check the Issue has no conflicting claim and no open `needs-coordination` thread.
- **Complete** by opening a PR that references the Issue (`Closes #N`), setting `status:review`, and then `status:done` after merge.
- Record technical decisions as comments on the task Issue.

## 6. Communication

- Send messages by posting a comment in the recipient's inbox Issue, using the format in [.agents/PROTOCOL.md](.agents/PROTOCOL.md).
- Every message needs `RELATED ISSUE` or `RELATED PR`.
- Respond to messages that have an `ACTION REQUIRED` other than `NONE`.
- Multi-agent topics go to the coordination Issue.
- Do not spam or continue circular threads. If a thread goes back and forth more than twice without progress, move it to the coordination Issue.

## 7. PR workflow

1. Work on `agents/<AGENT_ID>/issue-<N>` from fresh `origin/main`.
2. Before opening the PR, run the project's tests and make sure they pass.
3. Rebase or merge `origin/main` into your branch and resolve conflicts (section 8).
4. Open the PR against `main`, with `Closes #N` in the body and your `agent-N` label on the Issue.
5. Request review from another agent by posting a `REVIEW` message in that agent's inbox.
6. Merge only after review. Never enable auto-merge unless a human asks.

## 8. Conflict handling

- Before editing a file another agent is working on, check the open PRs and task Issues for overlap.
- Overlapping ownership must be agreed in the coordination Issue first.
- If changes conflict, do not overwrite the other agent's work. Post a `BLOCKER` message and resolve only after agreement.
- Keep merge-conflict resolutions minimal and explain them in the PR.

## 9. Shutdown

1. Check inbox and task Issues one last time.
2. Push your branch so the work is visible to other agents.
3. Post an `UPDATE` on your active task Issue with progress, next steps, and blockers.
4. If you are blocked, set `status:blocked` and post a `BLOCKER` message.
5. Report idle or stopped to the user.

## 10. Secrets

Never place passwords, API keys, or tokens in Issues, comments, PRs, or commits.
