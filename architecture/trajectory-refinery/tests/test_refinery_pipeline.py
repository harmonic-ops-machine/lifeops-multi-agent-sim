#!/usr/bin/env python3
"""Automated End-to-End Verification Suite for Trajectory Refinery (v8.4 / SESSION-BUNDLE-v3 + v8.3.1)."""
from __future__ import annotations

from http.server import HTTPServer
import json
import os
from pathlib import Path
import sys
import tempfile
import threading
import unittest
import urllib.error
import urllib.request

sys.dont_write_bytecode = True

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

import cloudrun_mcp_ingestor as mcp_srv  # noqa: E402
import refinery_engine as engine  # noqa: E402
import session_bundler as bundler  # noqa: E402


class TrajectoryRefineryTest(unittest.TestCase):
    def test_end_to_end_noise_pruning_and_rca_extraction(self) -> None:
        raw_turns = [
            {"role": "user", "modality": "voice_asr", "content": "Sprawdź integrację z GitHubem i przygotuj architekturę."},
            {"role": "assistant", "modality": "text", "content": "I'll update the-"},
            {"role": "assistant", "modality": "text", "content": "Nobody has spoken for a while. Are you still there?"},
            {
                "role": "assistant",
                "modality": "tool_result",
                "content": "fatal: Bad configuration option: \\357\\273\\277host (UTF-8 BOM in ssh config)",
            },
            {
                "role": "user",
                "modality": "voice_asr",
                "content": "Nagranie urwało się — chodzi o to, żeby osobny agent nie inżynier usuwał szum.",
            },
            {
                "role": "assistant",
                "modality": "text",
                "content": "Zapisano czystą konfigurację SSH bez BOM oraz architekturę dwuwarstwową GCS + GitHub.",
            },
        ]

        trace = engine.normalize_turns_to_trace(
            session_id="gem-20261116-demo",
            raw_turns=raw_turns,
            source_surface="gemini_app_docs_export",
            captured_at_hst="2026-11-16T13:05:00-10:00",
        )
        self.assertEqual(len(trace), 6)
        self.assertTrue(trace[1]["signals"]["is_noise_candidate"])
        self.assertTrue(trace[2]["signals"]["is_noise_candidate"])
        self.assertTrue(trace[3]["signals"]["is_error_or_correction"])
        self.assertTrue(trace[4]["signals"]["is_error_or_correction"])

        bundle = engine.run_refinery_audit(
            trace,
            gcs_raw_archive_uri="gs://enclave-session-refinery/raw/gem-20261116-demo.jsonl",
            analyzed_at_hst="2026-11-16T13:06:00-10:00",
        )
        rca = bundle["rca_json"]
        self.assertEqual(rca["schema"], "SESSION-RCA-v1")
        self.assertEqual(rca["compression_metrics"]["total_turns"], 6)
        self.assertEqual(rca["compression_metrics"]["pruned_noise_turns"], 3)
        self.assertEqual(rca["compression_metrics"]["kept_signal_turns"], 3)

        categories = {inc["root_cause_category"] for inc in rca["incidents"]}
        self.assertIn("ENVIRONMENT_CONFIG_MISMATCH", categories)
        self.assertIn("ASR_VOICE_MISRECOGNITION", categories)
        self.assertGreaterEqual(len(rca["proposed_patches"]), 2)

        # Ensure noise turns were stripped from L1 distilled Markdown
        self.assertNotIn("Nobody has spoken for a while", bundle["distilled_markdown"])
        self.assertIn("Zapisano czystą konfigurację SSH bez BOM", bundle["distilled_markdown"])

        with tempfile.TemporaryDirectory() as tmp:
            paths = engine.write_refinery_bundle(Path(tmp), "gem-20261116-demo", bundle)
            self.assertTrue(paths["distilled"].exists())
            self.assertTrue(paths["rca"].exists())
            self.assertTrue(paths["patch"].exists())

    def test_single_tool_cloudrun_mcp_contract(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            spool = Path(tmp)
            tools_resp = mcp_srv.handle_jsonrpc_payload({"jsonrpc": "2.0", "id": 1, "method": "tools/list"}, spool)
            self.assertIsNotNone(tools_resp)
            tools = tools_resp["result"]["tools"]
            # Must expose EXACTLY 1 tool to avoid Gemini Connectors batch RPC 13 bug
            self.assertEqual(len(tools), 1)
            self.assertEqual(tools[0]["name"], "archive_gemini_session")

            call_resp = mcp_srv.handle_jsonrpc_payload(
                {
                    "jsonrpc": "2.0",
                    "id": 2,
                    "method": "tools/call",
                    "params": {
                        "name": "archive_gemini_session",
                        "arguments": {
                            "session_id": "mcp-live-001",
                            "turns": [
                                {"role": "user", "content": "Zapisz wyniki analizy."},
                                {"role": "assistant", "content": "Gotowe — artefakt zweryfikowany."},
                            ],
                        },
                    },
                },
                spool,
            )
            self.assertIsNotNone(call_resp)
            self.assertFalse(call_resp["result"]["isError"])
            receipt = json.loads(call_resp["result"]["content"][0]["text"])
            self.assertEqual(receipt["turns_archived"], 2)
            self.assertTrue((spool / "mcp-live-001.jsonl").exists())

    def test_benign_assistant_prose_not_falsely_pruned(self) -> None:
        raw_turns = [
            {"role": "user", "modality": "text", "content": "Run full verification and summarize."},
            {
                "role": "assistant",
                "modality": "text",
                "content": "Completed verification with 0 errors and deterministic retry handling for failed requests.",
            },
        ]
        trace = engine.normalize_turns_to_trace("gem-benign-001", raw_turns)
        bundle = engine.run_refinery_audit(trace)
        rca = bundle["rca_json"]
        self.assertEqual(rca["incidents"], [])
        self.assertEqual(rca["compression_metrics"]["kept_signal_turns"], 2)
        self.assertEqual(rca["compression_metrics"]["pruned_noise_turns"], 0)
        self.assertIn("0 errors and deterministic retry handling", bundle["distilled_markdown"])

    def test_missing_context_and_permission_failure_categories(self) -> None:
        raw_turns = [
            {
                "role": "user",
                "modality": "text",
                "content": "You lost context from the prior checkpoint; reload bootstrap first.",
            },
            {
                "role": "tool",
                "modality": "tool_result",
                "content": "HTTP 403 Forbidden: PERMISSION_DENIED on target bucket.",
            },
            {
                "role": "assistant",
                "modality": "text",
                "content": "Loaded bootstrap context and documented IAM remediation steps.",
            },
        ]
        trace = engine.normalize_turns_to_trace("gem-cats-002", raw_turns)
        bundle = engine.run_refinery_audit(trace)
        rca = bundle["rca_json"]
        engine.validate_rca_payload(rca)
        categories = {inc["root_cause_category"] for inc in rca["incidents"]}
        self.assertEqual(categories, {"MISSING_CONTEXT_OR_MEMORY", "API_OR_PERMISSION_FAILURE"})
        self.assertEqual(rca["compression_metrics"]["kept_signal_turns"], 2)
        self.assertEqual(rca["compression_metrics"]["pruned_noise_turns"], 1)

    def test_schema_validators_reject_invalid_records(self) -> None:
        with self.assertRaises(ValueError):
            engine.normalize_turns_to_trace("abc", [{"role": "user", "content": "short id"}])

        with self.assertRaises(ValueError):
            engine.normalize_turns_to_trace(
                "valid-id-01",
                [{"role": "user", "content": "bad uri", "gcs_attachment_uris": ["https://example.com/nope"]}],
            )

        valid_trace = engine.normalize_turns_to_trace("valid-id-02", [{"role": "user", "content": "ok work"}])
        bad_trace = [dict(valid_trace[0], unexpected_extra="invalid")]
        with self.assertRaises(ValueError):
            engine.validate_trace_records(bad_trace)

        valid_rca = engine.run_refinery_audit(valid_trace)["rca_json"]
        bad_sha_rca = dict(valid_rca, raw_trace_sha256="not-a-sha256")
        with self.assertRaises(ValueError):
            engine.validate_rca_payload(bad_sha_rca)

        extra_key_rca = dict(valid_rca, extra_field=True)
        with self.assertRaises(ValueError):
            engine.validate_rca_payload(extra_key_rca)

    def test_docs_markdown_and_takeout_json_parsers(self) -> None:
        md = (
            "### You\n"
            "Verify repository integrity.\n\n"
            "### Gemini\n"
            "Verified 34 DAG nodes and 0 PII.\n"
        )
        md_turns = engine.parse_docs_export_markdown(md)
        self.assertEqual([t["role"] for t in md_turns], ["user", "assistant"])
        self.assertIn("Verify repository integrity.", md_turns[0]["content"])
        md_trace = engine.normalize_turns_to_trace("docs-export-001", md_turns, source_surface="gemini_app_docs_export")
        engine.validate_trace_records(md_trace)

        takeout_raw = json.dumps(
            [
                {
                    "title": "Prompted Build Zero-PII verifier",
                    "time": "2026-11-16T12:00:00-10:00",
                    "safeHtmlItem": [{"html": "<p>Implemented &amp; tested verifier.</p>"}],
                }
            ]
        )
        takeout_turns = engine.parse_takeout_activity_json(takeout_raw)
        self.assertEqual([t["role"] for t in takeout_turns], ["user", "assistant"])
        self.assertEqual(takeout_turns[0]["content"], "Build Zero-PII verifier")
        self.assertEqual(takeout_turns[1]["content"], "Implemented & tested verifier.")
        takeout_trace = engine.normalize_turns_to_trace(
            "takeout-export-001",
            takeout_turns,
            source_surface="gemini_takeout_json",
        )
        engine.validate_trace_records(takeout_trace)

    def test_mcp_notifications_ping_and_path_traversal_guard(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            spool = Path(tmp).resolve()
            notif_resp = mcp_srv.handle_jsonrpc_payload(
                {"jsonrpc": "2.0", "method": "notifications/initialized"},
                spool,
            )
            self.assertIsNone(notif_resp)

            ping_resp = mcp_srv.handle_jsonrpc_payload({"jsonrpc": "2.0", "id": 7, "method": "ping"}, spool)
            self.assertEqual(ping_resp, {"jsonrpc": "2.0", "id": 7, "result": {}})

            bad_turns_resp = mcp_srv.handle_jsonrpc_payload(
                {
                    "jsonrpc": "2.0",
                    "id": 8,
                    "method": "tools/call",
                    "params": {"name": "archive_gemini_session", "arguments": {"session_id": "ok-id", "turns": []}},
                },
                spool,
            )
            self.assertEqual(bad_turns_resp["error"]["code"], -32602)

            for unsafe_id in ("../../etc/passwd", "..", "x"):
                resp = mcp_srv.handle_jsonrpc_payload(
                    {
                        "jsonrpc": "2.0",
                        "id": 9,
                        "method": "tools/call",
                        "params": {
                            "name": "archive_gemini_session",
                            "arguments": {
                                "session_id": unsafe_id,
                                "turns": [{"role": "user", "content": "Safe write test."}],
                            },
                        },
                    },
                    spool,
                )
                receipt = json.loads(resp["result"]["content"][0]["text"])
                sid = receipt["session_id"]
                self.assertGreaterEqual(len(sid), 4)
                saved = (spool / f"{sid}.jsonl").resolve()
                self.assertEqual(saved.parent, spool)
                self.assertTrue(saved.exists())

    def test_http_handler_limits_auth_and_healthz(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            spool = Path(tmp)

            class TestHandler(mcp_srv.RefineryMCPHandler):
                spool_dir = spool

            server = HTTPServer(("127.0.0.1", 0), TestHandler)
            port = server.server_address[1]
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            prev_key = os.environ.get("REFINERY_MCP_BEARER_KEY")

            try:
                base = f"http://127.0.0.1:{port}"
                with urllib.request.urlopen(f"{base}/healthz", timeout=5) as r:
                    self.assertEqual(r.status, 200)
                    health = json.loads(r.read().decode("utf-8"))
                    self.assertTrue(health["ok"])
                    self.assertEqual(health["tools_count"], 1)

                # Malformed JSON returns 400 with JSON-RPC -32700
                req_bad = urllib.request.Request(
                    base,
                    data=b"{not-json",
                    headers={"Content-Type": "application/json"},
                    method="POST",
                )
                with self.assertRaises(urllib.error.HTTPError) as ctx:
                    urllib.request.urlopen(req_bad, timeout=5)
                self.assertEqual(ctx.exception.code, 400)
                err_body = json.loads(ctx.exception.read().decode("utf-8"))
                self.assertEqual(err_body["error"]["code"], -32700)

                # Notification returns 202 Accepted
                req_notif = urllib.request.Request(
                    base,
                    data=json.dumps({"jsonrpc": "2.0", "method": "notifications/initialized"}).encode("utf-8"),
                    headers={"Content-Type": "application/json"},
                    method="POST",
                )
                with urllib.request.urlopen(req_notif, timeout=5) as r:
                    self.assertEqual(r.status, 202)

                # Optional Bearer Auth gate
                os.environ["REFINERY_MCP_BEARER_KEY"] = "unit-test-key-value"
                req_unauth = urllib.request.Request(
                    base,
                    data=json.dumps({"jsonrpc": "2.0", "id": 1, "method": "ping"}).encode("utf-8"),
                    headers={"Content-Type": "application/json"},
                    method="POST",
                )
                with self.assertRaises(urllib.error.HTTPError) as ctx_unauth:
                    urllib.request.urlopen(req_unauth, timeout=5)
                self.assertEqual(ctx_unauth.exception.code, 401)

                req_auth = urllib.request.Request(
                    base,
                    data=json.dumps({"jsonrpc": "2.0", "id": 1, "method": "ping"}).encode("utf-8"),
                    headers={
                        "Content-Type": "application/json",
                        "Authorization": "Bearer unit-test-key-value",
                    },
                    method="POST",
                )
                with urllib.request.urlopen(req_auth, timeout=5) as r:
                    self.assertEqual(r.status, 200)
                    self.assertEqual(json.loads(r.read().decode("utf-8"))["result"], {})
            finally:
                if prev_key is None:
                    os.environ.pop("REFINERY_MCP_BEARER_KEY", None)
                else:
                    os.environ["REFINERY_MCP_BEARER_KEY"] = prev_key
                server.shutdown()
                server.server_close()
                thread.join(timeout=2)

    def test_session_and_products_bundler_tiered_scrub(self) -> None:
        template_path = ROOT.parents[1] / "templates" / "SESSION_CLOSEOUT_TEMPLATE.md"
        card_md = template_path.read_text(encoding="utf-8")
        fake_tok = "ya29." + "A0ARrdaM_example_token_1234567890"
        product_sql = f"-- Query in project demo-proj\n-- leaked={fake_tok}\nSELECT 1;\n".encode("utf-8")

        with tempfile.TemporaryDirectory() as tmp:
            existing_file = Path(tmp) / "live_output.md"
            existing_file.write_text("# Live Result\n", encoding="utf-8")
            missing_file = Path(tmp) / "deleted_draft.md"

            res = bundler.build_session_upload_bundle(
                repo_root=Path(tmp),
                session_id="20261116-bundler-test",
                session_card_md=card_md,
                trajectory_bytes=b'{"turn_index":0,"content":"ok"}\n',
                products={"report_query.sql": product_sql, "large_dump.bin": b"x" * 2048},
                generated_file_refs=[
                    existing_file,
                    missing_file,
                    "https://github.com/harmonic-ops-machine/lifeops-multi-agent-sim",
                ],
                date_slug="2026-11-16",
                mode="private",
                large_blob_threshold_bytes=1024,
            )
            mf = res["manifest"]
            self.assertEqual(mf["schema"], "SESSION-BUNDLE-MANIFEST-v3")
            self.assertTrue(mf["tier_a_secrets_scrubbed"])
            self.assertTrue(mf["tier_b_entities_preserved"])
            self.assertIn("TIER_A:OAUTH_ACCESS_TOKEN", mf["redactions_applied"])
            self.assertEqual(len(mf["products"]), 2)
            self.assertEqual(len(mf["generated_file_links"]), 3)
            self.assertEqual(mf["generated_file_links"][0]["availability"], "AVAILABLE_VERIFIED")
            self.assertIsNotNone(mf["generated_file_links"][0]["sha256"])
            self.assertEqual(mf["generated_file_links"][1]["availability"], "SUPERSEDED_OR_REMOVED")
            self.assertEqual(mf["generated_file_links"][2]["availability"], "REMOTE_URI_RECORDED")

            bdir = Path(res["bundle_dir"])
            saved_sql = (bdir / "products" / "report_query.sql").read_text(encoding="utf-8")
            self.assertNotIn(fake_tok, saved_sql)
            self.assertIn("<SCRUBBED_OAUTH_ACCESS_TOKEN>", saved_sql)
            self.assertTrue((bdir / "products" / "large_dump.bin.gcs.json").exists())

    def test_session_bundler_refresh_secret_and_collision_safety(self) -> None:
        template_path = ROOT.parents[1] / "templates" / "SESSION_CLOSEOUT_TEMPLATE.md"
        card_md = template_path.read_text(encoding="utf-8")
        fake_refresh = "1//" + "0gExampleRefreshSecretValue123456"

        with tempfile.TemporaryDirectory() as tmp:
            root_tmp = Path(tmp).resolve()
            res = bundler.build_session_upload_bundle(
                repo_root=root_tmp,
                session_id="../../escape",
                session_card_md=card_md,
                trajectory_bytes=f"refresh={fake_refresh}\n".encode("utf-8"),
                products={"a/report.md": b"one", "b/report.md": b"two"},
                date_slug="2026-11-16",
                mode="private",
            )
            mf = res["manifest"]
            self.assertEqual(mf["schema"], "SESSION-BUNDLE-MANIFEST-v3")
            self.assertIn("TIER_A:OAUTH_REFRESH_TOKEN", mf["redactions_applied"])
            bdir = Path(res["bundle_dir"]).resolve()
            self.assertTrue(bdir.is_relative_to((root_tmp / "sessions").resolve()))
            traj_txt = (bdir / "trajectory.jsonl").read_text(encoding="utf-8")
            self.assertNotIn(fake_refresh, traj_txt)
            self.assertIn("<SCRUBBED_OAUTH_REFRESH_TOKEN>", traj_txt)

            self.assertEqual(len(mf["products"]), 2)
            stored_paths = {p["stored_as"] for p in mf["products"]}
            self.assertEqual(len(stored_paths), 2)
            for rel_stored in stored_paths:
                self.assertTrue((bdir / rel_stored).exists())
            contents = {(bdir / rel_stored).read_bytes() for rel_stored in stored_paths}
            self.assertEqual(contents, {b"one", b"two"})

    def test_v3_rejects_missing_provenance_sections(self) -> None:
        incomplete_card = "---\nschema: SESSION-BUNDLE-v3\n---\n# Incomplete\n## 1. Runtime Environment & Subagent Provenance\n"
        errs = bundler.validate_session_card_markdown(incomplete_card)
        self.assertGreaterEqual(len(errs), 8)


if __name__ == "__main__":
    unittest.main(verbosity=2)
