#!/usr/bin/env python3
"""
Small discovery client for the Agent Port example pattern.

It scans a local port range, requests GET /agents on each responsive port,
and prints any services that match the agent-port/v1 protocol.
"""

from __future__ import annotations

import argparse
import json
from urllib.error import URLError, HTTPError
from urllib.request import urlopen


DEFAULT_PORT_START = 4242
DEFAULT_PORT_END = 4269


def fetch_json(url: str, timeout: float = 0.35):
    try:
        with urlopen(url, timeout=timeout) as response:
            if response.status != 200:
                return None
            return json.loads(response.read().decode("utf-8"))
    except (URLError, HTTPError, TimeoutError, json.JSONDecodeError, UnicodeDecodeError):
        return None


def main() -> None:
    parser = argparse.ArgumentParser(description="Discover local Agent Port services.")
    parser.add_argument("--port-start", type=int, default=DEFAULT_PORT_START)
    parser.add_argument("--port-end", type=int, default=DEFAULT_PORT_END)
    args = parser.parse_args()

    matches = []
    for port in range(args.port_start, args.port_end + 1):
        url = f"http://127.0.0.1:{port}/agents"
        payload = fetch_json(url)
        if not isinstance(payload, dict):
            continue
        if payload.get("protocol") != "agent-port/v1":
            continue
        matches.append(
            {
                "port": port,
                "service": payload.get("service"),
                "display_name": payload.get("display_name"),
                "base_url": payload.get("base_url"),
                "health_url": payload.get("health_url"),
            }
        )

    if not matches:
        print(f"No agent-port/v1 services found on localhost:{args.port_start}-{args.port_end}.")
        return

    print(json.dumps({"services": matches}, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
