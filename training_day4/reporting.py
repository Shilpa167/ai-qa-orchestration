"""
Readable results.md for each run, and the summary command.

Unknown usage and timing are shown as "not measured (replay)" or
"not reported", never as zero. Replay evidence is labelled as authored.
"""

from pathlib import Path

from day3_lab.data import sha256_file
from training_day4 import data, rubric, runs

DIMS = rubric.DIMENSIONS
SHORT = {"correctness": "C", "relevance": "R", "completeness": "Cm", "safety_and_policy": "S"}


def cell(value) -> str:
    return str(value).replace("|", "\\|").replace("\n", " ")


def usage_text(call: dict | None, mode: str) -> str:
    if not call:
        return "-"
    if mode == "replay":
        return "not measured (replay)"
    return cell(call["usage"]) if call.get("usage") else "not reported"


def latency_text(call: dict | None, mode: str) -> str:
    if not call:
        return "-"
    if mode == "replay":
        return "not measured (replay)"
    return f"{call['latency_seconds']}s" if call.get("latency_seconds") is not None else "not reported"


def evaluation_cells(obs: dict) -> list[str]:
    evaluation = obs.get("judge") or {}
    if evaluation.get("evaluation_status") == "valid":
        scores = evaluation["assessment"]["scores"]
        return [*(str(scores[d]) for d in DIMS), str(evaluation["computed"]["total"]),
                ", ".join(evaluation["assessment"]["critical_violations"]) or "none", evaluation["computed"]["verdict"]]
    errors = "; ".join(evaluation.get("validation_errors") or ["no evaluation"])
    return ["-", "-", "-", "-", "-", "-", f"EVALUATION ERROR: {errors}"]


def header(run: dict) -> list[str]:
    config = run.get("config", {})
    lines = [
        f"# Day 4 {run['experiment']}: `{run['run_id']}`",
        "",
        f"> **{run['evidence_label']}**",
        "",
        f"- Mode: **{run['mode']}**. Status: **{run.get('status', 'unfinished')}**",
        f"- Created: {run['created_at']}. Finished: {run.get('finished_at')}",
        f"- Git commit: `{run['git']['commit']}`. Working tree dirty: {run['git']['dirty']}",
    ]
    inputs = run.get("inputs", {})
    if "dataset" in inputs:
        lines.append(f"- Dataset: `{inputs['dataset']['path']}` {inputs['dataset'].get('version')} (sha256 `{inputs['dataset']['sha256'][:12]}`)")
    if "rubric" in inputs:
        lines.append(f"- Rubric: {inputs['rubric']['version']} (sha256 `{inputs['rubric']['sha256'][:12]}`)")
    for name, prompt in inputs.get("prompts", {}).items():
        lines.append(f"- Prompt `{name}`: `{prompt['path']}` (sha256 `{prompt['sha256'][:12]}`)")
    if config.get("source") == "live":
        lines.append(f"- Response model: `{config.get('response_model')}`. Judge model: `{config.get('judge_model')}` "
                     f"(from {config.get('judge_model_source')})")
        lines.append(f"- Retry policy: {config.get('retry_policy')}; at most {config.get('max_attempts_per_call')} attempts per call")
    elif config.get("source") == "replay":
        lines.append(f"- Replay fixtures: `{config['replay_fixtures']['path']}` (sha256 `{config['replay_fixtures']['sha256'][:12]}`). "
                     "No model was called; no latency or token usage exists.")
    if config.get("generation_settings"):
        lines.append(f"- Generation settings: {cell(config['generation_settings'])}")
    if run.get("ordering"):
        lines.append(f"- A/B order seed: {run['ordering']['seed']}. {run['ordering']['note']}")
    for note in run.get("dataset_notes", []):
        lines.append(f"- Dataset dependency: {note}")
    for error in run.get("run_errors", []):
        lines.append(f"- **RUN ERROR** ({error['type']}): {error['message']}")
    counts = run.get("counts")
    if counts and run["experiment"] != "calibrate":
        if run.get("planned_calls"):
            lines.append(f"- Planned calls: {run['planned_calls']['generation']} generation, {run['planned_calls']['judge']} judge")
        for kind in ("generation", "judge", "access_check"):
            c = counts[kind]
            if c["calls"]:
                lines.append(f"- {kind} calls: {c['calls']} ({c['succeeded']} succeeded, {c['failed']} failed), "
                             f"{c['attempts']} attempts, {c['retries']} retries")
        if run["experiment"] != "access-check":
            lines.append(f"- Evaluations: {counts['evaluations']['valid']} valid, {counts['evaluations']['errors']} errors. "
                         f"Verdicts over valid evaluations: PASS {counts['verdicts']['PASS']}, FAIL {counts['verdicts']['FAIL']}")
    lines.append("")
    return lines


def observation_table(run: dict, with_variant: bool) -> list[str]:
    head = ["Order", "Case", "Split"] + (["Prompt", "Rep"] if with_variant else []) + \
           ["Response ID", "Response"] + [SHORT[d] for d in DIMS] + ["Total", "Critical", "Verdict"]
    lines = ["| " + " | ".join(head) + " |", "|" + " --- |" * len(head)]
    for obs in run["observations"]:
        response = obs.get("response_text")
        if response is None:
            error = (obs.get("generation") or {}).get("error") or {}
            response = f"GENERATION ERROR ({error.get('type')})"
        row = [str(obs["order"]), obs["case_id"], obs["split"]]
        if with_variant:
            row += [obs["prompt_variant"], str(obs["repetition"] + 1)]
        row += [f"`{obs['response_id']}`", cell(response)] + [cell(c) for c in evaluation_cells(obs)]
        lines.append("| " + " | ".join(row) + " |")
    return lines


def reasons_section(run: dict) -> list[str]:
    lines = ["## Judge reasons and call details", ""]
    for obs in run["observations"]:
        evaluation = obs.get("judge") or {}
        call = evaluation.get("call")
        lines.append(f"### {obs['observation_id']}: {obs['case_id']}"
                     + (f", prompt {obs['prompt_variant']}, repetition {obs['repetition'] + 1}" if obs.get("prompt_variant") else "")
                     + f" (`{obs['response_id']}`)")
        if obs.get("generation"):
            gen = obs["generation"]
            lines.append(f"- Generation: {gen['status']}, attempts {gen['attempt_count']}, latency {latency_text(gen, run['mode'])}, "
                         f"usage {usage_text(gen, run['mode'])}, returned model {gen.get('returned_model')}")
        if call:
            lines.append(f"- Judge call: {call['status']}, attempts {call['attempt_count']}, latency {latency_text(call, run['mode'])}, "
                         f"usage {usage_text(call, run['mode'])}, returned model {call.get('returned_model')}")
        if evaluation.get("evaluation_status") == "valid":
            for dimension in DIMS:
                lines.append(f"- {dimension} = {evaluation['assessment']['scores'][dimension]}: {cell(evaluation['assessment']['reasons'][dimension])}")
            if evaluation["computed"]["fail_reasons"]:
                lines.append(f"- FAIL because: {', '.join(evaluation['computed']['fail_reasons'])}")
        else:
            lines.append(f"- **Evaluation error:** {cell('; '.join(evaluation.get('validation_errors') or ['no evaluation']))}")
            if evaluation.get("raw_output_sanitised"):
                lines.append(f"- Raw judge output (sanitised): `{cell(evaluation['raw_output_sanitised'])}`")
        lines.append("")
    return lines


def compare_preference(per_variant: dict) -> str:
    """A provisional reading of machine assessments. Never forces a winner."""
    a, b = per_variant["A"], per_variant["B"]
    if a["errors"] or b["errors"]:
        return (f"Inconclusive: evaluation errors (A {a['errors']}, B {b['errors']}) leave the comparison incomplete.")
    if a["critical_observations"] and b["critical_observations"]:
        return "No recommendation: both prompts produced critical violations. Neither should be approved on this evidence."
    better, worse = ("A", "B") if a["PASS"] > b["PASS"] else ("B", "A")
    if a["PASS"] == b["PASS"]:
        return "Inconclusive: both prompts have the same number of judge passes."
    if per_variant[better]["critical_observations"] > per_variant[worse]["critical_observations"]:
        return "Inconclusive: the prompt with more passes also has more critical violations."
    return (f"Provisional preference: Prompt {better} ({per_variant[better]['PASS']} vs {per_variant[worse]['PASS']} judge passes). "
            "Machine assessments only. Not a final selection until humans review the generated answers.")


def per_variant_counts(run: dict) -> dict:
    result = {}
    for variant in ("A", "B"):
        rows = [obs for obs in run["observations"] if obs["prompt_variant"] == variant]
        valid = [obs for obs in rows if obs["status"] == "ok"]
        result[variant] = {
            "observations": len(rows),
            "PASS": sum(obs["judge"]["computed"]["verdict"] == "PASS" for obs in valid),
            "FAIL": sum(obs["judge"]["computed"]["verdict"] == "FAIL" for obs in valid),
            "errors": len(rows) - len(valid),
            "critical_observations": sum(bool(obs["judge"]["assessment"]["critical_violations"]) for obs in valid),
        }
    return result


def repeat_stats(run: dict) -> dict:
    stats = {}
    for case_id in run["cases_selected"]:
        rows = [obs for obs in run["observations"] if obs["case_id"] == case_id]
        valid = [obs for obs in rows if obs["status"] == "ok"]
        stats[case_id] = {
            "attempted": len(rows),
            "valid_evaluations": len(valid),
            "errors": len(rows) - len(valid),
            "passes": sum(obs["judge"]["computed"]["verdict"] == "PASS" for obs in valid),
            "score_ranges": {d: (f"{min(o['judge']['assessment']['scores'][d] for o in valid)}–"
                                 f"{max(o['judge']['assessment']['scores'][d] for o in valid)}") if valid else "n/a" for d in DIMS},
            "critical_violations": sorted({c for o in valid for c in o["judge"]["assessment"]["critical_violations"]}),
            "distinct_responses": len({o["response_sha256"] for o in rows if o.get("response_sha256")}),
        }
    return stats


def human_review_lines(run: dict, run_dir: Path) -> list[str]:
    from training_day4 import reviews

    status = reviews.generated_review_status(run, run_dir)
    reviewed = sum(1 for entry in status.values() if entry["current"])
    lines = [
        "## Human review of generated answers",
        "",
        f"Reviewed: **{reviewed} of {len(status)}** generated responses (at the time this file was written).",
        "Fixed-response labels are not reused for generated answers. To review one response:",
        "",
        "```",
        f"python -m training_day4 review-generated --run {run['run_id']} --response <response-id> --reviewer \"<your name>\" "
        "--scores <correctness> <relevance> <completeness> <safety_and_policy> --critical none --reason \"<why>\"",
        "```",
        "",
        "Reviews are saved to `human_reviews.json` in this run folder. `run.json` is not changed. "
        "`python -m training_day4 summary` shows the current review count.",
        "",
    ]
    return lines


def write_results(run: dict, run_dir: Path) -> Path:
    lines = header(run)
    experiment = run["experiment"]
    if experiment == "judge-fixed" and run["observations"]:
        lines += ["## Machine assessments of the fixed responses", "",
                  "These are judge scores, not human labels. Totals and verdicts are computed in code.", ""]
        lines += observation_table(run, with_variant=False) + [""] + reasons_section(run)
        lines += ["Next: `python -m training_day4 calibrate --run " + run["run_id"] + "`", ""]
    elif experiment == "compare" and run["observations"]:
        per_variant = per_variant_counts(run)
        lines += ["## Per-prompt counts (machine assessments)", "",
                  "| Prompt | Observations | PASS | FAIL | Evaluation errors | Observations with critical violations |",
                  "| --- | --- | --- | --- | --- | --- |"]
        for variant, c in per_variant.items():
            lines.append(f"| {variant} | {c['observations']} | {c['PASS']} | {c['FAIL']} | {c['errors']} | {c['critical_observations']} |")
        lines += ["", f"**{compare_preference(per_variant)}**", ""]
        if run["mode"] == "replay":
            lines += ["In replay mode this reading reflects hand-authored fixtures, not model behaviour. "
                      "It demonstrates the comparison workflow only.", ""]
        lines += [
                  "The judge never saw which prompt produced a response; prompt labels were mapped back in code.", "",
                  "## Responses and assessments", ""]
        lines += observation_table(run, with_variant=True) + [""] + human_review_lines(run, run_dir) + reasons_section(run)
    elif experiment == "repeat" and run["observations"]:
        lines += [f"## Repeat results: prompt {run['prompt_variant']}, {run['repetitions']} repetitions per case", "",
                  "Variation may come from response generation, from judging, or both. This experiment does not separate them. "
                  "A few successful observations do not guarantee future reliability.", ""]
        if run["mode"] == "replay":
            lines += ["Replay repeats use authored variants. They demonstrate the workflow only, not live-model variation.", ""]
        lines += ["| Case | Passed / attempted | Valid evaluations | Errors | Distinct responses | " + " | ".join(f"{SHORT[d]} range" for d in DIMS) + " | Critical |",
                  "|" + " --- |" * (6 + len(DIMS))]
        for case_id, s in repeat_stats(run).items():
            lines.append(f"| {case_id} | {s['passes']}/{s['attempted']} | {s['valid_evaluations']} | {s['errors']} | {s['distinct_responses']} | "
                         + " | ".join(s["score_ranges"][d] for d in DIMS) + f" | {', '.join(s['critical_violations']) or 'none'} |")
        lines += ["", "## Every observation", ""] + observation_table(run, with_variant=True) + [""]
        lines += human_review_lines(run, run_dir) + reasons_section(run)
    elif experiment == "access-check":
        lines += ["## Access check (billable preflight)", ""]
        for obs in run["observations"]:
            check = obs["check"]
            lines.append(f"- {', '.join(obs['roles'])} `{check['requested_model']}`: **{check['status']}**, "
                         f"returned model `{check.get('returned_model')}`, attempts {check['attempt_count']}, "
                         f"latency {latency_text(check, 'live')}, usage {usage_text(check, 'live')}"
                         + (f", error {check['error']['type']}: {cell(check['error']['message'])}" if check.get("error") else ""))
        lines.append("")
    elif experiment == "calibrate":
        lines += calibration_lines(run)
    (run_dir / "results.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    return run_dir / "results.md"


def _stats_lines(stats: dict, title: str) -> list[str]:
    agreement = stats["verdict_agreement"]
    agreement_text = agreement if isinstance(agreement, str) else f"{agreement['count']} of {agreement['denominator']} valid pairs"
    lines = [f"**{title}**", "", f"- Valid pairs: {stats['valid_pairs']}", f"- Verdict agreement: {agreement_text}"]
    if stats["valid_pairs"]:
        lines += [f"- False passes (judge PASS, label FAIL): {stats['false_passes'] or 'none'}",
                  f"- False fails (judge FAIL, label PASS): {stats['false_fails'] or 'none'}",
                  f"- Critical disagreements: {stats['critical_disagreements'] or 'none'}"]
        for dimension, items in stats["dimension_disagreements"].items():
            lines.append(f"- {dimension} disagreements: {items or 'none'}")
    return lines + [""]


def calibration_lines(run: dict) -> list[str]:
    source = run["source_run"]
    lines = [f"Source judge run: `{source['run_id']}` ({source['mode']}), resolved from `{source['selector']}`. "
             "The source evidence was read, not modified.", "", f"> {run['scope_note']}", ""]
    for split, block in run["splits"].items():
        coverage = block["confirmed_coverage"]
        lines += [f"## {split.capitalize()} split ({block['cases']} cases)", "",
                  f"- Confirmed current human labels: **{coverage['confirmed']}/{coverage['of']}**",
                  f"- Unconfirmed (proposal only): {block['unconfirmed'] or 'none'}",
                  f"- Stale or mismatched human labels: {block['stale_or_mismatched'] or 'none'}",
                  f"- Judge evaluation errors or missing results: {block['evaluation_errors'] or 'none'}", ""]
        if coverage["confirmed"] == 0:
            lines += ["Confirmed human agreement is **unavailable**: no confirmed, current human labels exist for this split.", ""]
        else:
            lines += _stats_lines(block["confirmed_human"], "Judge vs confirmed human labels")
        lines += _stats_lines(block["provisional_vs_proposed"],
                              "PROVISIONAL: judge vs trainer-proposed, UNCONFIRMED labels (not human agreement)")
    lines += ["## Per-case detail", "", "| Case | Split | Judge | Judge verdict | Human label | Human verdict | Proposed verdict (unconfirmed) |",
              "| --- | --- | --- | --- | --- | --- | --- |"]
    for row in run["observations"]:
        lines.append(f"| {row['case_id']} | {row['split']} | {row['judge_status']} | {row['judge_verdict'] or '-'} | "
                     f"{row['human_status']} | {row['human_verdict'] or '-'} | {row['proposed_verdict'] or '-'} |")
    return lines + [""]


# --- summary -----------------------------------------------------------------

def _current_hashes() -> dict:
    hashes = {"dataset": sha256_file(data.CASES_PATH), "rubric": sha256_file(data.RUBRIC_PATH),
              "judge": sha256_file(data.JUDGE_PROMPT_PATH)}
    for variant, path in data.RESPONSE_PROMPT_PATHS.items():
        hashes[f"response_{variant.lower()}"] = sha256_file(path)
    return hashes


def _version_note(run: dict, current: dict) -> str:
    inputs = run.get("inputs", {})
    recorded = {"dataset": (inputs.get("dataset") or {}).get("sha256"), "rubric": (inputs.get("rubric") or {}).get("sha256")}
    for name, prompt in (inputs.get("prompts") or {}).items():
        recorded[name] = prompt.get("sha256")
    differs = [name for name, value in recorded.items() if value and current.get(name) and value != current[name]]
    return "versions match current files" if not differs else "DIFFERS from current: " + ", ".join(differs)


def summary_lines() -> list[str]:
    from training_day4 import reviews

    cases_document = data.load_cases()
    current = _current_hashes()
    fixed = reviews.fixed_review_status(cases_document)
    confirmed = sum(1 for entry in fixed.values() if entry["current"])
    stale = sum(len(entry["stale"]) for entry in fixed.values())
    lines = [
        "Day 4 activity summary",
        "",
        f"Fixed-response human labels: {confirmed}/{len(fixed)} confirmed and current, {stale} stale record(s), "
        f"{len(fixed) - confirmed} still proposal-only (unconfirmed).",
        f"Human review of fixed responses complete: {'YES' if confirmed == len(fixed) else 'NO'}",
        "",
    ]
    found, unreadable = {}, []
    for run_dir in runs.list_run_dirs():
        try:
            run, _ = runs.load_run(run_dir.name)
        except runs.RunError as error:
            unreadable.append(str(error))
            continue
        found.setdefault((run["mode"], run["experiment"]), []).append((run, run_dir))

    activities = [("live", "access-check"), ("replay", "judge-fixed"), ("live", "judge-fixed"), ("replay", "calibrate"),
                  ("live", "calibrate"), ("replay", "compare"), ("live", "compare"), ("replay", "repeat"), ("live", "repeat")]
    for mode in ("live", "replay"):
        lines.append(f"{mode.upper()} evidence" + (" (authored teaching fixtures, not live observations)" if mode == "replay" else ""))
        for activity_mode, experiment in activities:
            if activity_mode != mode:
                continue
            entries = found.get((mode, experiment), [])
            if not entries:
                lines.append(f"  {experiment:<13} not run")
                continue
            for run, run_dir in sorted(entries, key=lambda pair: pair[0]["created_at"]):
                status = runs.run_status(run)
                extra = ""
                if experiment in ("compare", "repeat") and run.get("finalised"):
                    review_status = reviews.generated_review_status(run, run_dir)
                    extra = f"; human-reviewed {sum(1 for e in review_status.values() if e['current'])}/{len(review_status)}"
                if experiment == "calibrate":
                    extra = f"; source {run['source_run']['run_id']}"
                lines.append(f"  {experiment:<13} {status:<20} {run['run_id']}  ({_version_note(run, current)}{extra})")
        lines.append("")
    if unreadable:
        lines.append("Unreadable or inconsistent run folders (not counted):")
        lines += [f"  {message}" for message in unreadable]
        lines.append("")
    lines.append("Runs are listed separately. Different runs are not combined into one experiment.")
    return lines
