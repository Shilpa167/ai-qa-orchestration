"""
Human reviews. These are the ONLY functions that create human assessments,
and they are called only by the review-fixed and review-generated
commands, with scores a named person typed. Judge scores and proposed
labels never pass through here.

Fixed-response reviews  -> datasets/day4/confirmed_reviews.json (append-only)
Generated-answer reviews -> reports/day4/<run_id>/human_reviews.json (run.json is never changed)

Each review is bound to hashes of what was reviewed. If the response, the
case context or the rubric changes, the review becomes STALE and is not
used. It is never moved to the new version automatically.
"""

import uuid

from day3_lab.data import sha256_text
from day3_lab.decision import utc_now
from training_day4 import data, rubric, runs

REVIEW_KEYS = ("review_id", "case_id", "label_source", "human_confirmed", "reviewer", "reviewed_at", "scores",
               "critical_violations", "total", "verdict", "reason", "binding")


class ReviewInputError(ValueError):
    """Raised when a review cannot be recorded. Nothing is saved."""


def parse_inputs(reviewer, scores, criticals, reason) -> tuple[str, dict, list, str]:
    if not isinstance(reviewer, str) or not reviewer.strip():
        raise ReviewInputError("--reviewer must be your actual name or identifier")
    if "<" in reviewer or ">" in reviewer:
        raise ReviewInputError("--reviewer still contains a <placeholder>; enter your actual name")
    if not isinstance(reason, str) or not reason.strip() or "<" in reason:
        raise ReviewInputError("--reason must be a non-empty explanation (not a <placeholder>)")
    scores = list(scores)
    if len(scores) != len(rubric.DIMENSIONS):
        raise ReviewInputError(f"--scores needs {len(rubric.DIMENSIONS)} values: {' '.join(rubric.DIMENSIONS)}")
    criticals = [] if list(criticals) == ["none"] else list(criticals)
    try:
        checked_scores = rubric.check_scores(dict(zip(rubric.DIMENSIONS, scores)))
        checked_criticals = rubric.check_criticals(criticals)
    except rubric.ScoreError as error:
        raise ReviewInputError(str(error)) from error
    return reviewer.strip(), checked_scores, checked_criticals, reason.strip()


def _record(case_id, reviewer, scores, criticals, reason, binding) -> dict:
    computed = rubric.compute_verdict(scores, criticals)
    return {
        "review_id": "hr-" + uuid.uuid4().hex[:10],
        "case_id": case_id,
        "label_source": "human_confirmed",
        "human_confirmed": True,
        "reviewer": reviewer,
        "reviewed_at": utc_now(),
        "scores": scores,
        "critical_violations": criticals,
        "total": computed["total"],
        "verdict": computed["verdict"],
        "reason": reason,
        "binding": binding,
    }


# --- Fixed responses ----------------------------------------------------------

def fixed_binding(case: dict) -> dict:
    snapshot = rubric.rubric_snapshot()
    return {
        "response_sha256": sha256_text(case["fixed_response"]),
        "case_context_sha256": data.case_context_sha256(case),
        "rubric_sha256": snapshot["sha256"],
        "rubric_version": snapshot["version"],
    }


def load_confirmed() -> dict:
    return data.load_json(data.CONFIRMED_REVIEWS_PATH)


def add_fixed_review(case_id: str, reviewer, scores, criticals, reason) -> dict:
    cases = data.cases_by_id(data.load_cases())
    if case_id not in cases:
        raise ReviewInputError(f"Unknown case {case_id!r}")
    reviewer, scores, criticals, reason = parse_inputs(reviewer, scores, criticals, reason)
    proposals = {label["case_id"]: label for label in data.load_labels()["labels"]}
    record = _record(case_id, reviewer, scores, criticals, reason, fixed_binding(cases[case_id]))
    proposal = proposals.get(case_id)
    if proposal:
        record["proposal_comparison"] = {
            "proposed_scores": proposal["scores"],
            "proposed_critical_violations": proposal["critical_violations"],
            "proposed_verdict": proposal["verdict"],
            "matches_proposal": proposal["scores"] == scores and sorted(proposal["critical_violations"]) == criticals,
        }
    record["entered_with"] = "python -m training_day4 review-fixed"
    document = load_confirmed()
    document["reviews"].append(record)
    runs.write_json(data.CONFIRMED_REVIEWS_PATH, document)
    return record


def fixed_review_state(review: dict, case: dict) -> tuple[str, list[str]]:
    """('current', []) or ('stale', [what changed])."""
    expected = fixed_binding(case)
    changed = [key for key in ("response_sha256", "case_context_sha256", "rubric_sha256") if review["binding"].get(key) != expected[key]]
    return ("stale" if changed else "current"), changed


def fixed_review_status(cases_document: dict) -> dict:
    """{case_id: {'current': latest current review or None, 'stale': [reviews]}}."""
    status = {case["case_id"]: {"current": None, "stale": []} for case in cases_document["cases"]}
    cases = data.cases_by_id(cases_document)
    for review in load_confirmed()["reviews"]:
        case = cases.get(review.get("case_id"))
        if case is None:
            continue
        state, changed = fixed_review_state(review, case)
        if state == "current":
            status[case["case_id"]]["current"] = review  # later records supersede earlier ones
        else:
            status[case["case_id"]]["stale"].append({**review, "stale_because": changed})
    return status


def validate_confirmed(document: dict) -> list[str]:
    problems = []
    if not isinstance(document.get("reviews"), list):
        return ["confirmed_reviews.json must contain a 'reviews' list"]
    for review in document["reviews"]:
        name = review.get("review_id", "?")
        missing = [key for key in REVIEW_KEYS if key not in review]
        if missing:
            problems.append(f"{name}: missing {missing}")
            continue
        if review["label_source"] != "human_confirmed" or review["human_confirmed"] is not True:
            problems.append(f"{name}: must be a human_confirmed record")
        if not str(review["reviewer"]).strip():
            problems.append(f"{name}: reviewer is empty")
        try:
            computed = rubric.compute_verdict(review["scores"], review["critical_violations"])
        except rubric.ScoreError as error:
            problems.append(f"{name}: {error}")
            continue
        if computed["verdict"] != review["verdict"] or computed["total"] != review["total"]:
            problems.append(f"{name}: stored verdict/total disagree with the PASS rule")
    return problems


# --- Generated responses ------------------------------------------------------

def generated_reviews_path(run_dir):
    return run_dir / "human_reviews.json"


def load_generated(run_dir, run_id: str) -> dict:
    path = generated_reviews_path(run_dir)
    if path.is_file():
        return data.load_json(path)
    return {"format": "day4-generated-reviews-v1", "run_id": run_id,
            "notice": "Human reviews of generated responses. run.json is never modified by reviews.", "reviews": []}


def add_generated_review(run_id: str, response_id: str, reviewer, scores, criticals, reason) -> dict:
    run, run_dir = runs.load_run(run_id)
    if run["experiment"] not in ("compare", "repeat"):
        raise ReviewInputError(f"{run_id} is a {run['experiment']} run. Review fixed responses with review-fixed.")
    if not run["finalised"]:
        raise ReviewInputError(f"{run_id} is unfinished and cannot be reviewed.")
    matches = [obs for obs in run["observations"] if obs.get("response_id") == response_id]
    if not matches:
        raise ReviewInputError(f"No response {response_id!r} in {run_id}. Response IDs are listed in its results.md.")
    obs = matches[0]
    if not isinstance(obs.get("response_text"), str):
        raise ReviewInputError(f"{response_id} has no generated response (generation failed), so there is nothing to review.")
    if obs["response_sha256"] != sha256_text(obs["response_text"]):
        raise ReviewInputError(f"{response_id}: stored response no longer matches its hash. Refusing to review changed evidence.")
    reviewer, scores, criticals, reason = parse_inputs(reviewer, scores, criticals, reason)
    snapshot = rubric.rubric_snapshot()
    binding = {
        "run_id": run_id,
        "response_id": response_id,
        "response_sha256": obs["response_sha256"],
        "case_context_sha256": obs["case_context_sha256"],
        "rubric_sha256": snapshot["sha256"],
        "rubric_version": snapshot["version"],
    }
    record = _record(obs["case_id"], reviewer, scores, criticals, reason, binding)
    record["prompt_variant"] = obs["prompt_variant"]
    record["repetition"] = obs["repetition"]
    record["entered_with"] = "python -m training_day4 review-generated"
    document = load_generated(run_dir, run_id)
    document["reviews"].append(record)
    runs.write_json(generated_reviews_path(run_dir), document)
    return record


def generated_review_status(run: dict, run_dir) -> dict:
    """{response_id: {'current': review or None, 'stale': [...]}} for every generated response in a run."""
    observations = {obs["response_id"]: obs for obs in run["observations"] if obs.get("response_source") == "generated"}
    status = {response_id: {"current": None, "stale": []} for response_id in observations}
    current_rubric = rubric.rubric_snapshot()["sha256"]
    for review in load_generated(run_dir, run["run_id"])["reviews"]:
        obs = observations.get(review["binding"].get("response_id"))
        if obs is None:
            continue
        fresh = (review["binding"]["response_sha256"] == obs.get("response_sha256")
                 and review["binding"]["response_sha256"] == (sha256_text(obs["response_text"]) if obs.get("response_text") else None)
                 and review["binding"]["rubric_sha256"] == current_rubric)
        if fresh:
            status[obs["response_id"]]["current"] = review
        else:
            status[obs["response_id"]]["stale"].append(review)
    return status
