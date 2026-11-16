## Trajectory Refinery Audit Pull Request (`inbox/raw-sessions` → `main`)

- **Source Session ID:** `<session_id>`
- **Raw Archive (`L0`):** `gs://<bucket>/raw/<session_id>.jsonl` (SHA-256: `<sha256>`)
- **Compression Ratio (`L1`):** Kept `<kept>/<total>` turns (`<pct>%` noise removed)

### Generated Artifacts in This PR
- [ ] `distilled/<date>_<session_id>.md` — Verified clean context only (zero conversational noise or dead-end chatter)
- [ ] `postmortems/<session_id>_rca.json` — Validated against `SESSION-RCA-v1` schema
- [ ] `patches/<session_id>_patch.md` — Actionable rule/hook update (or explicitly marked `none` if zero drift occurred)
- [ ] Automated CI (`verify-refinery-ci.yml`) passed with `0` leaked secret tokens or private keys
