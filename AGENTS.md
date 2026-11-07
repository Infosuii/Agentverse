# AGENTS.md

This is the authoritative collaboration protocol for all eleven agents, `agent-1` to `agent-11`. It applies equally to Claude Code, OpenAI Codex CLI and Google Antigravity.

- Detailed message, label and branch formats are in [.agents/PROTOCOL.md](.agents/PROTOCOL.md).
- Inbox Issue numbers are in [.agents/INBOXES.md](.agents/INBOXES.md).
- The product and folder ownership are in [PROJECT.md](PROJECT.md).
- The full build specification is in [docs/MASTER_PROMPT.md](docs/MASTER_PROMPT.md).

There is no orchestrator. Agents coordinate by reading and writing GitHub Issues, comments and Pull Requests, using `gh`. Agent-11 is the integration lead: it watches CI and the whole system and unblocks others, but it does not direct work.

## 1. Identity

- You are exactly one agent, `agent-1` through `agent-11`. Your ID and your workstream come from your startup prompt, which is one of the files in `docs/prompts/`.
- Agents are general-purpose. Your workstream comes from your prompt and the ownership table in `PROJECT.md`, not from your tool. The recommended tools are:
  - `agent-1` to `agent-5`: Claude Code
  - `agent-6`: Codex
  - `agent-7` to `agent-11`: Antigravity
- Every agent shares one GitHub account. Identity comes from **labels, branch names, and the `FROM:` line** in messages. It does not come from the GitHub assignee field.
- Set your git author on every commit: `git -c user.name=<AGENT_ID> commit ...`.

## 2. Branches

| Purpose | Name | Rule |
|---|---|---|
| Integration | `main` | Never commit or push directly. Changes arrive through PRs. |
| Identity | `agents/<AGENT_ID>` | Persistent. Owned by that agent only. Do not use it for task work. |
| Task work | `agents/<AGENT_ID>/issue-<N>` | Created from fresh `origin/main` for each task Issue `#N`. |
| Setup | `setup/*` | Infrastructure changes only, reviewed by a PR. |

- Do not modify another agent's branch without explicit agreement recorded in the coordination Issue.
- Never force-push, reset shared branches, or delete a branch that someone else may use. You may delete your own task branch after its PR is merged.

## 3. Startup procedure

1. Identify yourself: confirm your `AGENT_ID`.
2. Run `git fetch --all --prune`.
3. Read this file, [.agents/PROTOCOL.md](.agents/PROTOCOL.md), [PROJECT.md](PROJECT.md), and the sections of [docs/MASTER_PROMPT.md](docs/MASTER_PROMPT.md) named in your prompt.
4. Run the inbox check and the task check (see section 4).
5. Resume your claimed task. If you have no task Issues, create them from your prompt (see section 5).
6. Note the time of your last check, for later comparison.

## 4. Checking GitHub

Check at these times:

- at session start;
- every 3–5 minutes during active work, at safe interruption points;
- after each meaningful milestone;
- before starting a task;
- before opening or updating a PR;
- before ending the session.

Each check reads, in order:

1. **Inbox:** new comments on your inbox Issue since your last processed comment ID.
2. **Assigned work:** open Issues labelled with your `agent-N` label.
3. **Active task Issues and PRs:** new comments, review comments and label changes.
4. **Coordination Issue #8 and Contracts Issue #20:** new comments since your last check.

Your last processed comment ID is stored locally in `.agents/local/<AGENT_ID>.last-comment-id`. This folder is git-ignored; never commit it.

- **Rate limit.** All eleven agents share one GitHub account, which allows 5,000 API calls per hour. Keep each check to a few `gh` calls, and do not poll more often than every 3 minutes.
- **Do not busy-loop.** Checks happen between steps of your work, not in a tight loop. If no work is available, report idle and stop normally.

## 5. Tasks: creating, claiming and completing

- **Creating.** A task is an Issue with:
  - your `agent-N` label;
  - a status label;
  - a milestone label (`M1` or `M2`);
  - a clear objective and completion criteria.

  Each agent **creates its own task Issues** at startup from its prompt, using the commands in the prompt. Humans or agent-11 may also create tasks for you. Before creating, check that they don't already exist: `gh issue list --label agent-N --state all`.
- **Claiming.** Comment `CLAIM: agent-N` on the Issue and set its status label to `status:in-progress`.
  - If two claims appear, the **earliest** claim comment wins. The other agent withdraws and posts a note on the Issue.
  - Before starting, check that the Issue has no conflicting claim and no open `needs-coordination` thread.
- **Completing.** Open a PR that references the Issue (`Closes #N`) and set the Issue to `status:review`. After the merge, set it to `status:done`.
- **Decisions.** Record technical decisions as comments on the task Issue. Cross-cutting decisions also go in `docs/ARCHITECTURE_NOTES.md`, through agent-1.

## 6. Communication

- To send a message, post a comment in the recipient's inbox Issue, using the format in [.agents/PROTOCOL.md](.agents/PROTOCOL.md).
- Every message needs a `RELATED ISSUE` or `RELATED PR` line.
- Respond to every message whose `ACTION REQUIRED` is anything other than `NONE`.
- Multi-agent topics go to the coordination Issue #8. Contract and interface changes go to Issue #20.
- Do not spam or continue circular threads. If a thread goes back and forth more than twice without progress, move it to #8 and tag agent-11.

## 7. PR workflow

1. Work on `agents/<AGENT_ID>/issue-<N>`, branched from fresh `origin/main`.
2. Keep PRs small: under about 400 changed lines, excluding generated files and data. Open a draft PR early.
3. Before requesting review, merge `origin/main` into your branch and run the project checks (`scripts/check` once it exists, otherwise the commands in `PROJECT.md`). All checks must pass.
4. Open the PR against `main`. The title is `#N: summary`, and the body contains `Closes #N`.
5. Request review from your assigned reviewer (`PROJECT.md`) by posting a `REVIEW` message in their inbox.
6. **Reviews.** The shared account cannot use GitHub's "Approve", so reviewers post a PR comment instead:
   - `REVIEW: APPROVED by agent-X`, or
   - `REVIEW: CHANGES REQUESTED by agent-X`, followed by specific points.

   Review within about 20 minutes. If your reviewer has been silent for 30 minutes, ask agent-11.
7. **Merging.** The author merges after approval: `gh pr merge <n> --squash --delete-branch`. Never enable auto-merge unless a human asks.

## 8. Conflict handling

- Only edit paths you own (see `PROJECT.md`). Before touching another agent's path, post a `REQUEST` and wait for agreement.
- `backend/jane_avenue/contracts/` belongs to nobody. Change it only through a `contract-change` PR (see `PROJECT.md`).
- If changes conflict, do not overwrite the other agent's work. Post a `BLOCKER` message and resolve only after agreement.
- Keep merge-conflict resolutions minimal, and explain them in the PR. For dependency files (`requirements.txt`, `package.json`), keep both sides.

## 9. Shutdown

1. Check your inbox and task Issues one last time.
2. Push your branch so the work is visible to other agents.
3. Post an `UPDATE` on your active task Issue with progress, next steps and blockers.
4. If you are blocked, set `status:blocked` and post a `BLOCKER` message.
5. Report to the user that you are idle or stopped.

## 10. Secrets

Never place passwords, API keys or tokens in Issues, comments, PRs or commits. `GEMINI_API_KEY` lives only in your local `.env`, which is git-ignored.
