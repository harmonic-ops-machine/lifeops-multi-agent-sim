# Spacefast — Platform Reference, Company History & HIGHRES Enclave History (`Zero-PII`)

- **Compiled At (`HST` / `UTC-10`):** `2026-11-17T03:35:00-10:00` (Updated `2026-11-17T04:08:00-10:00`)
- **Workstation / Enclave:** `HIGHRES` (`Windows 11`, Hub `SEAT_A_PRIMARY_HUB` `/u/0/`, GitHub `harmonic-ops-machine`)
- **Sister Repositories:**
  - **Private Full-Precision Vault:** `https://github.com/harmonic-ops-machine/lifeops-enclave-private` (`inventory/SPACEFAST_INFO_AND_HISTORY.md`)
  - **Public Zero-PII Blueprint:** `https://github.com/harmonic-ops-machine/lifeops-multi-agent-sim` (`inventory/SPACEFAST_INFO_AND_HISTORY.md`)
- **Credential & Zero-PII Safety:** `0` personal emails, `0` Windows user paths, `0` private team/workspace IDs, `0` court docket identifiers, and `0` Tier-A secrets (API keys, OAuth tokens, claim keys, or private keys).

---

## 0. Cloud Agent Quick-Start — Station Basics (`Read This First`)

Any Cloud Agent (Antigravity Cloud VM, Claude Code `--cloud`, GitHub Actions worker, or remote verifier) interacting with `HIGHRES`'s Spacefast archive layer only needs the facts below:

- **Station Role of Spacefast:** Zero-inbound-port, **100% Zero-PII HTTPS relay** (`SYMMETRIC_DUAL_OUTBOX_ACTIVE`) bridging `HIGHRES` (`Windows 11`), Cloud/GitHub workers (`harmonic-ops-machine`), and `Gemini Web App` (`SEAT_A_PRIMARY_HUB` `/u/0/`, `4 Carbon` Task Mode).
- **Two Isolated Production Spaces (Never Cross-Write):**
  1. **Outbox A (`Antigravity` / Windows Station Outbox):** `spc_4191a55af38b42d986059e576e4b9800` (`OUTBOX_A_TEAM` `OUTBOX_A_TEAM_ID`) → `https://harmonic-garden.space.fast`
     - `GET /manifest.json` · `GET /CONTINUITY_CHECKPOINT.json` (`HIGHRES-CONTINUITY-CHECKPOINT-v2`) · `GET /prior_work_digest.json` (`CARBON-WORKFLOW-DIGEST-v1`) · `GET /carbon_loop_feed.json` · `GET /simulation_spec.json` · `GET /verify.py`
  2. **Outbox B (`Gemini Web App` / `4 Carbon` Outbox):** `spc_3f43447fca9d4d32b0d483fdf63d25fb` (`OUTBOX_B_TEAM` `OUTBOX_B_TEAM_ID` under `SEAT_A_PRIMARY_HUB`) → `https://harmonic-carbon-outbox.space.fast`
     - `GET /advisory_feed.json` (`CARBON-ADVISORY-v2` — **LIVE `HTTP 200`**)
     - `GET /gemini_sessions_feed.json` (`GEMINI-SESSIONS-FEED-v1` — daily `21:00 HST` session catalog export; `HTTP 404` = `AWAITING_FIRST_PUBLISH`, treat as non-fatal no-op)
- **Zero-Auth Cloud Agent Verification One-Liners:**
  ```bash
  # 1. Verify Outbox A cryptographic manifest + Zero-PII + 34-node DAG over HTTPS:
  curl -fsSL https://harmonic-garden.space.fast/verify.py | python3 - --url https://harmonic-garden.space.fast

  # 2. Check latest Windows station continuity checkpoint & Carbon advisories:
  curl -fsSL https://harmonic-garden.space.fast/CONTINUITY_CHECKPOINT.json | jq .
  curl -fsSL https://harmonic-carbon-outbox.space.fast/advisory_feed.json | jq .
  ```
- **Hard Guardrails for Cloud Agents:**
  - **Public `*.space.fast` = Strictly Zero-PII:** Never publish emails, host user paths, personal names, court docket strings, or credential tokens to public Spaces.
  - **SSRF Fence:** Only `https://<slug>.space.fast/...` (`port 443`) is accepted by station sync scripts (`$WIRE_BIN/spacefast_carbon_sync.py` / `agy-index sync-spacefast`).
  - **MCP Endpoint & IDE Plugin Status:** `https://mcp.spacefast.com` (`505` actions). On `Gemini Web App` (`SEAT_A_PRIMARY_HUB` `/u/0/`), `@Spacefast` core read + `Publish` actions were configured as `Always allow` and billing/domain/delete actions gated on `Always ask` (never toggle bulk category dropdowns on `gemini.google.com/customize/connectors` — triggers Google RPC error `13`). On `HIGHRES` `Antigravity` IDE, the `spacefast` plugin was uninstalled on `2026-11-17T04:08-10:00` (see Section 4) to eliminate 474-tool context bloat while static HTTPS archive Spaces remain untouched.

---

## 1. Spacefast — Company, Platform & Public History

**Spacefast** (`https://spacefast.com` · live domains `*.space.fast` · dashboard `https://my.spacefast.com` · MCP `https://mcp.spacefast.com`) is an agent-native web deployment, storage, and hosting company spun out of **Automattic** (the company behind WordPress.com, WooCommerce, Tumblr, Pocket Casts, Day One, Gravatar, and Beeper/Texts).

### 1.1 Origin & Launch Timeline
- **Early 2026 (*Automattic Radical Speed Month*):** Prototyped solo by **Batuhan İçöz** (who joined Automattic through its acquisition of *Texts* and worked on the Beeper team; early internal working name: *Stattic*). Non-technical friends kept sending him AI-coded ("vibe-coded") apps and asking for help deploying them to GitHub or Vercel. He built an instant static hosting layer atop Automattic's global edge infrastructure (`15B+` monthly page views), then added SQL databases, file uploads, and collaboration primitives as internal testers adopted it.
- **September 2026:** Soft-launched and spun out by Automattic into its own standalone company with **Batuhan İçöz** as Founder & CEO (core team includes Fatih Kadir Akın).
- **November 9, 2026:** Public general-availability launch ([Automattic Launch Post](https://automattic.com/2026/11/09/meet-spacefast), [Founder Blog](https://spacefast.com/blog/spacefast-and-beyond), [PRNewswire](https://prnewswire.com/news-releases/automattic-launches-spacefast-a-new-company-that-gets-apps-and-websites-live-in-seconds-302933038.html)), shipping official plugins and MCP support across Antigravity, Claude / Claude Code, Gemini, ChatGPT, Cursor, Codex, Grok Bot, OpenClaw, and Hermes.

### 1.2 Architecture & Core Capabilities ("Not an AI Builder")
Spacefast deliberately provides **zero LLM or chat builder of its own** and charges strictly for infrastructure rather than AI inference credits—users keep their existing agents, memory, and local toolchains:

| Capability | Details |
| :--- | :--- |
| **Four Publish Routes** | 1. **Hosted HTTP MCP** (`https://mcp.spacefast.com` — OAuth 5-min delegated tokens, `~505` granular actions with sensitive-action approval gates)<br>2. **Drag & Drop** (`https://drop.fast` — folder or `.zip`, no terminal or account needed)<br>3. **Git Push** (`https://git.spacefast.com` — `main` deploys to production; branches mint preview URLs)<br>4. **CLI / API** (`npx spacefast publish`, scriptable rollbacks, sharing, and domains) |
| **Supported Runtimes** | Static HTML/CSS/JS, JSON/artifact feeds, presentations, Astro, Next.js, TanStack Start, and PHP. |
| **Immutable Versioning** | Every publish creates a permanent immutable version (`ver_...` -> `https://<slug>--vN.space.fast`) with 1-click or 1-command rollback. |
| **Built-in Backend** | Ready-to-use per-Space SQL database, user file uploads, and built-in privacy-preserving traffic stats (no tracker snippet needed). |
| **Sharing & Lifecycle** | **Private by default** (invite-only, password-protected, viewer share links, or public). Anonymous unclaimed Spaces expire `33h 20m` after creation/latest file-changing publish (capped at `30` days); claimed Spaces stay live indefinitely. |
| **Agent Collaboration** | Inline page/path comments (`createSpaceVersionComment` / `listSpaceVersionComments`) allow humans or peer agents to pin structured feedback directly to a Space path. |

### 1.3 Pricing & Plan Limits (Verified Nov 2026)

| Plan | Monthly Price | Included Usage Credit | Spaces & Custom Domains | Seats & Key Extras |
| :--- | :--- | :--- | :--- | :--- |
| **Personal** | `$0` (no card) | `$1` / mo | `20` Spaces · `20` domains | `1` member; commercial use allowed; if `$1` metered credit runs out, new builds/Workers pause while already-deployed static sites continue serving. |
| **Go** | `$5` / mo | `$5` / mo | `100` Spaces · `100` domains | `1` member; hourly database backups; datacenter selection; email support. |
| **Pro / Plus** | `$15` / mo | `$15` / mo | `500` Spaces · `500` domains | Up to `5` members included (`$15`/mo each additional); team roles & wildcard domains; priority support. |
| **Add-ons / Enterprise** | `$9` / Space / mo (*Boost*) · Custom (*Enterprise*) | Custom | Unlimited (Enterprise) | *Boost* raises single-Space CPU/RAM/disk; *Enterprise* adds SAML/SCIM SSO, subteams, audit logs, network policies, and contracted SLA. |

---

## 2. `HIGHRES` Enclave Spacefast Topology & Live Status (`2026-11-17 HST`)

Within `HIGHRES`, Spacefast operates as the **Zero-Inbound-Port, 100% Zero-PII Cloud Relay** (`SYMMETRIC_DUAL_OUTBOX_ACTIVE`) connecting `Antigravity` on Windows, Cloud/GitHub workers, and `Gemini Web App` (`4 Carbon` Task Mode) without opening Windows Firewall ports, touching Win32 clipboard data, or scraping `gemini.google.com`.

### 2.1 Active Production Spaces (Live HTTP Probe Verified `2026-11-17 03:32 HST`)

| Outbox Plane | Space ID & Team Binding | Live Endpoints & Verified HTTP Status | Operational Purpose |
| :--- | :--- | :--- | :--- |
| **Outbox A** (`Antigravity` Orchestrator) | `spc_4191a55af38b42d986059e576e4b9800`<br>`OUTBOX_A_TEAM` (`OUTBOX_A_TEAM_ID` under `SEAT_B_LEGACY_PERSONAL`, workspace `OUTBOX_A_WORKSPACE_ID`) | • `https://harmonic-garden.space.fast/` — **`HTTP 200`** (`52,137 B`)<br>• `/manifest.json` — **`HTTP 200`** (`1,374 B`)<br>• `/CONTINUITY_CHECKPOINT.json` — **`HTTP 200`** (`2,387 B` live; `3,260 B` local)<br>• `/prior_work_digest.json` — **`HTTP 200`** (`18,198 B` live; `19,027 B` local)<br>• `/carbon_loop_feed.json` & `/simulation_spec.json` — **`HTTP 200`**<br>• Immutable historical pins: `https://harmonic-garden--v2.space.fast/` (`v5.0.0`), `https://harmonic-garden--v4.space.fast/` (`v7.0.0`) | Hosts the 34-node / 63-edge Multi-Agent Isolation DAG (`v8.2.0`), `verify.py`, sanitized `CARBON-WORKFLOW-DIGEST-v1`, and hash-chained `HIGHRES-CONTINUITY-CHECKPOINT-v2`. |
| **Outbox B** (`Gemini App` / `4 Carbon`) | `spc_3f43447fca9d4d32b0d483fdf63d25fb`<br>`OUTBOX_B_TEAM` (`OUTBOX_B_TEAM_ID` under `SEAT_A_PRIMARY_HUB`) | • `https://harmonic-carbon-outbox.space.fast/advisory_feed.json` — **`HTTP 200`** (`4,235 B`, Zero-PII verified)<br>• `/gemini_sessions_feed.json` — **`HTTP 404`** (*`AWAITING_FIRST_PUBLISH` from daily `21:00 HST` Gemini Scheduled Task*) | Dedicated write-isolated outbox for `Gemini 4 Carbon` (`CARBON-ADVISORY-v2`) and daily `GEMINI-SESSIONS-FEED-v1` session catalogs—bypassing the Personal plan's 1-member team ceiling with zero shared write blast radius. |

### 2.2 Local Plugin, Connector & Script Bindings
- **Antigravity IDE Plugin (`antigravity-plugins-partners/plugin/spacefast`, `v0.9.0`):**
  - Previously installed at `~/.gemini/config/plugins/spacefast` (`PROVENANCE.json` `sourceSha: d5bcd8b1b4b06af778710e7ae4412d81f3bda008`, refreshed `2026-11-16 08:48 HST`) with `13` skills (`apply-design-system`, `build-website`, `custom-domain`, `edit-space`, `fix-deployment`, `import-design-system`, `moderate-show-and-tell`, `setup`, `share-space`, `show-and-tell`, `spacefast`, `update-design`, `verify-design-system`).
  - **Current IDE Status:** **Uninstalled (`2026-11-17T04:08-10:00`)** via `agy plugin uninstall spacefast` after backing up `~/.gemini/config/config.json` (see Section 4).
- **Gemini Web App Connector (`SEAT_A_PRIMARY_HUB` `/u/0/` at `https://gemini.google.com/customize/connectors`):**
  - `@Spacefast` (`https://mcp.spacefast.com`) configured with `505` actions (`263` read-only, `242` write/delete).
  - Individual action flags were toggled one-by-one (`~200ms` spacing) to avoid Google's `batchexecute` RPC error `Something went wrong (13)` on bulk category toggles.
  - Core operational actions (`GetAccount`, `GetMe`, `GetSpace`, `ListSpaces`, `GetSpaceVersion`, `ListSpaceVersions`, `GetTeamAgentContext`, `Publish`) were set to `Always allow`, while billing, domain-purchase, and destructive actions (`PurchaseDomain`, `DeleteSpace`, `DeleteSpaceVersion`, `FinalizeSpaceVersion`, `PromoteSpaceVersion`) remained gated on `Always ask`.
- **Deterministic Sync & Security Engine (`$WIRE_BIN/spacefast_carbon_sync.py`):**
  - Enforces `https://*.space.fast` SSRF host fencing, `verify_zero_pii()`, shell-injection regex blocking, SHA-256 deduplication, full-jitter exponential backoff `(30, 60, 120, 300, 900)`, dead-letter spooling, and inert quarantine into `$LO_ROOT/staged_manifests/carbon_advisories/` (protected by `pretool_single_hub_guard.py` Invariant 10).
  - Audit ledger: `$LO_ROOT/data/spacefast_carbon_sync_audit.jsonl` (`40` logged operations between `2026-11-12` and `2026-11-16 HST`).

---

## 3. Chronological Evolution on `HIGHRES` (`2026-11-12` → `2026-11-17 HST`)

| Date / Window (`HST`) | Milestone / Version | Key Commits, Artifacts & Architectural Advances |
| :--- | :--- | :--- |
| **`2026-11-12 12:27–12:35`** | **`v5.0.0` — Initial Spacefast Deployment (`v2`)** | Deployed the 7-agent isolation DAG (`30` nodes, `52` edges) from `$LO_ROOT/simulations/lifeops-multi-agent-sim` (`56672de`) to `spc_4191a55af38b42d986059e576e4b9800` (`ver_a45301abb2f741bcb5bcc97e5d5bfe5d` -> `https://harmonic-garden--v2.space.fast/`), enforcing `.gitattributes` `LF` normalization for byte-identical SHA-256 verification across Windows, loopback `:8788`, and HTTPS (`reports/versioned_7_agent_simulation_v5_20261112.md`). |
| **`2026-11-12 12:49–13:50`** | **`v6.0.0` → `v7.0.0` — Zero-PII Airgap & `L1`–`L9` Sentinel (`v4`)** | Added single-command Seat-A unlocker (`seat_a_hub_unlock.py`), 9-surface Win32/clipboard leakage matrix (`L1`–`L9`), `verify_zero_pii()`, `HANDOFF_REDACTED`, and outbound `carbon_loop_feed.json` (`ver_45ff8173335643b5a98035cc779eb675` -> `https://harmonic-garden--v4.space.fast/`, `reports/2026-11-12_FULL_ECOSYSTEM_PROJECT_HANDOFF.md`). Public `origin/main` was subsequently re-rooted cleanly at `v7.0.0` (`0` PII across all public commits). |
| **`2026-11-12 14:16–14:34`** | **`v8.0.0` — Bidirectional Sync & Single Local Executor (`v5`)** | Built `spacefast_carbon_sync.py` (`--build-digest` + `--ingest-spacefast-comments`) and `designated_local_executor.py` (`Claude Code 2.1.321 --model fable`), initially routing `CARBON-ADVISORY-v2` return payloads through Spacefast page comments anchored to `/prior_work_digest.json` (`ver_ea91ff1ea78a49289d1d0d2e3004aef6`, `reports/2026-11-12_WINDOWS_SINGLE_EXECUTOR_AND_SPACEFAST_AUTOMATION_V8.md`). |
| **`2026-11-12 15:44–17:42`** | **`v8.1.0` → `v8.2.0` — Symmetric Dual-Outbox Proven Live** | Provisioned Outbox B (`spc_3f43447fca9d4d32b0d483fdf63d25fb` -> `https://harmonic-carbon-outbox.space.fast/advisory_feed.json`) on `OUTBOX_B_TEAM` (`ver_16452831ab9b419eabae1574917dd006`), while promoting Outbox A to `ver_604684b89bff4049aa49f1661f1c6573` (`bld_e69bcdf91dcc40dd85934fdbad8f2ae2`). `Gemini 4 Carbon` autonomously published `CA-20261112-001` (`IMP-LOOP-810-PREFLIGHT-GRANT-HANDSHAKE`), which was quarantined, verified, and distilled into `--preflight`, SSRF host fencing, retry/DLQ resilience, hash-chained `HIGHRES-CONTINUITY-CHECKPOINT-v2` (`session_continuity_daemon.py`), and `single-enclave-carbon-loop/SKILL.md` (`reports/2026-11-12_FULL_AGENTIC_CARBON_LOOP_PROVEN_V8_2.md`, `reports/2026-11-12_SESSION_HANDOFF_V8_2_SINGLE_HUB_ROLLOVER.md`). |
| **`2026-11-16 08:48–23:26`** | **`v8.3.x` & `GEMINI-SESSIONS-FEED-v1` Bridge (`v1.2`)** | Refreshed Spacefast plugin to `v0.9.0`; verified Dual-Outbox preflight across the `harmonic-ops-machine` SSH rollover; built the Zero-Repo-Access `GEMINI-SESSIONS-FEED-v1` bridge (`advisory/spacefast-gemini-session-bridge-v1.2` `7d6b959` + Issue `#3` on `harmonic-ops-machine/agy-session-index` and `--ingest-sessions-url` in `spacefast_carbon_sync.py`, `4/4` self-tests green) to replace flaky multi-tab Google Sheet appends with atomic Spacefast JSON publishing (`reports/2026-11-16_SESSION_HANDOFF_ORCHESTRATOR_SPACEFAST_BRIDGE_f2ac3b2c.md`). |
| **`2026-11-17 03:30–03:38`** | **Live Audit & Dual-Repo Reference Deposit** | Verified live `HTTP 200` across both Spacefast production outboxes, audited the 40-event local sync ledger + plugin/connector posture, and published this consolidated reference to `$LO_ROOT/reports/`, `harmonic-ops-machine/lifeops-enclave-private`, and (in Zero-PII form) `harmonic-ops-machine/lifeops-multi-agent-sim`. |

---

## 4. `2026-11-17T04:08-10:00` Addendum — Plugin & Cloud Bridge Decommission

- **Decommissioned Surfaces:** The `spacefast` Antigravity IDE plugin (`v0.9.0`, removed from `~/.gemini/config/plugins/` after backing up `~/.gemini/config/config.json` to `config.json.bak.20261117_0408`) and the `agy-session-index` Cloud bridge were decommissioned to eliminate 474-tool context bloat.
- **Static Archive Spaces Preserved:** Existing static HTTPS archive Spaces (`https://harmonic-garden.space.fast/` and `https://harmonic-carbon-outbox.space.fast/`) remain untouched.
