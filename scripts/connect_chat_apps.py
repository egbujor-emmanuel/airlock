"""Connect Discord and Telegram to the local Switch server, from .secrets/chat.env.

Signs in as the server's admin (the account Switch Console created for the local
server) and registers each messaging app through the Gateway, the same call
Console's Connect form makes. Skips an app that is already connected.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parents[1]
CORE_ENV = Path(os.environ["APPDATA"]) / "switchdash/local-switch-server/native/run/switch-core.env"


def read_env(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        if "=" in line and not line.lstrip().startswith("#"):
            key, value = line.split("=", 1)
            values[key.strip()] = value.strip()
    return values


def admin_client(core: dict[str, str]) -> httpx.Client:
    base = f"http://127.0.0.1:{core['SERVER_PORT']}/gateway"
    client = httpx.Client(base_url=base, timeout=60)
    resp = client.post(
        "/auth/login",
        json={"email": core["GATEWAY_ADMIN_EMAIL"], "password": core["GATEWAY_ADMIN_PASSWORD"]},
    )
    resp.raise_for_status()
    return client


def connect(client: httpx.Client, bridge_type: str, name: str, config: dict[str, object]) -> None:
    existing = client.get("/collaborations").json()
    rows = existing if isinstance(existing, list) else existing.get("bridges", existing.get("items", []))
    if any(b.get("bridge_type", b.get("type")) == bridge_type for b in rows):
        print(f"{bridge_type}: already connected")
        return
    resp = client.post(
        "/collaborations",
        json={
            "bridge_type": bridge_type,
            "display_name": name,
            "connection_config": config,
            "channel_creation_enabled": bridge_type == "discord",
            "set_as_default": bridge_type == "discord",
        },
    )
    if resp.is_success:
        print(f"{bridge_type}: connected ({resp.json().get('id')})")
    else:
        print(f"{bridge_type}: FAILED {resp.status_code}: {resp.text[:400]}")


def main() -> int:
    chat = read_env(ROOT / ".secrets/chat.env")
    missing = [k for k, v in chat.items() if not v]
    if missing:
        print("Still empty in .secrets/chat.env:", ", ".join(missing))
        return 1
    client = admin_client(read_env(CORE_ENV))
    connect(client, "discord", "Airlock Discord",
            {"bot_token": chat["DISCORD_BOT_TOKEN"], "guild_id": chat["DISCORD_SERVER_ID"], "agent_roles": True})
    connect(client, "telegram", "Airlock Telegram",
            {"bot_token": chat["TELEGRAM_BOT_TOKEN"], "bot_username": chat["TELEGRAM_BOT_USERNAME"].lstrip("@")})
    return 0


if __name__ == "__main__":
    sys.exit(main())
