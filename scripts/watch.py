"""Print a room's messages since N minutes ago: `uv run python scripts/watch.py acme 10`."""
import asyncio, json, pathlib, sys, time
from airlock.switch.creds import load_creds
from airlock.switch.http import AgentHttp
ROOT = pathlib.Path(__file__).resolve().parents[1]
topo = json.loads((ROOT / "config/topology.local.json").read_text())
ROOMS = {"acme": ("envoy-acme", topo["orgs"]["acme"]["inside_room"]),
         "payco": ("envoy-payco", topo["orgs"]["payco"]["inside_room"]),
         "shared": ("envoy-acme", topo["shared_room"])}
async def main(which, minutes, width):
    reader, room = ROOMS[which]
    h = AgentHttp(load_creds(ROOT / f".airlock/agents/{reader}.json"))
    since = (time.time() - minutes * 60) * 1000
    ctx = await h.op("read_context", room_id=room, limit=40)
    msgs = sorted((m for t in ctx["threads"] for m in [t.get("root", t)] + t.get("replies", [])), key=lambda m: m.get("timestamp", 0))
    for m in msgs:
        if m.get("timestamp", 0) >= since:
            print(time.strftime("%H:%M:%S", time.localtime(m["timestamp"] / 1000)), m.get("sender_name"), "|", m.get("body", "").replace("\n", " ⏎ ")[:width])
    await h.aclose()
asyncio.run(main(sys.argv[1], float(sys.argv[2]) if len(sys.argv) > 2 else 10, int(sys.argv[3]) if len(sys.argv) > 3 else 400))
