"""Per-org policy: who may approve a crossing, and what the envoy relays to."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import yaml


@dataclass(frozen=True)
class OrgPolicy:
    org: str
    display_name: str
    other_org: str
    approvers: frozenset[str]
    inside_agent: str | None = None
    max_code_lines: int = 25
    canaries: tuple[str, ...] = field(default_factory=tuple)

    def may_approve(self, sender_name: str) -> bool:
        return sender_name.lstrip("@").casefold() in {a.casefold() for a in self.approvers}


def load_policy(path: Path, canaries: tuple[str, ...] = ()) -> OrgPolicy:
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    return OrgPolicy(
        org=data["org"],
        display_name=data.get("display_name", data["org"].title()),
        other_org=data["other_org"],
        approvers=frozenset(str(a).lstrip("@") for a in data.get("approvers", [])),
        inside_agent=data.get("inside_agent"),
        max_code_lines=int(data.get("max_code_lines", 25)),
        canaries=canaries,
    )
