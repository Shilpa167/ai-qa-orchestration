"""
Where responses and judge outputs come from.

Live:   the OpenAI Responses API (openai SDK 3.x, `client.responses.create`),
        with the same client pattern Day 3 verified.
Replay: authored teaching fixtures in datasets/day4/replay_fixtures.json.

Both expose the same small interface:
    generator.generate(variant, prompt_text, case, repetition) -> CallResult
    judge_backend.complete(judge_request)                       -> CallResult

A live failure is recorded as an error. Nothing ever falls back to replay.
"""

import importlib.util
import json
import os
import time
from dataclasses import asdict, dataclass, field

from day3_lab.providers import classify_exception, redact
from training_day4 import data
from training_day4.judge import provider_judge_schema

REQUEST_TIMEOUT_SECONDS = 60.0
MAX_ATTEMPTS = 3                    # total attempts per call, including the first
BACKOFF_SECONDS = (2.0, 4.0)        # waits before attempt 2 and attempt 3
GENERATION_MAX_OUTPUT_TOKENS = 400
JUDGE_MAX_OUTPUT_TOKENS = 600
ACCESS_CHECK_MAX_OUTPUT_TOKENS = 16
TRANSIENT_ERROR_TYPES = ("timeout", "connection_error", "rate_limited")

REPLAY_LABEL = "REPLAY: authored teaching fixtures, not live observations"
LIVE_LABEL = "LIVE: OpenAI API observations"


@dataclass
class CallResult:
    status: str                      # "ok" or "error"
    text: str | None
    error: dict | None
    source: str                      # "live" or "replay"
    requested_model: str | None = None
    returned_model: str | None = None
    attempts: list = field(default_factory=list)
    latency_seconds: float | None = None   # None for replay: no measured latency exists
    usage: dict | None = None              # None when the provider reported none

    def record(self) -> dict:
        record = asdict(self)
        record["attempt_count"] = len(self.attempts)
        record["retries"] = max(len(self.attempts) - 1, 0)
        return record


def generation_request(prompt_text: str, case: dict) -> dict:
    """The ONLY inputs a response generator receives: prompt, employee request, approved context."""
    return {
        "instructions": prompt_text,
        "input": f"Employee request:\n{case['user_input']}\n\nApproved context:\n{case['approved_context']}",
    }


GENERATION_INPUT_FORMAT = "Employee request:\\n{user_input}\\n\\nApproved context:\\n{approved_context}"


# --- Live ---------------------------------------------------------------------

def _default_client_factory(api_key: str, timeout: float):
    from openai import OpenAI

    # max_retries=0: the SDK's own retries are disabled so this module's
    # bounded retry loop is the only one, and every attempt is counted.
    return OpenAI(api_key=api_key, timeout=timeout, max_retries=0)


QUOTE_CHARACTERS = "\"'‘’“”`"


def key_format_problems(key: str) -> list[str]:
    """Describe characters that can never appear in an API key. Never returns the key itself."""
    problems = []
    if any(character in QUOTE_CHARACTERS for character in key):
        problems.append("it contains a quote character (often pasted in with the key)")
    if any(character.isspace() for character in key):
        problems.append("it contains whitespace")
    if not key.isascii():
        problems.append("it contains a non-ASCII character")
    return problems


def _is_transient(error_type: str, http_status) -> bool:
    if error_type in TRANSIENT_ERROR_TYPES:
        return True
    return isinstance(http_status, int) and (http_status >= 500 or http_status in (408, 409))


class LiveClient:
    """Reads OPENAI_API_KEY, OPENAI_MODEL and optional OPENAI_JUDGE_MODEL. The key is never stored."""

    def __init__(self, environ=None, client_factory=None, sleep=time.sleep, clock=time.perf_counter):
        self.environ = os.environ if environ is None else environ
        self.client_factory = client_factory or _default_client_factory
        self.sleep = sleep
        self.clock = clock
        self._client = None
        self.response_model = (self.environ.get("OPENAI_MODEL") or "").strip() or None
        judge_model = (self.environ.get("OPENAI_JUDGE_MODEL") or "").strip() or None
        self.judge_model = judge_model or self.response_model
        self.judge_model_source = "OPENAI_JUDGE_MODEL" if judge_model else "OPENAI_MODEL (OPENAI_JUDGE_MODEL is unset)"

    def config_errors(self) -> list[dict]:
        errors = []
        key = (self.environ.get("OPENAI_API_KEY") or "").strip()
        if not key:
            errors.append({"type": "missing_credentials", "message": "OPENAI_API_KEY is not set. No request was sent."})
        else:
            problems = key_format_problems(key)
            if problems:
                errors.append({"type": "malformed_credentials", "message": (
                    "OPENAI_API_KEY is set but " + "; ".join(problems) + ". These can never be part of a valid key, "
                    "so no request was sent. Set it again with single quotes and nothing else inside them. The key is not shown.")})
        if not self.response_model:
            errors.append({"type": "missing_configuration", "message": "OPENAI_MODEL is not set. No request was sent."})
        if self.client_factory is _default_client_factory and importlib.util.find_spec("openai") is None:
            errors.append({"type": "sdk_unavailable", "message": 'The openai package is not installed: python -m pip install -e ".[dev,live]"'})
        return errors

    def config_record(self) -> dict:
        return {
            "response_model": self.response_model,
            "judge_model": self.judge_model,
            "judge_model_source": self.judge_model_source,
            "request_timeout_seconds": REQUEST_TIMEOUT_SECONDS,
            "max_attempts_per_call": MAX_ATTEMPTS,
            "retry_policy": "retry only timeouts, connection errors, rate limits, HTTP 408/409/5xx; SDK retries disabled",
        }

    def _sdk(self):
        if self._client is None:
            self._client = self.client_factory(self.environ["OPENAI_API_KEY"].strip(), REQUEST_TIMEOUT_SECONDS)
        return self._client

    def call(self, model: str, instructions: str, input_text: str, max_output_tokens: int, text_format: dict | None = None) -> CallResult:
        kwargs = {"model": model, "instructions": instructions, "input": input_text, "max_output_tokens": max_output_tokens}
        if text_format is not None:
            kwargs["text"] = {"format": text_format}
        api_key = (self.environ.get("OPENAI_API_KEY") or "").strip()
        attempts = []
        for attempt in range(1, MAX_ATTEMPTS + 1):
            started = self.clock()
            try:
                response = self._sdk().responses.create(**kwargs)
            except Exception as exc:
                error_type = classify_exception(exc)
                http_status = getattr(exc, "status_code", None)
                attempts.append({"attempt": attempt, "status": "error", "error_type": error_type,
                                 "http_status": http_status, "seconds": round(self.clock() - started, 3)})
                if _is_transient(error_type, http_status) and attempt < MAX_ATTEMPTS:
                    self.sleep(BACKOFF_SECONDS[attempt - 1])
                    continue
                error = {"type": error_type, "message": redact(f"{type(exc).__name__}: {exc}", api_key)}
                if http_status is not None:
                    error["http_status"] = http_status
                return CallResult("error", None, error, "live", requested_model=model, attempts=attempts)
            seconds = round(self.clock() - started, 3)
            attempts.append({"attempt": attempt, "status": "ok", "seconds": seconds})
            return self._interpret(response, model, attempts, seconds)
        raise AssertionError("unreachable")

    @staticmethod
    def _interpret(response, model, attempts, seconds) -> CallResult:
        usage = getattr(response, "usage", None)
        usage = None if usage is None else {
            name: getattr(usage, name, None) for name in ("input_tokens", "output_tokens", "total_tokens")
        }
        if usage is not None and all(value is None for value in usage.values()):
            usage = None
        common = {"requested_model": model, "returned_model": getattr(response, "model", None),
                  "attempts": attempts, "latency_seconds": seconds, "usage": usage}

        status = getattr(response, "status", None)
        if status != "completed":
            reason = getattr(getattr(response, "incomplete_details", None), "reason", None)
            return CallResult("error", None, {"type": "incomplete_response", "message": f"status={status!r}, reason={reason!r}"}, "live", **common)
        for output in getattr(response, "output", None) or []:
            for content in getattr(output, "content", None) or []:
                if getattr(content, "type", None) == "refusal":
                    return CallResult("error", None, {"type": "refusal", "message": redact(getattr(content, "refusal", "") or "")}, "live", **common)
        text = getattr(response, "output_text", None)
        if not isinstance(text, str) or not text.strip():
            return CallResult("error", None, {"type": "malformed_response", "message": "no output text"}, "live", **common)
        return CallResult("ok", redact(text), None, "live", **common)


class LiveGenerator:
    def __init__(self, client: LiveClient):
        self.client = client

    def settings(self) -> dict:
        # Only settings every Responses model accepts are sent. Sampling settings
        # such as temperature are not set, so the model default applies.
        return {"model": self.client.response_model, "max_output_tokens": GENERATION_MAX_OUTPUT_TOKENS,
                "sampling": "model default (no temperature or top_p sent)"}

    def generate(self, variant: str, prompt_text: str, case: dict, repetition: int) -> CallResult:
        request = generation_request(prompt_text, case)
        return self.client.call(self.client.response_model, request["instructions"], request["input"], GENERATION_MAX_OUTPUT_TOKENS)


class LiveJudge:
    def __init__(self, client: LiveClient):
        self.client = client

    def settings(self) -> dict:
        return {"model": self.client.judge_model, "model_source": self.client.judge_model_source,
                "max_output_tokens": JUDGE_MAX_OUTPUT_TOKENS, "structured_output": "json_schema, strict"}

    def complete(self, request: dict) -> CallResult:
        text_format = {"type": "json_schema", "name": "day4_judge_assessment", "schema": provider_judge_schema(), "strict": True}
        return self.client.call(self.client.judge_model, request["instructions"], request["input"], JUDGE_MAX_OUTPUT_TOKENS, text_format)


# --- Replay -------------------------------------------------------------------

class ReplayGenerator:
    """Returns authored responses. It reads only the fixtures file, never labels or answer keys."""

    def __init__(self, fixtures: dict):
        self.fixtures = fixtures

    def settings(self) -> dict:
        return {"model": None, "source": data.relative(data.REPLAY_FIXTURES_PATH), "note": REPLAY_LABEL}

    def generate(self, variant: str, prompt_text: str, case: dict, repetition: int) -> CallResult:
        variants = self.fixtures.get("generation", {}).get(variant, {}).get(case["case_id"])
        if not variants:
            return CallResult("error", None, {"type": "no_replay_fixture", "message": f"No authored response for prompt {variant}, {case['case_id']}."},
                              "replay", attempts=[{"attempt": 1, "status": "error", "error_type": "no_replay_fixture"}])
        text = variants[repetition % len(variants)]
        return CallResult("ok", text, None, "replay", attempts=[{"attempt": 1, "status": "ok", "source": "replay fixture"}])


class ReplayJudge:
    """Looks up an authored judge output by the exact candidate text.

    It never reads proposed or confirmed labels. A response with no authored
    judge output becomes an evaluation error, not a guess.
    """

    def __init__(self, fixtures: dict):
        self.by_text = {entry["response_text"]: entry for entry in fixtures.get("judge", [])}

    def settings(self) -> dict:
        return {"model": None, "source": data.relative(data.REPLAY_FIXTURES_PATH), "note": REPLAY_LABEL}

    def complete(self, request: dict) -> CallResult:
        payload = request["payload"]
        entry = self.by_text.get(payload["candidate_response"])
        attempts = [{"attempt": 1, "status": "ok", "source": "replay fixture"}]
        if entry is None:
            return CallResult("error", None, {"type": "no_replay_fixture", "message": "No authored judge output for this response text."},
                              "replay", attempts=[{"attempt": 1, "status": "error", "error_type": "no_replay_fixture"}])
        if "raw_output" in entry:
            text = entry["raw_output"].replace("{{response_id}}", payload["response_id"])
        else:
            text = json.dumps({"response_id": payload["response_id"], **entry["output"]}, ensure_ascii=False)
        return CallResult("ok", text, None, "replay", attempts=attempts)
