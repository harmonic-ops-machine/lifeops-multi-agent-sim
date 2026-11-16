#!/usr/bin/env python3
"""Automated End-to-End Verification Suite for Trajectory Refinery (v8.3.0)."""
from __future__ import annotations

import json
from pathlib import Path
import sys
import tempfile
import unittest

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
            self.assertFalse(call_resp["result"]["isError"])
            receipt = json.loads(call_resp["result"]["content"][0]["text"])
            self.assertEqual(receipt["turns_archived"], 2)
            self.assertTrue((spool / "mcp-live-001.jsonl").exists())

    def test_session_and_products_bundler_tiered_scrub(self) -> None:
        template_path = ROOT.parents[1] / "templates" / "SESSION_CLOSEOUT_TEMPLATE.md"
        card_md = template_path.read_text(encoding="utf-8")
        fake_tok = "ya29." + "A0ARrdaM_example_token_1234567890"
        product_sql = f"-- Query in project demo-proj\n-- leaked={fake_tok}\nSELECT 1;\n".encode("utf-8")

        with tempfile.TemporaryDirectory() as tmp:
            res = bundler.build_session_upload_bundle(
                repo_root=Path(tmp),
                session_id="20261116-bundler-test",
                session_card_md=card_md,
                trajectory_bytes=b'{"turn_index":0,"content":"ok"}\n',
                products={"report_query.sql": product_sql, "large_dump.bin": b"x" * 2048},
                date_slug="2026-11-16",
                mode="private",
                large_blob_threshold_bytes=1024,
            )
            mf = res["manifest"]
            self.assertTrue(mf["tier_a_secrets_scrubbed"])
            self.assertTrue(mf["tier_b_entities_preserved"])
            self.assertIn("TIER_A:OAUTH_ACCESS_TOKEN", mf["redactions_applied"])
            self.assertEqual(len(mf["products"]), 2)

            bdir = Path(res["bundle_dir"])
            saved_sql = (bdir / "products" / "report_query.sql").read_text(encoding="utf-8")
            self.assertNotIn(fake_tok, saved_sql)
            self.assertIn("<SCRUBBED_OAUTH_ACCESS_TOKEN>", saved_sql)
            self.assertTrue((bdir / "products" / "large_dump.bin.gcs.json").exists())


if __name__ == "__main__":
    unittest.main(verbosity=2)
