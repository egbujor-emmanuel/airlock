"""Redaction: replace every finding with a numbered placeholder.

The original value never leaves this process. What the ledger keeps is a
SHA3-256 digest of it, so both sides can later prove what was withheld without
anyone being able to recover it.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass

from airlock.scan.detectors import Finding, normalise, scan


@dataclass(frozen=True)
class Redaction:
    placeholder: str
    kind: str
    category: str
    via: str
    digest: str  # sha3-256 of the withheld value


@dataclass(frozen=True)
class RedactedText:
    text: str
    redactions: tuple[Redaction, ...]

    @property
    def clean(self) -> bool:
        return not self.redactions


def digest(value: str) -> str:
    return hashlib.sha3_256(value.encode("utf-8")).hexdigest()


def redact(text: str, canaries: tuple[str, ...] = ()) -> RedactedText:
    normal = normalise(text)
    findings = scan(normal, canaries)
    out: list[str] = []
    redactions: list[Redaction] = []
    cursor = 0
    for n, f in enumerate(findings, start=1):
        placeholder = f"[REDACTED:{f.kind}#{n}]"
        out.append(normal[cursor : f.start])
        out.append(placeholder)
        redactions.append(
            Redaction(placeholder, f.kind, f.category.value, f.via, digest(normal[f.start : f.end]))
        )
        cursor = f.end
    out.append(normal[cursor:])
    return RedactedText("".join(out), tuple(redactions))


def findings_in(text: str, canaries: tuple[str, ...] = ()) -> list[Finding]:
    return scan(normalise(text), canaries)
