"""Live end-to-end test of one crossing, against a running Switch server and envoys.

Stand-in agents play the people: a PayCo engineer asks in the shared room,
Acme's agent answers in Acme's room (leaking a fake key), and Acme's approver
approves. The script then checks what actually landed in each room and that
both ledgers verify. Run it with both envoys up and ``sim-acme-lead`` listed
as an approver in policies/acme.yaml.
"""

from __future__ import annotations

import asyncio
import json
import re
import sys
import time
from pathlib import Path

from airlock.ledger.chain import verify_chain
from airlock.ledger.signing import load_or_create
from airlock.switch.creds import load_creds
from airlock.switch.http import AgentHttp

ROOT = Path(__file__).resolve().parents[1]
TOPO = json.loads((ROOT / "config/topology.local.json").read_text(encoding="utf-8"))
SHARED = TOPO["shared_room"]
ACME_IN = TOPO["orgs"]["acme"]["inside_room"]
PAYCO_IN = TOPO["orgs"]["payco"]["inside_room"]
FAKE_KEY = "AKIA" + "Z7Q2" * 4
WAIT_S = 45


def agent(name: str) -> AgentHttp:
    return AgentHttp(load_creds(ROOT / f".airlock/agents/{name}.json"))


def flatten(ctx: dict) -> list[dict]:
    out = []
    for thread in ctx.get("threads", []):
        out.append(thread.get("root", thread))
        out.extend(thread.get("replies", []))
    return out


async def wait_for(reader: AgentHttp, room: str, sender: str, pattern: str, since_ms: int) -> dict:
    deadline = time.monotonic() + WAIT_S
    while time.monotonic() < deadline:
        msgs = flatten(await reader.op("read_context", room_id=room, limit=30))
        for m in msgs:
            if m.get("sender_name") == sender and m.get("timestamp", 0) >= since_ms and re.search(pattern, m.get("body", "")):
                return m
        await asyncio.sleep(1.5)
    raise TimeoutError(f"no message from {sender} matching {pattern!r} in room {room}")


def step(n: int, text: str) -> None:
    print(f"\n[{n}] {text}")


async def main() -> int:
    eng, acme_agent, lead = agent("sim-payco-eng"), agent("sim-acme-agent"), agent("envoy-payco")
    acme_lead = agent("sim-acme-lead")
    start = int(time.time() * 1000)

    step(1, "PayCo engineer asks Acme's envoy in the shared room")
    await eng.send_message(SHARED, "@envoy-acme what Content-Type and body does your webhook endpoint receive?")
    q = await wait_for(acme_agent, ACME_IN, "envoy-acme", r"📨", start)
    assert "＠envoy-acme" in q["body"], "the relayed question kept a live mention"
    print("    arrived in Acme Inside, quoted and defanged ✓")

    step(2, "Acme's agent answers to its envoy, leaking a fake AWS key")
    await acme_agent.send_message(
        ACME_IN, f"@envoy-acme It arrives as application/json but express.json() parses it first. Our key is {FAKE_KEY}"
    )
    req = await wait_for(acme_agent, ACME_IN, "envoy-acme", r"🔒 Crossing A-\d+", start)
    crossing = re.search(r"Crossing (A-\d+)", req["body"]).group(1)
    assert FAKE_KEY not in req["body"] and "[REDACTED:aws_access_key" in req["body"]
    print(f"    approval request {crossing}, key redacted ✓")

    step(3, "Before approval, nothing from Acme is in the shared room")
    early = [m for m in flatten(await eng.op("read_context", room_id=SHARED, limit=30))
             if m.get("sender_name") == "envoy-acme" and m.get("timestamp", 0) >= start]
    assert not early, "something crossed before approval"
    print("    shared room has nothing from Acme ✓")

    step(4, f"Acme's approver approves {crossing}")
    await acme_lead.send_message(ACME_IN, f"approve {crossing}")
    out = await wait_for(eng, SHARED, "envoy-acme", rf"airlock crossing {crossing} · entry", start)
    assert FAKE_KEY not in out["body"]
    print("    redacted answer posted to shared room with signed footer ✓")

    step(5, "PayCo's envoy receives it and countersigns")
    await wait_for(lead, PAYCO_IN, "envoy-payco", rf"📥 .*crossing {crossing}", start)
    print("    PayCo Inside got it with a receipt ✓")

    step(6, "Both ledgers verify (ML-DSA-65 signatures, hash chain)")
    for org in ("acme", "payco"):
        key = load_or_create(ROOT / f".airlock/keys/{org}.json", org)
        lines = (ROOT / f".airlock/ledger/{org}.jsonl").read_text(encoding="utf-8").splitlines()
        result = verify_chain([json.loads(x) for x in lines if x.strip()], {org: key.public_key})
        assert result.ok, result.problems
        print(f"    {org}: {result.entries} entries, chain and signatures valid ✓")

    for h in (eng, acme_agent, lead, acme_lead):
        await h.aclose()
    print("\nSELFTEST PASSED")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
