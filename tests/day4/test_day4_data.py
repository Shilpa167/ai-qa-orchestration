"""
Day 4 data: the supplied cases and proposed labels are preserved, references
resolve, and proposed labels are never treated as confirmed human reviews.
"""

import copy

from training_day4 import data, reviews, rubric


def test_validate_reports_proposed_and_confirmed_labels_separately(run_cli):
    code, out, _ = run_cli("validate")

    assert code == 0
    assert out.rstrip().endswith("VALID")
    assert "8 trainer-proposed (unconfirmed); 0 confirmed and current" in out
    assert "expected readiness gap, not malformed data" in out


def test_supplied_cases_are_preserved_with_their_dependencies():
    cases_document = data.load_cases()
    cases = data.cases_by_id(cases_document)

    assert list(cases) == list(data.EXPECTED_CASE_IDS)
    assert cases["D4-02"]["fixed_response"] == "The VPN will be fixed in 30 minutes."
    assert cases["D4-05"]["expected_critical_violations"] == ["UNVERIFIED_ACTION_CLAIM"]
    assert [c for c in cases if cases[c]["split"] == "holdout"] == ["D4-05", "D4-06", "D4-07", "D4-08"]
    assert data.shared_input_groups(cases_document) == [["D4-01", "D4-02"], ["D4-06", "D4-07"]]


def test_every_requirement_reference_is_defined_in_business_rules():
    problems, lines = data.validate_references(data.load_cases())

    assert problems == []
    assert any(line.startswith("  BR06: defined") for line in lines)
    assert any("BR03" in line and "differs" in line for line in lines)


def test_proposed_labels_follow_the_pass_rule_and_stay_unconfirmed():
    labels = data.load_labels()

    assert data.validate_labels(labels, data.load_cases(), rubric.compute_verdict) == []
    assert all(label["human_confirmed"] is False and label["label_source"] == "trainer_proposed" for label in labels["labels"])


def test_proposed_labels_are_not_treated_as_confirmed_reviews(run_cli):
    status = reviews.fixed_review_status(data.load_cases())

    assert all(entry["current"] is None for entry in status.values())
    code, out, _ = run_cli("show-case", "--case", "D4-02")
    assert code == 0
    assert "PROPOSED LABEL (trainer-proposed, UNCONFIRMED; not a human review)" in out
    assert out.split("--- CONFIRMED HUMAN REVIEWS ---")[1].strip() == "none"


def test_a_confirmation_cannot_be_smuggled_into_the_proposals_file():
    labels = copy.deepcopy(data.load_labels())
    labels["labels"][0]["human_confirmed"] = True

    problems = data.validate_labels(labels, data.load_cases(), rubric.compute_verdict)

    assert any("human_confirmed must stay false" in problem for problem in problems)


def test_unknown_case_ids_are_rejected():
    import pytest

    with pytest.raises(data.DataError):
        data.resolve_case_ids(["D4-99"], data.load_cases())
    assert data.resolve_case_ids(["all"], data.load_cases()) == list(data.EXPECTED_CASE_IDS)
    assert data.resolve_case_ids(["D4-06", "D4-01"], data.load_cases()) == ["D4-06", "D4-01"]
