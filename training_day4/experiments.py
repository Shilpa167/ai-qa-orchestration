"""
The four experiments: judge fixed responses, compare prompts A/B, repeat
selected requests, and the live access check.

Each experiment creates a new run directory, records every observation
(including errors), finalises run.json and writes results.md.
"""

import random
import secrets
import uuid

from day3_lab.data import sha256_text
from training_day4 import clients, data, judge, reporting, rubric, runs


def opaque_response_id() -> str:
    """A random ID that reveals neither the case nor the prompt variant."""
    return "resp-" + uuid.uuid4().hex[:12]


def common_inputs(cases_document: dict, variants: list[str], judge_instructions: str) -> dict:
    prompts = {"judge": {**data.file_snapshot(data.JUDGE_PROMPT_PATH, include_text=True),
                         "rendered_instructions_sha256": sha256_text(judge_instructions)}}
    for variant in variants:
        prompts[f"response_{variant.lower()}"] = data.file_snapshot(data.RESPONSE_PROMPT_PATHS[variant], include_text=True)
    return {
        "dataset": {**data.file_snapshot(data.CASES_PATH), "version": cases_document.get("dataset_version")},
        "rubric": rubric.rubric_snapshot(),
        "judge_schema": data.file_snapshot(data.JUDGE_SCHEMA_PATH),
        "prompts": prompts,
        "generation_input_format": clients.GENERATION_INPUT_FORMAT if variants else None,
    }


def backends_for(mode: str, environ=None, client_factory=None, sleep=None):
    """Return (generator, judge_backend, config, label, config_errors) for a mode."""
    if mode == "replay":
        fixtures = data.load_replay_fixtures()
        generator, judge_backend = clients.ReplayGenerator(fixtures), clients.ReplayJudge(fixtures)
        config = {"source": "replay", "replay_fixtures": data.file_snapshot(data.REPLAY_FIXTURES_PATH),
                  "response_model": None, "judge_model": None, "judge_model_source": None}
        return generator, judge_backend, config, clients.REPLAY_LABEL, []
    kwargs = {"environ": environ, "client_factory": client_factory}
    if sleep is not None:
        kwargs["sleep"] = sleep
    client = clients.LiveClient(**kwargs)
    config = {"source": "live", **client.config_record()}
    return clients.LiveGenerator(client), clients.LiveJudge(client), config, clients.LIVE_LABEL, client.config_errors()


def observation(order, case, response_id, source, variant, repetition, response_text, generation_record, evaluation) -> dict:
    ok = (generation_record is None or generation_record["status"] == "ok") and evaluation is not None \
        and evaluation["evaluation_status"] == "valid"
    return {
        "observation_id": f"obs-{order:03d}",
        "order": order,
        "case_id": case["case_id"],
        "split": case["split"],
        "response_id": response_id,
        "response_source": source,
        "prompt_variant": variant,
        "repetition": repetition,
        "case_context_sha256": data.case_context_sha256(case),
        "response_text": response_text,
        "response_sha256": sha256_text(response_text) if isinstance(response_text, str) else None,
        "generation": generation_record,
        "judge": evaluation,
        "status": "ok" if ok else "error",
    }


def _start(experiment, mode, cases_document, selected, variants, config, label, extra):
    instructions = judge.render_judge_instructions()
    run, run_dir = runs.create_run(experiment, mode, label, {
        "inputs": common_inputs(cases_document, variants, instructions),
        "config": config,
        "cases_selected": selected,
        "dataset_notes": data.dependency_notes(cases_document, selected),
        **extra,
    })
    return run, run_dir, instructions


def _finish(run, run_dir):
    runs.finalise(run, run_dir)
    reporting.write_results(run, run_dir)
    return run, run_dir


def run_judge_fixed(mode: str, case_ids: list[str], **backend_options):
    cases_document = data.load_cases()
    cases = data.cases_by_id(cases_document)
    _, judge_backend, config, label, config_errors = backends_for(mode, **backend_options)
    config["judge_settings"] = judge_backend.settings()
    run, run_dir, instructions = _start(runs.JUDGE_FIXED, mode, cases_document, case_ids, [], config, label, {})
    if config_errors:
        run["run_errors"] = config_errors
        return _finish(run, run_dir)
    for order, case_id in enumerate(case_ids, start=1):
        case = cases[case_id]
        response_id = opaque_response_id()
        evaluation = judge.evaluate(judge_backend, instructions, response_id, case, case["fixed_response"])
        run["observations"].append(observation(order, case, response_id, "fixed_response", None, None,
                                               case["fixed_response"], None, evaluation))
    return _finish(run, run_dir)


def _generate_and_judge(order, case, variant, repetition, prompt_text, generator, judge_backend, instructions):
    response_id = opaque_response_id()
    generated = generator.generate(variant, prompt_text, case, repetition)
    generation_record = generated.record()
    if generated.status != "ok":
        evaluation = {"call": None, "raw_output_sanitised": None, "assessment": None, "computed": None,
                      "validation_errors": ["not judged: response generation failed"], "evaluation_status": "error"}
        return observation(order, case, response_id, "generated", variant, repetition, None, generation_record, evaluation)
    evaluation = judge.evaluate(judge_backend, instructions, response_id, case, generated.text)
    return observation(order, case, response_id, "generated", variant, repetition, generated.text, generation_record, evaluation)


def run_compare(mode: str, case_ids: list[str], seed: int | None = None, **backend_options):
    cases_document = data.load_cases()
    cases = data.cases_by_id(cases_document)
    generator, judge_backend, config, label, config_errors = backends_for(mode, **backend_options)
    config["generation_settings"] = generator.settings()
    config["judge_settings"] = judge_backend.settings()
    seed = secrets.randbelow(2**31) if seed is None else seed
    pairs = [(case_id, variant) for case_id in case_ids for variant in ("A", "B")]
    random.Random(seed).shuffle(pairs)
    extra = {
        "ordering": {"seed": seed, "note": "The seed reproduces the A/B execution order only. It does not make model responses reproducible.",
                     "execution_order": [f"{case_id}/{variant}" for case_id, variant in pairs]},
        "planned_calls": {"generation": len(pairs), "judge": len(pairs)},
    }
    run, run_dir, instructions = _start("compare", mode, cases_document, case_ids, ["A", "B"], config, label, extra)
    if config_errors:
        run["run_errors"] = config_errors
        return _finish(run, run_dir)
    prompts = {variant: data.load_text(data.RESPONSE_PROMPT_PATHS[variant]) for variant in ("A", "B")}
    for order, (case_id, variant) in enumerate(pairs, start=1):
        run["observations"].append(_generate_and_judge(order, cases[case_id], variant, 0, prompts[variant],
                                                       generator, judge_backend, instructions))
    return _finish(run, run_dir)


def run_repeat(mode: str, variant: str, case_ids: list[str], repetitions: int, **backend_options):
    cases_document = data.load_cases()
    cases = data.cases_by_id(cases_document)
    generator, judge_backend, config, label, config_errors = backends_for(mode, **backend_options)
    config["generation_settings"] = generator.settings()
    config["judge_settings"] = judge_backend.settings()
    extra = {"prompt_variant": variant, "repetitions": repetitions,
             "planned_calls": {"generation": len(case_ids) * repetitions, "judge": len(case_ids) * repetitions}}
    run, run_dir, instructions = _start("repeat", mode, cases_document, case_ids, [variant], config, label, extra)
    if config_errors:
        run["run_errors"] = config_errors
        return _finish(run, run_dir)
    prompt_text = data.load_text(data.RESPONSE_PROMPT_PATHS[variant])
    order = 0
    for case_id in case_ids:
        for repetition in range(repetitions):
            order += 1
            run["observations"].append(_generate_and_judge(order, cases[case_id], variant, repetition, prompt_text,
                                                           generator, judge_backend, instructions))
    return _finish(run, run_dir)


def run_access_check(environ=None, client_factory=None, sleep=None):
    """Billable preflight: one tiny request per distinct model (response model, then judge model)."""
    kwargs = {"environ": environ, "client_factory": client_factory}
    if sleep is not None:
        kwargs["sleep"] = sleep
    client = clients.LiveClient(**kwargs)
    run, run_dir = runs.create_run("access-check", "live", clients.LIVE_LABEL, {"config": {"source": "live", **client.config_record()}})
    run["run_errors"] = client.config_errors()
    if not run["run_errors"]:
        roles = {}
        for role, model in (("response model", client.response_model), ("judge model", client.judge_model)):
            roles.setdefault(model, []).append(role)
        for order, (model, model_roles) in enumerate(roles.items(), start=1):
            result = client.call(model, "Reply with the single word OK.", "Access check.", clients.ACCESS_CHECK_MAX_OUTPUT_TOKENS)
            run["observations"].append({"observation_id": f"obs-{order:03d}", "roles": model_roles,
                                        "check": result.record(), "status": "ok" if result.status == "ok" else "error"})
    runs.finalise(run, run_dir)
    reporting.write_results(run, run_dir)
    return run, run_dir
