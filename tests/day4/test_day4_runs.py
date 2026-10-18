"""
Day 4 run evidence: no overwrites, every repeat kept, strict latest-fixed
resolution, calibration with zero confirmed labels, and an honest summary.
"""

import json

import pytest

from tests.day4.day4_helpers import LIVE_ENV, FakeSDK, factory_for, judge_json, payload_of, sdk_response
from training_day4 import calibration, data, experiments, runs


def replay_judge(case_ids=None):
    return experiments.run_judge_fixed("replay", case_ids or list(data.EXPECTED_CASE_IDS))


def test_existing_run_evidence_is_never_overwritten(monkeypatch):
    monkeypatch.setattr(runs, "new_run_id", lambda kind: f"{kind}-fixed-id")
    run, run_dir = runs.create_run("compare", "replay", "label", {})
    before = (run_dir / "run.json").read_bytes()

    with pytest.raises(runs.RunError, match="never overwritten"):
        runs.create_run("compare", "replay", "label", {})

    assert (run_dir / "run.json").read_bytes() == before


def test_repeat_keeps_every_result_and_error(run_cli):
    code, out, _ = run_cli("repeat", "--mode", "replay", "--prompt", "B", "--cases", "D4-01", "D4-06", "D4-08", "--runs", "3")

    assert code == 1  # one authored judge output is invalid, so the run is partial
    run = json.loads(next(data.REPORTS_DIR.glob("repeat-replay-*/run.json")).read_text(encoding="utf-8"))
    assert len(run["observations"]) == 9
    assert [(o["case_id"], o["repetition"]) for o in run["observations"]] == [(c, r) for c in ("D4-01", "D4-06", "D4-08") for r in range(3)]
    errors = [o for o in run["observations"] if o["status"] == "error"]
    assert len(errors) == 1 and errors[0]["case_id"] == "D4-08"
    assert any("completeness" in e for e in errors[0]["judge"]["validation_errors"])
    assert errors[0]["judge"]["raw_output_sanitised"]
    assert run["status"] == "partially completed"
    assert "D4-08: 1/3 passed, 2 valid, 1 errors" in out


def test_latest_fixed_resolves_the_newest_finalised_run():
    replay_judge()
    newest, _ = replay_judge()

    run, _ = runs.resolve_fixed_run("latest-fixed")

    assert run["run_id"] == newest["run_id"]


def test_latest_fixed_never_falls_back_past_an_unfinished_run():
    replay_judge()
    runs.create_run(runs.JUDGE_FIXED, "replay", "label", {})  # started, never finalised

    with pytest.raises(runs.RunError, match="unfinished"):
        runs.resolve_fixed_run("latest-fixed")


def test_latest_fixed_rejects_corrupted_metadata():
    replay_judge()
    _, broken_dir = replay_judge()
    (broken_dir / "run.json").write_text("{not json", encoding="utf-8")

    with pytest.raises(runs.RunError, match="corrupted"):
        runs.resolve_fixed_run("latest-fixed")


def test_latest_fixed_rejects_ambiguous_timestamps():
    first, first_dir = replay_judge()
    second, second_dir = replay_judge()
    tampered = json.loads((second_dir / "run.json").read_text(encoding="utf-8"))
    tampered["created_at_ns"] = first["created_at_ns"]
    (second_dir / "run.json").write_text(json.dumps(tampered), encoding="utf-8")

    with pytest.raises(runs.RunError, match="Ambiguous"):
        runs.resolve_fixed_run("latest-fixed")


def test_calibration_with_zero_confirmed_labels_reports_unavailable(run_cli):
    replay_judge()

    code, out, _ = run_cli("calibrate", "--run", "latest-fixed")

    assert code == 0
    assert "development: confirmed human labels 0/4; confirmed human agreement unavailable" in out
    assert "holdout: confirmed human labels 0/4; confirmed human agreement unavailable" in out
    assert "workflow demonstration" in out
    results = next(data.REPORTS_DIR.glob("calibrate-replay-*/results.md")).read_text(encoding="utf-8")
    assert "%" not in results
    assert "PROVISIONAL: judge vs trainer-proposed, UNCONFIRMED labels" in results


def test_calibration_makes_missing_results_and_evaluation_errors_explicit():
    def script(kwargs, n):
        if n == 1:
            return sdk_response("not json at all")
        return sdk_response(judge_json(payload_of(kwargs)["response_id"]))

    sdk = FakeSDK(script)
    experiments.run_judge_fixed("live", ["D4-01", "D4-02"], environ=LIVE_ENV, client_factory=factory_for(sdk), sleep=lambda s: None)

    run, _, _ = calibration.calibrate("latest-fixed")

    development, holdout = run["splits"]["development"], run["splits"]["holdout"]
    assert development["evaluation_errors"] == ["D4-01", "D4-03", "D4-04"]
    assert holdout["evaluation_errors"] == ["D4-05", "D4-06", "D4-07", "D4-08"]
    rows = {row["case_id"]: row for row in run["observations"]}
    assert rows["D4-01"]["judge_status"] == "evaluation error"
    assert rows["D4-03"]["judge_status"] == "missing from run"
    assert rows["D4-03"]["human_status"].startswith("not paired")


def test_calibrate_rejects_a_run_that_is_not_a_fixed_response_run():
    run, _ = experiments.run_compare("replay", ["D4-01"], seed=1)

    with pytest.raises(runs.RunError, match="not a fixed-response judge run"):
        runs.resolve_fixed_run(run["run_id"])


def test_summary_distinguishes_modes_and_does_not_claim_review_completion(run_cli):
    code, out, _ = run_cli("summary")
    assert code == 0 and out.count("not run") == 9
    assert "Human review of fixed responses complete: NO" in out

    replay_judge()
    _, out, _ = run_cli("summary")
    live_block, replay_block = out.split("REPLAY evidence")
    assert "judge-fixed   not run" in live_block
    assert "judge-fixed   completed" in replay_block
    assert "0/8 confirmed and current" in out
