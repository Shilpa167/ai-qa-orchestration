"""
Day 3: live-mode failures become ERROR, never a mock PASS.

No test here reaches the network. Two techniques are used:

1. A fake client object (works even without the openai package).
2. The real openai SDK with an in-memory httpx2 MockTransport, so the
   SDK's own request building, response parsing and error classes are
   exercised offline. Skipped automatically if the SDK is not installed.
"""

import json
from types import SimpleNamespace

import pytest

from day3_lab import data, runs
from day3_lab.mock_responses import MOCK_RESPONSES
from day3_lab.providers import OpenAIProvider, redact, render_prompt
from tests.day3.day3_helpers import read_run

FAKE_KEY = "sk-test-not-a-real-key-000000"
ENV = {"OPENAI_API_KEY": FAKE_KEY, "OPENAI_MODEL": "test-model"}
VALID_TEXT = json.dumps({"answer": "Outage confirmed; no ETA published.", "service_status": "outage", "recovery_time": None, "next_step": "Watch for updates."})


@pytest.fixture()
def case(cases_document):
    return data.cases_by_id(cases_document)["D3-01"]


def fake_response(status="completed", text=VALID_TEXT, refusal=None, usage=(10, 20, 30), reason=None):
    content = [SimpleNamespace(type="refusal", refusal=refusal)] if refusal else [SimpleNamespace(type="output_text", text=text)]
    return SimpleNamespace(
        status=status,
        model="test-model-2026",
        output=[SimpleNamespace(type="message", content=content)],
        output_text="" if refusal else text,
        usage=SimpleNamespace(input_tokens=usage[0], output_tokens=usage[1], total_tokens=usage[2]) if usage else None,
        incomplete_details=SimpleNamespace(reason=reason) if reason else None,
        error=None,
    )


class FakeClient:
    def __init__(self, result=None, raises=None):
        self.calls = []
        self.result = result
        self.raises = raises
        self.responses = SimpleNamespace(create=self.create)

    def create(self, **kwargs):
        self.calls.append(kwargs)
        if self.raises:
            raise self.raises
        return self.result


def provider_with(client, environ=ENV):
    return OpenAIProvider(environ=environ, client_factory=lambda key, timeout, retries: client)


def respond(provider, case):
    return provider.respond(case, render_prompt(data.load_prompt_template(), case))


@pytest.mark.parametrize(
    "environ, error_type",
    [({}, "missing_credentials"), ({"OPENAI_API_KEY": FAKE_KEY}, "missing_configuration"), ({"OPENAI_MODEL": "m"}, "missing_credentials")],
)
def test_missing_configuration_is_error_and_sends_nothing(case, environ, error_type):
    client = FakeClient(result=fake_response())

    result = respond(provider_with(client, environ), case)

    assert result.status == "error"
    assert result.error["type"] == error_type
    assert result.raw_response is None
    assert client.calls == []


def test_successful_call_uses_env_model_structured_outputs_and_real_usage(case):
    client = FakeClient(result=fake_response())

    result = respond(provider_with(client), case)

    assert result.status == "ok"
    assert result.raw_response == VALID_TEXT
    assert result.model == "test-model"
    assert result.token_usage == {"input_tokens": 10, "output_tokens": 20, "total_tokens": 30}
    sent = client.calls[0]
    assert sent["model"] == "test-model"
    assert sent["text"]["format"]["type"] == "json_schema"
    assert sent["text"]["format"]["strict"] is True
    assert sent["text"]["format"]["schema"]["additionalProperties"] is False
    assert case["question"] in sent["input"]


def test_missing_usage_is_recorded_as_null_not_invented(case):
    result = respond(provider_with(FakeClient(result=fake_response(usage=None))), case)

    assert result.status == "ok"
    assert result.token_usage is None


@pytest.mark.parametrize(
    "response, error_type",
    [
        (fake_response(refusal="I can't help with that."), "refusal"),
        (fake_response(status="incomplete", reason="max_output_tokens"), "incomplete_response"),
        (fake_response(status="failed"), "incomplete_response"),
        (fake_response(text=""), "malformed_response"),
    ],
)
def test_unusable_responses_are_errors(case, response, error_type):
    result = respond(provider_with(FakeClient(result=response)), case)

    assert result.status == "error"
    assert result.error["type"] == error_type
    assert result.raw_response is None


def test_exception_is_error_and_key_is_redacted(case):
    client = FakeClient(raises=TimeoutError(f"timed out using key {FAKE_KEY}"))

    result = respond(provider_with(client), case)

    assert result.status == "error"
    assert result.error["type"] == "timeout"
    assert FAKE_KEY not in json.dumps(result.provider_record())


@pytest.mark.parametrize(
    "echoed",
    [
        "sk-proj-ab****************wxyz",
        'sk-proj-ab****************wxy"',   # a stray quote pasted into the key
        '"sk-ab***yz"',
        "not-a-normal-key-at-all",
    ],
)
def test_masked_key_echo_in_a_401_message_is_fully_redacted(echoed):
    message = f"Error code: 401 - Incorrect API key provided: {echoed}. You can find your API key at https://platform.openai.com/account/api-keys."

    cleaned = redact(message)

    assert "Incorrect API key provided: [REDACTED]. You can find" in cleaned
    assert echoed not in cleaned
    assert '[REDACTED]"' not in cleaned


def test_live_run_without_credentials_is_error_never_mock(run_cli, tmp_path):
    out = tmp_path / "live"

    code, out_text, _ = run_cli("run", "--mode", "live", "--case", "D3-01", "--out", out)

    assert code == 1
    run = read_run(out / "run.json")
    item = run["items"][0]
    assert run["provider_mode"] == "live" and run["label"] == "LIVE"
    assert item["outcome"]["result"] == "ERROR"
    assert item["provider"]["error"]["type"] == "missing_credentials"
    assert item["raw_response"] is None and item["parsed_response"] is None
    assert json.dumps(MOCK_RESPONSES["D3-01"]) not in (out / "run.json").read_text(encoding="utf-8")
    assert "Nothing fell back to mock" in out_text


def test_live_error_item_can_never_become_pass_through_review(run_cli, tmp_path):
    out = tmp_path / "live"
    run_cli("run", "--mode", "live", "--case", "D3-01", "--out", out)

    code, _, err = run_cli("review", "--report", out / "run.json", "--case", "D3-01",
                           "--scores", "2", "2", "2", "2", "--critical", "no", "--note", "trying to pass it")

    assert code == 2
    assert "nothing to review" in err
    assert read_run(out / "run.json")["items"][0]["outcome"]["result"] == "ERROR"


# --- Real SDK, mocked network ------------------------------------------------

def sdk_provider(handler):
    openai = pytest.importorskip("openai")
    httpx2 = pytest.importorskip("httpx2")

    def factory(api_key, timeout, max_retries):
        return openai.OpenAI(
            api_key=api_key, base_url="https://api.invalid/v1", timeout=timeout, max_retries=0,
            http_client=httpx2.Client(transport=httpx2.MockTransport(handler)),
        )

    return OpenAIProvider(environ=ENV, client_factory=factory)


def sdk_body(text=VALID_TEXT, status="completed"):
    return {
        "id": "resp_test", "object": "response", "created_at": 0, "status": status, "model": "test-model-2026",
        "output": [{"type": "message", "id": "msg_test", "role": "assistant", "status": "completed",
                    "content": [{"type": "output_text", "text": text, "annotations": []}]}],
        "parallel_tool_calls": False, "tool_choice": "auto", "tools": [],
        "usage": {"input_tokens": 11, "input_tokens_details": {"cached_tokens": 0},
                  "output_tokens": 7, "output_tokens_details": {"reasoning_tokens": 0}, "total_tokens": 18},
    }


def test_sdk_success_offline(case):
    httpx2 = pytest.importorskip("httpx2")
    sent = {}

    def handler(request):
        sent["body"] = json.loads(request.content)
        return httpx2.Response(200, json=sdk_body())

    result = respond(sdk_provider(handler), case)

    assert result.status == "ok"
    assert result.raw_response == VALID_TEXT
    assert result.token_usage == {"input_tokens": 11, "output_tokens": 7, "total_tokens": 18}
    assert sent["body"]["text"]["format"]["strict"] is True


@pytest.mark.parametrize(
    "make_reply, error_type",
    [
        (lambda httpx2, request: (_ for _ in ()).throw(httpx2.ReadTimeout("slow", request=request)), "timeout"),
        (lambda httpx2, request: (_ for _ in ()).throw(httpx2.ConnectError("down", request=request)), "connection_error"),
        (lambda httpx2, request: httpx2.Response(401, json={"error": {"message": f"Incorrect API key provided: {FAKE_KEY}"}}), "authentication_error"),
        (lambda httpx2, request: httpx2.Response(429, json={"error": {"message": "slow down"}}), "rate_limited"),
        (lambda httpx2, request: httpx2.Response(500, json={"error": {"message": "boom"}}), "api_status_error"),
    ],
)
def test_sdk_failures_offline_are_errors(case, make_reply, error_type):
    httpx2 = pytest.importorskip("httpx2")

    result = respond(sdk_provider(lambda request: make_reply(httpx2, request)), case)

    assert result.status == "error"
    assert result.error["type"] == error_type
    assert FAKE_KEY not in json.dumps(result.provider_record())


def test_sdk_malformed_json_is_kept_as_evidence_and_fails_structure(case):
    # The API call worked but the text is not valid JSON: the provider succeeded,
    # so this is a structural FAIL with the raw text kept, not a PASS.
    httpx2 = pytest.importorskip("httpx2")
    provider = sdk_provider(lambda request: httpx2.Response(200, json=sdk_body(text='{"answer": "cut off')))

    result = respond(provider, case)
    item = runs.build_item(case, result, "prompt")

    assert item["raw_response"] == '{"answer": "cut off'
    assert item["structural"]["status"] == "FAIL"
    assert item["outcome"]["result"] == "FAIL"
