#!/usr/bin/env python3
"""Trajectory Refinery Core Engine (v8.3.1).

Normalizes raw Gemini App exports / Takeout JSON records into canonical
SESSION-TRACE-v1 JSONL streams, separates conversational noise from durable
engineering decisions (L1), extracts structured root-cause analysis records
(L2: SESSION-RCA-v1), validates trace and RCA payloads against schema contracts,
and emits actionable guardrail patch proposals (L3).
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import html
import json
from pathlib import Path
import re
from typing import Any

HST = dt.timezone(dt.timedelta(hours=-10), name="HST")

VALID_ROLES = ("user", "assistant", "tool", "system")
VALID_MODALITIES = ("text", "voice_asr", "artifact", "tool_result")
VALID_SOURCE_SURFACES = (
    "gemini_app_mcp",
    "gemini_app_docs_export",
    "gemini_takeout_json",
    "antigravity_transcript",
)
VALID_ROOT_CAUSE_CATEGORIES = (
    "ASR_VOICE_MISRECOGNITION",
    "MISSING_CONTEXT_OR_MEMORY",
    "TOOL_OR_CONNECTOR_LIMITATION",
    "INSTRUCTION_DRIFT_OR_AMBIGUITY",
    "API_OR_PERMISSION_FAILURE",
    "PREMATURE_COMPLETION_CLAIM",
    "ENVIRONMENT_CONFIG_MISMATCH",
)
VALID_PATCH_SURFACES = (
    "GEMINI.md",
    "AGENTS.md",
    "gemini_web_saved_info",
    "pretool_single_hub_guard.py",
    "skill_update",
    "workflow_script",
)
GCS_URI_RE = re.compile(r"^gs://[a-z0-9._-]+/.+")
SHA256_HEX_RE = re.compile(r"^[a-f0-9]{64}$")

NOISE_PATTERNS = (
    re.compile(r"^\s*(nobody has spoken for a while|are you still there)\b", re.I),
    re.compile(r"^\s*(ok|okay|dobrze|dzięki|dzieki|thanks|test|halo)\s*[.!?]*\s*$", re.I),
    re.compile(r"^\s*i'll (look into|update|configure|verify)\b.*-\s*$", re.I),
)

RUNTIME_CRASH_RE = re.compile(
    r"(?:^|\n)(?:Traceback \(most recent call last\)|fatal:|ERROR:|RuntimeError:|ValueError:)|\bfatal:\s|\bTraceback \(most recent call last\)",
    re.M,
)

CORRECTION_AND_ERROR_RULES: list[tuple[str, str, re.Pattern[str], str]] = [
    (
        "ASR_VOICE_MISRECOGNITION",
        "asr_clip_or_substitution",
        re.compile(r"\b(misheard|clipped|urwało się|przerwane zdanie|osobny agent|nie inżynier)\b", re.I),
        "Verify raw audio/turn continuity before acting on ambiguous voice ASR nouns; ask one concise clarifying question on clipped tails.",
    ),
    (
        "MISSING_CONTEXT_OR_MEMORY",
        "missing_prior_session_context",
        re.compile(r"\b(lost context|missing context|forgot earlier|brak kontekstu|nie pamiętasz|zgubiony wątek)\b", re.I),
        "Load NEXT_SESSION_BOOTSTRAP.md and CONTINUITY_CHECKPOINT.json on SessionStart before planning or acting.",
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
        "API_OR_PERMISSION_FAILURE",
        "http_auth_or_iam_denial",
        re.compile(r"\b(401 unauthorized|403 forbidden|permission_denied|insufficient permissions|quota exceeded|resource_exhausted)\b", re.I),
        "Verify IAM principal bindings, OAuth scopes, and preflight health endpoints before invoking cloud mutations.",
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
        re.compile(r"\b(nie o to chodzi\w*|popraw to|zamiast tego|źle zrozumiał\w*|wrong repo|wrong branch)\b", re.I),
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

SPEAKER_LINE_RE = re.compile(
    r"^\s*(?:#{1,6}\s*|\*\*)?(you|user|gemini|assistant|tool|system)(?:\*\*)?\s*:?\s*(.*)$",
    re.I,
)
HTML_BREAK_RE = re.compile(r"<(?:br\s*/?|/(?:p|div|li|h[1-6]))>", re.I)
HTML_TAG_RE = re.compile(r"<[^>]+>")


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

    if RUNTIME_CRASH_RE.search(text) and (
        role == "tool" or modality == "tool_result" or "fatal:" in text.lower()
    ):
        if not any(m.startswith(("ENVIRONMENT_CONFIG_MISMATCH:", "API_OR_PERMISSION_FAILURE:")) for m in markers):
            markers.append("ENVIRONMENT_CONFIG_MISMATCH:runtime_crash")
        is_err = True

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
    clean_session_id = str(session_id or "").strip()
    if len(clean_session_id) < 4:
        raise ValueError("session_id must be at least 4 characters.")
    if source_surface not in VALID_SOURCE_SURFACES:
        raise ValueError(f"Unsupported source_surface: {source_surface}")

    ts = captured_at_hst or now_hst_iso()
    trace: list[dict[str, Any]] = []
    for idx, item in enumerate(raw_turns):
        role = str(item.get("role") or "user").lower()
        if role not in VALID_ROLES:
            role = "user"
        modality = str(item.get("modality") or "text")
        if modality not in VALID_MODALITIES:
            modality = "text"
        content = str(item.get("content") or "")
        signals = classify_turn_signals(role=role, content=content, modality=modality)
        record: dict[str, Any] = {
            "schema": "SESSION-TRACE-v1",
            "session_id": clean_session_id,
            "source_surface": source_surface,
            "captured_at_hst": str(item.get("captured_at_hst") or ts),
            "turn_index": idx,
            "role": role,
            "modality": modality,
            "content": content,
            "signals": signals,
        }
        if item.get("gcs_attachment_uris"):
            uris = [str(u) for u in item["gcs_attachment_uris"]]
            for uri in uris:
                if not GCS_URI_RE.match(uri):
                    raise ValueError(f"Invalid GCS URI in gcs_attachment_uris: {uri}")
            record["gcs_attachment_uris"] = uris
        trace.append(record)
    return trace


def validate_trace_records(trace: list[dict[str, Any]]) -> None:
    """Validate SESSION-TRACE-v1 records against schemas/session_trace.schema.json."""
    if not isinstance(trace, list) or not trace:
        raise ValueError("Trace must be a non-empty list of SESSION-TRACE-v1 records.")

    required = {
        "schema",
        "session_id",
        "source_surface",
        "captured_at_hst",
        "turn_index",
        "role",
        "content",
        "signals",
    }
    allowed = required | {"modality", "gcs_attachment_uris"}

    for idx, rec in enumerate(trace):
        if not isinstance(rec, dict):
            raise ValueError(f"Trace record {idx} is not an object.")
        keys = set(rec.keys())
        missing = required - keys
        if missing:
            raise ValueError(f"Trace record {idx} missing keys: {sorted(missing)}")
        extra = keys - allowed
        if extra:
            raise ValueError(f"Trace record {idx} has unexpected keys: {sorted(extra)}")
        if rec["schema"] != "SESSION-TRACE-v1":
            raise ValueError(f"Trace record {idx} invalid schema: {rec['schema']}")
        if not isinstance(rec["session_id"], str) or len(rec["session_id"]) < 4:
            raise ValueError(f"Trace record {idx} session_id violates minLength 4.")
        if rec["source_surface"] not in VALID_SOURCE_SURFACES:
            raise ValueError(f"Trace record {idx} invalid source_surface: {rec['source_surface']}")
        if not isinstance(rec["captured_at_hst"], str):
            raise ValueError(f"Trace record {idx} captured_at_hst must be a string.")
        if not isinstance(rec["turn_index"], int) or isinstance(rec["turn_index"], bool) or rec["turn_index"] < 0:
            raise ValueError(f"Trace record {idx} invalid turn_index: {rec['turn_index']}")
        if rec["role"] not in VALID_ROLES:
            raise ValueError(f"Trace record {idx} invalid role: {rec['role']}")
        if rec.get("modality", "text") not in VALID_MODALITIES:
            raise ValueError(f"Trace record {idx} invalid modality: {rec.get('modality')}")
        if not isinstance(rec["content"], str):
            raise ValueError(f"Trace record {idx} content must be a string.")
        if "gcs_attachment_uris" in rec:
            uris = rec["gcs_attachment_uris"]
            if not isinstance(uris, list) or not all(isinstance(u, str) and GCS_URI_RE.match(u) for u in uris):
                raise ValueError(f"Trace record {idx} contains invalid gcs_attachment_uris.")
        sig = rec["signals"]
        if not isinstance(sig, dict):
            raise ValueError(f"Trace record {idx} signals must be an object.")
        sig_req = {"is_noise_candidate", "is_error_or_correction", "detected_markers"}
        if not sig_req.issubset(sig.keys()):
            raise ValueError(f"Trace record {idx} signals missing keys.")
        if not isinstance(sig["is_noise_candidate"], bool) or not isinstance(sig["is_error_or_correction"], bool):
            raise ValueError(f"Trace record {idx} signal flags must be booleans.")
        if not isinstance(sig["detected_markers"], list) or not all(isinstance(m, str) for m in sig["detected_markers"]):
            raise ValueError(f"Trace record {idx} detected_markers must be an array of strings.")


def validate_rca_payload(rca: dict[str, Any]) -> None:
    """Validate SESSION-RCA-v1 output against schemas/session_rca.schema.json."""
    if not isinstance(rca, dict):
        raise ValueError("RCA payload must be an object.")
    required = {
        "schema",
        "session_id",
        "analyzed_at_hst",
        "auditor_agent",
        "raw_trace_sha256",
        "compression_metrics",
        "incidents",
        "proposed_patches",
    }
    allowed = required | {"gcs_raw_archive_uri"}
    keys = set(rca.keys())
    if not required.issubset(keys):
        raise ValueError(f"RCA payload missing keys: {sorted(required - keys)}")
    extra = keys - allowed
    if extra:
        raise ValueError(f"RCA payload has unexpected keys: {sorted(extra)}")
    if rca["schema"] != "SESSION-RCA-v1":
        raise ValueError(f"Invalid RCA schema: {rca['schema']}")
    for str_key in ("session_id", "analyzed_at_hst", "auditor_agent"):
        if not isinstance(rca[str_key], str):
            raise ValueError(f"RCA field {str_key} must be a string.")
    if not isinstance(rca["raw_trace_sha256"], str) or not SHA256_HEX_RE.match(rca["raw_trace_sha256"]):
        raise ValueError("RCA raw_trace_sha256 must be a 64-character lowercase hex digest.")
    uri = rca.get("gcs_raw_archive_uri")
    if uri is not None and not isinstance(uri, str):
        raise ValueError("RCA gcs_raw_archive_uri must be string or null.")

    metrics = rca["compression_metrics"]
    if not isinstance(metrics, dict):
        raise ValueError("RCA compression_metrics must be an object.")
    for int_key in ("total_turns", "kept_signal_turns", "pruned_noise_turns"):
        val = metrics.get(int_key)
        if not isinstance(val, int) or isinstance(val, bool) or val < 0:
            raise ValueError(f"Invalid compression_metrics.{int_key}: {val}")
    ratio = metrics.get("noise_reduction_ratio")
    if not isinstance(ratio, (int, float)) or isinstance(ratio, bool) or not (0.0 <= float(ratio) <= 1.0):
        raise ValueError(f"Invalid compression_metrics.noise_reduction_ratio: {ratio}")

    incidents = rca["incidents"]
    if not isinstance(incidents, list):
        raise ValueError("RCA incidents must be an array.")
    inc_req = {"incident_id", "turn_indices", "root_cause_category", "symptom", "causal_origin", "best_resolution"}
    for idx, inc in enumerate(incidents):
        if not isinstance(inc, dict) or not inc_req.issubset(inc.keys()):
            raise ValueError(f"Incident {idx} missing required keys.")
        if inc["root_cause_category"] not in VALID_ROOT_CAUSE_CATEGORIES:
            raise ValueError(f"Incident {idx} invalid root_cause_category: {inc['root_cause_category']}")
        t_indices = inc["turn_indices"]
        if not isinstance(t_indices, list) or not all(isinstance(i, int) and not isinstance(i, bool) and i >= 0 for i in t_indices):
            raise ValueError(f"Incident {idx} invalid turn_indices.")

    patches = rca["proposed_patches"]
    if not isinstance(patches, list):
        raise ValueError("RCA proposed_patches must be an array.")
    patch_req = {"target_surface", "action", "rationale", "patch_snippet"}
    for idx, patch in enumerate(patches):
        if not isinstance(patch, dict) or not patch_req.issubset(patch.keys()):
            raise ValueError(f"Proposed patch {idx} missing required keys.")
        if patch["target_surface"] not in VALID_PATCH_SURFACES:
            raise ValueError(f"Proposed patch {idx} invalid target_surface: {patch['target_surface']}")


def parse_docs_export_markdown(markdown_text: str) -> list[dict[str, Any]]:
    """Parse Channel A Gemini 'Export to Docs' Markdown into ordered turn dicts."""
    turns: list[dict[str, Any]] = []
    current_role: str | None = None
    buf: list[str] = []

    def flush() -> None:
        if current_role is not None:
            body = "\n".join(buf).strip()
            if body:
                turns.append({"role": current_role, "modality": "text", "content": body})

    for line in markdown_text.splitlines():
        m = SPEAKER_LINE_RE.match(line)
        if m:
            label = m.group(1).lower()
            rest = m.group(2).strip()
            has_heading_or_colon = line.lstrip().startswith(("#", "**")) or ":" in line.split(maxsplit=2)[0] or line.lstrip().lower().startswith(f"{label}:")
            if has_heading_or_colon:
                flush()
                buf = []
                current_role = "user" if label in ("you", "user") else ("tool" if label == "tool" else ("system" if label == "system" else "assistant"))
                if rest:
                    buf.append(rest)
                continue
        if current_role is not None:
            buf.append(line)

    flush()
    if not turns and markdown_text.strip():
        return [{"role": "user", "modality": "text", "content": markdown_text.strip()}]
    return turns


def _strip_takeout_html(raw_html: str) -> str:
    text = HTML_BREAK_RE.sub("\n", raw_html)
    text = HTML_TAG_RE.sub("", text)
    text = html.unescape(text)
    lines = [ln.strip() for ln in text.splitlines()]
    return "\n".join(ln for ln in lines if ln).strip()


def parse_takeout_activity_json(raw_json: str | list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Parse Channel B Google Takeout Gemini activity JSON records into ordered turn dicts."""
    records = json.loads(raw_json) if isinstance(raw_json, str) else raw_json
    if not isinstance(records, list):
        raise ValueError("Takeout activity payload must be a JSON array.")

    turns: list[dict[str, Any]] = []
    for item in records:
        if not isinstance(item, dict):
            continue
        if isinstance(item.get("role"), str) and isinstance(item.get("content"), str):
            turn: dict[str, Any] = {
                "role": item["role"].lower(),
                "modality": str(item.get("modality") or "text"),
                "content": item["content"],
            }
            if item.get("time") or item.get("captured_at_hst"):
                turn["captured_at_hst"] = str(item.get("captured_at_hst") or item.get("time"))
            turns.append(turn)
            continue

        ts = str(item["time"]) if item.get("time") else None
        title = str(item.get("title") or "").strip()
        if title:
            prompt_text = re.sub(r"^Prompted\s+", "", title, flags=re.I).strip()
            if prompt_text and prompt_text.lower() != "used gemini apps":
                u_turn: dict[str, Any] = {"role": "user", "modality": "text", "content": prompt_text}
                if ts:
                    u_turn["captured_at_hst"] = ts
                turns.append(u_turn)

        html_chunks: list[str] = []
        for sub in item.get("safeHtmlItem") or []:
            if isinstance(sub, dict) and sub.get("html"):
                cleaned = _strip_takeout_html(str(sub["html"]))
                if cleaned:
                    html_chunks.append(cleaned)
        if not html_chunks and item.get("html"):
            cleaned = _strip_takeout_html(str(item["html"]))
            if cleaned:
                html_chunks.append(cleaned)
        if html_chunks:
            a_turn: dict[str, Any] = {"role": "assistant", "modality": "text", "content": "\n\n".join(html_chunks)}
            if ts:
                a_turn["captured_at_hst"] = ts
            turns.append(a_turn)

    return turns


def serialize_trace_jsonl(trace: list[dict[str, Any]]) -> bytes:
    lines = [json.dumps(row, ensure_ascii=False, sort_keys=True) for row in trace]
    return ("\n".join(lines) + "\n").encode("utf-8")


def run_refinery_audit(
    trace: list[dict[str, Any]],
    auditor_agent: str = "RefineryAuditor-v8.3.1",
    gcs_raw_archive_uri: str | None = None,
    analyzed_at_hst: str | None = None,
) -> dict[str, Any]:
    """Execute L1 noise pruning, L2 root-cause extraction, and L3 patch generation."""
    if not trace:
        raise ValueError("Cannot audit an empty session trace.")
    validate_trace_records(trace)

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
            # unless it is a user turn establishing a durable requirement or clean assistant prose.
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
                if row["turn_index"] not in incidents_by_cat[cat]["turn_indices"]:
                    incidents_by_cat[cat]["turn_indices"].append(row["turn_index"])

            should_prune_non_user = (
                row["role"] == "tool"
                or row["modality"] == "tool_result"
                or bool(RUNTIME_CRASH_RE.search(row["content"]))
                or any(
                    m.endswith((":connector_or_headless_limit", ":bom_or_config_encoding", ":unverified_claim"))
                    for m in sig["detected_markers"]
                )
            )
            if row["role"] != "user" and should_prune_non_user:
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
    validate_rca_payload(rca_payload)

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

    p_distilled.write_text(bundle["distilled_markdown"], encoding="utf-8", newline="\n")
    p_rca.write_text(json.dumps(bundle["rca_json"], indent=2, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n")
    p_patch.write_text(bundle["patch_markdown"], encoding="utf-8", newline="\n")

    return {"distilled": p_distilled, "rca": p_rca, "patch": p_patch}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="HIGHRES Trajectory Refinery Engine CLI (v8.3.1)")
    ap.add_argument("--input", required=True, help="Path to input JSONL, Docs Markdown, or Takeout JSON file")
    ap.add_argument("--format", required=True, choices=["jsonl", "docs-md", "takeout-json"], help="Input format")
    ap.add_argument("--session-id", required=True, help="Canonical session_id (minLength 4)")
    ap.add_argument("--out-dir", default=None, help="Optional output directory for distilled/postmortems/patches")
    ap.add_argument("--gcs-uri", default=None, help="Optional gs:// raw archive URI to record in RCA")
    args = ap.parse_args(argv)

    in_path = Path(args.input)
    raw_text = in_path.read_text(encoding="utf-8")
    if args.format == "jsonl":
        trace = [json.loads(line) for line in raw_text.splitlines() if line.strip()]
    elif args.format == "docs-md":
        turns = parse_docs_export_markdown(raw_text)
        trace = normalize_turns_to_trace(args.session_id, turns, source_surface="gemini_app_docs_export")
    else:
        turns = parse_takeout_activity_json(raw_text)
        trace = normalize_turns_to_trace(args.session_id, turns, source_surface="gemini_takeout_json")

    bundle = run_refinery_audit(trace, gcs_raw_archive_uri=args.gcs_uri)
    if args.out_dir:
        write_refinery_bundle(Path(args.out_dir), args.session_id, bundle)
    print(json.dumps(bundle["rca_json"], indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
