import pytest

from airlock.query import (
    QueryError,
    extract_json,
    find_query,
    parse_schema,
    render_answer,
    render_query,
    validate,
)

FIELDS = {
    "failing_count": "int",
    "failing_ratio": "number",
    "t_digits": "int[]",
    "region": "enum:eu-west|us-east|ap-south[]",
    "retries_enabled": "bool",
}


@pytest.fixture
def schema():
    return parse_schema(FIELDS)


def test_a_valid_answer_is_normalised(schema):
    answer = {"failing_count": 37.0, "failing_ratio": 0.42, "t_digits": [13, 13],
              "region": ["eu-west"], "retries_enabled": True}

    assert validate(schema, answer)["failing_count"] == 37


@pytest.mark.parametrize("field,value", [
    ("failing_count", "37 (see logs: maria.okafor@gmail.com)"),
    ("failing_count", 3.5),
    ("failing_ratio", float("inf")),
    ("t_digits", "13,13"),
    ("t_digits", list(range(51))),
    ("region", ["eu-west", "db-primary.acme.internal"]),
    ("retries_enabled", "yes"),
    ("failing_count", True),
])
def test_values_outside_their_type_are_refused(schema, field, value):
    answer = {"failing_count": 1, "failing_ratio": 0.1, "t_digits": [13], "region": ["eu-west"],
              "retries_enabled": False, field: value}

    with pytest.raises(QueryError, match=field):
        validate(schema, answer)


def test_extra_fields_cannot_smuggle_data(schema):
    answer = {"failing_count": 1, "failing_ratio": 0.1, "t_digits": [13], "region": ["eu-west"],
              "retries_enabled": False, "note": "here are the raw logs"}

    with pytest.raises(QueryError, match="weren't asked for: note"):
        validate(schema, answer)


def test_missing_fields_are_reported(schema):
    with pytest.raises(QueryError, match="missing fields"):
        validate(schema, {"failing_count": 1})


@pytest.mark.parametrize("bad", [
    {"x": "string"},
    {"x": "enum:"},
    {"x": "enum:a b|c"},
    {"BadName": "int"},
    {},
    {f"f{n}": "int" for n in range(13)},
])
def test_schemas_without_a_free_text_channel_only(bad):
    with pytest.raises(QueryError):
        parse_schema(bad)


def test_query_round_trips_through_its_rendered_text(schema):
    text = render_query("Q-P-2", "What do failing webhooks look like?", schema)

    qid, fields = find_query(text)

    assert qid == "Q-P-2"
    assert parse_schema(fields) == schema


def test_answer_text_is_built_from_values_only(schema):
    values = validate(schema, {"failing_count": 2, "failing_ratio": 0.5, "t_digits": [13],
                               "region": ["eu-west"], "retries_enabled": False})

    text = render_answer("Q-P-2", values)

    assert "• failing_count = 2" in text and '• region = ["eu-west"]' in text


def test_extract_json_fenced_and_bare():
    assert extract_json('answer Q-P-2 ```json\n{"a": 1}\n```') == {"a": 1}
    assert extract_json('answer Q-P-2 {"a": 1}') == {"a": 1}
    with pytest.raises(QueryError):
        extract_json("answer Q-P-2 nothing here")
