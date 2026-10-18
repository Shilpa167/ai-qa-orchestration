"""
Paths, loading and validation for the Day 4 inputs.

Path constants are read at call time (data.CASES_PATH, not a default
argument), so tests can point them at temporary copies.
"""

import json
import re

from day3_lab.data import PROJECT_ROOT, DataError, load_json, relative, sha256_file, sha256_text

DATASET_DIR = PROJECT_ROOT / "datasets" / "day4"
CASES_PATH = DATASET_DIR / "cases.json"
LABELS_PATH = DATASET_DIR / "human_labels.json"
CONFIRMED_REVIEWS_PATH = DATASET_DIR / "confirmed_reviews.json"
REPLAY_FIXTURES_PATH = DATASET_DIR / "replay_fixtures.json"
RUBRIC_PATH = PROJECT_ROOT / "rubrics" / "day4" / "rubric.json"
JUDGE_PROMPT_PATH = PROJECT_ROOT / "prompts" / "day4" / "judge.txt"
RESPONSE_PROMPT_PATHS = {
    "A": PROJECT_ROOT / "prompts" / "day4" / "response_a.txt",
    "B": PROJECT_ROOT / "prompts" / "day4" / "response_b.txt",
}
JUDGE_SCHEMA_PATH = PROJECT_ROOT / "schemas" / "day4_judge_output.schema.json"
BUSINESS_RULES_PATH = PROJECT_ROOT / "docs" / "business_rules.md"
REPORTS_DIR = PROJECT_ROOT / "reports" / "day4"

EXPECTED_CASE_IDS = tuple(f"D4-0{number}" for number in range(1, 9))
SPLITS = ("development", "holdout")
CASE_KEYS = (
    "case_id", "requirement_ids", "split", "user_input", "approved_context",
    "expected_behaviour", "prohibited_behaviour", "fixed_response", "expected_critical_violations",
)
LABEL_KEYS = ("case_id", "label_source", "human_confirmed", "scores", "verdict", "critical_violations", "reason")

# The meanings the Day 4 specification gives these IDs. validate prints them next
# to the heading in docs/business_rules.md so a trainer can see any mismatch.
DAY4_RULE_MEANINGS = {
    "BR02": "Employees may access only their own tickets and permitted profile fields.",
    "BR03": "Check current service status; do not invent a recovery time.",
    "BR04": "Use approved guidance for the correct device and version; clarify or escalate when evidence is missing or conflicting.",
    "BR05": "Never ask for passwords, OTPs or recovery codes; do not expose sensitive values in logs.",
    "BR06": "Ask for employee confirmation before creating a ticket.",
    "BR11": "Claim success only when a tool confirms it; represent pending, failed and denied outcomes honestly.",
}
# Recorded after reading docs/business_rules.md on 2026-10-18. Not changed silently.
KNOWN_RULE_CONFLICTS = {
    "BR02": "Week 1 BR02 covers tickets only; the Day 4 meaning adds 'permitted profile fields'. Compatible but broader.",
    "BR03": "Week 1 BR03 is 'A missing ticket returns 404'. The Day 4 meaning (service status, no invented recovery time) differs.",
    "BR04": "Week 1 BR04 is 'VPN service status has a defined status and update time'. The Day 4 meaning (approved device/version guidance) differs.",
}


def load_cases() -> dict:
    return load_json(CASES_PATH)


def load_labels() -> dict:
    return load_json(LABELS_PATH)


def load_replay_fixtures() -> dict:
    return load_json(REPLAY_FIXTURES_PATH)


def load_text(path) -> str:
    if not path.is_file():
        raise DataError(f"Required file not found: {relative(path)}")
    return path.read_text(encoding="utf-8")


def cases_by_id(cases_document: dict) -> dict:
    return {case["case_id"]: case for case in cases_document["cases"]}


def resolve_case_ids(requested: list[str], cases_document: dict) -> list[str]:
    """Turn ['all'] or a list of case IDs into an ordered list of known case IDs."""
    known = [case["case_id"] for case in cases_document["cases"]]
    if requested == ["all"]:
        return known
    unknown = [case_id for case_id in requested if case_id not in known]
    if unknown or "all" in requested:
        raise DataError(f"Unknown case ID(s) {unknown or ['all mixed with IDs']}. Use 'all' or any of: {', '.join(known)}")
    if len(set(requested)) != len(requested):
        raise DataError("A case ID was listed more than once.")
    return list(requested)


def case_context_sha256(case: dict) -> str:
    """Hash of everything a reviewer judges a response against (not the response itself)."""
    context = {key: case[key] for key in ("user_input", "approved_context", "expected_behaviour", "prohibited_behaviour", "requirement_ids")}
    return sha256_text(json.dumps(context, sort_keys=True, ensure_ascii=False))


def shared_input_groups(cases_document: dict) -> list[list[str]]:
    """Case IDs that share the same employee request and approved context."""
    groups = {}
    for case in cases_document["cases"]:
        groups.setdefault((case["user_input"], case["approved_context"]), []).append(case["case_id"])
    return [ids for ids in groups.values() if len(ids) > 1]


def dependency_notes(cases_document: dict, selected: list[str]) -> list[str]:
    notes = []
    for group in shared_input_groups(cases_document):
        present = [case_id for case_id in group if case_id in selected]
        if len(present) > 1:
            notes.append(
                f"{' and '.join(present)} share the same employee request and approved context. "
                "They are separately identified observations, not independent scenarios."
            )
    return notes


def business_rule_headings() -> dict:
    """{'BR01': 'The demo employee comes from ...', ...} read from docs/business_rules.md."""
    text = load_text(BUSINESS_RULES_PATH)
    return {match.group(1): match.group(2).strip() for match in re.finditer(r"^## (BR\d\d) — (.+)$", text, re.MULTILINE)}


def file_snapshot(path, include_text: bool = False) -> dict:
    snapshot = {"path": relative(path), "sha256": sha256_file(path)}
    if include_text:
        snapshot["text"] = path.read_text(encoding="utf-8")
    return snapshot


def validate_cases(cases_document: dict, critical_categories: tuple) -> list[str]:
    problems = []
    cases = cases_document.get("cases")
    if not isinstance(cases, list):
        return ["cases.json must contain a 'cases' list"]
    ids = [case.get("case_id") for case in cases if isinstance(case, dict)]
    if len(ids) != len(set(ids)):
        problems.append("duplicate case_id values")
    if tuple(ids) != EXPECTED_CASE_IDS:
        problems.append(f"case IDs must be exactly {list(EXPECTED_CASE_IDS)}, got {ids}")
    for case in cases:
        label = case.get("case_id", "?")
        if set(case) != set(CASE_KEYS):
            problems.append(f"{label}: keys must be {sorted(CASE_KEYS)}")
            continue
        if case["split"] not in SPLITS:
            problems.append(f"{label}: split must be one of {list(SPLITS)}")
        for key in ("user_input", "approved_context", "fixed_response"):
            if not isinstance(case[key], str) or not case[key].strip():
                problems.append(f"{label}: {key} must be non-empty text")
        for key in ("expected_behaviour", "prohibited_behaviour", "requirement_ids"):
            if not isinstance(case[key], list) or not case[key] or not all(isinstance(v, str) and v.strip() for v in case[key]):
                problems.append(f"{label}: {key} must be a non-empty list of text")
        for category in case["expected_critical_violations"]:
            if category not in critical_categories:
                problems.append(f"{label}: unknown critical category {category!r}")
        for rule in case["requirement_ids"]:
            if rule not in DAY4_RULE_MEANINGS:
                problems.append(f"{label}: requirement {rule} has no Day 4 meaning")
    return problems


def validate_references(cases_document: dict) -> tuple[list[str], list[str]]:
    """Return (problems, report lines) for the business-rule references."""
    headings = business_rule_headings()
    used = sorted({rule for case in cases_document["cases"] for rule in case["requirement_ids"]})
    problems, lines = [], []
    for rule in used:
        heading = headings.get(rule)
        if heading is None:
            problems.append(f"{rule} is referenced by a case but not defined in {relative(BUSINESS_RULES_PATH)}")
            lines.append(f"  {rule}: NOT DEFINED")
            continue
        lines.append(f"  {rule}: defined as '{heading}'")
        if rule in KNOWN_RULE_CONFLICTS:
            lines.append(f"        meaning difference (reported, not changed): {KNOWN_RULE_CONFLICTS[rule]}")
    return problems, lines


def validate_labels(labels_document: dict, cases_document: dict, compute_verdict) -> list[str]:
    """Proposed labels must be well-formed, unconfirmed and consistent with the PASS rule."""
    problems = []
    labels = labels_document.get("labels")
    if not isinstance(labels, list):
        return ["human_labels.json must contain a 'labels' list"]
    cases = cases_by_id(cases_document)
    if [label.get("case_id") for label in labels] != list(cases):
        problems.append("there must be exactly one proposed label per case, in case order")
    for label in labels:
        name = label.get("case_id", "?")
        if set(label) != set(LABEL_KEYS):
            problems.append(f"{name}: label keys must be {sorted(LABEL_KEYS)}")
            continue
        if label["label_source"] != "trainer_proposed":
            problems.append(f"{name}: label_source must be 'trainer_proposed'")
        if label["human_confirmed"] is not False:
            problems.append(
                f"{name}: human_confirmed must stay false in the proposals file. "
                "Confirmations are separate records made with the review-fixed command."
            )
        try:
            computed = compute_verdict(label["scores"], label["critical_violations"])
        except ValueError as error:
            problems.append(f"{name}: {error}")
            continue
        if computed["verdict"] != label["verdict"]:
            problems.append(f"{name}: proposed verdict {label['verdict']} disagrees with the PASS rule ({computed['verdict']})")
        if name in cases and sorted(label["critical_violations"]) != sorted(cases[name]["expected_critical_violations"]):
            problems.append(f"{name}: proposed critical violations differ from the case's expected_critical_violations")
        if not isinstance(label["reason"], str) or not label["reason"].strip():
            problems.append(f"{name}: reason must be non-empty")
    return problems


def validate_replay_fixtures(fixtures: dict, cases_document: dict) -> list[str]:
    problems = []
    if fixtures.get("format") != "day4-replay-fixtures-v1" or "AUTHORED" not in fixtures.get("notice", ""):
        problems.append("replay fixtures must declare format day4-replay-fixtures-v1 and an AUTHORED notice")
    case_ids = [case["case_id"] for case in cases_document["cases"]]
    for variant in ("A", "B"):
        missing = [case_id for case_id in case_ids if not fixtures.get("generation", {}).get(variant, {}).get(case_id)]
        if missing:
            problems.append(f"replay generation fixtures for prompt {variant} missing cases {missing}")
    texts = [entry.get("response_text") for entry in fixtures.get("judge", [])]
    if len(texts) != len(set(texts)):
        problems.append("replay judge fixtures contain duplicate response_text values")
    for entry in fixtures.get("judge", []):
        if not ("output" in entry) ^ ("raw_output" in entry):
            problems.append("each replay judge fixture needs exactly one of 'output' or 'raw_output'")
        if "raw_output" in entry and not entry.get("intentionally_invalid"):
            problems.append("a raw_output judge fixture must be marked intentionally_invalid")
    return problems
