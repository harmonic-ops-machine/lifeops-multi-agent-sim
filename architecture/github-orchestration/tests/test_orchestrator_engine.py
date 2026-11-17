#!/usr/bin/env python3
"""Deterministic & Adversarial Test Suite for GH-ORCHESTRATOR-v1.

Covers all 6 stages of the Automated GitHub Orchestration Agent specification:
  1. Privilege-separated `.aw.md` -> GitHub Actions YAML compilation (`aw_compiler.py`)
  2. `X-Hub-Signature-256` HMAC verification & collaborator role admission pre-LLM
  3. Single-pass repository context discovery, DAG cycle detection, overlapping
     `owned_paths` rejection, and `chmod 0444` + SHA-256 plan state locking
  4. Sandboxed worker diff scope enforcement & plan-tamper detection
  5. AST element-retention verifier (`<= 20%` drop allowed; `> 20%` blocked) &
     bounded 3-attempt CI repair circuit breaker (`state:blocked` escalation)
  6. End-to-end async `git worktree` multi-wave fan-out merging strictly into
     `agent-work/*` while `main` remains untouched + OTel JSONL & orphan reaping
"""
from __future__ import annotations

import asyncio
import datetime as dt
import hashlib
import hmac
import json
import os
from pathlib import Path
import stat
import subprocess
import sys
import tempfile
import threading
import unittest
import urllib.error
import urllib.request

REPO_ROOT = Path(__file__).resolve().parents[3]
SRC_DIR = REPO_ROOT / "architecture" / "github-orchestration" / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

import aw_compiler  # noqa: E402
import orchestrator_engine as eng  # noqa: E402
import webhook_gateway as gw  # noqa: E402


def _sign(body: bytes, secret: str) -> str:
    return "sha256=" + hmac.new(secret.encode("utf-8"), body, hashlib.sha256).hexdigest()


class GitHubOrchestratorTestSuite(unittest.TestCase):
    def test_01_webhook_hmac_and_collaborator_admission(self) -> None:
        secret = "test-webhook-hmac-key"
        payload = json.dumps(
            {
                "action": "labeled",
                "label": {"name": "state:ready"},
                "issue": {"number": 101, "author_association": "COLLABORATOR"},
            }
        ).encode("utf-8")

        # Reject missing or forged signature before any LLM invocation
        code_missing, _ = gw.admit_github_webhook(payload, {"X-GitHub-Event": "issues"}, secret)
        self.assertEqual(code_missing, 401)

        code_bad, _ = gw.admit_github_webhook(
            payload,
            {"X-GitHub-Event": "issues", "X-Hub-Signature-256": _sign(payload, "wrong-key")},
            secret,
        )
        self.assertEqual(code_bad, 401)

        # Reject untrusted contributor even with valid GitHub signature
        untrusted = json.dumps(
            {
                "action": "labeled",
                "label": {"name": "state:ready"},
                "issue": {"number": 101, "author_association": "FIRST_TIME_CONTRIBUTOR"},
            }
        ).encode("utf-8")
        code_untrusted, _ = gw.admit_github_webhook(
            untrusted,
            {"X-GitHub-Event": "issues", "X-Hub-Signature-256": _sign(untrusted, secret)},
            secret,
        )
        self.assertEqual(code_untrusted, 403)

        # Admit verified collaborator on state:ready label
        code_ok, resp = gw.admit_github_webhook(
            payload,
            {"X-GitHub-Event": "issues", "X-Hub-Signature-256": _sign(payload, secret)},
            secret,
        )
        self.assertEqual(code_ok, 200)
        self.assertTrue(resp["accepted"])
        self.assertEqual(resp["umbrella_branch"], "agent-work/issue-101")

    def test_02_http_server_ingress_roundtrip(self) -> None:
        secret = "loopback-hmac-secret"
        srv = gw.create_http_server("127.0.0.1", 0, secret)
        port = srv.server_address[1]
        thread = threading.Thread(target=srv.serve_forever, daemon=True)
        thread.start()
        try:
            body = json.dumps(
                {
                    "action": "created",
                    "issue": {"number": 42, "author_association": "OWNER"},
                    "comment": {"body": "/orchestrate split by module", "author_association": "OWNER"},
                }
            ).encode("utf-8")
            req = urllib.request.Request(
                f"http://127.0.0.1:{port}/webhook",
                data=body,
                headers={
                    "Content-Type": "application/json",
                    "X-GitHub-Event": "issue_comment",
                    "X-Hub-Signature-256": _sign(body, secret),
                },
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=5) as resp:
                self.assertEqual(resp.status, 200)
                parsed = json.loads(resp.read().decode("utf-8"))
                self.assertEqual(parsed["tracker_id"], "trk-issue-42")

            bad_req = urllib.request.Request(
                f"http://127.0.0.1:{port}/webhook",
                data=body,
                headers={"Content-Type": "application/json", "X-GitHub-Event": "issue_comment"},
                method="POST",
            )
            with self.assertRaises(urllib.error.HTTPError) as ctx:
                urllib.request.urlopen(bad_req, timeout=5)
            self.assertEqual(ctx.exception.code, 401)
        finally:
            srv.shutdown()
            srv.server_close()

    def test_03_context_discovery_and_disjoint_dag_waves(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            out_json = Path(tmp) / "context_summary.json"
            summary = eng.discover_repo_context(REPO_ROOT, output_path=out_json)
            self.assertGreaterEqual(summary.tracked_file_count, 20)
            self.assertIn("manifest.json", summary.manifests)
            self.assertIn("python3 verify.py", summary.test_commands)
            self.assertEqual(len(summary.summary_sha256), 64)

        # Reject main as umbrella_branch
        with self.assertRaises(ValueError):
            eng.OrchestrationPlan(
                tracker_id="trk-bad-main",
                umbrella_branch="main",
                tasks=[
                    eng.SubTask(
                        task_id="t1",
                        issue_number=1,
                        owned_paths=["src/a/**"],
                        depends_on=[],
                        acceptance_criteria=["Pass unit tests"],
                    )
                ],
            )

        # Reject overlapping owned_paths across tasks
        overlapping_plan = eng.OrchestrationPlan(
            tracker_id="trk-overlap-01",
            umbrella_branch="agent-work/issue-10",
            tasks=[
                eng.SubTask(
                    task_id="worker-a",
                    issue_number=10,
                    owned_paths=["src/auth/**"],
                    depends_on=[],
                    acceptance_criteria=["Implement token verifier"],
                ),
                eng.SubTask(
                    task_id="worker-b",
                    issue_number=10,
                    owned_paths=["src/auth/routes.py"],
                    depends_on=[],
                    acceptance_criteria=["Add route handler"],
                ),
            ],
        )
        with self.assertRaises(ValueError):
            eng.validate_plan_and_waves(overlapping_plan)

        # Reject dependency cycles
        cyclic_plan = eng.OrchestrationPlan(
            tracker_id="trk-cycle-01",
            umbrella_branch="agent-work/issue-11",
            tasks=[
                eng.SubTask(
                    task_id="t-alpha",
                    issue_number=11,
                    owned_paths=["mod_a/**"],
                    depends_on=["t-beta"],
                    acceptance_criteria=["Alpha ok"],
                ),
                eng.SubTask(
                    task_id="t-beta",
                    issue_number=11,
                    owned_paths=["mod_b/**"],
                    depends_on=["t-alpha"],
                    acceptance_criteria=["Beta ok"],
                ),
            ],
        )
        with self.assertRaises(ValueError):
            eng.validate_plan_and_waves(cyclic_plan)

        # Valid 2-wave fan-out DAG
        valid_plan = eng.OrchestrationPlan(
            tracker_id="trk-waves-01",
            umbrella_branch="agent-work/issue-12",
            tasks=[
                eng.SubTask(
                    task_id="wave0-api",
                    issue_number=12,
                    owned_paths=["services/api/**"],
                    depends_on=[],
                    acceptance_criteria=["API endpoints green"],
                ),
                eng.SubTask(
                    task_id="wave0-cli",
                    issue_number=12,
                    owned_paths=["services/cli/**"],
                    depends_on=[],
                    acceptance_criteria=["CLI subcommands green"],
                ),
                eng.SubTask(
                    task_id="wave1-e2e",
                    issue_number=12,
                    owned_paths=["e2e/**"],
                    depends_on=["wave0-api", "wave0-cli"],
                    acceptance_criteria=["E2E integration green"],
                ),
            ],
        )
        waves = eng.validate_plan_and_waves(valid_plan)
        self.assertEqual(len(waves), 2)
        self.assertEqual([t.task_id for t in waves[0]], ["wave0-api", "wave0-cli"])
        self.assertEqual([t.task_id for t in waves[1]], ["wave1-e2e"])

    def test_04_dual_plan_locking_and_worker_scope_gate(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            plan_path = Path(tmp) / ".orchestrator" / "plans" / "trk-lock-01.plan.json"
            task = eng.SubTask(
                task_id="scoped-worker",
                issue_number=7,
                owned_paths=["pkg/billing/**"],
                depends_on=[],
                acceptance_criteria=["No scope escape"],
            )
            plan = eng.OrchestrationPlan(
                tracker_id="trk-lock-01",
                umbrella_branch="agent-work/issue-7",
                tasks=[task],
            )
            plan_sha = eng.lock_plan_file(plan, plan_path)
            mode = stat.S_IMODE(plan_path.stat().st_mode)
            self.assertEqual(mode, 0o444)
            ok, errs = eng.verify_plan_lock(plan_path, plan_sha)
            self.assertTrue(ok, errs)

            # Out-of-scope file edit rejected
            scope_errs = eng.validate_worker_diff_scope(
                task=task,
                changed_paths=["pkg/billing/calc.py", "pkg/auth/secret.py"],
                current_plan_bytes=plan_path.read_bytes(),
                expected_plan_sha256=plan_sha,
            )
            self.assertEqual(len(scope_errs), 1)
            self.assertIn("pkg/auth/secret.py", scope_errs[0])

            # Mutated plan bytes rejected even if worker bypassed chmod 0444
            tampered_errs = eng.validate_worker_diff_scope(
                task=task,
                changed_paths=["pkg/billing/calc.py"],
                current_plan_bytes=b'{"tampered": true}',
                expected_plan_sha256=plan_sha,
            )
            self.assertEqual(len(tampered_errs), 1)
            self.assertIn("mutated locked OrchestrationPlan", tampered_errs[0])

    def test_05_ast_element_retention_gate(self) -> None:
        before_code = "\n".join(
            [
                "class Ledger:",
                "    def open(self): return True",
                "    def close(self): return True",
                "def fn_one(): return 1",
                "def fn_two(): return 2",
            ]
        )
        # 5 symbols total: cls:Ledger, fn:Ledger.open, fn:Ledger.close, fn:fn_one, fn:fn_two
        # Dropping 1 of 5 (20.0%) passes threshold <= 0.20
        after_20pct = "\n".join(
            [
                "class Ledger:",
                "    def open(self): return True",
                "    def close(self): return True",
                "def fn_one(): return 1",
            ]
        )
        res_ok = eng.check_ast_retention(before_code, after_20pct, max_drop_ratio=0.20)
        self.assertTrue(res_ok.passed)
        self.assertAlmostEqual(res_ok.drop_ratio, 0.20)

        # Dropping 2 of 5 (40.0%) + adding decoy function STILL fails (>20% existing dropped!)
        after_40pct_with_decoy = "\n".join(
            [
                "class Ledger:",
                "    def open(self): return True",
                "def fn_one(): return 1",
                "def decoy_replacement(): return 99",
            ]
        )
        res_fail = eng.check_ast_retention(before_code, after_40pct_with_decoy, max_drop_ratio=0.20)
        self.assertFalse(res_fail.passed)
        self.assertAlmostEqual(res_fail.drop_ratio, 0.40)
        self.assertEqual(res_fail.dropped_symbols, ["fn:Ledger.close", "fn:fn_two"])

        # Syntax error in worker output fails immediately
        res_syntax = eng.check_ast_retention(before_code, "def broken(:\n    pass")
        self.assertFalse(res_syntax.passed)
        self.assertTrue(bool(res_syntax.syntax_error))

    def test_06_bounded_three_strike_ci_repair_and_token_breaker(self) -> None:
        ctrl = eng.CIRepairController(task_id="worker-fix", max_attempts=3, token_budget=50_000)
        for expected_attempt in (1, 2, 3):
            dec = ctrl.record_failure_and_decide([f"AssertionError on run {expected_attempt}"], tokens_delta=10_000)
            self.assertEqual(dec.action, "DISPATCH_REPAIR")
            self.assertEqual(dec.attempt, expected_attempt)
            self.assertFalse(dec.halted_for_human)

        # 4th failure (after 3 repair commits) halts and labels state:blocked
        dec_halt = ctrl.record_failure_and_decide(["Still failing after 3 repairs"], tokens_delta=5_000)
        self.assertEqual(dec_halt.action, "HALT_AND_ESCALATE")
        self.assertTrue(dec_halt.halted_for_human)
        self.assertEqual(dec_halt.escalation_label, "state:blocked")

        # Token circuit breaker trips immediately when budget exceeded
        breaker = eng.CIRepairController(task_id="runaway-worker", max_attempts=3, token_budget=10_000)
        dec_tok = breaker.record_failure_and_decide(["Timeout"], tokens_delta=15_000)
        self.assertTrue(dec_tok.halted_for_human)
        self.assertEqual(dec_tok.escalation_label, "state:blocked")

    def test_07_controlled_merge_targets_and_orphan_reaping(self) -> None:
        self.assertTrue(eng.validate_merge_target("agent-work/issue-101"))
        self.assertTrue(eng.validate_merge_target("refs/heads/agent-work/feature-wave"))
        self.assertFalse(eng.validate_merge_target("main"))
        self.assertFalse(eng.validate_merge_target("master"))
        self.assertFalse(eng.validate_merge_target("release/v1.0"))
        self.assertFalse(eng.validate_merge_target("feat/direct-to-main"))

        ref_now = dt.datetime(2026, 11, 17, 4, 0, 0, tzinfo=dt.timezone.utc)
        stalled = eng.reap_stalled_workers(
            {
                "healthy-worker": "2026-11-17T03:55:00+00:00",
                "orphaned-worker": "2026-11-17T03:10:00+00:00",
            },
            timeout_sec=900,
            now_utc=ref_now,
        )
        self.assertEqual(stalled, ["orphaned-worker"])

    def test_08_declarative_aw_compiler_parity(self) -> None:
        aw_md = REPO_ROOT / ".github" / "workflows" / "issue-supervisor.md"
        compiled_yml = REPO_ROOT / ".github" / "workflows" / "orchestrator-supervisor.yml"
        self.assertTrue(aw_md.is_file(), "Missing declarative .github/workflows/issue-supervisor.md")
        self.assertTrue(compiled_yml.is_file(), "Missing compiled .github/workflows/orchestrator-supervisor.yml")

        expected_yaml = aw_compiler.compile_actions_yaml(
            ".github/workflows/issue-supervisor.md",
            aw_md.read_text(encoding="utf-8"),
        )
        self.assertEqual(compiled_yml.read_text(encoding="utf-8"), expected_yaml)

        # Compiler must reject agent frontmatter requesting contents: write
        unsafe_md = aw_md.read_text(encoding="utf-8").replace("contents: read", "contents: write")
        with self.assertRaises(ValueError):
            aw_compiler.parse_aw_markdown(unsafe_md)

    def test_09_e2e_async_git_worktree_multi_wave_orchestration(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            repo = root / "demo-repo"
            repo.mkdir()
            subprocess.run(["git", "-C", str(repo), "init", "-b", "main"], check=True, capture_output=True)
            (repo / "mod_alpha").mkdir()
            (repo / "mod_beta").mkdir()
            (repo / "integration").mkdir()
            (repo / "mod_alpha" / "alpha.py").write_text(
                "def alpha_base() -> int:\n    return 10\n",
                encoding="utf-8",
            )
            (repo / "mod_beta" / "beta.py").write_text(
                "def beta_base() -> int:\n    return 20\n",
                encoding="utf-8",
            )
            subprocess.run(["git", "-C", str(repo), "add", "."], check=True, capture_output=True)
            subprocess.run(
                [
                    "git", "-C", str(repo),
                    "-c", "user.name=test-init",
                    "-c", "user.email=test-init@localhost",
                    "commit", "-m", "initial main commit",
                ],
                check=True,
                capture_output=True,
            )
            initial_main_sha = subprocess.check_output(
                ["git", "-C", str(repo), "rev-parse", "main"], text=True
            ).strip()

            plan = eng.OrchestrationPlan(
                tracker_id="trk-e2e-worktree-42",
                umbrella_branch="agent-work/issue-42",
                source_issue=42,
                tasks=[
                    eng.SubTask(
                        task_id="alpha-worker",
                        issue_number=42,
                        owned_paths=["mod_alpha/**"],
                        depends_on=[],
                        acceptance_criteria=["Extend alpha module without dropping alpha_base"],
                    ),
                    eng.SubTask(
                        task_id="beta-worker",
                        issue_number=42,
                        owned_paths=["mod_beta/**"],
                        depends_on=[],
                        acceptance_criteria=["Extend beta module with 1 simulated CI repair"],
                    ),
                    eng.SubTask(
                        task_id="integration-worker",
                        issue_number=42,
                        owned_paths=["integration/**"],
                        depends_on=["alpha-worker", "beta-worker"],
                        acceptance_criteria=["Combine alpha and beta outputs after Wave 0 merges"],
                    ),
                ],
            )

            def _worker_fn(task: eng.SubTask, wt_dir: Path, attempt: int) -> None:
                # Confirm locked plan inside sandbox is 0444 read-only
                locked = wt_dir / ".orchestrator" / "plans" / f"{plan.tracker_id}.plan.json"
                self.assertEqual(stat.S_IMODE(locked.stat().st_mode), 0o444)

                if task.task_id == "alpha-worker":
                    (wt_dir / "mod_alpha" / "alpha.py").write_text(
                        "def alpha_base() -> int:\n    return 10\n\ndef alpha_extra() -> int:\n    return 5\n",
                        encoding="utf-8",
                    )
                elif task.task_id == "beta-worker":
                    if attempt == 0:
                        # First attempt intentionally drops beta_base (>20% AST drop -> triggers CI repair #1!)
                        (wt_dir / "mod_beta" / "beta.py").write_text(
                            "def beta_replacement_only() -> int:\n    return 99\n",
                            encoding="utf-8",
                        )
                    else:
                        # Repair attempt #1 restores beta_base and adds beta_extra cleanly
                        (wt_dir / "mod_beta" / "beta.py").write_text(
                            "def beta_base() -> int:\n    return 20\n\ndef beta_extra() -> int:\n    return 7\n",
                            encoding="utf-8",
                        )
                elif task.task_id == "integration-worker":
                    # Wave 1 sees both Wave 0 merges already integrated on agent-work/issue-42!
                    self.assertIn("alpha_extra", (wt_dir / "mod_alpha" / "alpha.py").read_text(encoding="utf-8"))
                    self.assertIn("beta_extra", (wt_dir / "mod_beta" / "beta.py").read_text(encoding="utf-8"))
                    (wt_dir / "integration").mkdir(parents=True, exist_ok=True)
                    (wt_dir / "integration" / "summary.json").write_text(
                        json.dumps({"total": 42}) + "\n",
                        encoding="utf-8",
                    )

            store = gw.FileCheckpointStore(root / "checkpoints")
            ledger = root / "telemetry" / "spans.jsonl"
            graph = gw.OrchestrationStateGraph(repo, store, telemetry_ledger=ledger)

            ckpt = asyncio.run(graph.execute_plan(plan, root / "worktrees", _worker_fn))
            self.assertEqual(ckpt.blocked_tasks, [])
            self.assertEqual(
                ckpt.completed_tasks,
                ["alpha-worker", "beta-worker", "integration-worker"],
            )
            self.assertEqual(ckpt.repair_attempts["alpha-worker"], 0)
            self.assertEqual(ckpt.repair_attempts["beta-worker"], 1)
            self.assertTrue(ckpt.ready_for_main_pr)

            # Verify `main` was NEVER mutated directly while `agent-work/issue-42` has all 3 tasks!
            after_main_sha = subprocess.check_output(
                ["git", "-C", str(repo), "rev-parse", "main"], text=True
            ).strip()
            self.assertEqual(initial_main_sha, after_main_sha)

            umb_summary = subprocess.check_output(
                ["git", "-C", str(repo), "show", "agent-work/issue-42:integration/summary.json"],
                text=True,
            )
            self.assertEqual(json.loads(umb_summary)["total"], 42)
            spans = [json.loads(line) for line in ledger.read_text(encoding="utf-8").splitlines() if line.strip()]
            self.assertEqual(len(spans), 3)


if __name__ == "__main__":
    unittest.main(verbosity=2)
