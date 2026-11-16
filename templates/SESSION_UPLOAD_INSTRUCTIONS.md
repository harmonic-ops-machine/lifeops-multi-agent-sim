# Mandatory Session & Work-Product Upload Instructions (`SESSION-BUNDLE-v3`)

**Canonical Vault Repository (`PRIVATE`):** `ssh://github.com/harmonic-ops-machine/lifeops-enclave-private.git` (branch: `inbox/raw-sessions`)  
**Public Zero-PII Template Mirror:** `https://github.com/harmonic-ops-machine/lifeops-multi-agent-sim/tree/main/templates`  
**Template File to Populate:** [`templates/SESSION_CLOSEOUT_TEMPLATE.md`](SESSION_CLOSEOUT_TEMPLATE.md)  
**Deterministic Packager & Scrubber:** [`architecture/trajectory-refinery/src/session_bundler.py`](../architecture/trajectory-refinery/src/session_bundler.py)

---

## 1. Core Mandate (Applies to Every Substantive Session)

Whenever **any** work, research, configuration, troubleshooting, drafting, or code execution takes place in a session (across **Gemini Web App**, **Antigravity IDE**, **Gemini CLI**, or **Claude Code**), the session **MUST upload its entire work** before closeout (or immediately upon operator request) so that an independent **Refinery Auditor Agent** can:
1. Promote clean, noise-free state and verified deliverables onto `main` (`L1`),
2. Inspect the exact environment, plugins, skills, accounts, and OAuth/credential bindings to see **where and why errors occurred** (`L2`), and
3. Generate concrete guardrail patches (`L3`) and cross-session continuity (`L4`).

---

## 2. What "Uploading Entire Work" Means (The 4-Part Bundle)

Each session deposits a self-contained directory at `sessions/<YYYY-MM-DD>_<session_id>/` on branch **`inbox/raw-sessions`** of `harmonic-ops-machine/lifeops-enclave-private`:

```text
sessions/<YYYY-MM-DD>_<session_id>/
├── SESSION_CARD.md          # Completed 9-section SESSION-BUNDLE-v3 manifest (no blank placeholders)
├── trajectory.jsonl         # Full turn-by-turn black-box record (SESSION-TRACE-v1, including failed turns & ASR slips)
├── bundle_manifest.json     # Cryptographic SHA-256, byte-size, live-link & scrub receipt from session_bundler.py
└── products/                # Copies of EVERY deliverable file created/updated in the session
    ├── <artifact_1.md>      # Direct file copy if <= 5 MB
    ├── <script_2.py>        # Direct file copy if <= 5 MB
    └── <dataset.parquet>.gcs.json  # Automatic gs:// SHA-256 pointer stub if > 5 MB
```

---

## 3. Five Mandatory Provenance Requirements (Be Exact — Never Vague)

### 3.1 Exact Runtime Environment (`Section 1` of `SESSION_CARD.md`)
Do **not** write generic labels like `"Windows"` or `"Browser"`. Specify:
- **Physical / Cloud Host & OS:** e.g., `HIGHRES (Windows 11, PowerShell 5.1, Python 3.12.14, Git 2.56.0.windows.4)` or `Gemini Web Cloud Runtime (Chrome / Antigravity WebView)`.
- **Agent Surface & Session Identifier:** `conversationId`, Gemini App thread URL (`https://gemini.google.com/u/0/app/<id>`), active workspace root(s) (`$WORKSPACE_HOME\HIGHRES-Workspace.code-workspace` or `<no active workspace>`), and working directory.
- **Model & Execution Posture:** Exact model + effort tier (e.g., `Gemini 4 Carbon (High)`), permission preset (`TURBO` vs `ASK`), terminal sandbox state (`enabled` / `disabled`), and compensating hook enforcement (`hooks.json`).
- **Delegated Subagents / Workers:** Every subagent spawned (`conversationId`, type, model, role, and host-verified `visited_origins` / `blocked_origins`).

### 3.2 Skills, Plugins, MCP Servers & Hooks (`Section 2` of `SESSION_CARD.md`)
Distinguish **installed/available** capabilities from those **actually invoked** in the session:
- **Skills Read & Followed:** Exact skill name and `SKILL.md` path (e.g., `enforcing-resource-attribution` -> `$WORKSPACE_HOME\.gemini\config\skills\enforcing-resource-attribution\SKILL.md`). If a relevant skill existed but was *missed*, log that in Section 7!
- **Plugins Exercised:** Exact plugin directory/name, version, and whether enabled or found disabled (`enabled: false`).
- **MCP Servers & Tools Invoked:** Exact `ServerName`, `ToolName`, loading mode (`lazy` vs `eager`), and call outcome.
- **Hooks & Daemons Triggered:** `SessionStart`, `Stop`, and any `PreToolUse` invariants (`1`–`11`) that rewrote or blocked a tool call.

### 3.3 Accounts, OAuth Scopes & Non-Secret Credential Provenance (`Section 3` of `SESSION_CARD.md`)
Be **maximally specific** about *which identity and credential mechanism authenticated each application*, while **NEVER revealing secret values**:

| Allowed & Required (Record Explicitly!) | Strictly Forbidden (`Tier-A Secrets` — NEVER Write!) |
| :--- | :--- |
| • Exact account email / principal (`SEAT_A_PRIMARY_HUB`, `SEAT_C_READONLY_BI`, `harmonic-ops-machine`)<br>• Browser slot (`/u/0/` vs `/u/1/`) & `AGY_ACCOUNT=...` prefix<br>• GCP Project ID (`$GCP_ENCLAVE_PROJECT`) & IAM Service Account email<br>• Auth transport (`Ed25519 SSH`, `Plugins Manager OAuth2`, `ADC`, `GitHub OIDC`, `WebView Session Cookie`)<br>• SSH **public** key path (`.pub`), key title (`HIGHRES-enclave`), and `SHA256:...` fingerprint<br>• OAuth **scope URLs** (`https://www.googleapis.com/auth/drive`, `repo`, `workflow`)<br>• OS Credential Manager **target name only** (`gh:github.com:...`, `antigravity.plugins:.../oauth2:...`) | • Raw passwords or passphrases<br>• OAuth access or refresh tokens (`ya29.*`, `1//*`)<br>• GitHub PATs or app installation tokens (`ghp_*`, `github_pat_*`, `ghs_*`)<br>• Cloud / LLM API keys (`AIza*`, `sk-*`)<br>• SSH or TLS **private** key blocks (`-----BEGIN ... PRIVATE KEY-----`)<br>• Raw cookie values (`SID=...`, `SAPISID=...`)<br>• One-time 2FA, device, or email sudo verification codes (`XXXXXXXX`)<br>• Any Bitwarden vault content |

### 3.4 Generated Files, Bundled Copies & Live Links (`Section 4` of `SESSION_CARD.md`)
For **every** file, report, script, artifact, screenshot, Doc, Sheet, or cloud object generated or modified during the session:
1. Copy the file into `products/<filename>` (unless it is an external cloud table or `> 5 MB` binary offloaded to `gs://enclave-session-refinery/...`).
2. Provide its **clickable original/live link** if still available:
   - Local workstation files: `file:///$WORKSPACE_HOME/...` (forward slashes)
   - GitHub files/commits: `https://github.com/harmonic-ops-machine/<repo>/blob/<commit_sha>/<path>`
   - Cloud Storage objects: `gs://enclave-session-refinery/...`
   - Google Docs / Sheets / Gemini threads: full `https://docs.google.com/...` or `https://gemini.google.com/u/0/app/...` URL
3. Record its verified **Availability State** at closeout:
   - `AVAILABLE_VERIFIED` — confirmed present at original location with matching byte size & `SHA-256`.
   - `BUNDLED_ONLY_EPHEMERAL_SOURCE` — source was temporary/in-chat, preserved permanently inside `products/`.
   - `SUPERSEDED_OR_REMOVED` — intentionally deleted/replaced during session (state why).

### 3.5 Honest Dead-End & Error Attribution (`Sections 6–8` of `SESSION_CARD.md`)
Never sanitize away mistakes: log every failed command, hung tool, permission block, UTF-8/CRLF mismatch, voice ASR misrecognition, or operator correction with its exact turn index and root-cause taxonomy code.

---

## 4. Step-by-Step Execution Procedure by Surface

### Surface A — Local CLI-Capable Agents (`Antigravity IDE`, `Gemini CLI`, `Claude Code Fable`)

1. **Sync Vault Branch:**
   ```powershell
   $priv = '$WORKSPACE_HOME\LIFE-ORGANIZED\simulations\lifeops-enclave-private'
   git -C $priv fetch origin
   git -C $priv checkout inbox/raw-sessions
   git -C $priv pull --ff-only origin inbox/raw-sessions
   ```
2. **Build, Validate & Scrub the Session Bundle via `session_bundler.py`:**
   Pass:
   - completed `SESSION_CARD.md` following `templates/SESSION_CLOSEOUT_TEMPLATE.md` (`SESSION-BUNDLE-v3`),
   - raw `trajectory.jsonl` (`SESSION-TRACE-v1`),
   - `products` dict of all generated deliverables, and
   - `generated_file_paths` list so `session_bundler.py` automatically verifies live file existence, byte sizes, and `SHA-256` digests while scrubbing any accidental `Tier-A` secrets (`mode="private"`).
3. **Commit & Push Over `HIGHRES-enclave` SSH:**
   ```powershell
   git -C $priv add "sessions/<YYYY-MM-DD>_<session_id>"
   git -C $priv commit -m "ingest(session): upload SESSION-BUNDLE-v3 <session_id> + products"
   git -C $priv push origin inbox/raw-sessions
   git -C $priv ls-remote origin refs/heads/inbox/raw-sessions
   ```
   *(Only report the upload as complete **after** `git push` exits `0` and `git ls-remote` confirms the new commit SHA!)*

### Surface B — Browser-Only Sessions (`Gemini Web App` on `https://gemini.google.com/u/0/`)

Because Gemini Web's built-in `@GitHub` connector is **read-only**:
1. Read `templates/SESSION_CLOSEOUT_TEMPLATE.md` (`SESSION-BUNDLE-v3`) via `@GitHub` from `harmonic-ops-machine/lifeops-enclave-private` (or `harmonic-ops-machine/lifeops-multi-agent-sim`).
2. Populate all 9 sections completely—explicitly listing `gemini.google.com/u/0/` environment details, active Gemini connectors (`@GitHub`, `Google Workspace`, `Contacts`, etc.), linked Google account (`SEAT_A_PRIMARY_HUB` `/u/0/`), links to all Canvas/Docs artifacts created, and full Section 7 error/ASR logs (with zero `Tier-A` secrets).
3. Deliver via the active ingestion channel:
   - **If `archive_gemini_session` Cloud Run MCP connector is enabled:** Call `archive_gemini_session` directly with `session_id`, `session_card_md`, `turns`, and `products`.
   - **Otherwise (Zero-Cloud Fallback):** Output the complete filled `SESSION_CARD.md` + verbatim product blocks and click **`Export to Docs`**, titling the Google Doc `[SESSION-BUNDLE] YYYY-MM-DD <session_id>` so `wire_worker.py` (`gdrive` CLI on `SEAT_A_PRIMARY_HUB`) automatically ingests, hashes, and pushes the bundle to `inbox/raw-sessions`.
