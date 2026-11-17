# HIGHRES Enclave Architecture, Capabilities Audit & Trajectory Refinery (`v8.3.1`)

[![Zero-PII & Refinery CI](https://github.com/harmonic-ops-machine/lifeops-multi-agent-sim/actions/workflows/verify-zero-pii.yml/badge.svg)](https://github.com/harmonic-ops-machine/lifeops-multi-agent-sim/actions/workflows/verify-zero-pii.yml)

Cryptographically verified, **100% Zero-PII** multi-agent architecture, runtime capabilities inventory, and turnkey **Trajectory Refinery** (`Gemini App -> GCS Bronze + Private GitHub Vault -> Separate Auditor Agent`) maintained by machine account `harmonic-ops-machine`.

---

## Repository Modules (Reviewed & Hardened in `v8.3.1`)

| Module | Path | Description |
| :--- | :--- | :--- |
| **1. Enclave Capabilities & Connections Audit** | [`inventory/ENCLAVE_CAPABILITIES_AUDIT.md`](inventory/ENCLAVE_CAPABILITIES_AUDIT.md)<br>[`inventory/enclave_capabilities_manifest.json`](inventory/enclave_capabilities_manifest.json) | Complete, empirically verified review of active connections, `49` plugins (`15` enabled / `34` disabled for context budget), `54` skill slots, `6` lazy MCP servers (`37` tools), `hooks.json` (`11` `PreToolUse` invariants), automations, and runtime preferences. |
| **2. Trajectory Refinery Implementation Architecture (PL)** | [`architecture/trajectory-refinery/ARCHITECTURE_PL.md`](architecture/trajectory-refinery/ARCHITECTURE_PL.md) | Turnkey deployment architecture (`L0`–`L4`) pairing versioned **Google Cloud Storage (`GCS`)** with a **private GitHub vault** and an isolated **Auditor/Distiller Agent** (`distilled/`, `postmortems/`, `patches/`). |
| **3. Formal Trace & RCA JSON Schemas** | [`architecture/trajectory-refinery/schemas/session_trace.schema.json`](architecture/trajectory-refinery/schemas/session_trace.schema.json)<br>[`architecture/trajectory-refinery/schemas/session_rca.schema.json`](architecture/trajectory-refinery/schemas/session_rca.schema.json) | Canonical `SESSION-TRACE-v1` (turn-by-turn black-box JSONL) and `SESSION-RCA-v1` (root-cause classification & guardrail patch proposals). |
| **4. Reference Refinery Engine, Bundler & 1-Tool Cloud Run MCP** | [`architecture/trajectory-refinery/src/refinery_engine.py`](architecture/trajectory-refinery/src/refinery_engine.py)<br>[`architecture/trajectory-refinery/src/session_bundler.py`](architecture/trajectory-refinery/src/session_bundler.py)<br>[`architecture/trajectory-refinery/src/cloudrun_mcp_ingestor.py`](architecture/trajectory-refinery/src/cloudrun_mcp_ingestor.py)<br>[`templates/SESSION_CLOSEOUT_TEMPLATE.md`](templates/SESSION_CLOSEOUT_TEMPLATE.md) | Zero-dependency Python 3.12 signal/noise separator, 7-category incident classifier, Docs/Takeout parsers, strict schema validators, tiered secret-scrubbing session bundler + closeout templates, PR patch generator, and hardened single-tool (`archive_gemini_session`) MCP server with auth, `/healthz`, and payload bounds. |
| **5. Stage-Gated GCS + Keyless GitHub OIDC IaC** | [`architecture/trajectory-refinery/scripts/provision_gcs_and_oidc.ps1`](architecture/trajectory-refinery/scripts/provision_gcs_and_oidc.ps1) | Dry-run-by-default PowerShell provisioning (`Invoke-Expression`-free) for GCS (`Object Versioning` + `30d Soft Delete` + `Public Access Prevention`), least-privilege Service Account, and repository-scoped keyless GitHub Actions OIDC Workload Identity Federation. |
| **6. Multi-Agent Isolation DAG & Live Continuity** | [`simulation_spec.json`](simulation_spec.json)<br>[`CONTINUITY_CHECKPOINT.json`](CONTINUITY_CHECKPOINT.json)<br>[`verify.py`](verify.py) | `34`-node, `63`-edge topological dependency & leakage-fence graph (`L1`–`L9`) with SHA-256 manifest verification and full-repository Zero-PII scanning. |
| **7. Account & Architecture Review (`v8.3.1`)** | [`reviews/2026-11-16_GITHUB_ACCOUNT_AND_REPO_REVIEW.md`](reviews/2026-11-16_GITHUB_ACCOUNT_AND_REPO_REVIEW.md) | Comprehensive audit of `harmonic-ops-machine` repositories, Projects v2, security posture, and hardening improvements shipped on branch `improve/enclave-audit-v8.3.1`. |
| **8. Security & Zero-PII Policy** | [`SECURITY.md`](SECURITY.md) | Zero-PII airgap policy, 4-Tier Subagent Action Destructiveness Gate, keyless OIDC rules, and private advisory reporting process. |

---

## Independent Verification (Local or CI)

```bash
# 1. Verify Zero-PII airgap, SHA-256 manifest parity, advisories, and 34-node DAG invariants
python verify.py

# 2. Run Trajectory Refinery end-to-end unit & HTTP/MCP contract tests
python architecture/trajectory-refinery/tests/test_refinery_pipeline.py

# 3. Preview (Dry-Run) GCS Bronze bucket & repository-scoped OIDC provisioning
pwsh -NoProfile -File architecture/trajectory-refinery/scripts/provision_gcs_and_oidc.ps1 -ProjectId "enclave-ci-smoke" -BucketName "enclave-refinery-smoke"
```

> **History Note:** Public `main` is rooted at `v7.0.0+` (`0` PII across all commits and blobs). Earlier pre-`v7.0` development commits remain archived exclusively on an unpushed local workstation branch for future review as the project progresses.
