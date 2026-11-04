"""Deterministic detectors for what must not cross the boundary.

No model in this path: every finding is a regex, a checksum or an entropy
measure, so the same text always gets the same verdict and the verdict can be
explained. Text is normalised before matching (NFKC folds full-width and
compatibility forms; zero-width characters are removed), and encoded payloads
(base64, hex) are decoded and scanned again, so a key does not get through by
being dressed up.
"""

from __future__ import annotations

import base64
import binascii
import codecs
import math
import re
import unicodedata
import urllib.parse
from collections.abc import Iterable, Iterator
from dataclasses import dataclass
from enum import Enum


class Category(str, Enum):
    SECRET = "secret"
    PII = "pii"
    INFRA = "infra"
    CANARY = "canary"


@dataclass(frozen=True)
class Finding:
    kind: str
    category: Category
    start: int
    end: int
    text: str
    via: str = "plain"  # "plain", "base64", "hex": how the value was hidden


ZERO_WIDTH = dict.fromkeys(map(ord, "\u200b\u200c\u200d\u2060\ufeff\u00ad"), None)


def normalise(text: str) -> str:
    """Fold look-alike forms so `ＡＫＩＡ…` and `AK\u200bIA…` match as `AKIA…`.

    NFKC can change string length, so callers redact on the normalised text.
    """
    return unicodedata.normalize("NFKC", text).translate(ZERO_WIDTH)


SECRET_PATTERNS: tuple[tuple[str, str], ...] = (
    ("private_key", r"-----BEGIN (?:[A-Z ]+ )?PRIVATE KEY-----[\s\S]*?(?:-----END (?:[A-Z ]+ )?PRIVATE KEY-----|$)"),
    ("aws_access_key", r"\b(?:AKIA|ASIA|AGPA|AIDA|AROA|ANPA)[0-9A-Z]{16}\b"),
    ("github_token", r"\b(?:gh[pousr]_[A-Za-z0-9]{36,}|github_pat_[A-Za-z0-9_]{60,})\b"),
    ("slack_token", r"\bxox[abposr]-[A-Za-z0-9-]{10,}\b"),
    ("stripe_key", r"\b(?:sk|rk|pk)_(?:live|test)_[A-Za-z0-9]{16,}\b"),
    ("webhook_secret", r"\bwhsec_[A-Za-z0-9+/=]{16,}\b"),
    ("anthropic_key", r"\bsk-ant-[A-Za-z0-9_-]{20,}\b"),
    ("openai_key", r"\bsk-(?:proj-)?[A-Za-z0-9_-]{32,}\b"),
    ("google_api_key", r"\bAIza[0-9A-Za-z_-]{35}\b"),
    ("jwt", r"\beyJ[A-Za-z0-9_-]{8,}\.eyJ[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}\b"),
    ("bearer_token", r"(?i)\bbearer\s+[A-Za-z0-9._~+/-]{20,}=*"),
    ("url_credentials", r"\b[a-z][a-z0-9+.-]*://[^\s:/@]+:[^\s@/]+@[^\s/]+"),
    ("assigned_secret", r"(?i)\b(?:password|passwd|pwd|secret|api[_-]?key|access[_-]?token|auth[_-]?token|client[_-]?secret)\b\s*[:=]\s*['\"]?[^\s'\"]{6,}"),
)

PII_PATTERNS: tuple[tuple[str, str], ...] = (
    ("email", r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b"),
    ("phone", r"(?<![\w.])\+?\d{1,3}[\s.-]?\(?\d{2,4}\)?[\s.-]?\d{3,4}[\s.-]?\d{3,4}(?![\w.])"),
    ("card_number", r"\b(?:\d[ -]?){13,19}\b"),
)

INFRA_PATTERNS: tuple[tuple[str, str], ...] = (
    ("private_ipv4", r"\b(?:10(?:\.\d{1,3}){3}|192\.168(?:\.\d{1,3}){2}|172\.(?:1[6-9]|2\d|3[01])(?:\.\d{1,3}){2})\b"),
    ("internal_host", r"\b[a-z0-9-]+(?:\.[a-z0-9-]+)*\.(?:internal|corp|local|lan|intranet)\b"),
    ("aws_arn", r"\barn:aws[a-z-]*:[a-z0-9-]+:[a-z0-9-]*:\d{12}:[^\s]+"),
)

_COMPILED = {
    Category.SECRET: [(k, re.compile(p)) for k, p in SECRET_PATTERNS],
    Category.PII: [(k, re.compile(p)) for k, p in PII_PATTERNS],
    Category.INFRA: [(k, re.compile(p)) for k, p in INFRA_PATTERNS],
}

HIGH_ENTROPY_TOKEN = re.compile(r"[A-Za-z0-9+/_=-]{24,}")
ENTROPY_THRESHOLD = 4.0
BASE64_CANDIDATE = re.compile(r"(?<![A-Za-z0-9+/=])[A-Za-z0-9+/]{20,}={0,2}(?![A-Za-z0-9+/=])")
HEX_CANDIDATE = re.compile(r"\b(?:[0-9a-fA-F]{2}){12,}\b")
MAX_DECODE_DEPTH = 2


def luhn_ok(digits: str) -> bool:
    nums = [int(d) for d in digits if d.isdigit()]
    if not 13 <= len(nums) <= 19:
        return False
    total = 0
    for i, n in enumerate(reversed(nums)):
        if i % 2 == 1:
            n = n * 2 - 9 if n * 2 > 9 else n * 2
        total += n
    return total % 10 == 0


def shannon_entropy(token: str) -> float:
    counts = {c: token.count(c) for c in set(token)}
    return -sum((n / len(token)) * math.log2(n / len(token)) for n in counts.values())


def _looks_like_phone(match: str) -> bool:
    """A bare digit run is a timestamp or an id; a phone has a + or separators."""
    digits = sum(c.isdigit() for c in match)
    return digits >= 9 and (match.lstrip().startswith("+") or any(c in " .-()" for c in match.strip()))


def _looks_like_identifier(token: str) -> bool:
    """Long words, paths and snake_case names are not secrets."""
    has_digit = any(c.isdigit() for c in token)
    has_mixed = any(c.isupper() for c in token) and any(c.islower() for c in token)
    return not (has_digit and (has_mixed or any(c in "+/=" for c in token)))


def _pattern_findings(text: str, via: str) -> Iterator[Finding]:
    for category, patterns in _COMPILED.items():
        for kind, rx in patterns:
            for m in rx.finditer(text):
                if kind == "card_number" and not luhn_ok(m.group()):
                    continue
                if kind == "phone" and not _looks_like_phone(m.group()):
                    continue
                yield Finding(kind, category, m.start(), m.end(), m.group(), via)


def _entropy_findings(text: str, via: str) -> Iterator[Finding]:
    for m in HIGH_ENTROPY_TOKEN.finditer(text):
        token = m.group()
        if _looks_like_identifier(token):
            continue
        if shannon_entropy(token) >= ENTROPY_THRESHOLD:
            yield Finding("high_entropy", Category.SECRET, m.start(), m.end(), token, via)


def _canary_findings(text: str, canaries: Iterable[str], via: str) -> Iterator[Finding]:
    for canary in canaries:
        start = text.find(canary)
        while start != -1:
            yield Finding("canary", Category.CANARY, start, start + len(canary), canary, via)
            start = text.find(canary, start + 1)


def _decoded_candidates(text: str) -> Iterator[tuple[int, int, str, str]]:
    for m in BASE64_CANDIDATE.finditer(text):
        try:
            decoded = base64.b64decode(m.group() + "=" * (-len(m.group()) % 4), validate=True)
            yield m.start(), m.end(), decoded.decode("utf-8"), "base64"
        except (binascii.Error, UnicodeDecodeError, ValueError):
            continue
    for m in HEX_CANDIDATE.finditer(text):
        try:
            yield m.start(), m.end(), bytes.fromhex(m.group()).decode("utf-8"), "hex"
        except (ValueError, UnicodeDecodeError):
            continue


URL_ENCODED_RUN = re.compile(r"(?:%[0-9A-Fa-f]{2}|[A-Za-z0-9._~+-]){6,}")
SPACED_RUN = re.compile(r"(?<!\S)(?:\S ){7,}\S(?!\S)")


def _named_findings(text: str, canaries: tuple[str, ...], via: str) -> list[Finding]:
    """Named patterns and canaries only: used on whole-text views (rot13,
    reversed), where an entropy check would just repeat the plain scan."""
    named = [f for f in _pattern_findings(text, via) if f.kind not in ("phone", "card_number")]
    return named + list(_canary_findings(text, canaries, via))


def _view_findings(text: str, canaries: tuple[str, ...]) -> list[Finding]:
    """Text read back to front or rot13'd: same length, so positions map back."""
    findings = []
    rot = codecs.encode(text, "rot13")
    findings += [Finding(f.kind, f.category, f.start, f.end, text[f.start:f.end], "rot13")
                 for f in _named_findings(rot, canaries, "rot13")]
    n = len(text)
    findings += [Finding(f.kind, f.category, n - f.end, n - f.start, text[n - f.end:n - f.start], "reversed")
                 for f in _named_findings(text[::-1], canaries, "reversed")]
    return findings


def _run_findings(text: str, canaries: tuple[str, ...], depth: int) -> list[Finding]:
    """Runs that decode to something else: URL-encoded, or one character per space."""
    findings = []
    candidates = [(m, urllib.parse.unquote(m.group()), "url") for m in URL_ENCODED_RUN.finditer(text)
                  if "%" in m.group()]
    candidates += [(m, m.group().replace(" ", ""), "spaced") for m in SPACED_RUN.finditer(text)]
    for m, decoded, how in candidates:
        for f in _scan_layer(normalise(decoded), canaries, how, depth + 1):
            findings.append(Finding(f.kind, f.category, m.start(), m.end(), m.group(), how))
    return findings


def _scan_layer(text: str, canaries: tuple[str, ...], via: str, depth: int) -> list[Finding]:
    findings = [
        *_pattern_findings(text, via),
        *_entropy_findings(text, via),
        *_canary_findings(text, canaries, via),
    ]
    if depth >= MAX_DECODE_DEPTH:
        return findings
    if depth == 0:
        findings += _view_findings(text, canaries)
    findings += _run_findings(text, canaries, depth)
    for start, end, decoded, how in _decoded_candidates(text):
        if not decoded.isprintable() and not decoded.strip():
            continue
        inner = _scan_layer(normalise(decoded), canaries, how, depth + 1)
        # A hidden finding redacts the whole encoded run it was hidden in.
        for f in inner:
            findings.append(Finding(f.kind, f.category, start, end, text[start:end], how))
    return findings


def scan(text: str, canaries: Iterable[str] = ()) -> list[Finding]:
    """Every finding in already-normalised text, overlapping ones merged."""
    return merge_overlaps(_scan_layer(text, tuple(canaries), "plain", 0))


_SEVERITY = {Category.CANARY: 3, Category.SECRET: 2, Category.PII: 1, Category.INFRA: 0}


def _outranks(f: Finding, other: Finding) -> bool:
    """More severe wins; on a tie, a named or decoded finding beats a generic one."""
    if _SEVERITY[f.category] != _SEVERITY[other.category]:
        return _SEVERITY[f.category] > _SEVERITY[other.category]
    if (f.via != "plain") != (other.via != "plain"):
        return f.via != "plain"
    return other.kind == "high_entropy" and f.kind != "high_entropy"


def merge_overlaps(findings: list[Finding]) -> list[Finding]:
    """Keep one finding per overlapping run, the most severe, spanning the union."""
    ordered = sorted(findings, key=lambda f: (f.start, -f.end))
    merged: list[Finding] = []
    for f in ordered:
        if merged and f.start < merged[-1].end:
            prev = merged[-1]
            top = f if _outranks(f, prev) else prev
            start, end = prev.start, max(prev.end, f.end)
            merged[-1] = Finding(top.kind, top.category, start, end, "", top.via)
        else:
            merged.append(f)
    return merged
