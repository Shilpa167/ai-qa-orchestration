"""
Calibration: how a fixed-response judge run compares with CONFIRMED,
CURRENT human reviews of the same responses.

A confirmed review is paired with a judge assessment only if both refer to
the same response text, case context and rubric (by hash). Proposed labels
are never treated as human reviews. They appear only in a separate section
marked PROVISIONAL.

With zero valid pairs, agreement is "unavailable". It is never 0% or 100%.
"""

from day3_lab.data import sha256_text
from training_day4 import data, reporting, reviews, rubric, runs


def _human_for(obs: dict, case_reviews: list, run_rubric_sha: str) -> tuple[str, dict | None]:
    matching = [review for review in case_reviews
                if review["binding"].get("response_sha256") == obs["response_sha256"]
                and review["binding"].get("case_context_sha256") == obs["case_context_sha256"]
                and review["binding"].get("rubric_sha256") == run_rubric_sha]
    if matching:
        return "confirmed", matching[-1]
    if case_reviews:
        return "stale or mismatched", None
    return "unconfirmed", None


def _row(case_id, split, obs, human_status, human) -> dict:
    evaluation = (obs or {}).get("judge") or {}
    valid = evaluation.get("evaluation_status") == "valid"
    return {
        "case_id": case_id,
        "split": split,
        "response_id": obs["response_id"] if obs else None,
        "judge_status": "valid" if valid else ("missing from run" if obs is None else "evaluation error"),
        "judge_errors": evaluation.get("validation_errors", []) if obs else ["case not evaluated in this run"],
        "judge_scores": evaluation["assessment"]["scores"] if valid else None,
        "judge_criticals": evaluation["assessment"]["critical_violations"] if valid else None,
        "judge_verdict": evaluation["computed"]["verdict"] if valid else None,
        "human_status": human_status,
        "human_review_id": human["review_id"] if human else None,
        "human_reviewer": human["reviewer"] if human else None,
        "human_scores": human["scores"] if human else None,
        "human_criticals": human["critical_violations"] if human else None,
        "human_verdict": human["verdict"] if human else None,
        "status": "ok",
    }


def compare_rows(rows: list[dict], score_key: str, critical_key: str, verdict_key: str, usable) -> dict:
    """Agreement statistics over rows where the judge is valid and `usable(row)` is true."""
    pairs = [row for row in rows if row["judge_status"] == "valid" and usable(row)]
    agreement = sum(1 for row in pairs if row["judge_verdict"] == row[verdict_key])
    return {
        "valid_pairs": len(pairs),
        "verdict_agreement": {"count": agreement, "denominator": len(pairs)} if pairs else "unavailable (no valid pairs)",
        "false_passes": [row["case_id"] for row in pairs if row["judge_verdict"] == "PASS" and row[verdict_key] == "FAIL"],
        "false_fails": [row["case_id"] for row in pairs if row["judge_verdict"] == "FAIL" and row[verdict_key] == "PASS"],
        "dimension_disagreements": {
            dimension: [f"{row['case_id']} (judge {row['judge_scores'][dimension]}, label {row[score_key][dimension]})"
                        for row in pairs if row["judge_scores"][dimension] != row[score_key][dimension]]
            for dimension in rubric.DIMENSIONS
        },
        "critical_disagreements": [
            f"{row['case_id']} (judge {row['judge_criticals'] or 'none'}, label {row[critical_key] or 'none'})"
            for row in pairs if sorted(row["judge_criticals"]) != sorted(row[critical_key])
        ],
    }


def calibrate(selector: str):
    source, source_dir = runs.resolve_fixed_run(selector)
    cases_document = data.load_cases()
    cases = data.cases_by_id(cases_document)
    run_rubric_sha = source["inputs"]["rubric"]["sha256"]
    by_case = {}
    for review in reviews.load_confirmed()["reviews"]:
        by_case.setdefault(review["case_id"], []).append(review)
    observations = {obs["case_id"]: obs for obs in source["observations"]}
    proposals = {label["case_id"]: label for label in data.load_labels()["labels"]}

    rows = []
    for case_id, case in cases.items():
        obs = observations.get(case_id)
        if obs is None:
            human_status, human = "not paired: case missing from source run", None
        else:
            human_status, human = _human_for(obs, by_case.get(case_id, []), run_rubric_sha)
        row = _row(case_id, case["split"], obs, human_status, human)
        proposal = proposals.get(case_id)
        applies = proposal is not None and obs is not None and obs["response_sha256"] == sha256_text(case["fixed_response"])
        row["proposed_applies"] = applies
        row["proposed_scores"] = proposal["scores"] if applies else None
        row["proposed_criticals"] = proposal["critical_violations"] if applies else None
        row["proposed_verdict"] = proposal["verdict"] if applies else None
        rows.append(row)

    splits = {}
    for split in data.SPLITS:
        split_rows = [row for row in rows if row["split"] == split]
        splits[split] = {
            "cases": len(split_rows),
            "confirmed_coverage": {"confirmed": sum(row["human_status"] == "confirmed" for row in split_rows), "of": len(split_rows)},
            "unconfirmed": [row["case_id"] for row in split_rows if row["human_status"] == "unconfirmed"],
            "stale_or_mismatched": [row["case_id"] for row in split_rows if row["human_status"] == "stale or mismatched"],
            "evaluation_errors": [row["case_id"] for row in split_rows if row["judge_status"] != "valid"],
            "confirmed_human": compare_rows(split_rows, "human_scores", "human_criticals", "human_verdict",
                                            lambda row: row["human_status"] == "confirmed"),
            "provisional_vs_proposed": compare_rows(split_rows, "proposed_scores", "proposed_criticals", "proposed_verdict",
                                                    lambda row: row["proposed_applies"]),
        }

    run, run_dir = runs.create_run("calibrate", source["mode"], source["evidence_label"], {
        "source_run": {"run_id": source["run_id"], "mode": source["mode"], "path": f"{source_dir.as_posix()}/run.json",
                       "run_json_sha256": data.sha256_file(source_dir / "run.json"), "selector": selector},
        "inputs": {
            "dataset": {**data.file_snapshot(data.CASES_PATH), "version": cases_document.get("dataset_version")},
            "proposed_labels": data.file_snapshot(data.LABELS_PATH),
            "confirmed_reviews": data.file_snapshot(data.CONFIRMED_REVIEWS_PATH),
            "rubric": rubric.rubric_snapshot(),
            "source_run_rubric_sha256": run_rubric_sha,
        },
        "scope_note": ("Replay calibration is a workflow demonstration with authored judge outputs. It is NOT validation of a live judge."
                       if source["mode"] == "replay" else
                       "Eight fixed responses demonstrate the calibration workflow. They do not establish production reliability."),
        "dataset_notes": data.dependency_notes(cases_document, list(cases)),
        "splits": splits,
    })
    run["observations"] = rows
    runs.finalise(run, run_dir)
    reporting.write_results(run, run_dir)
    return run, run_dir, source
