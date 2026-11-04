"""Push agents/*.md to the inside agents and restart them, so each starts a fresh session.

    uv run python scripts/refresh_agents.py
"""

from __future__ import annotations

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from connect_chat_apps import CORE_ENV, admin_client, read_env  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
INSIDE_AGENTS = ("claude-acme", "opencode-payco")


def put(client, agent: dict, state: str, instructions: str) -> int:
    definition = {**agent["definition"], "instructions": instructions}
    body = {"controller_id": agent["controller_id"], "desired_state": state, "definition": definition}
    return client.put(f"/management/agents/{agent['agent_id']}", json=body).status_code


def main() -> int:
    client = admin_client(read_env(CORE_ENV))
    agents = {a["name"]: a for a in client.get("/management/agents").json() if a["name"] in INSIDE_AGENTS}
    for name, agent in agents.items():
        brief = (ROOT / "agents" / f"{name}.md").read_text(encoding="utf-8")
        print(name, "stop:", put(client, agent, "stopped", brief))
    time.sleep(5)
    for name, agent in agents.items():
        brief = (ROOT / "agents" / f"{name}.md").read_text(encoding="utf-8")
        print(name, "start with new brief:", put(client, agent, "running", brief))
    return 0


if __name__ == "__main__":
    sys.exit(main())
