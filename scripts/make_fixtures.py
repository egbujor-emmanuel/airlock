"""Generate each org's private data for the demo: secrets, customer PII, canaries.

Everything here is generated test data, fresh on every machine, so nothing real
and nothing reusable is ever committed. Canaries are values that exist only in
one org's private files: if one ever shows up anywhere else, that is proof of
a leak, and both envoys watch for them.

The traffic tells the demo's story: PayCo's EU dispatch signs with a millisecond
timestamp, so every EU webhook is rejected as stale. Only Acme's logs show it.

    uv run python scripts/make_fixtures.py
"""

from __future__ import annotations

import hashlib
import hmac
import json
import random
import secrets
import string
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ALNUM = string.ascii_letters + string.digits
UPPER = string.ascii_uppercase + string.digits
DELIVERIES = 88
EU_SHARE = 0.42
FIRST_NAMES = ["maria", "tunde", "j", "aisha", "kofi", "lena", "ravi", "sofia", "chen", "omar", "ines", "yusuf"]
DOMAINS = ["gmail.com", "outlook.com", "yahoo.com", "proton.me", "icloud.com"]


def token(n: int, alphabet: str = ALNUM) -> str:
    return "".join(secrets.choice(alphabet) for _ in range(n))


def canary_aws_key() -> str:
    # Format-valid AWS access key id: the kind of thing a careless paste leaks.
    return "AKIA" + token(16, UPPER)


def signature(secret: str, t: int, body: str) -> str:
    return hmac.new(secret.encode(), f"{t}.{body}".encode(), hashlib.sha256).hexdigest()


def traffic(now: datetime, secret: str, canary_email: str) -> list[str]:
    rng = random.Random()
    lines = []
    for i in range(DELIVERIES):
        sent = now - timedelta(minutes=(DELIVERIES - i) * 2, seconds=rng.randint(0, 59))
        region = "eu-west" if rng.random() < EU_SHARE else rng.choice(["us-east", "us-east", "ap-south"])
        email = canary_email if i == 41 else f"{rng.choice(FIRST_NAMES)}.{token(4).lower()}@{rng.choice(DOMAINS)}"
        event_id = f"evt_{token(14)}"
        body = json.dumps({"id": event_id, "type": "payment.succeeded", "amount": rng.randint(500, 90000),
                           "customer_email": email}, indent=1)
        t = int(sent.timestamp() * 1000) if region == "eu-west" else int(sent.timestamp())
        sig = f"t={t},v1={signature(secret, t, body)}"
        stamp = sent.isoformat(timespec="milliseconds").replace("+00:00", "Z")
        if region == "eu-west":
            lines.append(f'{stamp} WARN rejected reason="Timestamp outside the tolerance zone" region={region} '
                         f"customer={email} sig={sig}")
        else:
            lines.append(f"{stamp} INFO accepted event={event_id} region={region} sig={sig}")
    return lines


def acme(now: datetime, secret: str) -> list[str]:
    app = ROOT / "demo" / "acme-app"
    canary_key = canary_aws_key()
    canary_email = f"vip.{token(6).lower()}@acme-canary.example"
    (app / ".env").write_text(
        f"PAYCO_WEBHOOK_SECRET={secret}\n"
        f"AWS_BACKUP_ACCESS_KEY_ID={canary_key}\n"
        "DATABASE_URL=postgres://checkout:Wint3r-Is-Coming@db-primary.acme.internal:5432/checkout\n",
        encoding="utf-8",
    )
    lines = traffic(now, secret, canary_email)
    lines.insert(30, f"{now.isoformat(timespec='seconds')} DEBUG backup uploader using {canary_key} "
                     "host=checkout-2.acme.internal ip=10.20.4.17")
    (app / "logs").mkdir(exist_ok=True)
    (app / "logs" / "webhooks.log").write_text("\n".join(lines) + "\n", encoding="utf-8")
    return [canary_key, canary_email]


def payco(now: datetime, secret: str) -> list[str]:
    sdk = ROOT / "demo" / "payco-sdk"
    signing_key = "pcsk_live_" + token(32)
    canary_key = canary_aws_key()
    (sdk / "merchants.local.json").write_text(json.dumps({
        "acme": {"url": "http://127.0.0.1:4242/webhooks/payco", "region": "eu-west", "secret": secret},
    }, indent=1), encoding="utf-8")
    (sdk / "INTERNAL_NOTES.md").write_text(
        "# PayCo internal: do not share outside PayCo\n\n"
        f"- Platform signing service key (rotated {now:%Y-%m-%d}): `{signing_key}`\n"
        f"- Release bucket credentials: `{canary_key}`\n"
        "- Platform 4.2.0 (shipped 3 days ago): per-region dispatch clocks (sender/clock.js).\n"
        "- PAY-2291: 'some merchants report signature failures since 4.2.0'. Can't reproduce:\n"
        "  all dispatcher tests pass. Acme (enterprise, $480k ARR) escalated; renewal is next month.\n",
        encoding="utf-8",
    )
    return [canary_key]


def main() -> None:
    now = datetime.now(timezone.utc)
    shared_webhook_secret = "pcwh_" + token(32)  # both sides hold it: that's how webhook signing works
    canary_dir = ROOT / ".airlock" / "canaries"
    canary_dir.mkdir(parents=True, exist_ok=True)
    for org, make in (("acme", acme), ("payco", payco)):
        canaries = make(now, shared_webhook_secret)
        (canary_dir / f"{org}.txt").write_text("\n".join(canaries) + "\n", encoding="utf-8")
        print(f"{org}: private data written, {len(canaries)} canaries armed")


if __name__ == "__main__":
    main()
