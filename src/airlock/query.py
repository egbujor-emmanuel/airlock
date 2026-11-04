"""Typed questions: the asking side declares fields, the answering side fills them.

This is how a data clean room works, applied to two agents in chat: the raw data
never becomes something that could cross. An answer is accepted only if every
value matches its declared type, and the text that crosses is rendered from the
validated values alone, so there is no free-text channel to leak through.

Types (a trailing ``[]`` makes a list of up to ``MAX_LIST`` items)::

    int        whole number
    number     any finite number
    bool       true or false
    enum:a|b   one of the listed words, chosen by the asking side

There is deliberately no free string type: a string field is a pipe for logs.
"""

from __future__ import annotations

import json
import math
import re
from dataclasses import dataclass
from typing import Any

MAX_FIELDS = 12
MAX_LIST = 50
MAX_ABS_NUMBER = 1e15
FIELD_NAME = re.compile(r"^[a-z][a-z0-9_]{0,39}$")
ENUM_WORD = re.compile(r"^[A-Za-z0-9._-]{1,40}$")
SCALARS = ("int", "number", "bool")
JSON_BLOCK = re.compile(r"```(?:json)?\s*(\{.*?\})\s*```", re.DOTALL)


class QueryError(ValueError):
    pass


@dataclass(frozen=True)
class FieldType:
    base: str  # "int" | "number" | "bool" | "enum"
    options: tuple[str, ...] = ()
    is_list: bool = False

    @property
    def spec(self) -> str:
        core = f"enum:{'|'.join(self.options)}" if self.base == "enum" else self.base
        return core + ("[]" if self.is_list else "")


def parse_type(spec: str) -> FieldType:
    raw = spec.strip()
    is_list = raw.endswith("[]")
    core = raw[:-2] if is_list else raw
    if core in SCALARS:
        return FieldType(core, (), is_list)
    if core.startswith("enum:"):
        options = tuple(o.strip() for o in core[5:].split("|") if o.strip())
        if not options or not all(ENUM_WORD.match(o) for o in options):
            raise QueryError(f"enum options must be short words: {spec!r}")
        return FieldType("enum", options, is_list)
    raise QueryError(f"unknown type {spec!r} (use int, number, bool or enum:a|b, optionally with [])")


def parse_schema(fields: dict[str, str]) -> dict[str, FieldType]:
    if not isinstance(fields, dict) or not fields:
        raise QueryError("a query needs at least one field")
    if len(fields) > MAX_FIELDS:
        raise QueryError(f"at most {MAX_FIELDS} fields per query")
    schema = {}
    for name, spec in fields.items():
        if not FIELD_NAME.match(name):
            raise QueryError(f"field names are lower_snake_case: {name!r}")
        schema[name] = parse_type(str(spec))
    return schema


def _check_scalar(t: FieldType, value: Any) -> Any:
    if t.base == "bool":
        if not isinstance(value, bool):
            raise QueryError("expected true or false")
        return value
    if t.base in ("int", "number"):
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise QueryError("expected a number")
        if not math.isfinite(value) or abs(value) > MAX_ABS_NUMBER:
            raise QueryError("number out of range")
        if t.base == "int":
            if isinstance(value, float) and not value.is_integer():
                raise QueryError("expected a whole number")
            return int(value)
        return value
    if value not in t.options:
        raise QueryError(f"expected one of {', '.join(t.options)}")
    return value


def validate(schema: dict[str, FieldType], answer: Any) -> dict[str, Any]:
    """Return the answer normalised, or raise listing every problem."""
    if not isinstance(answer, dict):
        raise QueryError("the answer must be a JSON object")
    problems = []
    extra = sorted(set(answer) - set(schema))
    missing = sorted(set(schema) - set(answer))
    if extra:
        problems.append(f"fields that weren't asked for: {', '.join(extra)}")
    if missing:
        problems.append(f"missing fields: {', '.join(missing)}")
    clean: dict[str, Any] = {}
    for name, t in schema.items():
        if name not in answer:
            continue
        value = answer[name]
        try:
            if t.is_list:
                if not isinstance(value, list) or len(value) > MAX_LIST:
                    raise QueryError(f"expected a list of at most {MAX_LIST}")
                clean[name] = [_check_scalar(t, v) for v in value]
            else:
                clean[name] = _check_scalar(t, value)
        except QueryError as exc:
            problems.append(f"{name} ({t.spec}): {exc}")
    if problems:
        raise QueryError("; ".join(problems))
    return clean


def extract_json(text: str) -> Any:
    """The first JSON object in a message, fenced or bare."""
    fenced = JSON_BLOCK.search(text)
    candidate = fenced.group(1) if fenced else text[text.find("{") : text.rfind("}") + 1]
    if not candidate:
        raise QueryError("no JSON object found")
    try:
        return json.loads(candidate)
    except json.JSONDecodeError as exc:
        raise QueryError(f"that isn't valid JSON: {exc.msg}") from exc


def render_query(qid: str, question: str, schema: dict[str, FieldType]) -> str:
    fields = {name: t.spec for name, t in schema.items()}
    return (
        f"❓ Query {qid}: {question}\n"
        f"```json\n{json.dumps({'query': qid, 'fields': fields}, indent=1)}\n```"
    )


def render_answer(qid: str, values: dict[str, Any]) -> str:
    lines = [f"📊 Answer to query {qid} (typed fields only; no free text can cross):"]
    lines += [f"• {name} = {json.dumps(value)}" for name, value in values.items()]
    return "\n".join(lines)


QUERY_BLOCK = re.compile(r'\{\s*"query":\s*"(Q-[A-Z]+-\d+)",\s*"fields":\s*(\{.*?\})\s*\}', re.DOTALL)


def find_query(text: str) -> tuple[str, dict[str, str]] | None:
    match = QUERY_BLOCK.search(text)
    if not match:
        return None
    return match.group(1), json.loads(match.group(2))
