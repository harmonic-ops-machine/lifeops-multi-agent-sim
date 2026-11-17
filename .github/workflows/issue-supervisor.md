---
name: Declarative Multi-Agent Issue Supervisor
on:
  issues:
    types: [labeled]
  issue_comment:
    types: [created]
  workflow_dispatch:
permissions:
  contents: read
  issues: read
engine: gemini
max-parallel: 6
max-ci-repairs: 3
allowed-base-branches: ["agent-work/*"]
safe-outputs:
  dispatch-workflow:
    workflows: [code-worker, test-worker]
    max: 6
---

When an issue is labeled `state:ready` (or triggered via `/orchestrate` by a verified collaborator or `workflow_dispatch`):

1. Reject untrusted actors (`NONE`, `FIRST_TIMER`, `CONTRIBUTOR`) prior to any planner or worker execution.
2. Run a single-pass repository discovery scan into `.orchestrator/context_summary.json` so downstream workers never re-index the repository.
3. Decompose the objective into acyclic `SubTask` units with strictly non-overlapping `owned_paths`, attach a correlation `tracker_id`, target an `agent-work/*` umbrella integration branch, and lock the serialized plan (`chmod 0444` + `plan_sha256`).
4. Fan out unblocked wave workers concurrently in read-only containers (`contents: read`), emitting validated safe-output artifacts rather than holding direct write tokens.
5. Enforce deterministic verification in `safe-outputs`: unit tests, Zero-PII airgap verification (`verify.py`), `owned_paths` confinement, and an AST element-retention gate blocking diffs that drop `> 20%` of existing functions or classes. Cap automated CI repair at `3` attempts before halting with `state:blocked`.
6. Restrict automated worker merges strictly to `agent-work/*` integration branches, spawn newly unblocked downstream waves, and emit OpenTelemetry-compatible JSONL spans prior to opening a single consolidated PR to `main`.
