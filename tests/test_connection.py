import asyncio
import json
from urllib.parse import parse_qs, urlparse

import pytest
import websockets

from airlock.switch.connection import (
    ConnectionState,
    ConnectionStopped,
    RoomConnection,
    apply_control,
    to_event,
    ws_url,
)
from airlock.switch.creds import AgentCreds


def _query(url: str) -> dict[str, list[str]]:
    return parse_qs(urlparse(url).query)


def test_ws_url_declares_room_and_connection_on_first_open():
    state = ConnectionState(connection_id="c-1")

    url = ws_url("http://127.0.0.1:61913", "agent-1", "room-9", state)

    assert url.startswith("ws://127.0.0.1:61913/agents/agent-1/connection/ws?")
    q = _query(url)
    assert q["connection_id"] == ["c-1"]
    assert q["rooms"] == ["room-9"]
    assert "start_from" not in q and "expected_generation" not in q


def test_ws_url_fences_a_reconnect_with_cursor_and_generation():
    state = ConnectionState(connection_id="c-1", cursor=42, generation=7)

    q = _query(ws_url("https://switch.example", "a", "r", state))

    assert q["start_from"] == ["42"]
    assert q["expected_generation"] == ["7"]


def test_ws_url_uses_wss_for_https():
    assert ws_url("https://h", "a", "r", ConnectionState("c")).startswith("wss://h/")


def test_connection_state_frame_is_read_not_assumed():
    state = ConnectionState(connection_id="c")

    apply_control(state, "connection_state", {"generation": 3, "rooms": ["r"], "cursor": 10})

    assert (state.generation, state.rooms, state.cursor) == (3, ["r"], 10)


def test_gap_moves_cursor_and_attaches_to_next_event():
    state = ConnectionState(connection_id="c", cursor=5)
    apply_control(state, "gap", {"resumed_at": 90, "reason": "retention"})

    event = to_event(state, "message", {"id": 91, "room_id": "r", "payload": {"addressed": True}})

    assert state.cursor == 90
    assert event.gap == {"resumed_at": 90, "reason": "retention"}
    assert to_event(state, "message", {"id": 92, "payload": {}}).gap is None


@pytest.mark.parametrize("code", ["taken_over", "closed"])
def test_final_evictions_stop_the_connection(code):
    with pytest.raises(ConnectionStopped):
        apply_control(ConnectionState("c"), "evicted", {"code": code})


@pytest.mark.parametrize("code", ["heartbeat_lapsed", "no_stream", "unfenced", "connection_error"])
def test_resumable_evictions_do_not_stop(code):
    apply_control(ConnectionState("c", cursor=3), "evicted", {"code": code})


def test_refused_stops():
    with pytest.raises(ConnectionStopped):
        apply_control(ConnectionState("c"), "refused", {"status": 409, "detail": "claimed"})


def test_only_addressed_messages_are_addressed():
    state = ConnectionState("c")
    assert to_event(state, "message", {"id": 1, "payload": {"addressed": True}}).addressed
    assert not to_event(state, "message", {"id": 2, "payload": {"addressed": False}}).addressed
    assert not to_event(state, "command", {"id": 3, "payload": {"addressed": True}}).addressed


async def test_pongs_pings_with_cursor_and_advances_only_after_handling():
    pongs: list[dict] = []

    async def server(ws):
        await ws.send(json.dumps({"event": "connection_state", "data": {"generation": 1, "rooms": ["r"], "cursor": 0}}))
        await ws.send(json.dumps({"event": "message", "data": {"id": 1, "room_id": "r", "payload": {"addressed": True, "body": "hi"}}}))
        await ws.send(json.dumps({"event": "ping", "data": {}}))
        pongs.append(json.loads(await ws.recv()))
        await asyncio.sleep(0.2)
        await ws.send(json.dumps({"event": "ping", "data": {}}))
        pongs.append(json.loads(await ws.recv()))
        await asyncio.sleep(5)

    async with websockets.serve(server, "127.0.0.1", 0) as srv:
        port = srv.sockets[0].getsockname()[1]
        conn = RoomConnection(AgentCreds(f"http://127.0.0.1:{port}", "a", "envoy", "k"), "r", "c-1")
        runner = asyncio.create_task(conn.run())
        await conn.wait_ready()
        events = conn.events()
        first = await anext(events)
        assert first.payload["body"] == "hi"
        await asyncio.sleep(0.05)
        # Received but the consumer hasn't asked for the next one: not yet handled.
        assert pongs[0] == {"type": "pong", "cursor": 0}
        pending = asyncio.create_task(anext(events))
        await asyncio.sleep(0.4)
        assert pongs[1] == {"type": "pong", "cursor": 1}
        pending.cancel()
        runner.cancel()
