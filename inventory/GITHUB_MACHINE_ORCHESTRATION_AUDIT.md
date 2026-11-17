# GitHub Machine Account Capability Audit, Deposit Ledger & Pending Decisions (`v8.3.2`)

- **Audited Account:** `harmonic-ops-machine` (`id: 356038468`, `node_id: U_kgDOFTi3RA`, `type: User`)
- **App Installation:** `antigravity-for-github` (`#182713228`, `client_id: Iv23liuNmlOTgaZ5mkpZ`, `repository_selection: all`)
- **Audited From Surface:** Antigravity Cloud VM (`conversationId: 299a0581-0909-42de-9682-0801c990322b`, standalone non-Project thread)
- **Zero-PII Airgap Attestation:** `0` email addresses, `0` local user paths, `0` tokens or secrets.

---

## 1. What IS Live & Deposited on GitHub (`Verified via REST/GraphQL/Git`)

| Target on `github.com/harmonic-ops-machine` | Current Live State | Verification |
| :--- | :--- | :--- |
| **`lifeops-multi-agent-sim` (`main` branch)** | Live at commit `5b59853` (`16` root items, `SESSION-BUNDLE-v3` templates, `v8.3.0` Trajectory Refinery, `ENCLAVE_CAPABILITIES_AUDIT.md`) | `git ls-remote` + `5/5` green Actions runs |
| **`lifeops-multi-agent-sim` (`improve/enclave-audit-v8.3.1`)** | Pushed at commit `880b0bc` (`+1,158 / -108` across `13` files: `FIND-01`..`FIND-06`, `SECURITY.md`, `reviews/2026-11-16_GITHUB_ACCOUNT_AND_REPO_REVIEW.md`) | **Pushed to remote branch, NOT merged into `main` (`0` open PRs)** |
| **`lifeops-enclave-private` (`PRIVATE` repo)** | Created & populated (`95 KB`, last push `2026-11-16T23:57:06Z`, default branch `main`) | Enclave content isolation holds (`403` to unattached Cloud VMs) |
| **`harmonic-test-alpha` & `harmonic-test-beta` (`PRIVATE`)** | Created (`7 KB` & `1 KB`, last pushes `23:27Z` & `23:22Z`) | Content/clone `403` to unattached Cloud VMs |
| **`users/harmonic-ops-machine/projects/1`** | Created in Web UI (`projectsV2.totalCount: 1`) | **Unusable by App `#182713228`** (`nodes: [null]`, `FORBIDDEN`) |

---

## 2. What Is NOT Yet on GitHub (Staged & Verified, Awaiting Authenticated Push / Admin Run)

### 2.1 Code & Manifest Deliverables (Packaged in `0001-feat-github-orchestration-deposit.patch`)
Blocked from pushing directly out of standalone Cloud thread `299a0581` because `agy-plugin-proxy` strips `contents: write` (`HTTP 403`) whenever `<project_resources>` is unattached:
1. `inventory/GITHUB_MACHINE_ORCHESTRATION_AUDIT.md` *(this ledger)*
2. `inventory/github_machine_orchestration_manifest.json` *(24-surface machine capability & decision JSON)*
3. `architecture/github-orchestration/bootstrap_governance.sh` *(idempotent `gh` CLI installer for merge flags, `main` Ruleset, and swarm labels)*
4. `.github/workflows/agent-orchestration-bus.yml` *(`workflow_dispatch` + `repository_dispatch` + `30m` stale-lease reaper + keyless GCP OIDC hook)*

### 2.2 Session Closeout Archive (`SESSION-BUNDLE-v3`)
- Staged via `session_bundler.py` at `$ARTIFACT_DIR/session_bundle_v3/sessions/2026-11-16_20261116-1355-github-machine-audit/` (`SESSION_CARD.md`, `trajectory.jsonl`, `bundle_manifest.json`, `products/*`), ready to copy/push into `lifeops-enclave-private` (`inbox/raw-sessions`) over `HIGHRES-enclave` SSH.

### 2.3 Live GitHub Repository & Account Admin Settings (Currently Unapplied on GitHub)
- **Repository Ruleset on `main`:** Currently `[]` (empty — direct pushes and workflow self-edits are still possible).
- **Merge Hygiene Flags:** `allow_auto_merge`, `delete_branch_on_merge`, `allow_update_branch` are `null`; `has_discussions` is `false`.
- **Swarm Label Taxonomy:** Only GitHub's `9` default human labels exist (`state:*`, `actor:*`, `prio:*`, `gate:*` labels not yet created).

---

## 3. Six Pending Operator Decisions

| Decision ID | Decision Required | Recommended Default | Why It Blocks / Matters |
| :--- | :--- | :--- | :--- |
| **`DEC-GH-01`** | **Reconcile & merge `improve/enclave-audit-v8.3.1` (`880b0bc`) into `main` (`5b59853`)** | Rebase/merge `880b0bc` onto `5b59853`, regenerate `manifest.json` SHA-256 entries, and open/merge PR | `main` (`5b59853`) has `SESSION-BUNDLE-v3` docs while `880b0bc` holds hardened `v8.3.1` `verify.py` & `refinery_engine.py` |
| **`DEC-GH-02`** | **Migrate repos to a free GitHub Organization vs. stay on solo `User` `harmonic-ops-machine`** | Create free Org (`harmonic-ops`) with separate Proposer (`harmonic-ops-machine`) and Approver (`CODEOWNERS`) seats | Solo `User` cannot self-approve PRs or enforce independent `CODEOWNERS` on `.github/workflows/**` & `verify.py` |
| **`DEC-GH-03`** | **App `#182713228` (`antigravity-for-github`) repository visibility scope** | Switch from **All repositories** to **Only select repositories** (exclude `lifeops-enclave-private` unless actively needed) | `repository_selection: all` currently leaks private repo names, KB sizes, and push timestamps to unattached Cloud chats |
| **`DEC-GH-04`** | **Retire GitHub Projects v2 (`projects/1`) in favor of Issues/Sub-Issues + `gsheets` Ledger** | Close `users/harmonic-ops-machine/projects/1`; standardize on GraphQL `addSubIssue` + `state:*` labels + `gsheets` | `antigravity-for-github` lacks `ProjectV2` permission (`nodes: [null]`, `403` even on public boards) |
| **`DEC-GH-05`** | **Decouple `CONTINUITY_CHECKPOINT.json` per-turn heartbeats from `main` git history** | Keep `main` strictly for verified code/specs; move `1800s` heartbeats to Issue leases, Spacefast outbox, or GCS OIDC | Per-turn commits to `main` cause `non-fast-forward` push races once Cloud + Local agents execute concurrently |
| **`DEC-GH-06`** | **Scope Workspace Cross-Integration (`SEAT_A_PRIMARY_HUB`) to dedicated sandbox IDs** | Pin a dedicated `gdrive` root `FOLDER_ID` and secondary `gcalendar` ID in Project instructions | Prevents autonomous Cloud sessions from mutating root Drive or primary Calendar on `SEAT_A_PRIMARY_HUB` |
