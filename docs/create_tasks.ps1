# Creates the five task Issues (agent-1 .. agent-5) from docs/tasks/.
# Run from the repo root after `gh auth login`:  .\docs\create_tasks.ps1
$ErrorActionPreference = "Stop"
$repo = "Infosuii/Agentverse"

# Make sure the labels exist (--force updates them if they already exist).
foreach ($n in 1..5) { gh label create "agent-$n" --repo $repo --force | Out-Null }
gh label create "status:todo" --repo $repo --force | Out-Null

foreach ($n in 1..5) {
    $file = "docs/tasks/agent-$n.md"
    $title = (Get-Content $file -TotalCount 1).TrimStart('#', ' ')
    gh issue create --repo $repo --title $title --body-file $file --label "agent-$n" --label "status:todo"
}
