"""
Run directories and run.json evidence under reports/day4/.

Each experiment gets a new directory named after its run ID, created with
exist_ok=False so existing evidence can never be overwritten. run.json is
written once at the start with finalised=false and once at the end with
finalised=true. A run that stops part-way stays unfinalised, and the
calibration lookup refuses to use it.
"""

import json
import os
import time
from pathlib import Path

from day3_lab.decision import utc_now
from day3_lab.runs import git_info, new_run_id
from training_day4 import data

RUN_FORMAT = "day4-run-v1"
JUDGE_FIXED = "judge-fixed"


class RunError(Exception):
    """Raised for missing, unfinished, corrupted or ambiguous runs, and for overwrite attempts."""


def reports_dir() -> Path:
    return Path(data.REPORTS_DIR)


def create_run(experiment: str, mode: str, label: str, extra: dict) -> tuple[dict, Path]:
    run_id = new_run_id(f"{experiment}-{mode}")
    run_dir = reports_dir() / run_id
    try:
        run_dir.mkdir(parents=True, exist_ok=False)
    except FileExistsError as error:
        raise RunError(f"{run_dir.as_posix()} already exists. Existing evidence is never overwritten.") from error
    run = {
        "format": RUN_FORMAT,
        "run_id": run_id,
        "experiment": experiment,
        "mode": mode,
        "evidence_label": label,
        "created_at": utc_now(),
        "created_at_ns": time.time_ns(),  # precise ordering for latest-fixed
        "finished_at": None,
        "finalised": False,
        "git": git_info(),
        **extra,
        "run_errors": [],
        "observations": [],
    }
    write_json(run_dir / "run.json", run)
    return run, run_dir


def write_json(path: Path, value) -> None:
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    os.replace(temporary, path)


def run_status(run: dict) -> str:
    """completed, partially completed, failed or unfinished."""
    if not run.get("finalised"):
        return "unfinished"
    observations = run.get("observations", [])
    if run.get("run_errors") or not observations:
        return "failed"
    problems = [obs for obs in observations if obs.get("status") != "ok"]
    if not problems:
        return "completed"
    return "failed" if len(problems) == len(observations) else "partially completed"


def finalise(run: dict, run_dir: Path) -> dict:
    run["finished_at"] = utc_now()
    run["finalised"] = True
    run["counts"] = count_calls(run)
    run["status"] = run_status(run)
    write_json(run_dir / "run.json", run)
    return run


def count_calls(run: dict) -> dict:
    """Count calls (each with attempts and retries) separately from evaluations and verdicts."""
    empty = {"calls": 0, "attempts": 0, "succeeded": 0, "failed": 0, "retries": 0}
    counts = {
        "observations": len(run["observations"]),
        "generation": dict(empty),
        "judge": dict(empty),
        "access_check": dict(empty),
        "evaluations": {"valid": 0, "errors": 0},
        "verdicts": {"PASS": 0, "FAIL": 0},
    }
    for obs in run["observations"]:
        calls = {"generation": obs.get("generation"), "judge": (obs.get("judge") or {}).get("call"), "access_check": obs.get("check")}
        for kind, call in calls.items():
            if not call:
                continue
            counts[kind]["calls"] += 1
            counts[kind]["attempts"] += call["attempt_count"]
            counts[kind]["retries"] += call["retries"]
            counts[kind]["succeeded" if call["status"] == "ok" else "failed"] += 1
        if "judge" not in obs:
            continue
        evaluation = obs["judge"]
        if evaluation and evaluation["evaluation_status"] == "valid":
            counts["evaluations"]["valid"] += 1
            counts["verdicts"][evaluation["computed"]["verdict"]] += 1
        else:
            counts["evaluations"]["errors"] += 1
    return counts


def load_run(run_id: str) -> tuple[dict, Path]:
    run_dir = reports_dir() / run_id
    path = run_dir / "run.json"
    if not path.is_file():
        raise RunError(f"No run {run_id!r} in {reports_dir().as_posix()}.")
    try:
        run = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as error:
        raise RunError(f"{path.as_posix()} is corrupted: {error}") from error
    for key in ("format", "run_id", "experiment", "mode", "created_at", "finalised", "observations"):
        if not isinstance(run, dict) or key not in run:
            raise RunError(f"{path.as_posix()} is corrupted: missing {key!r}")
    if run["format"] != RUN_FORMAT or run["run_id"] != run_id:
        raise RunError(f"{path.as_posix()} is not consistent Day 4 run evidence")
    return run, run_dir


def list_run_dirs() -> list[Path]:
    root = reports_dir()
    return sorted(path for path in root.iterdir() if path.is_dir()) if root.is_dir() else []


def resolve_fixed_run(selector: str) -> tuple[dict, Path]:
    """Return a finalised fixed-response judge run: 'latest-fixed' or an explicit run ID.

    'latest-fixed' looks only at the newest judge-fixed run. If that run is
    unfinished, corrupted or tied with another run, it is rejected. An older
    run is never substituted.
    """
    if selector != "latest-fixed":
        run, run_dir = load_run(selector)
        if run["experiment"] != JUDGE_FIXED:
            raise RunError(f"{selector} is a {run['experiment']} run, not a fixed-response judge run.")
        if not run["finalised"]:
            raise RunError(f"{selector} is unfinished (finalised=false) and cannot be calibrated.")
        return run, run_dir

    candidates = [path for path in list_run_dirs() if path.name.startswith(f"{JUDGE_FIXED}-")]
    if not candidates:
        raise RunError("No fixed-response judge run exists yet. Run: python -m training_day4 judge --mode replay --cases all")
    dated = []
    for path in candidates:
        run_json = path / "run.json"
        try:
            metadata = json.loads(run_json.read_text(encoding="utf-8"))
            created_at = metadata["created_at_ns"]
        except (OSError, ValueError, KeyError, TypeError) as error:
            raise RunError(f"Run metadata in {run_json.as_posix()} is unreadable or corrupted ({error}). "
                           "Refusing to guess which run is latest.") from error
        dated.append((created_at, path.name))
    dated.sort()
    newest_time = dated[-1][0]
    tied = [name for created, name in dated if created == newest_time]
    if len(tied) > 1:
        raise RunError(f"Ambiguous latest run: {tied} share the same creation time. Pass an explicit run ID.")
    run, run_dir = load_run(dated[-1][1])
    if not run["finalised"]:
        raise RunError(f"The latest fixed-response run {run['run_id']} is unfinished (finalised=false). "
                       "It is not replaced by an older run. Re-run judge or pass an explicit run ID.")
    return run, run_dir
