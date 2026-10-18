"""
Command-line interface. This module only reads arguments, calls the other
modules in order and prints results. The work itself lives elsewhere.

Exit codes: 0 success, 1 the run finished but has ERROR items or the data
is invalid, 2 the command could not run (bad arguments, missing files, an
earlier run in the output directory, a refused review).
"""

import argparse
import getpass
import sys
import webbrowser
from pathlib import Path

from day3_lab import clinic, data, decision, runs
from day3_lab.mock_responses import MOCK_RESPONSES
from day3_lab.providers import make_provider, render_prompt


def _print_items(run: dict) -> None:
    for item in run["items"]:
        print(
            f"  {item['item_id']:<30} structural={item['structural']['status']:<7} "
            f"human={decision.review_status(item):<8} outcome={item['outcome']['result']}"
        )


def load_checked_inputs() -> tuple[dict, dict, list[str]]:
    """Load cases and rubric and return every problem found in them."""
    cases_document = data.load_cases()
    rubric = data.load_rubric()
    problems = data.validate_cases(cases_document)
    problems += data.validate_rubric(rubric, decision.DIMENSIONS, decision.SUPPORTED_RUBRIC_VERSION)
    if not problems:
        problems += data.validate_consistency(cases_document, rubric)
    return cases_document, rubric, problems


def command_validate_data(args) -> int:
    cases_document, rubric, problems = load_checked_inputs()
    for copy_path, source_path in ((data.CASES_PATH, data.SOURCE_CASES_PATH), (data.RUBRIC_PATH, data.SOURCE_RUBRIC_PATH)):
        difference = data.compare_with_source(copy_path, source_path)
        if difference:
            problems.append(difference)
        source_state = "matches supplied source" if source_path.is_file() and not difference else (
            "DIFFERS from supplied source" if difference else "supplied source not present, comparison skipped")
        print(f"{data.relative(copy_path)}: {source_state}")

    case_ids = [case.get("case_id") for case in cases_document.get("cases", []) if isinstance(case, dict)]
    missing_mocks = sorted(set(case_ids) - set(MOCK_RESPONSES))
    extra_mocks = sorted(set(MOCK_RESPONSES) - set(case_ids))
    if missing_mocks:
        problems.append(f"no reviewed mock response for {missing_mocks}")
    if extra_mocks:
        problems.append(f"mock responses for unknown cases {extra_mocks}")

    print(f"Dataset version: {cases_document.get('dataset_version')}  Rubric version: {rubric.get('version')}")
    print(f"Unique case IDs: {len(set(case_ids))} of {len(case_ids)}")
    if problems:
        print(f"INVALID: {len(problems)} problem(s):")
        for problem in problems:
            print(f"  - {problem}")
        return 1
    print(f"Cases validated: {len(case_ids)}")
    return 0


def command_run(args) -> int:
    cases_document, rubric, problems = load_checked_inputs()
    if problems:
        print("Data is invalid. Run `python -m day3_lab validate-data` for details.", file=sys.stderr)
        return 2

    cases = data.cases_by_id(cases_document)
    if args.case:
        if args.case not in cases:
            print(f"Unknown case {args.case!r}. Known cases: {', '.join(cases)}", file=sys.stderr)
            return 2
        selected = [cases[args.case]]
    else:
        selected = list(cases.values())

    out_dir = runs.ensure_fresh_output(Path(args.out))
    template = data.load_prompt_template()
    provider = make_provider(args.mode)

    items = []
    for case in selected:
        prompt_text = render_prompt(template, case)
        result = provider.respond(case, prompt_text)
        items.append(runs.build_item(case, result, prompt_text))

    if args.mode == "mock":
        note = "Reviewed fixed mock responses. A mock PASS shows fixture and workflow success only, never live model quality."
    else:
        note = "Live provider output. Structural checks are not semantic evaluation; human review decides quality."
    run = runs.build_run("run", args.mode, provider.label, note, provider.model, items, cases_document, rubric)
    json_path, html_path = runs.save_run(run, out_dir)

    print(f"{run['label']} run {run['run_id']} ({len(items)} case(s), model: {run['model']})")
    _print_items(run)
    print(f"Saved {json_path.as_posix()} and {html_path.as_posix()}")
    errors = run["summary"]["outcomes"].get("ERROR", 0)
    if errors:
        print(f"{errors} item(s) are ERROR. Nothing fell back to mock. See the provider error in the report.")
        return 1
    return 0


def command_open(args) -> int:
    path = Path(args.path)
    if not path.is_file():
        print(f"Report not found: {path.as_posix()}", file=sys.stderr)
        return 2
    uri = path.resolve().as_uri()
    opened = webbrowser.open(uri)
    print(f"{'Opened' if opened else 'Could not launch a browser. Open this address manually'}: {uri}")
    return 0


def _default_reviewer() -> str:
    try:
        return getpass.getuser()
    except Exception:
        return ""


def command_review(args) -> int:
    report_path = Path(args.report)
    run = runs.load_run(report_path)
    matches = [item for item in run["items"] if item["item_id"] == args.case]
    if not matches:
        known = ", ".join(item["item_id"] for item in run["items"])
        print(f"No item {args.case!r} in {report_path.as_posix()}. Items: {known}", file=sys.stderr)
        return 2

    reviewer = args.reviewer if args.reviewer is not None else _default_reviewer()
    try:
        item = decision.apply_review(matches[0], args.scores, args.critical, args.note, reviewer)
    except decision.ReviewError as error:
        print(f"Review not recorded: {error}", file=sys.stderr)
        return 2

    json_path, html_path = runs.save_run(run, report_path.parent)
    current = item["human_review"]["current"]
    scores = ", ".join(f"{name}={value}" for name, value in current["scores"].items())
    print(f"Review recorded for {item['item_id']} by {current['reviewer']} at {current['reviewed_at']}")
    print(f"  bound to response sha256 {current['response_sha256']}")
    print(f"  {scores}, critical={current['critical']}")
    print(f"  outcome={item['outcome']['result']}: {item['outcome']['reason']}")
    print(f"Updated {json_path.as_posix()} and regenerated {html_path.as_posix()}")
    return 0


def command_clinic(args) -> int:
    cases_document, rubric, problems = load_checked_inputs()
    if problems:
        print("Data is invalid. Run `python -m day3_lab validate-data` for details.", file=sys.stderr)
        return 2
    out_dir = runs.ensure_fresh_output(Path(args.out))
    run = clinic.build_clinic_run(args.variant, cases_document, rubric)
    json_path, html_path = runs.save_run(run, out_dir)
    notes_path = out_dir / "clinic_notes.md"
    notes_path.write_text(clinic.clinic_notes(run), encoding="utf-8")

    print(f"{run['label']} ({args.variant}) run {run['run_id']}. No live calls were made.")
    for item in run["items"]:
        exact = item["clinic"]["naive_exact_match"]["result"]
        print(
            f"  {item['item_id']:<30} structural={item['structural']['status']:<5} "
            f"naive-exact={exact:<5} human={decision.review_status(item):<8} outcome={item['outcome']['result']}"
        )
    print("Design intent is not a review. No scores were recorded.")
    print(f"Saved {json_path.as_posix()}, {html_path.as_posix()} and {notes_path.as_posix()}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="python -m day3_lab", description="Day 3 response-evaluation lab.")
    commands = parser.add_subparsers(dest="command", required=True)

    validate = commands.add_parser("validate-data", help="check the cases, rubric and mock coverage")
    validate.set_defaults(handler=command_validate_data)

    run = commands.add_parser("run", help="generate responses and save run.json and run.html")
    run.add_argument("--mode", choices=("mock", "live"), required=True)
    run.add_argument("--case", help="run one case, e.g. D3-01 (default: all cases)")
    run.add_argument("--out", required=True, help="a fresh output directory")
    run.set_defaults(handler=command_run)

    open_report = commands.add_parser("open", help="open a saved run.html in the default browser")
    open_report.add_argument("path")
    open_report.set_defaults(handler=command_open)

    review = commands.add_parser("review", help="record a human rubric assessment for one item")
    review.add_argument("--report", required=True, help="path to run.json")
    review.add_argument("--case", required=True, help="item ID, e.g. D3-01 or D3-04-unsafe")
    review.add_argument(
        "--scores", required=True, nargs=4, type=int, choices=decision.ALLOWED_SCORES,
        metavar=("CORRECTNESS", "RELEVANCE", "COMPLETENESS", "SAFETY"),
        help="four scores, each 0, 1 or 2, in this order",
    )
    review.add_argument("--critical", required=True, choices=("yes", "no"))
    review.add_argument("--note", required=True, help="non-empty reason for the scores")
    review.add_argument("--reviewer", help="reviewer identifier (default: your OS user name)")
    review.set_defaults(handler=command_review)

    clinic_parser = commands.add_parser("clinic", help="controlled failure clinic with fixed fixtures")
    clinic_parser.add_argument("--variant", choices=(clinic.ORIGINAL, clinic.CORRECTED), default=clinic.ORIGINAL)
    clinic_parser.add_argument("--out", required=True, help="a fresh output directory")
    clinic_parser.set_defaults(handler=command_clinic)
    return parser


def main(argv=None) -> int:
    args = build_parser().parse_args(argv)
    try:
        return args.handler(args)
    except (data.DataError, runs.OutputExistsError) as error:
        print(str(error), file=sys.stderr)
        return 2
