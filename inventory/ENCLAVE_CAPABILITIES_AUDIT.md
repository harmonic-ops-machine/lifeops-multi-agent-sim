# HIGHRES Enclave Capabilities, Connections & Runtime Audit (`v8.3.0` — Zero-PII)

- **Audit Timestamp (`HST` / `UTC-10`):** `2026-11-16T13:10:00-10:00`
- **Repository:** `https://github.com/harmonic-ops-machine/lifeops-multi-agent-sim`
- **Zero-PII Airgap:** Verified (`0` personal emails, `0` host user paths, `0` tokens, `0` private case identifiers; personal account identifiers are mapped to deterministic role aliases `SEAT_A_PRIMARY_HUB`, `SEAT_B_LEGACY_PERSONAL`, `SEAT_C_READONLY_BI`, `FROZEN_LEGACY_ACCOUNT`, and `LEGACY_PERSONAL_GITHUB`).

---

## 1. Connections & Identity Boundaries

| Surface | Active Identity / Role Alias | Transport & Scope | Enforcement Mechanism | Status |
| :--- | :--- | :--- | :--- | :---: |
| **Google WebView Enclave** | `SEAT_A_PRIMARY_HUB` (`/u/0/` Ultra) | Browser session on `gemini.google.com/u/0/` (`0` secondary accounts visible) | `/u/0/` pinning + Saved Info global rules | `LIVE` |
| **GitHub Machine Account** | `harmonic-ops-machine` | OpenSSH Ed25519 key `HIGHRES-enclave` + global `.gitconfig` + WebView session | `IdentitiesOnly yes` + `PreToolUse` **Invariant 11** | `LIVE` |
| **Legacy Personal GitHub** | `LEGACY_PERSONAL_GITHUB` | Detached (`0` stored credentials in OS Credential Manager) | Read-only HTTPS `git clone` on demand only; pushes/auth hard-blocked by **Invariant 11** | `FENCED` |
| **Google Cloud (`gcloud` / `bq` / `GCS`)** | `SEAT_A_PRIMARY_HUB` (`$GCP_ENCLAVE_PROJECT`) | Cloud SDK + GCS (`public_access_prevention=enforced`) + BigQuery | `CLOUDSDK_METRICS_ENVIRONMENT=datacloud.antigravity` + `datacloud:antigravity` job labels | `LIVE` |
| **Google Workspace CLIs** | `SEAT_A_PRIMARY_HUB` (default) | `gmail`, `gdrive`, `gdocs`, `gsheets`, `gcalendar` sandboxed OAuth CLIs | `PreToolUse` **Invariant 3, 4, 5** auto-injects `AGY_ACCOUNT` for `SEAT_A_PRIMARY_HUB` & blocks mail send/delete/trash | `LIVE` |
| **Workspace Secondary OAuth Slots** | `SEAT_B_LEGACY_PERSONAL`, `SEAT_C_READONLY_BI` | Stored in Plugins Manager on `gdrive`, `gdocs`, `gsheets`, `gcalendar` (`gmail` is single-account `SEAT_A_PRIMARY_HUB`; `gslides` is disconnected) | Blocked from unprefixed/write execution by `PreToolUse` **Invariant 4 & 5** | `GATED` |
| **Frozen / Paused Surfaces** | `FROZEN_LEGACY_ACCOUNT` & `email-blitz` | Zero access / execution paused | Hard-blocked at engine level by `PreToolUse` **Invariant 1 & 2** | `LOCKED` |
| **Gemini Web `/u/0/` Connectors** | `SEAT_A_PRIMARY_HUB` | `@GitHub` (`Installed`, read-only), `Google Workspace` (`Protected`), `Contacts` (`Protected`), `Adobe` (`Protected`); `@Spacefast` detached (`+ Add`) | Protected-capability rule (`NEVER disconnect` 1P Google or linked SSO) | `VERIFIED` |
| **Designated Local Code Executor** | `Claude Code CLI 2.1.321 --model fable` | `$WORKSPACE_HOME/wire/bin/designated_local_executor.py` | Win32 Mutex `Local\HighresDesignatedExecutorLock_v8` + SHA-256 ticket (`cloud` default, `--restricted` fallback) | `LIVE` |

---

## 2. Installed Plugins (`49` Total: `15` Active, `34` Disabled for Context Budget)

### 2.1 Active Plugins (`15`)
| # | Plugin Directory | Source | Role in Enclave |
| :-: | :--- | :--- | :--- |
| 1 | `browse` | Marketplace (`partners`, `v0.3.0`) | Browserbase / web fetch & automation CLI |
| 2 | `data-agent-kit-plugin` | Marketplace (`official`, `v1.2.0`) | BigQuery, Knowledge Catalog, Notebooks, Optimization, Observability, Troubleshooting (`4` lazy MCPs + `8` skills) |
| 3 | `egm` | Marketplace (`official`, `v0.1.1`) | `10` specialized Goldfish adversarial review subagents (`design`, `zoom-out`, `codebase-details`, `comprehension`, `implementation-readiness`, `inventive-catalyst`, `structural`, `style`, `synthesizer`, `bootstrap-orchestrator`) |
| 4 | `gcalendar` | Marketplace (`official`, `v0.0.8`) | Google Calendar CLI (`SEAT_A_PRIMARY_HUB` default) |
| 5 | `gdocs` | Marketplace (`official`, `v0.0.9`) | Google Docs CLI (`SEAT_A_PRIMARY_HUB` default) |
| 6 | `gdrive` | Marketplace (`official`, `v0.0.11`) | Google Drive API v3 CLI (`SEAT_A_PRIMARY_HUB` default) |
| 7 | `gdrive-remediator` | Custom Local Plugin | Stage-gated 7-step forensic Drive/DriveFS incident remediation (`gdrive-remediator` subagent + safety rules) |
| 8 | `gmail` | Marketplace (`official`, `v0.0.7`) | Gmail read-only CLI (`SEAT_A_PRIMARY_HUB` single-account; send/delete/trash blocked by hook) |
| 9 | `gsheets` | Marketplace (`official`, `v0.0.8`) | Google Sheets CLI (`SEAT_A_PRIMARY_HUB` default) |
| 10 | `highres-workspace` | Custom Local Plugin | Canonical HIGHRES workstation rules (`AGENTS.md`) + `station-onboard` diagnostics |
| 11 | `keenable` | Marketplace (`partners`, `v1.1.0`) | Web search & page reader (`keenable` lazy MCP + `keenable-web` skill) |
| 12 | `parallel` | Marketplace (`partners`, `v0.10.1`) | Parallel web search & fetch (`parallel-search` lazy MCP) |
| 13 | `plugin-manager` | Custom Local Plugin | Chat-native plugin inventory & OAuth account management |
| 14 | `superpowers` | Marketplace (`partners`, `v7.0.2`) | `12` structured engineering skills (`brainstorming`, `writing-plans`, `test-driven-development`, `systematic-debugging`, `verification-before-completion`, etc.) |
| 15 | `swarm` | Built-in (`enabled: true`) | Native multi-agent message-board swarm coordinator & monitor |

### 2.2 Disabled Plugins (`34` — Intentionally Off to Preserve Context Window)
`android-cli-plugin`, `canva`, `chrome-devtools-plugin`, `context7`, `databricks`, `dynatrace`, `figma`, `firebase`, `flutter`, `gemini-api`, `google-antigravity-sdk`, `google-cloud-developer`, `google-developer-knowledge`, `google_maps_platform`, `googlecloudtools.datacloud_telemetry`, `gslides`, `invideo`, `linear`, `looker`, `mobbin`, `modern-web-guidance-plugin`, `neo4j`, `netlify`, `notion`, `pandadoc`, `science`, `semrush`, `spacefast`, `stripe`, `supabase`, `unity`, `vercel-plugin`, `wix`, `wordpress`.

---

## 3. Skills Inventory (`54` Active Slots) & Deduplication Finding

- **Global Standalone Skills (`7` in `~/.gemini/config/skills/`):**
  `accidental-data-loss-prevention`, `agentic-governance-harness`, `bigquery-graph-author`, `bigquery-graph-query`, `enforcing-resource-attribution`, `single-enclave-carbon-loop`, `skill-repair`.
- **Built-in Platform Skills (`14` on disk, `9` surfaced in active prompt):**
  `agy-customizations`, `antigravity-guide`, `automation`, `generative_ui`, `migrate-agent-settings`, `migrate-workflows`, `plugin`, `run-workflow`, `swarm`, `swarm_monitor`, `ui-plugin-navigation` *(plus internal `mcp-app-development`, `permissioned-github`, `swarm_narrator`)*.
- **Plugin-Provided Active Skills (`33`):**
  `data-agent-kit-plugin` (`8`), `superpowers` (`12`), Google Workspace (`5`), `browse` (`1`), `keenable` (`1`), `plugin-manager` (`1`), `gdrive-remediator` (`1`), `highres-workspace` (`1`), plus shared safety/graph skills.
- **Audit Optimization Finding (`SKILL-DEDUP-01`):**
  Three skills (`accidental-data-loss-prevention`, `bigquery-graph-author`, `bigquery-graph-query`) exist **both** in `~/.gemini/config/skills/` and inside `data-agent-kit-plugin/skills/`, appearing twice in the system prompt. Archiving the 3 redundant global copies frees prompt budget with zero capability loss.

---

## 4. MCP Servers (`6` Active, `100%` Lazy-Loaded = Zero Eager Schema Bloat)

| MCP Server | Mode | Lazy Tools (`37` total) | Purpose |
| :--- | :---: | :---: | :--- |
| `data-agent-kit-plugin_dak-bigquery` | Lazy | `9` | `execute_sql_readonly`, `execute_sql`, `list_dataset_ids`, `list_table_ids`, `get_table_info`, `get_job`, etc. |
| `data-agent-kit-plugin_dak-data-agent-kit` | Lazy | `0` | Plugin metadata anchor |
| `data-agent-kit-plugin_dak-kc` | Lazy | `14` | Google Cloud Knowledge Catalog / Dataplex glossary & entry lineage |
| `data-agent-kit-plugin_dak-notebook` | Lazy | `9` | Colab / Jupyter notebook cell inspection & authoring |
| `keenable_keenable` | Lazy | `2` | `search_web_pages`, `fetch_page_content` |
| `parallel_parallel-search` | Lazy | `3` | `web_search`, `web_fetch`, `send_feedback` |

*Global `~/.gemini/config/mcp_config.json` has `0` stale VS Code named-pipe entries.*

---

## 5. Automations, Daemons & Lifecycle Hooks

| Automation / Hook | Trigger | Backing Script | Current Verified State |
| :--- | :--- | :--- | :--- |
| **`SessionStart` Continuity Hook** | Every new conversation & subagent | `session_continuity_daemon.py --on-session-start` | **ACTIVE** (injects `v8.2+` enclave topology & port `8788` probe) |
| **`PreToolUse` Security Fence** | Every `run_command`, `write_file`, `edit_file` | `pretool_single_hub_guard.py` (`11` invariants) | **ACTIVE** (`11/11` invariants enforced outside the model) |
| **`Stop` Checkpoint Archiver** | End of every agent turn | `session_continuity_daemon.py --on-stop` | **ACTIVE** (updates rolling 30-checkpoint archive + `CONTINUITY_CHECKPOINT.json`) |
| **`wire` Local Job Queue Worker** | Scheduled Task (`15m` target) | `wire_worker.py` + `lifeops-wire-task.xml` | **STALE (`WF-03`)** — last heartbeat `2026-11-10T17:45:34-10:00`; XML ready on disk but not currently registered in OS Task Scheduler (`STOP` file = `False`) |
| **Live Graph Verifier Server** | On-demand background daemon | `live_graph_verifier_server.py` (`127.0.0.1:8788`) | **STOPPED** (spawned on demand; reused across chats via port probe) |
| **Antigravity `/automation` Jobs** | Cron / background schedules | `~/.gemini/antigravity/automations/` | **NONE CONFIGURED** (`0` jobs) |
| **Legacy `email-blitz` Pipeline** | Manual only | `$WORKSPACE_HOME/email-blitz/` | **PAUSED & HARD-BLOCKED** (`Invariant 2`) |

---

## 6. Runtime Preferences & Safety Balance

- **Active Model Selection:** `Gemini 4 Carbon (High)`
- **Execution & UI Presets (`config.json` -> `userSettings`):**
  - `permissionPreset`: `AGENT_PERMISSION_PRESET_TURBO`
  - `autoExecutionPolicy`: `CASCADE_COMMANDS_AUTO_EXECUTION_EAGER`
  - `artifactReviewMode`: `ARTIFACT_REVIEW_MODE_TURBO`
  - `browserJsExecutionPolicy`: `BROWSER_JS_EXECUTION_POLICY_TURBO`
  - `enableTerminalSandbox`: `false` *(compensated by deterministic engine-level `PreToolUse` hook `pretool_single_hub_guard.py` enforcing all 11 account, clipboard, drive-letter, and GitHub fences)*
  - `queuedMessageDeliveryStrategy`: `MESSAGE_DELIVERY_STRATEGY_WHEN_IDLE`
  - `voiceName`: `Arlo` (`voiceSpeed: 1.0`)
  - `remoteControlEnabled`: `true`
- **Gemini Web (`/u/0/saved-info`) Global Preferences:**
  1. Active GitHub enclave rule (`harmonic-ops-machine` primary; `LEGACY_PERSONAL_GITHUB` read-only clone-only; `v7.0.0` re-root review note).
  2. Response quality rule (clear, balanced, precise, comprehensive, source-backed responses).

---

## 7. Prioritized Remediation & Hygiene Recommendations

1. **Deploy Trajectory Refinery (`architecture/trajectory-refinery/`):** Use `GCS` (`$GCP_ENCLAVE_PROJECT`, `Object Versioning=ON`) + a **private** `harmonic-ops-machine` repository for raw Gemini App work sessions (`L0`–`L4`), retiring Spacefast Outbox A completely.
2. **Register `wire_worker.py` (`WF-03`):** Import `lifeops-wire-task.xml` (or migrate to native `/automation`) when enabling the 15-minute `Export to Docs -> GCS/GitHub` session ingestion poller.
3. **Deduplicate 3 Global Skills (`SKILL-DEDUP-01`):** Remove duplicate copies of `accidental-data-loss-prevention`, `bigquery-graph-author`, and `bigquery-graph-query` from `~/.gemini/config/skills/` since `data-agent-kit-plugin` already supplies them.
4. **Optional Credential Vault Pruning (`CRED-HYGIENE-01`):** Sign out of dormant `mcp-oauth:*` entries in OS Credential Manager for unused plugins (`canva`, `figma`, `linear`, `mobbin`, `netlify`, `notion`, `semrush`, `wix`) if no longer needed.
