#!/usr/bin/env python3
"""Minimal Single-Tool Cloud Run MCP Ingestor (`archive_gemini_session`).

Replaces sprawling 485-action third-party connectors with a deterministic,
1-tool JSON-RPC 2.0 MCP endpoint designed for Google Cloud Run:
  - Avoids Gemini Connectors batch-toggle RPC 13 failures (only 1 tool!).
  - Writes raw SESSION-TRACE-v1 JSONL payloads to a versioned GCS bucket (L0)
    and stages a commit on `inbox/raw-sessions` in the private GitHub vault repo.
"""
from __future__ import annotations

from http.server import BaseHTTPRequestHandler, HTTPServer
import json
import os
from pathlib import Path
import sys
from typing import Any

SRC_DIR = Path(__file__).resolve().parent
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

import refinery_engine as engine  # noqa: E402

MCP_TOOL_SPEC = {
    "name": "archive_gemini_session",
    "description": (
        "Archive a completed or active Gemini App work session (including raw turns, "
        "errors, and operator corrections) into the private GCS Bronze vault and "
        "GitHub inbox/raw-sessions branch for downstream Auditor distillation."
    ),
    "inputSchema": {
        "type": "object",
        "required": ["session_id", "turns"],
        "properties": {
            "session_id": {
                "type": "string",
                "description": "Unique slug or timestamped identifier for the Gemini session.",
            },
            "turns": {
                "type": "array",
                "description": "Ordered turn-by-turn records including mistakes and user corrections.",
                "items": {
                    "type": "object",
                    "required": ["role", "content"],
                    "properties": {
                        "role": {"type": "string", "enum": ["user", "assistant", "tool", "system"]},
                        "modality": {"type": "string", "enum": ["text", "voice_asr", "artifact", "tool_result"]},
                        "content": {"type": "string"},
                    },
                },
            },
        },
    },
}


def handle_jsonrpc_payload(payload: dict[str, Any], spool_dir: Path) -> dict[str, Any]:
    req_id = payload.get("id")
    method = payload.get("method", "")

    if method == "initialize":
        return {
            "jsonrpc": "2.0",
            "id": req_id,
            "result": {
                "protocolVersion": "2024-11-05",
                "serverInfo": {"name": "highres-trajectory-refinery-mcp", "version": "8.3.0"},
                "capabilities": {"tools": {}},
            },
        }

    if method == "tools/list":
        return {
            "jsonrpc": "2.0",
            "id": req_id,
            "result": {"tools": [MCP_TOOL_SPEC]},
        }

    if method == "tools/call":
        params = payload.get("params") or {}
        if params.get("name") != "archive_gemini_session":
            return {
                "jsonrpc": "2.0",
                "id": req_id,
                "error": {"code": -32601, "message": f"Unknown tool: {params.get('name')}"},
            }
        args = params.get("arguments") or {}
        session_id = re.sub(r"[^A-Za-z0-9._-]+", "-", str(args.get("session_id") or "session")).strip("-")
        turns = list(args.get("turns") or [])
        trace = engine.normalize_turns_to_trace(
            session_id=session_id,
            raw_turns=turns,
            source_surface="gemini_app_mcp",
        )
        raw_bytes = engine.serialize_trace_jsonl(trace)
        digest = engine.sha256_hex(raw_bytes)

        spool_dir.mkdir(parents=True, exist_ok=True)
        out_file = spool_dir / f"{session_id}.jsonl"
        out_file.write_bytes(raw_bytes)

        receipt = {
            "ok": True,
            "session_id": session_id,
            "turns_archived": len(trace),
            "sha256": digest,
            "target_branch": "inbox/raw-sessions",
        }
        return {
            "jsonrpc": "2.0",
            "id": req_id,
            "result": {
                "content": [{"type": "text", "text": json.dumps(receipt)}],
                "isError": False,
            },
        }

    return {
        "jsonrpc": "2.0",
        "id": req_id,
        "error": {"code": -32601, "message": f"Unsupported JSON-RPC method: {method}"},
    }


import re  # noqa: E402


class RefineryMCPHandler(BaseHTTPRequestHandler):
    spool_dir = Path(os.environ.get("REFINERY_SPOOL_DIR", "/tmp/refinery_spool"))

    def do_POST(self) -> None:  # noqa: N802
        length = int(self.headers.get("Content-Length", "0"))
        raw = self.rfile.read(length)
        resp = handle_jsonrpc_payload(json.loads(raw.decode("utf-8")), self.spool_dir)
        body = json.dumps(resp).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, fmt: str, *args: Any) -> None:
        return


def main() -> None:
    port = int(os.environ.get("PORT", "8080"))
    srv = HTTPServer(("0.0.0.0", port), RefineryMCPHandler)
    srv.serve_forever()


if __name__ == "__main__":
    main()
