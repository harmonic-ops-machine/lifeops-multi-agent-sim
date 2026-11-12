#!/usr/bin/env python3
"""Zero-dependency Cross-Seat, Closed-Loop & Zero-PII Simulation Verifier (v7.0.0).

Can be executed by ANY independent session or device:
  - Local Seat (Codex V-0, Hermes --safe-mode, Claude Code, PowerShell):
      python verify.py
  - Remote / Hosted HTTPS Instance Verification:
      python verify.py --url https://harmonic-garden.space.fast
"""
from __future__ import annotations

import argparse
from collections import deque
import hashlib
import json
from pathlib import Path
import re
import sys
import urllib.request

EMAIL_RE = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
WIN_USER_RE = re.compile(r"[A-Za-z]:\\Users\\[A-Za-z0-9._-]+", re.IGNORECASE)
TOKEN_RE = re.compile(r"\b(ya29\.[A-Za-z0-9_-]{12,}|AIza[0-9A-Za-z_-]{20,}|ghp_[A-Za-z0-9]{20,}|sk-[A-Za-z0-9_-]{20,})\b")


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def fetch_or_read(base_url: str | None, base_dir: Path, name: str) -> bytes:
    if base_url:
        u = base_url.rstrip("/")
        with urllib.request.urlopen(f"{u}/{name}", timeout=15) as r:
            return r.read()
    return (base_dir / name).read_bytes()


def check_zero_pii_bytes(label: str, raw: bytes) -> list[str]:
    txt = raw.decode("utf-8", errors="replace")
    errs = []
    if EMAIL_RE.search(txt):
        errs.append(f"Zero-PII violation in {label}: email address pattern detected")
    if WIN_USER_RE.search(txt):
        errs.append(f"Zero-PII violation in {label}: local Windows user path detected")
    if TOKEN_RE.search(txt):
        errs.append(f"Zero-PII violation in {label}: credential token pattern detected")
    return errs


def verify_bundle(base_url: str | None, base_dir: Path) -> dict:
    spec_raw = fetch_or_read(base_url, base_dir, "simulation_spec.json")
    man_raw = fetch_or_read(base_url, base_dir, "manifest.json")
    feed_raw = fetch_or_read(base_url, base_dir, "carbon_loop_feed.json")
    spec = json.loads(spec_raw.decode("utf-8"))
    manifest = json.loads(man_raw.decode("utf-8"))
    feed = json.loads(feed_raw.decode("utf-8"))

    errors: list[str] = []

    # 1. Cryptographic SHA-256 parity
    for fname, raw_b in [("simulation_spec.json", spec_raw), ("carbon_loop_feed.json", feed_raw)]:
        actual = sha256_bytes(raw_b)
        expected = manifest.get("files", {}).get(fname, {}).get("sha256")
        if actual != expected:
            errors.append(f"SHA-256 mismatch on {fname}: got {actual}, expected {expected}")

    # 2. Schema version parity
    if spec.get("schema_version") != manifest.get("version"):
        errors.append(f"Version mismatch: spec={spec.get('schema_version')} vs manifest={manifest.get('version')}")
    if feed.get("schema") != "CARBON-FEED-v1":
        errors.append(f"Invalid Carbon feed schema: {feed.get('schema')}")

    # 3. Zero-PII airgap verification across public artifacts
    errors.extend(check_zero_pii_bytes("simulation_spec.json", spec_raw))
    errors.extend(check_zero_pii_bytes("carbon_loop_feed.json", feed_raw))

    # 4. Kahn topological sort (DAG acyclicity)
    nodes = spec.get("nodes", [])
    node_ids = [n["id"] for n in nodes]
    if len(node_ids) != len(set(node_ids)):
        errors.append("Duplicate node IDs detected")
    node_set = set(node_ids)

    indeg = {nid: 0 for nid in node_set}
    adj: dict[str, list[str]] = {nid: [] for nid in node_set}
    edge_pairs = set()
    for u, v, _ in spec.get("edges", []):
        if u not in node_set or v not in node_set:
            errors.append(f"Dangling edge reference: {u} -> {v}")
            continue
        edge_pairs.add((u, v))
        adj[u].append(v)
        indeg[v] += 1

    q = deque([nid for nid, d in indeg.items() if d == 0])
    visited = 0
    while q:
        cur = q.popleft()
        visited += 1
        for nxt in adj[cur]:
            indeg[nxt] -= 1
            if indeg[nxt] == 0:
                q.append(nxt)
    if visited != len(node_set):
        errors.append(f"Cycle detected in dependency graph: visited {visited}/{len(node_set)} nodes")

    # 5. Mandatory Multi-Agent & Leakage Isolation Invariants
    required_edges = [
        ("SEC-P1", "REM-CC"),
        ("FENCE-GH", "REM-CC"),
        ("FENCE-GH", "VER-GIT"),
        ("FENCE-APP", "VAL-HRM"),
        ("FENCE-CLIP", "SEC-P2"),
        ("FENCE-CLIP", "CARBON-LOOP"),
        ("VER-GIT", "CARBON-LOOP"),
        ("CARBON-LOOP", "LEG-GATE1"),
        ("VER-GIT", "VAL-HRM"),
        ("VER-GIT", "VAL-CDX"),
        ("VAL-CDX", "LEG-GATE1"),
        ("VAL-HRM", "LEG-GATE1"),
    ]
    for req_u, req_v in required_edges:
        if (req_u, req_v) not in edge_pairs:
            errors.append(f"Missing mandatory isolation edge: {req_u} -> {req_v}")

    if len(spec.get("dry_run_self_tests", [])) < 12:
        errors.append("Expected >=12 PreToolUse adversarial self-tests in v7.0.0")
    if len(spec.get("leakage_surfaces", [])) < 9:
        errors.append("Expected >=9 audited leakage surfaces (L1-L9) in v7.0.0")

    return {
        "ok": len(errors) == 0,
        "version": manifest.get("version"),
        "git_commit": manifest.get("git_head_parent", "staged"),
        "spec_sha256": sha256_bytes(spec_raw),
        "carbon_feed_sha256": sha256_bytes(feed_raw),
        "zero_pii_verified": True if not any("Zero-PII" in e for e in errors) else False,
        "node_count": len(nodes),
        "edge_count": len(spec.get("edges", [])),
        "leakage_surfaces_count": len(spec.get("leakage_surfaces", [])),
        "errors": errors,
    }


def main() -> int:
    ap = argparse.ArgumentParser(description="Deterministic Multi-Seat & Zero-PII Verifier v7.0.0")
    ap.add_argument("--url", default=None, help="Verify remote HTTPS or loopback instance URL")
    ap.add_argument("--dir", default=str(Path(__file__).resolve().parent), help="Local bundle directory")
    args = ap.parse_args()

    report = verify_bundle(args.url, Path(args.dir))
    print(json.dumps(report, indent=2))
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
