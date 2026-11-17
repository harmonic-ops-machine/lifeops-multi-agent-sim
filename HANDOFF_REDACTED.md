# Multi-Agent Governance, Zero-PII Leakage Fence & Carbon Closed-Loop Handoff (`v8.0.0`)

- **Schema / Bundle Version:** `v8.0.0` (`CARBON-FEED-v1` / `CARBON-ADVISORY-v1`)
- **Released At (HST):** `2026-11-12T13:30:29-10:00`
- **Simulation Spec SHA-256:** `3390eef53df405724a9eef5590cdb6604f519285c3b740a8ef1726259c18c590`
- **Carbon Telemetry Feed SHA-256:** `cfa5b4abde334f3724d58f2865ec880f526995b4a6109dd474dfcf0301dbd53e`
- **Public Airgap Policy:** **Zero-PII Enforced (`0` emails, `0` tokens, `0` local user paths, `0` unredacted case captions)**. Full unredacted operational paths reside strictly on local NVMe inside `$LO_ROOT/reports/`.

---

## 1. System Topology & Structural Aliases

| Structural Alias | Operational Role | Isolation Boundary |
| :--- | :--- | :--- |
| **`hub:primary`** | Single-Account Automation Hub | Read-only Gmail, canonical Drive SSOT (`THE SOURCE`), BigQuery KG IAM on `gcp:legal_kg_primary` |
| **`id:principal_legal`** | External Legal / Correspondence Domain | Super-Admin auto-forward + IAM `Viewer`-only Calendar/Drive share into `hub:primary` |
| **`id:hospitality_ro`** | Hospitality BI Domain | Strict IAM `Viewer`-only share into `hub:primary` (`0` mutations permitted) |
| **`id:frozen_archive`** | Frozen Archive Account | Hard-banned at engine level (`PreToolUse` Invariant 1) |
| **`CASE-DC-507` / `CASE-ICA-028`** | Trial (`507/507`) & Appellate (`28/28`) Record | `738`-node, `1,223`-edge Property Graph (`100%` FK parity) + Tier-3 `LEG-GATE1` human sign-off |

---

## 2. Nine-Surface Data & Clipboard Leakage Matrix (`L1`–`L9`)

1. **`L1` — `Soniox` Voice Dictation <-> Win32 Global Clipboard Race:** `soniox.exe` pastes transcribed speech via Win32 Clipboard + `SendInput(Ctrl+V)` and restores prior clipboard state. Concurrent agent/script clipboard writes (`Set-Clipboard`/`clip.exe`) or UI `Copy` clicks risk pasting secrets into LLM prompts or stripping privacy formats on restore. **Mitigation:** `PreToolUse` Invariant 8 hard-blocks all shell clipboard reads/writes; UI `Copy` actions require idle dictation confirmation.
2. **`L2` — Windows 11 Clipboard History (`Win+V` / `cbdhsvc`):** `EnableClipboardHistory=1` without `ExcludeClipboardContentFromMonitorProcessing` persists dictated utterances and copied text in local history. **Mitigation:** Zero-content-read `GetClipboardSequenceNumber()` + format-tag monitor; disable `EnableClipboardHistory` (`0`) during vault/legal work.
3. **`L3` — `Bitwarden` Vault Clipboard Window:** `PreToolUse` Invariants 7 & 8 block `hermes secrets`, `bw` CLI, vault files, and clipboard scraping.
4. **`L4` — `ShareX` & Desktop CUA (`ChatGPT cua_node` / `Claude computer-use`):** `PreToolUse` Invariant 9 blocks `ShareX` CLI uploads; CUA foreground automation stays off while `Soniox` dictation is active.
5. **`L5` — Gemini App (`Carbon` Task Mode) Shared-Account `@Google Workspace` Bypass:** Cloud `@Workspace` extensions run outside local `hooks.json`. **Mitigation:** Gemini `Carbon` operates under a strict **Passive Read-Only Advisory Charter**, consuming `carbon_loop_feed.json` and emitting `CARBON-ADVISORY-v1` proposals quarantined in `$LO_ROOT/staged_manifests/carbon_advisories/`.
6. **`L6` — `GoogleDriveFS` Virtual Mounts (`G:` / `H:`):** `PreToolUse` Invariant 6 blocks all local file/shell/`.git` writes to virtual mounts.
7. **`L7` — Session Transcripts (`transcript_full.jsonl`) & Temp CLI Shims:** Probes inspect integer counters and booleans only—never secret values or clipboard text.
8. **`L8` — Public HTTPS & Outbound Webhooks:** `verify_zero_pii()` deterministically blocks any payload containing email addresses, tokens, local user paths, or case PII.
9. **`L9` — Localhost `:8788` CORS Scraping:** Strict `Origin` allowlist returns `403 Forbidden` to arbitrary browser tabs.

---

## 3. Gemini App (`Carbon` Model in Task Mode) Closed-Loop Protocol

### Mode A — On-Prompt / Scheduled Task Mode Pull
Point Gemini (`Carbon` in Task Mode) to:
- `https://harmonic-garden.space.fast/carbon_loop_feed.json`
- `https://harmonic-garden.space.fast/simulation_spec.json`

### Mode B — Event/Webhook Push & Quarantine Ingest
- **Outbound Sanitized Webhook:** `python "$WIRE_BIN/carbon_leakage_loop.py" --dispatch-sanitized <HTTPS_RELAY_URL>` (HMAC-SHA256 signed `X-Carbon-Signature-256`, `verify_zero_pii()` gated) or Spacefast build/publish webhook.
- **Canonical Manifest SSOT (`v8.2.0+`):** Exact SHA-256 digests and byte lengths for every released bundle artifact are tracked in [`manifest.json`](manifest.json).
- **Inbound Quarantine Endpoint:** `POST http://127.0.0.1:8788/api/carbon-advisory` (or `--ingest-file`) validates `CARBON-ADVISORY-v1` schema and stages proposals for `Seat A` + `Codex V-0` + `Hermes --safe-mode` + Human sign-off.

## v8.0.0 Single Designated Local Executor & Automated Spacefast Sync
- **Single Local Executor Broker:** `$WIRE_BIN/designated_local_executor.py` (`Claude Code 2.1.321 --model fable --restricted` + Win32 Named Mutex + Dual-Engine `PreToolUse` Guard).
- **Zero-Port Spacefast Return Channel:** `prior_work_digest.json` (`CARBON-WORKFLOW-DIGEST-v1`) <-> `createSpaceVersionComment` / `listSpaceVersionComments` on `/prior_work_digest.json`.
