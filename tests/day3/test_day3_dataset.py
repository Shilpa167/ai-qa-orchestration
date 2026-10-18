"""
Day 3: the dataset and rubric are valid, consistent and unchanged copies.
"""

import copy

from day3_lab import data, decision
from day3_lab.mock_responses import MOCK_RESPONSES


def test_validate_data_command_reports_ten_cases(run_cli):
    code, out, _ = run_cli("validate-data")

    assert code == 0
    assert "Cases validated: 10" in out
    assert "Unique case IDs: 10 of 10" in out


def test_copies_are_byte_identical_to_the_supplied_materials():
    # Expectations must not be silently changed while copying.
    assert data.sha256_file(data.CASES_PATH) == data.sha256_file(data.SOURCE_CASES_PATH)
    assert data.sha256_file(data.RUBRIC_PATH) == data.sha256_file(data.SOURCE_RUBRIC_PATH)


def test_case_ids_are_unique_and_the_dataset_is_valid(cases_document):
    case_ids = [case["case_id"] for case in cases_document["cases"]]

    assert len(case_ids) == 10
    assert len(set(case_ids)) == len(case_ids)
    assert data.validate_cases(cases_document) == []


def test_rubric_matches_the_decision_rule_in_code(cases_document, rubric):
    assert data.validate_rubric(rubric, decision.DIMENSIONS, decision.SUPPORTED_RUBRIC_VERSION) == []
    assert data.validate_consistency(cases_document, rubric) == []


def test_duplicate_case_id_is_detected(cases_document):
    broken = copy.deepcopy(cases_document)
    broken["cases"][1]["case_id"] = broken["cases"][0]["case_id"]

    problems = data.validate_cases(broken)

    assert any("duplicate case_id" in problem for problem in problems)


def test_invalid_context_status_is_detected(cases_document):
    broken = copy.deepcopy(cases_document)
    broken["cases"][0]["approved_context"]["service_status"] = "down"

    problems = data.validate_cases(broken)

    assert any("service_status 'down'" in problem for problem in problems)


def test_rubric_version_mismatch_is_detected(cases_document, rubric):
    other = dict(rubric, version="day3-v2")

    assert data.validate_consistency(cases_document, other)
    assert data.validate_rubric(other, decision.DIMENSIONS, decision.SUPPORTED_RUBRIC_VERSION)


def test_every_case_has_exactly_one_reviewed_mock_response(cases_document):
    assert set(MOCK_RESPONSES) == {case["case_id"] for case in cases_document["cases"]}
