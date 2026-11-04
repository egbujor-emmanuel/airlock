import json

import httpx
import pytest

from airlock.policy import load_policy
from airlock.switch.creds import AgentCreds, load_creds, save_creds
from airlock.switch.http import AgentHttp, SwitchError, ensure_registered, register_agent

CREDS = AgentCreds("http://switch.test", "agent-1", "envoy-acme", "key-1")


def client_for(handler) -> AgentHttp:
    transport = httpx.MockTransport(handler)
    http = httpx.AsyncClient(base_url=CREDS.base_url, transport=transport,
                             headers={"Authorization": f"Bearer {CREDS.api_key}"})
    return AgentHttp(CREDS, http)


async def test_operations_send_arguments_unwrapped_with_the_connection_header():
    seen = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["path"] = request.url.path
        seen["conn"] = request.headers.get("X-Switch-Connection-Id")
        seen["auth"] = request.headers.get("Authorization")
        seen["body"] = json.loads(request.content)
        return httpx.Response(200, json={"result": {"ok": True}})

    result = await client_for(handler).op("create_room", connection_id="c-1", name="acme-x-payco")

    assert result == {"ok": True}
    assert seen == {"path": "/agents/agent-1/ops/create_room", "conn": "c-1",
                    "auth": "Bearer key-1", "body": {"name": "acme-x-payco"}}


async def test_a_refused_operation_raises_with_the_servers_reason():
    def handler(request):
        return httpx.Response(403, json={"detail": "An agent can't change its own settings"})

    with pytest.raises(SwitchError) as err:
        await client_for(handler).op("update_agent_detail", agent_id="agent-1", addressing="anyone")

    assert err.value.status == 403 and "own settings" in str(err.value)


async def test_send_message_needs_no_connection():
    def handler(request):
        assert request.url.path == "/agents/agent-1/message"
        assert json.loads(request.content) == {"room_id": "r", "content": "hi"}
        return httpx.Response(200, json={"ok": True, "event_id": "sw_1"})

    assert await client_for(handler).send_message("r", "hi") == "sw_1"


async def test_list_ops():
    def handler(request):
        return httpx.Response(200, json={"operations": {"post_message": {"description": "Send"}}})

    assert "post_message" in await client_for(handler).list_ops()


async def test_register_once_then_reuse_stored_credentials(tmp_path, monkeypatch):
    calls = []

    async def fake_register(base_url, key, **kwargs):
        calls.append(kwargs["name"])
        return AgentCreds(base_url, "new-id", kwargs["name"], "issued-once")

    monkeypatch.setattr("airlock.switch.http.register_agent", fake_register)
    path = tmp_path / "envoy.json"

    first = await ensure_registered(path, "http://s", "reg", name="envoy-acme", description="d")
    again = await ensure_registered(path, "http://s", "reg", name="envoy-acme", description="d")

    assert calls == ["envoy-acme"]
    assert first == again == load_creds(path)


async def test_register_agent_posts_the_integration_profile(monkeypatch):
    seen = {}

    def handler(request):
        seen["auth"] = request.headers["Authorization"]
        seen["body"] = json.loads(request.content)
        return httpx.Response(200, json={"id": "a-9", "api_key": "k-9"})

    real_client = httpx.AsyncClient
    monkeypatch.setattr(httpx, "AsyncClient",
                        lambda **kw: real_client(transport=httpx.MockTransport(handler), **kw))

    creds = await register_agent("http://s", "reg-key", name="envoy-acme", description="d")

    assert creds == AgentCreds("http://s", "a-9", "envoy-acme", "k-9")
    assert seen["auth"] == "Bearer reg-key"
    assert seen["body"]["integration_profile"]["connection_model"] == "always_on"


def test_creds_round_trip(tmp_path):
    path = tmp_path / "a" / "creds.json"
    save_creds(path, CREDS)

    assert load_creds(path) == CREDS
    assert load_creds(tmp_path / "missing.json") is None


def test_policy_loads_and_matches_approvers_case_insensitively(tmp_path):
    path = tmp_path / "acme.yaml"
    path.write_text("org: acme\nother_org: payco\napprovers: ['@DeFi_Maroh']\ninside_agent: claude-acme\n")

    policy = load_policy(path, ("CANARY",))

    assert policy.may_approve("defi_maroh") and not policy.may_approve("someone")
    assert policy.inside_agent == "claude-acme" and policy.canaries == ("CANARY",)
