"""
Day 4 live mode, exercised only with a fake SDK client (no network).

Live failures stay errors and never become replay results; retries are
bounded and only for transient errors; low scores are never retried.
"""

import json

import pytest

from tests.day4.day4_helpers import LIVE_ENV, FakeSDK, HttpError, factory_for, judge_json, payload_of, sdk_response
from training_day4 import clients, data, experiments


def judge_one(script, env=LIVE_ENV, case_ids=("D4-01",)):
    sdk, sleeps = FakeSDK(script), []
    run, run_dir = experiments.run_judge_fixed("live", list(case_ids), environ=env, client_factory=factory_for(sdk), sleep=sleeps.append)
    return sdk, sleeps, run, run_dir


def valid_judge(kwargs, n):
    return sdk_response(judge_json(payload_of(kwargs)["response_id"]))


def test_missing_credentials_record_an_error_and_never_use_replay(run_cli):
    code, out, _ = run_cli("judge", "--mode", "live", "--cases", "all")

    assert code == 1
    assert "Nothing fell back to replay." in out
    run_json = next(data.REPORTS_DIR.glob("judge-fixed-live-*/run.json"))
    run = json.loads(run_json.read_text(encoding="utf-8"))
    assert run["mode"] == "live" and run["status"] == "failed" and run["observations"] == []
    assert {error["type"] for error in run["run_errors"]} >= {"missing_credentials", "missing_configuration"}
    assert "REPLAY" not in run["evidence_label"] and "replay_fixtures" not in run["config"]


def test_transient_errors_are_retried_a_bounded_number_of_times():
    def script(kwargs, n):
        if n <= 2:
            raise HttpError(503, "service unavailable")
        return valid_judge(kwargs, n)

    sdk, sleeps, run, _ = judge_one(script)
    call = run["observations"][0]["judge"]["call"]

    assert len(sdk.calls) == 3
    assert call["attempt_count"] == 3 and call["retries"] == 2 and call["status"] == "ok"
    assert [attempt["http_status"] for attempt in call["attempts"][:2]] == [503, 503]
    assert sleeps == list(clients.BACKOFF_SECONDS)
    assert run["counts"]["judge"]["retries"] == 2


def test_retries_stop_at_the_limit_and_the_error_is_kept():
    sdk, _, run, _ = judge_one(lambda kwargs, n: (_ for _ in ()).throw(TimeoutError("slow")))
    obs = run["observations"][0]

    assert len(sdk.calls) == clients.MAX_ATTEMPTS
    assert obs["judge"]["call"]["error"]["type"] == "timeout"
    assert obs["judge"]["evaluation_status"] == "error" and obs["status"] == "error"
    assert run["status"] == "failed"


def test_non_transient_error_is_not_retried_and_the_key_is_redacted():
    message = f"Incorrect API key provided: {LIVE_ENV['OPENAI_API_KEY']}."
    sdk, _, run, run_dir = judge_one(lambda kwargs, n: (_ for _ in ()).throw(HttpError(401, message)))

    assert len(sdk.calls) == 1
    assert run["observations"][0]["judge"]["call"]["error"]["http_status"] == 401
    for name in ("run.json", "results.md"):
        assert LIVE_ENV["OPENAI_API_KEY"] not in (run_dir / name).read_text(encoding="utf-8")


def test_a_low_score_is_never_retried():
    sdk, _, run, _ = judge_one(lambda kwargs, n: sdk_response(judge_json(payload_of(kwargs)["response_id"], scores=(0, 0, 0, 0))))

    assert len(sdk.calls) == 1
    assert run["observations"][0]["judge"]["computed"]["verdict"] == "FAIL"


def test_malformed_judge_output_is_not_retried():
    sdk, _, run, _ = judge_one(lambda kwargs, n: sdk_response("I think it is fine."))

    assert len(sdk.calls) == 1
    assert run["observations"][0]["judge"]["evaluation_status"] == "error"
    assert run["observations"][0]["judge"]["raw_output_sanitised"] == "I think it is fine."


def test_judge_model_defaults_to_the_response_model_and_says_so():
    sdk, _, run, _ = judge_one(valid_judge)

    assert run["config"]["judge_model"] == "configured-response-model"
    assert "OPENAI_JUDGE_MODEL is unset" in run["config"]["judge_model_source"]
    assert sdk.calls[0]["model"] == "configured-response-model"
    assert run["observations"][0]["judge"]["call"]["returned_model"] == "returned-model-001"
    assert run["observations"][0]["judge"]["call"]["usage"] == {"input_tokens": 12, "output_tokens": 8, "total_tokens": 20}


def test_separate_judge_model_is_used_only_for_judging():
    env = {**LIVE_ENV, "OPENAI_JUDGE_MODEL": "configured-judge-model"}

    def script(kwargs, n):
        if "text" in kwargs:
            return valid_judge(kwargs, n)
        return sdk_response("An answer.")

    sdk = FakeSDK(script)
    experiments.run_repeat("live", "A", ["D4-01"], 2, environ=env, client_factory=factory_for(sdk), sleep=lambda s: None)

    assert {call["model"] for call in sdk.generation_calls} == {"configured-response-model"}
    assert {call["model"] for call in sdk.judge_calls} == {"configured-judge-model"}


def test_sdk_retries_are_disabled_in_the_default_client(monkeypatch):
    openai = pytest.importorskip("openai")
    seen = {}
    monkeypatch.setattr(openai, "OpenAI", lambda **kwargs: seen.update(kwargs) or object())

    clients._default_client_factory("sk-test-not-a-real-key-123456", 30.0)

    assert seen["max_retries"] == 0 and seen["timeout"] == 30.0


@pytest.mark.parametrize("judge_model, expected_calls", [(None, 1), ("configured-judge-model", 2)])
def test_access_check_calls_each_distinct_model_once(judge_model, expected_calls):
    env = dict(LIVE_ENV, **({"OPENAI_JUDGE_MODEL": judge_model} if judge_model else {}))
    sdk = FakeSDK(lambda kwargs, n: sdk_response("OK"))

    run, _ = experiments.run_access_check(environ=env, client_factory=factory_for(sdk), sleep=lambda s: None)

    assert len(sdk.calls) == expected_calls
    assert run["status"] == "completed"
    if expected_calls == 1:
        assert run["observations"][0]["roles"] == ["response model", "judge model"]


def test_generation_failure_is_kept_and_not_judged():
    def script(kwargs, n):
        if "text" not in kwargs:
            raise HttpError(400, "bad request")
        return valid_judge(kwargs, n)

    sdk = FakeSDK(script)
    run, _ = experiments.run_repeat("live", "B", ["D4-06"], 3, environ=LIVE_ENV, client_factory=factory_for(sdk), sleep=lambda s: None)

    assert len(run["observations"]) == 3 and sdk.judge_calls == []
    assert all(obs["generation"]["status"] == "error" and obs["response_text"] is None for obs in run["observations"])
    assert run["counts"]["generation"]["failed"] == 3 and run["status"] == "failed"


def test_offline_guard_blocks_real_network_connections():
    import socket

    # Match the message rather than importing conftest (importing it would load a second copy).
    with pytest.raises(RuntimeError, match="Day 4 tests are offline"):
        socket.create_connection(("api.openai.com", 443), timeout=1)
