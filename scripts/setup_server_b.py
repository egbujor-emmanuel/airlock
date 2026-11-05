"""Set up Acme's own Switch server (two-server mode).

    uv run python scripts/setup_server_b.py

Run after scripts/server_b.py start. Then, in Telegram, create a new group (for
example "Acme Private") with only the new bot from .secrets/chat2.env in it, send
one message there, and run this again. It:

1. connects the second Telegram bot to server B
2. registers `envoy-acme` on server B (a separate identity from the one on server A)
3. finds Acme's private room on server B and puts the envoy in it, taking
   instructions only there
4. writes config/topology.federated.json: Acme's inside room on server B,
   the shared room and PayCo's room on server A

Safe to re-run.
"""

from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parent))
from connect_chat_apps import read_env  # noqa: E402

from airlock.switch.http import ensure_registered  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
ENV_B = ROOT / ".airlock" / "server-b" / "switch-core.env"
CREDS_B = ROOT / ".airlock" / "agents" / "envoy-acme-b.json"


def admin_b(env: dict[str, str]) -> httpx.Client:
    client = httpx.Client(base_url=f"http://127.0.0.1:{env['SERVER_PORT']}/gateway", timeout=60)
    resp = client.post("/auth/login", json={"email": env["GATEWAY_ADMIN_EMAIL"], "password": env["GATEWAY_ADMIN_PASSWORD"]})
    resp.raise_for_status()
    return client


def connect_telegram(client: httpx.Client) -> None:
    rows = client.get("/collaborations").json()
    bridges = rows if isinstance(rows, list) else rows.get("bridges", rows.get("items", []))
    if any(b.get("bridge_type", b.get("type")) == "telegram" for b in bridges):
        print("server B telegram: already connected")
        return
    chat = read_env(ROOT / ".secrets" / "chat2.env")
    if not chat.get("TELEGRAM_BOT_TOKEN"):
        raise SystemExit("Fill in .secrets/chat2.env first")
    resp = client.post("/collaborations", json={
        "bridge_type": "telegram",
        "display_name": "Acme Telegram",
        "connection_config": {"bot_token": chat["TELEGRAM_BOT_TOKEN"],
                              "bot_username": chat["TELEGRAM_BOT_USERNAME"].lstrip("@")},
        "channel_creation_enabled": False,
        "set_as_default": True,
    })
    if resp.is_success or "already uses Telegram bot" in resp.text:
        print("server B telegram: connected")
    else:
        print(f"server B telegram: FAILED {resp.status_code} {resp.text[:300]}")


def acme_room(client: httpx.Client) -> str | None:
    rows = client.get("/rooms").json()
    rooms = rows if isinstance(rows, list) else rows.get("rooms", rows.get("items", []))
    live = [r for r in rooms if not r.get("archived") and r.get("bridge_type") == "telegram"]
    return live[0]["id"] if live else None


def main() -> int:
    env = read_env(ENV_B)
    base_b = f"http://127.0.0.1:{env['SERVER_PORT']}"
    client = admin_b(env)
    connect_telegram(client)
    creds = asyncio.run(ensure_registered(
        CREDS_B, base_b, env["AGENT_REGISTRATION_TOKEN"], name="envoy-acme", display_name="Acme Envoy",
        description="Acme Envoy on Acme's own server: the inside half. Its other half sits in the shared room on PayCo's server.",
    ))
    print("envoy-acme on server B:", creds.agent_id)

    room = acme_room(client)
    if room is None:
        print("\nNext: in Telegram, create a group (e.g. 'Acme Private') with ONLY the new bot in it, "
              "send one message there, then run this script again.")
        return 0
    client.post(f"/rooms/{room}/agents", json={"agent_ids": [creds.agent_id]})
    client.put(f"/agents/{creds.agent_id}/addressing-policy", json={"policy": {"rules": [{"rooms": [room]}]}})
    print("Acme's private room on server B:", room)

    single = json.loads((ROOT / "config" / "topology.local.json").read_text(encoding="utf-8"))
    federated = {
        **single,
        "orgs": {
            **single["orgs"],
            "acme": {"envoy": "envoy-acme", "inside_envoy": "envoy-acme-b", "inside_room": room,
                     "inside_server": base_b},
        },
    }
    out = ROOT / "config" / "topology.federated.json"
    out.write_text(json.dumps(federated, indent=2), encoding="utf-8")
    print("wrote", out.relative_to(ROOT))
    return 0


if __name__ == "__main__":
    sys.exit(main())
