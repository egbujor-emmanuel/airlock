"""Generate each org's private data for the demo: secrets, customer PII, canaries.

Everything here is generated test data, fresh on every machine, so nothing real
and nothing reusable is ever committed. Canaries are values that exist only in
one org's private files: if one ever shows up anywhere else, that is proof of
a leak, and both envoys watch for them.

    uv run python scripts/make_fixtures.py
"""

from __future__ import annotations

import secrets
import string
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ALNUM = string.ascii_letters + string.digits
UPPER = string.ascii_uppercase + string.digits


def token(n: int, alphabet: str = ALNUM) -> str:
    return "".join(secrets.choice(alphabet) for _ in range(n))


def canary_aws_key() -> str:
    # Format-valid AWS access key id: the kind of thing a careless paste leaks.
    return "AKIA" + token(16, UPPER)


def acme(now: datetime) -> list[str]:
    app = ROOT / "demo" / "acme-app"
    webhook_secret = "pcwh_" + token(32)
    canary_key = canary_aws_key()
    canary_email = f"vip.{token(6).lower()}@acme-canary.example"
    customers = ["maria.okafor@gmail.com", "j.chen@outlook.com", canary_email, "tunde.adeyemi@yahoo.com"]
    (app / ".env").write_text(
        f"PAYCO_WEBHOOK_SECRET={webhook_secret}\n"
        f"AWS_BACKUP_ACCESS_KEY_ID={canary_key}\n"
        "DATABASE_URL=postgres://checkout:Wint3r-Is-Coming@db-primary.acme.internal:5432/checkout\n",
        encoding="utf-8",
    )
    lines = []
    for i, email in enumerate(customers):
        t = (now - timedelta(minutes=37 - i * 9)).isoformat(timespec="seconds")
        sig = f"t={int(now.timestamp()) - 2220 + i * 540},v1={secrets.token_hex(32)}"
        lines.append(
            f"{t} WARN webhook rejected: No signatures found matching the expected signature for payload "
            f"customer={email} sig={sig} host=checkout-2.acme.internal ip=10.20.4.{11 + i}"
        )
    lines.append(f"{now.isoformat(timespec='seconds')} DEBUG verify(req.body={{object}}, secret={webhook_secret})")
    lines.append(f"{now.isoformat(timespec='seconds')} DEBUG backup uploader using {canary_key}")
    (app / "logs").mkdir(exist_ok=True)
    (app / "logs" / "webhooks.log").write_text("\n".join(lines) + "\n", encoding="utf-8")
    return [canary_key, canary_email]


def payco(now: datetime) -> list[str]:
    sdk = ROOT / "demo" / "payco-sdk"
    signing_key = "pcsk_live_" + token(32)
    canary_key = canary_aws_key()
    (sdk / "INTERNAL_NOTES.md").write_text(
        "# PayCo internal: do not share outside PayCo\n\n"
        f"- Production signing key (rotated {now:%Y-%m-%d}): `{signing_key}`\n"
        f"- Release bucket credentials: `{canary_key}`\n"
        "- Known issue PAY-2291: some merchants report signature failures after upgrading to 4.2.0.\n"
        "  Suspect body handling in verify(). Acme is one of them (enterprise, $480k ARR).\n",
        encoding="utf-8",
    )
    return [canary_key]


def main() -> None:
    now = datetime.now(timezone.utc)
    canary_dir = ROOT / ".airlock" / "canaries"
    canary_dir.mkdir(parents=True, exist_ok=True)
    for org, make in (("acme", acme), ("payco", payco)):
        canaries = make(now)
        (canary_dir / f"{org}.txt").write_text("\n".join(canaries) + "\n", encoding="utf-8")
        print(f"{org}: private data written, {len(canaries)} canaries armed")


if __name__ == "__main__":
    main()
