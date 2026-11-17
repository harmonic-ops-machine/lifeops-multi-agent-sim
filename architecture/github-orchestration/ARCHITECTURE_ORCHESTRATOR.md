# Automated GitHub Multi-Agent Orchestrator (`GH-ORCHESTRATOR-v1`)

Separates **stateless/checkpointed coordination** from **isolated read-only worker execution** across both GitHub-native Actions workflows (`.github/workflows/issue-supervisor.md` -> `orchestrator-supervisor.yml`) and external state-graph webhook runtimes (`webhook_gateway.py`).

## 1. Execution Foundations & Topologies

| Layer | Native Actions Mode (`gh-aw` / `aw_compiler.py`) | External Graph Mode (`webhook_gateway.py`) |
| :--- | :--- | :--- |
| **Ingress & Admission** | `issues.labeled`, `issue_comment.created`, `workflow_dispatch` gated on collaborator association (`OWNER` / `MEMBER` / `COLLABORATOR`) | HTTP/FastAPI ingress verifying `X-Hub-Signature-256` HMAC (`hmac.compare_digest`) + collaborator role prior to any model call |
| **Context -> Plan** | `orchestrator_engine.py discover` writes `.orchestrator/context_summary.json`; locks `.orchestrator/plans/<tracker_id>.plan.json` (`0444` + SHA-256) | `FileCheckpointStore` (pluggable to Redis/SQLite) persists `OrchestrationPlan` + DAG wave state keyed by `tracker_id` |
| **Worker Dispatch** | Matrix fan-out job running with `permissions: contents: read` on isolated `agent-worker/*` worktrees | `asyncio.gather` fan-out across ephemeral `git worktree` sandboxes emitting read-only diff/bundle artifacts |
| **Safe-Outputs & Judge** | Dedicated `safe-outputs-judge-gate` job verifies `plan_sha256`, `owned_paths`, Zero-PII, and `<= 20%` AST drop before touching `agent-work/*` | Deterministic Judge + AST + Zero-PII verifier merges verified worker branches strictly into `agent-work/*` |

## 2. Production Hardening Adjustments (`harmonic-ops-machine`)

Four concrete failure modes in standard reference specs are remediated in this implementation:

1. **Dual Plan-State Locking (`chmod 0444` + Cryptographic `plan_sha256` Diff Guard):**
   Git tree objects persist only `100644` and `100755` file modes, stripping `chmod 0444` across fresh runner checkouts, and containerized processes owned by the runner UID can call `chmod +w`. `orchestrator_engine.py` applies `os.chmod(plan_path, 0o444)` inside worker worktrees **and** enforces cryptographic `plan_sha256` verification plus unconditional diff rejection on `.orchestrator/plans/**` inside `safe-outputs`.
2. **OpenTelemetry JSONL + Native Sub-Issues Replacing `403` Projects v2:**
   GitHub App installation `#182713228` lacks org/user `Projects v2` GraphQL scope (`ProjectV2 == null`). Telemetry (`tracker_id`, token usage, tool call counts, checkpoint SHAs, heartbeats) is persisted to `.orchestrator/telemetry/spans.jsonl` and `$GITHUB_STEP_SUMMARY`, paired with Issue state labels (`state:ready` / `state:claimed` / `state:review` / `state:blocked`).
3. **Deterministic `.aw.md` Compiler (`aw_compiler.py`) Alongside `github/gh-aw`:**
   Declarative agent workflows in `.github/workflows/issue-supervisor.md` remain compatible with `gh extension install github/gh-aw && gh aw compile`, while `src/aw_compiler.py` compiles frontmatter deterministically into `.github/workflows/orchestrator-supervisor.yml` with zero external binary or secret dependency during CI verification.
4. **Dual Pydantic v2 / Zero-Dependency Python 3.12 Runtime:**
   `SubTask` and `OrchestrationPlan` inherit from `pydantic.BaseModel` automatically when Pydantic is installed while executing identically on bare Python 3.12 stdlib runners (`verify-zero-pii.yml`).

## 3. Six-Step Security & Verification Contract

1. **Identity & Least Privilege:** Workers execute with `contents: read` only; zero PATs are stored in repo files. Writes occur exclusively inside `safe-outputs` jobs or GitHub App installation tokens.
2. **Signed Event Admission & Typed Schemas:** Rejects missing/invalid `X-Hub-Signature-256` digests and untrusted actors (`NONE`, `FIRST_TIMER`, `CONTRIBUTOR`) before invoking any LLM. Inter-stage handoffs exchange validated JSON (`schemas/orchestration_plan.schema.json`, `schemas/worker_safe_output.schema.json`).
3. **Single-Pass Discovery & Disjoint Wave Planning:** Indexes tracked files, manifests, and verifier commands once into `.orchestrator/context_summary.json`, rejects cyclic task graphs via Kahn topological sort, and rejects overlapping `owned_paths` globs across tasks.
4. **Sandboxed Parallel Fan-Out:** Dispatches each unblocked wave (`Wave 0`, `Wave 1`, ...) concurrently across isolated worktrees branched from `agent-work/issue-<N>`.
5. **AST Element-Retention (`<= 20%` Drop) & 3-Strike CI Repair Circuit Breaker:** Blocks diffs that silently delete `> 20%` of existing Python functions/classes (`FunctionDef`, `AsyncFunctionDef`, `ClassDef`). Failed check runs trigger at most **`3`** automated repair attempts before halting and applying `state:blocked`.
6. **Umbrella-Only Automated Merges & Orphan Reaping:** Enforces `allowed-base-branches: ["agent-work/*"]` (hard-blocking automated worker merges into `main`), opens a single consolidated PR to `main` once all tasks and integration checks pass, and reaps stalled worker leases via `reap_stalled_workers` + `agent-orchestration-bus.yml`.
