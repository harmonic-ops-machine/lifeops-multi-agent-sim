# HIGHRES Enclave Architecture, Capabilities Audit & Trajectory Refinery (`v8.3.0`)

Cryptographically verified, **100% Zero-PII** multi-agent architecture, runtime capabilities inventory, and turnkey **Trajectory Refinery** (`Gemini App -> GCS Bronze + Private GitHub Vault -> Separate Auditor Agent`) maintained by machine account `harmonic-ops-machine`.

---

## Repository Modules (Ready for Architectural & Code Review)

| Module | Path | Description |
| :--- | :--- | :--- |
| **1. Enclave Capabilities & Connections Audit** | [`inventory/ENCLAVE_CAPABILITIES_AUDIT.md`](inventory/ENCLAVE_CAPABILITIES_AUDIT.md)<br>[`inventory/enclave_capabilities_manifest.json`](inventory/enclave_capabilities_manifest.json) | Complete, empirically verified review of active connections, `49` plugins (`15` enabled / `34` disabled for context budget), `54` skill slots, `6` lazy MCP servers (`37` tools), `hooks.json` (`11` `PreToolUse` invariants), automations, and runtime preferences. |
| **2. Trajectory Refinery Implementation Architecture (PL)** | [`architecture/trajectory-refinery/ARCHITECTURE_PL.md`](architecture/trajectory-refinery/ARCHITECTURE_PL.md) | Turnkey deployment architecture (`L0`–`L4`) pairing versioned **Google Cloud Storage (`GCS`)** with a **private GitHub vault** and an isolated **Auditor/Distiller Agent** (`distilled/`, `postmortems/`, `patches/`). |
| **3. Formal Trace & RCA JSON Schemas** | [`architecture/trajectory-refinery/schemas/session_trace.schema.json`](architecture/trajectory-refinery/schemas/session_trace.schema.json)<br>[`architecture/trajectory-refinery/schemas/session_rca.schema.json`](architecture/trajectory-refinery/schemas/session_rca.schema.json) | Canonical `SESSION-TRACE-v1` (turn-by-turn black-box JSONL) and `SESSION-RCA-v1` (root-cause classification & guardrail patch proposals). |
| **4. Reference Refinery Engine & 1-Tool Cloud Run MCP** | [`architecture/trajectory-refinery/src/refinery_engine.py`](architecture/trajectory-refinery/src/refinery_engine.py)<br>[`architecture/trajectory-refinery/src/cloudrun_mcp_ingestor.py`](architecture/trajectory-refinery/src/cloudrun_mcp_ingestor.py) | Zero-dependency Python 3.12 signal/noise separator, incident classifier, PR patch generator, and single-tool (`archive_gemini_session`) MCP server eliminating 485-tool connector bloat. |
| **5. Stage-Gated GCS + Keyless GitHub OIDC IaC** | [`architecture/trajectory-refinery/scripts/provision_gcs_and_oidc.ps1`](architecture/trajectory-refinery/scripts/provision_gcs_and_oidc.ps1) | Dry-run-by-default PowerShell provisioning for GCS (`Object Versioning` + `30d Soft Delete` + `Public Access Prevention`) and keyless GitHub Actions OIDC Workload Identity Federation. |
| **6. Multi-Agent Isolation DAG & Live Continuity** | [`simulation_spec.json`](simulation_spec.json)<br>[`CONTINUITY_CHECKPOINT.json`](CONTINUITY_CHECKPOINT.json)<br>[`verify.py`](verify.py) | `34`-node, `63`-edge topological dependency & leakage-fence graph (`L1`–`L9`) with SHA-256 manifest verification. |

---

## Independent Verification (Local or CI)

```bash
# 1. Verify Zero-PII airgap, SHA-256 manifest parity, and 34-node DAG invariants
python verify.py

# 2. Run Trajectory Refinery end-to-end unit & MCP contract tests
python architecture/trajectory-refinery/tests/test_refinery_pipeline.py
```

> **History Note:** Public `main` is rooted at `v7.0.0+` (`0` PII across all commits and blobs). Earlier pre-`v7.0` development commits remain archived exclusively on an unpushed local workstation branch for future review as the project progresses.
