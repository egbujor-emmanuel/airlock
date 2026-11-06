"""Open the demo: Acme's on-call engineer raises the problem in the shared room.

    uv run python scripts/start_scenario.py

Posted by the `sim-acme-oncall` stand-in. In a real deployment this is a person
typing in the shared Discord channel; anything they type there is theirs to share.
"""

from __future__ import annotations

import asyncio
import json
from pathlib import Path

from airlock.switch.creds import load_creds
from airlock.switch.http import AgentHttp

ROOT = Path(__file__).resolve().parents[1]
REPORT = (
    "@envoy-payco Hi PayCo, Acme on-call here. Since around your platform 4.2.0 release a share of your "
    "webhooks to our checkout endpoint are being rejected by our signature verification. We haven't "
    "changed our verification code and our own tests pass. Can your team take a look?"
)


async def main() -> None:
    topology = json.loads((ROOT / "config/topology.federated.json").read_text(encoding="utf-8"))
    oncall = AgentHttp(load_creds(ROOT / ".airlock/agents/sim-acme-oncall.json"))
    await oncall.send_message(topology["shared_room"], REPORT)
    await oncall.aclose()
    print("posted Acme's report to the shared room")


if __name__ == "__main__":
    asyncio.run(main())
