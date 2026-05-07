---
name: git-branch-workflow
description: "Use when user asks to commit, push, save, or open a PR; enforces feature-branch workflow, coverage checks, and safe PR creation"
---

# Git Branch Workflow

Use this workflow when the user requests commit/push/save/open PR activity.

## Core Rule
Never commit directly to `master`. Always use a feature branch and land via PR.

## Branch Naming Convention

Use prefixed branch names to categorize work:

- **`feature/<desc>`** — for functional/code changes (new features, bug fixes, spec implementations)
  - Examples: `feature/spec-21-dashboard-key-rotation`, `feature/fix-cache-bug`
- **`chore/<desc>`** — for documentation, config, spec file reorganization (no code changes)
  - Examples: `chore/update-readme`, `chore/move-spec-13-to-completed`

## Standard Flow
1. Show current pending changes first with `git status` and staged/unstaged diffs.
2. If not already on a feature branch:
   - `git checkout master`
   - `git pull origin master`
   - Determine change type: functional code (`.cs`, behavior, tests, endpoints) → `feature/*`; docs/config/spec only → `chore/*`
   - Create branch: `git checkout -b feature/<spec-or-feature-name>` or `git checkout -b chore/<chore-name>`
3. Determine change type before staging/commit:
   - Run `git diff --stat` (and `git status --porcelain --untracked-files=all` if needed) to classify the change set.
   - Before push/PR, classify the entire branch delta against base (for example `git diff --name-only origin/master...HEAD`) to decide CI behavior.
   - If files are docs/config/spec only, treat as a chore PR path.
   - If any functional/code files are present (for example `.cs`), treat as functional path.
4. Stage intended files and create a clear commit message.
5. Validate test coverage for behavior changes:
   - new endpoints
   - validation paths
   - DTO changes
   - business logic changes
6. Add missing tests before pushing.
7. Run full tests only when changes are functional (for example `.cs`, behavior, validation, DTO, API, or business logic updates):
   - First check whether a debugger or local API host is running and may lock `bin/Debug` outputs.
   - PowerShell detection examples:
     - `Get-Process -Name dotnet,vsdbg -ErrorAction SilentlyContinue`
     - `Get-CimInstance Win32_Process | Where-Object { $_.Name -in @('dotnet.exe','vsdbg.exe') -and $_.CommandLine -match 'locker.api|CoopLocker.Api' } | Select-Object Name, ProcessId, CommandLine`
     - `Get-NetTCPConnection -State Listen -ErrorAction SilentlyContinue | Where-Object { $_.LocalPort -in 5000,5001 }`
   - If no debugger/host is running, use: `dotnet test locker.tests/CoopLocker.Tests.csproj`.
   - If debugger/host is running (or if test build fails with file-lock errors like `MSB3021`/`MSB3027`), use a non-conflicting output path: `dotnet test locker.tests/CoopLocker.Tests.csproj --configuration Release`.
8. If tests were run, fix failures before proceeding; do not push failing branches.
9. Check if roadmap/docs updates are needed in `BUSINESS_PLAN.md`.
10. Before push or PR creation, ask for user confirmation.
11. Push branch and open PR with `gh pr create` (preferred in PowerShell). If `gh` is unavailable on PATH, use an absolute executable path that works in the current shell.
12. Provide PR URL as a clickable markdown link.
13. After merge confirmation, sync local master with `git checkout master && git pull origin master`.
14. Clean up merged feature branches:
   - delete local branch: `git branch -d <feature-branch>`
   - delete remote branch: `git push origin --delete <feature-branch>`
15. If remote deletion fails with "remote ref does not exist", treat it as already cleaned up (for example auto-delete on merge).

## Spec Completion Rule
If PR implements a pending spec:
1. Move the spec into completed before PR:
   - `git mv docs/specs/pending/<spec>.md docs/specs/completed/`
2. Commit that move on the feature branch.
3. Do not use `[skip ci]` on that commit.

## Chore PR Exception (docs/config only)
Use `chore/*` branch prefix for documentation and configuration-only changes:
1. Verify changed files are docs/config/spec only (`git diff --stat`).
2. Skip test execution.
3. Verify the entire PR branch is docs/config/spec only (for example `git diff --name-only origin/master...HEAD`).
4. Only if the entire branch is chore-only, commit message MUST include `[skip ci]`.
5. If the current HEAD commit does not contain `[skip ci]` for a chore-only branch, amend it before pushing:
   - `git commit --amend -m "<existing message> [skip ci]"`
6. If any commit in the branch is functional/non-chore, do NOT use `[skip ci]`; CI must run.
7. Continue with push + PR.

Important: For multi-commit PRs, apply `[skip ci]` only when all commits/changes in the branch are chore-only. If any non-chore change exists, ensure HEAD does not contain `[skip ci]` so CI runs.

If `.cs` files are changed, do not treat it as a chore PR — use `feature/*` branch instead.

## Safety Requirement
Always confirm with the user before push or PR creation because those are shared actions.
