"""
Response providers: where a raw response comes from.

    MockProvider    returns the reviewed fixed response for a case (labelled MOCK)
    OpenAIProvider  calls the OpenAI Responses API with structured outputs (labelled LIVE)

Both return a ProviderResult. A provider never validates or scores its own
output; that happens later in validation.py and decision.py.

The live provider NEVER falls back to mock. Missing credentials, a refusal,
a timeout, an incomplete or malformed response, or any API failure becomes
status "error", which the decision rule turns into ERROR, never PASS.
"""

import json
import os
import re
import time
from dataclasses import dataclass

from day3_lab.mock_responses import MOCK_RESPONSES
from day3_lab.validation import provider_schema

MOCK_LABEL = "MOCK"
LIVE_LABEL = "LIVE"

# Bounded network behaviour for live mode. The SDK retries connection errors,
# 408, 409, 429 and 5xx up to max_retries times with exponential backoff.
LIVE_TIMEOUT_SECONDS = 30.0
LIVE_MAX_RETRIES = 2
LIVE_MAX_OUTPUT_TOKENS = 800

_SECRET_PATTERN = re.compile(r"sk-[A-Za-z0-9_\-\*]{6,}")
# A 401 message echoes a masked copy of the rejected key after this phrase.
# Redact the whole echoed token, including characters outside the sk- pattern
# (for example a stray quote that was pasted into the key).
_KEY_ECHO_PATTERN = re.compile(r"(API key provided: )\S+?(?=\.?(?:\s|$))")


@dataclass
class ProviderResult:
    mode: str
    label: str
    model: str | None
    status: str  # "ok" or "error"
    raw_response: str | None
    error: dict | None
    elapsed_seconds: float
    token_usage: dict | None
    response_model: str | None = None

    def provider_record(self) -> dict:
        """The provider part of a run item (the raw response is stored separately)."""
        return {
            "mode": self.mode,
            "label": self.label,
            "model": self.model,
            "response_model": self.response_model,
            "status": self.status,
            "error": self.error,
            "elapsed_seconds": round(self.elapsed_seconds, 4),
            "token_usage": self.token_usage,
        }


def render_prompt(template: str, case: dict) -> str:
    """Fill the prompt template with one case's question and approved context."""
    context = json.dumps(case["approved_context"], indent=2, ensure_ascii=False)
    return template.replace("{{question}}", case["question"]).replace("{{approved_context}}", context)


class MockProvider:
    mode = "mock"
    label = MOCK_LABEL
    model = None

    def respond(self, case: dict, prompt_text: str) -> ProviderResult:
        started = time.perf_counter()
        fixture = MOCK_RESPONSES.get(case["case_id"])
        if fixture is None:
            return ProviderResult(
                mode=self.mode, label=self.label, model=None, status="error", raw_response=None,
                error={"type": "no_mock_fixture", "message": f"No reviewed mock response exists for {case['case_id']}."},
                elapsed_seconds=time.perf_counter() - started, token_usage=None,
            )
        raw = json.dumps(fixture, ensure_ascii=False)
        return ProviderResult(
            mode=self.mode, label=self.label, model=None, status="ok", raw_response=raw, error=None,
            elapsed_seconds=time.perf_counter() - started, token_usage=None,
        )


def redact(text: str, secret: str | None = None) -> str:
    """Remove anything that looks like an API key from an error message."""
    if secret:
        text = text.replace(secret, "[REDACTED]")
    text = _SECRET_PATTERN.sub("[REDACTED]", text)
    return _KEY_ECHO_PATTERN.sub(r"\1[REDACTED]", text)


def classify_exception(exc: Exception) -> str:
    """Name the kind of failure, using the SDK's documented error classes when available."""
    try:
        import openai
    except ImportError:
        openai = None
    if openai is not None:
        checks = (
            (openai.APITimeoutError, "timeout"),
            (openai.APIConnectionError, "connection_error"),
            (openai.AuthenticationError, "authentication_error"),
            (openai.RateLimitError, "rate_limited"),
            (openai.APIStatusError, "api_status_error"),
            (openai.APIError, "api_error"),
        )
        for error_class, name in checks:
            if isinstance(exc, error_class):
                return name
    if isinstance(exc, TimeoutError):
        return "timeout"
    return "unexpected_error"


def _default_client_factory(api_key: str, timeout: float, max_retries: int):
    from openai import OpenAI  # imported here so mock mode never needs the SDK

    return OpenAI(api_key=api_key, timeout=timeout, max_retries=max_retries)


class OpenAIProvider:
    """OpenAI Responses API adapter.

    Reads OPENAI_API_KEY and OPENAI_MODEL from the environment. No model name
    is hard-coded. The key is passed to the SDK and never stored, printed or
    written to a report.
    """

    mode = "live"
    label = LIVE_LABEL

    def __init__(self, environ=None, client_factory=None, timeout=LIVE_TIMEOUT_SECONDS,
                 max_retries=LIVE_MAX_RETRIES, max_output_tokens=LIVE_MAX_OUTPUT_TOKENS):
        self.environ = os.environ if environ is None else environ
        self.client_factory = client_factory or _default_client_factory
        self.timeout = timeout
        self.max_retries = max_retries
        self.max_output_tokens = max_output_tokens
        self.model = (self.environ.get("OPENAI_MODEL") or "").strip() or None
        self._client = None

    def _error(self, started: float, error_type: str, message: str, **details) -> ProviderResult:
        error = {"type": error_type, "message": message, **details}
        return ProviderResult(
            mode=self.mode, label=self.label, model=self.model, status="error", raw_response=None,
            error=error, elapsed_seconds=time.perf_counter() - started, token_usage=None,
        )

    def respond(self, case: dict, prompt_text: str) -> ProviderResult:
        started = time.perf_counter()
        api_key = (self.environ.get("OPENAI_API_KEY") or "").strip()
        if not api_key:
            return self._error(started, "missing_credentials", "OPENAI_API_KEY is not set. No request was sent. See docs/day3_notes.md, 'Live API setup'.")
        if not self.model:
            return self._error(started, "missing_configuration", "OPENAI_MODEL is not set. No request was sent. See docs/day3_notes.md, 'Live API setup'.")

        try:
            if self._client is None:
                self._client = self.client_factory(api_key, self.timeout, self.max_retries)
        except ImportError:
            return self._error(started, "sdk_unavailable", 'The openai package is not installed. Install it with: python -m pip install -e ".[dev,live]"')

        try:
            response = self._client.responses.create(
                model=self.model,
                input=prompt_text,
                max_output_tokens=self.max_output_tokens,
                text={
                    "format": {
                        "type": "json_schema",
                        "name": "service_desk_response",
                        "schema": provider_schema(),
                        "strict": True,
                    }
                },
            )
        except Exception as exc:  # every failure is evidence, never a pass
            details = {}
            status_code = getattr(exc, "status_code", None)
            if status_code is not None:
                details["http_status"] = status_code
            request_id = getattr(exc, "request_id", None)
            if request_id:
                details["request_id"] = request_id
            return self._error(started, classify_exception(exc), redact(f"{type(exc).__name__}: {exc}", api_key), **details)

        return self._interpret(started, response)

    def _interpret(self, started: float, response) -> ProviderResult:
        usage = _token_usage(getattr(response, "usage", None))
        response_model = getattr(response, "model", None)

        def error(error_type, message, **details):
            result = self._error(started, error_type, message, **details)
            result.token_usage = usage
            result.response_model = response_model
            return result

        status = getattr(response, "status", None)
        if status != "completed":
            reason = getattr(getattr(response, "incomplete_details", None), "reason", None)
            api_error = getattr(response, "error", None)
            message = f"Response status was {status!r}, not 'completed'."
            if reason:
                message += f" Incomplete reason: {reason}."
            if api_error is not None:
                message += f" API error: {getattr(api_error, 'message', api_error)}."
            return error("incomplete_response", message)

        refusals = []
        for output in getattr(response, "output", None) or []:
            if getattr(output, "type", None) != "message":
                continue
            for content in getattr(output, "content", None) or []:
                if getattr(content, "type", None) == "refusal":
                    refusals.append(getattr(content, "refusal", ""))
        if refusals:
            return error("refusal", "The model refused to answer.", refusal_text=" ".join(refusals))

        raw = getattr(response, "output_text", None)
        if not isinstance(raw, str) or not raw:
            return error("malformed_response", "The response contained no output text.")

        return ProviderResult(
            mode=self.mode, label=self.label, model=self.model, status="ok", raw_response=raw, error=None,
            elapsed_seconds=time.perf_counter() - started, token_usage=usage, response_model=response_model,
        )


def _token_usage(usage) -> dict | None:
    """Copy the provider's own token counts. None when the provider gave none."""
    if usage is None:
        return None
    counts = {name: getattr(usage, name, None) for name in ("input_tokens", "output_tokens", "total_tokens")}
    if all(value is None for value in counts.values()):
        return None
    return counts


def make_provider(mode: str):
    if mode == "mock":
        return MockProvider()
    if mode == "live":
        return OpenAIProvider()
    raise ValueError(f"unknown provider mode {mode!r}")
