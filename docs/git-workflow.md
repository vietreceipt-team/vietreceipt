# Git and Task Workflow

This file summarizes the supplied internal Git/GitHub guide and applies it to the Week 1 contract task.

## Mandatory rules

- Repository and GitHub Project stay private.
- Never commit `.env`, passwords, tokens, API keys, database credentials or sensitive receipt images.
- Every official task has one GitHub Issue.
- Every Issue has its own branch and Pull Request.
- Do not push directly to `main`, force-push `main`, self-merge without review or mark an unreviewed task Done.

## Branch naming

```text
<type>/<issue-number>-<short-description>
```

Allowed types: `feat`, `fix`, `test`, `docs`, `exp`, `refactor`, `chore`.

Week 1 example:

```text
docs/12-week1-backend-contract
```

## Commit naming

```text
<type>(<module>): <short imperative description>
```

Examples:

```text
docs(architecture): define module communication
docs(api): add receipt endpoints and shared models
docs(integration): define OCR and KIE contracts
fix(api): align total value with integer VND convention
```

Avoid messages such as `update`, `done`, `ok`, `fix`, `final` or `abc`.

## Pull Request requirements

The PR body must contain:

- Related Issue with `Closes #<number>`.
- What was implemented.
- Files delivered.
- How schemas/OpenAPI were validated.
- Which owners reviewed the contract.
- Remaining questions or explicitly `None`.
- Impact on Frontend, OCR, KIE and DevOps.

Suggested title:

```text
docs(backend): publish week 1 architecture and contract v1
```

## Task states

```text
Backlog -> Ready -> In Progress -> In Review -> Done
                         \-> Blocked
```

- Developer moves the task to `In Review` after opening the PR.
- Reviewer/technical lead moves it to `Done` after approval, validation and merge.
- A blocker lasting more than 24 hours must be reported in the Issue.

Blocked report format:

```text
STATUS: BLOCKED
Blocked by: Issue #... / module ...
Reason: ...
Required action: ...
Owner needed: ...
Blocked since: ...
```

## Proposed Week 1 Issue breakdown

| Issue | Output | Dependency |
| --- | --- | --- |
| Architecture v1 | `docs/architecture.md` | Project scope |
| Receipt lifecycle | `docs/receipt-state-machine.md` | Architecture |
| API Contract v1 | `openapi/openapi.yaml` | State machine + Frontend review |
| OCR/KIE contract | `schemas/*.json`, integration doc | OCR and KIE owner confirmation |
| Contract sign-off | Completed review checklist | All four previous outputs |

They may be one parent Issue with sub-issues or separate Issues in GitHub Project. Each code/document change still uses one clear branch and PR.

