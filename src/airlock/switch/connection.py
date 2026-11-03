"""WebSocket half of the Switch agent protocol, one connection per room.

Rules this module exists to get right (docs: internals/agent-connection):

* Every frame is ``{"event": kind, "data": {...}}``. The server pings every
  2 s and evicts a connection that has not ponged for 6 s, so the reader
  answers a ping before it does anything else, and slow work happens off it.
* The connection id is a UUID reused on every reconnect, and a reconnect
  passes ``start_from`` (our cursor) and ``expected_generation`` so it only
  ever takes back our own connection.
* Rooms are declared on the open URL: a room claimed later loses the events
  buffered before the claim.
* ``taken_over`` is final. ``closed`` is not retried automatically. Lapses and
  refused pongs are resumed from the cursor.
"""

from __future__ import annotations

import asyncio
import json
import logging
from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from typing import Any
from urllib.parse import urlencode

import websockets
from websockets.exceptions import ConnectionClosed

from airlock.switch.creds import AgentCreds

log = logging.getLogger(__name__)

DOMAIN_EVENTS = frozenset({"message", "command", "room_join"})
RESUMABLE_EVICTIONS = frozenset({"heartbeat_lapsed", "no_stream", "unfenced", "connection_error"})
FINAL_EVICTIONS = frozenset({"taken_over", "closed"})
# Close codes 44xx are 4000 + an HTTP status. 4401/4403/4400 won't fix
# themselves by retrying; 4409 is a takeover or a claim conflict.
FINAL_CLOSE_CODES = frozenset({4400, 4401, 4403, 4409})
RECONNECT_BACKOFF_S = (0.5, 1, 2, 5, 10)


class ConnectionStopped(RuntimeError):
    """The server told us not to reconnect."""


@dataclass(frozen=True)
class RoomEvent:
    kind: str
    room_id: str
    sequence: int
    payload: dict[str, Any]
    gap: dict[str, Any] | None = None

    @property
    def addressed(self) -> bool:
        return bool(self.payload.get("addressed")) if self.kind == "message" else False


@dataclass
class ConnectionState:
    connection_id: str
    cursor: int | None = None
    generation: int | None = None
    rooms: list[str] = field(default_factory=list)
    pending_gap: dict[str, Any] | None = None


def ws_url(base_url: str, agent_id: str, room_id: str, state: ConnectionState) -> str:
    scheme_base = base_url.replace("https://", "wss://", 1).replace("http://", "ws://", 1)
    params: dict[str, str] = {
        "connection_id": state.connection_id,
        "rooms": room_id,
        "filter": "all",
        "client": "airlock-envoy",
    }
    if state.cursor is not None:
        params["start_from"] = str(state.cursor)
    if state.generation is not None:
        params["expected_generation"] = str(state.generation)
    return f"{scheme_base.rstrip('/')}/agents/{agent_id}/connection/ws?{urlencode(params)}"


def apply_control(state: ConnectionState, kind: str, data: dict[str, Any]) -> None:
    """Update connection state from a control frame; raise when we must stop."""
    if kind == "connection_state":
        state.generation = data.get("generation")
        state.rooms = list(data.get("rooms") or [])
        if data.get("cursor") is not None:
            state.cursor = int(data["cursor"])
    elif kind == "gap":
        state.cursor = int(data["resumed_at"])
        state.pending_gap = data
    elif kind == "refused":
        raise ConnectionStopped(f"refused {data.get('status')}: {data.get('detail')}")
    elif kind == "evicted":
        code = data.get("code")
        if code in FINAL_EVICTIONS:
            raise ConnectionStopped(f"evicted {code}: {data.get('reason')}")
        log.warning("evicted %s, will resume from %s", code, state.cursor)


def to_event(state: ConnectionState, kind: str, data: dict[str, Any]) -> RoomEvent:
    sequence = int(data.get("id", data.get("sequence", 0)))
    gap, state.pending_gap = state.pending_gap, None
    return RoomEvent(
        kind=kind,
        room_id=str(data.get("room_id", "")),
        sequence=sequence,
        payload=dict(data.get("payload") or {}),
        gap=gap,
    )


class RoomConnection:
    """Holds one room's socket open and yields its domain events in order.

    The cursor advances only when the consumer asks for the next event, so an
    event that was received but not yet handled is replayed after a reconnect.
    """

    def __init__(self, creds: AgentCreds, room_id: str, connection_id: str) -> None:
        self.creds = creds
        self.room_id = room_id
        self.state = ConnectionState(connection_id=connection_id)
        self._queue: asyncio.Queue[RoomEvent] = asyncio.Queue()
        self._stopped: BaseException | None = None
        self._ready = asyncio.Event()

    @property
    def connection_id(self) -> str:
        return self.state.connection_id

    async def wait_ready(self, timeout: float = 15.0) -> None:
        await asyncio.wait_for(self._ready.wait(), timeout)

    async def run(self) -> None:
        attempt = 0
        while True:
            try:
                await self._session()
                attempt = 0
            except ConnectionStopped as exc:
                self._stopped = exc
                log.error("room %s connection stopped: %s", self.room_id, exc)
                raise
            except (OSError, ConnectionClosed, asyncio.TimeoutError) as exc:
                if isinstance(exc, ConnectionClosed) and exc.rcvd and exc.rcvd.code in FINAL_CLOSE_CODES:
                    self._stopped = ConnectionStopped(f"closed {exc.rcvd.code}: {exc.rcvd.reason}")
                    raise self._stopped from exc
                delay = RECONNECT_BACKOFF_S[min(attempt, len(RECONNECT_BACKOFF_S) - 1)]
                log.warning("room %s socket dropped (%s); reconnecting in %ss", self.room_id, exc, delay)
                attempt += 1
                await asyncio.sleep(delay)

    async def _session(self) -> None:
        url = ws_url(self.creds.base_url, self.creds.agent_id, self.room_id, self.state)
        headers = {"Authorization": f"Bearer {self.creds.api_key}"}
        async with websockets.connect(url, additional_headers=headers, ping_interval=None) as ws:
            async for raw in ws:
                frame = json.loads(raw)
                kind, data = frame.get("event"), frame.get("data") or {}
                if kind == "ping":
                    await ws.send(json.dumps({"type": "pong", "cursor": self.state.cursor or 0}))
                    continue
                if kind in DOMAIN_EVENTS:
                    await self._queue.put(to_event(self.state, kind, data))
                    continue
                apply_control(self.state, kind, data)
                if kind == "connection_state":
                    self._ready.set()

    async def events(self) -> AsyncIterator[RoomEvent]:
        while True:
            if self._stopped is not None and self._queue.empty():
                raise self._stopped
            event = await self._queue.get()
            yield event
            # Handled: only now may a reconnect skip past it.
            self.state.cursor = max(self.state.cursor or 0, event.sequence)
