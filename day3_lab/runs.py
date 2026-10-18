"""
Building, saving and reloading run.json.

A run is one execution of the lab: some cases, one provider, one output
directory. run.json is the evidence. run.html is a readable view of it.
"""

import json
import os
import subprocess
import uuid
from pathlib import Path

from day3_lab import data
from day3_lab.decision import decide_outcome, empty_review, utc_now
from day3_lab.validation import check_structure

RUN_FORMAT = "day3-run-v1"
RUN_FILES = ("run.json", "run.html", "clinic_notes.md")


class OutputExistsError(Exception):
    """Raised instead of overwriting an earlier run."""


def ensure_fresh_output(out_dir: Path) -> Path:
    """Refuse to reuse a directory that already holds a run. Create it otherwise."""
    out_dir = Path(out_dir)
    existing = [name for name in RUN_FILES if (out_dir / name).exists()]
    if existing:
        raise OutputExistsError(
            f"{out_dir.as_posix()} already contains an earlier run ({', '.join(existing)}). "
            "Nothing was overwritten. Choose a fresh --out directory."
        )
    out_dir.mkdir(parents=True, exist_ok=True)
    return out_dir


def git_info() -> dict:
    """Current commit and whether the working tree has uncommitted changes."""

    def git(*args):
        return subprocess.run(
            ["git", *args], cwd=data.PROJECT_ROOT, capture_output=True, text=True, timeout=10, check=True
        ).stdout.strip()

    try:
        commit = git("rev-parse", "HEAD")
        dirty = bool(git("status", "--porcelain"))
        return {"commit": commit, "dirty": dirty}
    except (OSError, subprocess.SubprocessError):
        return {"commit": "unavailable", "dirty": None}


def new_run_id(kind: str) -> str:
    stamp = utc_now().replace("-", "").replace(":", "")
    return f"{kind}-{stamp}-{uuid.uuid4().hex[:6]}"


def build_item(case: dict, result, prompt_text: str | None, item_id: str | None = None, label: str | None = None) -> dict:
    """Combine one case, one provider result and its structural check into a run item."""
    item = {
        "item_id": item_id or case["case_id"],
        "case_id": case["case_id"],
        "label": label or result.label,
        "case": case,
        "rendered_prompt_sha256": data.sha256_text(prompt_text) if prompt_text is not None else None,
        "provider": result.provider_record(),
        "raw_response": result.raw_response,
        "response_sha256": data.sha256_text(result.raw_response) if result.raw_response is not None else None,
        "parsed_response": None,
        "structural": {"status": "NOT_RUN", "findings": []},
        "human_review": empty_review(),
    }
    if result.status == "ok":
        structure = check_structure(result.raw_response)
        item["parsed_response"] = structure["parsed"]
        item["structural"] = {"status": structure["status"], "findings": structure["findings"]}
    item["outcome"] = decide_outcome(item)
    return item


def summarize(items: list[dict]) -> dict:
    counts = {"PASS": 0, "FAIL": 0, "ERROR": 0, "REVIEW_PENDING": 0}
    for item in items:
        counts[item["outcome"]["result"]] = counts.get(item["outcome"]["result"], 0) + 1
    return {"items": len(items), "outcomes": counts}


def build_run(kind: str, mode: str, label: str, label_note: str, model, items: list[dict],
              cases_document: dict, rubric: dict, extra: dict | None = None) -> dict:
    """Wrap items with everything needed to reproduce and audit the run."""
    run = {
        "format": RUN_FORMAT,
        "run_id": new_run_id(kind),
        "created_at": utc_now(),
        "kind": kind,
        "label": label,
        "label_note": label_note,
        "provider_mode": mode,
        "model": model,
        "git": git_info(),
        "prompt": {"path": data.relative(data.PROMPT_PATH), "sha256": data.sha256_file(data.PROMPT_PATH)},
        "dataset": {
            "path": data.relative(data.CASES_PATH),
            "sha256": data.sha256_file(data.CASES_PATH),
            "version": cases_document.get("dataset_version"),
        },
        "rubric": {
            "path": data.relative(data.RUBRIC_PATH),
            "sha256": data.sha256_file(data.RUBRIC_PATH),
            "version": rubric.get("version"),
            "dimension_order": rubric.get("dimension_order"),
            "scales": rubric.get("scales"),
            "decision_rule": rubric.get("decision_rule"),
            "review_scope": rubric.get("review_scope"),
        },
        "response_schema": {
            "path": data.relative(data.RESPONSE_SCHEMA_PATH),
            "sha256": data.sha256_file(data.RESPONSE_SCHEMA_PATH),
        },
        "items": items,
    }
    if extra:
        run.update(extra)
    run["summary"] = summarize(items)
    return run


def _write_atomic(path: Path, text: str) -> None:
    """Write to a temporary file first, then swap it in, so a crash never leaves half a file."""
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_text(text, encoding="utf-8")
    os.replace(temporary, path)


def save_run(run: dict, out_dir: Path) -> tuple[Path, Path]:
    """Write run.json and regenerate run.html next to it."""
    from day3_lab.report import render_html  # local import keeps module roles separate

    out_dir = Path(out_dir)
    run["summary"] = summarize(run["items"])
    json_path = out_dir / "run.json"
    html_path = out_dir / "run.html"
    _write_atomic(json_path, json.dumps(run, indent=2, ensure_ascii=False) + "\n")
    _write_atomic(html_path, render_html(run))
    return json_path, html_path


def load_run(path: Path) -> dict:
    run = data.load_json(path)
    if not isinstance(run, dict) or run.get("format") != RUN_FORMAT:
        raise data.DataError(f"{Path(path).as_posix()} is not a Day 3 run report ({RUN_FORMAT})")
    return run
