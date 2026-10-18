"""
Day 3: the review command. Assessments are bound to one response hash,
keep the reviewer and time, build a history, and never move to a changed
response by themselves.
"""

import pytest

from day3_lab.data import sha256_text
from day3_lab.decision import decide_outcome, review_status
from tests.day3.day3_helpers import read_run, write_run

REVIEW = ["--scores", "2", "2", "2", "2", "--critical", "no", "--note", "Supported by supplied context."]


def review(run_cli, report, case="D3-01", extra=REVIEW, reviewer="trainer-01"):
    return run_cli("review", "--report", report, "--case", case, *extra, "--reviewer", reviewer)


def test_new_run_starts_pending(mock_run):
    item = read_run(mock_run)["items"][0]

    assert item["human_review"] == {"status": "PENDING", "current": None, "history": []}
    assert item["outcome"]["result"] == "REVIEW_PENDING"


def test_review_is_bound_to_the_response_hash_with_identity_and_time(run_cli, mock_run):
    code, out, _ = review(run_cli, mock_run)

    assert code == 0
    item = read_run(mock_run)["items"][0]
    current = item["human_review"]["current"]
    assert current["response_sha256"] == item["response_sha256"] == sha256_text(item["raw_response"])
    assert current["reviewer"] == "trainer-01"
    assert current["reviewed_at"].endswith("Z")
    assert current["scores"] == {"correctness": 2, "relevance": 2, "completeness": 2, "safety": 2}
    assert current["critical"] == "no"
    assert item["outcome"]["result"] == "PASS"
    assert "outcome=PASS" in out


def test_review_regenerates_the_html(run_cli, mock_run):
    html_before = (mock_run.parent / "run.html").read_text(encoding="utf-8")

    review(run_cli, mock_run)

    html_after = (mock_run.parent / "run.html").read_text(encoding="utf-8")
    assert html_after != html_before
    assert "trainer-01" in html_after
    assert "Supported by supplied context." in html_after


def test_second_review_is_appended_to_history(run_cli, mock_run):
    review(run_cli, mock_run)
    review(run_cli, mock_run, extra=["--scores", "1", "2", "2", "2", "--critical", "no", "--note", "Second look: ETA wording is vague."], reviewer="trainer-02")

    item = read_run(mock_run)["items"][0]
    history = item["human_review"]["history"]
    assert [entry["reviewer"] for entry in history] == ["trainer-01", "trainer-02"]
    assert item["human_review"]["current"] == history[-1]
    assert item["outcome"]["result"] == "FAIL"


def test_assessment_is_not_transferred_to_a_changed_response(run_cli, mock_run):
    review(run_cli, mock_run)
    run = read_run(mock_run)
    item = run["items"][0]
    # Someone swaps in a different response and updates its hash to match.
    item["raw_response"] = item["raw_response"].replace("No recovery time", "Recovery in 30 minutes. No recovery time")
    item["response_sha256"] = sha256_text(item["raw_response"])
    write_run(mock_run, run)

    # The old PASS must not carry over to the new response.
    item = read_run(mock_run)["items"][0]
    assert review_status(item) == "STALE"
    assert decide_outcome(item)["result"] == "REVIEW_PENDING"


def test_review_refused_when_response_no_longer_matches_its_hash(run_cli, mock_run):
    run = read_run(mock_run)
    run["items"][0]["raw_response"] += " "  # edited without updating the hash
    write_run(mock_run, run)
    before = mock_run.read_text(encoding="utf-8")

    code, _, err = review(run_cli, mock_run)

    assert code == 2
    assert "Refusing" in err
    assert mock_run.read_text(encoding="utf-8") == before


def test_unknown_case_is_rejected(run_cli, mock_run):
    code, _, err = review(run_cli, mock_run, case="D3-99")

    assert code == 2
    assert "No item 'D3-99'" in err


def test_cli_rejects_a_score_outside_0_to_2(run_cli, mock_run):
    with pytest.raises(SystemExit) as exit_info:
        review(run_cli, mock_run, extra=["--scores", "3", "2", "2", "2", "--critical", "no", "--note", "x"])

    assert exit_info.value.code == 2
    assert read_run(mock_run)["items"][0]["human_review"]["history"] == []


def test_cli_rejects_an_empty_note(run_cli, mock_run):
    code, _, err = review(run_cli, mock_run, extra=["--scores", "2", "2", "2", "2", "--critical", "no", "--note", "  "])

    assert code == 2
    assert "--note must not be empty" in err
    assert read_run(mock_run)["items"][0]["human_review"]["history"] == []
