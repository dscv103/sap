# HOW TO ITERATE ON GITHUB ACTIONS

## One-Time Setup for a New Repo

Before the workflows will run, configure these in **Settings → Secrets and variables → Actions**:

### Repository Variables (`vars.*`)

|Variable          |Example value             |Purpose                                            |
|——————|—————————|—————————————————|
|`THOUGHTS_REPO`   |`standard-syntax/thoughts`|The humanlayer thoughts repository (org/repo)      |
|`GIT_USER_EMAIL`  |`bot@example.com`         |Git commit author email                            |
|`GIT_USER_NAME`   |`mybot`                   |Git commit author name                             |
|`DEFAULT_ASSIGNEE`|`myusername`              |GitHub username used as the default assignee filter|

### Repository Secrets (`secrets.*`)

|Secret                     |Purpose                                                              |
|—————————|———————————————————————|
|`COMPOUND_PAT`             |Personal access token with `repo` + `issues` + `pull_requests` scopes|
|`THOUGHTS_WRITE_DEPLOY_KEY`|SSH deploy key with **write** access to `THOUGHTS_REPO`              |

### File Layout

```
.github/
  actions/
    issue-worker-setup/
      action.yml          ← composite action (shared setup)
  workflows/
    gh-issues-research-tickets.yml
    gh-issues-create-plan.yml
    gh-issues-implement-plan.yml
    gh-prs-apply-review-fixes.yml
```

——

## Workflow Iteration Loop

1. **Select a branch** to work on
1. **Add branch to workflow trigger**:
   
   ```yaml
   on:
     push:
       branches:
         - main
         - your-debug-branch  # Add this
   ```
1. **Make one targeted change** per iteration
1. **Commit and push** to upstream:
   
   ```bash
   git push -u upstream your-debug-branch
   ```
1. **Check logs** with `gh`:
   
   ```bash
   gh run list —workflow=gh-issues-implement-plan.yml
   gh run view <run-id>
   gh run watch <run-id>
   gh run view <run-id> —log-failed   # jump straight to failures
   ```
1. **Repeat** until working. Remove branch from triggers before merging.

——

## Debugging opencode on the Runner

SSH into the runner and test opencode directly before wiring it into a workflow:

```bash
# Verify tools are on PATH
which opencode humanlayer bun node

# Test a prompt non-interactively (same flag the workflows use)
cd /path/to/repo
opencode run —format json —print-logs “list the files in the current directory”

# Check the API key is set in the runner environment
printenv | grep ANTHROPIC
```

If `opencode` is not found, add the bin dir to your shell profile:

```bash
echo ‘export PATH=“$HOME/.opencode/bin:$PATH”’ >> ~/.bashrc
```

——

## Self-Hosted Runner PATH

The workflows prepend these dirs to `$GITHUB_PATH` at runtime:

|Tool      |Path                                   |
|-———|—————————————|
|opencode  |`/home/github-runner/.opencode/bin`    |
|bun       |`/home/github-runner/.bun/bin`         |
|humanlayer|`/home/github-runner/.local/share/pnpm`|
|node      |resolved from `fnm` at runtime         |

If a tool is missing mid-run, check the **“Configure PATH”** step logs first.

——

## Common Failure Modes

|Symptom                                    |Likely cause                     |Fix                                              |
|-——————————————|———————————|-————————————————|
|`opencode: command not found`              |PATH not set                     |Check “Configure PATH” step                      |
|`gh: Resource not accessible`              |`COMPOUND_PAT` lacks scope       |Add `repo` + `issues` scopes to PAT              |
|`SSH deploy key` error on thoughts checkout|Key not in repo secrets          |Add `THOUGHTS_WRITE_DEPLOY_KEY` secret           |
|Label edit fails silently                  |Label doesn’t exist on repo      |Create labels via `gh label create`              |
|`make setup` fails                         |Go/mockgen missing on runner     |Install Go on runner; check `go env GOPATH`      |
|opencode produces empty output             |Prompt or slash command not found|Test prompt directly on runner first             |
|`vars.THOUGHTS_REPO` is empty              |Variable not set                 |Add variable in Settings → Variables → Actions   |
|Wrong assignee filtering                   |`DEFAULT_ASSIGNEE` not set       |Add variable or pass `assignee` input at dispatch|

——

## Useful One-Liners

```bash
# Re-run a failed job without pushing a new commit
gh run rerun <run-id> —failed

# Tail a live run
gh run watch $(gh run list —limit 1 —json databaseId —jq ‘.[0].databaseId’)

# Check which labels exist on the repo
gh label list

# Create a missing label
gh label create “ready-for-dev” —color 0075ca

# Manually trigger a workflow (skipping fetch, testing one issue)
gh workflow run gh-issues-implement-plan.yml -f num_issues=1

# Check configured repo variables
gh variable list
```