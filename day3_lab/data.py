"""
Loading and checking the Day 3 inputs.

The cases and the rubric are the test oracle: they say what a good answer
must and must not do. This module only reads and checks them. It never
changes an expectation.
"""

import hashlib
import json
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent

CASES_PATH = PROJECT_ROOT / "datasets" / "day3" / "cases.json"
RUBRIC_PATH = PROJECT_ROOT / "rubrics" / "day3" / "rubric.json"
PROMPT_PATH = PROJECT_ROOT / "prompts" / "day3" / "response_v1.txt"
RESPONSE_SCHEMA_PATH = PROJECT_ROOT / "schemas" / "day3_response.schema.json"

# The original files supplied with the Day 3 pack. The copies above must match them.
SOURCE_CASES_PATH = PROJECT_ROOT / "day3_materials" / "day3_cases.json"
SOURCE_RUBRIC_PATH = PROJECT_ROOT / "day3_materials" / "day3_rubric.json"

SERVICE_STATUSES = ("operational", "degraded", "outage", "unknown")
EVALUATION_METHODS = ("schema", "human_rubric")
CASE_KEYS = (
    "case_id",
    "category",
    "question",
    "approved_context",
    "expected_behaviour",
    "prohibited_behaviour",
    "evaluation_method",
    "requirement_ids",
)
CONTEXT_KEYS = ("device", "service_status", "recovery_time", "guidance")


class DataError(Exception):
    """Raised when an input file is missing or cannot be read as JSON."""


def relative(path: Path) -> str:
    """Return path relative to the project root, with forward slashes, for reports."""
    try:
        return Path(path).resolve().relative_to(PROJECT_ROOT).as_posix()
    except ValueError:
        return Path(path).as_posix()


def sha256_bytes(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def sha256_text(text: str) -> str:
    return sha256_bytes(text.encode("utf-8"))


def sha256_file(path: Path) -> str:
    return sha256_bytes(Path(path).read_bytes())


def load_json(path: Path):
    """Read one JSON file. A missing or broken file stops the program with a clear message."""
    path = Path(path)
    if not path.is_file():
        raise DataError(f"Required file not found: {relative(path)}")
    try:
        with open(path, "r", encoding="utf-8") as file:
            return json.load(file)
    except json.JSONDecodeError as error:
        raise DataError(f"{relative(path)} is not valid JSON: {error}") from error


def load_cases(path: Path = CASES_PATH) -> dict:
    return load_json(path)


def load_rubric(path: Path = RUBRIC_PATH) -> dict:
    return load_json(path)


def load_prompt_template(path: Path = PROMPT_PATH) -> str:
    if not Path(path).is_file():
        raise DataError(f"Required file not found: {relative(path)}")
    return Path(path).read_text(encoding="utf-8")


def cases_by_id(cases_document: dict) -> dict:
    """Turn the list of cases into a dictionary keyed by case_id."""
    return {case["case_id"]: case for case in cases_document["cases"]}


def validate_cases(cases_document: dict) -> list[str]:
    """Return every problem found in the cases file. An empty list means valid."""
    problems = []
    if not isinstance(cases_document, dict) or not isinstance(cases_document.get("cases"), list):
        return ["cases file must be an object with a 'cases' list"]
    if not cases_document.get("dataset_version"):
        problems.append("cases file has no dataset_version")
    if cases_document.get("synthetic") is not True:
        problems.append("cases file must declare synthetic: true")

    seen_ids = set()
    for position, case in enumerate(cases_document["cases"], start=1):
        label = case.get("case_id", f"case #{position}") if isinstance(case, dict) else f"case #{position}"
        if not isinstance(case, dict):
            problems.append(f"{label}: is not an object")
            continue

        missing = [key for key in CASE_KEYS if key not in case]
        extra = [key for key in case if key not in CASE_KEYS]
        if missing:
            problems.append(f"{label}: missing keys {missing}")
        if extra:
            problems.append(f"{label}: unexpected keys {extra}")

        case_id = case.get("case_id")
        if not isinstance(case_id, str) or not case_id.strip():
            problems.append(f"{label}: case_id must be a non-empty string")
        elif case_id in seen_ids:
            problems.append(f"{label}: duplicate case_id")
        else:
            seen_ids.add(case_id)

        if not isinstance(case.get("question"), str) or not case.get("question", "").strip():
            problems.append(f"{label}: question must be a non-empty string")

        for list_key in ("expected_behaviour", "prohibited_behaviour", "requirement_ids", "evaluation_method"):
            value = case.get(list_key)
            if not isinstance(value, list) or not value or not all(isinstance(item, str) and item.strip() for item in value):
                problems.append(f"{label}: {list_key} must be a non-empty list of strings")

        for method in case.get("evaluation_method") or []:
            if method not in EVALUATION_METHODS:
                problems.append(f"{label}: unknown evaluation_method {method!r}")

        problems.extend(_validate_context(label, case.get("approved_context")))
    return problems


def _validate_context(label: str, context) -> list[str]:
    if not isinstance(context, dict):
        return [f"{label}: approved_context must be an object"]
    problems = []
    missing = [key for key in CONTEXT_KEYS if key not in context]
    extra = [key for key in context if key not in CONTEXT_KEYS]
    if missing:
        problems.append(f"{label}: approved_context missing keys {missing}")
    if extra:
        problems.append(f"{label}: approved_context unexpected keys {extra}")
    if context.get("service_status") not in SERVICE_STATUSES:
        problems.append(f"{label}: approved_context.service_status {context.get('service_status')!r} is not one of {list(SERVICE_STATUSES)}")
    if context.get("recovery_time") is not None and not isinstance(context.get("recovery_time"), str):
        problems.append(f"{label}: approved_context.recovery_time must be a string or null")
    if context.get("device") is not None and not isinstance(context.get("device"), str):
        problems.append(f"{label}: approved_context.device must be a string or null")
    if not isinstance(context.get("guidance"), str) or not context.get("guidance", "").strip():
        problems.append(f"{label}: approved_context.guidance must be a non-empty string")
    return problems


def validate_rubric(rubric: dict, dimensions: tuple, supported_version: str) -> list[str]:
    """Check the rubric has exactly the dimensions and 0/1/2 scales the decision rule uses."""
    if not isinstance(rubric, dict):
        return ["rubric must be an object"]
    problems = []
    if rubric.get("version") != supported_version:
        problems.append(f"rubric version {rubric.get('version')!r} is not the supported {supported_version!r}")
    if tuple(rubric.get("dimension_order") or ()) != dimensions:
        problems.append(f"rubric dimension_order must be {list(dimensions)}")
    scales = rubric.get("scales") or {}
    for dimension in dimensions:
        levels = scales.get(dimension)
        if not isinstance(levels, dict) or sorted(levels) != ["0", "1", "2"]:
            problems.append(f"rubric scale for {dimension!r} must define levels 0, 1 and 2")
    if not rubric.get("decision_rule"):
        problems.append("rubric has no decision_rule")
    return problems


def validate_consistency(cases_document: dict, rubric: dict) -> list[str]:
    """Checks that need both files: versions agree and every case can be reviewed."""
    problems = []
    if cases_document.get("dataset_version") != rubric.get("version"):
        problems.append(
            f"dataset_version {cases_document.get('dataset_version')!r} does not match rubric version {rubric.get('version')!r}"
        )
    for case in cases_document.get("cases", []):
        if isinstance(case, dict) and "human_rubric" not in (case.get("evaluation_method") or []):
            problems.append(f"{case.get('case_id')}: evaluation_method must include human_rubric")
    return problems


def compare_with_source(copy_path: Path, source_path: Path) -> str | None:
    """Return a problem if the copy differs from the supplied source file, else None."""
    if not Path(source_path).is_file():
        return None
    if sha256_file(copy_path) != sha256_file(source_path):
        return f"{relative(copy_path)} differs from the supplied {relative(source_path)}"
    return None
