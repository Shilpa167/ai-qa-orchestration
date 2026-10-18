"""
Command-line interface for Day 4. Run `python -m training_day4 --help`.

Exit codes: 0 success; 1 the command ran but found problems or errors;
2 the command could not run (bad input, unusable run, refused review).
"""

import argparse
import sys

from day3_lab.data import DataError
from training_day4 import calibration, data, experiments, judge, reporting, reviews, rubric, runs

MODE_HELP = "replay = authored fixtures, no network; live = billable OpenAI API calls. There is no default."


def command_validate(args) -> int:
    problems = []
    cases_document = data.load_cases()
    loaded_rubric = rubric.load_rubric()
    problems += rubric.validate_rubric(loaded_rubric)
    problems += data.validate_cases(cases_document, rubric.CRITICAL_CATEGORIES)
    reference_problems, reference_lines = data.validate_references(cases_document)
    problems += reference_problems
    problems += data.validate_labels(data.load_labels(), cases_document, rubric.compute_verdict)
    confirmed_document = reviews.load_confirmed()
    problems += reviews.validate_confirmed(confirmed_document)
    fixtures = data.load_replay_fixtures()
    problems += data.validate_replay_fixtures(fixtures, cases_document)
    judge.judge_schema()  # raises if the schema itself is invalid
    template = data.load_text(data.JUDGE_PROMPT_PATH)
    for placeholder in ("{{rubric}}", "{{critical_categories}}"):
        if placeholder not in template:
            problems.append(f"prompts/day4/judge.txt is missing {placeholder}")
    for path in data.RESPONSE_PROMPT_PATHS.values():
        if not data.load_text(path).strip():
            problems.append(f"{data.relative(path)} is empty")

    cases = cases_document["cases"]
    print(f"Cases: {len(cases)} ({cases_document.get('dataset_version')}): {', '.join(c['case_id'] for c in cases)}")
    for split in data.SPLITS:
        print(f"  {split}: {', '.join(c['case_id'] for c in cases if c['split'] == split)}")
    for group in data.shared_input_groups(cases_document):
        print(f"  Shared input (not independent): {' + '.join(group)}")
    print("Business-rule references (docs/business_rules.md):")
    for line in reference_lines:
        print(line)
    print(f"Rubric: {loaded_rubric.get('version')}. Judge output schema: valid. Prompts: judge, response_a, response_b present.")
    invalid_fixtures = sum(1 for entry in fixtures.get("judge", []) if entry.get("intentionally_invalid"))
    print(f"Replay fixtures: {len(fixtures.get('judge', []))} authored judge outputs ({invalid_fixtures} intentionally invalid).")
    status = reviews.fixed_review_status(cases_document)
    confirmed = sum(1 for entry in status.values() if entry["current"])
    stale = sum(len(entry["stale"]) for entry in status.values())
    print(f"Labels: {len(data.load_labels()['labels'])} trainer-proposed (unconfirmed); "
          f"{confirmed} confirmed and current; {stale} stale confirmed record(s).")
    if confirmed < len(status):
        print("  Unconfirmed labels are an expected readiness gap, not malformed data.")
    if problems:
        print(f"INVALID: {len(problems)} problem(s):")
        for problem in problems:
            print(f"  - {problem}")
        return 1
    print("VALID")
    return 0


def command_show_case(args) -> int:
    cases_document = data.load_cases()
    cases = data.cases_by_id(cases_document)
    if args.case not in cases:
        print(f"Unknown case {args.case!r}. Known: {', '.join(cases)}", file=sys.stderr)
        return 2
    case = cases[args.case]
    print(f"{case['case_id']}  split={case['split']}  requirements={', '.join(case['requirement_ids'])}")
    for note in data.dependency_notes(cases_document, [c for group in data.shared_input_groups(cases_document) if args.case in group for c in group]):
        print(f"Note: {note}")
    print(f"\nEmployee request:\n  {case['user_input']}\n\nApproved context:\n  {case['approved_context']}")
    print("\nExpected behaviour:\n" + "\n".join(f"  - {item}" for item in case["expected_behaviour"]))
    print("Prohibited behaviour:\n" + "\n".join(f"  - {item}" for item in case["prohibited_behaviour"]))
    print(f"\nFixed response:\n  {case['fixed_response']}")
    loaded = rubric.load_rubric()
    print(f"\nRubric ({loaded['version']}):\n{rubric.rubric_text(loaded)}\nCritical categories:\n{rubric.critical_text(loaded)}")
    print(f"PASS rule (computed in code): {loaded['pass_rule']['text']}")

    proposal = {label["case_id"]: label for label in data.load_labels()["labels"]}[case["case_id"]]
    print("\n--- PROPOSED LABEL (trainer-proposed, UNCONFIRMED; not a human review) ---")
    print("  " + ", ".join(f"{d}={proposal['scores'][d]}" for d in rubric.DIMENSIONS)
          + f"; critical={proposal['critical_violations'] or 'none'}; verdict={proposal['verdict']}")
    print(f"  Reason: {proposal['reason']}")
    status = reviews.fixed_review_status(cases_document)[case["case_id"]]
    print("\n--- CONFIRMED HUMAN REVIEWS ---")
    if status["current"]:
        review = status["current"]
        print(f"  CURRENT: {review['review_id']} by {review['reviewer']} at {review['reviewed_at']}: "
              + ", ".join(f"{d}={review['scores'][d]}" for d in rubric.DIMENSIONS)
              + f"; critical={review['critical_violations'] or 'none'}; verdict={review['verdict']}")
        print(f"  Reason: {review['reason']}")
    for review in status["stale"]:
        print(f"  STALE (not used): {review['review_id']} by {review['reviewer']}; changed: {', '.join(review['stale_because'])}")
    if not status["current"] and not status["stale"]:
        print("  none")
    return 0


def _report(run, run_dir) -> int:
    print(f"{run['evidence_label']}")
    print(f"Run {run['run_id']} ({run['experiment']}, mode {run['mode']}): {run['status']}")
    for error in run.get("run_errors", []):
        print(f"  RUN ERROR {error['type']}: {error['message']}")
    counts = run["counts"]
    for kind in ("generation", "judge", "access_check"):
        c = counts[kind]
        if c["calls"]:
            print(f"  {kind}: {c['calls']} calls, {c['succeeded']} succeeded, {c['failed']} failed, {c['attempts']} attempts, {c['retries']} retries")
    if run["experiment"] != "access-check":
        print(f"  evaluations: {counts['evaluations']['valid']} valid, {counts['evaluations']['errors']} errors; "
              f"PASS {counts['verdicts']['PASS']}, FAIL {counts['verdicts']['FAIL']}")
    print(f"Saved {run_dir.as_posix()}/run.json and results.md")
    if run["mode"] == "live" and run.get("run_errors"):
        print("Nothing fell back to replay.")
    return 0 if run["status"] == "completed" else 1


def command_judge(args) -> int:
    case_ids = data.resolve_case_ids(args.cases, data.load_cases())
    return _report(*experiments.run_judge_fixed(args.mode, case_ids))


def command_compare(args) -> int:
    case_ids = data.resolve_case_ids(args.cases, data.load_cases())
    run, run_dir = experiments.run_compare(args.mode, case_ids, seed=args.seed)
    code = _report(run, run_dir)
    if run["observations"]:
        print(reporting.compare_preference(reporting.per_variant_counts(run)))
    return code


def command_repeat(args) -> int:
    case_ids = data.resolve_case_ids(args.cases, data.load_cases())
    run, run_dir = experiments.run_repeat(args.mode, args.prompt, case_ids, args.runs)
    code = _report(run, run_dir)
    for case_id, stats in reporting.repeat_stats(run).items():
        print(f"  {case_id}: {stats['passes']}/{stats['attempted']} passed, {stats['valid_evaluations']} valid, {stats['errors']} errors")
    return code


def command_access_check(args) -> int:
    return _report(*experiments.run_access_check())


def command_calibrate(args) -> int:
    run, run_dir, source = calibration.calibrate(args.run)
    print(f"Calibrating {source['run_id']} (mode {source['mode']}, resolved from {args.run!r})")
    print(run["scope_note"])
    for split, block in run["splits"].items():
        coverage = block["confirmed_coverage"]
        agreement = block["confirmed_human"]["verdict_agreement"]
        print(f"  {split}: confirmed human labels {coverage['confirmed']}/{coverage['of']}; "
              + ("confirmed human agreement unavailable" if coverage["confirmed"] == 0 or isinstance(agreement, str)
                 else f"agreement {agreement['count']} of {agreement['denominator']} valid pairs")
              + f"; evaluation errors {block['evaluation_errors'] or 'none'}")
    print(f"Saved {run_dir.as_posix()}/run.json and results.md")
    return 0


def command_summary(args) -> int:
    print("\n".join(reporting.summary_lines()))
    return 0


def command_review_fixed(args) -> int:
    record = reviews.add_fixed_review(args.case, args.reviewer, args.scores, args.critical, args.reason)
    print(f"Saved human review {record['review_id']} for {record['case_id']} by {record['reviewer']} "
          f"to {data.relative(data.CONFIRMED_REVIEWS_PATH)}")
    print(f"  total={record['total']} verdict={record['verdict']} (computed); matches proposal: "
          f"{record.get('proposal_comparison', {}).get('matches_proposal')}")
    print("  The proposal in human_labels.json was not changed.")
    return 0


def command_review_generated(args) -> int:
    record = reviews.add_generated_review(args.run, args.response, args.reviewer, args.scores, args.critical, args.reason)
    print(f"Saved human review {record['review_id']} of {args.response} ({record['case_id']}, prompt {record['prompt_variant']}) "
          f"by {record['reviewer']}: verdict={record['verdict']}. run.json was not changed.")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m training_day4",
        description="Day 4: evaluate fixed responses with an LLM judge, calibrate against confirmed human labels, "
                    "compare prompts A/B and repeat requests. API-calling commands need an explicit --mode.",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("validate", help="check cases, labels, references, prompts, schemas and fixtures").set_defaults(handler=command_validate)

    show = sub.add_parser("show-case", help="show one case, its fixed response, rubric, proposed label and confirmed reviews")
    show.add_argument("--case", required=True)
    show.set_defaults(handler=command_show_case)

    access = sub.add_parser("access-check", help="BILLABLE live preflight of the response and judge models")
    access.add_argument("--mode", required=True, choices=("live",), help="must be live")
    access.set_defaults(handler=command_access_check)

    judge_parser = sub.add_parser("judge", help="judge the eight fixed responses (new evidence run)")
    judge_parser.add_argument("--mode", required=True, choices=("replay", "live"), help=MODE_HELP)
    judge_parser.add_argument("--cases", required=True, nargs="+", help="'all' or case IDs, e.g. D4-01 D4-06")
    judge_parser.set_defaults(handler=command_judge)

    calibrate_parser = sub.add_parser("calibrate", help="compare a fixed-response judge run with confirmed human labels")
    calibrate_parser.add_argument("--run", required=True, help="'latest-fixed' or an explicit judge-fixed run ID")
    calibrate_parser.set_defaults(handler=command_calibrate)

    compare = sub.add_parser("compare", help="generate with prompts A and B, judge each answer blind to the prompt")
    compare.add_argument("--mode", required=True, choices=("replay", "live"), help=MODE_HELP)
    compare.add_argument("--cases", required=True, nargs="+", help="'all' or case IDs")
    compare.add_argument("--seed", type=int, help="A/B order seed (default: random, always recorded)")
    compare.set_defaults(handler=command_compare)

    repeat = sub.add_parser("repeat", help="generate and judge fresh responses several times")
    repeat.add_argument("--mode", required=True, choices=("replay", "live"), help=MODE_HELP)
    repeat.add_argument("--prompt", required=True, choices=("A", "B"))
    repeat.add_argument("--cases", required=True, nargs="+", help="'all' or case IDs")
    repeat.add_argument("--runs", required=True, type=int, choices=range(1, 11), metavar="1-10")
    repeat.set_defaults(handler=command_repeat)

    sub.add_parser("summary", help="show which activities ran, separately for live and replay").set_defaults(handler=command_summary)

    for name, help_text in (("review-fixed", "record YOUR human review of one fixed response"),
                            ("review-generated", "record YOUR human review of one generated response")):
        review = sub.add_parser(name, help=help_text)
        if name == "review-fixed":
            review.add_argument("--case", required=True)
        else:
            review.add_argument("--run", required=True, help="compare or repeat run ID")
            review.add_argument("--response", required=True, help="response ID from that run's results.md")
        review.add_argument("--reviewer", required=True, help="your actual name or identifier")
        review.add_argument("--scores", required=True, nargs=4, type=int, choices=rubric.ALLOWED_SCORES,
                            metavar=("CORRECTNESS", "RELEVANCE", "COMPLETENESS", "SAFETY_AND_POLICY"))
        review.add_argument("--critical", required=True, nargs="+", choices=("none", *rubric.CRITICAL_CATEGORIES),
                            help="'none' or one or more critical categories")
        review.add_argument("--reason", required=True)
        review.set_defaults(handler=command_review_fixed if name == "review-fixed" else command_review_generated)
    return parser


def main(argv=None) -> int:
    args = build_parser().parse_args(argv)
    try:
        return args.handler(args)
    except (DataError, runs.RunError, reviews.ReviewInputError) as error:
        print(str(error), file=sys.stderr)
        return 2
