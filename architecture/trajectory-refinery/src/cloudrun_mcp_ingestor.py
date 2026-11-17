#!/usr/bin/env python3
"""Minimal Single-Tool Cloud Run MCP Ingestor (`archive_gemini_session`).

Replaces sprawling 485-action third-party connectors with a deterministic,
1-tool JSON-RPC 2.0 MCP endpoint designed for Google Cloud Run:
  - Avoids Gemini Connectors batch-toggle RPC 13 failures (only 1 tool!).
  - Writes raw SESSION-TRACE-v1 JSONL payloads to a versioned GCS bucket (L0)
    and stages a commit on `inbox/raw-sessions` in the private GitHub vault repo.
"""
from __future__ import annotations

import hmac
from http.server import BaseHTTPRequestHandler, HTTPServer
import json
import os
from pathlib import Path
import re
import sys
from typing import Any

SRC_DIR = Path(__file__).resolve().parent
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

import refinery_engine as engine  # noqa: E402

MAX_REQUEST_BYTES = 2 * 1024 * 1024
SAFE_SESSION_ID_RE = re.compile(r"[^A-Za-z0-9._-]+")

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
                "minLength": 4,
                "maxLength": 128,
                "description": "Unique slug or timestamped identifier for the Gemini session.",
            },
            "turns": {
                "type": "array",
                "minItems": 1,
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


def sanitize_session_id(raw_value: Any) -> str:
    """Sanitize session_id into a path-safe identifier satisfying schema minLength >= 4."""
    text = SAFE_SESSION_ID_RE.sub("-", str(raw_value or ""))
    text = re.sub(r"\.{2,}", "-", text).strip(".-_")
    text = text[:128].strip(".-_")
    if not text:
        return "session-default"
    if len(text) < 4:
        return f"sess-{text}"
    return text


def _jsonrpc_error(req_id: Any, code: int, message: str) -> dict[str, Any]:
    return {"jsonrpc": "2.0", "id": req_id, "error": {"code": code, "message": message}}


def handle_jsonrpc_payload(payload: Any, spool_dir: Path) -> dict[str, Any] | None:
    if not isinstance(payload, dict) or payload.get("jsonrpc") != "2.0":
        req_id = payload.get("id") if isinstance(payload, dict) else None
        return _jsonrpc_error(req_id, -32600, "Invalid JSON-RPC 2.0 request")

    req_id = payload.get("id")
    method = payload.get("method", "")

    if "id" not in payload and isinstance(method, str) and method.startswith("notifications/"):
        return None

    if method == "ping":
        return {"jsonrpc": "2.0", "id": req_id, "result": {}}

    if method == "initialize":
        return {
            "jsonrpc": "2.0",
            "id": req_id,
            "result": {
                "protocolVersion": "2024-11-05",
                "serverInfo": {"name": "highres-trajectory-refinery-mcp", "version": "8.3.1"},
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
        params = payload.get("params")
        if not isinstance(params, dict):
            return _jsonrpc_error(req_id, -32602, "Invalid params: expected object")
        if params.get("name") != "archive_gemini_session":
            return _jsonrpc_error(req_id, -32601, f"Unknown tool: {params.get('name')}")

        args = params.get("arguments")
        if not isinstance(args, dict):
            return _jsonrpc_error(req_id, -32602, "Invalid params: 'arguments' must be an object")

        turns = args.get("turns")
        if (
            not isinstance(turns, list)
            or not turns
            or not all(
                isinstance(t, dict) and isinstance(t.get("role"), str) and isinstance(t.get("content"), str)
                for t in turns
            )
        ):
            return _jsonrpc_error(req_id, -32602, "Invalid params: 'turns' must be a non-empty array of turn objects")

        session_id = sanitize_session_id(args.get("session_id"))
        try:
            trace = engine.normalize_turns_to_trace(
                session_id=session_id,
                raw_turns=turns,
                source_surface="gemini_app_mcp",
            )
            engine.validate_trace_records(trace)
        except ValueError as exc:
            return _jsonrpc_error(req_id, -32602, f"Invalid trace payload: {exc}")

        raw_bytes = engine.serialize_trace_jsonl(trace)
        digest = engine.sha256_hex(raw_bytes)

        spool_resolved = spool_dir.resolve()
        spool_resolved.mkdir(parents=True, exist_ok=True)
        out_file = (spool_resolved / f"{session_id}.jsonl").resolve()
        if out_file.parent != spool_resolved:
            return _jsonrpc_error(req_id, -32602, "Invalid session_id path")
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

    return _jsonrpc_error(req_id, -32601, f"Unsupported JSON-RPC method: {method}")


class RefineryMCPHandler(BaseHTTPRequestHandler):
    spool_dir = Path(os.environ.get("REFINERY_SPOOL_DIR", "/tmp/refinery_spool"))

    def _write_json(self, status: int, body_obj: dict[str, Any]) -> None:
        body = json.dumps(body_obj).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _check_auth(self) -> bool:
        expected = os.environ.get("REFINERY_MCP_BEARER_KEY", "")
        if not expected:
            return True
        auth_header = self.headers.get("Authorization", "")
        expected_header = f"Bearer {expected}"
        if not hmac.compare_digest(auth_header.encode("utf-8"), expected_header.encode("utf-8")):
            self._write_json(401, {"error": "Unauthorized"})
            return False
        return True

    def do_GET(self) -> None:  # noqa: N802
        if self.path.rstrip("/") in ("/healthz", "/health"):
            self._write_json(
                200,
                {
                    "ok": True,
                    "service": "highres-trajectory-refinery-mcp",
                    "version": "8.3.1",
                    "tools_count": 1,
                },
            )
            return
        self._write_json(404, {"error": "Not found"})

    def do_POST(self) -> None:  # noqa: N802
        if not self._check_auth():
            return

        try:
            length = int(self.headers.get("Content-Length", "0"))
        except ValueError:
            self._write_json(400, _jsonrpc_error(None, -32600, "Invalid Content-Length header"))
            return

        if length <= 0:
            self._write_json(400, _jsonrpc_error(None, -32600, "Empty or non-positive Content-Length"))
            return

        if length > MAX_REQUEST_BYTES:
            self._write_json(413, _jsonrpc_error(None, -32600, "Payload too large"))
            return

        raw = self.rfile.read(length)
        try:
            payload = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            self._write_json(400, _jsonrpc_error(None, -32700, f"Parse error: {exc}"))
            return

        resp = handle_jsonrpc_payload(payload, self.spool_dir)
        if resp is None:
            self.send_response(202)
            self.send_header("Content-Length", "0")
            self.end_headers()
            return
        self._write_json(200, resp)

    def log_message(self, fmt: str, *args: Any) -> None:
        return


def main() -> None:
    port = int(os.environ.get("PORT", "8080"))
    srv = HTTPServer(("0.0.0.0", port), RefineryMCPHandler)
    srv.serve_forever()


if __name__ == "__main__":
    main()
