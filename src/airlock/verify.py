"""Check a disclosure ledger: order, hash links, every ML-DSA-65 signature, and receipts.

    uv run airlock-verify docs/evidence/run-3        # a folder of exported ledgers
    uv run airlock-verify                            # this machine's live ledgers

A folder holds `<org>.jsonl` (the ledger) and `<org>.pub` (that org's public key,
base64). Receipts are matched against the other org's ledger: every crossing one
side says it sent must have been received and countersigned by the other.
"""

from __future__ import annotations

import argparse
import base64
import json
import sys
from pathlib import Path

from airlock.ledger.chain import entry_hash, verify_chain
from airlock.ledger.signing import load_or_create


def load_folder(folder: Path) -> tuple[dict[str, list[dict]], dict[str, bytes]]:
    ledgers, keys = {}, {}
    for path in sorted(folder.glob("*.jsonl")):
        org = path.stem
        ledgers[org] = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
        keys[org] = base64.b64decode((folder / f"{org}.pub").read_text(encoding="utf-8").strip())
    return ledgers, keys


def load_live(root: Path) -> tuple[dict[str, list[dict]], dict[str, bytes]]:
    ledgers, keys = {}, {}
    for path in sorted((root / ".airlock" / "ledger").glob("*.jsonl")):
        org = path.stem
        ledgers[org] = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
        keys[org] = load_or_create(root / ".airlock" / "keys" / f"{org}.json", org).public_key
    return ledgers, keys


def unreceived(ledgers: dict[str, list[dict]]) -> list[str]:
    """Approved crossings with no countersigned receipt in the other org's ledger."""
    receipts = {(e["from"], e["crossing"], e["of"]) for es in ledgers.values() for e in es if e["type"] == "receipt"}
    missing = []
    for org, entries in ledgers.items():
        for e in entries:
            if e["type"] == "approved" and (org, e["crossing"], entry_hash(e)[:16]) not in receipts:
                missing.append(f"{org} {e['crossing']}")
    return missing


def main() -> int:
    parser = argparse.ArgumentParser(description="Verify Airlock disclosure ledgers")
    parser.add_argument("folder", nargs="?", help="folder of exported <org>.jsonl + <org>.pub")
    args = parser.parse_args()
    ledgers, keys = load_folder(Path(args.folder)) if args.folder else load_live(Path.cwd())
    ok = True
    for org, entries in ledgers.items():
        result = verify_chain(entries, {org: keys[org]})
        crossings = sum(1 for e in entries if e["type"] == "approved")
        print(f"{org}: {result.entries} entries, {crossings} crossings approved, "
              f"hash chain and ML-DSA-65 signatures {'valid' if result.ok else 'INVALID'}")
        for problem in result.problems:
            print(f"  ✗ {problem}")
        ok &= result.ok
    missing = unreceived(ledgers)
    if len(ledgers) > 1:
        print(f"receipts: {'every approved crossing was countersigned by the other side' if not missing else 'missing'}")
        for m in missing:
            print(f"  ✗ no receipt for {m}")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
