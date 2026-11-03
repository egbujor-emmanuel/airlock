"""The disclosure ledger: an append-only, hash-chained, signed record.

Every crossing is one entry, signed by the envoy that sent it. The receiving
envoy appends a receipt that names the entry's hash and signs it too, so
neither side can later deny what was disclosed, or claim something else was.

An entry is written before the message is posted (the record precedes the act),
and its ``status`` advances by appending new entries, never by editing old ones.
"""

from __future__ import annotations

import base64
import hashlib
import json
import time
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from airlock.ledger.signing import ALGORITHM, SigningKey, verify

GENESIS = "0" * 64


def canonical(body: Mapping[str, Any]) -> bytes:
    return json.dumps(body, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def entry_hash(entry: Mapping[str, Any]) -> str:
    return hashlib.sha3_256(canonical(entry)).hexdigest()


def seal(body: Mapping[str, Any], prev_hash: str, seq: int, key: SigningKey) -> dict[str, Any]:
    unsigned = {**body, "seq": seq, "prev_hash": prev_hash, "signer": key.org, "alg": ALGORITHM}
    signature = key.sign(canonical(unsigned))
    return {**unsigned, "sig": base64.b64encode(signature).decode()}


@dataclass(frozen=True)
class VerifyResult:
    ok: bool
    entries: int
    problems: tuple[str, ...]


class Ledger:
    """One org's view of the ledger, as a JSONL file."""

    def __init__(self, path: Path, key: SigningKey) -> None:
        self.path = path
        self.key = key
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def entries(self) -> list[dict[str, Any]]:
        if not self.path.exists():
            return []
        lines = self.path.read_text(encoding="utf-8").splitlines()
        return [json.loads(line) for line in lines if line.strip()]

    def head(self) -> tuple[int, str]:
        existing = self.entries()
        if not existing:
            return 0, GENESIS
        last = existing[-1]
        return last["seq"], entry_hash(last)

    def append(self, body: Mapping[str, Any]) -> dict[str, Any]:
        seq, prev = self.head()
        entry = seal({**body, "at": body.get("at", time.time())}, prev, seq + 1, self.key)
        with self.path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(entry, ensure_ascii=False) + "\n")
        return entry


def verify_chain(entries: Iterable[Mapping[str, Any]], public_keys: Mapping[str, bytes]) -> VerifyResult:
    """Check order, links and every signature. Reports every problem, not the first."""
    problems: list[str] = []
    prev, expected_seq, count = GENESIS, 1, 0
    for entry in entries:
        count += 1
        seq = entry.get("seq")
        if seq != expected_seq:
            problems.append(f"entry {count}: seq {seq}, expected {expected_seq}")
        if entry.get("prev_hash") != prev:
            problems.append(f"seq {seq}: prev_hash does not link to the entry before it")
        problems.extend(_signature_problems(entry, public_keys))
        prev, expected_seq = entry_hash(entry), (seq or expected_seq) + 1
    return VerifyResult(not problems, count, tuple(problems))


def _signature_problems(entry: Mapping[str, Any], public_keys: Mapping[str, bytes]) -> list[str]:
    seq, signer = entry.get("seq"), entry.get("signer")
    pk = public_keys.get(str(signer))
    if pk is None:
        return [f"seq {seq}: unknown signer {signer!r}"]
    unsigned = {k: v for k, v in entry.items() if k != "sig"}
    try:
        signature = base64.b64decode(str(entry.get("sig", "")))
    except ValueError:
        return [f"seq {seq}: signature is not base64"]
    if not verify(pk, canonical(unsigned), signature):
        return [f"seq {seq}: signature by {signer} does not verify"]
    return []
