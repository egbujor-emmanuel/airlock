"""ML-DSA-65 signing keys for each org's envoy (NIST FIPS 204).

Post-quantum signatures because a disclosure record is evidence: it has to hold
up for as long as the contract it was made under, and a signature that a future
quantum computer could forge is not evidence for that long.
"""

from __future__ import annotations

import base64
import json
import os
from dataclasses import dataclass
from pathlib import Path

from dilithium_py.ml_dsa import ML_DSA_65

ALGORITHM = "ML-DSA-65"


@dataclass(frozen=True)
class SigningKey:
    org: str
    public_key: bytes
    secret_key: bytes

    def sign(self, message: bytes) -> bytes:
        return ML_DSA_65.sign(self.secret_key, message)

    @property
    def public_b64(self) -> str:
        return base64.b64encode(self.public_key).decode()


def generate(org: str) -> SigningKey:
    pk, sk = ML_DSA_65.keygen()
    return SigningKey(org, pk, sk)


def verify(public_key: bytes, message: bytes, signature: bytes) -> bool:
    return bool(ML_DSA_65.verify(public_key, message, signature))


def load_or_create(path: Path, org: str) -> SigningKey:
    if path.exists():
        data = json.loads(path.read_text(encoding="utf-8"))
        return SigningKey(data["org"], base64.b64decode(data["pk"]), base64.b64decode(data["sk"]))
    key = generate(org)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(
        json.dumps({"org": org, "alg": ALGORITHM, "pk": key.public_b64, "sk": base64.b64encode(key.secret_key).decode()}),
        encoding="utf-8",
    )
    os.replace(tmp, path)
    return key
