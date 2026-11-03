"""Create each org's coding agent in its inside room (and nowhere else).

    uv run python scripts/setup_inside_agents.py

Acme gets Claude Code in demo/acme-app; PayCo gets OpenCode on a free model in
demo/payco-sdk. Two vendors' agents, one per org. Each is a managed agent on this
machine's Switch controller, a member of its own inside room only, and takes
instructions only in that room. Re-running skips an agent that already exists.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from connect_chat_apps import CORE_ENV, admin_client, read_env  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
TOPO = json.loads((ROOT / "config/topology.local.json").read_text(encoding="utf-8"))

AGENTS = [
    {
        "org": "acme",
        "name": "claude-acme",
        "display_name": "Acme Engineer (Claude Code)",
        "description": "Acme's engineering agent: works on Acme's checkout service, inside Acme only.",
        "provider": "claude",
        "model": None,
        # Claude Code's own automatic review decides what needs asking.
        "auto_mode": True,
        "directory": ROOT / "demo" / "acme-app",
    },
    {
        "org": "payco",
        "name": "opencode-payco",
        "display_name": "PayCo SDK Engineer (OpenCode)",
        "description": "PayCo's SDK agent: works on the webhooks SDK, inside PayCo only.",
        "provider": "opencode",
        "model": "opencode/deepseek-v4.1-flash-free",
        # OpenCode's auto mode approves everything unreviewed, so this one asks in the room.
        "auto_mode": False,
        "directory": ROOT / "demo" / "payco-sdk",
    },
]


def online_controller(client) -> str:
    controllers = client.get("/management/controllers").json()
    rows = controllers if isinstance(controllers, list) else controllers.get("controllers", [])
    for c in rows:
        if c.get("state", c.get("controller_state")) == "online":
            return c.get("controller_id") or c["id"]
    # Fall back to the controller the existing managed agents run on.
    agents = client.get("/management/agents").json()
    return next(a["controller_id"] for a in agents if a.get("controller_state") == "online")


def ensure_agent(client, spec: dict, controller_id: str) -> str:
    existing = {a["name"]: a for a in client.get("/management/agents").json()}
    if spec["name"] in existing:
        print(f"{spec['name']}: already exists")
        return existing[spec["name"]]["agent_id"]
    body = {
        "name": spec["name"],
        "description": spec["description"],
        "display_name": spec["display_name"],
        "controller_id": controller_id,
        "desired_state": "running",
        "definition": {
            "provider": spec["provider"],
            "model": spec["model"],
            "instructions": (ROOT / "agents" / f"{spec['name']}.md").read_text(encoding="utf-8"),
            "auto_mode": spec["auto_mode"],
            "auto_approve": False,
            "directory": str(spec["directory"]),
            "isolation": "shared",
            "advanced_config": {},
        },
    }
    resp = client.post("/management/agents", json=body)
    if not resp.is_success:
        raise SystemExit(f"{spec['name']}: create failed {resp.status_code}: {resp.text[:500]}")
    agent_id = resp.json().get("agent_id") or resp.json().get("id")
    print(f"{spec['name']}: created ({agent_id})")
    return agent_id


def place_in_inside_room(client, spec: dict, agent_id: str) -> None:
    room = TOPO["orgs"][spec["org"]]["inside_room"]
    resp = client.post(f"/rooms/{room}/agents", json={"agent_ids": [agent_id]})
    print(f"  joined {spec['org']} inside room: {resp.status_code}")
    policy = {"policy": {"rules": [{"rooms": [room]}]}}
    resp = client.put(f"/agents/{agent_id}/addressing-policy", json=policy)
    print(f"  takes instructions only in that room: {resp.status_code}")


def main() -> int:
    client = admin_client(read_env(CORE_ENV))
    controller_id = online_controller(client)
    print("controller:", controller_id)
    for spec in AGENTS:
        agent_id = ensure_agent(client, spec, controller_id)
        place_in_inside_room(client, spec, agent_id)
    return 0


if __name__ == "__main__":
    sys.exit(main())
