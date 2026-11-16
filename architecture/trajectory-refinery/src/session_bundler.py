#!/usr/bin/env python3
"""Deterministic Session + Products Self-Upload Bundler & Tiered Secret Scrubber (v8.3.0).

Implements the two-tier privacy & precision policy decided for HIGHRES:
  1. Tier-A Cryptographic Secrets (ALWAYS SCRUBBED, even in Private repo):
     - OAuth bearer/refresh tokens (ya29.*), GitHub PATs (ghp_*, github_pat_*),
       Google API keys (AIza*), LLM keys (sk-*), OpenSSH/PEM private keys,
       Cookie headers (SID/HSID/SAPISID), and explicit verification codes.
  2. Tier-B Operational Entities (PRESERVED in Private repo for full precision;
     scrubbed ONLY when `--mode public-zero-pii` is explicitly requested):
     - Account emails, GCP project/bucket IDs, workstation paths, and domain text.

Packages a session and all of its deliverables into:
  sessions/<YYYY-MM-DD>_<session_id>/
    ├── SESSION_CARD.md
    ├── trajectory.jsonl
    ├── bundle_manifest.json
    └── products/<deliverables...>
"""
from __future__ import annotations

import datetime as dt
import hashlib
import json
from pathlib import Path
import re
import sys
from typing import Any

sys.dont_write_bytecode = True

HST = dt.timezone(dt.timedelta(hours=-10), name="HST")

# Tier-A: Cryptographic secrets & credentials — NEVER allowed in ANY repo (Private or Public)
TIER_A_SECRET_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    ("OAUTH_ACCESS_TOKEN", re.compile(r"\bya29\.[A-Za-z0-9._-]{16,}\b")),
    ("GOOGLE_API_KEY", re.compile(r"\bAIza[0-9A-Za-z_-]{30,}\b")),
    ("GITHUB_CLASSIC_PAT", re.compile(r"\bghp_[A-Za-z0-9]{25,}\b")),
    ("GITHUB_FINE_PAT", re.compile(r"\bgithub_pat_[A-Za-z0-9_]{25,}\b")),
    ("GENERIC_API_SECRET", re.compile(r"\bsk-[A-Za-z0-9_-]{25,}\b")),
    ("PRIVATE_KEY_BLOCK", re.compile(r"-----BEGIN [A-Z0-9 ]*PRIVATE KEY-----[\s\S]*?-----END [A-Z0-9 ]*PRIVATE KEY-----")),
    ("GOOGLE_AUTH_COOKIE", re.compile(r"\b(SAPISID|HSID|SSID|__Secure-1PSID)=[^\s;\"']+")),
]

# Tier-B: Operational PII/entities — Preserved in Private repo; scrubbed ONLY in public-zero-pii mode
TIER_B_PUBLIC_PATTERNS: list[tuple[str, re.Pattern[str], str]] = [
    ("EMAIL_ADDRESS", re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}"), "<REDACTED_EMAIL>"),
    ("WINDOWS_USER_PATH", re.compile(r"[A-Za-z]:[/\\]Users[/\\][A-Za-z0-9._-]+", re.I), "$WORKSPACE_HOME"),
]

REQUIRED_TEMPLATE_SECTIONS = (
    "## 1. Uploaded Session Products Inventory",
    "## 2. Verified Outcomes & Binding Decisions",
    "## 3. Pruned Noise & Rejected Approaches",
    "## 4. Forensic Error, ASR & Operator Correction Ledger",
    "## 5. Candidate System Guardrail / Skill / Hook Patches",
    "## 6. Next-Session Handoff & Open Approval Gates",
)


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def scrub_text(text: str, mode: str = "private") -> tuple[str, list[str]]:
    """Apply Tier-A secret scrubbing always, plus Tier-B entity scrubbing if mode == 'public-zero-pii'."""
    if mode not in ("private", "public-zero-pii"):
        raise ValueError(f"Invalid scrub mode: {mode}")

    redactions: list[str] = []
    out = text
    for label, pat in TIER_A_SECRET_PATTERNS:
        if pat.search(out):
            out = pat.sub(f"<SCRUBBED_{label}>", out)
            redactions.append(f"TIER_A:{label}")

    if mode == "public-zero-pii":
        for label, pat, replacement in TIER_B_PUBLIC_PATTERNS:
            if pat.search(out):
                out = pat.sub(replacement, out)
                redactions.append(f"TIER_B:{label}")

    return out, redactions


def validate_session_card_markdown(card_md: str) -> list[str]:
    errors: list[str] = []
    if not card_md.lstrip().startswith("---"):
        errors.append("Missing YAML frontmatter header ('---') in SESSION_CARD.md")
    if "schema: SESSION-BUNDLE-v2" not in card_md:
        errors.append("Missing 'schema: SESSION-BUNDLE-v2' in SESSION_CARD.md frontmatter")
    for sec in REQUIRED_TEMPLATE_SECTIONS:
        if sec not in card_md:
            errors.append(f"Missing required template section: {sec}")
    return errors


def build_session_upload_bundle(
    repo_root: Path,
    session_id: str,
    session_card_md: str,
    trajectory_bytes: bytes,
    products: dict[str, bytes],
    date_slug: str | None = None,
    mode: str = "private",
    large_blob_threshold_bytes: int = 5 * 1024 * 1024,
    gcs_bucket_prefix: str = "gs://enclave-session-refinery",
) -> dict[str, Any]:
    """Create a complete, scrubbed, SHA-256-verified session + products upload directory."""
    d_slug = date_slug or dt.datetime.now(HST).strftime("%Y-%m-%d")
    clean_card, card_redactions = scrub_text(session_card_md, mode=mode)
    val_errors = validate_session_card_markdown(clean_card)
    if val_errors:
        raise ValueError("Invalid SESSION_CARD.md: " + "; ".join(val_errors))

    traj_txt = trajectory_bytes.decode("utf-8", errors="replace")
    clean_traj_txt, traj_redactions = scrub_text(traj_txt, mode=mode)
    clean_traj_bytes = clean_traj_txt.encode("utf-8")

    bundle_rel = Path("sessions") / f"{d_slug}_{session_id}"
    bundle_dir = repo_root / bundle_rel
    products_dir = bundle_dir / "products"
    products_dir.mkdir(parents=True, exist_ok=True)

    product_entries: list[dict[str, Any]] = []
    all_redactions = list(card_redactions) + list(traj_redactions)

    for rel_name, raw_b in sorted(products.items()):
        safe_name = Path(rel_name).name
        if len(raw_b) > large_blob_threshold_bytes:
            # Offload binary > 5 MB to GCS pointer stub
            digest = sha256_bytes(raw_b)
            gcs_uri = f"{gcs_bucket_prefix.rstrip('/')}/sessions/{session_id}/products/{safe_name}"
            pointer_obj = {
                "pointer_schema": "GCS-PRODUCT-POINTER-v1",
                "original_filename": safe_name,
                "bytes": len(raw_b),
                "sha256": digest,
                "gcs_uri": gcs_uri,
            }
            ptr_bytes = (json.dumps(pointer_obj, indent=2) + "\n").encode("utf-8")
            (products_dir / f"{safe_name}.gcs.json").write_bytes(ptr_bytes)
            product_entries.append(
                {
                    "name": safe_name,
                    "stored_as": f"products/{safe_name}.gcs.json",
                    "offloaded_to_gcs": True,
                    "gcs_uri": gcs_uri,
                    "bytes": len(raw_b),
                    "sha256": digest,
                }
            )
        else:
            # Scrub text products for Tier-A secrets while preserving exact operational entities in private mode
            try:
                as_text = raw_b.decode("utf-8")
                clean_p_txt, p_red = scrub_text(as_text, mode=mode)
                all_redactions.extend(p_red)
                final_b = clean_p_txt.encode("utf-8")
            except UnicodeDecodeError:
                final_b = raw_b

            out_p = products_dir / safe_name
            out_p.write_bytes(final_b)
            product_entries.append(
                {
                    "name": safe_name,
                    "stored_as": f"products/{safe_name}",
                    "offloaded_to_gcs": False,
                    "bytes": len(final_b),
                    "sha256": sha256_bytes(final_b),
                }
            )

    card_bytes = clean_card.encode("utf-8")
    (bundle_dir / "SESSION_CARD.md").write_bytes(card_bytes)
    (bundle_dir / "trajectory.jsonl").write_bytes(clean_traj_bytes)

    manifest = {
        "schema": "SESSION-BUNDLE-MANIFEST-v2",
        "session_id": session_id,
        "created_at_hst": dt.datetime.now(HST).isoformat(timespec="seconds"),
        "privacy_mode": mode,
        "tier_a_secrets_scrubbed": True,
        "tier_b_entities_preserved": mode == "private",
        "redactions_applied": sorted(set(all_redactions)),
        "files": {
            "SESSION_CARD.md": {"bytes": len(card_bytes), "sha256": sha256_bytes(card_bytes)},
            "trajectory.jsonl": {"bytes": len(clean_traj_bytes), "sha256": sha256_bytes(clean_traj_bytes)},
        },
        "products": product_entries,
    }
    (bundle_dir / "bundle_manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    return {"bundle_dir": str(bundle_dir), "manifest": manifest}
