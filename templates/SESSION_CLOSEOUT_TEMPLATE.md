---
schema: SESSION-BUNDLE-v3
session_id: "YYYYMMDD-HHMM-<short-topic-slug>"
started_at_hst: "YYYY-MM-DDTHH:MM:SS-10:00"
ended_at_hst: "YYYY-MM-DDTHH:MM:SS-10:00"
status: "completed"                    # completed | paused | blocked
project_domain: "life-ops"             # life-ops | infra | workspace-bi | gdrive-remediation | legal-en
destination_repo: "harmonic-ops-machine/lifeops-enclave-private"
destination_branch: "inbox/raw-sessions"
bundle_dir: "sessions/YYYY-MM-DD_<session_id>/"
environment:
  host_and_os: "<e.g. HIGHRES Windows 11 / PowerShell 5.1 / Python 3.12.14 | Gemini Web Cloud UI>"
  agent_surface: "<antigravity_ide | gemini_app_web | gemini_cli | claude_code_cli>"
  conversation_or_thread_id: "<UUID or https://gemini.google.com/u/0/app/...>"
  active_workspace: "<e.g. $WORKSPACE_HOME\\HIGHRES-Workspace.code-workspace | none>"
  model_and_tier: "<e.g. Gemini 4 Carbon (High) | Claude Code 2.1.321 fable>"
  execution_and_sandbox_posture: "<e.g. TURBO + terminalSandbox=false + hooks.json PreToolUse 11 invariants>"
visibility_and_scrub_policy:
  repo_visibility: "private"
  tier_a_secrets_scrubbed: true        # MANDATORY: 0 passwords, OAuth/API tokens, private keys, cookies, or 2FA codes
  tier_b_entities_preserved: true      # INTENTIONAL IN PRIVATE: keep exact emails, GCP IDs, $WORKSPACE_HOME paths & product text
  public_zero_pii_exportable: false
raw_gcs_uri: "gs://enclave-session-refinery/sessions/<session_id>/trajectory.jsonl"
products_count: 0
---

# Session Full-Work Upload Manifest (`SESSION-BUNDLE-v3`): `<Short Title>`

> **Follow [`templates/SESSION_UPLOAD_INSTRUCTIONS.md`](SESSION_UPLOAD_INSTRUCTIONS.md) strictly.** Populate all 9 sections below with exact technical provenance. **Never reveal raw secrets** (passwords, bearer/refresh tokens, API keys, private keys, cookie values, or verification codes), while **being 100% explicit** about which accounts, OAuth scopes, SSH public fingerprints, environments, skills, plugins, and generated file links were used.

---

## 1. Runtime Environment & Subagent Provenance
- **Host, OS & Shell / Toolchains:** `<exact OS, shell, Python/Node/Git/gcloud versions>`
- **Surface, Conversation ID & Workspace Root:** `<surface + conversation://ID or thread URL + workspace path>`
- **Model, Permission Preset & Hook Guardrails:** `<model + preset + active hooks>`
- **Subagents / Background Daemons Used:**
  - `<subagent conversationId | type | model | role | visited_origins / blocked_origins — or "None">`

---

## 2. Skills, Plugins, MCP Servers & Automations Provenance
*List specifically what was activated, invoked, or triggered in this session (plus any relevant skill/plugin found disabled or missed).*

| Capability Type (`skill` / `plugin` / `mcp_tool` / `hook` / `daemon`) | Exact Name / Identifier | Path, Server, or Version | How Used in This Session (or Why Missed/Disabled) |
| :--- | :--- | :--- | :--- |
| `skill` | `<e.g. enforcing-resource-attribution>` | `<file:///$WORKSPACE_HOME/SKILL.md>` | `<Read & applied CLOUDSDK_METRICS_ENVIRONMENT>` |
| `plugin` | `<e.g. gdrive / data-agent-kit-plugin>` | `<v0.0.11 / enabled>` | `<Used for ...>` |
| `mcp_tool` | `<e.g. dak-bigquery:execute_sql_readonly>` | `<lazy MCP>` | `<Queried ... — or "None invoked">` |
| `hook` | `<e.g. pretool_single_hub_guard.py>` | `<hooks.json PreToolUse>` | `<Enforced Invariant 5 / intercepted ...>` |

---

## 3. Accounts, OAuth Grants & Non-Secret Credential Provenance (Zero Secrets!)
*Specify every application/API touched, the exact account/principal used, the authentication mechanism, and non-secret credential identifiers (public key fingerprint, key title, `cmdkey` target name, OAuth scopes). **NEVER include secret tokens, passwords, private keys, or verification codes.***

| Application / Service | Bound Account / Principal / Project | Auth Mechanism & Session Slot | Non-Secret Credential ID / Fingerprint / OAuth Scopes Used | Boundary / Guardrail Enforced |
| :--- | :--- | :--- | :--- | :--- |
| `<e.g. GitHub Git/SSH>` | `harmonic-ops-machine` (`356038468+...`) | `OpenSSH Ed25519 (IdentitiesOnly)` | `Key title: HIGHRES-enclave · Pub: ~/.ssh/id_ed25519_harmonic_ops.pub · SHA256:5fuFR0nA...` | `PreToolUse Invariant 11 (LEGACY_PERSONAL_GITHUB clone-only)` |
| `<e.g. Google Cloud / GCS>` | `SEAT_A_PRIMARY_HUB` (`$GCP_ENCLAVE_PROJECT`) | `gcloud SDK user OAuth` | `Active gcloud config default · CLOUDSDK_METRICS_ENVIRONMENT=datacloud.antigravity` | `public_access_prevention=enforced` |
| `<e.g. Gemini Web App>` | `SEAT_A_PRIMARY_HUB` | `WebView Google Session (/u/0/ only)` | `/u/0/ cookie slot · Connectors: @GitHub, Google Workspace, Contacts, Adobe` | `Never touch /u/1/ or disconnect 1P capabilities` |
| `<e.g. Google Drive CLI>` | `SEAT_A_PRIMARY_HUB` | `Antigravity Plugins Manager OAuth2` | `Provider: google (oauth2) · Scopes: auth/drive, auth/userinfo.email · AGY_ACCOUNT injected` | `PreToolUse Invariant 3 & 5` |

- **Secret-Exclusion Attestation:** Confirmed `0` raw passwords, `0` OAuth access/refresh tokens, `0` API keys, `0` private keys, `0` cookie strings, and `0` verification codes appear in this bundle.

---

## 4. Complete Generated & Modified Files Inventory (Bundled Copies + Live Links)
*List every file, artifact, report, script, screenshot, or cloud object generated or modified during the session, providing clickable live links (`file:///`, `https://github.com/...`, `gs://...`, or Docs URL) alongside bundled `products/` copies.*

| # | Bundled Copy (`products/...` or `none`) | Original / Live File or Cloud Link (if still available) | Availability Status (`AVAILABLE_VERIFIED` / `BUNDLED_ONLY_EPHEMERAL_SOURCE` / `SUPERSEDED_OR_REMOVED`) | Bytes | SHA-256 | Purpose & Verification |
| :-: | :--- | :--- | :--- | ---: | :--- | :--- |
| 1 | `products/<file.ext>` | `[<file.ext>](file:///$WORKSPACE_HOME)` | `AVAILABLE_VERIFIED` | `0` | `<sha256>` | `<What it is & how verified>` |

---

## 5. Verified Outcomes & Binding Decisions (`L1 Signal — Promote to main/distilled/`)
- **Primary User Objective:** `<1 sentence>`
- **Binding Decisions & Architecture Choices:**
  - `<Decision 1 — exact target + rationale>`
- **Live Mutations / Commits / Cloud Changes Completed:**
  - `<Commit SHA / URL / resource changed>`

---

## 6. Pruned Dead Ends & Noise Turn Ranges (`L1 Noise Filter — Strip from Active Context`)

| Turn Range | Noise / Dead-End Type (`voice_cutoff` / `idle_ping` / `abandoned_approach` / `duplicate_retry`) | What Was Dropped & Why Future Sessions Must Not Re-Try It |
| :--- | :--- | :--- |
| `Turns <A>-<B>` | `<type>` | `<1-line anti-pattern summary>` |

---

## 7. Forensic Error, ASR & Operator Correction Ledger (`L2 Root-Cause Analysis Input`)

| Turn # | Taxonomy Code | Exact Symptom / Failure / User Correction | Root Cause (Why It Happened — Env / Auth / Skill / ASR) | Applied Fix & Optimal Systemic Solution |
| :-: | :--- | :--- | :--- | :--- |
| `<N>` | `<ASR_VOICE_MISRECOGNITION \| TOOL_OR_CONNECTOR_LIMITATION \| ENVIRONMENT_CONFIG_MISMATCH \| INSTRUCTION_DRIFT_OR_AMBIGUITY \| PREMATURE_COMPLETION_CLAIM \| MISSING_CONTEXT_OR_MEMORY \| API_OR_PERMISSION_FAILURE>` | `<Observed failure>` | `<Underlying cause>` | `<Applied fix + long-term fix>` |

---

## 8. Candidate System Guardrail / Skill / Hook Patches (`L3 Self-Healing Input`)
- **Target Control File:** `<GEMINI.md | AGENTS.md | gemini_web_saved_info | SKILL.md | pretool_single_hub_guard.py | none>`
- **Proposed Addition / Modification:**
  ```markdown
  <Exact rule, skill check, or PreToolUse invariant>
  ```

---

## 9. Next-Session Handoff & Open Approval Gates (`L4 Cross-Agent Continuity`)
1. `[ ]` **Next Concrete Action:** `<Step 1>`
2. `[?]` **Open Operator Decision / Gate:** `<Question or None>`
