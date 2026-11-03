"""HTTP half of the Switch agent protocol: registration, operations, posting.

Operations are ``POST /agents/{id}/ops/{op}`` with the arguments unwrapped in
the body. The server validates arguments by signature inspection, so a key it
does not expect is a 400 even when the published schema would allow it: callers
pass only the arguments an operation declares.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import httpx

from airlock.switch.creds import AgentCreds, load_creds, save_creds

CONNECTION_HEADER = "X-Switch-Connection-Id"
REQUEST_TIMEOUT_S = 30.0

# How Switch reports this agent's liveness. Envoy holds a socket per room for
# as long as it runs, so it is reachable whenever it is up.
ENVOY_INTEGRATION_PROFILE: dict[str, Any] = {
    "connection_model": "always_on",
    "message_exchange": True,
    "pre_invocation_mediation": [],
    "post_invocation_mediation": [],
    "event_reporting": [],
}


class SwitchError(RuntimeError):
    def __init__(self, status: int, detail: str, op: str) -> None:
        super().__init__(f"{op} failed with {status}: {detail}")
        self.status = status
        self.detail = detail
        self.op = op


def _raise_for(resp: httpx.Response, op: str) -> None:
    if resp.is_success:
        return
    try:
        detail = resp.json().get("detail", resp.text)
    except ValueError:
        detail = resp.text
    raise SwitchError(resp.status_code, str(detail), op)


async def register_agent(
    base_url: str,
    registration_key: str,
    *,
    name: str,
    description: str,
    display_name: str | None = None,
    connector_type: str = "airlock-envoy",
) -> AgentCreds:
    body = {
        "name": name,
        "description": description,
        "display_name": display_name,
        "connector_type": connector_type,
        "integration_profile": ENVOY_INTEGRATION_PROFILE,
    }
    async with httpx.AsyncClient(base_url=base_url, timeout=REQUEST_TIMEOUT_S) as http:
        resp = await http.post(
            "/agents", json=body, headers={"Authorization": f"Bearer {registration_key}"}
        )
    _raise_for(resp, "register")
    data = resp.json()
    return AgentCreds(base_url=base_url, agent_id=data["id"], name=name, api_key=data["api_key"])


async def ensure_registered(
    creds_path: Path,
    base_url: str,
    registration_key: str,
    *,
    name: str,
    description: str,
    display_name: str | None = None,
) -> AgentCreds:
    """Return stored credentials, registering the agent only the first time."""
    existing = load_creds(creds_path)
    if existing is not None:
        return existing
    creds = await register_agent(
        base_url, registration_key, name=name, description=description, display_name=display_name
    )
    save_creds(creds_path, creds)
    return creds


class AgentHttp:
    """Authenticated calls an agent makes. One instance per agent."""

    def __init__(self, creds: AgentCreds, client: httpx.AsyncClient | None = None) -> None:
        self.creds = creds
        self._http = client or httpx.AsyncClient(
            base_url=creds.base_url,
            timeout=REQUEST_TIMEOUT_S,
            headers={"Authorization": f"Bearer {creds.api_key}"},
        )

    async def aclose(self) -> None:
        await self._http.aclose()

    async def op(self, operation: str, /, *, connection_id: str | None = None, **args: Any) -> Any:
        # Positional-only: operations take arguments such as `name` themselves.
        headers = {CONNECTION_HEADER: connection_id} if connection_id else {}
        resp = await self._http.post(
            f"/agents/{self.creds.agent_id}/ops/{operation}", json=args, headers=headers
        )
        _raise_for(resp, operation)
        return resp.json().get("result")

    async def list_ops(self) -> dict[str, Any]:
        resp = await self._http.get(f"/agents/{self.creds.agent_id}/ops")
        _raise_for(resp, "list_ops")
        return resp.json()["operations"]

    async def send_message(self, room_id: str, content: str) -> str:
        """Post to a room without a connection (the route needs none)."""
        resp = await self._http.post(
            f"/agents/{self.creds.agent_id}/message",
            json={"room_id": room_id, "content": content},
        )
        _raise_for(resp, "send_message")
        return str(resp.json().get("event_id", ""))
