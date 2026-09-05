---
name: repository-workflow
description: Apply stage-specific repository rules and validate all applicable earlier stages when the user requests work with issues, branches, project files, commits, pushes, pull requests, or merges in this repository.
---

# Repository Workflow

## Source of truth

Locate the repository root and read [`docs/repo_rules.md`](../../../docs/repo_rules.md) completely before handling an applicable repository stage. Treat that document as the single source of truth for naming conventions, segment definitions, validation requirements, and merge policies.

Do not duplicate maintained repository rules in this skill. Follow the current document if it changes. Explicit user instructions take precedence, but they do not authorize unrelated changes or unrequested external actions.

## Chronological stages and operating boundary

Use these stages in order:

1. Issue
2. Branch
3. Project changes
4. Commit
5. Push
6. Pull request
7. Merge

Apply only the stage or stages explicitly requested by the user. Before performing a requested stage, validate the existing results of every applicable earlier stage against the source-of-truth document. Do not create, change, or repair an earlier stage unless the user also requested that operation.

If a required earlier stage is missing or noncompliant, stop before performing the requested stage and report the blocker and the action needed to resolve it. Do not automatically continue to a later stage.

For example, a request to create a commit requires checking the linked issue, current branch, and project changes, but does not authorize fixing those items, pushing the commit, or opening a pull request.

If the user requests several stages, validate and perform only those stages in chronological order. Preserve unrelated tracked and untracked changes at every stage.

## Stage-specific guidance

### 1. Issue

When the user asks to inspect, create, or update an issue:

- use GitHub MCP when available and inspect both open and closed issues when repository numbering must be derived;
- check the issue title, segment, sequence number, scope, description, and acceptance criteria against the source-of-truth document;
- create or update only the issue authorized by the request;
- report the resulting issue identifier and any rule violation or missing information.

This stage has no repository-workflow prerequisite. Stop after the requested issue operation unless another stage was also requested.

### 2. Branch

When the user asks to inspect, create, rename, or switch a branch:

- first verify that the linked issue exists and complies with the source-of-truth document;
- inspect existing local and remote branch iterations;
- check the current working tree before changing branches;
- derive and verify the branch name against the source-of-truth document;
- perform only the requested branch operation and preserve unrelated work.

Stop after the requested branch operation unless another stage was also requested.

### 3. Project changes

When the user asks to change project files:

- first verify the linked issue and check that the current branch is appropriate for it;
- change only files within the requested scope;
- apply the repository structure, code-comment language, approved tooling, and secret-handling rules from the source-of-truth document;
- discover applicable checks from project configuration and run those relevant to the changed area without inventing commands.

Do not commit, push, or open a pull request unless the user also requests those stages.

### 4. Commit

When the user asks to create, amend, squash, or inspect commits:

- first verify the linked issue, current branch, and that the project changes match the issue scope and acceptance criteria;
- inspect the working tree, complete diff, staged files, results of applicable configured checks, and commits relative to the intended base;
- stage only files belonging to the current issue;
- check the commit message and logical scope against the linked issue and the source-of-truth document;
- rewrite existing history only when explicitly requested.

Do not push the resulting commit unless the user also requests a push.

### 5. Push

When the user asks to push or force-push:

- first verify the linked issue, current branch, results of applicable configured checks, and commit history;
- check the upstream, local commit IDs, and remote state before pushing;
- never rewrite `main`;
- use `--force-with-lease` for an authorized feature-branch history rewrite;
- verify the remote branch and commit after the push.

Do not create or update a pull request unless the user also requests that stage.

### 6. Pull request

When the user asks to inspect, create, or update a pull request:

- first verify the linked issue, branch, results of applicable configured checks, commit history, and remote branch state;
- check its head, base, title, linked issue, diff scope, commit list, and applicable required checks;
- check that the branch satisfies the pull request preparation rules in the source-of-truth document;
- verify that it contains only the requested issue's changes and follows the source-of-truth document;
- use GitHub MCP when available;
- perform only the requested pull request operation and verify the resulting remote state.

Do not merge the pull request unless the user explicitly requests a merge.

### 7. Merge

When the user asks to merge a pull request:

- first verify the linked issue, branch, results of applicable configured checks, commits, push state, and pull request state;
- check the allowed target and merge method in the source-of-truth document;
- verify approvals, required status checks, diff scope, and the expected head commit;
- merge only the explicitly requested pull request;
- verify the resulting target-branch and issue state.

## Response

Report the result and checks for the requested stage only. Clearly identify blockers, rule violations, and unrelated working-tree files that were left untouched.
