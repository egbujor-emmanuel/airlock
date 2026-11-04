"""Set up Airlock on a Switch server: envoys, the shared room, and who may talk to whom.

    uv run python scripts/setup_envoys.py

Run after scripts/connect_chat_apps.py, once the two Telegram groups ("Acme Inside"
and "PayCo Inside") have the bot in them and one message each, so Switch has made a
room for each. The script:

1. registers `envoy-acme` and `envoy-payco` (once; credentials kept in .airlock/agents)
2. creates the shared room `acme-x-payco` on Discord, with only the two envoys in it
3. puts each envoy in its own org's inside room, and nowhere else
4. lets each envoy take instructions only in its own two rooms
5. writes config/topology.local.json, which the envoys read

Safe to re-run: anything that already exists is reused.
"""

from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from connect_chat_apps import CORE_ENV, admin_client, read_env  # noqa: E402

from airlock.switch.creds import load_creds  # noqa: E402
from airlock.switch.http import AgentHttp, ensure_registered  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
SHARED_NAME = "acme-x-payco"
ORGS = {
    "acme": {"display": "Acme Envoy", "inside_name": "Acme Inside"},
    "payco": {"display": "PayCo Envoy", "inside_name": "PayCo Inside"},
}


def registration_key() -> str:
    key_file = ROOT / ".secrets" / "registration.key"
    if key_file.exists():
        return key_file.read_text(encoding="utf-8").strip()
    # A server Switch Console runs for you carries a bootstrap registration token.
    return read_env(CORE_ENV)["AGENT_REGISTRATION_TOKEN"]


def find_room(client, name_part: str) -> str | None:
    rows = client.get("/rooms").json()
    rooms = rows if isinstance(rows, list) else rows.get("rooms", rows.get("items", []))
    for room in rooms:
        if name_part.lower() in str(room.get("name", "")).lower() and not room.get("archived"):
            return room["id"]
    return None


def bridge_id(client, bridge_type: str) -> str:
    rows = client.get("/collaborations").json()
    bridges = rows if isinstance(rows, list) else rows.get("bridges", rows.get("items", []))
    for b in bridges:
        if b.get("type") == bridge_type:
            return b["id"]
    raise SystemExit(f"No {bridge_type} connection yet: run scripts/connect_chat_apps.py first")


async def register_envoys(base_url: str) -> dict[str, str]:
    ids = {}
    for org, spec in ORGS.items():
        creds = await ensure_registered(
            ROOT / ".airlock" / "agents" / f"envoy-{org}.json", base_url, registration_key(),
            name=f"envoy-{org}", display_name=spec["display"],
            description=(f"{spec['display']}: the only way anything crosses between "
                         f"{org.title()}'s private room and the shared room. Redacts, asks a human, signs."),
        )
        ids[org] = creds.agent_id
        print(f"envoy-{org}: {creds.agent_id}")
    return ids


async def create_shared_room(discord_id: str) -> str:
    acme = AgentHttp(load_creds(ROOT / ".airlock" / "agents" / "envoy-acme.json"))
    room = await acme.op(
        "create_room", name=SHARED_NAME, bridge_id=discord_id, channel_type="channel_public",
        agent_names=["envoy-acme", "envoy-payco"],
        description="Shared room: Acme (customer) and PayCo (vendor). Only envoys relay private findings here.",
    )
    await acme.aclose()
    return room["id"]


def main() -> int:
    core = read_env(CORE_ENV)
    base_url = f"http://127.0.0.1:{core['SERVER_PORT']}"
    client = admin_client(core)
    ids = asyncio.run(register_envoys(base_url))

    shared = find_room(client, SHARED_NAME) or asyncio.run(create_shared_room(bridge_id(client, "discord")))
    print("shared room:", shared)

    topology = {"base_url": base_url, "shared_room": shared, "orgs": {}}
    for org, spec in ORGS.items():
        inside = find_room(client, spec["inside_name"])
        if inside is None:
            raise SystemExit(f"No room for the Telegram group '{spec['inside_name']}' yet: add the bot "
                             "to the group, send one message there, then re-run.")
        client.post(f"/rooms/{inside}/agents", json={"agent_ids": [ids[org]]})
        client.post(f"/rooms/{shared}/agents", json={"agent_ids": [ids[org]]})
        policy = {"policy": {"rules": [{"rooms": [shared, inside]}]}}
        status = client.put(f"/agents/{ids[org]}/addressing-policy", json=policy).status_code
        print(f"envoy-{org}: inside room {inside}; takes instructions only in its two rooms ({status})")
        topology["orgs"][org] = {"envoy": f"envoy-{org}", "inside_room": inside}

    out = ROOT / "config" / "topology.local.json"
    out.parent.mkdir(exist_ok=True)
    out.write_text(json.dumps(topology, indent=2), encoding="utf-8")
    print("wrote", out.relative_to(ROOT))
    return 0


if __name__ == "__main__":
    sys.exit(main())
