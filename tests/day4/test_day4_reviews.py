"""
Day 4 human reviews: explicit, named, bound to what was reviewed, kept
separate from proposals and run evidence, and never created by the judge.
"""

import json

import pytest

from training_day4 import calibration, data, experiments, reviews

REVIEW = ["--reviewer", "Test Trainer", "--reason", "Checked against the approved context."]


def review_fixed(run_cli, case_id, scores, critical=("none",)):
    return run_cli("review-fixed", "--case", case_id, "--scores", *scores, "--critical", *critical, *REVIEW)


def test_review_fixed_saves_a_separate_record_and_keeps_the_proposal(run_cli):
    labels_before = data.LABELS_PATH.read_bytes()

    code, out, _ = review_fixed(run_cli, "D4-02", ["0", "2", "0", "0"])

    assert code == 0 and "verdict=FAIL" in out
    assert data.LABELS_PATH.read_bytes() == labels_before
    [record] = reviews.load_confirmed()["reviews"]
    assert record["human_confirmed"] is True and record["reviewer"] == "Test Trainer"
    assert record["binding"]["rubric_version"] == "day4-v1"
    assert record["proposal_comparison"]["matches_proposal"] is True
    _, out, _ = run_cli("validate")
    assert "1 confirmed and current" in out


@pytest.mark.parametrize(
    "argv",
    [
        ["--reviewer", "<your name>", "--reason", "fine"],
        ["--reviewer", "  ", "--reason", "fine"],
        ["--reviewer", "Test Trainer", "--reason", "   "],
    ],
)
def test_review_requires_a_real_identity_and_reason(run_cli, argv):
    code, _, err = run_cli("review-fixed", "--case", "D4-01", "--scores", "2", "2", "2", "2", "--critical", "none", *argv)

    assert code == 2 and err
    assert reviews.load_confirmed()["reviews"] == []


def test_review_rejects_invalid_scores_and_mixed_criticals(run_cli):
    with pytest.raises(SystemExit):
        review_fixed(run_cli, "D4-01", ["3", "2", "2", "2"])
    code, _, err = review_fixed(run_cli, "D4-03", ["0", "2", "0", "0"], critical=("none", "SECRET_REQUEST"))

    assert code == 2 and "unknown critical category 'none'" in err
    assert reviews.load_confirmed()["reviews"] == []


def test_review_becomes_stale_when_the_response_changes(run_cli, cases_copy):
    review_fixed(run_cli, "D4-01", ["2", "2", "2", "2"])
    document = json.loads(cases_copy.read_text(encoding="utf-8"))
    document["cases"][0]["fixed_response"] += " It will be back at 3pm."
    cases_copy.write_text(json.dumps(document), encoding="utf-8")

    status = reviews.fixed_review_status(data.load_cases())["D4-01"]

    assert status["current"] is None
    assert status["stale"][0]["stale_because"] == ["response_sha256"]


def test_review_becomes_stale_when_the_rubric_changes(run_cli, monkeypatch, tmp_path):
    rubric_copy = tmp_path / "rubric.json"
    rubric_copy.write_bytes(data.RUBRIC_PATH.read_bytes())
    monkeypatch.setattr(data, "RUBRIC_PATH", rubric_copy)
    review_fixed(run_cli, "D4-04", ["2", "2", "2", "2"])
    changed = json.loads(rubric_copy.read_text(encoding="utf-8"))
    changed["dimensions"][0]["levels"]["1"] = "Reworded level."
    rubric_copy.write_text(json.dumps(changed), encoding="utf-8")

    status = reviews.fixed_review_status(data.load_cases())["D4-04"]

    assert status["current"] is None and status["stale"][0]["stale_because"] == ["rubric_sha256"]


def test_calibration_pairs_only_confirmed_current_reviews(run_cli):
    review_fixed(run_cli, "D4-06", ["2", "2", "2", "2"])
    review_fixed(run_cli, "D4-03", ["0", "2", "0", "0"], critical=("SECRET_REQUEST",))
    experiments.run_judge_fixed("replay", list(data.EXPECTED_CASE_IDS))

    run, _, _ = calibration.calibrate("latest-fixed")

    holdout, development = run["splits"]["holdout"], run["splits"]["development"]
    assert holdout["confirmed_coverage"] == {"confirmed": 1, "of": 4}
    assert holdout["confirmed_human"]["verdict_agreement"] == {"count": 0, "denominator": 1}
    assert holdout["confirmed_human"]["false_fails"] == ["D4-06"]
    assert development["confirmed_human"]["verdict_agreement"] == {"count": 1, "denominator": 1}
    assert development["confirmed_human"]["critical_disagreements"] == []


def test_review_generated_binds_to_run_and_response_without_changing_the_run(run_cli):
    run, run_dir = experiments.run_compare("replay", ["D4-03"], seed=3)
    response_id = run["observations"][0]["response_id"]
    run_json_before = (run_dir / "run.json").read_bytes()

    code, out, _ = run_cli("review-generated", "--run", run["run_id"], "--response", response_id,
                           "--scores", "2", "2", "2", "2", "--critical", "none", *REVIEW)

    assert code == 0 and "run.json was not changed" in out
    assert (run_dir / "run.json").read_bytes() == run_json_before
    status = reviews.generated_review_status(run, run_dir)
    assert status[response_id]["current"]["binding"]["run_id"] == run["run_id"]
    assert sum(1 for entry in status.values() if entry["current"]) == 1
    _, summary, _ = run_cli("summary")
    assert "human-reviewed 1/2" in summary


def test_review_generated_rejects_unknown_ids_and_changed_evidence(run_cli):
    run, run_dir = experiments.run_compare("replay", ["D4-01"], seed=3)
    code, _, err = run_cli("review-generated", "--run", run["run_id"], "--response", "resp-unknown",
                           "--scores", "2", "2", "2", "2", "--critical", "none", *REVIEW)
    assert code == 2 and "No response" in err

    tampered = json.loads((run_dir / "run.json").read_text(encoding="utf-8"))
    tampered["observations"][0]["response_text"] += " Edited."
    (run_dir / "run.json").write_text(json.dumps(tampered), encoding="utf-8")
    code, _, err = run_cli("review-generated", "--run", run["run_id"], "--response", tampered["observations"][0]["response_id"],
                           "--scores", "2", "2", "2", "2", "--critical", "none", *REVIEW)
    assert code == 2 and "no longer matches its hash" in err


def test_judge_and_compare_runs_never_create_human_reviews():
    experiments.run_judge_fixed("replay", list(data.EXPECTED_CASE_IDS))
    _, run_dir = experiments.run_compare("replay", list(data.EXPECTED_CASE_IDS), seed=5)

    assert reviews.load_confirmed()["reviews"] == []
    assert not (run_dir / "human_reviews.json").exists()
