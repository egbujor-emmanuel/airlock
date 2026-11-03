"""Agent credentials, registered once and kept on disk.

Switch returns an agent's API key exactly once, at registration, and
re-registering with ``overwrite`` rotates it (the old key stops working). So a
client registers a name once and reuses the stored key on every launch.
"""

from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass
from pathlib import Path


@dataclass(frozen=True)
class AgentCreds:
    base_url: str
    agent_id: str
    name: str
    api_key: str


def load_creds(path: Path) -> AgentCreds | None:
    if not path.exists():
        return None
    data = json.loads(path.read_text(encoding="utf-8"))
    return AgentCreds(**data)


def save_creds(path: Path, creds: AgentCreds) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(asdict(creds), indent=2), encoding="utf-8")
    os.replace(tmp, path)
