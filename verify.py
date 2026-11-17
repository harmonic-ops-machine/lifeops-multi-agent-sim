#!/usr/bin/env python3
"""Zero-dependency Cross-Seat, Closed-Loop & Zero-PII Simulation Verifier (v8.3.1).

Can be executed by ANY independent session or device:
  - Local Seat (Full repo Zero-PII + manifest + DAG + advisories verification):
      python verify.py
  - Bundle-only verification (manifest + spec + feed + digest):
      python verify.py --bundle-only
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
import subprocess
import sys
import urllib.request

EMAIL_RE = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
WIN_USER_RE = re.compile(r"[A-Za-z]:[/\\]Users[/\\][A-Za-z0-9._-]+", re.IGNORECASE)
TOKEN_RE = re.compile(
    r"(?:\b(?:ya29\.[A-Za-z0-9_-]{12,}|AIza[0-9A-Za-z_-]{20,}|ghp_[A-Za-z0-9]{20,}|"
    r"github_pat_[A-Za-z0-9_]{20,}|sk-[A-Za-z0-9_-]{20,}|1//[A-Za-z0-9_-]{20,}|"
    r"xox[baprs]-[A-Za-z0-9-]{10,})\b|-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----)"
)


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
    errs: list[str] = []
    if EMAIL_RE.search(txt):
        errs.append(f"Zero-PII violation in {label}: email address pattern detected")
    if WIN_USER_RE.search(txt):
        errs.append(f"Zero-PII violation in {label}: local Windows user path detected")
    if TOKEN_RE.search(txt):
        errs.append(f"Zero-PII violation in {label}: credential token pattern detected")
    return errs


def _list_repo_files(base_dir: Path) -> list[Path]:
    try:
        proc = subprocess.run(
            ["git", "-C", str(base_dir), "ls-files"],
            capture_output=True,
            text=True,
            check=True,
        )
        rels = [line.strip() for line in proc.stdout.splitlines() if line.strip()]
        if rels:
            return [base_dir / rel for rel in rels]
    except Exception:
        pass
    return [p for p in base_dir.rglob("*") if p.is_file() and ".git" not in p.parts]


def verify_repo_tracked_files(base_dir: Path) -> tuple[list[str], int, int]:
    errs: list[str] = []
    checked_files = 0
    for fp in _list_repo_files(base_dir):
        if not fp.is_file():
            continue
        if fp.name == "verify-zero-pii.yml":
            continue
        rel = fp.relative_to(base_dir).as_posix()
        checked_files += 1
        errs.extend(check_zero_pii_bytes(rel, fp.read_bytes()))

    advisories_checked = 0
    adv_dir = base_dir / "advisories"
    if adv_dir.is_dir():
        for adv in sorted(adv_dir.glob("*.json")):
            advisories_checked += 1
            try:
                obj = json.loads(adv.read_text(encoding="utf-8"))
            except Exception as exc:
                errs.append(f"Invalid JSON in {adv.relative_to(base_dir).as_posix()}: {exc}")
                continue
            schema = obj.get("schema") or (obj.get("payload") or {}).get("schema")
            if schema not in ("CARBON-ADVISORY-v1", "CARBON-ADVISORY-v2"):
                errs.append(f"Unexpected schema in {adv.relative_to(base_dir).as_posix()}: {schema}")

    return errs, checked_files, advisories_checked


def verify_bundle(base_url: str | None, base_dir: Path, bundle_only: bool = False) -> dict:
    spec_raw = fetch_or_read(base_url, base_dir, "simulation_spec.json")
    man_raw = fetch_or_read(base_url, base_dir, "manifest.json")
    feed_raw = fetch_or_read(base_url, base_dir, "carbon_loop_feed.json")
    digest_raw = fetch_or_read(base_url, base_dir, "prior_work_digest.json")
    spec = json.loads(spec_raw.decode("utf-8"))
    manifest = json.loads(man_raw.decode("utf-8"))
    feed = json.loads(feed_raw.decode("utf-8"))

    errors: list[str] = []

    # 1. Cryptographic SHA-256 parity
    sha_targets: list[tuple[str, bytes]] = [
        ("simulation_spec.json", spec_raw),
        ("carbon_loop_feed.json", feed_raw),
        ("prior_work_digest.json", digest_raw),
    ]
    if base_url is None:
        for local_rel in ("index.html", "HANDOFF_REDACTED.md", "advisories/CA-20261112-001.json"):
            local_path = base_dir / local_rel
            if not local_path.is_file():
                errors.append(f"Missing manifest artifact on disk: {local_rel}")
            else:
                sha_targets.append((local_rel, local_path.read_bytes()))

    for fname, raw_b in sha_targets:
        actual = sha256_bytes(raw_b)
        expected = manifest.get("files", {}).get(fname, {}).get("sha256")
        if actual != expected:
            errors.append(f"SHA-256 mismatch on {fname}: got {actual}, expected {expected}")

    # 2. Schema version parity
    if spec.get("schema_version") != manifest.get("version"):
        errors.append(f"Version mismatch: spec={spec.get('schema_version')} vs manifest={manifest.get('version')}")
    if feed.get("schema") != "CARBON-FEED-v1":
        errors.append(f"Invalid Carbon feed schema: {feed.get('schema')}")

    # 3. Zero-PII airgap verification across public artifacts & tracked repo files
    errors.extend(check_zero_pii_bytes("simulation_spec.json", spec_raw))
    errors.extend(check_zero_pii_bytes("carbon_loop_feed.json", feed_raw))
    errors.extend(check_zero_pii_bytes("prior_work_digest.json", digest_raw))

    repo_files_checked = 0
    advisories_checked = 0
    if base_url is None and not bundle_only:
        repo_errs, repo_files_checked, advisories_checked = verify_repo_tracked_files(base_dir)
        errors.extend(repo_errs)

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
        ("SF-SYNC", "CARBON-LOOP"),
        ("CARBON-LOOP", "EXEC-FABLE"),
        ("EXEC-FABLE", "LEG-GATE1"),
        ("VER-GIT", "VAL-HRM"),
        ("VER-GIT", "VAL-CDX"),
        ("VAL-CDX", "LEG-GATE1"),
        ("VAL-HRM", "LEG-GATE1"),
    ]
    for req_u, req_v in required_edges:
        if (req_u, req_v) not in edge_pairs:
            errors.append(f"Missing mandatory isolation edge: {req_u} -> {req_v}")

    if len(spec.get("dry_run_self_tests", [])) < 12:
        errors.append("Expected >=12 PreToolUse adversarial self-tests in v8.0.0+")
    if len(spec.get("leakage_surfaces", [])) < 9:
        errors.append("Expected >=9 audited leakage surfaces (L1-L9) in v8.0.0+")

    return {
        "ok": len(errors) == 0,
        "version": manifest.get("version"),
        "verifier_version": "8.3.1",
        "git_commit": manifest.get("git_head_parent", "staged"),
        "spec_sha256": sha256_bytes(spec_raw),
        "carbon_feed_sha256": sha256_bytes(feed_raw),
        "prior_work_digest_sha256": sha256_bytes(digest_raw),
        "zero_pii_verified": not any("Zero-PII" in e for e in errors),
        "repo_files_checked": repo_files_checked,
        "advisories_checked": advisories_checked,
        "node_count": len(nodes),
        "edge_count": len(spec.get("edges", [])),
        "leakage_surfaces_count": len(spec.get("leakage_surfaces", [])),
        "errors": errors,
    }


def main() -> int:
    ap = argparse.ArgumentParser(description="Deterministic Multi-Seat & Zero-PII Verifier v8.3.1")
    ap.add_argument("--url", default=None, help="Verify remote HTTPS or loopback instance URL")
    ap.add_argument("--dir", default=str(Path(__file__).resolve().parent), help="Local bundle directory")
    ap.add_argument("--bundle-only", action="store_true", help="Verify core bundle artifacts without scanning all git files")
    args = ap.parse_args()

    report = verify_bundle(args.url, Path(args.dir), bundle_only=args.bundle_only)
    print(json.dumps(report, indent=2))
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
