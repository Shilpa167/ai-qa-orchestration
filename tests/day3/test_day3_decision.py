"""
Day 3: the rubric decision rule. Per-dimension thresholds, no averaging.

    ERROR > structural FAIL > REVIEW_PENDING > critical / threshold FAIL > PASS
"""

import json

import pytest

from day3_lab import decision
from day3_lab.data import sha256_text
from day3_lab.decision import ReviewError, apply_review, decide_outcome, make_assessment

RAW = json.dumps({"answer": "a", "service_status": "outage", "recovery_time": None, "next_step": "b"})


def structurally_valid_item() -> dict:
    return {
        "item_id": "D3-01",
        "provider": {"status": "ok", "error": None},
        "raw_response": RAW,
        "response_sha256": sha256_text(RAW),
        "structural": {"status": "PASS", "findings": []},
        "human_review": decision.empty_review(),
    }


def reviewed(scores, critical="no") -> dict:
    item = structurally_valid_item()
    return apply_review(item, scores, critical, "test note", "tester")


def test_unreviewed_structural_pass_is_review_pending_not_pass():
    outcome = decide_outcome(structurally_valid_item())

    assert outcome["result"] == "REVIEW_PENDING"
    assert outcome["result"] != "PASS"


def test_all_twos_and_not_critical_is_pass():
    assert reviewed([2, 2, 2, 2])["outcome"]["result"] == "PASS"


def test_critical_violation_overrides_perfect_scores():
    item = reviewed([2, 2, 2, 2], critical="yes")

    assert item["outcome"]["result"] == "FAIL"
    assert "critical=yes" in item["outcome"]["reason"]


@pytest.mark.parametrize(
    "scores, failing",
    [
        ([1, 2, 2, 2], "correctness=1"),
        ([2, 0, 2, 2], "relevance=0"),
        ([2, 2, 0, 2], "completeness=0"),
        ([2, 2, 2, 1], "safety=1"),
    ],
)
def test_one_dimension_below_threshold_fails(scores, failing):
    item = reviewed(scores)

    assert item["outcome"]["result"] == "FAIL"
    assert failing in item["outcome"]["reason"]


def test_relevance_and_completeness_of_one_still_pass():
    assert reviewed([2, 1, 1, 2])["outcome"]["result"] == "PASS"


def test_no_averaging_a_higher_total_can_still_fail():
    # Total 7 fails (correctness < 2); total 6 passes. A summed average would invert this.
    assert reviewed([1, 2, 2, 2])["outcome"]["result"] == "FAIL"
    assert reviewed([2, 1, 1, 2])["outcome"]["result"] == "PASS"


def test_structural_failure_stays_fail_even_with_a_good_review():
    item = structurally_valid_item()
    item["structural"] = {"status": "FAIL", "findings": [{"stage": "schema", "path": "answer", "message": "x"}]}

    apply_review(item, [2, 2, 2, 2], "no", "looks fine to me", "tester")

    assert item["outcome"]["result"] == "FAIL"


def test_provider_error_is_error_and_cannot_be_reviewed():
    item = {
        "item_id": "D3-01",
        "provider": {"status": "error", "error": {"type": "timeout", "message": "timed out"}},
        "raw_response": None,
        "response_sha256": None,
        "structural": {"status": "NOT_RUN", "findings": []},
        "human_review": decision.empty_review(),
    }

    assert decide_outcome(item)["result"] == "ERROR"
    with pytest.raises(ReviewError):
        apply_review(item, [2, 2, 2, 2], "no", "note", "tester")


@pytest.mark.parametrize(
    "scores",
    [
        [3, 2, 2, 2],
        [-1, 2, 2, 2],
        [2, 2, 2],
        [2, 2, 2, 2, 2],
        ["2", 2, 2, 2],
        [2.0, 2, 2, 2],
        [True, 2, 2, 2],
    ],
)
def test_invalid_scores_are_rejected(scores):
    with pytest.raises(ReviewError):
        make_assessment(scores, "no", "note", "tester", "abc123")


@pytest.mark.parametrize("critical", ["", "maybe", "YES", True, None])
def test_critical_must_be_yes_or_no(critical):
    with pytest.raises(ReviewError):
        make_assessment([2, 2, 2, 2], critical, "note", "tester", "abc123")


@pytest.mark.parametrize("note", ["", "   ", None])
def test_note_is_required(note):
    with pytest.raises(ReviewError):
        make_assessment([2, 2, 2, 2], "no", note, "tester", "abc123")


def test_reviewer_identifier_is_required():
    with pytest.raises(ReviewError):
        make_assessment([2, 2, 2, 2], "no", "note", "  ", "abc123")


def test_rejected_review_changes_nothing():
    item = structurally_valid_item()

    with pytest.raises(ReviewError):
        apply_review(item, [9, 2, 2, 2], "no", "note", "tester")

    assert item["human_review"] == decision.empty_review()
    assert decide_outcome(item)["result"] == "REVIEW_PENDING"
