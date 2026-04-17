# GET /agents

Agents were supposed to make life easier, rather than increase the burden on vendors and user to install and learn skills, MCP, etc.

Every integration ends up hardcoded. One app listens on a random localhost port. Another has custom docs. A third only works if the agent was explicitly taught about it in advance. Users have to learn what MCP and skills are. 
A better pattern is to make APIs self-discoverable.


# Agent Port Example

This is a small, publishable example repo for a new local API pattern:

- apps bind to `127.0.0.1`
- apps prefer a memorable reserved local port range starting at `50000`
- apps expose `GET /agents` as the canonical discovery endpoint
- agents scan the reserved range, request `GET /agents`, and learn how to use the app

The goal is to make local APIs self-discoverable instead of hardcoded.

## Why This Exists

Local AI agents and desktop automation tools often need to work with other apps on the same machine. The usual pattern is messy:

- one app uses a random localhost port
- another app has custom docs
- another requires special-case code inside the agent

This repo demonstrates a cleaner convention:

1. Reserve a local "agent port" range.
2. Bind only to loopback.
3. Expose `GET /agents`.
4. Return a machine-readable discovery document that explains:
   - what the app is
   - what port it is on
   - what capabilities it supports
   - what routes exist
   - what JSON payloads to send

That gives tools like OpenClaw a standard way to discover and use local apps.

## What This Example Shows

This example app:

- prefers port `50000`
- falls forward to the next free port through `50001`
- exposes `GET /agents` as the canonical discovery endpoint
- also supports `.well-known` aliases
- includes a tiny discovery client that scans the port range

It also exposes a few example JSON endpoints:

- `GET /health`
- `GET /notes`
- `GET /tasks`
- `POST /tools/echo`
- `POST /tools/add_task`
- `POST /tools/complete_task`

The endpoints are intentionally simple. The point of the repo is the discovery model, not the business logic.

## Files

- `server.py` - example localhost app implementing the pattern
- `discover.py` - small client that scans for `GET /agents`
- `README.md` - explanation and usage
- `LICENSE` - MIT license for easy GitHub publishing

## Run The Example

Start the example app:

```bash
python3 server.py
```

Expected output:

```text
Agent Port Example listening on http://127.0.0.1:50000
Discovery document: http://127.0.0.1:50000/agents
Reserved agent range: 50000-50069
```

If `50000` is already taken, it will automatically pick the next available port in the reserved range.

## Discover The App

In another terminal:

```bash
python3 discover.py
```

That script scans `127.0.0.1:50000-50069`, requests `GET /agents`, and prints any services that match `agent-port/v1`.

## Try The API

Read the discovery document:

```bash
curl -s http://127.0.0.1:50000/agents
```

Check health:

```bash
curl -s http://127.0.0.1:50000/health
```

Read feature notes:

```bash
curl -s http://127.0.0.1:50000/notes
```

Add a task:

```bash
curl -s http://127.0.0.1:50000/tools/add_task \
  -H 'Content-Type: application/json' \
  -d '{"title":"Ship the agent-port example"}'
```

Complete a task:

```bash
curl -s http://127.0.0.1:50000/tools/complete_task \
  -H 'Content-Type: application/json' \
  -d '{"id":1}'
```

## Example Discovery Shape

The most important endpoint is:

```http
GET /agents
```

It returns a document like:

```json
{
  "protocol": "agent-port/v1",
  "service": "AgentPortExample",
  "display_name": "Agent Port Example App",
  "base_url": "http://127.0.0.1:50000",
  "health_url": "http://127.0.0.1:50000/health",
  "agent_port": {
    "preferred_port": 50000,
    "current_port": 50000,
    "scan_range_start": 50000,
    "scan_range_end": 50069
  },
  "capabilities": [
    {
      "method": "GET",
      "path": "/agents",
      "summary": "Canonical machine-readable discovery document."
    },
    {
      "method": "POST",
      "path": "/tools/add_task",
      "summary": "Add a task to the local task list."
    }
  ]
}
```

## Suggested Agent Behavior

An agent should:

1. Scan the local reserved agent-port range, starting at `50000`.
2. Request `GET /agents` on each responsive localhost port.
3. Check whether `protocol == "agent-port/v1"`.
4. Use the returned `base_url` and `capabilities` to decide what it can do.
5. Avoid hardcoding app-specific ports or routes whenever possible.

## Why `GET /agents`

`GET /agents` is easy to remember, easy to document, and obvious to both humans and models.

It acts like:

- a service introduction
- a machine-readable README
- a live integration contract

The app is not just exposing an API. It is explaining itself to agents.

## Suggested Conventions

If you use this pattern in other local apps, a good baseline is:

- bind only to `127.0.0.1`
- use a memorable reserved range starting at `50000`
- expose `GET /agents` as the canonical discovery route
- optionally support `.well-known` aliases
- include `protocol`, `service`, `base_url`, and `capabilities`
- describe request schemas and examples inside the discovery document
- keep all responses JSON unless there is a good reason not to

## License

MIT
