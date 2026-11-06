"""Push agents/*.md to the inside agents and restart them.

    uv run python scripts/refresh_agents.py                    # one server: both agents on server A
    uv run python scripts/refresh_agents.py --server-b         # two servers: claude-acme on server B
    uv run python scripts/refresh_agents.py --server-b --fresh # ...and start brand-new sessions

A plain restart resumes the agent's previous conversation: Switch keeps each managed
agent's native session id in ~/.local/state/switch/sdk-sessions/<hash>/ and picks it
up again on start. `--fresh` moves that folder aside while the agent is stopped, so
it comes back with no memory of earlier runs (use it before every recorded demo).
With `--server-b`, server A's own copy of claude-acme is stopped and left stopped:
in two-server mode Acme's agent lives only on Acme's server.
"""

from __future__ import annotations

import shutil
import sys
import time
from pathlib import Path

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parent))
from connect_chat_apps import CORE_ENV, admin_client, read_env  # noqa: E402
from setup_server_b import ENV_B, admin_b  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
SESSIONS = Path.home() / ".local" / "state" / "switch" / "sdk-sessions"
ARCHIVE = ROOT / ".airlock" / "archive" / "sdk-sessions"
SETTLE_SECONDS = 5


def put(client: httpx.Client, agent: dict, state: str, instructions: str | None = None) -> int:
    definition = dict(agent["definition"])
    if instructions is not None:
        definition["instructions"] = instructions
    body = {"controller_id": agent["controller_id"], "desired_state": state, "definition": definition}
    return client.put(f"/management/agents/{agent['agent_id']}", json=body).status_code


def find(client: httpx.Client, name: str) -> dict | None:
    return next((a for a in client.get("/management/agents").json() if a["name"] == name), None)


def archive_sessions(agent_id: str) -> list[str]:
    """Move aside every session folder that belongs to this agent; return their names."""
    if not SESSIONS.exists():
        return []
    stamp = time.strftime("%Y%m%d-%H%M%S")
    moved = []
    for folder in SESSIONS.iterdir():
        config = folder / "config.json"
        if config.exists() and agent_id in config.read_text(encoding="utf-8", errors="replace"):
            target = ARCHIVE / f"{stamp}-{folder.name[:12]}"
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(folder), str(target))
            moved.append(folder.name[:12])
    return moved


def main() -> int:
    server_b = "--server-b" in sys.argv
    fresh = "--fresh" in sys.argv
    client_a = admin_client(read_env(CORE_ENV))
    targets = [(client_a, "opencode-payco")]
    if server_b:
        targets.append((admin_b(read_env(ENV_B)), "claude-acme"))
        stale = find(client_a, "claude-acme")
        if stale is not None:
            print("server A claude-acme (unused in two-server mode) stop:", put(client_a, stale, "stopped"))
    else:
        targets.append((client_a, "claude-acme"))

    agents = []
    for client, name in targets:
        agent = find(client, name)
        if agent is None:
            print(f"{name}: not found; run scripts/setup_inside_agents.py first")
            return 1
        agents.append((client, agent, (ROOT / "agents" / f"{name}.md").read_text(encoding="utf-8")))

    for client, agent, brief in agents:
        print(agent["name"], "stop:", put(client, agent, "stopped", brief))
    time.sleep(SETTLE_SECONDS)
    if fresh:
        for _, agent, _ in agents:
            moved = archive_sessions(agent["agent_id"])
            print(agent["name"], "previous session archived:", ", ".join(moved) or "none found")
    for client, agent, brief in agents:
        print(agent["name"], "start:", put(client, agent, "running", brief))
    return 0


if __name__ == "__main__":
    sys.exit(main())
