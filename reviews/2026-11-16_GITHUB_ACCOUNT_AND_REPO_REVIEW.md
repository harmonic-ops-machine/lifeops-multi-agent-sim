# GitHub Account & Repository Architecture Review: `harmonic-ops-machine` (`v8.3.1`)

- **Review Date (`HST` / `UTC-10`):** `2026-11-16`
- **Target Account:** `https://github.com/harmonic-ops-machine`
- **Target Branch:** `improve/enclave-audit-v8.3.1` (isolated from `main` at `2afe70b`)
- **Zero-PII Compliance:** Strict (`0` emails, `0` local user paths, `0` tokens, `0` personal identifiers)

---

## 1. Account & Multi-Repository Footprint Review

### 1.1 Observed GitHub Inventory

| Asset | Visibility | Current State | Assessment & Gap |
| :--- | :---: | :--- | :--- |
| **GitHub Profile (`harmonic-ops-machine`)** | `Public` | Created `2026-11-13`; `name`, `bio`, `company`, `blog`, `location` empty; no profile README repo | Missing operator-facing context on role (`HIGHRES Zero-PII Machine Enclave`) and canonical public/private vault links |
| **`lifeops-multi-agent-sim`** | `Public` | `main` at `2afe70b`; CI passed on `2afe70b` after 4 prior advisory-schema CI failures; description says `v8.0.0`, `topics: []` | Strong flagship spec (`v8.3.0`), but lacks `SECURITY.md`, branch protection on `main`, `improve/**` CI triggers, and several hardening fixes below |
| **`harmonic-test-alpha`** | `Private` | 4 live branches (`main`, `dev`, `feat/remote-control-smoke`, `test/enclave-branch-probe`); paired with Private Project `#2` | Clean visual topology docs (`docs/GITHUB-TOPOLOGY.md`), but lacks `.github/workflows` CI and `push_turn.py` uses a looser email allowlist than `lifeops-multi-agent-sim` |
| **`harmonic-test-beta`** | `Private` | 4 live branches (`main`, `staging`, `feat/pipeline-smoke`, `fix/branch-sync-test`); paired with Private Project `#3` | Smoke-test scaffold works for branch parity, but has no CI workflow or branch ruleset yet |
| **Private Vault Target (`lifeops-enclave-private` / `gemini-session-refinery`)** | `Uncreated Remote` | Local `$LO_ROOT/simulations/lifeops-enclave-private` exists (`14376af`, branches `main`, `inbox/raw-sessions`), while `ARCHITECTURE_PL.md` & `provision_gcs_and_oidc.ps1` name `gemini-session-refinery` | **Naming & provisioning drift:** remote repo does not yet exist on GitHub (`Repository not found`). Standardize on one name and create it as `Private` with CI secret scanning before pushing raw traces |

### 1.2 Architectural Observations on `lifeops-multi-agent-sim`

1. **Per-Turn Daemon Churn on `main`:** Global `Stop` hooks mutate `CONTINUITY_CHECKPOINT.json` and `manifest.json` on the local `main` checkout after every IDE turn. Any review or feature work done directly in the primary local directory risks dirty diffs or accidental commits across unrelated state updates; isolated Git worktrees (`isolated-worktrees/<branch>`) eliminate that hazard cleanly.
2. **Verifier Parity Drift:** `verify.py` previously checked only 3 of the 8 `manifest.json` artifacts (`simulation_spec.json`, `carbon_loop_feed.json`, `prior_work_digest.json`) and did not run the full-repo Zero-PII or `advisories/*.json` schema checks that GitHub Actions ran inline—meaning local `python verify.py` could return `ok: true` even when a change would fail CI.
3. **Trajectory Refinery Gap Between Spec & Code:** `ARCHITECTURE_PL.md` (`v8.3.0`) described Channel A (`Export to Docs` Markdown), Channel B (`Google Takeout JSON`), and 7 root-cause categories, whereas `refinery_engine.py` (`v8.3.0`) lacked Channel A/B parsers, covered only 5 of 7 categories, had no runtime schema enforcement, and matched broad words like `error` and `failed` that caused benign engineering summaries to be falsely pruned from `L1` distilled output.

---

## 2. Detailed Code, Security, Schema & IaC Improvements Implemented (`improve/enclave-audit-v8.3.1`)

| Finding ID | Severity | Component | Root Cause Identified | Improvement Implemented |
| :--- | :---: | :--- | :--- | :--- |
| **`FIND-01`** | `High` | `architecture/trajectory-refinery/src/cloudrun_mcp_ingestor.py` | Unbounded `Content-Length` reads; missing bearer-auth hook; unguarded `session_id` length (`< 4` possible) and path containment; missing MCP `notifications/*` (`202 Accepted`) & `ping` support; unhandled JSON parse errors crashing handler | Added `2 MiB` `MAX_REQUEST_BYTES` guard (`413`), optional constant-time `REFINERY_MCP_BEARER_KEY` (`hmac.compare_digest` -> `401`), `GET /healthz`, structured JSON-RPC `-32700`/`-32600`/`-32602` error responses, `202` notification handling, strict `sanitize_session_id()` (`4..128` chars) + `resolve()` containment, and `validate_trace_records()` pre-write enforcement |
| **`FIND-02`** | `High` | `architecture/trajectory-refinery/scripts/provision_gcs_and_oidc.ps1` | Used `Invoke-Expression` on interpolated shell strings; lacked `[ValidatePattern]` parameter checks; OIDC `--attribute-condition` trusted any repo under `repository_owner`; omitted least-privilege Service Account + bucket-scoped IAM steps | Replaced `Invoke-Expression` with `& gcloud @($step.Args)` + `$LASTEXITCODE` checks; added strict regex `[ValidatePattern]` on all parameters; narrowed OIDC trust to exact `assertion.repository == '<owner>/<repo>'`; added SA creation + bucket-scoped `roles/storage.objectUser` + `roles/iam.workloadIdentityUser` binding steps (dry-run by default) |
| **`FIND-03`** | `Medium` | `architecture/trajectory-refinery/src/refinery_engine.py` | `INSTRUCTION_DRIFT_OR_AMBIGUITY` matched generic English words (`error`, `failed`), pruning clean assistant summaries from `L1` output; missing `MISSING_CONTEXT_OR_MEMORY` and `API_OR_PERMISSION_FAILURE` detectors; no runtime schema validation; missing Channel A (`docs-md`) & Channel B (`takeout-json`) parsers and CLI | Covered all 7 `SESSION-RCA-v1` categories; refined drift regex + `RUNTIME_CRASH_RE` so benign assistant prose stays in `L1`; added stdlib `validate_trace_records()` and `validate_rca_payload()`; implemented `parse_docs_export_markdown()`, `parse_takeout_activity_json()`, and standalone `argparse` CLI `main()` |
| **`FIND-04`** | `Medium` | `verify.py` & `.github/workflows/verify-zero-pii.yml` | Local `verify.py` omitted full-repo Zero-PII scanning, `advisories/*.json` schema checks, `index.html`/`HANDOFF_REDACTED.md`/`CA-20261112-001.json` manifest SHA checks, `/` Windows paths, and `github_pat_`/`1//`/`xox*-`/PEM key detection; CI missed `improve/**`, `feat/**`, `fix/**`, `workflow_dispatch`, and IaC dry-run execution | Unified local & CI Zero-PII/schema/manifest verification in `verify.py` (`v8.3.1`), expanded `TOKEN_RE` and `WIN_USER_RE`, added CI branch triggers (`improve/**`, `feat/**`, `fix/**`), `workflow_dispatch`, and `pwsh` IaC dry-run smoke check |
| **`FIND-05`** | `Low` | `HANDOFF_REDACTED.md`, `SECURITY.md`, `README.md` | Loopback IP typo `128.0.0.1:8788` in `HANDOFF_REDACTED.md`; missing root `SECURITY.md`; `README.md` lacked CI badge & review links | Fixed `127.0.0.1:8788` and documented `manifest.json` SSOT; added `SECURITY.md`; added CI badge and module links in `README.md` |
| **`FIND-06`** | `Medium` | `architecture/trajectory-refinery/src/session_bundler.py` | Missed OAuth refresh (`1//*`) and Slack (`xox*-`) Tier-A secret patterns despite docstring guarantee; concatenated unsanitized `session_id`/`date_slug` into bundle path without containment check; `Path(rel_name).name` failed on `..` and silently overwrote colliding product basenames | Added `OAUTH_REFRESH_TOKEN` (`1//*`) & `SLACK_API_SECRET` (`xox*-`) Tier-A patterns, slug sanitization + `.is_relative_to()` containment on `sessions/`, collision-safe `_sanitize_product_filename()`, and LF `bundle_manifest.json` output |

---

## 3. Recommended GitHub Account & Admin Settings Follow-Ups (Outside Repo Code)

These items require repository/account settings changes in the GitHub UI or `gh` admin API and cannot be completed solely by pushing a git branch:

1. **Enable Branch Protection / Ruleset on `lifeops-multi-agent-sim` (`main`):**
   - Require a Pull Request before merging to `main` and require status check **`verify-zero-pii`** to pass (blocking direct unverified pushes to `main`).
2. **Update Repository Metadata & Account Profile:**
   - Update `lifeops-multi-agent-sim` repository description from `(v8.0.0)` to `(v8.3.1)` and add GitHub topics (`multi-agent`, `zero-pii`, `trajectory-refinery`, `cloud-run`, `mcp`, `oidc`).
   - Populate `harmonic-ops-machine` profile bio (marking it as the `HIGHRES Zero-PII Machine Enclave`) and optionally create a `harmonic-ops-machine/harmonic-ops-machine` profile README indexing public specs.
3. **Reconcile Private Vault Repository Name Before Provisioning:**
   - Choose one canonical private repository name between `lifeops-enclave-private` (currently configured in local `$LO_ROOT/simulations/lifeops-enclave-private`) and `gemini-session-refinery` (referenced in `ARCHITECTURE_PL.md` and `provision_gcs_and_oidc.ps1`), create it as **`Private`**, and enable GitHub Secret Scanning / Push Protection + CI verification before pushing `inbox/raw-sessions`.
4. **Standardize CI & Zero-PII Regexes on Smoke-Test Repositories:**
   - Add a lightweight `.github/workflows/verify-zero-pii.yml` workflow to `harmonic-test-alpha` and `harmonic-test-beta`, and tighten `harmonic-test-alpha/scripts/push_turn.py` if any smoke logs are ever promoted publicly.

---

## 4. Verification Summary for Branch `improve/enclave-audit-v8.3.1`

All checks below execute deterministically with zero external dependencies:

- `python verify.py` — Full-repo Zero-PII check across tracked files, `advisories/*.json` schema check, SHA-256 manifest parity, and 34-node/63-edge Kahn DAG validation.
- `python architecture/trajectory-refinery/tests/test_refinery_pipeline.py` — Expanded unit & HTTP integration suite covering L1/L2/L3 distillation, benign-prose preservation, all 7 RCA categories, schema rejection tests, Docs/Takeout parsers, MCP notifications/traversal guards, and HTTP auth/limits/`/healthz`.
- `pwsh -NoProfile -File architecture/trajectory-refinery/scripts/provision_gcs_and_oidc.ps1 -ProjectId "enclave-ci-smoke" -BucketName "enclave-refinery-smoke"` — Dry-run verification of repository-scoped OIDC & GCS IaC commands.
