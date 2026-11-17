#!/usr/bin/env python3
"""Automated GitHub Multi-Agent Orchestrator Core Engine (GH-ORCHESTRATOR-v1).

Implements the 6-stage control plane separating stateless/checkpointed coordination
from isolated, read-only worker execution:
  1. Signed Webhook HMAC (`X-Hub-Signature-256`) & Collaborator Role Admission
  2. Typed Inter-Agent Schemas (`SubTask`, `OrchestrationPlan`, dual Pydantic/stdlib)
  3. Single-Pass Context Discovery, Disjoint Wave DAG Validation & `0444`+SHA-256 Plan Lock
  4. Sandboxed Worker Diff Scope & Safe-Outputs Policy Gate
  5. AST Element-Retention Verifier (`<= 20%` symbol drop) & Bounded 3-Attempt CI Repair
  6. Controlled `agent-work/*` Umbrella Merges, OTel JSONL Telemetry & Orphan Reaping
"""
from __future__ import annotations

import argparse
import ast
from collections import deque
from dataclasses import asdict, dataclass, field
import datetime as dt
import fnmatch
import hashlib
import hmac
import json
import os
from pathlib import Path
import re
import stat
import subprocess
import sys
from typing import Any

try:
    from pydantic import BaseModel as _PydanticBaseModel, ConfigDict, field_validator
    HAS_PYDANTIC = True
except ImportError:  # Bare CI Python 3.12 fallback
    _PydanticBaseModel = object  # type: ignore[assignment,misc]
    HAS_PYDANTIC = False

PLAN_SCHEMA_ID = "GH-ORCHESTRATION-PLAN-v1"
SAFE_OUTPUT_SCHEMA_ID = "GH-WORKER-SAFE-OUTPUT-v1"
TELEMETRY_SCHEMA_ID = "GH-OTEL-SPAN-v1"

TRUSTED_AUTHOR_ASSOCIATIONS = frozenset({"OWNER", "MEMBER", "COLLABORATOR"})
TRUSTED_EXPLICIT_ROLES = frozenset({"admin", "maintain", "write"})
VALID_MODEL_TIERS = frozenset({"fast-discovery", "frontier-planner", "code-worker", "judge-review"})
PROTECTED_BRANCH_PATTERNS = ("main", "master", "production", "release/*")
DEFAULT_ALLOWED_UMBRELLA_PATTERNS = ("agent-work/*",)

TRACKER_ID_RE = re.compile(r"^[A-Za-z0-9._:-]{6,128}$")
TASK_ID_RE = re.compile(r"^[A-Za-z0-9._-]+$")
UMBRELLA_BRANCH_RE = re.compile(r"^agent-work/[A-Za-z0-9._/-]+$")

EMAIL_PII_RE = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
WIN_PATH_PII_RE = re.compile(r"[A-Za-z]:[/\\]Users[/\\][A-Za-z0-9._-]+", re.IGNORECASE)
SECRET_TOKEN_RE = re.compile(
    r"(?:\b(?:ya29\.[A-Za-z0-9_-]{12,}|AIza[0-9A-Za-z_-]{20,}|ghp_[A-Za-z0-9]{20,}|"
    r"github_pat_[A-Za-z0-9_]{20,}|sk-[A-Za-z0-9_-]{20,}|1//[A-Za-z0-9_-]{20,}|"
    r"xox[baprs]-[A-Za-z0-9-]{10,})\b|-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----)"
)


def utc_now_iso() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat()


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def canonical_json_bytes(obj: Any) -> bytes:
    return (json.dumps(obj, sort_keys=True, indent=2) + "\n").encode("utf-8")


# ---------------------------------------------------------------------------
# Step 2A: Ingress Admission — HMAC Signature & Collaborator Role Guard
# ---------------------------------------------------------------------------


def verify_webhook_hmac(payload: bytes, signature_header: str | None, secret: str) -> bool:
    """Validate GitHub X-Hub-Signature-256 HMAC header using constant-time compare."""
    if not secret or not signature_header or not isinstance(signature_header, str):
        return False
    if not signature_header.startswith("sha256="):
        return False
    provided_hex = signature_header[len("sha256=") :].strip().lower()
    if len(provided_hex) != 64 or any(c not in "0123456789abcdef" for c in provided_hex):
        return False
    expected_hex = hmac.new(secret.encode("utf-8"), payload, hashlib.sha256).hexdigest()
    return hmac.compare_digest(provided_hex, expected_hex)


def authorize_collaborator_role(
    author_association: str | None,
    explicit_permission: str | None = None,
) -> bool:
    """Reject untrusted actors before invoking any planner or worker LLM."""
    if explicit_permission and explicit_permission.strip().lower() in TRUSTED_EXPLICIT_ROLES:
        return True
    if not author_association:
        return False
    return author_association.strip().upper() in TRUSTED_AUTHOR_ASSOCIATIONS


# ---------------------------------------------------------------------------
# Step 2B: Typed State Schemas (Pydantic v2 when installed + stdlib parity)
# ---------------------------------------------------------------------------


def _validate_subtask_fields(
    task_id: str,
    issue_number: int,
    owned_paths: list[str],
    depends_on: list[str],
    acceptance_criteria: list[str],
    model_tier: str,
    token_budget: int,
    heartbeat_timeout_sec: int,
) -> None:
    if not TASK_ID_RE.match(task_id):
        raise ValueError(f"Invalid task_id: {task_id!r}")
    if int(issue_number) < 1:
        raise ValueError(f"issue_number must be >= 1, got {issue_number!r}")
    if not owned_paths or any(not p.strip() for p in owned_paths):
        raise ValueError(f"SubTask {task_id!r} requires at least one non-empty owned_path")
    for dep in depends_on:
        if not TASK_ID_RE.match(dep):
            raise ValueError(f"Invalid dependency task_id {dep!r} in {task_id!r}")
        if dep == task_id:
            raise ValueError(f"SubTask {task_id!r} cannot depend on itself")
    if not acceptance_criteria or any(len(c.strip()) < 3 for c in acceptance_criteria):
        raise ValueError(f"SubTask {task_id!r} requires non-empty acceptance_criteria")
    if model_tier not in VALID_MODEL_TIERS:
        raise ValueError(f"Unsupported model_tier {model_tier!r}; expected one of {sorted(VALID_MODEL_TIERS)}")
    if not (1000 <= int(token_budget) <= 2_000_000):
        raise ValueError(f"token_budget out of bounds [1000, 2000000]: {token_budget}")
    if not (60 <= int(heartbeat_timeout_sec) <= 7200):
        raise ValueError(f"heartbeat_timeout_sec out of bounds [60, 7200]: {heartbeat_timeout_sec}")


def _validate_plan_fields(
    tracker_id: str,
    umbrella_branch: str,
    tasks: list[Any],
    source_issue: int,
    discovery_sha256: str,
) -> None:
    if not TRACKER_ID_RE.match(tracker_id):
        raise ValueError(f"Invalid tracker_id: {tracker_id!r}")
    if not UMBRELLA_BRANCH_RE.match(umbrella_branch):
        raise ValueError(
            f"umbrella_branch {umbrella_branch!r} must match 'agent-work/<slug>' and never target main"
        )
    if int(source_issue) < 1:
        raise ValueError(f"source_issue must be >= 1, got {source_issue!r}")
    if discovery_sha256 and (
        len(discovery_sha256) != 64 or any(c not in "0123456789abcdef" for c in discovery_sha256)
    ):
        raise ValueError(f"Invalid discovery_sha256: {discovery_sha256!r}")
    if not tasks:
        raise ValueError("OrchestrationPlan requires at least one SubTask")


if HAS_PYDANTIC:

    class SubTask(_PydanticBaseModel):
        model_config = ConfigDict(extra="forbid")

        task_id: str
        issue_number: int
        owned_paths: list[str]
        depends_on: list[str] = []
        acceptance_criteria: list[str]
        model_tier: str = "code-worker"
        token_budget: int = 120_000
        heartbeat_timeout_sec: int = 900

        def model_post_init(self, __context: Any) -> None:
            _validate_subtask_fields(
                self.task_id,
                self.issue_number,
                self.owned_paths,
                self.depends_on,
                self.acceptance_criteria,
                self.model_tier,
                self.token_budget,
                self.heartbeat_timeout_sec,
            )

    class OrchestrationPlan(_PydanticBaseModel):
        model_config = ConfigDict(extra="forbid")

        schema_id: str = PLAN_SCHEMA_ID
        tracker_id: str
        umbrella_branch: str
        source_issue: int = 1
        discovery_sha256: str = "0" * 64
        created_at_utc: str = ""
        tasks: list[SubTask]

        @field_validator("created_at_utc", mode="before")
        @classmethod
        def _default_created(cls, v: str) -> str:
            return v or utc_now_iso()

        def model_post_init(self, __context: Any) -> None:
            if not self.created_at_utc:
                object.__setattr__(self, "created_at_utc", utc_now_iso())
            _validate_plan_fields(
                self.tracker_id,
                self.umbrella_branch,
                self.tasks,
                self.source_issue,
                self.discovery_sha256,
            )

        def to_canonical_dict(self) -> dict[str, Any]:
            raw = self.model_dump()
            raw["schema"] = raw.pop("schema_id", PLAN_SCHEMA_ID)
            return raw

        @classmethod
        def from_dict(cls, data: dict[str, Any]) -> "OrchestrationPlan":
            copied = dict(data)
            if "schema" in copied and "schema_id" not in copied:
                copied["schema_id"] = copied.pop("schema")
            return cls.model_validate(copied)

else:

    @dataclass
    class SubTask:  # type: ignore[no-redef]
        task_id: str
        issue_number: int
        owned_paths: list[str]
        depends_on: list[str] = field(default_factory=list)
        acceptance_criteria: list[str] = field(default_factory=list)
        model_tier: str = "code-worker"
        token_budget: int = 120_000
        heartbeat_timeout_sec: int = 900

        def __post_init__(self) -> None:
            _validate_subtask_fields(
                self.task_id,
                self.issue_number,
                self.owned_paths,
                self.depends_on,
                self.acceptance_criteria,
                self.model_tier,
                self.token_budget,
                self.heartbeat_timeout_sec,
            )

        def model_dump(self) -> dict[str, Any]:
            return asdict(self)

        @classmethod
        def model_validate(cls, data: dict[str, Any] | "SubTask") -> "SubTask":
            if isinstance(data, SubTask):
                return data
            return cls(**data)

    @dataclass
    class OrchestrationPlan:  # type: ignore[no-redef]
        tracker_id: str
        umbrella_branch: str
        tasks: list[SubTask]
        schema_id: str = PLAN_SCHEMA_ID
        source_issue: int = 1
        discovery_sha256: str = "0" * 64
        created_at_utc: str = field(default_factory=utc_now_iso)

        def __post_init__(self) -> None:
            self.tasks = [SubTask.model_validate(t) for t in self.tasks]
            if not self.created_at_utc:
                self.created_at_utc = utc_now_iso()
            _validate_plan_fields(
                self.tracker_id,
                self.umbrella_branch,
                self.tasks,
                self.source_issue,
                self.discovery_sha256,
            )

        def model_dump(self) -> dict[str, Any]:
            return {
                "schema_id": self.schema_id,
                "tracker_id": self.tracker_id,
                "umbrella_branch": self.umbrella_branch,
                "source_issue": self.source_issue,
                "discovery_sha256": self.discovery_sha256,
                "created_at_utc": self.created_at_utc,
                "tasks": [t.model_dump() for t in self.tasks],
            }

        def to_canonical_dict(self) -> dict[str, Any]:
            raw = self.model_dump()
            raw["schema"] = raw.pop("schema_id", PLAN_SCHEMA_ID)
            return raw

        @classmethod
        def from_dict(cls, data: dict[str, Any]) -> "OrchestrationPlan":
            copied = dict(data)
            if "schema" in copied and "schema_id" not in copied:
                copied["schema_id"] = copied.pop("schema")
            return cls(**copied)


# ---------------------------------------------------------------------------
# Step 3: Context Discovery, Disjoint Path Geometry & Plan State Locking
# ---------------------------------------------------------------------------

KNOWN_MANIFEST_NAMES = frozenset(
    {
        "manifest.json",
        "pyproject.toml",
        "requirements.txt",
        "package.json",
        "Cargo.toml",
        "go.mod",
        "Makefile",
    }
)


@dataclass
class RepoContextSummary:
    repo_root_name: str
    tracked_file_count: int
    top_level_entries: list[str]
    manifests: list[str]
    workflows: list[str]
    test_commands: list[str]
    summary_sha256: str = ""

    def to_dict(self) -> dict[str, Any]:
        payload = {
            "repo_root_name": self.repo_root_name,
            "tracked_file_count": self.tracked_file_count,
            "top_level_entries": self.top_level_entries,
            "manifests": self.manifests,
            "workflows": self.workflows,
            "test_commands": self.test_commands,
        }
        digest = sha256_bytes(canonical_json_bytes(payload))
        payload["summary_sha256"] = digest
        return payload


def discover_repo_context(repo_root: Path, output_path: Path | None = None) -> RepoContextSummary:
    """Single-pass repository indexer preventing redundant downstream worker scans."""
    repo_root = repo_root.resolve()
    rel_files: list[str] = []
    try:
        proc = subprocess.run(
            ["git", "-C", str(repo_root), "ls-files"],
            capture_output=True,
            text=True,
            check=True,
        )
        rel_files = sorted(line.strip() for line in proc.stdout.splitlines() if line.strip())
    except Exception:
        for p in sorted(repo_root.rglob("*")):
            if p.is_file() and ".git" not in p.parts and ".orchestrator" not in p.parts:
                rel_files.append(p.relative_to(repo_root).as_posix())

    top_entries = sorted({rel.split("/", 1)[0] for rel in rel_files})
    manifests = [rel for rel in rel_files if Path(rel).name in KNOWN_MANIFEST_NAMES]
    workflows = [rel for rel in rel_files if rel.startswith(".github/workflows/") and rel.endswith((".yml", ".yaml", ".md"))]

    test_cmds: list[str] = []
    if "verify.py" in rel_files:
        test_cmds.append("python3 verify.py")
    for rel in rel_files:
        if rel.endswith(".py") and Path(rel).name.startswith("test_"):
            test_cmds.append(f"python3 {rel}")

    summary = RepoContextSummary(
        repo_root_name=repo_root.name,
        tracked_file_count=len(rel_files),
        top_level_entries=top_entries,
        manifests=manifests,
        workflows=workflows,
        test_commands=test_cmds,
    )
    serialized = summary.to_dict()
    summary.summary_sha256 = serialized["summary_sha256"]

    if output_path is not None:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_bytes(canonical_json_bytes(serialized))
    return summary


def _normalize_glob(pattern: str) -> str:
    norm = pattern.strip().replace("\\", "/")
    while norm.startswith("./"):
        norm = norm[2:]
    norm = re.sub(r"/{2,}", "/", norm).strip("/")
    return norm or "*"


def _glob_to_regex(pattern: str) -> re.Pattern[str]:
    norm = _normalize_glob(pattern)
    # Directory-prefix shorthand: "src/auth" owns "src/auth" and everything underneath if no wildcards/ext
    parts: list[str] = ["^"]
    i = 0
    n = len(norm)
    while i < n:
        if norm[i : i + 3] == "**/":
            parts.append("(?:.+/)?")
            i += 3
        elif norm[i : i + 2] == "**":
            parts.append(".*")
            i += 2
        elif norm[i] == "*":
            parts.append("[^/]*")
            i += 1
        elif norm[i] == "?":
            parts.append("[^/]")
            i += 1
        else:
            parts.append(re.escape(norm[i]))
            i += 1
    parts.append("$")
    return re.compile("".join(parts))


def _static_prefix_segments(pattern: str) -> tuple[list[str], bool]:
    norm = _normalize_glob(pattern)
    segs = norm.split("/")
    static: list[str] = []
    has_glob = False
    for s in segs:
        if any(ch in s for ch in "*?["):
            has_glob = True
            break
        static.append(s)
    return static, has_glob


def _sample_witness_paths(pattern: str) -> list[str]:
    norm = _normalize_glob(pattern)
    concrete = norm.replace("**/", "nested/sub/").replace("**", "nested/leaf.py").replace("*", "sample").replace("?", "x")
    concrete_shallow = norm.replace("**/", "").replace("**", "sample.py").replace("*", "sample").replace("?", "x")
    return [concrete, concrete_shallow]


def path_matches_owned(rel_path: str, owned_patterns: list[str]) -> bool:
    norm_path = _normalize_glob(rel_path)
    for raw_pat in owned_patterns:
        norm_pat = _normalize_glob(raw_pat)
        if _glob_to_regex(norm_pat).match(norm_path):
            return True
        # Treat bare directory path (e.g. "src/module") as owning descendants "src/module/..."
        if not any(ch in norm_pat for ch in "*?[") and "." not in Path(norm_pat).name:
            if norm_path == norm_pat or norm_path.startswith(norm_pat + "/"):
                return True
    return False


def paths_overlap(glob_a: str, glob_b: str) -> bool:
    """Return True if two owned_path globs/prefixes can match any common repository file."""
    na = _normalize_glob(glob_a)
    nb = _normalize_glob(glob_b)
    if na == nb or na in ("*", "**") or nb in ("*", "**"):
        return True

    # Check witness paths in both directions
    for cand in _sample_witness_paths(na):
        if path_matches_owned(cand, [nb]):
            return True
    for cand in _sample_witness_paths(nb):
        if path_matches_owned(cand, [na]):
            return True

    # Leading wildcard-free segments constrain every matching path deterministically:
    # if they diverge at any concrete segment index < min_len, intersection is empty.
    segs_a, glob_flag_a = _static_prefix_segments(na)
    segs_b, glob_flag_b = _static_prefix_segments(nb)
    min_len = min(len(segs_a), len(segs_b))
    if segs_a[:min_len] != segs_b[:min_len]:
        return False

    # Same static prefix up to min_len: check subtree globbing
    if len(segs_a) <= len(segs_b) and (na.endswith("/**") or (not glob_flag_a and "." not in Path(na).name)):
        return True
    if len(segs_b) <= len(segs_a) and (nb.endswith("/**") or (not glob_flag_b and "." not in Path(nb).name)):
        return True
    return False


def validate_plan_and_waves(
    plan: OrchestrationPlan,
    enforce_global_disjoint: bool = True,
) -> list[list[SubTask]]:
    """Validate task DAG acyclicity, compute parallel execution waves, and block path overlaps."""
    task_map: dict[str, SubTask] = {}
    for t in plan.tasks:
        if t.task_id in task_map:
            raise ValueError(f"Duplicate task_id in OrchestrationPlan: {t.task_id!r}")
        for pat in t.owned_paths:
            norm = _normalize_glob(pat)
            if norm.startswith(".orchestrator/plans"):
                raise ValueError(f"Task {t.task_id!r} cannot own immutable plan state path {pat!r}")
        task_map[t.task_id] = t

    indeg: dict[str, int] = {tid: 0 for tid in task_map}
    dependents: dict[str, list[str]] = {tid: [] for tid in task_map}
    for t in plan.tasks:
        for dep in dict.fromkeys(t.depends_on):
            if dep not in task_map:
                raise ValueError(f"Task {t.task_id!r} depends on unknown task_id {dep!r}")
            indeg[t.task_id] += 1
            dependents[dep].append(t.task_id)

    waves: list[list[SubTask]] = []
    ready = sorted(tid for tid, d in indeg.items() if d == 0)
    visited = 0
    while ready:
        waves.append([task_map[tid] for tid in ready])
        visited += len(ready)
        next_ready: list[str] = []
        for tid in ready:
            for child in dependents[tid]:
                indeg[child] -= 1
                if indeg[child] == 0:
                    next_ready.append(child)
        ready = sorted(next_ready)

    if visited != len(task_map):
        raise ValueError(f"Dependency cycle detected in OrchestrationPlan ({visited}/{len(task_map)} tasks resolved)")

    # Check disjoint file ownership across parallel wave peers (and globally if requested)
    groups_to_check: list[list[SubTask]] = [list(plan.tasks)] if enforce_global_disjoint else waves
    for group in groups_to_check:
        for i in range(len(group)):
            for j in range(i + 1, len(group)):
                ta, tb = group[i], group[j]
                for pa in ta.owned_paths:
                    for pb in tb.owned_paths:
                        if paths_overlap(pa, pb):
                            raise ValueError(
                                f"Overlapping owned_paths between tasks {ta.task_id!r} ({pa!r}) "
                                f"and {tb.task_id!r} ({pb!r})"
                            )
    return waves


def lock_plan_file(plan: OrchestrationPlan, plan_path: Path) -> str:
    """Validate, serialize, write, and lock plan read-only (`chmod 0444`) + `.sha256` sidecar."""
    validate_plan_and_waves(plan)
    plan_path.parent.mkdir(parents=True, exist_ok=True)
    if plan_path.exists():
        os.chmod(plan_path, stat.S_IRUSR | stat.S_IWUSR)

    raw = canonical_json_bytes(plan.to_canonical_dict())
    digest = sha256_bytes(raw)
    plan_path.write_bytes(raw)
    os.chmod(plan_path, 0o444)

    sidecar = plan_path.with_suffix(plan_path.suffix + ".sha256")
    if sidecar.exists():
        os.chmod(sidecar, stat.S_IRUSR | stat.S_IWUSR)
    sidecar.write_text(f"{digest}  {plan_path.name}\n", encoding="utf-8")
    os.chmod(sidecar, 0o444)
    return digest


def verify_plan_lock(plan_path: Path, expected_sha256: str) -> tuple[bool, list[str]]:
    """Verify both cryptographic integrity (`plan_sha256`) and read-only OS mode."""
    errors: list[str] = []
    if not plan_path.is_file():
        return False, [f"Locked plan missing at {plan_path.as_posix()}"]
    actual = sha256_bytes(plan_path.read_bytes())
    if actual != expected_sha256:
        errors.append(f"Plan lock tampered: expected sha256={expected_sha256}, got {actual}")
    mode = stat.S_IMODE(plan_path.stat().st_mode)
    if mode & (stat.S_IWUSR | stat.S_IWGRP | stat.S_IWOTH):
        errors.append(f"Plan file {plan_path.name} is writable (octal mode {oct(mode)}); expected 0o444")
    return len(errors) == 0, errors


# ---------------------------------------------------------------------------
# Step 4: Sandboxed Worker Diff Scope & Zero-PII Safe-Outputs Enforcement
# ---------------------------------------------------------------------------


def scan_zero_pii_text(label: str, text: str) -> list[str]:
    errs: list[str] = []
    if EMAIL_PII_RE.search(text):
        errs.append(f"Zero-PII violation in {label}: email pattern detected")
    if WIN_PATH_PII_RE.search(text):
        errs.append(f"Zero-PII violation in {label}: Windows user path detected")
    if SECRET_TOKEN_RE.search(text):
        errs.append(f"Zero-PII violation in {label}: secret token pattern detected")
    return errs


def validate_worker_diff_scope(
    task: SubTask,
    changed_paths: list[str],
    current_plan_bytes: bytes,
    expected_plan_sha256: str,
) -> list[str]:
    """Safe-outputs gate ensuring worker did not mutate plan or escape `task.owned_paths`."""
    errors: list[str] = []
    actual_plan_sha = sha256_bytes(current_plan_bytes)
    if actual_plan_sha != expected_plan_sha256:
        errors.append(
            f"Worker mutated locked OrchestrationPlan (expected {expected_plan_sha256}, got {actual_plan_sha})"
        )

    for rel in changed_paths:
        norm = _normalize_glob(rel)
        if norm.startswith(".orchestrator/plans/"):
            errors.append(f"Worker attempted forbidden write to locked plan directory: {norm}")
            continue
        if not path_matches_owned(norm, task.owned_paths):
            errors.append(
                f"Scope violation: task {task.task_id!r} modified {norm!r} outside owned_paths={task.owned_paths}"
            )
    return errors


# ---------------------------------------------------------------------------
# Step 5: AST Element-Retention Gate (`<= 20%` Drop) & 3-Strike CI Repair
# ---------------------------------------------------------------------------


@dataclass
class ASTCheckResult:
    file_path: str
    passed: bool
    before_count: int
    after_count: int
    drop_ratio: float
    dropped_symbols: list[str]
    syntax_error: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _collect_ast_symbols(tree: ast.AST) -> set[str]:
    symbols: set[str] = set()

    def _walk_body(stmts: list[ast.stmt], prefix: str) -> None:
        for node in stmts:
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                qual = f"{prefix}.{node.name}" if prefix else node.name
                symbols.add(f"fn:{qual}")
                _walk_body(node.body, qual)
            elif isinstance(node, ast.ClassDef):
                qual = f"{prefix}.{node.name}" if prefix else node.name
                symbols.add(f"cls:{qual}")
                _walk_body(node.body, qual)

    if isinstance(tree, ast.Module):
        _walk_body(tree.body, "")
    return symbols


def check_ast_retention(
    before_source: str,
    after_source: str,
    max_drop_ratio: float = 0.20,
    file_path: str = "<memory>",
) -> ASTCheckResult:
    """Block Python diffs that fail AST parsing or drop >20% of existing functions/classes."""
    try:
        before_tree = ast.parse(before_source, filename=file_path)
    except SyntaxError:
        before_symbols: set[str] = set()
    else:
        before_symbols = _collect_ast_symbols(before_tree)

    try:
        after_tree = ast.parse(after_source, filename=file_path)
    except SyntaxError as exc:
        return ASTCheckResult(
            file_path=file_path,
            passed=False,
            before_count=len(before_symbols),
            after_count=0,
            drop_ratio=1.0 if before_symbols else 0.0,
            dropped_symbols=sorted(before_symbols),
            syntax_error=f"Line {exc.lineno}: {exc.msg}",
        )

    after_symbols = _collect_ast_symbols(after_tree)
    dropped = sorted(before_symbols - after_symbols)
    if not before_symbols:
        drop_ratio = 0.0
    else:
        drop_ratio = round(len(dropped) / len(before_symbols), 6)

    passed = drop_ratio <= (max_drop_ratio + 1e-9)
    return ASTCheckResult(
        file_path=file_path,
        passed=passed,
        before_count=len(before_symbols),
        after_count=len(after_symbols),
        drop_ratio=drop_ratio,
        dropped_symbols=dropped,
    )


@dataclass
class RepairDecision:
    action: str  # "DISPATCH_REPAIR" | "HALT_AND_ESCALATE"
    attempt: int
    max_attempts: int
    halted_for_human: bool
    escalation_label: str
    remove_labels: list[str]
    repair_prompt: str
    reason: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class CIRepairController:
    """Bounded CI repair state machine capping automated fix commits at 3 iterations."""

    task_id: str
    max_attempts: int = 3
    token_budget: int = 120_000
    attempts_used: int = 0
    tokens_consumed: int = 0
    halted_for_human: bool = False
    annotations_history: list[str] = field(default_factory=list)

    def record_failure_and_decide(
        self,
        check_annotations: list[str],
        tokens_delta: int = 0,
    ) -> RepairDecision:
        self.tokens_consumed += max(0, int(tokens_delta))
        digest = "; ".join(a.strip() for a in check_annotations if a.strip()) or "Unspecified CI failure"
        self.annotations_history.append(digest)

        if self.tokens_consumed > self.token_budget:
            self.halted_for_human = True
            return RepairDecision(
                action="HALT_AND_ESCALATE",
                attempt=self.attempts_used,
                max_attempts=self.max_attempts,
                halted_for_human=True,
                escalation_label="state:blocked",
                remove_labels=["state:claimed"],
                repair_prompt="",
                reason=f"Token circuit breaker tripped ({self.tokens_consumed} > {self.token_budget})",
            )

        if self.attempts_used >= self.max_attempts:
            self.halted_for_human = True
            return RepairDecision(
                action="HALT_AND_ESCALATE",
                attempt=self.attempts_used,
                max_attempts=self.max_attempts,
                halted_for_human=True,
                escalation_label="state:blocked",
                remove_labels=["state:claimed"],
                repair_prompt="",
                reason=f"Exhausted max_attempts={self.max_attempts} automated CI repair iterations",
            )

        self.attempts_used += 1
        prompt = (
            f"[CI Repair Attempt {self.attempts_used}/{self.max_attempts}] "
            f"Fix task {self.task_id} strictly within owned_paths. Annotations: {digest}"
        )
        return RepairDecision(
            action="DISPATCH_REPAIR",
            attempt=self.attempts_used,
            max_attempts=self.max_attempts,
            halted_for_human=False,
            escalation_label="none",
            remove_labels=[],
            repair_prompt=prompt,
            reason="Within bounded CI repair budget",
        )


# ---------------------------------------------------------------------------
# Step 6: Controlled Umbrella Merges, Telemetry & Stale-Heartbeat Reaping
# ---------------------------------------------------------------------------


def validate_merge_target(
    base_branch: str,
    allowed_base_patterns: tuple[str, ...] = DEFAULT_ALLOWED_UMBRELLA_PATTERNS,
) -> bool:
    """Restrict automated worker merges strictly to non-protected integration branches."""
    branch = base_branch.strip()
    if branch.startswith("refs/heads/"):
        branch = branch[len("refs/heads/") :]
    if not branch:
        return False
    for protected in PROTECTED_BRANCH_PATTERNS:
        if fnmatch.fnmatchcase(branch, protected):
            return False
    return any(fnmatch.fnmatchcase(branch, pat) for pat in allowed_base_patterns)


def evaluate_umbrella_progression(
    plan: OrchestrationPlan,
    completed_task_ids: set[str],
    integration_ci_passed: bool,
) -> dict[str, Any]:
    """Compute newly unblocked downstream tasks or authorize 1 consolidated PR to `main`."""
    waves = validate_plan_and_waves(plan)
    all_ids = {t.task_id for t in plan.tasks}
    unknown = completed_task_ids - all_ids
    if unknown:
        raise ValueError(f"Unknown completed_task_ids: {sorted(unknown)}")

    unblocked_next: list[str] = []
    for t in plan.tasks:
        if t.task_id in completed_task_ids:
            continue
        if all(dep in completed_task_ids for dep in t.depends_on):
            unblocked_next.append(t.task_id)

    all_tasks_merged = completed_task_ids == all_ids
    open_consolidated_main_pr = bool(all_tasks_merged and integration_ci_passed)
    return {
        "tracker_id": plan.tracker_id,
        "umbrella_branch": plan.umbrella_branch,
        "wave_count": len(waves),
        "completed_count": len(completed_task_ids),
        "total_tasks": len(all_ids),
        "unblocked_task_ids": sorted(unblocked_next),
        "all_tasks_merged_to_umbrella": all_tasks_merged,
        "ready_for_consolidated_main_pr": open_consolidated_main_pr,
        "consolidated_pr_target": "main" if open_consolidated_main_pr else None,
    }


@dataclass
class TelemetrySpan:
    tracker_id: str
    task_id: str
    stage: str
    model_tier: str
    prompt_tokens: int
    completion_tokens: int
    tool_calls: int
    checkpoint_sha: str
    status: str = "OK"
    heartbeat_utc: str = field(default_factory=utc_now_iso)

    def to_otel_record(self) -> dict[str, Any]:
        return {
            "schema": TELEMETRY_SCHEMA_ID,
            "tracker_id": self.tracker_id,
            "task_id": self.task_id,
            "stage": self.stage,
            "status": self.status,
            "attributes": {
                "gen_ai.request.model_tier": self.model_tier,
                "gen_ai.usage.input_tokens": self.prompt_tokens,
                "gen_ai.usage.output_tokens": self.completion_tokens,
                "orchestrator.tool_calls": self.tool_calls,
                "git.checkpoint.sha": self.checkpoint_sha,
            },
            "heartbeat_utc": self.heartbeat_utc,
        }


def append_telemetry_span(ledger_path: Path, span: TelemetrySpan) -> dict[str, Any]:
    record = span.to_otel_record()
    pii_errs = scan_zero_pii_text("telemetry_span", json.dumps(record))
    if pii_errs:
        raise ValueError("; ".join(pii_errs))
    ledger_path.parent.mkdir(parents=True, exist_ok=True)
    with ledger_path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(record, sort_keys=True) + "\n")
    return record


def reap_stalled_workers(
    worker_heartbeats: dict[str, str],
    timeout_sec: int = 900,
    now_utc: dt.datetime | None = None,
) -> list[str]:
    """Identify orphaned/stalled workers whose last heartbeat exceeds `timeout_sec`."""
    ref_now = now_utc or dt.datetime.now(dt.timezone.utc)
    stalled: list[str] = []
    for task_id, ts_raw in sorted(worker_heartbeats.items()):
        parsed = dt.datetime.fromisoformat(ts_raw.replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=dt.timezone.utc)
        age = (ref_now - parsed).total_seconds()
        if age > timeout_sec:
            stalled.append(task_id)
    return stalled


# ---------------------------------------------------------------------------
# CLI Interface for GitHub Actions & Local Verification
# ---------------------------------------------------------------------------


def _cmd_discover(args: argparse.Namespace) -> int:
    out = Path(args.output) if args.output else None
    summary = discover_repo_context(Path(args.repo_root), output_path=out)
    print(json.dumps(summary.to_dict(), indent=2))
    return 0


def _cmd_bootstrap_smoke_plan(args: argparse.Namespace) -> int:
    repo_root = Path(args.repo_root).resolve()
    ctx_path = repo_root / ".orchestrator" / "context_summary.json"
    summary = discover_repo_context(repo_root, output_path=ctx_path)
    plan = OrchestrationPlan(
        tracker_id=args.tracker_id,
        umbrella_branch=args.umbrella_branch,
        source_issue=args.issue_number,
        discovery_sha256=summary.summary_sha256,
        tasks=[
            SubTask(
                task_id="worker-code-scope",
                issue_number=args.issue_number,
                owned_paths=["architecture/github-orchestration/src/**"],
                depends_on=[],
                acceptance_criteria=["Pass AST retention <=20% drop and Zero-PII verifier"],
                model_tier="code-worker",
            ),
            SubTask(
                task_id="worker-schema-scope",
                issue_number=args.issue_number,
                owned_paths=["architecture/github-orchestration/schemas/**"],
                depends_on=[],
                acceptance_criteria=["Maintain JSON Schema Draft 2020-12 validity"],
                model_tier="code-worker",
            ),
            SubTask(
                task_id="worker-integration-tests",
                issue_number=args.issue_number,
                owned_paths=["architecture/github-orchestration/tests/**"],
                depends_on=["worker-code-scope", "worker-schema-scope"],
                acceptance_criteria=["Pass full orchestrator unit and worktree test suite"],
                model_tier="judge-review",
            ),
        ],
    )
    plan_path = Path(args.plan_path)
    digest = lock_plan_file(plan, plan_path)
    waves = validate_plan_and_waves(plan)
    print(
        json.dumps(
            {
                "ok": True,
                "tracker_id": plan.tracker_id,
                "umbrella_branch": plan.umbrella_branch,
                "plan_path": plan_path.as_posix(),
                "plan_sha256": digest,
                "discovery_sha256": summary.summary_sha256,
                "wave_0_task_ids": [t.task_id for t in waves[0]],
                "wave_count": len(waves),
            },
            indent=2,
        )
    )
    return 0


def _cmd_check_merge_target(args: argparse.Namespace) -> int:
    allowed = validate_merge_target(args.base_branch)
    print(json.dumps({"base_branch": args.base_branch, "allowed_automated_merge": allowed}))
    return 0 if allowed else 1


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Automated GitHub Multi-Agent Orchestrator Engine")
    sub = ap.add_subparsers(dest="cmd", required=True)

    p_disc = sub.add_parser("discover", help="Generate single-pass repository context summary")
    p_disc.add_argument("--repo-root", default=".", help="Repository root directory")
    p_disc.add_argument("--output", default=None, help="Optional JSON output path")
    p_disc.set_defaults(func=_cmd_discover)

    p_plan = sub.add_parser("bootstrap-plan", help="Discover context, validate disjoint waves, and lock 0444 plan")
    p_plan.add_argument("--repo-root", default=".")
    p_plan.add_argument("--tracker-id", required=True)
    p_plan.add_argument("--umbrella-branch", required=True)
    p_plan.add_argument("--issue-number", type=int, default=1)
    p_plan.add_argument("--plan-path", required=True)
    p_plan.set_defaults(func=_cmd_bootstrap_smoke_plan)

    p_merge = sub.add_parser("check-merge-target", help="Verify base branch matches allowed agent-work/* pattern")
    p_merge.add_argument("--base-branch", required=True)
    p_merge.set_defaults(func=_cmd_check_merge_target)

    args = ap.parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":
    sys.exit(main())
