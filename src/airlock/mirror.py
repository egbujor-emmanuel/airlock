"""Airlock Mirror's API: both ledgers, folded into crossings, verified, streamed.

    uv run airlock-mirror            # http://127.0.0.1:8787 (serves mirror/dist if built)

Reads the envoys' ledgers from .airlock/ledger (or `--evidence docs/evidence/run-3`
for a recorded run) and serves:

    GET /api/state    the full picture: crossings, ledger entries, verification
    GET /api/events   server-sent events: a fresh state whenever a ledger changes

Everything it shows is already in the ledgers, which hold digests and redacted
text only, never an original secret.
"""

from __future__ import annotations

import argparse
import base64
import json
import threading
import time
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

from airlock.ledger.chain import GENESIS, canonical, entry_hash
from airlock.ledger.signing import load_or_create, verify

ROOT = Path.cwd()
POLL_S = 0.5
ORGS = ("acme", "payco")
DISPLAY = {"acme": "Acme", "payco": "PayCo"}


class Source:
    """Where ledgers and public keys come from: this machine's envoys, or an export."""

    def __init__(self, evidence: Path | None) -> None:
        self.evidence = evidence

    def ledger_path(self, org: str) -> Path:
        return (self.evidence / f"{org}.jsonl") if self.evidence else ROOT / ".airlock" / "ledger" / f"{org}.jsonl"

    def public_key(self, org: str) -> bytes | None:
        if self.evidence:
            pub = self.evidence / f"{org}.pub"
            return base64.b64decode(pub.read_text(encoding="utf-8").strip()) if pub.exists() else None
        key_file = ROOT / ".airlock" / "keys" / f"{org}.json"
        return load_or_create(key_file, org).public_key if key_file.exists() else None

    def read(self, org: str) -> list[dict[str, Any]] | None:
        path = self.ledger_path(org)
        if not path.exists():
            return None
        lines = path.read_text(encoding="utf-8").splitlines()
        return [json.loads(line) for line in lines if line.strip()]

    def fingerprint(self) -> tuple:
        out = []
        for org in ORGS:
            p = self.ledger_path(org)
            out.append((p.stat().st_mtime_ns, p.stat().st_size) if p.exists() else None)
        return tuple(out)


_VERIFY_LOCK = threading.Lock()
_VERIFIED: set[tuple[bytes, bytes, str]] = set()


def _signature_ok(public_key: bytes, unsigned: bytes, signature_b64: str) -> bool:
    """ML-DSA verification, one at a time.

    Every browser connection is a thread, and the pure-Python ML-DSA library is not
    safe to call concurrently: overlapping verifications returned spurious failures.
    Only successes are cached, so a failure is always recomputed.
    """
    key = (public_key, unsigned, signature_b64)
    if key in _VERIFIED:
        return True
    with _VERIFY_LOCK:
        try:
            ok = verify(public_key, unsigned, base64.b64decode(signature_b64))
        except ValueError:
            ok = False
    if ok:
        _VERIFIED.add(key)
    return ok


def annotate(org: str, entries: list[dict[str, Any]], public_key: bytes | None) -> list[dict[str, Any]]:
    """Each entry with its hash, whether it links to the one before, and its signature check."""
    out, prev = [], GENESIS
    for e in entries:
        unsigned = canonical({k: v for k, v in e.items() if k != "sig"})
        sig_ok = bool(public_key) and _signature_ok(public_key, unsigned, str(e.get("sig", "")))
        h = entry_hash(e)
        out.append({**e, "org": org, "hash": h, "linked": e.get("prev_hash") == prev, "signature_ok": sig_ok})
        prev = h
    return out


def fold_crossings(ledgers: dict[str, list[dict[str, Any]]]) -> list[dict[str, Any]]:
    """One record per crossing: proposal, decision, and the other side's receipt."""
    receipts = {}
    for org, entries in ledgers.items():
        for e in entries:
            if e["type"] == "receipt":
                receipts[(e["from"], e["crossing"])] = {"by": org, "hash": e["hash"], "at": e.get("at"), "of": e["of"]}
    crossings: dict[tuple[str, str], dict[str, Any]] = {}
    for org, entries in ledgers.items():
        for e in entries:
            cid = e.get("crossing")
            if not cid or e["type"] == "receipt":
                continue
            c = crossings.setdefault((org, cid), {"id": cid, "org": org, "status": "proposed", "events": []})
            c["events"].append({"type": e["type"], "at": e.get("at"), "hash": e["hash"]})
            if e["type"] == "proposed":
                c.update(proposed_at=e.get("at"), text=e.get("redacted_text", ""), requested_by=e.get("requested_by"),
                         redactions=e.get("redactions", []), answers=e.get("answers"))
            elif e["type"] in ("approved", "declined", "refused"):
                c["status"] = e["type"] if e["type"] != "refused" else c["status"]
                if e["type"] != "refused":
                    c.update(decided_at=e.get("at"), decided_by=e.get("by"), entry=e["hash"])
            c["signed"] = all(x["signature_ok"] for x in entries if x.get("crossing") == cid)
    for (org, cid), c in crossings.items():
        r = receipts.get((org, cid))
        if r and c.get("entry", "").startswith(r["of"]):
            c["receipt"] = r
        c["is_query"] = "❓ Query" in c.get("text", "")
    return sorted(crossings.values(), key=lambda c: c.get("proposed_at") or 0)


def snapshot(source: Source) -> dict[str, Any]:
    ledgers, missing = {}, []
    for org in ORGS:
        entries = source.read(org)
        if entries is None:
            missing.append(org)
            continue
        ledgers[org] = annotate(org, entries, source.public_key(org))
    entries = sorted((e for es in ledgers.values() for e in es), key=lambda e: e.get("at") or 0)
    verification = {
        org: {
            "entries": len(es),
            "chain_ok": all(e["linked"] for e in es),
            "signatures_ok": all(e["signature_ok"] for e in es),
        }
        for org, es in ledgers.items()
    }
    breaches = [e for e in entries if e["type"] == "breach"]
    return {
        "generated_at": time.time(),
        "source": str(source.evidence) if source.evidence else "live",
        "orgs": {org: DISPLAY[org] for org in ORGS},
        "missing": missing,
        "verification": verification,
        "crossings": fold_crossings(ledgers),
        "entries": entries[-200:],
        "breaches": breaches,
        "counts": {
            "ingress": sum(1 for e in entries if e["type"] == "ingress"),
            "redactions": sum(len(e.get("redactions") or []) for e in entries if e["type"] == "proposed"),
            "blocked": sum(1 for e in entries if e["type"] in ("blocked", "rejected")),
        },
    }


def make_handler(source: Source, static_dir: Path):
    class Handler(SimpleHTTPRequestHandler):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, directory=str(static_dir), **kwargs)

        def log_message(self, fmt, *args):  # quiet
            pass

        def _json(self, payload: dict) -> None:
            body = json.dumps(payload).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self):  # noqa: N802 - http.server API
            if self.path.startswith("/api/state"):
                return self._json(snapshot(source))
            if self.path.startswith("/api/events"):
                return self._stream()
            if not (static_dir / self.path.lstrip("/").split("?")[0]).exists():
                self.path = "/index.html"  # single-page app
            return super().do_GET()

        def _stream(self) -> None:
            self.send_response(200)
            self.send_header("Content-Type", "text/event-stream")
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            last = None
            try:
                while True:
                    fp = source.fingerprint()
                    if fp != last:
                        data = json.dumps(snapshot(source))
                        self.wfile.write(f"data: {data}\n\n".encode("utf-8"))
                        self.wfile.flush()
                        last = fp
                    else:
                        self.wfile.write(b": keep-alive\n\n")
                        self.wfile.flush()
                    time.sleep(POLL_S)
            except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError):
                return

    return Handler


def main() -> None:
    parser = argparse.ArgumentParser(description="Airlock Mirror")
    parser.add_argument("--port", type=int, default=8787)
    parser.add_argument("--evidence", help="replay an exported run instead of the live ledgers")
    args = parser.parse_args()
    source = Source(Path(args.evidence) if args.evidence else None)
    static_dir = ROOT / "mirror" / "dist"
    static_dir.mkdir(parents=True, exist_ok=True)
    server = ThreadingHTTPServer(("127.0.0.1", args.port), make_handler(source, static_dir))
    threading.Thread(target=server.serve_forever, daemon=True).start()
    print(f"Airlock Mirror on http://127.0.0.1:{args.port} ({'evidence ' + args.evidence if args.evidence else 'live ledgers'})")
    try:
        threading.Event().wait()
    except KeyboardInterrupt:
        server.shutdown()


if __name__ == "__main__":
    main()
