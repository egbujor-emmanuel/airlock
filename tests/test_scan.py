import base64

import pytest

from airlock.scan.detectors import luhn_ok, normalise, shannon_entropy
from airlock.scan.redact import digest, findings_in, redact

# Format-valid fakes assembled at runtime, so no scanner (ours or GitHub's
# push protection) sees a literal key in the source.
AWS = "AKIA" + "Z7Q2" * 4
STRIPE = "sk_" + "live_" + "4eC39HqLyjWDarjtT1zdp7dc"
WHSEC = "whsec_" + "MfKQ9r8GKYqrTwjUPD8ILPZIo2LaLaSw"
GH = "ghp_" + "a1B2c3D4e5F6g7H8i9J0k1L2m3N4o5P6q7R8"
JWT = "eyJhbGciOiJIUzI1NiJ9" + "." + "eyJzdWIiOiJ1c2VyLTQyIn0" + "." + "dBjftJeZ4CVPmB92K27uhbUJU1p1r_wW1gFWFOEjXk"
CANARY = "AKIA" + "CANARY" + "0000" + "XYZ7"

LEAKS = {
    "aws key": f"the failing request used {AWS} as the key",
    "stripe key": f"STRIPE_SECRET={STRIPE}",
    "webhook secret": f"endpoint secret is {WHSEC}",
    "github token": f"token {GH}",
    "jwt": f"Authorization header carried {JWT}",
    "bearer": "Authorization: Bearer abcDEF123456ghiJKL789mnoPQR",
    "email": "customer jane.doe@acme-customer.com saw the error",
    "phone": "call the merchant on +44 20 7946 0958",
    "card": "card 4242 4242 4242 4242 was charged twice",
    "private ip": "the webhook came from 10.4.22.17",
    "internal host": "logs are on payments-db.acme.internal",
    "url credentials": "DATABASE_URL=postgres://app:hunter2pass@db.example.com/prod",
    "assigned password": "password = 'Tr0ub4dor&3'",
    "private key": "-----BEGIN RSA PRIVATE KEY-----\nMIIEpAIBAAKCAQEA\n-----END RSA PRIVATE KEY-----",
    "base64 hidden key": "config blob: " + base64.b64encode(f"key={AWS}".encode()).decode(),
    "hex hidden key": "dump " + f"token={STRIPE}".encode().hex(),
    "full-width key": "key " + "".join(chr(ord(c) + 0xFEE0) if c.isalnum() else c for c in AWS),
    "zero-width split key": "key " + AWS[:6] + "​" + AWS[6:],
    "canary": f"leaked {CANARY} here",
}

BENIGN = [
    "The webhook handler returns 400 because the body was parsed as JSON before verification.",
    "Use express.raw({ type: 'application/json' }) on the /webhook route only.",
    "Signature header format is t=1730650000,v1=<hex digest>; tolerance is 300 seconds.",
    "content_type=application/json body_bytes=1832 signature_header_present=true",
    "The test suite has 14 passing tests and 2 failing in test_webhook_signature.py.",
    "Stack trace points at constructEvent in src/webhooks/verify.ts line 88.",
    "Upgrade the SDK from 4.2.0 to 4.3.1 and redeploy.",
    "requestId 7f3e9a2b handled in 182 ms on node v20.11.1",
    "See https://docs.stripe.com/webhooks/signature for the raw body requirement.",
    "def verify_signature(payload: bytes, header: str, secret: str) -> bool:",
]


@pytest.mark.parametrize("label", sorted(LEAKS))
def test_every_leak_is_caught(label):
    result = redact(LEAKS[label], canaries=(CANARY,))

    assert not result.clean, f"{label} got through: {result.text}"


@pytest.mark.parametrize("label", sorted(LEAKS))
def test_redacted_text_no_longer_contains_the_value(label):
    result = redact(LEAKS[label], canaries=(CANARY,))

    for value in (AWS, STRIPE, WHSEC, GH, JWT, CANARY, "jane.doe@acme-customer.com", "hunter2pass"):
        assert value not in result.text


@pytest.mark.parametrize("text", BENIGN)
def test_ordinary_debugging_talk_passes_untouched(text):
    result = redact(text)

    assert result.clean, f"false positive: {[r.kind for r in result.redactions]} in {text!r}"
    assert result.text == text


def test_redaction_keeps_a_digest_not_the_value():
    result = redact(f"key {AWS}")

    (r,) = result.redactions
    assert r.digest == digest(AWS)
    assert AWS not in repr(result)


def test_hidden_values_record_how_they_were_hidden():
    result = redact(LEAKS["base64 hidden key"])

    assert result.redactions[0].via == "base64"


def test_canary_outranks_the_secret_it_resembles():
    (finding,) = findings_in(f"x {CANARY} y", canaries=(CANARY,))

    assert finding.kind == "canary"


def test_placeholders_are_numbered_in_order():
    result = redact(f"{AWS} and jane@acme-customer.com")

    assert result.text == "[REDACTED:aws_access_key#1] and [REDACTED:email#2]"


def test_luhn():
    assert luhn_ok("4242424242424242")
    assert not luhn_ok("4242424242424241")


def test_entropy_separates_keys_from_words():
    assert shannon_entropy("4eC39HqLyjWDarjtT1zdp7dc") > 4.0
    assert shannon_entropy("aaaaaaaaaaaaaaaaaaaaaaaa") < 1.0


def test_normalise_folds_full_width_and_strips_zero_width():
    assert normalise("ＡＫＩＡ​1") == "AKIA1"
