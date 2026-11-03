"""Make relayed text inert before it lands in a room.

Text from the other org is data, never instructions. Two things in a Switch
room act on text rather than read it:

* ``@name`` addresses an agent: the other side could otherwise make our inside
  agent act just by writing its name.
* A message starting with ``!`` (or ``/`` on Telegram and Teams) is a room
  command when a person sends it.

Mentions get a full-width at sign (it renders the same, matches nothing), and
every relayed line is quoted, so no relayed line can start a message.
"""

from __future__ import annotations

import re

MENTION = re.compile(r"@(?=[A-Za-z0-9])")
FULLWIDTH_AT = "＠"
CODE_FENCE = re.compile(r"^\s*```")


def defang(text: str) -> str:
    return MENTION.sub(FULLWIDTH_AT, text)


def quote(text: str) -> str:
    return "\n".join(f"> {line}" if line.strip() else ">" for line in text.splitlines() or [""])


def inert(text: str) -> str:
    """Defanged and quoted: safe to post as someone else's words."""
    return quote(defang(text))


def code_lines(text: str) -> int:
    """Lines inside fenced code blocks: the measure for the paste limit."""
    inside, count = False, 0
    for line in text.splitlines():
        if CODE_FENCE.match(line):
            inside = not inside
            continue
        count += inside
    return count
