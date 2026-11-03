"""Run one org's envoy: a connection to each of its two rooms, and the relay.

    uv run airlock-envoy acme

One socket per room (single scope), each with a connection id kept on disk so a
restart resumes the same connection instead of opening a new one. Events from
both rooms go through one queue, in arrival order, so the relay never sees two
messages at once.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import uuid
from pathlib import Path

from airlock.ledger.chain import Ledger
from airlock.ledger.signing import load_or_create
from airlock.policy import load_policy
from airlock.relay import Message, Post, Relay
from airlock.switch.connection import RoomConnection, RoomEvent
from airlock.switch.creds import load_creds
from airlock.switch.http import AgentHttp

log = logging.getLogger("airlock.envoy")
ROOT = Path.cwd()
STATE = ROOT / ".airlock"


def connection_id(org: str, room: str) -> str:
    """Stable per (org, room): reconnecting must reuse the id, not mint one."""
    path = STATE / "connections" / f"{org}-{room}.id"
    if path.exists():
        return path.read_text(encoding="utf-8").strip()
    path.parent.mkdir(parents=True, exist_ok=True)
    value = str(uuid.uuid4())
    path.write_text(value, encoding="utf-8")
    return value


def to_message(event: RoomEvent) -> Message:
    p = event.payload
    return Message(
        sender_name=str(p.get("sender_name") or p.get("sender") or ""),
        body=str(p.get("body") or ""),
        message_id=str(p.get("message_id") or ""),
        thread_id=p.get("thread_id"),
        addressed=event.addressed,
    )


class Envoy:
    def __init__(self, org: str, topology: dict, canaries: tuple[str, ...] = ()) -> None:
        o = topology["orgs"][org]
        self.org = org
        self.rooms = {"inside": o["inside_room"], "shared": topology["shared_room"]}
        self.creds = load_creds(STATE / "agents" / f"{o['envoy']}.json")
        if self.creds is None:
            raise SystemExit(f"{o['envoy']} isn't registered yet (no credentials in .airlock/agents)")
        self.http = AgentHttp(self.creds)
        policy = load_policy(ROOT / "policies" / f"{org}.yaml", canaries)
        other = topology["orgs"][policy.other_org]["envoy"]
        ledger = Ledger(STATE / "ledger" / f"{org}.jsonl", load_or_create(STATE / "keys" / f"{org}.json", org))
        self.relay = Relay(policy, o["envoy"], other, ledger)
        self.conns = {
            name: RoomConnection(self.creds, room, connection_id(org, name)) for name, room in self.rooms.items()
        }
        self.queue: asyncio.Queue[tuple[str, RoomEvent]] = asyncio.Queue()

    async def _pump(self, name: str) -> None:
        async for event in self.conns[name].events():
            await self.queue.put((name, event))

    async def _post(self, post: Post) -> None:
        conn = self.conns[post.room]
        args = {"body": post.body}
        if post.thread_id:
            args["thread_id"] = post.thread_id
        await self.http.op("post_message", connection_id=conn.connection_id, **args)

    async def _handle(self, name: str, event: RoomEvent) -> None:
        if event.kind != "message":
            return
        msg = to_message(event)
        log.info("[%s] %s%s: %s", name, msg.sender_name, " (addressed)" if msg.addressed else "", msg.body[:120])
        posts = self.relay.on_shared(msg) if name == "shared" else self.relay.on_inside(msg)
        for post in posts:
            await self._post(post)
            log.info("  → posted to %s room (%d chars)", post.room, len(post.body))

    async def run(self) -> None:
        runners = [asyncio.create_task(c.run(), name=f"conn-{n}") for n, c in self.conns.items()]
        for name, conn in self.conns.items():
            await conn.wait_ready()
            await self.http.op("connect_to_room", connection_id=conn.connection_id,
                               room_id=self.rooms[name], include_general_instructions=False)
        pumps = [asyncio.create_task(self._pump(n), name=f"pump-{n}") for n in self.conns]
        log.info("%s online in %s", self.creds.name, ", ".join(self.rooms))
        try:
            while True:
                name, event = await self.queue.get()
                try:
                    await self._handle(name, event)
                except Exception:  # one bad message must not take the envoy down
                    log.exception("failed handling %s event %s", name, event.sequence)
        finally:
            for t in runners + pumps:
                t.cancel()
            await self.http.aclose()


def main() -> None:
    parser = argparse.ArgumentParser(description="Run an Airlock envoy")
    parser.add_argument("org")
    parser.add_argument("--topology", default="config/topology.local.json")
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(message)s")
    logging.getLogger("httpx").setLevel(logging.WARNING)
    topology = json.loads((ROOT / args.topology).read_text(encoding="utf-8"))
    canaries_file = STATE / "canaries" / f"{args.org}.txt"
    canaries = tuple(canaries_file.read_text(encoding="utf-8").split()) if canaries_file.exists() else ()
    asyncio.run(Envoy(args.org, topology, canaries).run())


if __name__ == "__main__":
    main()
