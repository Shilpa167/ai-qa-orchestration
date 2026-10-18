"""
Static HTML view of a run.json. No JavaScript, no external files.

Every value from the run is passed through html.escape, so text in a
model response is shown as text and can never run as code in the page.
"""

import html
import json

from day3_lab.decision import DIMENSIONS, review_status

OUTCOME_COLOURS = {
    "PASS": "#1b7f3b",
    "FAIL": "#b42318",
    "ERROR": "#7a2e0e",
    "REVIEW_PENDING": "#8a6d00",
}

STYLE = """
body { font-family: Segoe UI, Arial, sans-serif; margin: 2rem; color: #1d2433; max-width: 1200px; }
h1 { margin-bottom: 0.2rem; }
.banner { padding: 0.8rem 1rem; border-radius: 6px; font-weight: 600; margin: 1rem 0; }
.banner.mock { background: #fff4ce; border: 1px solid #c9a400; }
.banner.live { background: #e1effe; border: 1px solid #3f83f8; }
.banner.clinic { background: #fde8e8; border: 1px solid #c81e1e; }
table { border-collapse: collapse; width: 100%; margin: 0.6rem 0 1.2rem; }
th, td { border: 1px solid #d0d5dd; padding: 0.35rem 0.5rem; text-align: left; vertical-align: top; font-size: 0.92rem; }
th { background: #f2f4f7; }
.outcome { font-weight: 700; }
pre { background: #f6f8fa; padding: 0.6rem; white-space: pre-wrap; word-break: break-word; border-radius: 4px; }
section.item { border-top: 2px solid #d0d5dd; margin-top: 1.5rem; padding-top: 0.5rem; }
.muted { color: #667085; font-size: 0.88rem; }
.note { background: #f9fafb; border-left: 4px solid #98a2b3; padding: 0.5rem 0.8rem; }
"""


def esc(value) -> str:
    if value is None:
        return "<span class='muted'>null</span>"
    return html.escape(str(value))


def as_json(value) -> str:
    return html.escape(json.dumps(value, indent=2, ensure_ascii=False))


def outcome_cell(outcome: dict) -> str:
    result = outcome["result"]
    colour = OUTCOME_COLOURS.get(result, "#1d2433")
    return f"<span class='outcome' style='color:{colour}'>{esc(result)}</span>"


def _banner(run: dict) -> str:
    css = "clinic" if run["kind"] == "clinic" else ("live" if run["provider_mode"] == "live" else "mock")
    return f"<div class='banner {css}'>{esc(run['label'])}: {esc(run['label_note'])}</div>"


def _summary_table(run: dict) -> str:
    is_clinic = run["kind"] == "clinic"
    headers = ["Item", "Case", "Structural"]
    if is_clinic:
        headers += ["Naive exact-string check (diagnostic only)", "Fixture design intent (not a review)"]
    headers += ["Human review"] + [dimension.capitalize() for dimension in DIMENSIONS] + ["Critical", "Outcome", "Reason"]
    rows = []
    for item in run["items"]:
        current = item["human_review"].get("current") if review_status(item) == "ASSESSED" else None
        scores = current["scores"] if current else {}
        cells = [esc(item["item_id"]), esc(item["case_id"]), esc(item["structural"]["status"])]
        if is_clinic:
            clinic = item.get("clinic", {})
            exact = clinic.get("naive_exact_match", {})
            intent = clinic.get("designed_expectation", {})
            cells += [
                esc(exact.get("result")),
                esc(", ".join(f"{key}={value}" for key, value in intent.items())),
            ]
        cells += [esc(review_status(item))]
        cells += [esc(scores.get(dimension, "-")) for dimension in DIMENSIONS]
        cells += [esc(current["critical"] if current else "-"), outcome_cell(item["outcome"]), esc(item["outcome"]["reason"])]
        rows.append("<tr>" + "".join(f"<td>{cell}</td>" for cell in cells) + "</tr>")
    head = "".join(f"<th>{esc(header)}</th>" for header in headers)
    return f"<table><tr>{head}</tr>{''.join(rows)}</table>"


def _metadata(run: dict) -> str:
    rows = [
        ("Run ID", run["run_id"]),
        ("Created (UTC)", run["created_at"]),
        ("Kind", run["kind"]),
        ("Provider mode", run["provider_mode"]),
        ("Model", run["model"]),
        ("Git commit", run["git"]["commit"]),
        ("Working tree dirty", run["git"]["dirty"]),
        ("Prompt", f"{run['prompt']['path']} (sha256 {run['prompt']['sha256']})"),
        ("Dataset", f"{run['dataset']['path']} {run['dataset']['version']} (sha256 {run['dataset']['sha256']})"),
        ("Rubric", f"{run['rubric']['path']} {run['rubric']['version']} (sha256 {run['rubric']['sha256']})"),
        ("Response schema", f"{run['response_schema']['path']} (sha256 {run['response_schema']['sha256']})"),
    ]
    if run.get("variant"):
        rows.append(("Clinic variant", run["variant"]))
    body = "".join(f"<tr><th>{esc(name)}</th><td>{esc(value)}</td></tr>" for name, value in rows)
    return f"<table>{body}</table>"


def _rubric_table(run: dict) -> str:
    scales = run["rubric"].get("scales") or {}
    rows = []
    for dimension in DIMENSIONS:
        levels = scales.get(dimension, {})
        rows.append(
            f"<tr><th>{esc(dimension)}</th>"
            + "".join(f"<td><b>{level}</b>: {esc(levels.get(level))}</td>" for level in ("0", "1", "2"))
            + "</tr>"
        )
    return (
        "<table><tr><th>Dimension</th><th>0</th><th>1</th><th>2</th></tr>"
        + "".join(rows)
        + f"</table><p class='note'><b>Decision rule:</b> {esc(run['rubric'].get('decision_rule'))}<br>"
        + f"<b>Scope:</b> {esc(run['rubric'].get('review_scope'))}</p>"
    )


def _item_section(item: dict) -> str:
    case = item["case"]
    parts = [
        f"<section class='item' id='{esc(item['item_id'])}'>",
        f"<h3>{esc(item['item_id'])}: {esc(case['category'])} {outcome_cell(item['outcome'])}</h3>",
        f"<p class='muted'>Label: {esc(item['label'])}</p>",
        f"<p><b>Question:</b> {esc(case['question'])}</p>",
        f"<p><b>Approved context:</b></p><pre>{as_json(case['approved_context'])}</pre>",
        "<p><b>Expected behaviour:</b></p><ul>" + "".join(f"<li>{esc(entry)}</li>" for entry in case["expected_behaviour"]) + "</ul>",
        "<p><b>Prohibited behaviour:</b></p><ul>" + "".join(f"<li>{esc(entry)}</li>" for entry in case["prohibited_behaviour"]) + "</ul>",
        f"<p><b>Requirement IDs:</b> {esc(', '.join(case['requirement_ids']))}</p>",
    ]

    clinic = item.get("clinic")
    if clinic:
        parts.append(f"<div class='note'><b>Clinic scenario:</b> {esc(clinic.get('scenario'))}<br>"
                     f"<b>Teaching point:</b> {esc(clinic.get('teaching_point'))}<br>"
                     f"<b>Fixture design intent (not a review):</b> {esc(clinic.get('designed_expectation'))}</div>")
        exact = clinic.get("naive_exact_match")
        if exact:
            parts.append(f"<p><b>Naive exact-string check:</b> {esc(exact['result'])}. {esc(exact['note'])}</p>"
                         f"<p class='muted'>Reference answer: {esc(exact['reference_answer'])}</p>")
        if clinic.get("corrects"):
            parts.append(f"<p><b>Corrects fixture:</b> {esc(clinic['corrects'])} from the original clinic run (same item ID, separate directory). "
                         f"Original raw response (kept for comparison):</p><pre>{esc(clinic.get('original_raw_response'))}</pre>")

    provider = item["provider"]
    parts += [
        f"<p><b>Provider:</b> mode={esc(provider['mode'])}, model={esc(provider['model'])}, "
        f"status={esc(provider['status'])}, elapsed={esc(provider['elapsed_seconds'])}s, "
        f"token usage={esc(provider['token_usage'])}</p>",
    ]
    if provider.get("error"):
        parts.append(f"<p><b>Provider error:</b></p><pre>{as_json(provider['error'])}</pre>")
    parts += [
        f"<p><b>Raw response</b> (sha256 {esc(item['response_sha256'])}):</p><pre>{esc(item['raw_response'])}</pre>",
        f"<p><b>Parsed response:</b></p><pre>{as_json(item['parsed_response'])}</pre>",
        f"<p><b>Structural check:</b> {esc(item['structural']['status'])}. A pass means shape only, not truth or safety.</p>",
    ]
    findings = item["structural"]["findings"]
    if findings:
        parts.append("<table><tr><th>Stage</th><th>Path</th><th>Finding</th></tr>" + "".join(
            f"<tr><td>{esc(f['stage'])}</td><td>{esc(f['path'])}</td><td>{esc(f['message'])}</td></tr>" for f in findings
        ) + "</table>")

    history = item["human_review"].get("history", [])
    parts.append(f"<p><b>Human review:</b> {esc(review_status(item))}</p>")
    if history:
        rows = "".join(
            "<tr>" + "".join(f"<td>{esc(value)}</td>" for value in (
                entry["reviewed_at"], entry["reviewer"],
                *[entry["scores"][dimension] for dimension in DIMENSIONS],
                entry["critical"], entry["note"], entry["response_sha256"][:12] + "…",
            )) + "</tr>" for entry in history
        )
        parts.append(
            "<table><tr><th>Reviewed (UTC)</th><th>Reviewer</th>"
            + "".join(f"<th>{esc(dimension.capitalize())}</th>" for dimension in DIMENSIONS)
            + "<th>Critical</th><th>Note</th><th>Bound to response</th></tr>" + rows + "</table>"
        )
    else:
        parts.append("<p class='muted'>No human assessment recorded.</p>")
    parts.append(f"<p><b>Outcome:</b> {outcome_cell(item['outcome'])}. {esc(item['outcome']['reason'])}</p>")
    parts.append("</section>")
    return "\n".join(parts)


def render_html(run: dict) -> str:
    summary = run["summary"]["outcomes"]
    counts = ", ".join(f"{name}: {count}" for name, count in summary.items())
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>Day 3 run {esc(run['run_id'])}</title>
<style>{STYLE}</style>
</head>
<body>
<h1>Day 3 response evaluation: {esc(run['label'])}</h1>
<p class="muted">Generated from run.json. Edit nothing here; use the review command.</p>
{_banner(run)}
<p class="note">Automated checks are structural only. They are not semantic evaluation.
Truth, relevance and safety are decided by human review against the rubric.</p>
<h2>Summary</h2>
<p>{esc(run['summary']['items'])} item(s). {esc(counts)}.</p>
{_summary_table(run)}
<h2>Run details</h2>
{_metadata(run)}
<h2>Rubric</h2>
{_rubric_table(run)}
<h2>Items</h2>
{''.join(_item_section(item) for item in run['items'])}
</body>
</html>
"""
