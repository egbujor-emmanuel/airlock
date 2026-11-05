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
import sys
import uuid
from pathlib import Path
from typing import IO

from airlock.ledger.chain import Ledger
from airlock.ledger.signing import load_or_create
from airlock.policy import load_policy
from airlock.relay import FOOTER, Message, Post, Relay
from airlock.switch.connection import RoomConnection, RoomEvent
from airlock.switch.creds import load_creds
from airlock.switch.http import AgentHttp

log = logging.getLogger("airlock.envoy")
ROOT = Path.cwd()
STATE = ROOT / ".airlock"
RECONCILE_WINDOW = 100  # recent shared-room messages checked for missed crossings on start


def _connection_path(org: str, room: str) -> Path:
    return STATE / "connections" / f"{org}-{room}.id"


def connection_id(org: str, room: str) -> str:
    """Stable per (org, room): reconnecting must reuse the id, not mint one."""
    path = _connection_path(org, room)
    if path.exists():
        return path.read_text(encoding="utf-8").strip()
    return save_connection_id(org, room, str(uuid.uuid4()))


def save_connection_id(org: str, room: str, value: str) -> str:
    path = _connection_path(org, room)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(value, encoding="utf-8")
    return value


def hold_single_instance_lock(org: str) -> IO[bytes]:
    """One envoy per org, ever. A second copy would fight over the connections.

    The OS releases the lock when the process dies, so a crash never leaves it stuck.
    Holding it is also what makes rotating a refused connection safe.
    """
    path = STATE / "locks" / f"envoy-{org}.lock"
    path.parent.mkdir(parents=True, exist_ok=True)
    handle = open(path, "a+b")  # noqa: SIM115 - held for the life of the process
    try:
        if sys.platform == "win32":
            import msvcrt

            handle.seek(0)
            msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
        else:
            import fcntl

            fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        raise SystemExit(f"envoy-{org} is already running (lock held: {path})") from None
    return handle


def _creds(name: str):
    creds = load_creds(STATE / "agents" / f"{name}.json")
    if creds is None:
        raise SystemExit(f"{name} isn't registered yet (no credentials in .airlock/agents)")
    return creds


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
        # Two-server mode: the inside room can live on the org's own Switch server,
        # where the envoy is registered separately. Each room gets its own credentials.
        self.creds = {
            "shared": _creds(o["envoy"]),
            "inside": _creds(o.get("inside_envoy", o["envoy"])),
        }
        self.http = {room: AgentHttp(c) for room, c in self.creds.items()}
        policy = load_policy(ROOT / "policies" / f"{org}.yaml", canaries)
        other = topology["orgs"][policy.other_org]["envoy"]
        ledger = Ledger(STATE / "ledger" / f"{org}.jsonl", load_or_create(STATE / "keys" / f"{org}.json", org))
        self.relay = Relay(policy, o["envoy"], other, ledger)
        self._lock = hold_single_instance_lock(org)
        self.conns = {
            name: RoomConnection(
                self.creds[name], room, connection_id(org, name),
                on_rotate=lambda new_id, name=name: save_connection_id(org, name, new_id),
            )
            for name, room in self.rooms.items()
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
        await self.http[post.room].op("post_message", connection_id=conn.connection_id, **args)

    async def _handle(self, name: str, event: RoomEvent) -> None:
        if event.kind != "message":
            return
        msg = to_message(event)
        log.info("[%s] %s%s: %s", name, msg.sender_name, " (addressed)" if msg.addressed else "", msg.body[:120])
        posts = self.relay.on_shared(msg) if name == "shared" else self.relay.on_inside(msg)
        for post in posts:
            await self._post(post)
            log.info("  → posted to %s room (%d chars)", post.room, len(post.body))

    async def _reconcile(self) -> None:
        """Catch up on crossings posted to the shared room while this envoy was down."""
        ctx = await self.http["shared"].op(
            "read_context", connection_id=self.conns["shared"].connection_id, limit=RECONCILE_WINDOW
        )
        entries = [m for t in ctx.get("threads", []) for m in [t.get("root", t), *t.get("replies", [])]]
        history = [
            Message(sender_name=str(m.get("sender_name", "")), body=str(m.get("body", "")),
                    message_id=str(m.get("id", "")))
            for m in sorted(entries, key=lambda m: m.get("timestamp", 0))
        ]
        in_room = {m.group(1) for msg in history if (m := FOOTER.search(msg.body))}
        ours = self.relay.unposted(in_room)
        theirs = self.relay.reconcile(history)
        for post in ours + theirs:
            await self._post(post)
        if ours:
            log.info("re-posted %d approved crossing(s) that never reached the shared room", len(ours))
        if theirs:
            log.info("countersigned %d crossing(s) posted while this envoy was down", len(theirs))

    async def run(self) -> None:
        runners = [asyncio.create_task(c.run(), name=f"conn-{n}") for n, c in self.conns.items()]
        for name, conn in self.conns.items():
            await conn.wait_ready()
            await self.http[name].op("connect_to_room", connection_id=conn.connection_id,
                                     room_id=self.rooms[name], include_general_instructions=False)
        await self._reconcile()
        pumps = [asyncio.create_task(self._pump(n), name=f"pump-{n}") for n in self.conns]
        servers = {name: c.base_url for name, c in self.creds.items()}
        log.info("%s online: inside on %s, shared on %s", self.creds["shared"].name, servers["inside"], servers["shared"])
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
            for http in self.http.values():
                await http.aclose()


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
