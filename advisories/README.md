# Carbon Advisory Quarantine Inbox (`advisories/`)

This directory receives versioned, strictly **Zero-PII** workflow improvement proposals from **`Gemini 4 Carbon`** (Task Mode / Scheduled Actions) via branch `carbon/advisories` or Pull Requests against `main`.

## Required Schema (`CARBON-ADVISORY-v2`)

Save each proposal as `advisories/CA-<YYYYMMDD-HHMM>.json`:

```json
{
  "schema": "CARBON-ADVISORY-v2",
  "advisory_id": "CA-20261112-1545",
  "digest_sha256_reviewed": "992ac5d6be2adb9f7a287b727f609b6669dfdee933ad47cf312bd37a5b6bacfd",
  "severity": "medium",
  "target_node": "WIRE-HB",
  "target_workflow": "wire_heartbeat_and_continuity",
  "finding": "Describe concrete bottleneck observed in prior_work_digest.json or CONTINUITY_CHECKPOINT.json",
  "proposed_improvement": "Actionable Zero-PII engineering specification",
  "expected_impact": "Deterministic reliability or latency gain",
  "zero_pii_attested": true
}
```

Every push or PR automatically triggers `.github/workflows/verify-zero-pii.yml` (`python verify.py`).
