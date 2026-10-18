"""
Day 3: structural validation of the response contract.

    answer          non-empty string
    service_status  operational | degraded | outage | unknown
    recovery_time   string or null
    next_step       non-empty string
    no extra keys, no coercion of bad output into a good one
"""

import json

import pytest

from day3_lab.mock_responses import MOCK_RESPONSES
from day3_lab.validation import check_structure

VALID = {
    "answer": "A VPN outage is confirmed and no recovery time has been published.",
    "service_status": "outage",
    "recovery_time": None,
    "next_step": "Watch for the official status update.",
}


def raw(value) -> str:
    return json.dumps(value)


def finding_paths(result) -> list[str]:
    return [finding["path"] for finding in result["findings"]]


def test_valid_response_passes():
    result = check_structure(raw(VALID))

    assert result["status"] == "PASS"
    assert result["findings"] == []
    assert result["parsed"] == VALID


@pytest.mark.parametrize("case_id", sorted(MOCK_RESPONSES))
def test_every_mock_response_is_structurally_valid(case_id):
    assert check_structure(raw(MOCK_RESPONSES[case_id]))["status"] == "PASS"


@pytest.mark.parametrize("missing", ["answer", "service_status", "recovery_time", "next_step"])
def test_missing_field_fails(missing):
    response = {key: value for key, value in VALID.items() if key != missing}

    result = check_structure(raw(response))

    assert result["status"] == "FAIL"
    assert any(f"'{missing}' is a required property" in finding["message"] for finding in result["findings"])


def test_extra_key_fails():
    result = check_structure(raw({**VALID, "confidence": 0.99}))

    assert result["status"] == "FAIL"
    assert any("Additional properties" in finding["message"] for finding in result["findings"])


@pytest.mark.parametrize(
    "field, bad_value",
    [
        ("answer", 42),
        ("answer", None),
        ("service_status", 1),
        ("recovery_time", 30),
        ("recovery_time", False),
        ("next_step", ["step one"]),
    ],
)
def test_wrong_type_fails(field, bad_value):
    result = check_structure(raw({**VALID, field: bad_value}))

    assert result["status"] == "FAIL"
    assert field in finding_paths(result)


@pytest.mark.parametrize("bad_status", ["down", "Outage", "OUTAGE", "", "partial outage"])
def test_invalid_status_enum_fails(bad_status):
    result = check_structure(raw({**VALID, "service_status": bad_status}))

    assert result["status"] == "FAIL"
    assert "service_status" in finding_paths(result)


@pytest.mark.parametrize("field", ["answer", "next_step"])
@pytest.mark.parametrize("blank", ["", "   ", "\n\t"])
def test_empty_or_blank_text_fails(field, blank):
    result = check_structure(raw({**VALID, field: blank}))

    assert result["status"] == "FAIL"
    assert field in finding_paths(result)


@pytest.mark.parametrize(
    "raw_text",
    [
        "Sure! The VPN is down.",                    # prose, not JSON
        '{"answer": "cut off',                        # truncated JSON
        "",                                           # nothing at all
        "```json\n" + json.dumps(VALID) + "\n```",  # JSON wrapped in a markdown fence
    ],
)
def test_unparseable_output_fails_at_parse_stage_and_keeps_evidence(raw_text):
    result = check_structure(raw_text)

    assert result["status"] == "FAIL"
    assert result["parsed"] is None
    assert result["findings"][0]["stage"] == "parse"


def test_no_coercion_of_json_inside_a_string():
    # The model returned a JSON *string* containing JSON. It is not repaired.
    result = check_structure(json.dumps(json.dumps(VALID)))

    assert result["status"] == "FAIL"
    assert isinstance(result["parsed"], str)


def test_no_coercion_of_a_list_holding_a_valid_response():
    result = check_structure(raw([VALID]))

    assert result["status"] == "FAIL"
    assert result["findings"][0]["path"] == "<whole response>"


def test_duplicate_keys_are_rejected_not_silently_merged():
    text = '{"answer": "a", "service_status": "outage", "service_status": "operational", "recovery_time": null, "next_step": "b"}'

    result = check_structure(text)

    assert result["status"] == "FAIL"
    assert "duplicate keys" in result["findings"][0]["message"]


def test_valid_enum_does_not_prove_the_status_matches_the_facts():
    # D3-01's approved context says "outage". This says "operational", which is
    # structurally valid. Structure cannot catch the contradiction; a human must.
    contradicting = {**VALID, "service_status": "operational", "answer": "The VPN is working normally."}

    assert check_structure(raw(contradicting))["status"] == "PASS"
