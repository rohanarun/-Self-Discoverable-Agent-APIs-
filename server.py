#!/usr/bin/env python3
"""
Tiny example app for the Agent Port / GET /agents discovery pattern.

This server:
- binds only to 127.0.0.1
- prefers port 4242 and falls forward to the next free port
- exposes GET /agents as the canonical discovery endpoint
- provides a couple of example JSON actions for local agents
"""

from __future__ import annotations

import argparse
import json
import socket
from dataclasses import dataclass
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any
from urllib.parse import parse_qs, urlparse


DEFAULT_PORT_START = 4242
DEFAULT_PORT_END = 4269


@dataclass
class AppState:
    service_name: str
    port: int
    port_start: int
    port_end: int
    started_at: str
    notes: str
    tasks: list[dict[str, Any]]
    next_task_id: int = 1

    @property
    def base_url(self) -> str:
        return f"http://127.0.0.1:{self.port}"


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def find_available_port(preferred: int, start: int, end: int) -> int:
    candidates = [preferred] + [port for port in range(start, end + 1) if port != preferred]
    for port in candidates:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            try:
                sock.bind(("127.0.0.1", port))
            except OSError:
                continue
            return port
    raise RuntimeError(f"No free agent ports found in range {start}-{end}.")


class AgentPortExampleHandler(BaseHTTPRequestHandler):
    server_version = "AgentPortExample/1.0"

    @property
    def state(self) -> AppState:
        return self.server.app_state  # type: ignore[attr-defined]

    def log_message(self, format: str, *args: Any) -> None:
        # Keep console noise minimal for the example repo.
        return

    def do_OPTIONS(self) -> None:
        self.send_response(204)
        self._send_common_headers("application/json; charset=utf-8")
        self.end_headers()

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        path = parsed.path.rstrip("/") or "/"
        query = parse_qs(parsed.query)

        if path in ("/",):
            self._send_json(
                200,
                {
                    "success": True,
                    "message": "Agent Port Example is running.",
                    "discovery_url": f"{self.state.base_url}/agents",
                },
            )
            return

        if path in ("/agents", "/.well-known/agents.json", "/.well-known/agent.json"):
            self._send_json(200, self._agent_document())
            return

        if path == "/health":
            self._send_json(
                200,
                {
                    "success": True,
                    "service": self.state.service_name,
                    "status": "ok",
                    "started_at": self.state.started_at,
                    "task_count": len(self.state.tasks),
                    "base_url": self.state.base_url,
                },
            )
            return

        if path == "/notes":
            self._send_json(
                200,
                {
                    "success": True,
                    "service": self.state.service_name,
                    "notes": self.state.notes,
                    "usage_tip": "Agents should read GET /agents first, then call the capability endpoints they need.",
                },
            )
            return

        if path == "/tasks":
            include_completed = query.get("include_completed", ["true"])[0].lower() in ("1", "true", "yes")
            tasks = self.state.tasks
            if not include_completed:
                tasks = [task for task in tasks if not task["completed"]]
            self._send_json(
                200,
                {
                    "success": True,
                    "tasks": tasks,
                    "count": len(tasks),
                },
            )
            return

        self._send_json(404, {"success": False, "error": f"Unknown route: {path}"})

    def do_POST(self) -> None:
        parsed = urlparse(self.path)
        path = parsed.path.rstrip("/") or "/"
        body = self._read_json_body()
        if body is None:
            return

        if path == "/tools/echo":
            text = str(body.get("text", "")).strip()
            self._send_json(
                200,
                {
                    "success": True,
                    "echo": text,
                    "received_at": utc_now_iso(),
                },
            )
            return

        if path == "/tools/add_task":
            title = str(body.get("title", "")).strip()
            if not title:
                self._send_json(400, {"success": False, "error": "Missing required field: title"})
                return
            task = {
                "id": self.state.next_task_id,
                "title": title,
                "completed": False,
                "created_at": utc_now_iso(),
            }
            self.state.next_task_id += 1
            self.state.tasks.append(task)
            self._send_json(
                200,
                {
                    "success": True,
                    "task": task,
                    "tasks": self.state.tasks,
                },
            )
            return

        if path == "/tools/complete_task":
            task_id = body.get("id")
            try:
                task_id = int(task_id)
            except (TypeError, ValueError):
                self._send_json(400, {"success": False, "error": "Missing or invalid task id."})
                return
            for task in self.state.tasks:
                if task["id"] == task_id:
                    task["completed"] = True
                    task["completed_at"] = utc_now_iso()
                    self._send_json(200, {"success": True, "task": task})
                    return
            self._send_json(404, {"success": False, "error": f"Task {task_id} was not found."})
            return

        self._send_json(404, {"success": False, "error": f"Unknown route: {path}"})

    def _read_json_body(self) -> dict[str, Any] | None:
        try:
            length = int(self.headers.get("Content-Length", "0"))
        except ValueError:
            self._send_json(400, {"success": False, "error": "Invalid Content-Length header."})
            return None

        raw = self.rfile.read(length) if length > 0 else b"{}"
        try:
            payload = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            self._send_json(400, {"success": False, "error": "Expected a UTF-8 JSON request body."})
            return None

        if not isinstance(payload, dict):
            self._send_json(400, {"success": False, "error": "Expected a JSON object."})
            return None
        return payload

    def _send_json(self, status_code: int, payload: dict[str, Any]) -> None:
        body = json.dumps(payload, indent=2, sort_keys=True).encode("utf-8")
        self.send_response(status_code)
        self._send_common_headers("application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _send_common_headers(self, content_type: str) -> None:
        self.send_header("Content-Type", content_type)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")

    def _agent_document(self) -> dict[str, Any]:
        return {
            "success": True,
            "protocol": "agent-port/v1",
            "service": self.state.service_name,
            "service_slug": "agent-port-example",
            "display_name": "Agent Port Example App",
            "description": (
                "A tiny localhost app that demonstrates the self-discoverable "
                "Agent Port pattern with GET /agents."
            ),
            "base_url": self.state.base_url,
            "discovery_url": f"{self.state.base_url}/agents",
            "health_url": f"{self.state.base_url}/health",
            "auth": {
                "type": "none",
                "scope": "loopback_only",
                "notes": "This example binds only to 127.0.0.1 for local agent use.",
            },
            "agent_port": {
                "preferred_port": self.state.port_start,
                "current_port": self.state.port,
                "scan_range_start": self.state.port_start,
                "scan_range_end": self.state.port_end,
                "scan_strategy": (
                    "Scan localhost ports in the reserved range and request GET /agents. "
                    "Use the first response whose protocol is agent-port/v1."
                ),
            },
            "capabilities": [
                {
                    "id": "agents_discovery",
                    "method": "GET",
                    "path": "/agents",
                    "summary": "Canonical machine-readable discovery document.",
                },
                {
                    "id": "health",
                    "method": "GET",
                    "path": "/health",
                    "summary": "Basic health and runtime state.",
                },
                {
                    "id": "notes",
                    "method": "GET",
                    "path": "/notes",
                    "summary": "Human-readable feature and usage notes for agents.",
                },
                {
                    "id": "tasks_list",
                    "method": "GET",
                    "path": "/tasks",
                    "summary": "Read the current task list.",
                    "query": {
                        "include_completed": "Optional boolean. Defaults to true.",
                    },
                },
                {
                    "id": "tools_echo",
                    "method": "POST",
                    "path": "/tools/echo",
                    "summary": "Echo text back to the caller.",
                    "request_json_schema": {
                        "text": "Required string to echo.",
                    },
                },
                {
                    "id": "tools_add_task",
                    "method": "POST",
                    "path": "/tools/add_task",
                    "summary": "Add a task to the local task list.",
                    "request_json_schema": {
                        "title": "Required task title string.",
                    },
                },
                {
                    "id": "tools_complete_task",
                    "method": "POST",
                    "path": "/tools/complete_task",
                    "summary": "Mark a task as complete.",
                    "request_json_schema": {
                        "id": "Required integer task id.",
                    },
                },
            ],
            "examples": {
                "discover": f"curl -s {self.state.base_url}/agents",
                "health": f"curl -s {self.state.base_url}/health",
                "add_task": (
                    f"curl -s {self.state.base_url}/tools/add_task "
                    "-H 'Content-Type: application/json' "
                    "-d '{\"title\":\"Ship the agent-port example\"}'"
                ),
            },
            "usage_notes": [
                "Agents should request GET /agents first before calling other endpoints.",
                "All non-file endpoints return JSON.",
                "POST bodies should be JSON objects.",
                "The API is intended for trusted local tools running on the same machine.",
            ],
        }


def build_argument_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run the Agent Port example app.")
    parser.add_argument(
        "--preferred-port",
        type=int,
        default=DEFAULT_PORT_START,
        help=f"Preferred starting port inside the agent range (default: {DEFAULT_PORT_START}).",
    )
    parser.add_argument(
        "--port-start",
        type=int,
        default=DEFAULT_PORT_START,
        help=f"Start of the agent port scan range (default: {DEFAULT_PORT_START}).",
    )
    parser.add_argument(
        "--port-end",
        type=int,
        default=DEFAULT_PORT_END,
        help=f"End of the agent port scan range (default: {DEFAULT_PORT_END}).",
    )
    return parser


def main() -> None:
    parser = build_argument_parser()
    args = parser.parse_args()

    if args.port_end < args.port_start:
        raise SystemExit("--port-end must be greater than or equal to --port-start")

    port = find_available_port(args.preferred_port, args.port_start, args.port_end)
    state = AppState(
        service_name="AgentPortExample",
        port=port,
        port_start=args.port_start,
        port_end=args.port_end,
        started_at=utc_now_iso(),
        notes=(
            "This repo exists to demonstrate the Agent Port pattern: reserve a local port range, "
            "bind to loopback, and expose GET /agents so local agents can discover and use the app."
        ),
        tasks=[],
    )

    server = ThreadingHTTPServer(("127.0.0.1", port), AgentPortExampleHandler)
    server.app_state = state  # type: ignore[attr-defined]

    print(f"Agent Port Example listening on {state.base_url}")
    print(f"Discovery document: {state.base_url}/agents")
    print(f"Reserved agent range: {state.port_start}-{state.port_end}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down.")
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
