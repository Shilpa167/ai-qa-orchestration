"""
Plain helpers for the Day 4 tests: a fake OpenAI SDK client and small
response builders. No network, no real SDK needed.
"""

import json
from types import SimpleNamespace


def sdk_response(text, status="completed", model="returned-model-001", usage=(12, 8, 20), refusal=None):
    content = [SimpleNamespace(type="refusal", refusal=refusal)] if refusal else [SimpleNamespace(type="output_text", text=text)]
    return SimpleNamespace(
        status=status,
        model=model,
        output=[SimpleNamespace(type="message", content=content)],
        output_text="" if refusal else text,
        usage=SimpleNamespace(input_tokens=usage[0], output_tokens=usage[1], total_tokens=usage[2]) if usage else None,
        incomplete_details=None,
    )


def judge_json(response_id, scores=(2, 2, 2, 2), criticals=(), **extra):
    names = ("correctness", "relevance", "completeness", "safety_and_policy")
    body = {
        "response_id": response_id,
        "scores": dict(zip(names, scores)),
        "critical_violations": list(criticals),
        "reasons": {name: f"Evidence for {name}." for name in names},
        **extra,
    }
    return json.dumps(body)


class HttpError(Exception):
    """Stands in for an SDK status error: it carries status_code like openai.APIStatusError."""

    def __init__(self, status_code, message="error"):
        super().__init__(message)
        self.status_code = status_code


class FakeSDK:
    """Records every responses.create call. `script` decides each reply.

    script(kwargs, call_number) returns a response object or raises.
    """

    def __init__(self, script):
        self.script = script
        self.calls = []
        self.responses = SimpleNamespace(create=self._create)

    def _create(self, **kwargs):
        self.calls.append(kwargs)
        return self.script(kwargs, len(self.calls))

    @property
    def judge_calls(self):
        return [call for call in self.calls if "text" in call]

    @property
    def generation_calls(self):
        return [call for call in self.calls if "text" not in call]


def payload_of(judge_call) -> dict:
    """The JSON data block sent to the judge."""
    return json.loads(judge_call["input"].split("\n", 1)[1])


def factory_for(sdk, seen=None):
    def factory(api_key, timeout):
        if seen is not None:
            seen.append({"timeout": timeout})
        return sdk

    return factory


LIVE_ENV = {"OPENAI_API_KEY": "sk-test-not-a-real-key-123456", "OPENAI_MODEL": "configured-response-model"}
