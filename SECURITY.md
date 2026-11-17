# Security & Zero-PII Policy

## 1. Public Zero-PII Airgap Invariant

This repository (`harmonic-ops-machine/lifeops-multi-agent-sim`) is strictly **Zero-PII**:
- **Zero** email addresses (`*@*.*`)
- **Zero** local Windows host profile paths (`$USERPROFILE` / `$WORKSPACE_HOME`)
- **Zero** OAuth/API tokens, private keys, or credentials (`ya29.*`, `AIza*`, `ghp_*`, `github_pat_*`, `sk-*`, `1//*`, `xox*-`, PEM keys)
- **Zero** private case identifiers or personal infrastructure names

Every commit, pull request, and branch under `main`, `carbon/**`, `improve/**`, `feat/**`, and `fix/**` is verified deterministically via `.github/workflows/verify-zero-pii.yml` and `python verify.py`.

## 2. Subagent Action Destructiveness Policy (4-Tier Gate)

| Tier | Scope | Policy |
| :-: | :--- | :--- |
| **Tier 0** | Read / Observe (`get*`, `list*`, `search*`, `--preflight`) | `Always allow` (Zero-PII gated) |
| **Tier 1** | Bounded Reversible Outbox / Worktree Write | `Always allow` (scoped strictly to own outbox or worktree) |
| **Tier 2** | Shared-State, Destructive, or External Comms | `Always ask` (explicit operator confirmation) |
| **Tier 3** | Billing, Domain Purchase & Identity / Account Links | `Always ask` (human only) / `Never allow` (subagent) |

## 3. Cloud Infrastructure & Authentication Posture

- **Keyless CI/CD:** Cloud provisioning (`architecture/trajectory-refinery/scripts/provision_gcs_and_oidc.ps1`) uses repository-scoped GitHub Actions OIDC Workload Identity Federation (`assertion.repository == '<owner>/<repo>'`) rather than long-lived JSON service-account keys.
- **MCP Endpoint Hardening:** `cloudrun_mcp_ingestor.py` enforces `2 MiB` payload limits, path-safe `session_id` sanitization, strict schema validation, and optional constant-time bearer authentication (`REFINERY_MCP_BEARER_KEY`).

## 4. Reporting a Security Issue

Do not open public issues containing PII, tokens, or unredacted traces. Report security concerns privately via GitHub Security Advisories at:

`https://github.com/harmonic-ops-machine/lifeops-multi-agent-sim/security/advisories`

## 5. Local Verification Commands

```bash
python verify.py
python architecture/trajectory-refinery/tests/test_refinery_pipeline.py
pwsh -NoProfile -File architecture/trajectory-refinery/scripts/provision_gcs_and_oidc.ps1 -ProjectId "enclave-ci-smoke" -BucketName "enclave-refinery-smoke"
```
