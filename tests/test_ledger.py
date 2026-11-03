import json

import pytest

from airlock.ledger.chain import GENESIS, Ledger, entry_hash, verify_chain
from airlock.ledger.signing import generate, load_or_create, verify


@pytest.fixture(scope="module")
def acme():
    return generate("acme")


@pytest.fixture(scope="module")
def payco():
    return generate("payco")


def test_ml_dsa_signature_round_trip(acme):
    sig = acme.sign(b"disclosure")

    assert verify(acme.public_key, b"disclosure", sig)
    assert not verify(acme.public_key, b"disclosure!", sig)


def test_chain_links_and_verifies(tmp_path, acme):
    ledger = Ledger(tmp_path / "acme.jsonl", acme)
    first = ledger.append({"type": "egress", "crossing": "x1", "digest": "aa"})
    second = ledger.append({"type": "posted", "crossing": "x1"})

    assert first["prev_hash"] == GENESIS
    assert second["prev_hash"] == entry_hash(first)
    result = verify_chain(ledger.entries(), {"acme": acme.public_key})
    assert result.ok and result.entries == 2


def test_tampering_with_an_entry_is_detected(tmp_path, acme):
    ledger = Ledger(tmp_path / "acme.jsonl", acme)
    ledger.append({"type": "egress", "approver": "yoma"})
    ledger.append({"type": "posted"})
    lines = ledger.path.read_text(encoding="utf-8").splitlines()
    forged = json.loads(lines[0]) | {"approver": "someone-else"}
    ledger.path.write_text(json.dumps(forged) + "\n" + lines[1] + "\n", encoding="utf-8")

    result = verify_chain(ledger.entries(), {"acme": acme.public_key})

    assert not result.ok
    assert any("does not verify" in p for p in result.problems)
    assert any("does not link" in p for p in result.problems)


def test_deleting_an_entry_breaks_the_chain(tmp_path, acme):
    ledger = Ledger(tmp_path / "acme.jsonl", acme)
    for n in range(3):
        ledger.append({"type": "egress", "n": n})
    entries = ledger.entries()

    result = verify_chain([entries[0], entries[2]], {"acme": acme.public_key})

    assert not result.ok


def test_a_receipt_signed_by_the_other_org_verifies_with_its_key(tmp_path, acme, payco):
    sent = Ledger(tmp_path / "acme.jsonl", acme).append({"type": "egress", "crossing": "x1"})
    receipts = Ledger(tmp_path / "payco.jsonl", payco)
    receipts.append({"type": "receipt", "crossing": "x1", "of": entry_hash(sent), "from": "acme"})

    keys = {"acme": acme.public_key, "payco": payco.public_key}
    assert verify_chain(receipts.entries(), keys).ok
    assert not verify_chain(receipts.entries(), {"payco": acme.public_key}).ok


def test_signing_key_persists_and_reloads(tmp_path):
    path = tmp_path / "keys" / "acme.json"
    first = load_or_create(path, "acme")
    again = load_or_create(path, "acme")

    assert first.public_key == again.public_key
    assert verify(again.public_key, b"m", first.sign(b"m"))
