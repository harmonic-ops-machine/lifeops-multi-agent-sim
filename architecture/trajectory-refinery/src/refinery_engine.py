#!/usr/bin/env python3
"""Trajectory Refinery Core Engine (v8.3.0).

Normalizes raw Gemini App exports / Takeout JSON records into canonical
SESSION-TRACE-v1 JSONL streams, separates conversational noise from durable
engineering decisions (L1), extracts structured root-cause analysis records
(L2: SESSION-RCA-v1), and emits actionable guardrail patch proposals (L3).
"""
from __future__ import annotations

import datetime as dt
import hashlib
import json
from pathlib import Path
import re
from typing import Any

HST = dt.timezone(dt.timedelta(hours=-10), name="HST")

NOISE_PATTERNS = (
    re.compile(r"^\s*(nobody has spoken for a while|are you still there)\b", re.I),
    re.compile(r"^\s*(ok|okay|dobrze|dzięki|dzieki|thanks|test|halo)\s*[.!?]*\s*$", re.I),
    re.compile(r"^\s*i'll (look into|update|configure|verify)\b.*-\s*$", re.I),
)

CORRECTION_AND_ERROR_RULES: list[tuple[str, str, re.Pattern[str], str]] = [
    (
        "ASR_VOICE_MISRECOGNITION",
        "asr_clip_or_substitution",
        re.compile(r"\b(misheard|clipped|urwało się|przerwane zdanie|osobny agent|nie inżynier)\b", re.I),
        "Verify raw audio/turn continuity before acting on ambiguous voice ASR nouns; ask one concise clarifying question on clipped tails.",
    ),
    (
        "TOOL_OR_CONNECTOR_LIMITATION",
        "connector_or_headless_limit",
        re.compile(r"\b(read-only|tylko do odczytu|hung silently|headless|batchexecute|something went wrong \(13\))\b", re.I),
        "Route writes through dedicated SSH or single-tool Cloud Run MCP endpoints rather than read-only consumer connectors or interactive GUI prompts inside headless shells.",
    ),
    (
        "ENVIRONMENT_CONFIG_MISMATCH",
        "bom_or_config_encoding",
        re.compile(r"\b(bad configuration option|\\357\\273\\277|utf-8 bom|permission denied \(publickey\))\b", re.I),
        "Write SSH and dotfile configs as BOM-less UTF-8 bytes and pin core.sshCommand to deterministic system OpenSSH.",
    ),
    (
        "PREMATURE_COMPLETION_CLAIM",
        "unverified_claim",
        re.compile(r"\b(before tool success|prematurely|przed wykonaniem|zanim narzędzie)\b", re.I),
        "Enforce verification-before-completion: assert exit code 0 and remote state parity before reporting any push or mutation as done.",
    ),
    (
        "INSTRUCTION_DRIFT_OR_AMBIGUITY",
        "user_correction_signal",
        re.compile(r"\b(nie o to chodzi|popraw|błąd|error|fatal:|failed|zamiast tego)\b", re.I),
        "Capture explicit operator correction into AGENTS.md / GEMINI.md and add a regression check to the PreToolUse guard when deterministic.",
    ),
]

TARGET_SURFACE_BY_CATEGORY = {
    "ASR_VOICE_MISRECOGNITION": "gemini_web_saved_info",
    "TOOL_OR_CONNECTOR_LIMITATION": "workflow_script",
    "ENVIRONMENT_CONFIG_MISMATCH": "pretool_single_hub_guard.py",
    "PREMATURE_COMPLETION_CLAIM": "AGENTS.md",
    "INSTRUCTION_DRIFT_OR_AMBIGUITY": "GEMINI.md",
    "MISSING_CONTEXT_OR_MEMORY": "GEMINI.md",
    "API_OR_PERMISSION_FAILURE": "skill_update",
}


def now_hst_iso() -> str:
    return dt.datetime.now(HST).isoformat(timespec="seconds")


def sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def classify_turn_signals(role: str, content: str, modality: str = "text") -> dict[str, Any]:
    text = content.strip()
    markers: list[str] = []
    is_noise = not text
    for pat in NOISE_PATTERNS:
        if pat.search(text):
            is_noise = True
            markers.append("conversational_noise_or_cutoff")
            break

    is_err = False
    for category, marker_slug, pat, _ in CORRECTION_AND_ERROR_RULES:
        if pat.search(text):
            is_err = True
            markers.append(f"{category}:{marker_slug}")

    if is_err:
        # Never discard error evidence as mere noise in the Bronze trace;
        # the Separate Auditor needs it for L2 RCA before excluding it from L1 distilled output.
        is_noise = False

    if modality == "voice_asr" and text.endswith("-"):
        markers.append("ASR_VOICE_MISRECOGNITION:trailing_cutoff")
        is_err = True

    return {
        "is_noise_candidate": is_noise,
        "is_error_or_correction": is_err,
        "detected_markers": markers,
    }


def normalize_turns_to_trace(
    session_id: str,
    raw_turns: list[dict[str, Any]],
    source_surface: str = "gemini_app_docs_export",
    captured_at_hst: str | None = None,
) -> list[dict[str, Any]]:
    ts = captured_at_hst or now_hst_iso()
    trace: list[dict[str, Any]] = []
    for idx, item in enumerate(raw_turns):
        role = str(item.get("role") or "user").lower()
        if role not in ("user", "assistant", "tool", "system"):
            role = "user"
        modality = str(item.get("modality") or "text")
        content = str(item.get("content") or "")
        signals = classify_turn_signals(role=role, content=content, modality=modality)
        record: dict[str, Any] = {
            "schema": "SESSION-TRACE-v1",
            "session_id": session_id,
            "source_surface": source_surface,
            "captured_at_hst": str(item.get("captured_at_hst") or ts),
            "turn_index": idx,
            "role": role,
            "modality": modality,
            "content": content,
            "signals": signals,
        }
        if item.get("gcs_attachment_uris"):
            record["gcs_attachment_uris"] = list(item["gcs_attachment_uris"])
        trace.append(record)
    return trace


def serialize_trace_jsonl(trace: list[dict[str, Any]]) -> bytes:
    lines = [json.dumps(row, ensure_ascii=False, sort_keys=True) for row in trace]
    return ("\n".join(lines) + "\n").encode("utf-8")


def run_refinery_audit(
    trace: list[dict[str, Any]],
    auditor_agent: str = "RefineryAuditor-v8.3",
    gcs_raw_archive_uri: str | None = None,
    analyzed_at_hst: str | None = None,
) -> dict[str, Any]:
    """Execute L1 noise pruning, L2 root-cause extraction, and L3 patch generation."""
    if not trace:
        raise ValueError("Cannot audit an empty session trace.")

    session_id = trace[0]["session_id"]
    ts = analyzed_at_hst or now_hst_iso()
    raw_bytes = serialize_trace_jsonl(trace)
    raw_sha = sha256_hex(raw_bytes)

    kept_turns: list[dict[str, Any]] = []
    pruned_count = 0
    incidents_by_cat: dict[str, dict[str, Any]] = {}

    for row in trace:
        sig = row["signals"]
        if sig["is_noise_candidate"]:
            pruned_count += 1
            continue

        if sig["is_error_or_correction"]:
            # Error/diagnostic turns feed L2 postmortem rather than polluting L1 clean state,
            # unless it is a user turn establishing a durable requirement.
            for marker in sig["detected_markers"]:
                cat = marker.split(":", 1)[0]
                resolution = next(
                    (res for c, _, _, res in CORRECTION_AND_ERROR_RULES if c == cat),
                    "Add explicit preflight verification and update canonical agent instructions.",
                )
                if cat not in incidents_by_cat:
                    incidents_by_cat[cat] = {
                        "incident_id": f"INC-{session_id}-{len(incidents_by_cat) + 1:02d}",
                        "turn_indices": [],
                        "root_cause_category": cat,
                        "symptom": row["content"][:200],
                        "causal_origin": f"Detected via trajectory marker '{marker}' on turn {row['turn_index']}.",
                        "best_resolution": resolution,
                    }
                incidents_by_cat[cat]["turn_indices"].append(row["turn_index"])

            if row["role"] != "user":
                pruned_count += 1
                continue

        kept_turns.append(row)

    total = len(trace)
    kept_n = len(kept_turns)
    ratio = round(pruned_count / total, 4) if total else 0.0

    incidents = list(incidents_by_cat.values())
    proposed_patches: list[dict[str, Any]] = []
    for inc in incidents:
        cat = inc["root_cause_category"]
        surface = TARGET_SURFACE_BY_CATEGORY.get(cat, "GEMINI.md")
        proposed_patches.append(
            {
                "target_surface": surface,
                "action": f"Harden {surface} against {cat}",
                "rationale": f"Prevent recurrence of {inc['incident_id']} (turns {inc['turn_indices']}).",
                "patch_snippet": f"- [{cat}] {inc['best_resolution']}",
            }
        )

    rca_payload: dict[str, Any] = {
        "schema": "SESSION-RCA-v1",
        "session_id": session_id,
        "analyzed_at_hst": ts,
        "auditor_agent": auditor_agent,
        "raw_trace_sha256": raw_sha,
        "gcs_raw_archive_uri": gcs_raw_archive_uri,
        "compression_metrics": {
            "total_turns": total,
            "kept_signal_turns": kept_n,
            "pruned_noise_turns": pruned_count,
            "noise_reduction_ratio": ratio,
        },
        "incidents": incidents,
        "proposed_patches": proposed_patches,
    }

    distilled_lines = [
        f"# Distilled Session State: `{session_id}`",
        "",
        f"- **Analyzed At (`HST`):** `{ts}`",
        f"- **Raw Trace SHA-256:** `{raw_sha}`",
        f"- **Signal Compression:** Kept `{kept_n}/{total}` turns (`{int(ratio * 100)}%` noise/retry turns removed)",
        "",
        "## Verified Decisions & Work Output",
    ]
    for kt in kept_turns:
        role_tag = kt["role"].upper()
        distilled_lines.append(f"- **[Turn {kt['turn_index']} · {role_tag}]** {kt['content'].strip()}")

    patch_lines = [
        f"# Guardrail Patch Proposal: `{session_id}`",
        "",
        f"Generated from `raw_trace_sha256={raw_sha}` (`{len(incidents)}` incident class(es)).",
        "",
    ]
    if not proposed_patches:
        patch_lines.append("No error or drift incidents detected; no rule mutations required.")
    else:
        for p in proposed_patches:
            patch_lines.extend(
                [
                    f"## Target: `{p['target_surface']}` — {p['action']}",
                    f"- **Rationale:** {p['rationale']}",
                    "```markdown",
                    p["patch_snippet"],
                    "```",
                    "",
                ]
            )

    return {
        "distilled_markdown": "\n".join(distilled_lines) + "\n",
        "rca_json": rca_payload,
        "patch_markdown": "\n".join(patch_lines) + "\n",
    }


def write_refinery_bundle(out_dir: Path, session_id: str, bundle: dict[str, Any], date_slug: str = "2026-11-16") -> dict[str, Path]:
    distilled_dir = out_dir / "distilled"
    postmortems_dir = out_dir / "postmortems"
    patches_dir = out_dir / "patches"
    for d in (distilled_dir, postmortems_dir, patches_dir):
        d.mkdir(parents=True, exist_ok=True)

    p_distilled = distilled_dir / f"{date_slug}_{session_id}.md"
    p_rca = postmortems_dir / f"{session_id}_rca.json"
    p_patch = patches_dir / f"{session_id}_patch.md"

    p_distilled.write_text(bundle["distilled_markdown"], encoding="utf-8")
    p_rca.write_text(json.dumps(bundle["rca_json"], indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    p_patch.write_text(bundle["patch_markdown"], encoding="utf-8")

    return {"distilled": p_distilled, "rca": p_rca, "patch": p_patch}
